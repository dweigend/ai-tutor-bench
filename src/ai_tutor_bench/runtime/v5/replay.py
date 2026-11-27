"""Verify blind releases and optionally recompute private outcome counts."""

from collections import Counter
from pathlib import Path

from pydantic import Field

from ..contracts import Contract, canonical, digest
from ..core.cell_plan import CellPlan
from ..core.export_manifest import parse_rows, validate_export_rows
from ..core.export_receipt import ExportReceipt, PublicReceipt, verify_files
from ..core.result_settlement import CellOutcome, SettlementRecord
from .contracts import BoundRun
from .export import (
    BLIND_FILE,
    BLIND_SIDECAR,
    LAYOUT,
    NOTE_FILE,
    RAW_FILE,
    RAW_SIDECAR,
    RECEIPT_FILE,
    check_projection_text,
    checked_bytes,
    export_index,
    public_projection,
    validate_visible_text,
)
from .runner import RUN_FILE
from .workflow import PRIVATE_EXPORT_DIR


class BlindRow(Contract):
    blind_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    text: str | None


def replay_public(directory: Path, expected: int) -> tuple[PublicReceipt, int]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("public export must be a regular directory")
    if {path.name for path in directory.iterdir()} != {BLIND_FILE, BLIND_SIDECAR}:
        raise ValueError("unexpected public file set")
    sidecar = directory / BLIND_SIDECAR
    if sidecar.is_symlink() or not sidecar.is_file():
        raise ValueError("public sidecar must be a regular file")
    receipt = PublicReceipt.model_validate_json(sidecar.read_bytes())
    payload = checked_bytes(directory, BLIND_FILE, receipt.file_sha256)
    rows = [BlindRow.model_validate(row) for row in parse_rows(payload)]
    if len({row.blind_id for row in rows}) != len(rows) or len(rows) != receipt.row_count:
        raise ValueError("invalid blind row count or repeated blind identifier")
    if receipt.row_count != expected:
        raise ValueError("public row count differs from the frozen denominator")
    if b"".join(sorted(canonical(row.model_dump()) + b"\n" for row in rows)) != payload:
        raise ValueError("blind projection must be canonical and sorted")
    for row in rows:
        validate_visible_text(row.text, ())
    return receipt, sum(row.text is not None for row in rows)


def replay_private(
    directory: Path, public: Path, plan: CellPlan, public_receipt: PublicReceipt
) -> dict[str, object]:
    run = BoundRun.model_validate_json((directory / RUN_FILE).read_bytes())
    if run.spec.plan != plan:
        raise ValueError("private run differs from the frozen run plan")
    export = directory / PRIVATE_EXPORT_DIR
    receipt = ExportReceipt.model_validate_json((export / RECEIPT_FILE).read_bytes())
    if (
        receipt.plan_sha256 != plan.plan_sha256
        or receipt.execution_revision != run.execution_revision
        or receipt.public != public_receipt
        or receipt.abort_reason == "identity_violation"
    ):
        raise ValueError("private receipt differs from the frozen plan or public receipt")
    checked_bytes(export, RAW_FILE, receipt.private_raw_sha256)
    checked_bytes(export, RAW_SIDECAR, receipt.private_manifest_sha256)
    checked_bytes(export, NOTE_FILE, receipt.note_sha256)
    rows = validate_export_rows(
        export / RAW_FILE, index=export_index(plan), freeze_sha256=plan.freeze_sha256, layout=LAYOUT
    )
    projected, blind, sidecar = public_projection(rows)
    if projected != public_receipt or digest(sidecar) != receipt.public_sidecar_sha256:
        raise ValueError("reconstructed projection differs from the receipt")
    check_projection_text(
        blind, rows, (plan.run_id, *(binding.identity for binding in run.bindings))
    )
    verify_files(public, {BLIND_FILE: blind, BLIND_SIDECAR: sidecar})
    counts = Counter(row["status"] for row in rows if isinstance(row["status"], str))
    cost = 0
    for row in rows:
        attempts = row["attempts"]
        if not isinstance(attempts, list):
            raise ValueError("private attempts must be a list")
        for attempt in attempts:
            if not isinstance(attempt, dict):
                raise ValueError("private attempt must be a record")
            settlement = SettlementRecord.model_validate(attempt["settlement"])
            cost += (settlement.reported_microusd or 0) + settlement.reserved_microusd
    return {
        "outcomes": {status.value: counts[status] for status in CellOutcome},
        "cost_microusd": cost,
    }
