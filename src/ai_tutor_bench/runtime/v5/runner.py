"""Execute a frozen v5 plan and resume from durable attempt records."""

import fcntl
import os
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from ..contracts import ROOT, canonical
from ..core.cell_plan import EpisodeKey, PlannedCell
from ..core.primitives import PRIVATE_DIRECTORY_MODE, sync_path, write_verified
from ..core.result_settlement import AttemptResult, CellOutcome, SettledAttempt
from ..core.revisions import execution_revision
from ..core.run_summary import AbortReason, RunSummary
from ..core.start_journal import FIRST_ATTEMPT, AttemptKey, StartEvent, StartJournal
from .contracts import (
    AbortPolicy,
    AdapterKey,
    AdapterProtocol,
    BoundRun,
    EpisodeHistory,
    V5RunSpec,
)

RUN_FILE = "run.json"
START_FILE = "starts.jsonl"
RESULT_DIR = "results"
SUMMARY_FILE = "summary.json"
NON_OWNER_PERMISSIONS = 0o077


@dataclass
class DispatchLimit:
    remaining: int

    def take(self) -> None:
        if self.remaining == 0:
            raise RunPaused
        self.remaining -= 1


class RunPaused(Exception):
    """Stop at a cell boundary while leaving a resumable journal."""


@dataclass
class RunUsage:
    allocated_microusd: int = 0
    subscription_censures: int = 0
    identity_violation: bool = False

    def record(self, start: StartEvent, completion: SettledAttempt | None) -> None:
        if completion is None:
            self.allocated_microusd += start.reserved_microusd
            return
        settlement = completion.settlement_for(start)
        self.allocated_microusd += settlement.reported_microusd or 0
        self.allocated_microusd += settlement.reserved_microusd
        if (
            start.adapter_kind == "simulator-cli"
            and completion.result.outcome == CellOutcome.CENSORED
        ):
            self.subscription_censures += 1
        self.identity_violation |= not completion.result.identity_ok

    def abort_reason(self, policy: AbortPolicy) -> AbortReason | None:
        if self.identity_violation:
            return "identity_violation"
        if self.subscription_censures >= policy.max_subscription_censures:
            return "subscription_censure_limit"
        if self.allocated_microusd > policy.budget_microusd:
            return "budget_limit"
        return None


@dataclass
class RunJournal:
    starts: StartJournal
    results_dir: Path
    events: dict[AttemptKey, StartEvent]
    results: dict[AttemptKey, SettledAttempt]

    def dispatch(
        self,
        adapter: AdapterProtocol,
        cell: PlannedCell,
        start: StartEvent,
        history: EpisodeHistory,
    ) -> SettledAttempt:
        # Raw replies remain owned by the journal even while an adapter sees their values.
        context = tuple(reply.model_copy(deep=True) for reply in history)
        self.starts.append(start)
        self.events[start.key] = start
        reply = adapter.execute(cell, start, context)
        completion = SettledAttempt.model_validate(reply.model_dump())
        completion.settlement_for(start)
        path = result_path(self.results_dir, start.key)
        persist(path, canonical(completion.model_dump(mode="json")) + b"\n")
        self.results[start.key] = completion
        return completion

    def usage(self) -> RunUsage:
        usage = RunUsage()
        for key, start in self.events.items():
            usage.record(start, self.results.get(key))
        return usage


@dataclass(frozen=True)
class RunSnapshot:
    run: BoundRun
    summary: RunSummary
    events: Mapping[AttemptKey, StartEvent]
    results: Mapping[AttemptKey, SettledAttempt]


def result_path(directory: Path, key: AttemptKey) -> Path:
    return directory / f"{key.cell_id}-{key.attempt_index}.json"


def persist(path: Path, data: bytes) -> None:
    with TemporaryDirectory(dir=path.parent) as staging:
        source = Path(staging) / path.name
        write_verified(source, data)
        sync_path(source)
        path.hardlink_to(source)
        sync_path(path.parent)


def bind_run(directory: Path, run: BoundRun) -> None:
    path = directory / RUN_FILE
    if not path.exists():
        persist(path, run.model_dump_json().encode() + b"\n")
    if BoundRun.model_validate_json(path.read_bytes()) != run:
        raise ValueError("run specification, execution revision or adapters differ from saved run")


def load_starts(journal: StartJournal, run: BoundRun) -> dict[AttemptKey, StartEvent]:
    starts = journal.read()
    adapters = {binding.key: binding.kind for binding in run.bindings}
    planned = {cell.cell_id: adapters[cell.key.arm, cell.key.role] for cell in run.spec.plan.cells}
    for key, start in starts.items():
        if key.run_id != run.spec.plan.run_id or key.cell_id not in planned:
            raise ValueError(f"attempt outside v5 plan: {key}")
        if (start.execution_revision, start.adapter_kind) != (
            run.execution_revision,
            planned[key.cell_id],
        ):
            raise ValueError(f"attempt does not match the bound run: {key}")
    return starts


