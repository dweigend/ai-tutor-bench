"""Independent deterministic tutor for the offline release suite."""

from typing import ClassVar, Literal

from ...core.cell_plan import PlannedCell
from ...core.result_settlement import AttemptResult, BillingReport, CellOutcome, SettledAttempt
from ...core.start_journal import StartEvent
from ..contracts import EpisodeHistory


class AlternateAdapter:
    kind: ClassVar[Literal["fixture"]] = "fixture"
    identity: ClassVar[str] = "offline-alternate"

    def reserve(self, cell: PlannedCell) -> int:
        return 0

    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt:
        text = "Zeig einen ersten Versuch." if cell.key.turn % 2 else "Begründe deinen Schritt."
        return SettledAttempt(
            result=AttemptResult(
                key=start.key,
                outcome=CellOutcome.OK,
                raw={"response": text},
                visible_text=text,
                finish_reason="stop",
            ),
            billing=BillingReport(is_byok=False, reported_microusd=0),
        )
