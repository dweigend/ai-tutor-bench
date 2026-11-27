"""Project verified cells and stage the exact public bytes for crash recovery."""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from pydantic import JsonValue, TypeAdapter

from ..contracts import canonical, digest
from ..core.cell_plan import CellPlan, EpisodeKey, PlannedCell
from ..core.export_manifest import (
    CellKey,
    ExportIndex,
    ExportLayout,
    ExportManifest,
    RawRow,
    parse_rows,
    sidecar_path,
    validate_export_rows,
    write_raw_export,
)
from ..core.export_receipt import ExportReceipt, PublicReceipt, publish_files, verify_files
from ..core.primitives import Turn, sync_path, write_verified
from ..core.publish import publish_directory
from ..core.result_settlement import BillingReport, CellOutcome, SettledAttempt, SettlementRecord
from ..core.start_journal import StartEvent
from .adapters.alternate import AlternateAdapter
from .fixture import FixtureAdapter
from .runner import RunSnapshot

RAW_FILE = "raw.jsonl"
BLIND_FILE = "blind.jsonl"
RECEIPT_FILE = "receipt.json"
NOTE_FILE = "laufnotiz.md"
BLIND_SIDECAR = sidecar_path(Path(BLIND_FILE)).name
RAW_SIDECAR = sidecar_path(Path(RAW_FILE)).name
# A slash inside a word, fraction, or URL does not start a local path.
LOCAL_PATH = re.compile(
    r"(?:file://|\b[A-Z]:[\\/]|\\\\[\w.?-]+[\\/]"
    r"|(?<![\w:/])//[\w.-]|(?<![\w/])/[\w.$~-])",
    re.IGNORECASE,
)
BUNDLED_IDENTITIES = (FixtureAdapter.identity, AlternateAdapter.identity)
DRIFT_IDENTITY = re.compile(r"(?<!\w)offline-drift-(?:learner|tutor):[0-9a-f]{64}(?!\w)")
ROLE_TURNS = TypeAdapter(tuple[tuple[str, Turn], ...])


def raw_plan(episode: EpisodeKey, cells: Iterable[PlannedCell]) -> RawRow:
    suite, arm, case, seed = episode
    keys = [(cell.key.role, cell.key.turn) for cell in cells]
    return {
        "suite": suite,
        "arm": arm,
        "case": case,
        "seed": seed,
        "turns": max(turn for _, turn in keys),
        "cell_keys": [[role, turn] for role, turn in keys],
    }


def episode_plans(plan: CellPlan) -> dict[EpisodeKey, RawRow]:
    return {
        episode: raw_plan(episode, cells)
        for episode, cells in groupby(plan.cells, key=lambda cell: cell.key.episode())
    }


def planned_keys(plans: Mapping[str, RawRow]) -> Iterable[CellKey]:
    for episode, plan in plans.items():
        for role, turn in ROLE_TURNS.validate_python(plan["cell_keys"]):
            yield episode, role, turn


LAYOUT = ExportLayout(planned_keys, tuple(CellOutcome), include_role=True)


def episode_id(plan: CellPlan, raw: RawRow) -> str:
    return digest(canonical([plan.run_id, raw]))


def export_index(plan: CellPlan) -> ExportIndex:
    plans = {episode_id(plan, raw): raw for raw in episode_plans(plan).values()}
    return ExportIndex(
        run_id=plan.run_id,
        freeze_sha256=plan.freeze_sha256,
        expected_keys=tuple(planned_keys(plans)),
    )


def raw_rows(snapshot: RunSnapshot) -> list[RawRow]:
    attempts: dict[str, list[RawRow]] = {}
    for key in sorted(snapshot.events, key=lambda key: key.attempt_index):
        entry = attempt_row(snapshot.events[key], snapshot.results.get(key))
        attempts.setdefault(key.cell_id, []).append(entry)

    run = snapshot.run
    plan = run.spec.plan
    episodes = episode_plans(plan)
    adapters = {binding.key: binding.identity for binding in run.bindings}
    censored = set(snapshot.summary.censored_cells)
    rows: list[RawRow] = []
    for cell in plan.cells:
        key = cell.key
        raw = episodes[key.episode()]
        entries = attempts.get(cell.cell_id, [])
        attempt_log: list[JsonValue] = list(entries)
        row: RawRow = {
            "episode": episode_id(plan, raw),
            "role": key.role,
            "turn": key.turn,
            "plan": raw,
            "cell_id": cell.cell_id,
            "blind_id": uuid4().hex,
            "model": adapters[key.arm, key.role],
            "execution_revision": run.execution_revision,
            "freeze_sha256": plan.freeze_sha256,
            "attempts": attempt_log,
        }
        row.update(entries[-1] if entries else unstarted_row(cell.cell_id in censored))
        rows.append(row)
    return rows


