from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from shutil import copyfile

import pytest
from pydantic import ValidationError

from ai_tutor_bench.runtime.contracts import ROOT, canonical, digest
from ai_tutor_bench.runtime.core.cell_plan import CellKeyV5, CellPlan, PlannedCell
from ai_tutor_bench.runtime.core.projection_revisions import (
    ANALYSIS_FILES,
    EXPORT_FILES,
    check_revisions,
)
from ai_tutor_bench.runtime.core.result_settlement import (
    AttemptResult,
    BillingReport,
    CellOutcome,
    SettlementRecord,
)
from ai_tutor_bench.runtime.core.revisions import EXECUTION_FILES, execution_revision
from ai_tutor_bench.runtime.core.start_journal import AttemptKey, StartEvent, StartJournal

RUN_ID = digest(b"test run")
FREEZE = digest(b"test freeze")


def key(turn: int) -> CellKeyV5:
    return CellKeyV5(
        run_id=RUN_ID, suite="suite", arm="arm", case="case", seed=42, role="tutor", turn=turn
    )


def started() -> StartEvent:
    return StartEvent(
        key=AttemptKey(run_id=RUN_ID, cell_id=key(1).identifier(), attempt_index=1),
        timestamp=datetime.now(UTC),
        execution_revision=digest(b"execution"),
        adapter_kind="openrouter",
        reserved_microusd=100,
    )


def test_plan_is_sorted_hashed_and_validated() -> None:
    first, second = key(1), key(2)
    plan = CellPlan.from_keys(RUN_ID, FREEZE, (second, first))
    assert tuple(cell.key for cell in plan.cells) == (first, second)
    assert plan.expected_cell_count == 2
    assert plan.plan_sha256 == CellPlan.from_keys(RUN_ID, FREEZE, (first, second)).plan_sha256
    assert plan.cells[0].cell_id == digest(
        canonical([RUN_ID, "suite", "arm", "case", 42, "tutor", 1])
    )
    assert CellPlan.model_validate_json(plan.model_dump_json()) == plan
    with pytest.raises(ValidationError, match="duplicate planned cell"):
        CellPlan.from_keys(RUN_ID, FREEZE, (first, first))
    with pytest.raises(ValidationError, match="cell_id differs"):
        PlannedCell(key=first, cell_id=second.identifier())


def test_journal_enforces_unique_attempt_between_writers(tmp_path: Path) -> None:
    event = started()
    journal = StartJournal(tmp_path / "starts.jsonl")
    with ThreadPoolExecutor(max_workers=2) as pool:
        writes = [pool.submit(journal.append, event) for _ in range(2)]
    rejected = [write.exception() for write in writes if write.exception() is not None]
    assert len(rejected) == 1
    assert isinstance(rejected[0], ValueError) and "duplicate attempt key" in str(rejected[0])
    assert journal.read() == {event.key: event}


@pytest.mark.parametrize(
    ("byok", "reported", "reserve"),
    [(None, 0, 100), (True, 19, 100), (False, None, 100), (False, 0, 0)],
)
def test_settlement_requires_charge_and_confirmed_non_byok(
    byok: bool | None, reported: int | None, reserve: int
) -> None:
    start = started()
    report = BillingReport(is_byok=byok, reported_microusd=reported)
    record = SettlementRecord.resolve(start, report)
    assert record.key == start.key
    assert record.billing_mode == report.mode
    assert record.reported_microusd == reported
    assert record.reserved_microusd == reserve


def test_attempt_rejects_negative_reasoning_usage() -> None:
    with pytest.raises(ValidationError, match="reasoning_tokens"):
        AttemptResult(
            key=started().key,
            outcome=CellOutcome.OK,
            raw="reply",
            visible_text="reply",
            finish_reason="stop",
            reasoning_tokens=-1,
        )


def test_only_the_reviewed_revision_domain_changes(tmp_path: Path) -> None:
    for name in (*EXECUTION_FILES, *EXPORT_FILES, *ANALYSIS_FILES):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(ROOT / name, target)
    before = check_revisions(tmp_path)
    reporting = tmp_path / "analyse/bestand.py"
    reporting.write_bytes(reporting.read_bytes() + b"\n# Reporting only\n")
    after = check_revisions(tmp_path)
    assert before.execution_revision == after.execution_revision
    assert before.export_revision == after.export_revision
    assert before.analysis_revision != after.analysis_revision

    export = tmp_path / "runtime/v5/export.py"
    export.write_bytes(export.read_bytes() + b"\n# Export only\n")
    changed_export = check_revisions(tmp_path)
    assert changed_export.export_revision != after.export_revision
    assert changed_export.execution_revision == after.execution_revision
    assert changed_export.analysis_revision == after.analysis_revision

    manifest = tmp_path / "runtime/core/projection_revisions.py"
    manifest.write_text('EXPORT_FILES = ("revised_projection.py",)\nANALYSIS_FILES = ()\n')
    assert execution_revision(tmp_path) == after.execution_revision

    execution = tmp_path / "runtime/v5/runner.py"
    execution.write_bytes(execution.read_bytes() + b"\n# Changed dispatch\n")
    assert check_revisions(tmp_path).execution_revision != after.execution_revision


def test_journal_discards_only_incomplete_last_record(tmp_path: Path) -> None:
    original = started()
    next_key = original.key.model_copy(update={"attempt_index": 2})
    following = original.model_copy(update={"key": next_key})
    path = tmp_path / "starts.jsonl"
    journal = StartJournal(path)
    journal.append(original)
    full = path.read_bytes()
    path.write_bytes(full + following.model_dump_json().encode()[:9])
    assert journal.read() == {original.key: original}
    journal.append(following)
    assert journal.read() == {original.key: original, next_key: following}
    assert path.read_bytes() == full + following.model_dump_json().encode() + b"\n"

    path.write_bytes(full + b'{"bad":\n')
    with pytest.raises(ValidationError):
        journal.read()
    with pytest.raises(ValidationError):
        journal.append(following)


def test_execution_rejects_duplicate_assets() -> None:
    name = "v5/prompts/same.txt"
    with pytest.raises(ValueError, match="duplicate execution asset"):
        execution_revision(ROOT, (name, name))


@pytest.mark.parametrize("field", ["run_id", "call_id"])
def test_settlement_rejects_mismatched_identity(field: str) -> None:
    record = SettlementRecord.resolve(started(), BillingReport(is_byok=False, reported_microusd=0))
    with pytest.raises(ValidationError, match="settlement identifiers"):
        SettlementRecord.model_validate(record.model_dump() | {field: "different"})


@pytest.mark.parametrize(("text", "reason"), [("   ", "stop"), ("visible", "other")])
def test_attempt_validates_visible_text_and_finish_reason(text: str, reason: str) -> None:
    with pytest.raises(ValidationError):
        AttemptResult.model_validate(
            {
                "key": started().key,
                "outcome": "ok",
                "raw": "reply",
                "visible_text": text,
                "finish_reason": reason,
            }
        )
