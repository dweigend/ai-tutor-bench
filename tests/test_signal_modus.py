import json

import pytest
from pydantic import ValidationError

from ai_tutor_bench.runtime.contracts import ROOT
from ai_tutor_bench.v5.schema.signal_modus import (
    Dialogverlauf,
    LernendenSignal,
    ModusLabel,
    SignalBeobachtung,
    SignalModusMatrix,
    SyntheticLabels,
    TutorModus,
    Tutorzug,
    Wendepunkt,
    WendepunktUrteil,
    berechne_kennzahlen,
    export_json_schema,
)

SCHEMA_DIR = ROOT / "v5/schema"


@pytest.fixture
def matrix() -> SignalModusMatrix:
    return SignalModusMatrix.model_validate_json(
        (SCHEMA_DIR / "signal-modus-matrix.json").read_bytes()
    )


def test_matrix_and_export(matrix: SignalModusMatrix) -> None:
    assert set(matrix.signale) == set(LernendenSignal)
    assert set(matrix.modusdefinitionen) == set(TutorModus)
    for rule in matrix.signale.values():
        assert rule.erlaubte_modi
        assert set(rule.erlaubte_modi).isdisjoint(rule.verbotene_modi)
    exported = (SCHEMA_DIR / "signal-modus-schema.json").read_bytes()
    assert (
        exported == (json.dumps(export_json_schema(), ensure_ascii=False, indent=2) + "\n").encode()
    )


def test_matrix_rejects_overlap_and_missing_signal(matrix: SignalModusMatrix) -> None:
    raw = matrix.model_dump(mode="json")
    rule = raw["signale"][LernendenSignal.VISUALISIERUNGSBITTE]
    rule["verbotene_modi"].append(TutorModus.VISUALISIEREN.value)
    with pytest.raises(ValidationError, match="disjoint"):
        SignalModusMatrix.model_validate_json(json.dumps(raw))

    raw["signale"].pop(LernendenSignal.VISUALISIERUNGSBITTE)
    with pytest.raises(ValidationError, match="at least 12"):
        SignalModusMatrix.model_validate_json(json.dumps(raw))


