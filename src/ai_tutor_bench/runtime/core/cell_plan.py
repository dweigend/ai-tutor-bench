"""Freeze the exact set of cells before any dispatch."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from ..contracts import Contract, canonical, digest
from .primitives import Sha256, Turn

type Label = Annotated[str, Field(min_length=1, strict=True)]
type EpisodeKey = tuple[str, str, str, int]

LEARNER_ROLE = "learner"


class CellKeyV5(Contract):
    run_id: Sha256
    suite: Label
    arm: Label
    case: Label
    seed: int = Field(strict=True)
    role: Label
    turn: Turn

    def episode(self) -> EpisodeKey:
        return self.suite, self.arm, self.case, self.seed

    def sort_key(self) -> tuple[EpisodeKey, int, bool, str]:
        return self.episode(), self.turn, self.role != LEARNER_ROLE, self.role

    def identifier(self) -> str:
        return digest(canonical((self.run_id, *self.episode(), self.role, self.turn)))


class PlannedCell(Contract):
    key: CellKeyV5
    cell_id: Sha256

    @classmethod
    def from_key(cls, key: CellKeyV5) -> Self:
        return cls(key=key, cell_id=key.identifier())

    @model_validator(mode="after")
    def check_identifier(self) -> Self:
        if self.cell_id != self.key.identifier():
            raise ValueError("cell_id differs from its cell key")
        return self


class CellPlan(Contract):
    run_id: Sha256
    freeze_sha256: Sha256
    cells: tuple[PlannedCell, ...] = Field(min_length=1)

    @classmethod
    def from_keys(cls, run_id: str, freeze_sha256: str, keys: tuple[CellKeyV5, ...]) -> Self:
        cells = tuple(PlannedCell.from_key(key) for key in sorted(keys, key=CellKeyV5.sort_key))
        return cls(run_id=run_id, freeze_sha256=freeze_sha256, cells=cells)

    @property
    def expected_cell_count(self) -> int:
        return len(self.cells)

    @property
    def plan_sha256(self) -> str:
        return digest(canonical(self.model_dump(mode="json")))

    @model_validator(mode="after")
    def check_cells(self) -> Self:
        if any(cell.key.run_id != self.run_id for cell in self.cells):
            raise ValueError("cell belongs to a different run")
        if len({cell.cell_id for cell in self.cells}) != len(self.cells):
            raise ValueError("duplicate planned cell")
        if self.cells != tuple(sorted(self.cells, key=lambda cell: cell.key.sort_key())):
            raise ValueError("cells must be in canonical order")
        return self
