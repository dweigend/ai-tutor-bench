"""Exercise the v5 workflow with two scripted 32-turn dialogues at zero cost."""

import argparse
from pathlib import Path
from typing import ClassVar, Literal

from ...runtime.contracts import canonical, digest
from ...runtime.core.cell_plan import LEARNER_ROLE, CellKeyV5, CellPlan, PlannedCell
from ...runtime.core.export_receipt import ExportReceipt
from ...runtime.core.result_settlement import (
    AttemptResult,
    BillingReport,
    CellOutcome,
    SettledAttempt,
)
from ...runtime.core.start_journal import StartEvent
from ...runtime.v5.contracts import AbortPolicy, EpisodeHistory, V5RunSpec
from ...runtime.v5.workflow import run_benchmark
from ..schema.signal_modus import FIRST_TURN, LernendenSignal
from .modul import DriftKatalog, DriftModul, DriftZug, lade_drift_katalog

OFFLINE_ARM = "offline"
SUITE = "drift"
TUTOR_ROLE = "tutor"
ROLES = (LEARNER_ROLE, TUTOR_ROLE)
SEED = 0
BUDGET_MICROUSD = 0


def drift_spec(catalog: DriftKatalog) -> V5RunSpec:
    freeze = digest(canonical(catalog.model_dump(mode="json")))
    run_id = digest(canonical((SUITE, OFFLINE_ARM, SEED, freeze)))
    keys = tuple(
        CellKeyV5(
            run_id=run_id,
            suite=SUITE,
            arm=OFFLINE_ARM,
            case=module.stoff,
            seed=SEED,
            role=role,
            turn=turn.zug_nr,
        )
        for module in catalog.module
        for turn in module.zuege
        for role in ROLES
    )
    return V5RunSpec(
        plan=CellPlan.from_keys(run_id, freeze, keys),
        abort_policy=AbortPolicy(budget_microusd=BUDGET_MICROUSD, max_subscription_censures=1),
    )


def _learner_reply(
    module: DriftModul, turn: DriftZug, history: EpisodeHistory
) -> tuple[str, LernendenSignal | None]:
    reaction = turn.reaktion_auf_tutordrift
    if reaction is None:
        return turn.lernenden_text, turn.signal
    previous = module.zuege[turn.zug_nr - FIRST_TURN - 1]
    if history[-1].visible_text == previous.tutor_drift_fixture:
        return reaction, turn.signal
    return turn.lernenden_text, None


class OfflineDriftAdapter:
    kind: ClassVar[Literal["fixture"]] = "fixture"

    def __init__(self, catalog: DriftKatalog, role: str, source_sha256: str) -> None:
        self.modules = {module.stoff: module for module in catalog.module}
        self.role = role
        self.identity = f"offline-drift-{role}:{source_sha256}"

    def reserve(self, cell: PlannedCell) -> int:
        return BUDGET_MICROUSD

    def execute(
        self, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt:
        key = cell.key
        expected_history = len(ROLES) * (key.turn - FIRST_TURN) + ROLES.index(self.role)
        if key.role != self.role or len(history) != expected_history:
            raise ValueError(
                "offline drift adapter received a different role or incomplete history"
            )
        module = self.modules[key.case]
        turn = module.zuege[key.turn - FIRST_TURN]
        if self.role == LEARNER_ROLE:
            text, signal = _learner_reply(module, turn, history)
        else:
            text, signal = turn.tutor_drift_fixture or turn.tutor_fixture, None
        return SettledAttempt(
            result=AttemptResult(
                key=start.key,
                outcome=CellOutcome.OK,
                raw={"response": text, "signal": signal.value if signal is not None else None},
                visible_text=text,
                finish_reason="stop",
            ),
            billing=BillingReport(is_byok=False, reported_microusd=BUDGET_MICROUSD),
        )


def trockenlauf(directory: Path) -> ExportReceipt:
    catalog = lade_drift_katalog()
    source = digest(Path(__file__).read_bytes())
    adapters = {(OFFLINE_ARM, role): OfflineDriftAdapter(catalog, role, source) for role in ROLES}
    directory.mkdir(exist_ok=True)
    return run_benchmark(drift_spec(catalog), adapters, directory / "private", directory / "public")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline drift replay for 0 USD")
    parser.add_argument("directory", type=Path, help="Verzeichnis für Laufjournal und Export")
    args = parser.parse_args()
    receipt = trockenlauf(args.directory)
    print(receipt.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
