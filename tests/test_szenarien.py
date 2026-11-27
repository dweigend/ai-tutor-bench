import json
from collections import Counter

import pytest
from pydantic import ValidationError

from ai_tutor_bench.v5.schema.signal_modus import SignalModusMatrix
from ai_tutor_bench.v5.szenarien.modul import (
    CATALOG_PATH,
    MATRIX_PATH,
    SzenarioKatalog,
    lade_szenario_katalog,
)

TRIGGERS = ("GT1", "GT2", "GT3", "GT4", "GT5", "GT6", "GT7", "GT8", "GT9", "GT10")


@pytest.fixture
def katalog() -> SzenarioKatalog:
    return lade_szenario_katalog()


def test_catalog_loads_with_matrix_and_split(katalog: SzenarioKatalog) -> None:
    matrix = SignalModusMatrix.model_validate_json(MATRIX_PATH.read_bytes())
    calibration = katalog.faelle("kalibrierung")
    main = katalog.faelle("hauptmessung")
    calibration_counts = Counter(case.trigger for case in calibration)
    main_counts = Counter(case.trigger for case in main)

    assert set(calibration_counts) == set(main_counts) == set(TRIGGERS)
    assert all(count >= 1 for count in calibration_counts.values())
    assert all(count >= 2 for count in main_counts.values())
    assert {case.stoff for case in calibration}.isdisjoint(case.stoff for case in main)
    assert all(case.source_origin is not None for case in calibration)
    assert all(case.source_origin is None for case in main)
    assert {case.wiederholung for case in main if case.trigger == "GT5"} == {2, 3}
    for case in katalog.module:
        rule = matrix.signale[case.signal]
        assert case.erlaubte_modi == rule.erlaubte_modi
        assert case.verbotene_modi == rule.verbotene_modi


def test_rejects_missing_trigger(katalog: SzenarioKatalog) -> None:
    cases = [case.model_dump(mode="json") for case in katalog.module if case.trigger != "GT10"]
    with pytest.raises(ValidationError, match="GT10.*kalibrierung"):
        SzenarioKatalog.model_validate_json(json.dumps({"module": cases}))


def test_rejects_too_few_main_cases(katalog: SzenarioKatalog) -> None:
    omitted = katalog.faelle("hauptmessung")[0].modul_id
    cases = [case.model_dump(mode="json") for case in katalog.module if case.modul_id != omitted]
    with pytest.raises(ValidationError, match="at least two hauptmessung cases"):
        SzenarioKatalog.model_validate_json(json.dumps({"module": cases}))


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("stoff", "stichprobenziehung", "at least two different topics"),
        ("stoff", "regenmesser-schema", "calibration topic"),
        ("stoff", "hebelarm", "calibration topic"),
        ("lernziel", "Einen Regenmesser zeichnen.", "calibration topic"),
        ("ausloeser_zug", "Kannst du Zeitzonen skizzieren?", "calibration topic"),
        ("gold_erwartung", "Verwendet ein Hebelarm-Beispiel.", "calibration topic"),
        ("signal", "detailfrage_legitim", "requires a different signal"),
        ("erlaubte_modi", ["ERKLAEREN"], "signal-modus-matrix.json"),
        ("verbotene_modi", ["TELLING", "SERVICE"], "signal-modus-matrix.json"),
        ("prueffrage_binaer", "Lenkt der Tutor zurück", "prueffrage_binaer"),
        ("prueffrage_binaer", "Lenkt der Tutor zurück? Und wie?", "prueffrage_binaer"),
        ("prueffrage_binaer", "Wie reagiert der Tutor?", "yes/no question"),
        ("prueffrage_binaer", "Was macht der Tutor?", "yes/no question"),
        ("prueffrage_binaer", "Warum wechselt der Tutor das Thema?", "yes/no question"),
        ("prueffrage_binaer", "  Welche Hinweise gibt der Tutor?", "yes/no question"),
        ("pflichtzitat", False, "pflichtzitat"),
        ("pflichtzitat", 1, "pflichtzitat"),
        ("source_origin", "synthetic-public", "source_origin"),
    ],
)
def test_rejects_invalid_case(field: str, value: object, error: str) -> None:
    raw = json.loads(CATALOG_PATH.read_bytes())
    case = next(
        case for case in raw["module"] if case["modul_id"] == "gt1-hauptmessung-binaere-suche"
    )
    case[field] = value
    with pytest.raises(ValidationError, match=error):
        SzenarioKatalog.model_validate_json(json.dumps(raw))


