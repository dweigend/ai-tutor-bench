"""Bind the private manifest and the public projection to one completed plan."""

from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import Field

from ..contracts import Contract, digest
from .primitives import Sha256, sync_path, write_verified
from .publish import (
    PUBLIC_DIRECTORY_MODE,
    process_umask,
    publish_directory,
)
from .run_summary import AbortReason, Completeness


class PublicReceipt(Contract):
    file_sha256: Sha256
    row_count: int = Field(gt=0, strict=True)


class ExportReceipt(Contract):
    plan_sha256: Sha256
    execution_revision: Sha256
    abort_reason: AbortReason | None
    completeness: Completeness
    private_raw_sha256: Sha256
    note_sha256: Sha256
    public_sidecar_sha256: Sha256
    export_revision: Sha256
    private_manifest_sha256: Sha256
    public: PublicReceipt


def publish_files(target: Path, files: Mapping[str, bytes]) -> None:
    """Publish a complete directory without replacing an existing export."""
    with TemporaryDirectory(dir=target.parent) as staging:
        directory = Path(staging)
        for name, data in files.items():
            if Path(name).name != name or name in ("", ".", ".."):
                raise ValueError(f"invalid export filename: {name!r}")
            write_verified(directory / name, data)
            sync_path(directory / name)
        directory.chmod(PUBLIC_DIRECTORY_MODE & ~process_umask())
        publish_directory(directory, target)


def verify_files(target: Path, files: Mapping[str, bytes]) -> None:
    if {path.name for path in target.iterdir()} != files.keys():
        raise ValueError(f"unexpected file set in export {target}")
    for name, data in files.items():
        path = target / name
        if path.is_symlink() or digest(path.read_bytes()) != digest(data):
            raise ValueError(f"export hash mismatch: {path}")