def test_probe_entries_and_coverage() -> None:
    entries = [
        {
            "source_reference": f"example-{index}",
            "zug_nr": 2,
            "tutor_nachrichtenrolle": "assistant",
            "originalzitat": "Lege den blauen Stein neben das Lineal.",
            "signal_zug_nr": 1,
            "signalzitat": "Wo liegt der Anfang?",
            "beobachtung": {"signal": "detailfrage_legitim"},
            "abgrenzungsnotiz": "Synthetic label contract example.",
            "label_source": "synthetische_entwicklung",
            "modi": [mode],
        }
        for index, mode in enumerate(tuple(TutorModus) * 3)
    ]
    probe = SyntheticLabels.model_validate_json(
        json.dumps(
            {
                "eintraege": entries,
                "nicht_belegte_signale": {
                    signal: "No example in this synthetic batch."
                    for signal in LernendenSignal
                    if signal != LernendenSignal.DETAILFRAGE_LEGITIM
                },
            }
        )
    )
    assert len(probe.eintraege) == 24
    raw = probe.model_dump(mode="json")
    raw["eintraege"][0]["label_source"] = "human_gold"
    with pytest.raises(ValidationError, match="synthetische_entwicklung"):
        SyntheticLabels.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (SignalBeobachtung, '{"signal":"unbekannt"}'),
        (SignalBeobachtung, '{"signal":"nichtverstehen_1"}'),
        (SignalBeobachtung, '{"signal":"nichtverstehen_2_plus","huerde_id":"qkv"}'),
        (
            SignalBeobachtung,
            '{"signal":"nichtverstehen_2_plus","huerde_id":"qkv","wiederholung":"2"}',
        ),
        (SignalBeobachtung, '{"signal":"nichtverstehen_1","huerde_id":"qkv","wiederholung":2}'),
        (ModusLabel, '{"modi":["unbekannt"]}'),
        (ModusLabel, '{"modi":["PRUEFEN","PRUEFEN"]}'),
        (ModusLabel, '{"modi":["PRUEFEN"],"primaermodus":"TELLING"}'),
    ],
)
def test_invalid_signal_and_mode_labels(
    model: type[SignalBeobachtung] | type[ModusLabel], payload: str
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate_json(payload)


def test_urteil_requires_quote_and_strict_bools() -> None:
    raw = {
        "zug_nr": 1,
        "signal": LernendenSignal.SCHEINZUSTIMMUNG,
        "signal_erkannt": True,
        "passende_handlung_ausgefuehrt": False,
        "naechster_eigener_schritt_ermoeglicht": True,
        "label_source": "synthetische_entwicklung",
        "beleg_eingeholt": True,
        "beleg_spaeter_genutzt": False,
    }
    with pytest.raises(ValidationError, match="pflichtzitat"):
        WendepunktUrteil.model_validate(raw)
    with pytest.raises(ValidationError, match="pflichtzitat"):
        WendepunktUrteil.model_validate({**raw, "pflichtzitat": " "})
    with pytest.raises(ValidationError, match="signal_erkannt"):
        WendepunktUrteil.model_validate(
            {**raw, "pflichtzitat": "Versuch es hier.", "signal_erkannt": 1}
        )
    judgment = WendepunktUrteil.model_validate({**raw, "pflichtzitat": "Versuch es hier."})
    assert judgment.beleg_eingeholt is True
    assert judgment.beleg_spaeter_genutzt is False
    assert (
        WendepunktUrteil.model_validate(
            {**raw, "pflichtzitat": "Versuch es hier.", "beleg_eingeholt": None}
        ).beleg_eingeholt
        is None
    )
    del raw["label_source"]
    with pytest.raises(ValidationError, match="label_source"):
        WendepunktUrteil.model_validate({**raw, "pflichtzitat": "Versuch es hier."})


@pytest.mark.parametrize("collected", [False, None, True])
def test_later_evidence_use_requires_collection(collected: bool | None) -> None:
    raw = {
        "zug_nr": 2,
        "signal": LernendenSignal.SCHEINZUSTIMMUNG,
        "signal_erkannt": True,
        "passende_handlung_ausgefuehrt": True,
        "naechster_eigener_schritt_ermoeglicht": True,
        "pflichtzitat": "Zeige es am nächsten Beispiel.",
        "label_source": "synthetische_entwicklung",
        "beleg_eingeholt": collected,
        "beleg_spaeter_genutzt": True,
    }
    if collected is not True:
        with pytest.raises(ValidationError, match="beleg_spaeter_genutzt requires beleg_eingeholt"):
            WendepunktUrteil.model_validate(raw)
        return

    judgment = WendepunktUrteil.model_validate(raw)
    assert judgment.beleg_spaeter_genutzt is True
    for key in ("zug_nr", "signal"):
        without_key = {name: value for name, value in raw.items() if name != key}
        with pytest.raises(ValidationError, match=key):
            WendepunktUrteil.model_validate(without_key)
    with pytest.raises(ValidationError, match="zug_nr"):
        WendepunktUrteil.model_validate({**raw, "zug_nr": 0})


def test_passung_latenz_and_rueckfall(matrix: SignalModusMatrix) -> None:
    result = berechne_kennzahlen(
        matrix,
        Dialogverlauf.model_validate_json("""
        {
          "tutorzuege": [
            {"zug_nr": 1, "modi": ["ZIEL_STEUERN", "ERKLAEREN"], "primaermodus": "ZIEL_STEUERN"},
            {
              "zug_nr": 2,
              "modi": ["VISUALISIEREN", "TELLING", "SERVICE"],
              "primaermodus": "VISUALISIEREN"
            },
            {"zug_nr": 3, "modi": ["VISUALISIEREN"], "primaermodus": "VISUALISIEREN"},
            {"zug_nr": 4, "modi": ["ZIEL_STEUERN"]},
            {"zug_nr": 5, "modi": ["PRUEFEN"], "primaermodus": "PRUEFEN"}
          ],
          "wendepunkte": [
            {"zug_nr": 1, "signal": "exkurs"},
            {"zug_nr": 2, "signal": "visualisierungsbitte"},
            {"zug_nr": 4, "signal": "exkurs"},
            {"zug_nr": 5, "signal": "scheinzustimmung"},
            {"zug_nr": 6, "signal": "hilflosigkeit"}
          ]
        }
        """),
    )
    assert result.nicht_beobachtbar == 1
    assert result.passung.model_dump() == {"zaehler": 2, "nenner": 4, "wert": 0.5}
    assert (result.latenz.zaehler, result.latenz.nenner) == (3, 4)
    assert [
        (case.latenz, case.beobachtete_zuege, case.zensurgrund) for case in result.latenz.faelle
    ] == [
        (0, 1, None),
        (1, 2, None),
        (None, 1, "folgesignal"),
        (0, 1, None),
        (None, 0, "keine_gelegenheit"),
    ]
    assert result.rueckfall.model_dump() == {
        "zaehler": 1,
        "nenner": 5,
        "wert": 0.2,
        "erster_zug": 2,
    }
    assert result.aussageebene == matrix.aussageebene
    assert result.menschliche_lernwirkung == "nicht_gemessen"
    assert "formale Kalibrierung steht aus" in result.kalibrierstatus


@pytest.mark.parametrize(
    ("followup", "reason"),
    [((), "verlaufsende"), ((Wendepunkt(zug_nr=2, signal=LernendenSignal.EXKURS),), "folgesignal")],
)
def test_observed_latency_censoring_at_final_turn(
    matrix: SignalModusMatrix, followup: tuple[Wendepunkt, ...], reason: str
) -> None:
    result = berechne_kennzahlen(
        matrix,
        Dialogverlauf(
            tutorzuege=(Tutorzug(zug_nr=1, modi=(TutorModus.PRUEFEN,)),),
            wendepunkte=(Wendepunkt(zug_nr=1, signal=LernendenSignal.SCHEINZUSTIMMUNG), *followup),
        ),
    )
    assert result.passung.nenner == result.latenz.nenner == 1
    assert result.latenz.zaehler == 0
    assert result.latenz.faelle[0].zensurgrund == reason


def test_festhaengen_tracks_same_hurdle_and_label_set(matrix: SignalModusMatrix) -> None:
    explain, check, scaffold = (
        TutorModus.ERKLAEREN,
        TutorModus.PRUEFEN,
        TutorModus.RUECKFRAGE_SCAFFOLD,
    )
    first, repeated = LernendenSignal.NICHTVERSTEHEN_1, LernendenSignal.NICHTVERSTEHEN_2_PLUS
    labels = (
        (explain, check),
        (check, explain),
        (explain, check),
        (explain, check),
        (explain, scaffold),
        (explain, scaffold),
        (explain, scaffold),
    )
    result = berechne_kennzahlen(
        matrix,
        Dialogverlauf(
            tutorzuege=tuple(
                Tutorzug(zug_nr=index, modi=modes, primaermodus=explain)
                for index, modes in enumerate(labels, 1)
            ),
            wendepunkte=(
                Wendepunkt(zug_nr=1, signal=first, huerde_id="qkv"),
                Wendepunkt(zug_nr=2, signal=repeated, huerde_id="qkv", wiederholung=2),
                Wendepunkt(zug_nr=3, signal=repeated, huerde_id="qkv", wiederholung=3),
                Wendepunkt(zug_nr=4, signal=repeated, huerde_id="softmax", wiederholung=2),
                Wendepunkt(zug_nr=5, signal=repeated, huerde_id="softmax", wiederholung=3),
                Wendepunkt(zug_nr=7, signal=repeated, huerde_id="softmax", wiederholung=4),
            ),
        ),
    )
    assert (result.festhaengen.laengste_folge, result.festhaengen.faelle) == (3, 6)
    assert "Näherung" in result.festhaengen.hinweis
    assert result.rueckfall.erster_zug is None


def test_empty_episode_and_invalid_turn_number(matrix: SignalModusMatrix) -> None:
    result = berechne_kennzahlen(matrix, Dialogverlauf(tutorzuege=(), wendepunkte=()))
    assert result.passung.nenner == result.latenz.nenner == result.festhaengen.faelle == 0
    assert result.passung.wert is None
    assert result.rueckfall.wert is None
    with pytest.raises(ValidationError, match="contiguous"):
        Dialogverlauf(
            tutorzuege=(Tutorzug(zug_nr=2, modi=(TutorModus.PRUEFEN,)),),
            wendepunkte=(),
        )