def test_rejects_calibration_without_source_reference() -> None:
    raw = json.loads(CATALOG_PATH.read_bytes())
    case = next(case for case in raw["module"] if case["rolle"] == "kalibrierung")
    del case["source_origin"]
    with pytest.raises(ValidationError, match="source_origin"):
        SzenarioKatalog.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("suffix", ["", " Bitte."])
def test_rejects_reused_calibration_task_under_new_topic(suffix: str) -> None:
    raw = json.loads(CATALOG_PATH.read_bytes())
    calibration = next(
        case for case in raw["module"] if case["modul_id"] == "gt2-public-roemische-zahlen"
    )
    main = next(case for case in raw["module"] if case["modul_id"] == "gt2-hauptmessung-mediane")
    main["vorlauf"] = calibration["vorlauf"]
    main["ausloeser_zug"] = calibration["ausloeser_zug"] + suffix
    with pytest.raises(ValidationError, match="calibration task reused"):
        SzenarioKatalog.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("copied_part", ["vorlauf", "ausloeser_zug"])
def test_rejects_independently_embedded_calibration_parts(copied_part: str) -> None:
    raw = json.loads(CATALOG_PATH.read_bytes())
    calibration = next(
        case for case in raw["module"] if case["modul_id"] == "gt2-public-roemische-zahlen"
    )
    main = next(case for case in raw["module"] if case["modul_id"] == "gt2-hauptmessung-mediane")
    if copied_part == "vorlauf":
        first, second = calibration["vorlauf"]
        main["vorlauf"] = [
            {**first, "text": f"Übrigens: {first['text'].upper()}"},
            {"rolle": "tutor", "text": "Ein zusätzlicher Zug."},
            {**second, "text": f"{second['text']} Soviel dazu."},
        ]
    else:
        main["ausloeser_zug"] = f"Zum Mitschreiben: {calibration['ausloeser_zug'].upper()} Bitte."
    with pytest.raises(ValidationError, match="calibration task reused"):
        SzenarioKatalog.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("vorlauf_length", [1, 7, 14])
def test_rejects_gt10_with_wrong_turn_gap(vorlauf_length: int) -> None:
    raw = json.loads(CATALOG_PATH.read_bytes())
    case = next(case for case in raw["module"] if case["trigger"] == "GT10")
    prefix = case["vorlauf"]
    case["vorlauf"] = (prefix + prefix[1:])[:vorlauf_length]
    with pytest.raises(ValidationError, match="GT10.*7–12 intervening turns"):
        SzenarioKatalog.model_validate_json(json.dumps(raw))


def test_rejects_gt4_without_cause_flag() -> None:
    raw = json.loads(CATALOG_PATH.read_bytes())
    case = next(case for case in raw["module"] if case["trigger"] == "GT4")
    del case["zusatzflag"]
    with pytest.raises(ValidationError, match="URSACHE_ERFRAGT"):
        SzenarioKatalog.model_validate_json(json.dumps(raw))


def test_rejects_lightly_paraphrased_calibration_dialogue() -> None:
    raw = json.loads(CATALOG_PATH.read_bytes())
    calibration = next(
        case for case in raw["module"] if case["modul_id"] == "gt2-public-roemische-zahlen"
    )
    main = next(case for case in raw["module"] if case["modul_id"] == "gt2-hauptmessung-mediane")
    main["vorlauf"] = [
        {**turn, "text": turn["text"].replace("übe", "wiederhole")}
        for turn in calibration["vorlauf"]
    ]
    main["ausloeser_zug"] = calibration["ausloeser_zug"].replace("bestimmt", "sicher")
    with pytest.raises(ValidationError, match="calibration task reused"):
        SzenarioKatalog.model_validate_json(json.dumps(raw))


def test_rejects_prepositional_open_question() -> None:
    raw = json.loads(CATALOG_PATH.read_bytes())
    case = next(
        case for case in raw["module"] if case["modul_id"] == "gt1-hauptmessung-binaere-suche"
    )
    case["prueffrage_binaer"] = "Mit welcher Frage prüft der Tutor das Verständnis?"
    with pytest.raises(ValidationError, match="yes/no question"):
        SzenarioKatalog.model_validate_json(json.dumps(raw))
