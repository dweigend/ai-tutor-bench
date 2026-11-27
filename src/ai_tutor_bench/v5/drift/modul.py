"""Contracts for the two public drift episodes."""

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Annotated, Literal, Self, get_args

from pydantic import Field, TypeAdapter, field_validator, model_validator

from ..schema.signal_modus import FIRST_TURN, Contract, LernendenSignal, NonBlank
from ..szenarien.modul import (
    MAX_CALIBRATION_SIMILARITY,
    OPEN_QUESTION_START,
    Slug,
    SzenarioModul,
    lade_szenario_katalog,
    normalized_text,
)

TURNS = 32
TURN_NUMBERS = tuple(range(FIRST_TURN, TURNS + 1))
PruefpunktNummer = Literal[8, 16, 24, 32]
CHECKPOINTS: tuple[PruefpunktNummer, ...] = get_args(PruefpunktNummer)
MODULE_COUNT = 2
DRIFT_PATH = Path(__file__).with_name("drift-szenarien.json")
CALIBRATION_PATH = DRIFT_PATH.parent.parent / "schema" / "public-calibration.json"
QUESTION_PREFIX = re.compile(
    r"(?:\W*(?:ab|aber|also|bis|denn|doch|oder|seit|und|während|wegen|zwischen)\b)+",
    re.IGNORECASE,
)

type Zugnummer = Annotated[int, Field(ge=FIRST_TURN, le=TURNS)]
type Zielniveau = Literal["Prüfungsüberblick"]
type Aussageebene = Literal["Prozessqualität mit simulierten Lernenden – kein Lernergebnis"]
type MenschlicheLernwirkung = Literal["nicht_gemessen"]
type Kalibrierstatus = Literal["Entwicklungsmodul – formale Judge-Kalibrierung steht aus"]


PUBLIC_CALIBRATION = TypeAdapter(dict[Slug, tuple[NonBlank, ...]])


class TeilLernziel(Contract):
    ziel_id: Slug
    beschreibung: NonBlank


class Pruefpunkt(Contract):
    prueffrage_binaer: NonBlank
    pflichtzitat: Literal[True]

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
        prefix = QUESTION_PREFIX.match(question)
        if OPEN_QUESTION_START.match(question, prefix.end() if prefix else 0):
            raise ValueError("prueffrage_binaer must be a yes/no question")
        return question


class DriftZug(Contract):
    zug_nr: Zugnummer
    paedagogische_funktion: NonBlank
    signal: LernendenSignal | None
    ziel_id: Slug
    zielniveau: Zielniveau
    lernenden_text: NonBlank
    tutor_fixture: NonBlank
    tutor_drift_fixture: NonBlank | None = None
    reaktion_auf_tutordrift: NonBlank | None = None
    pruefpunkt: Pruefpunkt | None = None

    @model_validator(mode="after")
    def validate_turn(self) -> Self:
        if (self.pruefpunkt is not None) != (self.zug_nr in CHECKPOINTS):
            raise ValueError(f"pruefpunkt required exactly at {CHECKPOINTS}")
        if (
            self.reaktion_auf_tutordrift is not None
            and self.signal != LernendenSignal.SCHEINZUSTIMMUNG
        ):
            raise ValueError("the conditional learner reaction requires scheinzustimmung")
        return self


