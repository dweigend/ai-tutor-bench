"""Target tracking from turn labels and evidence checks for whole-episode judgments."""

import re
from collections.abc import Sequence
from itertools import groupby
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, StringConstraints, field_validator, model_validator

from ..schema.signal_modus import FIRST_TURN, Contract, NonBlank, ZaehlerNenner
from .modul import (
    CHECKPOINTS,
    TURN_NUMBERS,
    TURNS,
    Aussageebene,
    Kalibrierstatus,
    MenschlicheLernwirkung,
    PruefpunktNummer,
    Zugnummer,
)

MIN_QUOTE_CHARS = 15
MIN_QUOTE_WORDS = 3
CHECKPOINT_COUNT = len(CHECKPOINTS)
QUOTE_WORD = re.compile(r"\b[^\W\d_]+(?:[-’'][^\W\d_]+)*\b")


def _validate_quote(quote: str) -> str:
    if len(quote.strip()) < MIN_QUOTE_CHARS or len(QUOTE_WORD.findall(quote)) < MIN_QUOTE_WORDS:
        raise ValueError(
            f"quote requires at least {MIN_QUOTE_CHARS} characters and {MIN_QUOTE_WORDS} words"
        )
    return quote


type EvidenceQuote = Annotated[
    NonBlank, StringConstraints(min_length=MIN_QUOTE_CHARS), AfterValidator(_validate_quote)
]


class ZielverfolgungZug(Contract):
    zug_nr: Zugnummer
    bearbeitetes_lernziel: NonBlank | None
    detailtiefe: Literal["unter_niveau", "passend", "zu_tief"]
    zielbezug: bool
    detailfrage_legitim_gewahrt: bool | None
    prueffrage_erfuellt: bool | None = None

    @model_validator(mode="after")
    def validate_labels(self) -> Self:
        if self.zielbezug != (self.bearbeitetes_lernziel is not None):
            raise ValueError("zielbezug requires a goal ID and a goal ID requires zielbezug")
        if self.prueffrage_erfuellt is not None and self.zug_nr not in CHECKPOINTS:
            raise ValueError("prueffrage_erfuellt is reserved for checkpoint turns")
        return self


class ZielferneStrecke(Contract):
    laengste_strecke: Annotated[int, Field(ge=0, le=TURNS)]
    zuege_gesamt: Annotated[int, Field(ge=0, le=TURNS)]


class PruefpunktStatus(Contract):
    zug_nr: Zugnummer
    status: Literal["erfuellt", "nicht_erfuellt", "nicht_beobachtet", "nicht_kodiert"]


AUSSAGEEBENE: Aussageebene = "Prozessqualität mit simulierten Lernenden – kein Lernergebnis"


class Zielverfolgung(Contract):
    anteil_zielbezug: ZaehlerNenner
    zielabdeckung_ende: ZaehlerNenner
    laengste_zielferne_strecke: ZielferneStrecke
    zu_tief_zuege: ZaehlerNenner
    detailfrage_legitim_gewahrt: ZaehlerNenner
    pruefpunkt_status: tuple[PruefpunktStatus, ...]
    aussageebene: Aussageebene = AUSSAGEEBENE


def _goal_at_level(turn: ZielverfolgungZug) -> str | None:
    if turn.detailtiefe == "passend":
        return turn.bearbeitetes_lernziel
    return None


def _checkpoint_status(number: int, turns: Sequence[ZielverfolgungZug]) -> PruefpunktStatus:
    if number > len(turns):
        return PruefpunktStatus(zug_nr=number, status="nicht_beobachtet")
    passed = turns[number - FIRST_TURN].prueffrage_erfuellt
    if passed is None:
        return PruefpunktStatus(zug_nr=number, status="nicht_kodiert")
    return PruefpunktStatus(zug_nr=number, status="erfuellt" if passed else "nicht_erfuellt")


