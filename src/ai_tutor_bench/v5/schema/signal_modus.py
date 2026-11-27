"""Contracts and deterministic metrics for the public signal-mode matrix."""

from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.json_schema import models_json_schema

SIGNAL_COUNT = 12
MODE_COUNT = 8
MIN_PROBE_TURNS = 24
FIRST_TURN = 1
FIRST_REPETITION = 2

NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
ShortQuote = Annotated[NonBlank, StringConstraints(max_length=180)]
TurnIndex = Annotated[int, Field(ge=FIRST_TURN)]
Count = Annotated[int, Field(ge=0)]
LabelSource = Literal["synthetische_entwicklung", "human_gold", "panel_llm", "deterministic"]
Messziel = Literal["G1", "G2", "G3", "G4", "G5"]
Zensurgrund = Literal["folgesignal", "verlaufsende", "keine_gelegenheit"]


class LernendenSignal(StrEnum):
    NICHTVERSTEHEN_1 = "nichtverstehen_1"
    NICHTVERSTEHEN_2_PLUS = "nichtverstehen_2_plus"
    SCHEINZUSTIMMUNG = "scheinzustimmung"
    KORREKTE_LOESUNG = "korrekte_loesung"
    GEGENREDE_FALSCH = "gegenrede_falsch"
    GEGENREDE_RICHTIG = "gegenrede_richtig"
    EXKURS = "exkurs"
    DETAILFRAGE_LEGITIM = "detailfrage_legitim"
    FRUST_SELBSTZWEIFEL = "frust_selbstzweifel"
    ABKUERZUNGSBITTE = "abkuerzungsbitte"
    HILFLOSIGKEIT = "hilflosigkeit"
    VISUALISIERUNGSBITTE = "visualisierungsbitte"


class TutorModus(StrEnum):
    ZIEL_STEUERN = "ZIEL_STEUERN"
    ERKLAEREN = "ERKLAEREN"
    VISUALISIEREN = "VISUALISIEREN"
    PRUEFEN = "PRUEFEN"
    RUECKFRAGE_SCAFFOLD = "RUECKFRAGE_SCAFFOLD"
    MOTIVIEREN = "MOTIVIEREN"
    SERVICE = "SERVICE"
    TELLING = "TELLING"


RUECKFALL_MODI = frozenset({TutorModus.SERVICE, TutorModus.TELLING})


class Auswertungsrahmen(StrEnum):
    AUSSAGEEBENE = "Prozessqualität mit simulierten Lernenden"
    KALIBRIERSTATUS = "Prozessqualität – Entwicklungsschema, formale Kalibrierung steht aus"


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


Modes = Annotated[
    tuple[TutorModus, ...], Field(max_length=MODE_COUNT, json_schema_extra={"uniqueItems": True})
]


class SignalModusRegel(Contract):
    beschreibung: NonBlank
    erlaubte_modi: Annotated[Modes, Field(min_length=1)]
    verbotene_modi: Modes
    verbotene_handlungen: Annotated[tuple[NonBlank, ...], Field(min_length=1)]
    messziele: Annotated[tuple[Messziel, ...], Field(min_length=1)]
    paedagogische_funktion: NonBlank

    @model_validator(mode="after")
    def validate_modes(self) -> Self:
        allowed, forbidden = set(self.erlaubte_modi), set(self.verbotene_modi)
        if allowed & forbidden:
            raise ValueError("Allowed and forbidden modes must be disjoint")
        if len(allowed) != len(self.erlaubte_modi) or len(forbidden) != len(self.verbotene_modi):
            raise ValueError("Each mode may appear only once per list")
        return self


class SignalModusMatrix(Contract):
    revision: Literal["public-v5-signal-mode-1"]
    aussageebene: Literal[Auswertungsrahmen.AUSSAGEEBENE]
    menschliche_lernwirkung: Literal["nicht_gemessen"]
    modusdefinitionen: Annotated[
        dict[TutorModus, NonBlank], Field(min_length=MODE_COUNT, max_length=MODE_COUNT)
    ]
    signale: Annotated[
        dict[LernendenSignal, SignalModusRegel],
        Field(min_length=SIGNAL_COUNT, max_length=SIGNAL_COUNT),
    ]


class SignalBeobachtung(Contract):
    signal: LernendenSignal
    huerde_id: NonBlank | None = None
    wiederholung: Annotated[int, Field(ge=FIRST_REPETITION)] | None = None

    @model_validator(mode="after")
    def validate_stocken(self) -> Self:
        repeated = self.signal is LernendenSignal.NICHTVERSTEHEN_2_PLUS
        stocken = repeated or self.signal is LernendenSignal.NICHTVERSTEHEN_1
        if stocken != (self.huerde_id is not None):
            raise ValueError("Only stocken signals use huerde_id, which they require")
        if repeated != (self.wiederholung is not None):
            raise ValueError("Only nichtverstehen_2_plus requires wiederholung")
        return self


