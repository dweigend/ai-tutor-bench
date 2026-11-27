"""Offline input and adapter for the CLI dry run."""

from collections.abc import Mapping
from typing import ClassVar, Literal

from pydantic import Field, JsonValue

from ..contracts import ROOT, Contract, canonical, digest
from ..core.cell_plan import CellKeyV5, CellPlan, PlannedCell
from ..core.result_settlement import AttemptResult, BillingReport, CellOutcome, SettledAttempt
from ..core.revisions import FIXTURE_SOURCE
from ..core.start_journal import StartEvent
from .contracts import AbortPolicy, AdapterProtocol, EpisodeHistory, V5RunSpec

FIXTURE_REFERENCES = "runtime/v5/fixture-references.json"


class FixtureReferences(Contract):
    prompt: str = Field(min_length=1)
    cases: tuple[str, ...] = Field(min_length=1)
    answer: str = Field(min_length=1)


def load_fixture() -> FixtureReferences:
    return FixtureReferences.model_validate_json((ROOT / FIXTURE_REFERENCES).read_bytes())


def fixture_spec() -> V5RunSpec:
    run_id = digest(b"v5-offline-fixture")
    references = load_fixture()
    freeze = digest(canonical(references.model_dump(mode="json")))
    keys = tuple(
        CellKeyV5(
            run_id=run_id, suite="dry-run", arm="offline", case=case, seed=0, role="tutor", turn=1
        )
        for case in references.cases
    )
    return V5RunSpec(
        plan=CellPlan.from_keys(run_id, freeze, keys),
        abort_policy=AbortPolicy(budget_microusd=0, max_subscription_censures=1),
        execution_assets=(FIXTURE_SOURCE, FIXTURE_REFERENCES),
    )


class FixtureAdapter:
    kind: ClassVar[Literal["fixture"]] = "fixture"
    identity: ClassVar[str] = "offline-fixture"

    def __init__(
        self,
        drift: AdapterProtocol | None = None,
        prompts: Mapping[str, JsonValue] | None = None,
    ) -> None:
        self.drift = drift
        self.prompts = prompts or {}

    def reserve(self, cell: PlannedCell) -> int:
        return 0

    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt:
        if self.drift is not None and cell.key.suite == "drift":
            return self.drift.execute(cell, start, history)
        references = load_fixture()
        return SettledAttempt(
            result=AttemptResult(
                key=start.key,
                outcome=CellOutcome.OK,
                raw={
                    "prompt": self.prompts.get(cell.key.case, references.prompt),
                    "response": references.answer,
                },
                visible_text=references.answer,
                finish_reason="stop",
            ),
            billing=BillingReport(is_byok=False, reported_microusd=0),
        )
