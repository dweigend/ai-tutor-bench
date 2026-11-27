"""Vertragsprüfungen mit ausschließlich synthetischen Tutorzügen."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Literal

import pytest
from pydantic import JsonValue, ValidationError

from ai_tutor_bench.analyse.bestand import (
    COUNTS_NOTE,
    Dataset,
    Denominators,
    MCProbe,
    PlannedTurn,
    Status,
    assess,
    clopper_pearson,
    guard_public_output,
    summarize_mc,
    write_public,
)
from ai_tutor_bench.analyse.detektoren import (
    RULES_PATH,
    PatternName,
    analyse_turn,
    load_rules,
    pattern_label,
)

REPEATED = "Wir legen zuerst drei helle Steine neben die große Schachtel."
DIFFERENT = "Beobachte morgen das tiefe Summen unter dem alten hölzernen Dach."


@pytest.mark.parametrize(
    ("text", "pattern", "expected"),
    [
        ("Was fällt dir auf? Warum könnte das so sein?", "DOPPELFRAGE", True),
        ("Was fällt dir auf und warum könnte das so sein?", "DOPPELFRAGE", True),
        ("Woran erkennst du gerade und ungerade Zahlen?", "DOPPELFRAGE", False),
        ("Berechne den Rest und begründe deinen Weg?", "DOPPELFRAGE", True),
        ("Berechne den Rest und begründe deinen Weg.", "DOPPELFRAGE", True),
        ("Erkläre den Unterschied. Welche Zahl bleibt?", "DOPPELFRAGE", True),
        ("1. Bestimme den Rest\n2. Vergleiche die Ergebnisse", "DOPPELFRAGE", True),
        ("Welche Zahl fehlt? Oder?", "DOPPELFRAGE", False),
        ("Welche Zahl fehlt? Stimmt's?", "DOPPELFRAGE", False),
        ("Welche Zahl fehlt, glaubst du?", "DOPPELFRAGE", False),
        ("Rechne erst im Kopf und auf Papier.", "DOPPELFRAGE", False),
        ("Möchtest du noch eine Skizze sehen?", "SERVICE_MENUE", True),
        ("Was möchtest du danach üben?", "SERVICE_MENUE", True),
        ("Passt. Soll ich dir einen Tipp geben?", "SERVICE_MENUE", True),
        ("Willst du an dieser Stelle stoppen?", "SERVICE_MENUE", True),
        ("Kann ich noch etwas ergänzen?", "SERVICE_MENUE", True),
        ("If you want, I can show another example.", "SERVICE_MENUE", True),
        ("Would you like a recap?", "SERVICE_MENUE", True),
        ("The lesson continues. Do you want to stop?", "SERVICE_MENUE", True),
        ("1. Mengen\n2. Zahlen\nWähle eine Option.", "SERVICE_MENUE", True),
        ("1) Shapes\n2) Colors\nPick one.", "SERVICE_MENUE", True),
        ("1. Mengen\n2. Zahlen\nBeide sind Beispiele.", "SERVICE_MENUE", False),
        ("Findest du die Stelle im Rechenweg?", "SERVICE_MENUE", False),
        ("Ich erkläre, was möchtest du danach tun bedeutet.", "SERVICE_MENUE", False),
        ("Genau!", "PAUSCHALLOB_PREFIX", True),
        ("Perfekt. Wie geht es weiter?", "PAUSCHALLOB_PREFIX", True),
        ("**Super**, jetzt zum nächsten Schritt.", "PAUSCHALLOB_PREFIX", True),
        ("Richtig so!", "PAUSCHALLOB_PREFIX", True),
        ("Sehr gut!", "PAUSCHALLOB_PREFIX", True),
        ("Toll!", "PAUSCHALLOB_PREFIX", True),
        ("Wir haben ein Ergebnis. Toll!", "PAUSCHALLOB_PREFIX", True),
        ("Fast.", "PAUSCHALLOB_PREFIX", False),
        ("Genau genommen fehlt noch eine Zeile.", "PAUSCHALLOB_PREFIX", False),
        ("Genau, weil du beide Seiten gleich verändert hast.", "PAUSCHALLOB_PREFIX", False),
        ("Sehr gut! Du hast beide Fälle korrekt getrennt.", "PAUSCHALLOB_PREFIX", False),
        ("Toll, dass du die Einheiten beachtet hast.", "PAUSCHALLOB_PREFIX", False),
        ("Deine Wahl ist super, weil sie zwei Fälle abdeckt.", "PAUSCHALLOB_PREFIX", False),
    ],
)
def test_local_patterns(text: str, pattern: PatternName, expected: bool) -> None:
    assert (pattern in analyse_turn(text, load_rules().rules).hits) is expected


def test_coordinated_decision_and_open_question() -> None:
    metrics = analyse_turn("Ist das richtig und warum?", load_rules().rules)
    assert metrics.questions == metrics.impulses == 2
    assert "DOPPELFRAGE" in metrics.hits


@pytest.mark.parametrize(
    "ignored",
    [
        "~~~py\n# Was passiert? Warum?\n~~~~",
        "\x60\x60\x60python\n# Was passiert? Warum?\n\x60\x60\x60",
        "\x60\x60what? why?\x60\x60",
        "https://example.invalid/search?q=Warum?",
        "Beispiel: „Was ist der Grund? Welche Zahl fehlt?“",
        'Beispiel: "Was ist der Grund?"',
        "> Was ist der Grund?\n> Welche Zahl fehlt?",
    ],
)
def test_ignored_examples(ignored: str) -> None:
    metrics = analyse_turn(f"{ignored}\nWelcher Schritt folgt?", load_rules().rules)
    assert metrics.questions == metrics.impulses == 1
    assert "DOPPELFRAGE" not in metrics.hits


def test_quoted_questions_across_soft_line_break() -> None:
    metrics = analyse_turn("„Was ist der Rest?\nWarum?“\nWelche Zahl fehlt?", load_rules().rules)
    assert metrics.questions == metrics.impulses == 1
    assert "DOPPELFRAGE" not in metrics.hits


@pytest.mark.parametrize("definition", [None, "", "   ", "Erste Zeile\nZweite Zeile"])
def test_rule_requires_one_line_definition(tmp_path: Path, definition: str | None) -> None:
    rules = json.loads(RULES_PATH.read_text())
    if definition is None:
        del rules["DOPPELFRAGE"]["definition"]
    else:
        rules["DOPPELFRAGE"]["definition"] = definition
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules))
    with pytest.raises(ValidationError, match="DOPPELFRAGE.definition"):
        load_rules(path)


def test_structure_and_length() -> None:
    text = "~~~\nprint(1)\n~~~\n| A | B |\n| --- | ---: |\n| 1 | 2 |\n\n3 + 4 = 7"
    metrics = analyse_turn(text, load_rules().rules)
    assert metrics.characters == len(text)
    assert metrics.words == 9
    assert metrics.code_block and metrics.table and metrics.numeric_example_or_formula
    plain = analyse_turn("Nur Text mit 2 beliebigen Wörtern.", load_rules().rules)
    assert not (plain.code_block or plain.table or plain.numeric_example_or_formula)


def test_repetition_threshold_and_own_history() -> None:
    rules = load_rules().rules
    exact = analyse_turn(REPEATED.upper(), rules, previous_own=REPEATED)
    assert exact.own_similarity == 1.0
    assert "WIEDERHOLUNG" in exact.hits
    different = analyse_turn(DIFFERENT, rules, previous_own=REPEATED)
    assert different.own_similarity == 0.0
    assert "WIEDERHOLUNG" not in different.hits
    short = analyse_turn("Eins zwei drei", rules, previous_own="Eins zwei drei")
    assert short.own_similarity is None
    assert "WIEDERHOLUNG" not in short.hits
    assert analyse_turn(REPEATED, rules).own_similarity is None


def test_repetition_includes_threshold() -> None:
    rules = load_rules().rules
    left = "Eins zwei drei vier fünf sechs sieben acht neun zehn."
    right = "Eins zwei drei vier fünf sechs sieben Birne Stern Laub."
    assert analyse_turn(left, rules, previous_own=right).own_similarity == pytest.approx(5 / 11)
    assert "WIEDERHOLUNG" not in analyse_turn(left, rules, previous_own=right).hits
    six = "Eins zwei drei vier fünf sechs sieben acht."
    threshold = "Eins zwei drei vier fünf sechs Rad Kiste."
    equal = analyse_turn(six, rules, previous_own=threshold)
    assert equal.own_similarity == 0.5
    assert "WIEDERHOLUNG" in equal.hits


def as_object(value: JsonValue) -> dict[str, JsonValue]:
    assert isinstance(value, dict)
    return value


def points_of(report: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    points = as_object(report["verlauf"])["punkte"]
    assert isinstance(points, list)
    return [as_object(point) for point in points]


@pytest.mark.parametrize("suite", ["v1", "hf", "v2"])
def test_local_suites_refuse_drift_and_similarity(suite: Literal["v1", "hf", "v2"]) -> None:
    data = Dataset(suite=suite, turns=(PlannedTurn(turn=2, status="ok", visible=REPEATED),))
    assert "verlauf" not in assess(data, load_rules())
    with pytest.raises(ValueError, match="nur für v3"):
        assess(data, load_rules(), drift=True)
    with pytest.raises(ValueError, match="nur für v3"):
        assess(data, load_rules(), self_similarity=True)
    with pytest.raises(ValidationError, match="Episodenschlüssel"):
        Dataset(suite=suite, turns=(PlannedTurn(turn=2, status="offen", episode="opaque-x"),))


def own_episode(
    size: int,
    episode: str,
    *,
    sequence: Literal["hart-v8"] | None = None,
    missing: int = 0,
) -> tuple[PlannedTurn, ...]:
    return tuple(
        PlannedTurn(
            turn=index,
            status="zensiert" if index == missing else "ok",
            visible=None if index == missing else REPEATED,
            episode=episode,
            sequence=sequence,
        )
        for index in range(1, size + 1)
    )


def test_hart_v8_isolated_from_fixed_anchors() -> None:
    local = PlannedTurn(turn=1, status="ok", visible="Welche Zahl? Welcher Weg?")
    sequence = own_episode(4, "opaque-h", sequence="hart-v8")
    data = Dataset(suite="v2", turns=(local, *reversed(sequence)))
    report = assess(data, load_rules())
    points = points_of(report)
    assert [point["zug"] for point in points] == [1, 2, 3, 4]
    assert points[0]["skriptphase"] == "Geratener Nenner"
    assert as_object(points[0]["nenner"])["geplant"] == 1
    assert as_object(as_object(report["lokal"])["nenner"])["geplant"] == 5
    assert as_object(points[0]["mustertreffer"])[pattern_label("DOPPELFRAGE")] == 0
    assert as_object(points[1]["selbst_aehnlichkeit"])[pattern_label("WIEDERHOLUNG")] == 1


def test_v3_phases_and_missing_immediate_history() -> None:
    data = Dataset(
        suite="v3",
        turns=(*own_episode(16, "opaque-x", missing=2), *own_episode(16, "opaque-y")),
    )
    report = assess(data, load_rules())
    points = points_of(report)
    assert [point["zug"] for point in points] == list(range(1, 17))
    assert points[6]["skriptphase"] == "Absprache"
    assert points[11]["skriptphase"] == "Exkurs"
    assert points[15]["skriptphase"] == "Bilanz"
    assert "konfundiert" in str(as_object(report["verlauf"])["hinweis"])
    assert as_object(report["verlauf"])["hinweis_zaehlungen"] == COUNTS_NOTE
    assert as_object(points[0]["selbst_aehnlichkeit"])["vergleichbare_paare"] == 0
    assert as_object(points[2]["selbst_aehnlichkeit"])["vergleichbare_paare"] == 1
    overall = as_object(as_object(report["verlauf"])["selbst_aehnlichkeit"])
    assert overall["geplante_paare"] == 30
    assert overall["vergleichbare_paare"] == 28
    assert overall[pattern_label("WIEDERHOLUNG")] == 28


def test_sequence_requires_unique_complete_plan() -> None:
    sequence = own_episode(4, "opaque-h", sequence="hart-v8")
    with pytest.raises(ValidationError, match="genau einmal"):
        Dataset(suite="v2", turns=(*sequence[:-1], sequence[0]))


def test_denominators_keep_all_outcomes() -> None:
    statuses: list[tuple[Status, str | None]] = [
        ("ok", "Ein gültiger Zug."),
        ("abgeschnitten", "Ein sichtbarer Anfang"),
        ("abgeschnitten", None),
        ("leer", ""),
        ("zensiert", None),
        ("technisch", None),
        ("offen", None),
    ]
    rows = tuple(
        PlannedTurn(turn=1, status=status, visible=visible) for status, visible in statuses
    )
    report = assess(Dataset(suite="hf", turns=rows), load_rules())
    local = as_object(report["lokal"])
    assert local["hinweis_zaehlungen"] == COUNTS_NOTE
    assert local["nenner"] == {
        "geplant": 7,
        "angebotene": 5,
        "beurteilbar": 2,
        "beurteilbar_davon_abgeschnitten": 1,
        "offen": 1,
        "abgeschnitten": 2,
        "leer": 1,
        "zensiert": 1,
        "technisch": 1,
    }
    assert as_object(as_object(local["verteilungen"])["fragen"]) == {"0": 2}
    with pytest.raises(ValidationError, match="Sollmenge"):
        Denominators.model_validate(as_object(local["nenner"]) | {"geplant": 6})
    with pytest.raises(ValidationError, match="inkonsistent"):
        Denominators.model_validate(
            as_object(local["nenner"]) | {"beurteilbar_davon_abgeschnitten": 0}
        )
    with pytest.raises(ValidationError, match="sichtbare Text"):
        PlannedTurn(turn=1, status="leer", visible="Nicht leer")


@pytest.mark.parametrize(
    ("correct", "expected"), [(10, (0.6915, 1.0)), (7, (0.3475, 0.9333)), (0, (0.0, 0.3085))]
)
def test_clopper_pearson(correct: int, expected: tuple[float, float]) -> None:
    assert tuple(round(value, 4) for value in clopper_pearson(correct, 10)) == expected


def test_mc_sorted_by_configuration() -> None:
    probes = (
        MCProbe(configuration="Sonde-E", correct=10, trials=10, geplant=10),
        MCProbe(configuration="Sonde-A", correct=7, trials=10, geplant=12),
    )
    data = Dataset(suite="v1", turns=(), mc_probes=probes)
    output = assess(data, load_rules())
    guard_public_output(output)
    rows = output["mc_regelsonden"]
    assert isinstance(rows, list)
    assert [as_object(row)["konfiguration"] for row in rows] == ["Sonde-A", "Sonde-E"]
    assert [as_object(row)["richtig"] for row in rows] == [7, 10]
    assert [as_object(row)["geplant"] for row in rows] == [12, 10]
    assert [as_object(row)["beurteilbar"] for row in rows] == [10, 10]
    assert [as_object(row)["offen"] for row in rows] == [2, 0]
    with pytest.raises(ValueError, match="dieselbe Konfiguration"):
        summarize_mc((*probes, probes[0]))


@pytest.mark.parametrize(
    "label", ["Sonde-OPUS", "Sonde-Z", "private-route", " Sonde-A", "Sonde-A\n"]
)
def test_mc_rejects_nonblind_label(label: str) -> None:
    with pytest.raises(ValidationError, match="verblindete Namen"):
        MCProbe(configuration=label, correct=2, trials=10, geplant=10)
    with pytest.raises(ValueError, match="Leak-Guard"):
        guard_public_output({"konfiguration": label})


def test_mc_rejects_trials_above_plan() -> None:
    with pytest.raises(ValidationError, match="Sollmenge"):
        MCProbe(configuration="Sonde-A", correct=2, trials=10, geplant=9)


def test_leak_guard_ignores_identifier_inside_word() -> None:
    guard_public_output({"ebene": "deterministisch"}, private_identifiers=("is",))


@pytest.mark.parametrize(
    ("leak", "identifiers"),
    [
        ({"modell": "opaque-x"}, ()),
        ({"arm": 0}, ()),
        ({"seed": 42}, ()),
        ({"opaque-x": 2}, ()),
        ({"konfiguration": "opaque-x"}, ()),
        ({"konfiguration": "Sonde-A"}, ("sonde-a",)),
    ],
)
def test_leak_guard_stops_before_writing(
    tmp_path: Path, leak: dict[str, JsonValue], identifiers: tuple[str, ...]
) -> None:
    output = tmp_path / "public.json"
    output.write_text("original")
    with pytest.raises(ValueError, match="Leak-Guard"):
        write_public({"lokal": leak}, output, private_identifiers=identifiers)
    assert output.read_text() == "original"


def run_cli(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", "-m", f"ai_tutor_bench.analyse.{module}", *args],
        cwd=RULES_PATH.parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_hash_freeze_and_public_aggregation(tmp_path: Path) -> None:
    digest = hashlib.sha256(RULES_PATH.read_bytes()).hexdigest()
    checked = run_cli("detektoren", "--expect-sha256", digest.upper())
    assert checked.returncode == 0
    assert checked.stdout.strip() == digest

    source = tmp_path / "synthetic.json"
    report = tmp_path / "public.json"
    command = (str(source), "--output", str(report), "--expect-sha256")
    mismatch = run_cli("bestand", *command, "0" * 64)
    assert mismatch.returncode == 2
    assert "stimmt nicht überein" in mismatch.stderr
    assert not report.exists()

    source.write_text(
        Dataset(suite="v3", turns=own_episode(16, "opaque-episode-x")).model_dump_json()
    )
    success = run_cli("bestand", *command, digest)
    assert success.returncode == 0, success.stderr
    public_text = report.read_text()
    assert "opaque-episode-x" not in public_text and REPEATED not in public_text
    assert json.loads(public_text)["detektoren_sha256"] == digest


@pytest.mark.parametrize("protected", ["export", "rules"])
def test_cli_rejects_hardlinked_output(tmp_path: Path, protected: str) -> None:
    source = tmp_path / "export.json"
    source.write_text(Dataset(suite="v1", turns=()).model_dump_json())
    rules = tmp_path / "rules.json"
    rules.write_bytes(RULES_PATH.read_bytes())
    target = source if protected == "export" else rules
    original = target.read_bytes()
    output = tmp_path / "public.json"
    output.hardlink_to(target)

    result = run_cli(
        "bestand",
        str(source),
        "--output",
        str(output),
        "--rules",
        str(rules),
        "--expect-sha256",
        hashlib.sha256(rules.read_bytes()).hexdigest(),
    )
    assert result.returncode == 2
    assert "müssen verschieden sein" in result.stderr
    assert target.read_bytes() == original


def test_combined_decision_and_w_question_before_enumeration() -> None:
    metrics = analyse_turn(
        "Ist das richtig und woran erkennst du gerade und ungerade Zahlen?",
        load_rules().rules,
    )
    assert metrics.questions == metrics.impulses == 2
    assert "DOPPELFRAGE" in metrics.hits


def test_mc_probe_allows_zero_trials_as_fully_open() -> None:
    loaded = load_rules()
    data = Dataset(
        suite="v1",
        turns=(),
        mc_probes=(MCProbe(configuration="Sonde-A", correct=0, trials=0, geplant=12),),
    )
    report = assess(data, loaded)
    guard_public_output(report)
    probes = report["mc_regelsonden"]
    assert isinstance(probes, list)
    assert probes == [
        {
            "konfiguration": "Sonde-A",
            "richtig": 0,
            "geplant": 12,
            "beurteilbar": 0,
            "offen": 12,
            "clopper_pearson_95_prozent": None,
        }
    ]
