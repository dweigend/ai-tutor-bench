from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

ROOT = Path(__file__).resolve().parents[1]
JSON = TypeAdapter(JsonValue)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    import json

    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
