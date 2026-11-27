import ast
from collections import Counter
from importlib.util import resolve_name
from pathlib import Path
from shutil import copyfile

import pytest

from ai_tutor_bench.runtime.contracts import ROOT, digest
from ai_tutor_bench.runtime.core import export_receipt
from ai_tutor_bench.runtime.core.cell_plan import CellKeyV5, CellPlan, PlannedCell
from ai_tutor_bench.runtime.core.export_manifest import parse_rows, validate_cells
from ai_tutor_bench.runtime.core.export_receipt import ExportReceipt
from ai_tutor_bench.runtime.core.projection_revisions import EXPORT_FILES, export_revision
from ai_tutor_bench.runtime.core.result_settlement import (
    AttemptResult,
    BillingReport,
    CellOutcome,
    SettledAttempt,
)
from ai_tutor_bench.runtime.core.revisions import EXECUTION_FILES, execution_revision
from ai_tutor_bench.runtime.core.start_journal import AdapterKind, StartEvent, StartJournal
from ai_tutor_bench.runtime.v5.contracts import (
    AbortPolicy,
    AdapterProtocol,
    EpisodeHistory,
    V5RunSpec,
)
from ai_tutor_bench.runtime.v5.export import (
    BLIND_FILE,
    LAYOUT,
    NOTE_FILE,
    RAW_FILE,
    RECEIPT_FILE,
    export_index,
)
from ai_tutor_bench.runtime.v5.fixture import FixtureAdapter, fixture_spec
from ai_tutor_bench.runtime.v5.runner import RESULT_DIR, START_FILE, result_path
from ai_tutor_bench.runtime.v5.workflow import PRIVATE_EXPORT_DIR, run_benchmark


class InterruptedFixture(FixtureAdapter):
    def __init__(self, interrupt_after: int) -> None:
        super().__init__()
        self.calls: list[str] = []
        self.interrupt_after = interrupt_after

    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt:
        self.calls.append(cell.cell_id)
        if len(self.calls) == self.interrupt_after:
            raise KeyboardInterrupt
        return super().execute(cell, start, history)


def run_fixture(tmp_path: Path, adapter: AdapterProtocol, *, root: Path = ROOT) -> ExportReceipt:
    return run_benchmark(
        fixture_spec(),
        {("offline", "tutor"): adapter},
        tmp_path / "private",
        tmp_path / "public",
        root=root,
    )


def raw_path(tmp_path: Path) -> Path:
    return tmp_path / "private" / PRIVATE_EXPORT_DIR / RAW_FILE


def test_resume_never_dispatches_recorded_attempts(tmp_path: Path) -> None:
    plan = fixture_spec().plan
    fixture = InterruptedFixture(interrupt_after=2)
    with pytest.raises(KeyboardInterrupt):
        run_fixture(tmp_path, fixture)
    journal = StartJournal(tmp_path / "private" / START_FILE)
    assert len(journal.read()) == 2
    assert not (tmp_path / "public").exists()

    receipt = run_fixture(tmp_path, fixture)
    assert fixture.calls == [cell.cell_id for cell in plan.cells]
    assert len(journal.read()) == len(plan.cells)
    rows = parse_rows(raw_path(tmp_path).read_bytes())
    assert [row["status"] for row in rows] == ["ok", "abgebrochen", "ok"]
    assert receipt == run_fixture(tmp_path, fixture)
    assert len(fixture.calls) == len(plan.cells)


@pytest.mark.parametrize("duplicate", [False, True])
def test_export_rejects_wrong_cell_set(tmp_path: Path, duplicate: bool) -> None:
    run_fixture(tmp_path, FixtureAdapter())
    index = export_index(fixture_spec().plan)
    rows = parse_rows(raw_path(tmp_path).read_bytes())
    changed = [*rows, rows[0]] if duplicate else rows[:-1]
    message = "duplicate export cell" if duplicate else "missing export cell"
    with pytest.raises(ValueError, match=message):
        validate_cells(changed, index, LAYOUT)


