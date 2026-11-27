from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_tutor_bench.runtime.contracts import ROOT, digest
from ai_tutor_bench.runtime.core.cell_plan import (
    LEARNER_ROLE,
    PlannedCell,
)
from ai_tutor_bench.runtime.core.export_manifest import ExportManifest
from ai_tutor_bench.runtime.core.export_receipt import (
    ExportReceipt,
    PublicReceipt,
)
from ai_tutor_bench.runtime.core.result_settlement import (
    CellOutcome,
    SettledAttempt,
)
from ai_tutor_bench.runtime.core.revisions import execution_revision
from ai_tutor_bench.runtime.core.start_journal import (
    FIRST_ATTEMPT,
    StartEvent,
    StartJournal,
)
from ai_tutor_bench.runtime.v5.contracts import BoundRun, EpisodeHistory
from ai_tutor_bench.runtime.v5.export import (
    BLIND_FILE,
    BLIND_SIDECAR,
    RAW_FILE,
    RAW_SIDECAR,
    RECEIPT_FILE,
    export_index,
)
from ai_tutor_bench.runtime.v5.runner import (
    RESULT_DIR,
    RUN_FILE,
    START_FILE,
    result_path,
)
from ai_tutor_bench.runtime.v5.workflow import PRIVATE_EXPORT_DIR
from ai_tutor_bench.v5.drift.bewertung import (
    EpisodenDialogzug,
    EpisodenJudgeUrteil,
    PruefpunktUrteil,
    ZielverfolgungZug,
    berechne_zielverfolgung,
)
from ai_tutor_bench.v5.drift.modul import (
    CALIBRATION_PATH,
    CHECKPOINTS,
    PUBLIC_CALIBRATION,
    TURN_NUMBERS,
    DriftKatalog,
    DriftModul,
    DriftZug,
    Pruefpunkt,
    lade_drift_katalog,
)
from ai_tutor_bench.v5.drift.trockenlauf import (
    TUTOR_ROLE,
    OfflineDriftAdapter,
    drift_spec,
    trockenlauf,
)
from ai_tutor_bench.v5.schema.signal_modus import LernendenSignal
from ai_tutor_bench.v5.szenarien.modul import lade_szenario_katalog

RESUME_AFTER = 16
TUTOR_CELLS = 64
TOTAL_CELLS = 128


@pytest.fixture(scope="module")
def catalog() -> DriftKatalog:
    return lade_drift_katalog()


def test_catalog(catalog: DriftKatalog) -> None:
    topics = {module.stoff for module in catalog.module}
    assert topics == {"hash-tabellen-kollisionen", "osmose-membrantransport"}
    calibration = lade_szenario_katalog().faelle("kalibrierung")
    assert topics.isdisjoint(case.stoff for case in calibration)
    for module in catalog.module:
        assert tuple(zug.zug_nr for zug in module.zuege) == TURN_NUMBERS
        assert tuple(zug.zug_nr for zug in module.zuege if zug.pruefpunkt) == (8, 16, 24, 32)
        assert any(zug.reaktion_auf_tutordrift for zug in module.zuege)
        assert any(zug.signal == LernendenSignal.DETAILFRAGE_LEGITIM for zug in module.zuege)


def test_catalog_rejects_calibration_topic(catalog: DriftKatalog, tmp_path: Path) -> None:
    first, second = catalog.module
    calibration = lade_szenario_katalog().faelle("kalibrierung")
    path = tmp_path / "invalid.json"
    duplicate = first.model_copy(update={"stoff": calibration[0].stoff})
    path.write_text(DriftKatalog(module=(duplicate, second)).model_dump_json())
    with pytest.raises(ValueError, match="calibration topic"):
        lade_drift_katalog(path)


def _reject_copied_turn(catalog: DriftKatalog, path: Path, index: int, **text: str) -> None:
    first, second = catalog.module
    turns = list(first.zuege)
    turns[index] = turns[index].model_copy(update=text)
    contaminated = first.model_copy(update={"zuege": tuple(turns)})
    path.write_text(DriftKatalog(module=(contaminated, second)).model_dump_json())
    with pytest.raises(ValueError, match=rf"turn {index + 1}: reuses a calibration text"):
        lade_drift_katalog(path)


def test_catalog_rejects_exact_reference(catalog: DriftKatalog, tmp_path: Path) -> None:
    source = PUBLIC_CALIBRATION.validate_json(CALIBRATION_PATH.read_bytes())["lotrechte-uhrzeiger"]
    _reject_copied_turn(catalog, tmp_path / "copied.json", 0, lernenden_text=source[0])