class ModusLabel(Contract):
    modi: Annotated[Modes, Field(min_length=1)]
    primaermodus: TutorModus | None = None

    @model_validator(mode="after")
    def validate_label(self) -> Self:
        if len(set(self.modi)) != len(self.modi):
            raise ValueError("Tutor modes must be unique")
        if self.primaermodus is not None and self.primaermodus not in self.modi:
            raise ValueError("The primary mode must also occur in modi")
        return self


class WendepunktUrteil(Contract):
    zug_nr: TurnIndex
    signal: LernendenSignal
    signal_erkannt: bool
    passende_handlung_ausgefuehrt: bool
    naechster_eigener_schritt_ermoeglicht: bool
    pflichtzitat: NonBlank
    beleg_eingeholt: bool | None = None
    beleg_spaeter_genutzt: bool | None = None
    label_source: LabelSource

    @model_validator(mode="after")
    def validate_beleg(self) -> Self:
        if self.beleg_spaeter_genutzt is True and self.beleg_eingeholt is not True:
            raise ValueError("beleg_spaeter_genutzt requires beleg_eingeholt to be true")
        return self


class SyntheticLabel(ModusLabel):
    source_reference: NonBlank
    zug_nr: TurnIndex
    tutor_nachrichtenrolle: Literal["user", "assistant"]
    originalzitat: ShortQuote
    signal_zug_nr: TurnIndex
    signalzitat: ShortQuote
    beobachtung: SignalBeobachtung
    abgrenzungsnotiz: NonBlank
    label_source: Literal["synthetische_entwicklung"]

    @model_validator(mode="after")
    def validate_source_order(self) -> Self:
        if self.signal_zug_nr >= self.zug_nr:
            raise ValueError("The learner source message must precede the tutor source message")
        return self


class SyntheticLabels(Contract):
    eintraege: Annotated[tuple[SyntheticLabel, ...], Field(min_length=MIN_PROBE_TURNS)]
    nicht_belegte_signale: dict[LernendenSignal, NonBlank]

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        turns = {(entry.source_reference, entry.zug_nr) for entry in self.eintraege}
        if len(turns) != len(self.eintraege):
            raise ValueError("Probe tutor messages must be unique")
        if {mode for entry in self.eintraege for mode in entry.modi} != set(TutorModus):
            raise ValueError("Probe turns must illustrate all tutor modes")
        observed = {entry.beobachtung.signal for entry in self.eintraege}
        if set(self.nicht_belegte_signale) != set(LernendenSignal) - observed:
            raise ValueError("Unattested signals must account for exactly the missing signals")
        return self


class Tutorzug(ModusLabel):
    zug_nr: TurnIndex


class Wendepunkt(SignalBeobachtung):
    zug_nr: TurnIndex


class Dialogverlauf(Contract):
    tutorzuege: tuple[Tutorzug, ...]
    wendepunkte: tuple[Wendepunkt, ...]

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        after_last = FIRST_TURN + len(self.tutorzuege)
        if [turn.zug_nr for turn in self.tutorzuege] != list(range(FIRST_TURN, after_last)):
            raise ValueError("Observed tutor turns must be contiguous and start at 1")
        pivots = [pivot.zug_nr for pivot in self.wendepunkte]
        if pivots != sorted(set(pivots)) or any(index > after_last for index in pivots):
            raise ValueError(
                "Wendepunkte must be ordered, unique and at most one turn past the end"
            )
        return self


class ZaehlerNenner(Contract):
    zaehler: Count
    nenner: Count


class Anteil(ZaehlerNenner):
    wert: Annotated[float, Field(ge=0, le=1)] | None


class LatenzFall(Contract):
    zug_nr: TurnIndex
    beobachtete_zuege: Count
    latenz: Count | None
    zensurgrund: Zensurgrund | None

    @model_validator(mode="after")
    def validate_zensur(self) -> Self:
        if self.latenz is not None:
            if self.zensurgrund is not None or self.latenz >= self.beobachtete_zuege:
                raise ValueError("Reached latency must fall within the uncensored window")
        elif self.zensurgrund is None or (self.zensurgrund == "keine_gelegenheit") != (
            self.beobachtete_zuege == 0
        ):
            raise ValueError("Censored latency requires a reason consistent with the window")
        return self


class Latenz(ZaehlerNenner):
    faelle: tuple[LatenzFall, ...]


class FesthaengenKennzahl(Contract):
    laengste_folge: Count
    faelle: Count
    hinweis: NonBlank = "Gleiche Modusmenge und gleicher Primärmodus sind eine grobe Näherung."


class Rueckfall(Anteil):
    erster_zug: TurnIndex | None