def test_io_failure_in_publication_keeps_export_private_and_can_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(source: Path, target: Path) -> None:
        assert source.is_dir()
        assert target == tmp_path / "public"
        raise OSError("simulated publication failure")

    root = tmp_path / "checkout"
    for name in (*EXECUTION_FILES, *EXPORT_FILES, *fixture_spec().execution_assets):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(ROOT / name, target)
    fixture = InterruptedFixture(interrupt_after=0)
    with monkeypatch.context() as patch:
        patch.setattr(export_receipt, "publish_directory", fail)
        with pytest.raises(OSError, match="simulated publication failure"):
            run_fixture(tmp_path, fixture, root=root)
    assert not (tmp_path / "public").exists()
    assert raw_path(tmp_path).exists()
    private = raw_path(tmp_path).parent
    saved = ExportReceipt.model_validate_json((private / RECEIPT_FILE).read_bytes())
    export = root / "runtime/v5/export.py"
    export.write_bytes(export.read_bytes() + b"\n# Export only\n")
    assert saved.export_revision != export_revision(root)
    assert saved.execution_revision == execution_revision(root, fixture_spec().execution_assets)

    note = private / NOTE_FILE
    original_note = note.read_bytes()
    note.write_bytes(original_note + b"corrupt\n")
    with pytest.raises(ValueError, match="sealed export hash mismatch"):
        run_fixture(tmp_path, fixture, root=root)
    assert not (tmp_path / "public").exists()
    note.write_bytes(original_note)
    assert run_fixture(tmp_path, fixture, root=root) == saved
    assert saved.public.row_count == len(fixture.calls)
    assert max(Counter(fixture.calls).values()) == 1

    public = tmp_path / "public" / BLIND_FILE
    public.write_bytes(public.read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="export hash mismatch"):
        run_fixture(tmp_path, fixture, root=root)


class RewritingAdapter:
    identity = "test-adapter"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        self.calls = 0

    @property
    def kind(self) -> AdapterKind:
        return "simulator-cli" if self.reason == "censure" else "openrouter"

    def reserve(self, cell: PlannedCell) -> int:
        return 1

    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt:
        self.calls += 1
        return SettledAttempt(
            result=AttemptResult(
                key=start.key,
                outcome=CellOutcome.CENSORED if self.reason == "censure" else CellOutcome.OK,
                raw="raw",
                visible_text="text",
                finish_reason=None,
                identity_ok=self.reason != "identity",
            ),
            billing=BillingReport(is_byok=None, reported_microusd=0),
        )


@pytest.mark.parametrize(
    ("reason", "budget", "status"),
    [("censure", 100, "zensiert"), ("identity", 100, "ok"), ("budget", 1, "ok")],
)
def test_abort_policy_stops_dispatch(tmp_path: Path, reason: str, budget: int, status: str) -> None:
    spec = V5RunSpec(
        plan=fixture_spec().plan,
        abort_policy=AbortPolicy(budget_microusd=budget, max_subscription_censures=1),
    )
    adapter = RewritingAdapter(reason)
    receipt = run_benchmark(
        spec, {("offline", "tutor"): adapter}, tmp_path / "private", tmp_path / "public"
    )
    assert adapter.calls == 1
    private = parse_rows(raw_path(tmp_path).read_bytes())
    assert [row["status"] for row in private] == [status, "nicht_gestartet", "nicht_gestartet"]
    assert receipt.completeness == "partiell"
    if reason == "identity":
        assert receipt.abort_reason == "identity_violation"
        assert not (tmp_path / "public").exists()


def test_entire_runner_import_tree_matches_execution_manifest() -> None:
    assert import_tree("ai_tutor_bench.runtime.v5.runner") == {"__init__.py", *EXECUTION_FILES}
    import_tree("ai_tutor_bench.runtime.v5.__main__")