def test_catalog_rejects_embedded_reference(catalog: DriftKatalog, tmp_path: Path) -> None:
    source = PUBLIC_CALIBRATION.validate_json(CALIBRATION_PATH.read_bytes())["keramikglasur"]
    embedded = f"Hier ist eine zusätzliche Aufgabe. {source[0]} Kehren wir danach zurück."
    _reject_copied_turn(catalog, tmp_path / "copied.json", 1, tutor_fixture=embedded)


def test_catalog_rejects_near_copy_of_gt_prefix(catalog: DriftKatalog, tmp_path: Path) -> None:
    gt1 = next(
        case for case in lade_szenario_katalog().faelle("kalibrierung") if case.trigger == "GT1"
    )
    near_copy = gt1.vorlauf[0].text.replace("gestern", "vorgestern")
    assert near_copy != gt1.vorlauf[0].text
    origin = next(turn for turn in catalog.module[0].zuege if turn.tutor_drift_fixture)
    _reject_copied_turn(
        catalog, tmp_path / "copied.json", origin.zug_nr - 1, tutor_drift_fixture=near_copy
    )


def test_catalog_rejects_copied_gt_trigger_in_drift_reaction(
    catalog: DriftKatalog,
    tmp_path: Path,
) -> None:
    gt2 = next(
        case for case in lade_szenario_katalog().faelle("kalibrierung") if case.trigger == "GT2"
    )
    reaction = next(turn for turn in catalog.module[0].zuege if turn.reaktion_auf_tutordrift)
    _reject_copied_turn(
        catalog,
        tmp_path / "copied.json",
        reaction.zug_nr - 1,
        reaktion_auf_tutordrift=gt2.ausloeser_zug,
    )


def test_catalog_rejects_missing_checkpoint(catalog: DriftKatalog) -> None:
    checkpoint = catalog.module[0].zuege[CHECKPOINTS[0] - 1]
    with pytest.raises(ValidationError, match="pruefpunkt required"):
        DriftZug.model_validate({**checkpoint.model_dump(), "pruefpunkt": None})


def test_catalog_rejects_drift_on_checkpoint(catalog: DriftKatalog) -> None:
    module = catalog.module[0]
    checkpoint = CHECKPOINTS[0]
    turns = list(module.zuege)
    origin = next(turn for turn in turns if turn.tutor_drift_fixture)
    reaction = turns[origin.zug_nr]
    turns[origin.zug_nr - 1] = origin.model_copy(update={"tutor_drift_fixture": None})
    turns[origin.zug_nr] = reaction.model_copy(
        update={"reaktion_auf_tutordrift": None, "signal": None}
    )
    turns[checkpoint - 1] = turns[checkpoint - 1].model_copy(
        update={"tutor_drift_fixture": origin.tutor_drift_fixture}
    )
    turns[checkpoint] = turns[checkpoint].model_copy(
        update={
            "reaktion_auf_tutordrift": reaction.reaktion_auf_tutordrift,
            "signal": reaction.signal,
        }
    )
    with pytest.raises(ValidationError, match="cannot start on a checkpoint"):
        DriftModul.model_validate({**module.model_dump(), "zuege": tuple(turns)})


@pytest.mark.parametrize(
    "question",
    [
        "Warum stimmt das?",
        "Mit wem übst du?",
        "Seit wann gilt das?",
        "Und warum passiert das?",
        "Und seit wann gilt das?",
        "Woraufhin ändert sich der Druck?",
        "Klappt es? Ja?",
    ],
)
def test_checkpoint_rejects_nonbinary_questions(question: str) -> None:
    with pytest.raises(ValidationError, match="prueffrage_binaer"):
        Pruefpunkt(prueffrage_binaer=question, pflichtzitat=True)


@pytest.mark.parametrize(("related", "goal"), [(True, None), (False, "a")])
def test_target_tracking_requires_consistent_goal_id(related: bool, goal: str | None) -> None:
    with pytest.raises(ValidationError, match="zielbezug requires a goal ID"):
        ZielverfolgungZug(
            zug_nr=1,
            bearbeitetes_lernziel=goal,
            detailtiefe="passend",
            zielbezug=related,
            detailfrage_legitim_gewahrt=None,
        )


