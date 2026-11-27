"""Validate raw benchmark exports against their detached run and cell index."""

import json
import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from pydantic import Field, JsonValue, TypeAdapter, ValidationError, field_validator

from ..contracts import Contract, canonical, digest

type RawRow = dict[str, JsonValue]
type Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", strict=True)]
type Turn = Annotated[int, Field(gt=0, strict=True)]
type Role = Annotated[str, Field(min_length=1, strict=True)]
type CellKey = tuple[Sha256, Turn] | tuple[Sha256, Role, Turn]
type PlanKeys = Callable[[Mapping[str, RawRow]], Iterable[CellKey]]

ROW = TypeAdapter(RawRow)
CELL_KEY = TypeAdapter(CellKey)
TURN = TypeAdapter(Turn)
SHA256 = TypeAdapter(Sha256)
INLINE_FIELD = "export_manifest"
TUTOR_STATUSES = (
    "ok",
    "leer",
    "abgeschnitten",
    "technischer_fehler",
    "abgebrochen_unklar",
    "zensiert",
    "nicht_gestartet",
)


class ExportIndex(Contract):
    """The expected cell keys from a trusted run plan."""

    run_id: Sha256
    freeze_sha256: Sha256
    expected_keys: tuple[CellKey, ...] = Field(min_length=1)

    @field_validator("expected_keys")
    @classmethod
    def unique_keys(cls, keys: tuple[CellKey, ...]) -> tuple[CellKey, ...]:
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate cell key in export index")
        return keys


class ExportManifest(ExportIndex):
    """Detached manifest for the exact bytes of the finished JSONL file."""

    row_count: Annotated[int, Field(gt=0, strict=True)]
    file_sha256: Sha256


def tutor_plan_keys(plans: Mapping[str, RawRow]) -> Iterable[CellKey]:
    for episode, plan in plans.items():
        for turn in range(1, plan_turns(plan) + 1):
            yield episode, turn


@dataclass(frozen=True)
class ExportLayout:
    plan_keys: PlanKeys
    statuses: tuple[str, ...]
    include_role: bool = False


TUTOR_EXPORT = ExportLayout(tutor_plan_keys, TUTOR_STATUSES)


def plan_turns(plan: RawRow) -> int:
    return TURN.validate_python(plan.get("turns"))


def journal_export_index(
    db: sqlite3.Connection, run_id: str, *, layout: ExportLayout = TUTOR_EXPORT
) -> ExportIndex:
    """Read the registered plans, including those that never started."""
    run = db.execute(
        "SELECT a.body FROM run r JOIN asset a ON r.manifest=a.hash WHERE r.id=?", (run_id,)
    ).fetchone()
    if run is None:
        raise ValueError(f"unknown export run {run_id}")
    manifest = ROW.validate_json(run[0])
    # check-freeze hashes the original freeze file bytes. The asset map cannot recover them.
    try:
        freeze = SHA256.validate_python(manifest.get("freeze_sha256"))
    except ValidationError as exc:
        raise ValueError(f"run {run_id} lacks a valid freeze_sha256 field") from exc
    plans = {
        episode: ROW.validate_json(plan)
        for episode, plan in db.execute(
            "SELECT e.id, a.body FROM episode e JOIN asset a ON e.plan=a.hash "
            "WHERE e.run_id=? ORDER BY e.id",
            (run_id,),
        )
    }
    return ExportIndex(
        run_id=run_id, freeze_sha256=freeze, expected_keys=tuple(layout.plan_keys(plans))
    )


def parse_rows(data: bytes) -> list[RawRow]:
    rows = []
    for number, line in enumerate(data.splitlines(), start=1):
        try:
            row = ROW.validate_json(line)
        except ValidationError as exc:
            raise ValueError(f"invalid export JSON at line {number}") from exc
        # Ignore former inline headers. The checksum still covers their original bytes.
        rows.append({name: value for name, value in row.items() if name != INLINE_FIELD})
    return rows


def checked_row(row: RawRow, number: int, layout: ExportLayout) -> tuple[CellKey, RawRow]:
    parts = (row.get("episode"), row.get("turn"))
    if layout.include_role:
        parts = (row.get("episode"), row.get("role"), row.get("turn"))
    try:
        key = CELL_KEY.validate_python(parts)
        plan = ROW.validate_python(row.get("plan"))
        plan_turns(plan)
    except ValidationError as exc:
        raise ValueError(f"invalid export cell key or plan at line {number}") from exc
    if not isinstance(plan.get("suite"), str):
        raise ValueError(f"invalid export plan suite at line {number}")
    if row.get("status") not in layout.statuses:
        raise ValueError(f"invalid export status at line {number}")
    return key, plan


