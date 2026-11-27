"""Versionierte Oberflächenmuster für sichtbare Tutorantworten."""

import argparse
import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

RULES_PATH = Path(__file__).with_name("detektoren-v1.json")
SHA256 = re.compile(r"[0-9a-fA-F]{64}")
PatternName = Literal["DOPPELFRAGE", "SERVICE_MENUE", "PAUSCHALLOB_PREFIX", "WIEDERHOLUNG"]
LOCAL_PATTERNS: tuple[PatternName, ...] = ("DOPPELFRAGE", "SERVICE_MENUE", "PAUSCHALLOB_PREFIX")
REPETITION: PatternName = "WIEDERHOLUNG"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Preprocessing(Contract):
    code_block: re.Pattern[str]
    inline_code: re.Pattern[str]
    quoted_example: re.Pattern[str]
    url: re.Pattern[str]
    markdown_emphasis: re.Pattern[str]


class DetectorRule(Contract):
    definition: str = Field(pattern=r"^[^\r\n]*\S[^\r\n]*$")


class QuestionRule(DetectorRule):
    minimum_impulses: PositiveInt
    clauses: re.Pattern[str]
    confirmation: re.Pattern[str]
    trailing_confirmation: re.Pattern[str]
    imperative: re.Pattern[str]
    impulse_separator: re.Pattern[str]
    question_start: re.Pattern[str]
    decision_question_start: re.Pattern[str]
    list_marker: re.Pattern[str]

    @field_validator("clauses")
    @classmethod
    def require_clause_groups(cls, pattern: re.Pattern[str]) -> re.Pattern[str]:
        if pattern.groups != 2:
            raise ValueError("Das Satzmuster benötigt Gruppen für Inhalt und Satzzeichen.")
        return pattern


class ServiceRule(DetectorRule):
    offer: re.Pattern[str]
    numbered_option: re.Pattern[str]
    minimum_options: PositiveInt
    choice_hint: re.Pattern[str]


class PraiseRule(DetectorRule):
    opener: re.Pattern[str]
    direct_reason: re.Pattern[str]


class RepetitionRule(DetectorRule):
    word: re.Pattern[str]
    ngram_size: Literal[3]
    minimum_ngrams: PositiveInt
    jaccard_threshold: float = Field(gt=0, le=1)


class StructureRule(Contract):
    table: re.Pattern[str]
    numeric_example_or_formula: re.Pattern[str]


class Rules(Contract):
    version: Literal[1]
    preprocessing: Preprocessing
    double_question: QuestionRule = Field(alias="DOPPELFRAGE")
    service_menu: ServiceRule = Field(alias="SERVICE_MENUE")
    blanket_praise: PraiseRule = Field(alias="PAUSCHALLOB_PREFIX")
    repetition: RepetitionRule = Field(alias=REPETITION)
    structure: StructureRule


@dataclass(frozen=True, slots=True)
class LoadedRules:
    rules: Rules
    sha256: str


def load_rules(path: Path = RULES_PATH, *, expect_sha256: str | None = None) -> LoadedRules:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expect_sha256 is not None:
        if not SHA256.fullmatch(expect_sha256):
            raise ValueError("Erwartet werden 64 hexadezimale Zeichen für SHA-256.")
        if digest != expect_sha256.lower():
            raise ValueError(f"SHA-256 der Detektorregeln stimmt nicht überein (Ist: {digest}).")
    return LoadedRules(Rules.model_validate_json(raw), digest)


class TurnMetrics(Contract):
    hits: frozenset[PatternName]
    characters: int
    words: int
    questions: int
    impulses: int
    code_block: bool
    table: bool
    numeric_example_or_formula: bool
    own_similarity: float | None


def pattern_label(pattern: PatternName) -> str:
    return f"Treffer des Musters {pattern}"


def _mask(match: re.Match[str]) -> str:
    return " " + "\n" * match[0].count("\n")