def test_target_tracking() -> None:
    checkpoints = {8: True, 16: False}
    off_target = (2, 3, 4, 6, 7)
    goal_overrides = dict.fromkeys(off_target) | {10: "c"}
    detail_questions = {5: True, 6: False, 10: True}
    turns = [
        ZielverfolgungZug(
            zug_nr=number,
            bearbeitetes_lernziel=goal_overrides.get(number, "a" if number <= 5 else "b"),
            detailtiefe="zu_tief" if number in (3, 4, 10) else "passend",
            zielbezug=number not in off_target,
            detailfrage_legitim_gewahrt=detail_questions.get(number),
            prueffrage_erfuellt=checkpoints.get(number),
        )
        for number in range(1, 25)
    ]
    result = berechne_zielverfolgung(turns, ("a", "b", "c"))
    assert result.anteil_zielbezug.model_dump() == {"zaehler": 19, "nenner": 24}
    assert result.zielabdeckung_ende.model_dump() == {"zaehler": 2, "nenner": 3}
    assert result.zu_tief_zuege.model_dump() == {"zaehler": 3, "nenner": 24}
    assert result.detailfrage_legitim_gewahrt.model_dump() == {"zaehler": 2, "nenner": 3}
    assert result.laengste_zielferne_strecke.model_dump() == {
        "laengste_strecke": 3,
        "zuege_gesamt": 24,
    }
    assert result.aussageebene == "Prozessqualität mit simulierten Lernenden – kein Lernergebnis"
    assert [(item.zug_nr, item.status) for item in result.pruefpunkt_status] == [
        (8, "erfuellt"),
        (16, "nicht_erfuellt"),
        (24, "nicht_kodiert"),
        (32, "nicht_beobachtet"),
    ]
    no_detail = berechne_zielverfolgung(
        [turn.model_copy(update={"detailfrage_legitim_gewahrt": None}) for turn in turns[:3]],
        ("a", "b"),
    )
    assert no_detail.detailfrage_legitim_gewahrt.model_dump() == {"zaehler": 0, "nenner": 0}
    with pytest.raises(ValueError, match="unplanned goal"):
        berechne_zielverfolgung(turns, ("a",))


@pytest.fixture
def judgment(catalog: DriftKatalog) -> EpisodenJudgeUrteil:
    module = catalog.module[0]
    dialog = tuple(
        EpisodenDialogzug(
            zug_nr=zug.zug_nr,
            lernenden_text=zug.reaktion_auf_tutordrift or zug.lernenden_text,
            tutor_text=zug.tutor_drift_fixture or zug.tutor_fixture,
        )
        for zug in module.zuege
    )
    drift_turn = next(zug for zug in module.zuege if zug.tutor_drift_fixture is not None)
    return EpisodenJudgeUrteil(
        dialog=dialog,
        erster_ausfall_zug=drift_turn.zug_nr,
        ausfall_grund="Der Tutor wechselt von der Verkettung zu Baumrotationen.",
        pflichtzitat="die Fälle für Links- und Rechtsrotation",
        pruefpunkte=tuple(
            PruefpunktUrteil(zug_nr=number, erfuellt=True, zitat=dialog[number - 1].tutor_text)
            for number in CHECKPOINTS
        ),
        label_source="entwicklungs_dryrun",
        aussageebene=module.aussageebene,
        menschliche_lernwirkung=module.menschliche_lernwirkung,
        kalibrierstatus=module.kalibrierstatus,
    )


def test_judge_requires_evidence_in_the_cited_tutor_turn(judgment: EpisodenJudgeUrteil) -> None:
    assert judgment.erster_ausfall_zug is not None
    dialog = judgment.dialog
    with pytest.raises(ValidationError, match="cited tutor turn"):
        EpisodenJudgeUrteil.model_validate(
            {**judgment.model_dump(), "erster_ausfall_zug": judgment.erster_ausfall_zug + 1}
        )
    with pytest.raises(ValidationError, match="pflichtzitat"):
        EpisodenJudgeUrteil.model_validate({**judgment.model_dump(), "pflichtzitat": "  "})
    with pytest.raises(ValidationError, match="1 through 32"):
        EpisodenJudgeUrteil.model_validate(
            {**judgment.model_dump(), "dialog": (dialog[1], *dialog[1:])}
        )


def test_judge_checks_all_checkpoint_quotes(judgment: EpisodenJudgeUrteil) -> None:
    first, second, *rest = judgment.pruefpunkte
    with pytest.raises(ValidationError, match="exactly one judgment"):
        EpisodenJudgeUrteil.model_validate(
            {**judgment.model_dump(), "pruefpunkte": (second, second, *rest)}
        )
    wrong_quote = first.model_copy(update={"zitat": second.zitat})
    with pytest.raises(ValidationError, match="checkpoint quote must occur"):
        EpisodenJudgeUrteil.model_validate(
            {**judgment.model_dump(), "pruefpunkte": (wrong_quote, second, *rest)}
        )


@pytest.mark.parametrize("quote", ["a", ".", "eins zwei drei", "ZweiWörterMitGenugZeichen bleiben"])
def test_judge_rejects_short_evidence(judgment: EpisodenJudgeUrteil, quote: str) -> None:
    with pytest.raises(ValidationError, match="pflichtzitat"):
        EpisodenJudgeUrteil.model_validate({**judgment.model_dump(), "pflichtzitat": quote})
    with pytest.raises(ValidationError, match="zitat"):
        PruefpunktUrteil(zug_nr=8, erfuellt=False, zitat=quote)


