"""Exercise detached manifests against an independent v5 plan."""

import json
from pathlib import Path

import pytest

from ai_tutor_bench.runtime.contracts import digest
from ai_tutor_bench.runtime.core.export_manifest import (
    ExportManifest,
    parse_rows,
    sidecar_path,
    validate_export_rows,
)
from ai_tutor_bench.runtime.v5.export import LAYOUT, RAW_FILE, export_index
from ai_tutor_bench.runtime.v5.fixture import FixtureAdapter, fixture_spec
from ai_tutor_bench.runtime.v5.workflow import PRIVATE_EXPORT_DIR, run_benchmark


@pytest.fixture
def raw_path(tmp_path: Path) -> Path:
    run_benchmark(
        fixture_spec(),
        {("offline", "tutor"): FixtureAdapter()},
        tmp_path / "private",
        tmp_path / "public",
    )
    return tmp_path / "private" / PRIVATE_EXPORT_DIR / RAW_FILE


def validate(path: Path) -> int:
    plan = fixture_spec().plan
    return len(
        validate_export_rows(
            path, freeze_sha256=plan.freeze_sha256, index=export_index(plan), layout=LAYOUT
        )
    )


def test_manifest_round_trip(raw_path: Path) -> None:
    assert validate(raw_path) == fixture_spec().plan.expected_cell_count


@pytest.mark.parametrize("change", ["duplicate", "missing", "status", "cell"])
def test_corrupt_cells(raw_path: Path, change: str) -> None:
    rows = parse_rows(raw_path.read_bytes())
    if change == "duplicate":
        rows.append(rows[0])
    if change == "missing":
        rows.pop()
    if change == "status":
        rows[0]["status"] = "unknown"
    if change == "cell":
        rows[0]["turn"] = 812
    raw_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="duplicate|missing|status|foreign"):
        validate(raw_path)


@pytest.mark.parametrize("field", ["run_id", "freeze_sha256", "file_sha256", "row_count"])
def test_sidecar_disagreement(raw_path: Path, field: str) -> None:
    path = sidecar_path(raw_path)
    sidecar = ExportManifest.model_validate_json(path.read_bytes())
    value = 1 if field == "row_count" else digest(field.encode())
    path.write_text(sidecar.model_copy(update={field: value}).model_dump_json())
    with pytest.raises(ValueError, match="differs|another freeze|mismatch"):
        validate(raw_path)


def test_forged_smaller_manifest_cannot_override_plan(raw_path: Path) -> None:
    path = sidecar_path(raw_path)
    sidecar = ExportManifest.model_validate_json(path.read_bytes())
    data = raw_path.read_bytes().splitlines(keepends=True)[1:]
    raw = b"".join(data)
    raw_path.write_bytes(raw)
    forged = sidecar.model_copy(
        update={
            "row_count": len(data),
            "file_sha256": digest(raw),
            "expected_keys": sidecar.expected_keys[1:],
        }
    )
    path.write_text(forged.model_dump_json())
    with pytest.raises(ValueError, match="missing export cell"):
        validate(raw_path)
