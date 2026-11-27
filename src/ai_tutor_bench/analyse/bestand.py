"""Öffentlicher Ebene-A-Bericht aus einem normalisierten JSON-Export.

Der Export enthält jede geplante Position als eigene Zeile. Verlaufszeilen
tragen einen laufübergreifend eindeutigen, opaken Episodenschlüssel.
Die Konfigurationen der MC-Sonden werden vor dem Export zufällig verblindet
und nur als Sonde-A, Sonde-B usw. angeliefert. Die Zuordnung bleibt separat.
"""

import argparse
import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    JsonValue,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from .detektoren import (
    LOCAL_PATTERNS,
    REPETITION,
    RULES_PATH,
    SHA256,
    Contract,
    LoadedRules,
    TurnMetrics,
    analyse_turn,
    load_rules,
    pattern_label,
)

Suite = Literal["v1", "v2", "v3", "hf"]
Status = Literal["ok", "offen", "abgeschnitten", "leer", "zensiert", "technisch"]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OFFERED: tuple[Status, ...] = ("ok", "abgeschnitten", "leer", "technisch")
CONFIDENCE = 0.95
BISECTION_STEPS = 60
MC_BLIND_LABEL = re.compile(r"^Sonde-[A-E]$")
LEVEL = "deterministisch"
PHASE_NOTE = "Zugindex und Skriptphase sind konfundiert."
COUNTS_NOTE = "Zählungen ohne Intervall; Züge derselben Episode sind abhängig; keine Rangfolge"

# Die Positionen folgen dem jeweiligen Ablaufschema in v3-/v2-abnahme.md.
V3_PHASES = (
    "Einstieg und Lernziele",
    "Wahl des Einstiegs",
    "Fehlvorstellung",
    "Begriffsfrage vor der Absprache",
    "Erstes Nichtverstehen",
    "Wiederholtes Nichtverstehen",
    "Absprache",
    "Begriffsfrage direkt nach der Absprache",
    "Eigene Erklärung",
    "Zustimmung ohne Beleg",
    "Zusammenfassung mit Fachfehler",
    "Exkurs",
    "Fortsetzung des Exkurses",
    "Erneute Begriffsfrage",
    "Eigene Erklärung",
    "Bilanz",
)
HART_V8_PHASES = (
    "Geratener Nenner",
    "Alternative Nenner",
    "Bitte um ein Beispiel",
    "Konkurrierende Ergebnisse",
)


class PlannedTurn(Contract):
    turn: PositiveInt
    status: Status
    visible: str | None = None
    episode: NonEmptyString | None = None
    sequence: Literal["hart-v8"] | None = None

    @model_validator(mode="after")
    def validate_visible(self) -> Self:
        if self.status == "abgeschnitten":
            return self
        if (self.status == "ok") != (self.text is not None):
            raise ValueError("Der sichtbare Text passt nicht zum Status des Tutorzuges.")
        return self

    @property
    def text(self) -> str | None:
        if self.visible and self.visible.strip():
            return self.visible
        return None


class MCProbe(Contract):
    configuration: str
    correct: NonNegativeInt
    trials: NonNegativeInt
    geplant: PositiveInt

    @field_validator("configuration")
    @classmethod
    def validate_configuration(cls, label: str) -> str:
        if not MC_BLIND_LABEL.fullmatch(label):
            raise ValueError("Öffentliche MC-Regelsonden brauchen verblindete Namen wie Sonde-A.")
        return label

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.correct > self.trials:
            raise ValueError("Die Zahl richtiger Antworten überschreitet die Zahl der MC-Sonden.")
        if self.trials > self.geplant:
            raise ValueError("Die Zahl beurteilbarer MC-Sonden überschreitet die Sollmenge.")
        return self


class Dataset(Contract):
    suite: Suite
    turns: tuple[PlannedTurn, ...]
    mc_probes: tuple[MCProbe, ...] = ()

    @model_validator(mode="after")
    def validate_design(self) -> Self:
        if self.mc_probes and self.suite != "v1":
            raise ValueError("MC-Regelsonden sind nur für v1 vorgesehen.")
        _own_episodes(self)
        return self


