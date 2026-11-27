"""Construct the same frozen offline plan for both tutor adapters."""

from typing import Literal

from pydantic import JsonValue

from ...v5.drift.modul import DriftKatalog, lade_drift_katalog
from ...v5.drift.trockenlauf import (
    OFFLINE_ARM,
    TUTOR_ROLE,
    OfflineDriftAdapter,
    drift_spec,
)
from ...v5.szenarien.modul import SzenarioKatalog, SzenarioModul, lade_szenario_katalog
from ..contracts import ROOT, canonical, digest
from ..core.cell_plan import LEARNER_ROLE, CellKeyV5, CellPlan
from ..core.revisions import FIXTURE_SOURCE
from .adapters.alternate import AlternateAdapter
from .contracts import AbortPolicy, AdapterKey, AdapterProtocol, V5RunSpec
from .fixture import FIXTURE_REFERENCES, FixtureAdapter, load_fixture

type TutorName = Literal["fixture", "alternate"]

DRIFT_SOURCE = "v5/drift/trockenlauf.py"
SUITE_ASSETS = (
    FIXTURE_SOURCE,
    "runtime/core/freeze.py",
    FIXTURE_REFERENCES,
    "runtime/v5/adapters/__init__.py",
    "runtime/v5/adapters/alternate.py",
    "runtime/v5/suite.py",
    "v5/__init__.py",
    "v5/drift/__init__.py",
    "v5/drift/modul.py",
    DRIFT_SOURCE,
    "v5/drift/drift-szenarien.json",
    "v5/schema/__init__.py",
    "v5/schema/public-calibration.json",
    "v5/schema/signal-modus-matrix.json",
    "v5/schema/signal_modus.py",
    "v5/szenarien/__init__.py",
    "v5/szenarien/gt1-gt10-katalog.json",
    "v5/szenarien/modul.py",
)


def suite_spec(
    freeze: str, catalog: DriftKatalog, scenarios: SzenarioKatalog, adapter: TutorName
) -> V5RunSpec:
    run_id = digest(canonical(["public-v5", freeze, adapter]))
    drift_keys = tuple(
        cell.key.model_copy(update={"run_id": run_id}) for cell in drift_spec(catalog).plan.cells
    )
    fixture_cases = load_fixture().cases
    scenario_cases = tuple(case.modul_id for case in scenarios.module)
    single_turn_keys = tuple(
        CellKeyV5(
            run_id=run_id, suite=suite, arm=OFFLINE_ARM, case=case, seed=0, role=TUTOR_ROLE, turn=1
        )
        for suite, cases in (("fixture", fixture_cases), ("gt", scenario_cases))
        for case in cases
    )
    return V5RunSpec(
        plan=CellPlan.from_keys(run_id, freeze, drift_keys + single_turn_keys),
        abort_policy=AbortPolicy(budget_microusd=0, max_subscription_censures=1),
        execution_assets=SUITE_ASSETS,
    )


def scenario_prompt(case: SzenarioModul) -> JsonValue:
    messages: list[JsonValue] = []
    for turn in case.vorlauf:
        messages.append({"rolle": turn.rolle, "text": turn.text})
    messages.append({"rolle": "lernender", "text": case.ausloeser_zug})
    return messages


def suite_adapters(
    catalog: DriftKatalog, scenarios: SzenarioKatalog, name: TutorName
) -> dict[AdapterKey, AdapterProtocol]:
    source = digest((ROOT / DRIFT_SOURCE).read_bytes())
    prompts = {case.modul_id: scenario_prompt(case) for case in scenarios.module}
    tutor = FixtureAdapter(OfflineDriftAdapter(catalog, TUTOR_ROLE, source), prompts)
    return {
        (OFFLINE_ARM, LEARNER_ROLE): OfflineDriftAdapter(catalog, LEARNER_ROLE, source),
        (OFFLINE_ARM, TUTOR_ROLE): tutor if name == "fixture" else AlternateAdapter(),
    }


def load_suite(freeze: str, name: TutorName) -> tuple[V5RunSpec, dict[AdapterKey, AdapterProtocol]]:
    catalog = lade_drift_katalog()
    scenarios = lade_szenario_katalog()
    return suite_spec(freeze, catalog, scenarios, name), suite_adapters(catalog, scenarios, name)