def import_tree(entry: str) -> set[str]:
    pending = [entry]
    inspected: set[str] = set()
    historical = {f"v{version}" for version in range(1, 5)}
    while pending:
        name = pending.pop()
        parts = name.split(".")
        if parts[0] != "ai_tutor_bench":
            continue
        assert not historical.intersection(parts[1:3]), name
        path = ROOT.parent.joinpath(*parts)
        source = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
        relative = source.relative_to(ROOT).as_posix()
        if relative in inspected or not source.is_file():
            continue
        inspected.add(relative)
        package = ".".join(source.parent.relative_to(ROOT.parent).parts)
        pending.extend(".".join(parts[:length]) for length in range(1, len(parts)))
        for node in ast.walk(ast.parse(source.read_bytes(), filename=str(source))):
            pending.extend(imported_modules(node, package))
    return inspected


def imported_modules(node: ast.AST, package: str) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        module = resolve_name("." * node.level + (node.module or ""), package)
        return [module, *(f"{module}.{alias.name}" for alias in node.names)]
    return []


class RecordingAdapter:
    identity = "role-adapter"

    def __init__(
        self,
        kind: AdapterKind,
        *,
        fail_at: str = "",
        outcome: CellOutcome = CellOutcome.OK,
        identity_ok: bool = True,
        interrupt: bool = False,
    ) -> None:
        self.kind = kind
        self.fail_at = fail_at
        self.outcome = outcome
        self.identity_ok = identity_ok
        self.interrupt = interrupt
        self.calls: list[tuple[str, tuple[str | None, ...]]] = []

    def reserve(self, cell: PlannedCell) -> int:
        return 0

    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt:
        label = f"{cell.key.case}:{cell.key.role}:{cell.key.turn}"
        self.calls.append((label, tuple(result.visible_text for result in history)))
        failing = label == self.fail_at
        if failing and self.interrupt:
            raise KeyboardInterrupt
        return SettledAttempt(
            result=AttemptResult(
                key=start.key,
                outcome=self.outcome if failing else CellOutcome.OK,
                raw=label,
                visible_text=label,
                finish_reason="stop",
                identity_ok=not failing or self.identity_ok,
            ),
            billing=BillingReport(is_byok=False, reported_microusd=0),
        )


def dialogue_spec(max_censures: int = 1) -> V5RunSpec:
    run_id = digest(b"dialogue")
    keys = tuple(
        CellKeyV5(run_id=run_id, suite="s", arm="arm", case=case, seed=42, role=role, turn=turn)
        for case, turns in (("first", 2), ("second", 1))
        for turn in range(1, turns + 1)
        for role in ("tutor", "learner")
    )
    return V5RunSpec(
        plan=CellPlan.from_keys(run_id, digest(b"dialogue freeze"), keys),
        abort_policy=AbortPolicy(budget_microusd=0, max_subscription_censures=max_censures),
    )


def run_dialogue(
    tmp_path: Path, learner: AdapterProtocol, tutor: AdapterProtocol, max_censures: int = 1
) -> ExportReceipt:
    return run_benchmark(
        dialogue_spec(max_censures),
        {("arm", "learner"): learner, ("arm", "tutor"): tutor},
        tmp_path / "private",
        tmp_path / "public",
    )


def test_multi_adapter_resume_reconstructs_episode_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    learner = RecordingAdapter("simulator-cli")
    tutor = RecordingAdapter("openrouter")
    append = StartJournal.append

    def stop_before_dispatch(journal: StartJournal, event: StartEvent) -> None:
        if event.adapter_kind == "openrouter":
            raise OSError("stopped before starting tutor")
        append(journal, event)

    with monkeypatch.context() as patch:
        patch.setattr(StartJournal, "append", stop_before_dispatch)
        with pytest.raises(OSError, match="stopped before starting tutor"):
            run_dialogue(tmp_path, learner, tutor)
    assert not tutor.calls
    assert run_dialogue(tmp_path, learner, tutor).completeness == "vollstaendig"
    assert tutor.calls == [
        ("first:tutor:1", ("first:learner:1",)),
        ("first:tutor:2", ("first:learner:1", "first:tutor:1", "first:learner:2")),
        ("second:tutor:1", ("second:learner:1",)),
    ]
    rows = parse_rows(raw_path(tmp_path).read_bytes())
    assert len({row["episode"] for row in rows[:4]}) == 1
    assert all(isinstance(plan := row["plan"], dict) and plan["turns"] == 2 for row in rows[:4])