class Denominators(Contract):
    geplant: NonNegativeInt
    angebotene: NonNegativeInt
    beurteilbar: NonNegativeInt
    beurteilbar_davon_abgeschnitten: NonNegativeInt
    offen: NonNegativeInt
    abgeschnitten: NonNegativeInt
    leer: NonNegativeInt
    zensiert: NonNegativeInt
    technisch: NonNegativeInt

    @model_validator(mode="after")
    def validate_totals(self) -> Self:
        if self.geplant != self.angebotene + self.offen + self.zensiert:
            raise ValueError("Angebotene, offene und zensierte Züge ergeben nicht die Sollmenge.")
        complete = self.angebotene - self.abgeschnitten - self.leer - self.technisch
        if (
            complete < 0
            or self.beurteilbar != complete + self.beurteilbar_davon_abgeschnitten
            or self.beurteilbar_davon_abgeschnitten > self.abgeschnitten
        ):
            raise ValueError("Beurteilbare Züge und angebotene Ausfälle sind inkonsistent.")
        return self


def _denominators(rows: Sequence[PlannedTurn]) -> Denominators:
    counts = Counter(row.status for row in rows)
    return Denominators(
        geplant=len(rows),
        angebotene=sum(counts[status] for status in OFFERED),
        beurteilbar=sum(row.text is not None for row in rows),
        beurteilbar_davon_abgeschnitten=sum(
            row.status == "abgeschnitten" and row.text is not None for row in rows
        ),
        offen=counts["offen"],
        abgeschnitten=counts["abgeschnitten"],
        leer=counts["leer"],
        zensiert=counts["zensiert"],
        technisch=counts["technisch"],
    )


def _phases(suite: Suite) -> tuple[str, ...]:
    if suite == "v3":
        return V3_PHASES
    if suite == "v2":
        return HART_V8_PHASES
    return ()


def _own_episodes(data: Dataset) -> dict[str, list[PlannedTurn]]:
    episodes: dict[str, list[PlannedTurn]] = defaultdict(list)
    for row in data.turns:
        if row.sequence is not None and data.suite != "v2":
            raise ValueError("hart-v8 ist ausschließlich für v2 vorgesehen.")
        own_history = data.suite == "v3" or row.sequence == "hart-v8"
        if (row.episode is not None) != own_history:
            raise ValueError("Episodenschlüssel sind nur für v3 und v2 hart-v8 vorgesehen.")
        if row.episode is not None:
            episodes[row.episode].append(row)
    for rows in episodes.values():
        rows.sort(key=lambda row: row.turn)
        if [row.turn for row in rows] != list(range(1, len(_phases(data.suite)) + 1)):
            raise ValueError("Für jede Episode sind alle geplanten Positionen genau einmal nötig.")
    return episodes


def _histogram(counts: Collection[int]) -> dict[str, JsonValue]:
    return {str(value): count for value, count in sorted(Counter(counts).items())}


def _describe(rows: Sequence[PlannedTurn], metrics: Sequence[TurnMetrics]) -> dict[str, JsonValue]:
    return {
        "nenner": _denominators(rows).model_dump(mode="json"),
        "mustertreffer": {
            pattern_label(pattern): sum(pattern in metric.hits for metric in metrics)
            for pattern in LOCAL_PATTERNS
        },
        "verteilungen": {
            "zeichen": _histogram([metric.characters for metric in metrics]),
            "woerter": _histogram([metric.words for metric in metrics]),
            "fragen": _histogram([metric.questions for metric in metrics]),
            "aufgabenimpulse_inklusive_fragen": _histogram([metric.impulses for metric in metrics]),
        },
        "struktur": {
            "codeblock": sum(metric.code_block for metric in metrics),
            "markdown_tabelle": sum(metric.table for metric in metrics),
            "zahlenbeispiel_oder_formel": sum(
                metric.numeric_example_or_formula for metric in metrics
            ),
        },
    }


def _describe_similarity(
    metrics: Sequence[TurnMetrics], planned_pairs: int
) -> dict[str, JsonValue]:
    values = [metric.own_similarity for metric in metrics if metric.own_similarity is not None]
    return {
        "geplante_paare": planned_pairs,
        "vergleichbare_paare": len(values),
        "mittelwert_jaccard": math.fsum(values) / len(values) if values else None,
        pattern_label(REPETITION): sum(REPETITION in metric.hits for metric in metrics),
    }


def _evaluate_rows(
    rows: Sequence[PlannedTurn],
    loaded: LoadedRules,
    previous: dict[tuple[str, int], str | None],
) -> list[TurnMetrics]:
    result = []
    for row in rows:
        if row.text is None:
            continue
        prior = None if row.episode is None else previous.get((row.episode, row.turn - 1))
        result.append(analyse_turn(row.text, loaded.rules, previous_own=prior))
    return result