def require_keys(seen: set[CellKey], expected: set[CellKey], source: str) -> None:
    foreign = seen - expected
    if foreign:
        raise ValueError(f"foreign export cell {min(foreign, key=repr)!r}: outside {source}")
    missing = expected - seen
    if missing:
        raise ValueError(
            f"missing export cell {min(missing, key=repr)!r} ({len(missing)} missing from {source})"
        )


def validate_cells(rows: Sequence[RawRow], index: ExportIndex, layout: ExportLayout) -> None:
    seen: set[CellKey] = set()
    plans: dict[str, RawRow] = {}
    for number, row in enumerate(rows, start=1):
        key, plan = checked_row(row, number, layout)
        if digest(canonical([index.run_id, plan])) != key[0]:
            raise ValueError(f"foreign export cell {key!r}: episode does not match run and plan")
        if key in seen:
            raise ValueError(f"duplicate export cell {key!r}")
        seen.add(key)
        plans[key[0]] = plan
    require_keys(seen, set(index.expected_keys), "the manifest or journal cell index")
    require_keys(seen, set(layout.plan_keys(plans)), "the episode plans")


def sidecar_path(path: Path) -> Path:
    return path.with_name(path.name + ".manifest.json")


def write_raw_export(
    path: Path, rows: Sequence[RawRow], index: ExportIndex, *, layout: ExportLayout = TUTOR_EXPORT
) -> None:
    """Publish exclusively, with the sidecar last so incomplete exports fail closed."""
    validate_cells(rows, index, layout)
    data = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")
    manifest = ExportManifest(
        run_id=index.run_id,
        freeze_sha256=index.freeze_sha256,
        expected_keys=index.expected_keys,
        row_count=len(rows),
        file_sha256=digest(data),
    )
    with TemporaryDirectory(dir=path.parent) as staging:
        raw = Path(staging) / "raw"
        metadata = Path(staging) / "manifest"
        raw.write_bytes(data)
        metadata.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        path.hardlink_to(raw)
        try:
            sidecar_path(path).hardlink_to(metadata)
        except OSError:
            path.unlink()
            raise


def read_sidecar(path: Path) -> ExportManifest | None:
    sidecar = sidecar_path(path)
    try:
        data = sidecar.read_bytes()
    except FileNotFoundError:
        if sidecar.is_symlink():
            raise
        return None
    return ExportManifest.model_validate_json(data)


def check_index_agreement(manifest: ExportManifest, index: ExportIndex) -> None:
    if manifest.run_id != index.run_id:
        raise ValueError(f"sidecar run {manifest.run_id} differs from journal run {index.run_id}")
    if manifest.freeze_sha256 != index.freeze_sha256:
        raise ValueError("sidecar freeze SHA-256 differs from journal")
    require_keys(set(manifest.expected_keys), set(index.expected_keys), "the journal cell index")


def validate_export_rows(
    path: Path,
    *,
    freeze_sha256: str | tuple[str, ...],
    index: ExportIndex | None = None,
    expected_file_sha256: str | None = None,
    run_id: str | None = None,
    layout: ExportLayout = TUTOR_EXPORT,
) -> list[RawRow]:
    """Verify a sidecar or a historical journal index paired with a known file hash."""
    manifest = read_sidecar(path)
    selected = manifest if manifest is not None else index
    if selected is None:
        raise ValueError("raw export requires a sidecar manifest or a trusted historical index")
    if run_id is not None and selected.run_id != run_id:
        raise ValueError(f"raw export run {selected.run_id} differs from expected run {run_id}")
    accepted = (freeze_sha256,) if isinstance(freeze_sha256, str) else freeze_sha256
    if selected.freeze_sha256 not in accepted:
        raise ValueError("raw export belongs to another freeze")
    if manifest is None and expected_file_sha256 is None:
        raise ValueError("historical raw export requires expected_file_sha256")
    if manifest is not None and index is not None:
        check_index_agreement(manifest, index)
    data = path.read_bytes()
    rows = parse_rows(data)
    validate_cells(rows, selected, layout)
    verify_file(data, len(rows), manifest, expected_file_sha256)
    return rows


def verify_file(
    data: bytes, row_count: int, manifest: ExportManifest | None, expected_file_sha256: str | None
) -> None:
    actual = digest(data)
    if manifest is not None:
        if row_count != manifest.row_count:
            raise ValueError(
                f"export row count {row_count} differs from sidecar {manifest.row_count}"
            )
        if actual != manifest.file_sha256:
            raise ValueError("raw export file SHA-256 mismatch against sidecar")
    if expected_file_sha256 is not None and actual != SHA256.validate_python(expected_file_sha256):
        raise ValueError("historical raw export file SHA-256 mismatch")
