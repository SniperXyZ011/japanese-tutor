"""Answer evaluation: deterministic checks first, AI rubric for open-ended answers."""

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.errors import AppError
from app.schemas.evaluation import EvaluationResult
from app.services.japanese import (
    contains_japanese,
    normalize_english,
    normalize_japanese,
    normalize_romaji,
    similarity,
)

if TYPE_CHECKING:
    from app.models import Exercise
    from app.services.ai.service import AIService

logger = logging.getLogger("app.evaluation")

CHOICE_TYPES = {"multiple_choice", "listening_choice"}
JAPANESE_TYPES = {"en_to_ja", "typed_japanese", "sentence_completion"}
OPEN_ENDED_TYPES = {"en_to_ja", "ja_to_en", "speaking", "free_response"}
NON_GRADED_TYPES = {"presentation"}

TRANSCRIPT_NOTE = (
    "Checked against a speech-recognition transcript. This reflects what was recognised, "
    "not a pronunciation score."
)


@dataclass
class ExerciseSpec:
    type: str
    answer: str | None
    accepted_answers: list[str] = field(default_factory=list)
    choices: list[str] = field(default_factory=list)
    explanation: str = ""
    instructions: str = ""
    prompt_en: str | None = None
    prompt_ja: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_model(cls, ex: "Exercise") -> "ExerciseSpec":
        return cls(
            type=ex.type,
            answer=ex.answer,
            accepted_answers=list(ex.accepted_answers or []),
            choices=list(ex.choices or []),
            explanation=ex.explanation or "",
            instructions=ex.instructions,
            prompt_en=ex.prompt_en,
            prompt_ja=ex.prompt_ja,
            meta=dict(ex.meta or {}),
        )

    @property
    def expected(self) -> list[str]:
        items = [self.answer] if self.answer else []
        return items + [a for a in self.accepted_answers if a and a not in items]


def _result(
    spec: ExerciseSpec,
    *,
    correct: bool,
    score: float,
    verdict: str,
    feedback: str,
    confidence: float = 1.0,
    evaluator: str = "deterministic",
    accepted_alternative: bool = False,
    note: str | None = None,
) -> EvaluationResult:
    return EvaluationResult(
        is_correct=correct,
        score=round(max(0.0, min(1.0, score)), 3),
        verdict=verdict,  # type: ignore[arg-type]
        feedback=feedback,
        corrected_answer=None if correct and not accepted_alternative else spec.answer,
        expected_answers=spec.expected,
        explanation=spec.explanation or None,
        accepted_alternative=accepted_alternative,
        confidence=confidence,
        evaluator=evaluator,  # type: ignore[arg-type]
        transcript_note=note,
    )


def _best_japanese_match(
    answer: str, expected: list[str], kana_insensitive: bool = True
) -> tuple[float, int]:
    norm = normalize_japanese(answer, kana_insensitive)
    best, idx = 0.0, -1
    for i, e in enumerate(expected):
        s = similarity(norm, normalize_japanese(e, kana_insensitive))
        if s > best:
            best, idx = s, i
    return best, idx