def _sequence_report(
    data: Dataset,
    episodes: dict[str, list[PlannedTurn]],
    loaded: LoadedRules,
    *,
    drift: bool,
    self_similarity: bool,
) -> dict[str, JsonValue]:
    previous = {}
    if self_similarity:
        previous = {
            (episode, row.turn): row.text for episode, rows in episodes.items() for row in rows
        }
    points: list[JsonValue] = []
    comparisons: list[TurnMetrics] = []
    for index, phase in enumerate(_phases(data.suite)):
        rows = [turns[index] for turns in episodes.values()]
        metrics = _evaluate_rows(rows, loaded, previous)
        point: dict[str, JsonValue] = {"zug": index + 1, "skriptphase": phase}
        if drift:
            point.update(_describe(rows, metrics))
        if self_similarity:
            point["selbst_aehnlichkeit"] = _describe_similarity(metrics, len(rows) if index else 0)
            comparisons.extend(metrics)
        points.append(point)
    report: dict[str, JsonValue] = {
        "suite": "hart-v8" if data.suite == "v2" else data.suite,
        "hinweis": PHASE_NOTE,
        "hinweis_zaehlungen": COUNTS_NOTE,
        "punkte": points,
    }
    if self_similarity:
        planned_pairs = len(episodes) * (len(_phases(data.suite)) - 1)
        report["selbst_aehnlichkeit"] = _describe_similarity(comparisons, planned_pairs)
    return report


def _upper_binomial_tail(successes: int, trials: int, p: float) -> float:
    return math.fsum(
        math.exp(
            math.lgamma(trials + 1)
            - math.lgamma(k + 1)
            - math.lgamma(trials - k + 1)
            + k * math.log(p)
            + (trials - k) * math.log1p(-p)
        )
        for k in range(successes, trials + 1)
    )


def _exact_lower(successes: int, trials: int) -> float:
    if successes == 0:
        return 0.0
    left, right = 0.0, 1.0
    for _ in range(BISECTION_STEPS):
        middle = (left + right) / 2
        if middle in (left, right):
            break
        if _upper_binomial_tail(successes, trials, middle) < (1 - CONFIDENCE) / 2:
            left = middle
        else:
            right = middle
    return (left + right) / 2


def clopper_pearson(correct: int, trials: int) -> tuple[float, float]:
    """Zweiseitiges exaktes 95-%-Intervall für beobachtete Binomialergebnisse."""
    if not trials > 0 or not 0 <= correct <= trials:
        raise ValueError("Für das MC-Intervall gilt 0 ≤ richtig ≤ Anzahl und Anzahl > 0.")
    return _exact_lower(correct, trials), 1 - _exact_lower(trials - correct, trials)


def summarize_mc(probes: Sequence[MCProbe]) -> list[JsonValue]:
    names = {probe.configuration for probe in probes}
    if len(names) != len(probes):
        raise ValueError("Mehrere MC-Summen haben dieselbe Konfiguration.")
    return [
        {
            "konfiguration": probe.configuration,
            "richtig": probe.correct,
            "geplant": probe.geplant,
            "beurteilbar": probe.trials,
            "offen": probe.geplant - probe.trials,
            "clopper_pearson_95_prozent": (
                list(clopper_pearson(probe.correct, probe.trials)) if probe.trials > 0 else None
            ),
        }
        for probe in sorted(probes, key=lambda probe: probe.configuration)
    ]


def assess(
    data: Dataset,
    loaded: LoadedRules,
    *,
    drift: bool | None = None,
    self_similarity: bool | None = None,
) -> dict[str, JsonValue]:
    episodes = _own_episodes(data)
    eligible = bool(episodes) or data.suite == "v3"
    if not eligible and (drift or self_similarity):
        raise ValueError("Verlauf und Selbst-Ähnlichkeit sind nur für v3 und v2 hart-v8 zulässig.")
    local = _describe(data.turns, _evaluate_rows(data.turns, loaded, {}))
    local["hinweis_zaehlungen"] = COUNTS_NOTE
    report: dict[str, JsonValue] = {
        "ebene": LEVEL,
        "suite": data.suite,
        "detektoren_version": loaded.rules.version,
        "detektoren_sha256": loaded.sha256,
        "lokal": local,
    }
    show_drift = eligible if drift is None else drift
    show_similarity = eligible if self_similarity is None else self_similarity
    if show_drift or show_similarity:
        report["verlauf"] = _sequence_report(
            data, episodes, loaded, drift=show_drift, self_similarity=show_similarity
        )
    if data.mc_probes:
        report["mc_regelsonden"] = summarize_mc(data.mc_probes)
    return report


