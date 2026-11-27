"""Validated scenario catalogue for the public dialogue benchmark."""

import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Annotated, Literal, Self
from unicodedata import normalize

from pydantic import Field, StringConstraints, field_validator, model_validator

from ai_tutor_bench.v5.schema.signal_modus import (
    Contract,
    LernendenSignal,
    Messziel,
    Modes,
    NonBlank,
    SignalBeobachtung,
    SignalModusMatrix,
)

type GlatteisTriggerId = Literal[
    "GT1", "GT2", "GT3", "GT4", "GT5", "GT6", "GT7", "GT8", "GT9", "GT10"
]
type FallRolle = Literal["kalibrierung", "hauptmessung"]

SIGNAL_BY_TRIGGER: dict[GlatteisTriggerId, LernendenSignal] = {
    "GT1": LernendenSignal.EXKURS,
    "GT2": LernendenSignal.SCHEINZUSTIMMUNG,
    "GT3": LernendenSignal.ABKUERZUNGSBITTE,
    "GT4": LernendenSignal.GEGENREDE_FALSCH,
    "GT5": LernendenSignal.NICHTVERSTEHEN_2_PLUS,
    "GT6": LernendenSignal.DETAILFRAGE_LEGITIM,
    "GT7": LernendenSignal.GEGENREDE_RICHTIG,
    "GT8": LernendenSignal.HILFLOSIGKEIT,
    "GT9": LernendenSignal.VISUALISIERUNGSBITTE,
    "GT10": LernendenSignal.ABKUERZUNGSBITTE,
}
MIN_CALIBRATION_CASES = 1
MIN_MAIN_CASES = 2
MIN_MAIN_TOPICS = 2
MIN_GT10_GAP = 7
MAX_GT10_GAP = 12
MAX_CALIBRATION_SIMILARITY = 0.75
OPEN_QUESTION_START = re.compile(
    r"\W*(?:(?:an|auf|aus|bei|durch|für|gegen|in|mit|nach|ohne|über|um|unter|von|vor|zu)\s+)?"
    r"(?:wann|warum|was|welch\w*|wem|wen|wer|weshalb|wessen|weswegen|"
    r"wie|wieso|wieviel\w*|wieweit|inwiefern|inwieweit|"
    r"wo|wobei|wodurch|wofür|wogegen|woher|wohin|womit|wonach|woran|worauf|woraufhin|"
    r"woraus|worin|worüber|worum|worunter|wovon|wovor|wozu)\b",
    re.IGNORECASE,
)

SCENARIO_DIR = Path(__file__).parent
MATRIX_PATH = SCENARIO_DIR.parent / "schema" / "signal-modus-matrix.json"
CATALOG_PATH = SCENARIO_DIR / "gt1-gt10-katalog.json"

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]


class Dialogzug(Contract):
    rolle: Literal["lernender", "tutor"]
    text: NonBlank


class SzenarioModul(SignalBeobachtung):
    modul_id: Slug
    trigger: GlatteisTriggerId
    rolle: FallRolle
    stoff: Slug
    lernziel: NonBlank
    erlaubte_modi: Modes
    verbotene_modi: Modes
    paedagogische_funktion: NonBlank
    prueffrage_binaer: NonBlank
    pflichtzitat: Literal[True]
    messziele: Annotated[tuple[Messziel, ...], Field(min_length=1)]
    vorlauf: Annotated[tuple[Dialogzug, ...], Field(min_length=1)]
    ausloeser_zug: NonBlank
    gold_erwartung: NonBlank
    verbotenes_muster: NonBlank
    source_origin: Literal["synthetic-public"] | None = None
    zusatzflag: Literal["URSACHE_ERFRAGT"] | None = None
    aussageebene: Literal["Prozessqualität mit simulierten Lernenden – kein Lernergebnis"]
    menschliche_lernwirkung: Literal["nicht_gemessen"]

    @field_validator("pflichtzitat", mode="before")
    @classmethod
    def validate_quote_required(cls, value: object) -> object:
        if value is not True:
            raise ValueError("pflichtzitat must be the boolean true")
        return value

    @field_validator("prueffrage_binaer")
    @classmethod
    def validate_binary_question(cls, question: str) -> str:
        if question.count("?") != 1 or not question.rstrip().endswith("?"):
            raise ValueError("prueffrage_binaer must end in its only '?'")
        if OPEN_QUESTION_START.match(question):
            raise ValueError("prueffrage_binaer must be a yes/no question")
        return question

    @model_validator(mode="after")
    def validate_trigger_and_source(self) -> Self:
        if self.signal != SIGNAL_BY_TRIGGER[self.trigger]:
            raise ValueError(f"{self.modul_id}: {self.trigger} requires a different signal")
        if (self.rolle == "kalibrierung") != (self.source_origin is not None):
            raise ValueError("source_origin is required only for kalibrierung")
        if (self.trigger == "GT4") != (self.zusatzflag is not None):
            raise ValueError("URSACHE_ERFRAGT is required only for GT4")
        return self

    @model_validator(mode="after")
    def validate_late_challenge(self) -> Self:
        if self.trigger == "GT10" and (
            self.vorlauf[0].rolle != "tutor"
            or not MIN_GT10_GAP <= len(self.vorlauf) - 1 <= MAX_GT10_GAP
        ):
            raise ValueError(
                f"GT10 requires a tutor agreement in the first turn followed by "
                f"{MIN_GT10_GAP}–{MAX_GT10_GAP} intervening turns"
            )
        return self