def evaluate_deterministic(
    spec: ExerciseSpec, answer: str, input_mode: str = "typed"
) -> EvaluationResult | None:
    """Return a result when the answer can be judged without AI, otherwise None."""
    answer = (answer or "").strip()
    expected = spec.expected

    if spec.type in NON_GRADED_TYPES:
        return _result(spec, correct=True, score=1.0, verdict="correct", feedback="Got it!")

    if not answer:
        return _result(
            spec, correct=False, score=0.0, verdict="incorrect", feedback="No answer was given."
        )

    if spec.type in CHOICE_TYPES:
        ok = normalize_japanese(answer) in {normalize_japanese(e) for e in expected}
        return _result(
            spec,
            correct=ok,
            score=1.0 if ok else 0.0,
            verdict="correct" if ok else "incorrect",
            feedback="Correct!" if ok else f"Not quite. The answer is {spec.answer}.",
        )

    if spec.type == "sentence_ordering":
        ok = normalize_japanese(answer) in {normalize_japanese(e) for e in expected}
        return _result(
            spec,
            correct=ok,
            score=1.0 if ok else 0.0,
            verdict="correct" if ok else "incorrect",
            feedback="Correct order!" if ok else "The word order isn't right yet.",
        )

    if spec.type == "ja_to_en":
        norm = normalize_english(answer)
        targets = [normalize_english(e) for e in expected]
        if norm in targets:
            return _result(
                spec,
                correct=True,
                score=1.0,
                verdict="correct",
                feedback="Correct!",
                accepted_alternative=norm != targets[0],
            )
        best = max((similarity(norm, t) for t in targets), default=0.0)
        if best >= 0.9:
            return _result(
                spec,
                correct=True,
                score=0.95,
                verdict="correct",
                feedback="Correct (minor spelling differences).",
                confidence=0.85,
            )
        return None

    required = spec.meta.get("required_substrings")
    if required and spec.type in {"speaking", "typed_japanese", "free_response"}:
        norm = normalize_japanese(answer)
        ok = contains_japanese(answer) and all(normalize_japanese(r) in norm for r in required)
        return _result(
            spec,
            correct=ok,
            score=1.0 if ok else 0.3,
            verdict="correct" if ok else "incorrect",
            feedback="Good!" if ok else f"Try a full sentence using: {', '.join(required)}",
            confidence=0.6,
            note=TRANSCRIPT_NOTE if spec.type == "speaking" or input_mode == "speech" else None,
        )

    if spec.type in JAPANESE_TYPES or spec.type == "speaking":
        is_speech = spec.type == "speaking" or input_mode == "speech"
        note = TRANSCRIPT_NOTE if is_speech else None
        if not contains_japanese(answer):
            romaji = spec.meta.get("romaji_answers") or []
            if romaji and normalize_romaji(answer) in {normalize_romaji(r) for r in romaji}:
                return _result(
                    spec,
                    correct=True,
                    score=0.9,
                    verdict="correct",
                    feedback="Correct! Next time, try typing it in kana.",
                )
            if not is_speech:
                return _result(
                    spec,
                    correct=False,
                    score=0.0,
                    verdict="incorrect",
                    feedback="Please answer in Japanese (hiragana, katakana or kanji). "
                    "Most keyboards have a Japanese IME; romaji input converts as you type.",
                )
        best, idx = _best_japanese_match(
            answer, expected, kana_insensitive=not spec.meta.get("kana_strict")
        )
        exact_threshold = 0.85 if is_speech else 1.0
        if best >= exact_threshold:
            return _result(
                spec,
                correct=True,
                score=1.0 if best == 1.0 else 0.9,
                verdict="correct",
                feedback="Correct!" if not is_speech else "Matches the expected sentence.",
                confidence=0.75 if is_speech else 1.0,
                accepted_alternative=idx > 0,
                note=note,
            )
        if spec.type == "sentence_completion" or (
            spec.type == "typed_japanese" and not spec.meta.get("open_ended")
        ):
            close = best >= 0.75
            return _result(
                spec,
                correct=False,
                score=0.6 if close else 0.0,
                verdict="almost" if close else "incorrect",
                feedback=(
                    f"Very close — compare with: {spec.answer}"
                    if close
                    else f"Not quite. The answer is {spec.answer}."
                ),
                note=note,
            )
        return None

    return None


async def evaluate(
    spec: ExerciseSpec,
    answer: str,
    *,
    input_mode: str,
    user_id: uuid.UUID,
    ai: "AIService | None",
    target: list[str] | None = None,
) -> EvaluationResult:
    result = evaluate_deterministic(spec, answer, input_mode)
    if result is not None:
        return result

    is_speech = spec.type == "speaking" or input_mode == "speech"
    note = TRANSCRIPT_NOTE if is_speech else None
    best, _ = _best_japanese_match(answer, spec.expected) if spec.type != "ja_to_en" else (0, 0)

    if ai is not None and ai.available:
        try:
            ev, res = await ai.evaluate_open_answer(
                user_id,
                instructions=spec.instructions,
                prompt=spec.prompt_en if spec.type != "ja_to_en" else spec.prompt_ja,
                expected=spec.expected,
                answer=answer,
                input_mode=input_mode,
                target=target,
            )
        except AppError as exc:
            logger.warning("evaluation_ai_failed code=%s", exc.code)
        else:
            confidence = ev.confidence * (0.8 if is_speech else 1.0)
            verdict = "correct" if ev.is_correct else ("almost" if ev.score >= 0.6 else "incorrect")
            return EvaluationResult(
                is_correct=ev.is_correct,
                score=ev.score,
                verdict=verdict,
                feedback=ev.explanation or ("Correct!" if ev.is_correct else "Not quite."),
                corrected_answer=ev.corrected_answer,
                expected_answers=spec.expected,
                explanation=spec.explanation or None,
                accepted_alternative=ev.accepted_alternative,
                meaning=ev.meaning,
                grammar=ev.grammar,
                naturalness=ev.naturalness,
                confidence=round(confidence, 3),
                evaluator="mock_ai" if res.is_mock else "ai",
                transcript_note=note,
                follow_up=ev.follow_up,
            )

    close = best >= 0.7
    return _result(
        spec,
        correct=False,
        score=0.5 if close else 0.3,
        verdict="unverified",
        feedback=(
            "This answer differs from the reference and couldn't be checked automatically. "
            "Compare it with the model answer below."
        ),
        confidence=0.3,
        evaluator="fallback",
        note=note,
    )