def _verify_export(directory: Path, run: BoundRun, receipt: ExportReceipt) -> None:
    private_export = directory / "private" / PRIVATE_EXPORT_DIR
    public = directory / "public"
    assert receipt == ExportReceipt.model_validate_json(
        (private_export / RECEIPT_FILE).read_bytes()
    )
    assert receipt.completeness == "vollstaendig" and receipt.abort_reason is None
    assert receipt.plan_sha256 == run.spec.plan.plan_sha256
    assert receipt.execution_revision == run.execution_revision
    assert run.execution_revision == execution_revision(ROOT, run.spec.execution_assets)
    private_sidecar = (private_export / RAW_SIDECAR).read_bytes()
    manifest = ExportManifest.model_validate_json(private_sidecar)
    assert manifest.expected_keys == export_index(run.spec.plan).expected_keys
    assert (
        manifest.file_sha256
        == receipt.private_raw_sha256
        == digest((private_export / RAW_FILE).read_bytes())
    )
    public_sidecar = (public / BLIND_SIDECAR).read_bytes()
    assert PublicReceipt.model_validate_json(public_sidecar) == receipt.public
    assert receipt.public_sidecar_sha256 == digest(public_sidecar)
    assert receipt.private_manifest_sha256 == digest(private_sidecar)
    blind = (public / BLIND_FILE).read_bytes()
    assert digest(blind) == receipt.public.file_sha256
    assert manifest.row_count == receipt.public.row_count == len(blind.splitlines()) == TOTAL_CELLS


def test_full_offline_run_resumes_after_turn_16_without_duplicate_dispatch(
    tmp_path: Path,
    catalog: DriftKatalog,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = drift_spec(catalog).plan
    split = RESUME_AFTER * 2  # One learner and one tutor cell per turn.
    prefix, suffix = plan.cells[:split], plan.cells[split:]
    assert sum(cell.key.role == TUTOR_ROLE for cell in plan.cells) == TUTOR_CELLS
    assert plan.expected_cell_count == TOTAL_CELLS
    assert prefix[-1].key.turn == RESUME_AFTER and prefix[-1].key.role == TUTOR_ROLE

    dispatched: list[str] = []
    execute = OfflineDriftAdapter.execute

    def record_dispatch(
        adapter: OfflineDriftAdapter, cell: PlannedCell, start: StartEvent, history: EpisodeHistory
    ) -> SettledAttempt:
        dispatched.append(cell.cell_id)
        return execute(adapter, cell, start, history)

    monkeypatch.setattr(OfflineDriftAdapter, "execute", record_dispatch)
    reserve = OfflineDriftAdapter.reserve
    with monkeypatch.context() as patch:

        def interrupt_before_next_turn(adapter: OfflineDriftAdapter, cell: PlannedCell) -> int:
            if cell == suffix[0]:
                raise KeyboardInterrupt
            return reserve(adapter, cell)

        patch.setattr(OfflineDriftAdapter, "reserve", interrupt_before_next_turn)
        with pytest.raises(KeyboardInterrupt):
            trockenlauf(tmp_path)

    private = tmp_path / "private"
    journal = StartJournal(private / START_FILE)
    initial_starts = journal.read()
    assert [key.cell_id for key in initial_starts] == [cell.cell_id for cell in prefix]
    for key in initial_starts:
        assert result_path(private / RESULT_DIR, key).is_file()
    assert not (tmp_path / "public").exists()

    receipt = trockenlauf(tmp_path)
    run = BoundRun.model_validate_json((private / RUN_FILE).read_bytes())
    _verify_export(tmp_path, run, receipt)
    starts = journal.read()
    assert [key.cell_id for key in starts] == [cell.cell_id for cell in plan.cells]
    assert {key: starts[key] for key in initial_starts} == initial_starts
    assert all(key.attempt_index == FIRST_ATTEMPT for key in starts)
    assert all(event.execution_revision == run.execution_revision for event in starts.values())
    assert all(event.reserved_microusd == 0 for event in starts.values())
    results = {
        key.cell_id: SettledAttempt.model_validate_json(
            result_path(private / RESULT_DIR, key).read_bytes()
        )
        for key in starts
    }
    assert all(reply.result.outcome is CellOutcome.OK for reply in results.values())
    assert all(reply.billing.reported_microusd == 0 for reply in results.values())

    modules = {module.stoff: module for module in catalog.module}
    for cell in plan.cells:
        turn = modules[cell.key.case].zuege[cell.key.turn - 1]
        reply = results[cell.cell_id].result
        if cell.key.role == LEARNER_ROLE:
            assert reply.visible_text == (turn.reaktion_auf_tutordrift or turn.lernenden_text)
        else:
            assert reply.visible_text == (turn.tutor_drift_fixture or turn.tutor_fixture)
    assert trockenlauf(tmp_path) == receipt
    assert dispatched == [cell.cell_id for cell in plan.cells]