def normalized_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize("NFKD", value.casefold()))


def normalized_prefix(module: SzenarioModul) -> tuple[str, ...]:
    return tuple(normalized_text(turn.text) for turn in module.vorlauf)


def contains_prefix(known: tuple[str, ...], turns: tuple[str, ...], task: str) -> bool:
    if "".join(known) in task:
        return True

    # Use one advancing iterator so inserted turns cannot hide an ordered copy.
    remaining_turns = iter(turns)
    return all(any(line in turn for turn in remaining_turns) for line in known)


def validate_split(calibration: tuple[SzenarioModul, ...], main: tuple[SzenarioModul, ...]) -> None:
    calibration_topics = {normalized_text(module.stoff) for module in calibration}
    ordered_topics = sorted(calibration_topics)
    calibration_scripts = [
        (normalized_prefix(module), normalized_text(module.ausloeser_zug)) for module in calibration
    ]
    for module in main:
        turns = (*normalized_prefix(module), normalized_text(module.ausloeser_zug))
        task = "".join(turns)
        content = normalized_text(
            " ".join(
                (
                    module.modul_id,
                    module.stoff,
                    module.lernziel,
                    task,
                    module.huerde_id or "",
                    module.paedagogische_funktion,
                    module.prueffrage_binaer,
                    module.gold_erwartung,
                    module.verbotenes_muster,
                )
            )
        )
        for topic in ordered_topics:
            if topic in content:
                raise ValueError(f"{module.modul_id}: calibration topic in hauptmessung: {topic}")
        for prefix, trigger in calibration_scripts:
            calibration_task = "".join(prefix) + trigger
            if (
                trigger in task
                or contains_prefix(prefix, turns, task)
                or SequenceMatcher(None, calibration_task, task).ratio()
                >= MAX_CALIBRATION_SIMILARITY
            ):
                raise ValueError(f"{module.modul_id}: calibration task reused in hauptmessung")


class SzenarioKatalog(Contract):
    module: tuple[SzenarioModul, ...]

    def faelle(self, rolle: FallRolle) -> tuple[SzenarioModul, ...]:
        return tuple(module for module in self.module if module.rolle == rolle)

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        if len({module.modul_id for module in self.module}) != len(self.module):
            raise ValueError("modul_id must be unique")
        calibration, main = self.faelle("kalibrierung"), self.faelle("hauptmessung")
        calibration_counts = Counter(module.trigger for module in calibration)
        for trigger in SIGNAL_BY_TRIGGER:
            if calibration_counts[trigger] < MIN_CALIBRATION_CASES:
                raise ValueError(f"{trigger}: requires at least one kalibrierung case")
            cases = [module for module in main if module.trigger == trigger]
            if len(cases) < MIN_MAIN_CASES:
                raise ValueError(f"{trigger}: requires at least two hauptmessung cases")
            if len({normalized_text(module.stoff) for module in cases}) < MIN_MAIN_TOPICS:
                raise ValueError(f"{trigger}: hauptmessung requires at least two different topics")
        validate_split(calibration, main)
        self.validate_matrix()
        return self

    def validate_matrix(self) -> None:
        matrix = SignalModusMatrix.model_validate_json(MATRIX_PATH.read_bytes())
        for module in self.module:
            rule = matrix.signale[module.signal]
            if (
                module.erlaubte_modi != rule.erlaubte_modi
                or module.verbotene_modi != rule.verbotene_modi
            ):
                raise ValueError(f"{module.modul_id}: modes differ from signal-modus-matrix.json")


def lade_szenario_katalog(path: Path = CATALOG_PATH) -> SzenarioKatalog:
    return SzenarioKatalog.model_validate_json(path.read_bytes())
