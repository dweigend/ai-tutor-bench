"""Terminal run state shared by dispatch and publication."""

from typing import Literal

from ..contracts import Contract
from .primitives import Sha256

type AbortReason = Literal["identity_violation", "budget_limit", "subscription_censure_limit"]
type Completeness = Literal["vollstaendig", "partiell"]


class RunSummary(Contract):
    abort_reason: AbortReason | None
    completeness: Completeness
    censored_cells: tuple[Sha256, ...]
