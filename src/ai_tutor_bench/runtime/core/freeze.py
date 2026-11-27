"""Verify the complete release asset inventory using package-relative paths."""

from pathlib import Path

from pydantic import TypeAdapter

from ..contracts import ROOT, digest
from .primitives import Sha256

MANIFEST = "v5/schema/freeze.json"
MANIFEST_SHA256 = "7d1895270d7c82994afa22bcbfaccc96e9b0dc3b3d0f31da0805b8a8e638ced2"
PUBLIC_ASSETS = (
    "analyse/detektoren-v1.json",
    "runtime/v5/fixture-references.json",
    "v5/drift/drift-szenarien.json",
    "v5/schema/public-calibration.json",
    "v5/schema/rubric.json",
    "v5/schema/signal-modus-matrix.json",
    "v5/schema/signal-modus-schema.json",
    "v5/szenarien/gt1-gt10-katalog.json",
)
ASSET_HASHES = TypeAdapter(dict[str, Sha256])


def raise_walk_error(error: OSError) -> None:
    raise error


def asset_inventory(root: Path) -> set[str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("asset root must be a regular directory")
    assets: set[str] = set()
    for directory, dirs, files in root.walk(on_error=raise_walk_error):
        for name in sorted((*dirs, *files)):
            path = directory / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise ValueError(f"symlink in asset tree: {relative}")
            if path.is_dir():
                if path.suffix == ".json":
                    raise ValueError(f"asset must be a regular file: {relative}")
                continue
            if not path.is_file():
                raise ValueError(f"asset must be a regular file: {relative}")
            if path.suffix != ".py" and not (
                directory.name == "__pycache__" and path.suffix == ".pyc"
            ):
                assets.add(relative)
    return assets


def check_freeze(root: Path = ROOT) -> str:
    expected = {*PUBLIC_ASSETS, MANIFEST}
    inventory = asset_inventory(root)
    if inventory != expected:
        raise ValueError(
            f"freeze inventory mismatch: missing={sorted(expected - inventory)} "
            f"extra={sorted(inventory - expected)}"
        )
    payload = (root / MANIFEST).read_bytes()
    manifest_sha256 = digest(payload)
    if manifest_sha256 != MANIFEST_SHA256:
        raise ValueError("freeze manifest hash differs from the release")
    hashes = ASSET_HASHES.validate_json(payload)
    if hashes.keys() != set(PUBLIC_ASSETS):
        raise ValueError("freeze manifest has an unexpected asset list")
    for name in PUBLIC_ASSETS:
        if digest((root / name).read_bytes()) != hashes[name]:
            raise ValueError(f"freeze hash mismatch: {name}")
    return manifest_sha256
