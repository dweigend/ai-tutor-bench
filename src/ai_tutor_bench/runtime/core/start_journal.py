"""Durably record each dispatch intent under a unique attempt key."""

import fcntl
import os
from pathlib import Path
from typing import Annotated, BinaryIO, Literal

from pydantic import AwareDatetime, Field

from ..contracts import Contract
from .primitives import Sha256, sync_path

type Microusd = Annotated[int, Field(ge=0, strict=True)]
type AdapterKind = Literal["openrouter", "simulator-cli", "vllm", "peft", "fixture"]

FIRST_ATTEMPT = 1


class AttemptKey(Contract):
    run_id: Sha256
    cell_id: Sha256
    attempt_index: int = Field(ge=FIRST_ATTEMPT, strict=True)


class StartEvent(Contract):
    key: AttemptKey
    timestamp: AwareDatetime
    execution_revision: Sha256
    adapter_kind: AdapterKind
    reserved_microusd: Microusd


class StartJournal:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> dict[AttemptKey, StartEvent]:
        try:
            stream = self.path.open("rb")
        except FileNotFoundError:
            return {}
        with stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            starts, _ = self._read(stream)
            return starts

    def append(self, event: StartEvent) -> None:
        with self.path.open("a+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.seek(0)
            starts, valid_end = self._read(stream)
            self._insert(starts, event)
            if stream.tell() != valid_end:
                stream.truncate(valid_end)
            stream.write(event.model_dump_json().encode() + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
            sync_path(self.path.parent)

    @staticmethod
    def _read(stream: BinaryIO) -> tuple[dict[AttemptKey, StartEvent], int]:
        starts: dict[AttemptKey, StartEvent] = {}
        valid_end = 0
        for line in stream:
            if not line.endswith(b"\n"):
                break
            StartJournal._insert(starts, StartEvent.model_validate_json(line))
            valid_end += len(line)
        return starts, valid_end

    @staticmethod
    def _insert(starts: dict[AttemptKey, StartEvent], event: StartEvent) -> None:
        if event.key in starts:
            raise ValueError(f"duplicate attempt key: {event.key}")
        starts[event.key] = event