# Public strings are generated by this module. Reject unexpected keys as well as values,
# including identifiers that are not known to the process.
PUBLIC_KEYS = frozenset(
    {
        "ebene",
        "suite",
        "detektoren_version",
        "detektoren_sha256",
        "lokal",
        "nenner",
        "mustertreffer",
        "verteilungen",
        "struktur",
        "zeichen",
        "woerter",
        "fragen",
        "aufgabenimpulse_inklusive_fragen",
        "codeblock",
        "markdown_tabelle",
        "zahlenbeispiel_oder_formel",
        "verlauf",
        "hinweis",
        "hinweis_zaehlungen",
        "punkte",
        "zug",
        "skriptphase",
        "selbst_aehnlichkeit",
        "geplante_paare",
        "vergleichbare_paare",
        "mittelwert_jaccard",
        "mc_regelsonden",
        "konfiguration",
        "richtig",
        "clopper_pearson_95_prozent",
        *Denominators.model_fields,
        *(pattern_label(pattern) for pattern in (*LOCAL_PATTERNS, REPETITION)),
    }
)
PUBLIC_TEXT: dict[str, Collection[str]] = {
    "suite": ("v1", "v2", "v3", "hf", "hart-v8"),
    "ebene": (LEVEL,),
    "hinweis": (PHASE_NOTE,),
    "hinweis_zaehlungen": (COUNTS_NOTE,),
    "skriptphase": (*V3_PHASES, *HART_V8_PHASES),
}
PUBLIC_PATTERNS = {"detektoren_sha256": SHA256, "konfiguration": MC_BLIND_LABEL}
HISTOGRAMS = ("zeichen", "woerter", "fragen", "aufgabenimpulse_inklusive_fragen")


def _public_text(key: str, value: str) -> bool:
    pattern = PUBLIC_PATTERNS.get(key)
    if pattern is not None:
        return bool(pattern.fullmatch(value))
    return value in PUBLIC_TEXT.get(key, ())


def guard_public_output(value: JsonValue, private_identifiers: Collection[str] = ()) -> None:
    """Prüft Schlüssel und Textwerte vor der Serialisierung. Fehler enthalten keine Kennungen."""
    normalized = {unicodedata.normalize("NFKC", token).casefold() for token in private_identifiers}
    escaped = [re.escape(token) for token in sorted(normalized) if token]
    tokens = re.compile(r"(?<!\w)(?:" + "|".join(escaped) + r")(?!\w)") if escaped else None

    def check_text(text: str, allowed: bool) -> None:
        normalized_text = unicodedata.normalize("NFKC", text).casefold()
        if not allowed or (tokens and tokens.search(normalized_text)):
            raise ValueError("Leak-Guard: Unerlaubter Schlüssel oder Textwert im Bericht.")

    def check(item: JsonValue, parent: str = "") -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                numeric_key = parent in HISTOGRAMS and bool(re.fullmatch(r"[0-9]+", key))
                check_text(key, key in PUBLIC_KEYS or numeric_key)
                check(child, key)
        elif isinstance(item, list):
            for child in item:
                check(child, parent)
        elif isinstance(item, str):
            check_text(item, _public_text(parent, item))

    check(value)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Normalisierter Export mit allen Sollpositionen")
    parser.add_argument("--output", type=Path, help="Öffentlicher Bericht, sonst stdout")
    parser.add_argument("--rules", type=Path, default=RULES_PATH)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--drift", action=argparse.BooleanOptionalAction)
    parser.add_argument("--self-similarity", action=argparse.BooleanOptionalAction)
    args = parser.parse_args(argv)
    try:
        loaded = load_rules(args.rules, expect_sha256=args.expect_sha256)
        source: Path = args.input
        try:
            data = Dataset.model_validate_json(source.read_bytes())
        except ValueError as error:
            raise ValueError("Ungültiger Eingabeexport. Bitte Vertrag prüfen.") from error
        report = assess(data, loaded, drift=args.drift, self_similarity=args.self_similarity)
        identifiers = {row.episode for row in data.turns if row.episode is not None}
        write_public(
            report,
            args.output,
            private_identifiers=identifiers,
            protected_paths=(source, args.rules),
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))


def write_public(
    report: dict[str, JsonValue],
    output: Path | None,
    *,
    private_identifiers: Collection[str] = (),
    protected_paths: Collection[Path] = (),
) -> None:
    guard_public_output(report, private_identifiers)
    serialized = json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    if output is None:
        print(serialized, end="")
    else:
        if output.exists() and any(os.path.samefile(output, path) for path in protected_paths):
            raise ValueError("Ausgabeort, Eingabeexport und Regelwerk müssen verschieden sein.")
        output.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
