"""Dependency-free filesystem and identifier primitives for the v5 contracts."""

import os
from pathlib import Path
from typing import Annotated

from pydantic import Field

from ..contracts import digest

type Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", strict=True)]
type Turn = Annotated[int, Field(gt=0, strict=True)]

PRIVATE_DIRECTORY_MODE = 0o700


def sync_path(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_verified(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
    if digest(path.read_bytes()) != digest(data):
        raise ValueError(f"staged file hash mismatch: {path.name}")