def unstarted_row(censored: bool) -> RawRow:
    status = CellOutcome.CENSORED if censored else CellOutcome.NOT_STARTED
    return {"status": status.value, "start": None, "result": None, "settlement": None}


def attempt_row(start: StartEvent, completion: SettledAttempt | None) -> RawRow:
    if completion is None:
        unknown = BillingReport(is_byok=None, reported_microusd=None)
        outcome, settlement = CellOutcome.ABORTED, SettlementRecord.resolve(start, unknown)
    else:
        outcome, settlement = completion.result.outcome, completion.settlement_for(start)
    return {
        "status": outcome.value,
        "start": start.model_dump(mode="json"),
        "result": completion.result.model_dump(mode="json") if completion else None,
        "settlement": settlement.model_dump(mode="json"),
    }


def public_projection(rows: list[RawRow]) -> tuple[PublicReceipt, bytes, bytes]:
    blind_rows = [
        canonical({"blind_id": row["blind_id"], "text": public_text(row)}) + b"\n" for row in rows
    ]
    # Plan order exposes the arm and case ordering.
    data = b"".join(sorted(blind_rows))
    receipt = PublicReceipt(file_sha256=digest(data), row_count=len(rows))
    return receipt, data, receipt.model_dump_json().encode() + b"\n"


def public_text(row: RawRow) -> str | None:
    if row["status"] not in (CellOutcome.OK, CellOutcome.TRUNCATED):
        return None
    result = row["result"]
    if not isinstance(result, dict) or result.get("identity_ok") is not True:
        return None
    text = result.get("visible_text")
    return text if isinstance(text, str) else None


def validate_visible_text(text: str | None, private_identifiers: Iterable[str]) -> None:
    if text is None:
        return
    normalized = unicodedata.normalize("NFKC", text).casefold()
    if LOCAL_PATH.search(normalized):
        raise ValueError("blind text contains a local path")
    if DRIFT_IDENTITY.search(normalized):
        raise ValueError("blind text contains a bundled adapter identifier")
    for identifier in (*BUNDLED_IDENTITIES, *private_identifiers):
        token = unicodedata.normalize("NFKC", identifier).casefold()
        if token and re.search(rf"(?<!\w){re.escape(token)}(?!\w)", normalized):
            raise ValueError("blind text contains an adapter or private identifier")


def run_note(snapshot: RunSnapshot, rows: list[RawRow]) -> bytes:
    summary = snapshot.summary
    counts = {outcome: sum(row["status"] == outcome for row in rows) for outcome in CellOutcome}
    reason = summary.abort_reason or "keiner"
    lines = [
        "# v5-Laufnotiz",
        "",
        f"Sollmenge {snapshot.run.spec.plan.expected_cell_count} Zellen.",
        f"Begonnene Versuche {len(snapshot.events)}.",
        f"Beobachtete Texte {sum(public_text(row) is not None for row in rows)}.",
        f"Freeze `{snapshot.run.spec.plan.freeze_sha256}`.",
        f"Ausführungsrevision `{snapshot.run.execution_revision}`.",
        f"Vollständigkeit `{summary.completeness}`. Abbruchgrund `{reason}`.",
        "",
    ]
    if summary.abort_reason == "identity_violation":
        lines.extend(
            ["Die öffentliche Publikation ist wegen des Identitätsverstoßes gesperrt.", ""]
        )
    lines.extend(f"- {outcome.value}: {count}" for outcome, count in counts.items())
    return ("\n".join(lines) + "\n").encode()