def load_results(
    directory: Path, starts: dict[AttemptKey, StartEvent]
) -> dict[AttemptKey, SettledAttempt]:
    results: dict[AttemptKey, SettledAttempt] = {}
    for path in directory.glob("*.json"):
        completion = SettledAttempt.model_validate_json(path.read_bytes())
        key = completion.result.key
        if key not in starts or path != result_path(directory, key):
            raise ValueError(f"result has no matching start: {path.name}")
        completion.settlement_for(starts[key])
        results[key] = completion
    return results


def start_event(run: BoundRun, cell: PlannedCell, adapter: AdapterProtocol) -> StartEvent:
    return StartEvent(
        key=AttemptKey(run_id=cell.key.run_id, cell_id=cell.cell_id, attempt_index=FIRST_ATTEMPT),
        timestamp=datetime.now(UTC),
        execution_revision=run.execution_revision,
        adapter_kind=adapter.kind,
        reserved_microusd=adapter.reserve(cell),
    )


def execute_cells(
    run: BoundRun,
    adapters: Mapping[AdapterKey, AdapterProtocol],
    journal: RunJournal,
    limit: DispatchLimit | None = None,
) -> RunSummary:
    usage = journal.usage()
    policy = run.spec.abort_policy
    reason = usage.abort_reason(policy)
    latest = {key.cell_id: key for key in sorted(journal.events, key=lambda key: key.attempt_index)}
    histories: dict[EpisodeKey, list[AttemptResult]] = {}
    failed_episodes: set[EpisodeKey] = set()
    censored: list[str] = []
    completed = 0
    for cell in run.spec.plan.cells:
        episode = cell.key.episode()
        history = histories.setdefault(episode, [])
        saved = latest.get(cell.cell_id)
        if saved is not None:
            completion = journal.results.get(saved)
        else:
            if episode in failed_episodes:
                censored.append(cell.cell_id)
                continue
            if reason is not None:
                continue
            adapter = adapters[cell.key.arm, cell.key.role]
            start = start_event(run, cell, adapter)
            if usage.allocated_microusd + start.reserved_microusd > policy.budget_microusd:
                reason = "budget_limit"
                continue
            if limit is not None:
                limit.take()
            completion = journal.dispatch(adapter, cell, start, tuple(history))
            usage.record(start, completion)
            reason = usage.abort_reason(policy)

        if completion is not None and completion.result.outcome == CellOutcome.OK:
            history.append(completion.result)
            completed += 1
        else:
            failed_episodes.add(episode)

    return RunSummary(
        abort_reason=reason,
        completeness=(
            "vollstaendig"
            if reason is None and completed == run.spec.plan.expected_cell_count
            else "partiell"
        ),
        censored_cells=tuple(censored),
    )


@contextmanager
def lock_run(directory: Path) -> Generator[None]:
    directory.mkdir(mode=PRIVATE_DIRECTORY_MODE, exist_ok=True)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if os.fstat(fd).st_mode & NON_OWNER_PERMISSIONS:
            raise ValueError(f"run directory must be private: {directory}")
        sync_path(directory.parent)
        yield
    finally:
        os.close(fd)


@contextmanager
def execute_run(
    spec: V5RunSpec,
    adapters: Mapping[AdapterKey, AdapterProtocol],
    private: Path,
    *,
    root: Path = ROOT,
    stop_after: int | None = None,
) -> Generator[RunSnapshot]:
    run = BoundRun.bind(spec, execution_revision(root, spec.execution_assets), adapters)
    with lock_run(private):
        bind_run(private, run)
        starts = StartJournal(private / START_FILE)
        events = load_starts(starts, run)
        directory = private / RESULT_DIR
        directory.mkdir(exist_ok=True)
        sync_path(private)
        journal = RunJournal(starts, directory, events, load_results(directory, events))
        summary_path = private / SUMMARY_FILE
        if not summary_path.exists():
            limit = DispatchLimit(stop_after) if stop_after is not None else None
            summary = execute_cells(run, adapters, journal, limit)
            persist(summary_path, summary.model_dump_json().encode() + b"\n")
        else:
            summary = RunSummary.model_validate_json(summary_path.read_bytes())
            if journal.usage().identity_violation != (summary.abort_reason == "identity_violation"):
                raise ValueError("run summary differs from the journal's identity evidence")
        yield RunSnapshot(run, summary, journal.events, journal.results)