class Kennzahlen(Contract):
    aussageebene: Literal[Auswertungsrahmen.AUSSAGEEBENE] = Auswertungsrahmen.AUSSAGEEBENE
    kalibrierstatus: Literal[Auswertungsrahmen.KALIBRIERSTATUS] = Auswertungsrahmen.KALIBRIERSTATUS
    menschliche_lernwirkung: Literal["nicht_gemessen"] = "nicht_gemessen"
    nicht_beobachtbar: Count
    passung: Anteil
    latenz: Latenz
    festhaengen: FesthaengenKennzahl
    rueckfall: Rueckfall


def _passt(zug: Tutorzug, regel: SignalModusRegel) -> bool:
    return zug.primaermodus in regel.erlaubte_modi and not set(zug.modi).intersection(
        regel.verbotene_modi
    )


def _latenzfaelle(verlauf: Dialogverlauf, matrix: SignalModusMatrix) -> tuple[LatenzFall, ...]:
    end = FIRST_TURN + len(verlauf.tutorzuege)
    pivots = verlauf.wendepunkte
    cases = []
    for next_index, pivot in enumerate(pivots, start=1):
        has_next = next_index < len(pivots)
        stop = pivots[next_index].zug_nr if has_next else end
        turns = verlauf.tutorzuege[pivot.zug_nr - FIRST_TURN : stop - FIRST_TURN]
        rule = matrix.signale[pivot.signal]
        delay = next((offset for offset, turn in enumerate(turns) if _passt(turn, rule)), None)
        reason: Zensurgrund | None = None
        if delay is None:
            reason = "folgesignal" if has_next else "verlaufsende"
        if not turns:
            reason = "keine_gelegenheit"
        cases.append(
            LatenzFall(
                zug_nr=pivot.zug_nr,
                beobachtete_zuege=len(turns),
                latenz=delay,
                zensurgrund=reason,
            )
        )
    return tuple(cases)


def _festhaengen(verlauf: Dialogverlauf) -> FesthaengenKennzahl:
    """Count unchanged tutor responses in observed stretches of persistent stocken."""
    confirmed_firsts = {
        current.zug_nr
        for current, following in pairwise(verlauf.wendepunkte)
        if current.signal is LernendenSignal.NICHTVERSTEHEN_1
        and following.wiederholung == FIRST_REPETITION
        and current.huerde_id == following.huerde_id
        and following.zug_nr == current.zug_nr + 1
    }
    longest = total = current = 0
    previous_nr = 0
    previous_signature = None
    for pivot in verlauf.wendepunkte:
        if pivot.wiederholung is None and pivot.zug_nr not in confirmed_firsts:
            continue
        if pivot.zug_nr > len(verlauf.tutorzuege):
            break
        turn = verlauf.tutorzuege[pivot.zug_nr - FIRST_TURN]
        signature = (pivot.huerde_id, frozenset(turn.modi), turn.primaermodus)
        if pivot.zug_nr == previous_nr + 1 and signature == previous_signature:
            current += 1
        else:
            current = 1
        total += 1
        longest = max(longest, current)
        previous_nr, previous_signature = pivot.zug_nr, signature
    return FesthaengenKennzahl(laengste_folge=longest, faelle=total)


def _anteil(zaehler: int, nenner: int) -> Anteil:
    return Anteil(zaehler=zaehler, nenner=nenner, wert=zaehler / nenner if nenner else None)


def _rueckfall(tutorzuege: tuple[Tutorzug, ...]) -> Rueckfall:
    hits = [turn.zug_nr for turn in tutorzuege if RUECKFALL_MODI.intersection(turn.modi)]
    rate = _anteil(len(hits), len(tutorzuege))
    return Rueckfall(
        zaehler=rate.zaehler,
        nenner=rate.nenner,
        wert=rate.wert,
        erster_zug=hits[0] if hits else None,
    )


def berechne_kennzahlen(matrix: SignalModusMatrix, verlauf: Dialogverlauf) -> Kennzahlen:
    """Compute one episode's metrics from pre-existing labels."""
    cases = _latenzfaelle(verlauf, matrix)
    observed = sum(case.beobachtete_zuege > 0 for case in cases)
    return Kennzahlen(
        nicht_beobachtbar=len(cases) - observed,
        passung=_anteil(sum(case.latenz == 0 for case in cases), observed),
        latenz=Latenz(
            zaehler=sum(case.latenz is not None for case in cases), nenner=observed, faelle=cases
        ),
        festhaengen=_festhaengen(verlauf),
        rueckfall=_rueckfall(verlauf.tutorzuege),
    )


def export_json_schema() -> dict[str, object]:
    models = (
        SignalModusMatrix,
        SyntheticLabels,
        WendepunktUrteil,
        Dialogverlauf,
        Kennzahlen,
    )
    refs, schema = models_json_schema([(model, "validation") for model in models])
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **schema,
        "anyOf": [refs[model, "validation"] for model in models],
    }
