"""Interval-based spaced repetition (SM-2 inspired) and rules-based mastery updates.

Kept deliberately transparent so learners and tests can reason about it.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

Grade = Literal["again", "hard", "good", "easy"]

MIN_EASE = 1.3
MAX_EASE = 3.0
RELEARN_DELAY = timedelta(minutes=10)


@dataclass
class Schedule:
    state: str
    interval_days: float
    ease: float
    repetitions: int
    lapses: int
    due_at: datetime


def schedule_next(
    *,
    grade: Grade,
    now: datetime,
    state: str,
    interval_days: float,
    ease: float,
    repetitions: int,
    lapses: int,
) -> Schedule:
    if grade == "again":
        return Schedule(
            state="relearning" if repetitions > 0 else "learning",
            interval_days=0.0,
            ease=max(MIN_EASE, ease - 0.2),
            repetitions=0,
            lapses=lapses + (1 if repetitions > 0 else 0),
            due_at=now + RELEARN_DELAY,
        )

    if repetitions == 0:
        interval = {"hard": 0.5, "good": 1.0, "easy": 3.0}[grade]
    elif repetitions == 1:
        interval = {"hard": 1.5, "good": 3.0, "easy": 5.0}[grade]
    else:
        factor = {"hard": 1.2, "good": ease, "easy": ease * 1.3}[grade]
        interval = max(interval_days * factor, interval_days + 1)

    ease_delta = {"hard": -0.15, "good": 0.0, "easy": 0.15}[grade]
    new_ease = min(MAX_EASE, max(MIN_EASE, ease + ease_delta))
    return Schedule(
        state="review" if repetitions + 1 >= 2 else "learning",
        interval_days=round(interval, 2),
        ease=round(new_ease, 2),
        repetitions=repetitions + 1,
        lapses=lapses,
        due_at=now + timedelta(days=interval),
    )


def grade_from_result(is_correct: bool, score: float, used_hint: bool) -> Grade:
    if not is_correct:
        return "hard" if score >= 0.6 else "again"
    if used_hint:
        return "hard"
    return "good"


@dataclass
class MasteryUpdate:
    mastery: float
    confidence: float
    recent_failures: int


def update_mastery(
    *,
    mastery: float,
    attempts: int,
    recent_failures: int,
    is_correct: bool,
    used_hint: bool,
    evaluation_confidence: float,
) -> MasteryUpdate:
    """Move mastery toward 1 on independent success, gently down on failure.

    Uncertain evaluations (low confidence) produce proportionally smaller changes, and a
    single mistake never wipes out prior evidence.
    """
    weight = max(0.0, min(1.0, evaluation_confidence))
    if is_correct and not used_hint:
        new = mastery + (1.0 - mastery) * 0.3 * weight
        failures = 0
    elif is_correct and used_hint:
        new = mastery + (1.0 - mastery) * 0.1 * weight
        failures = 0
    else:
        failures = recent_failures + 1
        penalty = 0.12 if failures == 1 else 0.25
        new = mastery - mastery * penalty * weight
    total = attempts + 1
    confidence = min(0.95, 1.0 - 1.0 / (1.0 + 0.35 * total))
    return MasteryUpdate(
        mastery=round(max(0.0, min(1.0, new)), 4),
        confidence=round(confidence, 4),
        recent_failures=failures,
    )
