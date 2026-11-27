"""Adapter and abort contracts for the v5 runner."""

from collections.abc import Mapping
from typing import Protocol, Self

from pydantic import Field, model_validator

from ..contracts import Contract
from ..core.cell_plan import CellPlan, Label, PlannedCell
from ..core.primitives import Sha256
from ..core.result_settlement import AttemptResult, SettledAttempt
from ..core.start_journal import AdapterKind, Microusd, StartEvent

type AdapterKey = tuple[str, str]
type EpisodeHistory = tuple[AttemptResult, ...]


class AdapterProtocol(Protocol):
    """Resolve requests from frozen inputs and return classified outcomes.

    Reservations must be available without dispatch. Execute sends one attempt
    and returns billing evidence even when the provider's outcome is unusable.
    An exception leaves the start unresolved and the full reservation open.
    """

    @property
    def kind(self) -> AdapterKind: ...

    @property
    def identity(self) -> str: ...

    def reserve(self, cell: PlannedCell) -> Microusd: ...

    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt: ...


class AbortPolicy(Contract):
    budget_microusd: Microusd
    max_subscription_censures: int = Field(ge=1, strict=True)


class V5RunSpec(Contract):
    plan: CellPlan
    abort_policy: AbortPolicy
    execution_assets: tuple[str, ...] = ()


class AdapterBinding(Contract):
    arm: Label
    role: Label
    kind: AdapterKind
    identity: Label

    @property
    def key(self) -> AdapterKey:
        return self.arm, self.role


class BoundRun(Contract):
    spec: V5RunSpec
    execution_revision: Sha256
    bindings: tuple[AdapterBinding, ...]

    @model_validator(mode="after")
    def check_bindings(self) -> Self:
        keys = tuple(binding.key for binding in self.bindings)
        expected = sorted({(cell.key.arm, cell.key.role) for cell in self.spec.plan.cells})
        if keys != tuple(expected):
            raise ValueError("adapter bindings must cover each planned arm and role exactly once")
        return self

    @classmethod
    def bind(
        cls,
        spec: V5RunSpec,
        execution_revision: str,
        adapters: Mapping[AdapterKey, AdapterProtocol],
    ) -> Self:
        return cls(
            spec=spec,
            execution_revision=execution_revision,
            bindings=tuple(
                AdapterBinding(arm=arm, role=role, kind=adapter.kind, identity=adapter.identity)
                for (arm, role), adapter in sorted(adapters.items())
            ),
        )