def _plain_text(text: str, rules: Preprocessing) -> str:
    for pattern in (rules.inline_code, rules.quoted_example, rules.url):
        text = pattern.sub(_mask, text)
    return rules.markdown_emphasis.sub("", text)


def _count_impulses(text: str, rule: QuestionRule) -> tuple[int, int]:
    questions = 0
    tasks = 0
    unlisted = rule.list_marker.sub("", text)
    for match in rule.clauses.finditer(unlisted):
        clause = rule.trailing_confirmation.sub("", match[1].strip())
        parts = [part.strip() for part in rule.impulse_separator.split(clause)]
        if "?" in match[2] and clause and not rule.confirmation.fullmatch(clause):
            questions += _count_questions(parts, rule)
        tasks += sum(bool(rule.imperative.match(part)) for part in parts)
    return questions, questions + tasks


def _count_questions(parts: list[str], rule: QuestionRule) -> int:
    if any(rule.question_start.match(part) for part in parts[1:]):
        return sum(
            bool(rule.question_start.match(part) or rule.decision_question_start.match(part))
            for part in parts
        )
    return int(not rule.imperative.match(parts[0]))


def _has_menu(text: str, rule: ServiceRule) -> bool:
    if rule.offer.search(text):
        return True
    return len(rule.numbered_option.findall(text)) >= rule.minimum_options and bool(
        rule.choice_hint.search(text)
    )


def _has_praise(text: str, rule: PraiseRule) -> bool:
    return any(
        not rule.direct_reason.match(text[match.end() :]) for match in rule.opener.finditer(text)
    )


def _ngrams(text: str, rule: RepetitionRule) -> set[tuple[str, ...]]:
    words = rule.word.findall(text.casefold())
    return set(zip(*(words[start:] for start in range(rule.ngram_size)), strict=False))


def _similarity(text: str, previous: str | None, rule: RepetitionRule) -> float | None:
    if previous is None:
        return None
    current_grams = _ngrams(text, rule)
    previous_grams = _ngrams(previous, rule)
    if min(len(current_grams), len(previous_grams)) < rule.minimum_ngrams:
        return None
    return len(current_grams & previous_grams) / len(current_grams | previous_grams)


def analyse_turn(text: str, rules: Rules, *, previous_own: str | None = None) -> TurnMetrics:
    """Compare only when the caller has the immediately preceding own tutor turn."""
    visible = text.replace("\r\n", "\n").replace("\r", "\n")
    bare = rules.preprocessing.code_block.sub(_mask, visible)
    plain = _plain_text(bare, rules.preprocessing)
    questions, impulses = _count_impulses(plain, rules.double_question)
    similarity = _similarity(text, previous_own, rules.repetition)
    flags: dict[PatternName, bool] = {
        "DOPPELFRAGE": impulses >= rules.double_question.minimum_impulses,
        "SERVICE_MENUE": _has_menu(plain, rules.service_menu),
        "PAUSCHALLOB_PREFIX": _has_praise(plain, rules.blanket_praise),
        REPETITION: similarity is not None and similarity >= rules.repetition.jaccard_threshold,
    }
    return TurnMetrics(
        hits=frozenset(pattern for pattern, hit in flags.items() if hit),
        characters=len(text),
        words=len(rules.repetition.word.findall(text)),
        questions=questions,
        impulses=impulses,
        code_block=bool(rules.preprocessing.code_block.search(visible)),
        table=bool(rules.structure.table.search(bare)),
        numeric_example_or_formula=bool(rules.structure.numeric_example_or_formula.search(bare)),
        own_similarity=similarity,
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Detektorregeln prüfen und SHA-256 ausgeben.")
    parser.add_argument("--rules", type=Path, default=RULES_PATH)
    parser.add_argument("--expect-sha256")
    args = parser.parse_args(argv)
    try:
        print(load_rules(args.rules, expect_sha256=args.expect_sha256).sha256)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