def berechne_zielverfolgung(
    zuege: Sequence[ZielverfolgungZug],
    ziel_ids: Sequence[str],
) -> Zielverfolgung:
    """Aggregate an observed prefix. Only goal-related coverage at the agreed depth counts."""
    total = len(zuege)
    if tuple(zug.zug_nr for zug in zuege) != TURN_NUMBERS[:total]:
        raise ValueError("observed turns must be ordered and contiguous")
    goals = set(ziel_ids)
    if not goals or len(goals) != len(ziel_ids) or any(not goal.strip() for goal in goals):
        raise ValueError("planned goal IDs must be nonempty and unique")
    observed = {zug.bearbeitetes_lernziel for zug in zuege}
    if observed - goals - {None}:
        raise ValueError("turn label refers to an unplanned goal")
    reached = {_goal_at_level(zug) for zug in zuege} - {None}
    detail_questions = [
        zug.detailfrage_legitim_gewahrt
        for zug in zuege
        if zug.detailfrage_legitim_gewahrt is not None
    ]
    longest = max(
        (
            sum(1 for _ in group)
            for related, group in groupby(zuege, lambda z: z.zielbezug)
            if not related
        ),
        default=0,
    )
    return Zielverfolgung(
        anteil_zielbezug=ZaehlerNenner(zaehler=sum(zug.zielbezug for zug in zuege), nenner=total),
        zielabdeckung_ende=ZaehlerNenner(zaehler=len(reached), nenner=len(goals)),
        laengste_zielferne_strecke=ZielferneStrecke(laengste_strecke=longest, zuege_gesamt=total),
        zu_tief_zuege=ZaehlerNenner(
            zaehler=sum(zug.detailtiefe == "zu_tief" for zug in zuege), nenner=total
        ),
        detailfrage_legitim_gewahrt=ZaehlerNenner(
            zaehler=sum(detail_questions), nenner=len(detail_questions)
        ),
        pruefpunkt_status=tuple(_checkpoint_status(number, zuege) for number in CHECKPOINTS),
        aussageebene=AUSSAGEEBENE,
    )


class EpisodenDialogzug(Contract):
    zug_nr: Zugnummer
    lernenden_text: NonBlank
    tutor_text: NonBlank


class PruefpunktUrteil(Contract):
    zug_nr: PruefpunktNummer
    erfuellt: bool
    zitat: EvidenceQuote

    @field_validator("zug_nr", mode="before")
    @classmethod
    def validate_number(cls, number: object) -> object:
        if type(number) is not int:
            raise ValueError("checkpoint turn number must be an integer")
        return number


class EpisodenJudgeUrteil(Contract):
    dialog: Annotated[tuple[EpisodenDialogzug, ...], Field(min_length=TURNS, max_length=TURNS)]
    erster_ausfall_zug: Zugnummer | None
    ausfall_grund: NonBlank | None
    pflichtzitat: EvidenceQuote | None
    pruefpunkte: Annotated[
        tuple[PruefpunktUrteil, ...],
        Field(min_length=CHECKPOINT_COUNT, max_length=CHECKPOINT_COUNT),
    ]
    label_source: Literal["entwicklungs_dryrun", "human_gold", "panel_llm", "deterministic"]
    aussageebene: Aussageebene
    menschliche_lernwirkung: MenschlicheLernwirkung
    kalibrierstatus: Kalibrierstatus

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if tuple(zug.zug_nr for zug in self.dialog) != TURN_NUMBERS:
            raise ValueError("episode dialog must contain turns 1 through 32 in order")
        if tuple(sorted(point.zug_nr for point in self.pruefpunkte)) != CHECKPOINTS:
            raise ValueError(f"episode requires exactly one judgment at each of {CHECKPOINTS}")
        for point in self.pruefpunkte:
            if point.zitat not in self.dialog[point.zug_nr - FIRST_TURN].tutor_text:
                raise ValueError(
                    f"checkpoint quote must occur verbatim in tutor turn {point.zug_nr}"
                )
        return self

    @model_validator(mode="after")
    def validate_first_failure(self) -> Self:
        number = self.erster_ausfall_zug
        if number is None:
            if self.ausfall_grund is not None or self.pflichtzitat is not None:
                raise ValueError("reason and quote require a failure turn")
            return self
        if self.ausfall_grund is None or self.pflichtzitat is None:
            raise ValueError("failure turn requires a reason and quote")
        if self.pflichtzitat not in self.dialog[number - FIRST_TURN].tutor_text:
            raise ValueError("quote must occur verbatim in the cited tutor turn")
        return self
