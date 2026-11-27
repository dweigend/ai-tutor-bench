"""Publish a blind export after committing its manifest and key mapping to SQLite."""

import ctypes
import errno
import os
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import Field, JsonValue, field_validator

from ..contracts import JSON, Contract, canonical, digest
from ..store import Store

MANIFEST_NAME = "manifest.json"
KEY_FILE = "blind-keys.jsonl"
KEY_DIRECTORY_PREFIX = ".blind-keys-"
PUBLIC_DIRECTORY_MODE = 0o755
PRIVATE_DIRECTORY_MODE = 0o700
AT_FDCWD = -100
RENAME_NOREPLACE = 1
PROCESS_STATUS = Path("/proc/self/status")


class Sheet(Contract):
    sha256: str
    zeilen: int = Field(ge=0, strict=True)
    geplant: int = Field(ge=0, strict=True)
    nicht_im_blatt: list[dict[str, JsonValue]]


class Manifest(Contract):
    export_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    freeze_sha256: str
    rubrik: str
    dateien: dict[str, Sheet]

    @field_validator("dateien")
    @classmethod
    def validate_filenames(cls, sheets: dict[str, Sheet]) -> dict[str, Sheet]:
        for name in sheets:
            if Path(name).name != name or name in ("", ".", "..", MANIFEST_NAME):
                raise ValueError(f"invalid public sheet filename: {name!r}")
        return sheets


class BlindKey(Contract):
    blind_id: str
    call_id: str
    view: str
    position: int = Field(ge=0, strict=True)


def publish_export(
    store: Store, target: Path, write_sheets: Callable[[Path], Manifest]
) -> Manifest:
    """Keep both stages private and on the same filesystem as their own destination.

    Publish the public directory last. An interruption after commit can leave a
    registered private export without a public directory. Its keys remain in SQLite.
    """
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    private_root = store.database.parent
    public_mode = PUBLIC_DIRECTORY_MODE & ~process_umask()
    with (
        TemporaryDirectory(dir=target.parent, prefix=".blind-staging-") as public,
        TemporaryDirectory(dir=private_root, prefix=".keys-staging-") as private,
    ):
        public_stage, key_stage = Path(public), Path(private)
        public_stage.chmod(PRIVATE_DIRECTORY_MODE)
        key_stage.chmod(PRIVATE_DIRECTORY_MODE)
        with store.db:
            store.db.execute("BEGIN IMMEDIATE")
            manifest = write_sheets(public_stage)
            key_target = private_root / f"{KEY_DIRECTORY_PREFIX}{manifest.export_id}"
            if target.parent.resolve() / target.name == key_target:
                raise ValueError("public export and private key destinations must be distinct")
            if key_target.exists() or key_target.is_symlink():
                raise FileExistsError(key_target)
            stage_registration(store, manifest, public_stage, key_stage)
        publish_directory(key_stage, key_target)
        public_stage.chmod(public_mode)
        publish_directory(public_stage, target)
    return manifest


def stage_registration(store: Store, manifest: Manifest, public: Path, private: Path) -> None:
    keys = [
        BlindKey.model_validate(dict(row))
        for row in store.db.execute(
            "SELECT blind_id, call_id, view, position FROM blind_key "
            "WHERE export_id=? ORDER BY view, position",
            (manifest.export_id,),
        )
    ]
    expected = [(key.view, key.position, key.blind_id) for key in keys]
    actual = [
        (Path(name).stem, position, blind_id)
        for name, sheet in sorted(
            manifest.dateien.items(), key=lambda item: (Path(item[0]).stem, item[0])
        )
        for position, blind_id in enumerate(verified_ids(public / name, sheet))
    ]
    if actual != expected:
        raise ValueError("public sheets do not match the registered blind keys")
    write_verified(
        private / KEY_FILE, b"".join(canonical(key.model_dump()) + b"\n" for key in keys)
    )
    body = (manifest.model_dump_json(indent=2) + "\n").encode()
    write_verified(public / MANIFEST_NAME, body)
    for name in (*manifest.dateien, MANIFEST_NAME):
        sync_path(public / name)
    sync_path(private / KEY_FILE)
    store.asset(body)


def verified_ids(path: Path, sheet: Sheet) -> list[str]:
    data = path.read_bytes()
    if digest(data) != sheet.sha256:
        raise ValueError(f"public sheet hash mismatch: {path.name}")
    ids: list[str] = []
    for line in data.splitlines():
        row = JSON.validate_json(line)
        blind_id = row.get("blind_id") if isinstance(row, dict) else None
        if not isinstance(blind_id, str):
            raise ValueError(f"public sheet lacks a blind key: {path.name}")
        ids.append(blind_id)
    if len(ids) != sheet.zeilen:
        raise ValueError(f"public sheet row count mismatch: {path.name}")
    return ids


def write_verified(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
    if digest(path.read_bytes()) != digest(data):
        raise ValueError(f"staged file hash mismatch: {path.name}")


def process_umask() -> int:
    # Reading the Linux process status avoids changing the mask for concurrent writers.
    for line in PROCESS_STATUS.read_bytes().splitlines():
        label, _, value = line.partition(b":")
        if label == b"Umask":
            return int(value.strip(), 8)
    raise OSError("Linux process status does not expose the file creation mask")


def sync_path(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish_directory(source: Path, target: Path) -> None:
    sync_path(source)
    rename_noreplace(source, target)
    sync_path(target.parent)


def rename_noreplace(source: Path, target: Path) -> None:
    try:
        rename = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError:
        raise OSError(errno.ENOSYS, "renameat2 is required for blind export") from None
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(AT_FDCWD, os.fsencode(source), AT_FDCWD, os.fsencode(target), RENAME_NOREPLACE):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), source, None, target)