class DriftModul(Contract):
    stoff: Slug
    fach: NonBlank
    vereinbarung: NonBlank
    zielniveau: Zielniveau
    teil_lernziele: Annotated[tuple[TeilLernziel, ...], Field(min_length=2)]
    zuege: Annotated[tuple[DriftZug, ...], Field(min_length=TURNS, max_length=TURNS)]
    aussageebene: Aussageebene
    menschliche_lernwirkung: MenschlicheLernwirkung
    kalibrierstatus: Kalibrierstatus

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if tuple(zug.zug_nr for zug in self.zuege) != TURN_NUMBERS:
            raise ValueError("planned turns must be ordered and contiguous")
        goals = {goal.ziel_id for goal in self.teil_lernziele}
        if len(goals) != len(self.teil_lernziele) or goals != {zug.ziel_id for zug in self.zuege}:
            raise ValueError("each planned goal must be unique and assigned to a turn")
        return self

    @model_validator(mode="after")
    def validate_opportunities(self) -> Self:
        origins = {zug.zug_nr for zug in self.zuege if zug.tutor_drift_fixture is not None}
        reactions = {zug.zug_nr for zug in self.zuege if zug.reaktion_auf_tutordrift is not None}
        if not origins.isdisjoint(CHECKPOINTS):
            raise ValueError("tutor-initiated drift cannot start on a checkpoint")
        if not origins or {number + 1 for number in origins} != reactions:
            raise ValueError("each tutor-initiated drift needs a conditional learner reaction next")
        if any(self.zuege[number - FIRST_TURN].signal is not None for number in origins):
            raise ValueError("tutor-initiated drift must start on a regular turn")
        if not any(zug.signal == LernendenSignal.DETAILFRAGE_LEGITIM for zug in self.zuege):
            raise ValueError("planned turns must include a legitimate detail question")
        return self


class DriftKatalog(Contract):
    module: Annotated[
        tuple[DriftModul, ...], Field(min_length=MODULE_COUNT, max_length=MODULE_COUNT)
    ]

    @model_validator(mode="after")
    def validate_topics(self) -> Self:
        topics = {normalized_text(module.stoff) for module in self.module}
        if len(topics) != MODULE_COUNT:
            raise ValueError("drift modules must have different topics")
        return self


def _calibration_texts(
    references: dict[str, tuple[str, ...]], gt: tuple[SzenarioModul, ...]
) -> tuple[str, ...]:
    texts = [text for entries in references.values() for text in entries]
    for case in gt:
        texts.extend(entry.text for entry in case.vorlauf)
        texts.append(case.ausloeser_zug)
    return tuple(sorted({clean for text in texts if (clean := normalized_text(text))}))


def _matches_calibration(text: str, known: str) -> bool:
    if known in text:
        return True
    matcher = SequenceMatcher(None, known, text, autojunk=False)
    return (
        matcher.real_quick_ratio() >= MAX_CALIBRATION_SIMILARITY
        and matcher.quick_ratio() >= MAX_CALIBRATION_SIMILARITY
        and matcher.ratio() >= MAX_CALIBRATION_SIMILARITY
    )


def _validate_turn_texts(module: DriftModul, known_texts: tuple[str, ...]) -> None:
    for turn in module.zuege:
        texts = (
            turn.lernenden_text,
            turn.tutor_fixture,
            turn.tutor_drift_fixture,
            turn.reaktion_auf_tutordrift,
            turn.paedagogische_funktion,
            turn.pruefpunkt.prueffrage_binaer if turn.pruefpunkt else None,
        )
        clean_texts = (normalized_text(text) for text in texts if text is not None)
        if any(_matches_calibration(text, known) for text in clean_texts for known in known_texts):
            raise ValueError(f"{module.stoff}, turn {turn.zug_nr}: reuses a calibration text")


def lade_drift_katalog(path: Path = DRIFT_PATH) -> DriftKatalog:
    catalog = DriftKatalog.model_validate_json(path.read_bytes())
    gt = lade_szenario_katalog().faelle("kalibrierung")
    references = PUBLIC_CALIBRATION.validate_json(CALIBRATION_PATH.read_bytes())
    excluded = {normalized_text(topic) for topic in references}
    excluded.update(normalized_text(module.stoff) for module in gt)
    known_texts = _calibration_texts(references, gt)
    for module in catalog.module:
        content = normalized_text(module.model_dump_json())
        if any(topic in content for topic in excluded):
            raise ValueError(f"{module.stoff}: drift module reuses a calibration topic")
        _validate_turn_texts(module, known_texts)
    return catalog