def stage_export(directory: Path, snapshot: RunSnapshot, export_revision: str) -> None:
    plan = snapshot.run.spec.plan
    raw = directory / RAW_FILE
    index = export_index(plan)
    write_raw_export(raw, raw_rows(snapshot), index, layout=LAYOUT)
    rows = validate_export_rows(raw, index=index, freeze_sha256=plan.freeze_sha256, layout=LAYOUT)
    public, blind, sidecar = public_projection(rows)
    note = run_note(snapshot, rows)
    receipt = ExportReceipt(
        plan_sha256=plan.plan_sha256,
        execution_revision=snapshot.run.execution_revision,
        export_revision=export_revision,
        abort_reason=snapshot.summary.abort_reason,
        completeness=snapshot.summary.completeness,
        private_raw_sha256=digest(raw.read_bytes()),
        private_manifest_sha256=digest(sidecar_path(raw).read_bytes()),
        note_sha256=digest(note),
        public_sidecar_sha256=digest(sidecar),
        public=public,
    )
    write_verified(directory / BLIND_FILE, blind)
    write_verified(directory / BLIND_SIDECAR, sidecar)
    write_verified(directory / NOTE_FILE, note)
    write_verified(directory / RECEIPT_FILE, receipt.model_dump_json().encode() + b"\n")
    for path in directory.iterdir():
        sync_path(path)


def check_projection_text(
    data: bytes, rows: list[RawRow], private_identifiers: Iterable[str]
) -> None:
    identifiers = set(private_identifiers)
    identifiers.update(
        value
        for row in rows
        for value in (row["cell_id"], row["episode"])
        if isinstance(value, str)
    )
    for row in parse_rows(data):
        text = row.get("text")
        validate_visible_text(text if isinstance(text, str) else None, identifiers)


def checked_bytes(directory: Path, name: str, sha256: str) -> bytes:
    path = directory / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"sealed export requires a regular file: {name}")
    data = path.read_bytes()
    if digest(data) != sha256:
        raise ValueError(f"sealed export hash mismatch: {name}")
    return data


def load_sealed(directory: Path, snapshot: RunSnapshot) -> tuple[ExportReceipt, dict[str, bytes]]:
    path = directory / RECEIPT_FILE
    if path.is_symlink():
        raise ValueError("sealed export receipt must be a regular file")
    receipt = ExportReceipt.model_validate_json(path.read_bytes())
    plan = snapshot.run.spec.plan
    if (
        receipt.plan_sha256 != plan.plan_sha256
        or receipt.execution_revision != snapshot.run.execution_revision
        or receipt.abort_reason != snapshot.summary.abort_reason
        or receipt.completeness != snapshot.summary.completeness
        or receipt.public.row_count != plan.expected_cell_count
    ):
        raise ValueError("sealed export receipt differs from the completed run")

    checked_bytes(directory, RAW_FILE, receipt.private_raw_sha256)
    manifest = ExportManifest.model_validate_json(
        checked_bytes(directory, RAW_SIDECAR, receipt.private_manifest_sha256)
    )
    if (
        manifest.file_sha256 != receipt.private_raw_sha256
        or manifest.run_id != plan.run_id
        or manifest.freeze_sha256 != plan.freeze_sha256
        or manifest.row_count != receipt.public.row_count
    ):
        raise ValueError("sealed export manifest differs from the receipt")
    checked_bytes(directory, NOTE_FILE, receipt.note_sha256)
    files = {
        BLIND_FILE: checked_bytes(directory, BLIND_FILE, receipt.public.file_sha256),
        BLIND_SIDECAR: checked_bytes(directory, BLIND_SIDECAR, receipt.public_sidecar_sha256),
    }
    if PublicReceipt.model_validate_json(files[BLIND_SIDECAR]) != receipt.public:
        raise ValueError("sealed blind sidecar differs from the receipt")
    return receipt, files


def publish_run(
    private: Path, public: Path, snapshot: RunSnapshot, export_revision: str | None
) -> ExportReceipt:
    if not private.exists():
        if public.exists() or public.is_symlink():
            raise FileExistsError(public)
        if export_revision is None:
            raise ValueError("new export requires an export revision")
        with TemporaryDirectory(dir=private.parent) as staging:
            directory = Path(staging)
            stage_export(directory, snapshot, export_revision)
            load_sealed(directory, snapshot)
            publish_directory(directory, private)
    receipt, files = load_sealed(private, snapshot)
    if receipt.abort_reason == "identity_violation":
        return receipt
    check_projection_text(
        files[BLIND_FILE],
        parse_rows((private / RAW_FILE).read_bytes()),
        (snapshot.run.spec.plan.run_id, *(binding.identity for binding in snapshot.run.bindings)),
    )
    if not public.exists():
        publish_files(public, files)
    verify_files(public, files)
    return receipt
