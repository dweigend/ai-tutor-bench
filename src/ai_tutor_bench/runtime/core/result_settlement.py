"""Keep the observed outcome and billing evidence independently typed."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, model_validator

from ..contracts import Contract
from .settlement import BillingMode, Settlement
from .start_journal import AttemptKey, Microusd, StartEvent

type TokenCount = Annotated[int, Field(ge=0, strict=True)]


class CellOutcome(StrEnum):
    OK = "ok"
    TRUNCATED = "abgeschnitten"
    EMPTY = "leer"
    CENSORED = "zensiert"
    NOT_STARTED = "nicht_gestartet"
    TECHNICAL = "technisch"
    ABORTED = "abgebrochen"


class AttemptResult(Contract):
    key: AttemptKey
    outcome: CellOutcome
    raw: JsonValue
    visible_text: str | None
    finish_reason: Literal["stop", "length"] | None
    input_tokens: TokenCount | None = None
    output_tokens: TokenCount | None = None
    reasoning_tokens: TokenCount | None = None
    identity_ok: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def check_started(self) -> Self:
        if self.outcome == CellOutcome.NOT_STARTED:
            raise ValueError("attempt results require a start event")
        if self.outcome == CellOutcome.OK and not (self.visible_text or "").strip():
            raise ValueError("ok requires nonempty visible_text")
        return self


class BillingReport(Contract):
    is_byok: bool | None = Field(strict=True)
    reported_microusd: Microusd | None

    @property
    def mode(self) -> BillingMode:
        if self.is_byok is None:
            return "unknown"
        return "confirmed_yes" if self.is_byok else "confirmed_no"


class SettlementRecord(Settlement):
    """Bind the existing settlement view's accounting to an attempt."""

    key: AttemptKey

    @model_validator(mode="after")
    def check_attempt(self) -> Self:
        if self.run_id != self.key.run_id or self.call_id != self.attempt_call_id(self.key):
            raise ValueError("settlement identifiers differ from the attempt key")
        return self

    @staticmethod
    def attempt_call_id(key: AttemptKey) -> str:
        return f"{key.cell_id}:{key.attempt_index}"

    @classmethod
    def resolve(cls, start: StartEvent, report: BillingReport) -> Self:
        reserve = start.reserved_microusd
        if report.reported_microusd is not None and report.mode == "confirmed_no":
            reserve = 0
        return cls(
            key=start.key,
            run_id=start.key.run_id,
            call_id=cls.attempt_call_id(start.key),
            reported_microusd=report.reported_microusd,
            billing_mode=report.mode,
            reserved_microusd=reserve,
        )


class SettledAttempt(Contract):
    result: AttemptResult
    billing: BillingReport

    def settlement_for(self, start: StartEvent) -> SettlementRecord:
        if self.result.key != start.key:
            raise ValueError("result attempt does not match its start")
        return SettlementRecord.resolve(start, self.billing)