@pytest.mark.parametrize("interrupt", [True, False])
def test_failed_episode_censors_following_cells_only(tmp_path: Path, interrupt: bool) -> None:
    learner = RecordingAdapter("simulator-cli")
    tutor = RecordingAdapter(
        "openrouter", fail_at="first:tutor:1", outcome=CellOutcome.TECHNICAL, interrupt=interrupt
    )
    if interrupt:
        with pytest.raises(KeyboardInterrupt):
            run_dialogue(tmp_path, learner, tutor)
    receipt = run_dialogue(tmp_path, learner, tutor)
    assert receipt.completeness == "partiell" and receipt.abort_reason is None
    rows = parse_rows(raw_path(tmp_path).read_bytes())
    expected = "abgebrochen" if interrupt else "technisch"
    assert [row["status"] for row in rows] == ["ok", expected, "zensiert", "zensiert", "ok", "ok"]
    assert [label for label, _ in learner.calls] == ["first:learner:1", "second:learner:1"]
    assert [label for label, _ in tutor.calls] == ["first:tutor:1", "second:tutor:1"]


def test_simulator_censure_limit_across_roles(tmp_path: Path) -> None:
    learner = RecordingAdapter(
        "simulator-cli", fail_at="first:learner:2", outcome=CellOutcome.CENSORED
    )
    tutor = RecordingAdapter("openrouter")
    receipt = run_dialogue(tmp_path, learner, tutor)
    assert receipt.abort_reason == "subscription_censure_limit"
    assert tutor.calls == [("first:tutor:1", ("first:learner:1",))]
    assert [row["status"] for row in parse_rows(raw_path(tmp_path).read_bytes())] == [
        "ok",
        "ok",
        "zensiert",
        "zensiert",
        "nicht_gestartet",
        "nicht_gestartet",
    ]


def test_identity_violation_in_last_cell_blocks_publication(tmp_path: Path) -> None:
    learner = RecordingAdapter("simulator-cli")
    tutor = RecordingAdapter("openrouter", fail_at="second:tutor:1", identity_ok=False)
    receipt = run_dialogue(tmp_path, learner, tutor)
    assert receipt.abort_reason == "identity_violation"
    assert receipt.completeness == "partiell"
    assert not (tmp_path / "public").exists()
    note = (raw_path(tmp_path).parent / NOTE_FILE).read_text()
    assert (
        receipt.execution_revision in note and "identity_violation" in note and "partiell" in note
    )
    assert "gesperrt" in note
    assert receipt == run_dialogue(tmp_path, learner, tutor)
    assert not (tmp_path / "public").exists()


def test_attempt_history_retains_older_settlements(tmp_path: Path) -> None:
    fixture = InterruptedFixture(interrupt_after=1)
    with pytest.raises(KeyboardInterrupt):
        run_fixture(tmp_path, fixture)
    private = tmp_path / "private"
    journal = StartJournal(private / START_FILE)
    (original,) = journal.read().values()
    retry_key = original.key.model_copy(update={"attempt_index": 2})
    retry = original.model_copy(update={"key": retry_key})
    journal.append(retry)
    cell = fixture_spec().plan.cells[0]
    result = FixtureAdapter().execute(cell, retry, ())
    result_path(private / RESULT_DIR, retry_key).write_text(result.model_dump_json())

    run_fixture(tmp_path, fixture)
    first = parse_rows(raw_path(tmp_path).read_bytes())[0]
    entries = first["attempts"]
    assert isinstance(entries, list)
    assert [entry["status"] for entry in entries if isinstance(entry, dict)] == [
        "abgebrochen",
        "ok",
    ]
    assert [
        entry["settlement"]["call_id"]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry["settlement"], dict)
    ] == [f"{cell.cell_id}:1", f"{cell.cell_id}:2"]
