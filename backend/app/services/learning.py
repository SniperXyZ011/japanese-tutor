"""Mastery updates, review scheduling, lesson status and recommendations."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CurriculumUnit,
    Exercise,
    ExerciseAttempt,
    Lesson,
    LessonAttempt,
    Profile,
    ReviewItem,
    UserMastery,
)
from app.schemas.api import LessonSummary, Recommendation
from app.schemas.evaluation import EvaluationResult
from app.services.assessment import LEVEL_UNITS
from app.services.srs import grade_from_result, schedule_next, update_mastery


def concept_type(concept_id: str) -> str:
    return "grammar" if concept_id.startswith("g-") else "vocabulary"


def now_utc() -> datetime:
    return datetime.now(UTC)


def touch_streak(profile: Profile, today: date | None = None) -> None:
    today = today or now_utc().date()
    if profile.last_active_date == today:
        return
    if profile.last_active_date == today - timedelta(days=1):
        profile.streak_days += 1
    else:
        profile.streak_days = 1
    profile.last_active_date = today


def apply_attempt(
    db: Session,
    profile: Profile,
    exercise: Exercise,
    evaluation: EvaluationResult,
    used_hint: bool,
) -> list[dict[str, Any]]:
    """Update mastery and review scheduling for each concept the exercise practises."""
    if exercise.type == "presentation":
        return []
    now = now_utc()
    updates: list[dict[str, Any]] = []
    for cid in exercise.concept_ids:
        m = db.scalar(
            select(UserMastery).where(
                UserMastery.user_id == profile.id,
                UserMastery.concept_id == cid,
                UserMastery.skill == exercise.skill,
            )
        )
        if m is None:
            m = UserMastery(
                user_id=profile.id,
                concept_id=cid,
                concept_type=concept_type(cid),
                skill=exercise.skill,
                attempts=0,
                independent_successes=0,
                hint_uses=0,
                recent_failures=0,
                mastery=0.0,
                confidence=0.0,
            )
            db.add(m)
        res = update_mastery(
            mastery=m.mastery,
            attempts=m.attempts,
            recent_failures=m.recent_failures,
            is_correct=evaluation.is_correct,
            used_hint=used_hint,
            evaluation_confidence=evaluation.confidence,
        )
        m.attempts += 1
        m.hint_uses += 1 if used_hint else 0
        m.independent_successes += 1 if evaluation.is_correct and not used_hint else 0
        m.mastery, m.confidence, m.recent_failures = (
            res.mastery,
            res.confidence,
            res.recent_failures,
        )
        m.last_reviewed_at = now

        r = db.scalar(
            select(ReviewItem).where(ReviewItem.user_id == profile.id, ReviewItem.concept_id == cid)
        )
        grade = grade_from_result(evaluation.is_correct, evaluation.score, used_hint)
        if evaluation.confidence < 0.5 and grade == "again":
            grade = "hard"
        if r is None:
            sched = schedule_next(
                grade=grade,
                now=now,
                state="new",
                interval_days=0,
                ease=2.5,
                repetitions=0,
                lapses=0,
            )
            r = ReviewItem(
                user_id=profile.id,
                concept_id=cid,
                concept_type=concept_type(cid),
                due_at=sched.due_at,
                from_mistake=not evaluation.is_correct,
            )
            db.add(r)
        elif r.due_at <= now or not evaluation.is_correct:
            sched = schedule_next(
                grade=grade,
                now=now,
                state=r.state,
                interval_days=r.interval_days,
                ease=r.ease,
                repetitions=r.repetitions,
                lapses=r.lapses,
            )
        else:
            sched = None
        if sched is not None:
            r.state, r.interval_days, r.ease = sched.state, sched.interval_days, sched.ease
            r.repetitions, r.lapses, r.due_at = sched.repetitions, sched.lapses, sched.due_at
            r.last_grade, r.last_reviewed_at = grade, now
            if not evaluation.is_correct:
                r.from_mistake = True
        updates.append(
            {
                "concept_id": cid,
                "skill": exercise.skill,
                "mastery": m.mastery,
                "confidence": m.confidence,
            }
        )
    return updates


def lesson_statuses(db: Session, user_id: uuid.UUID) -> dict[str, tuple[str, float | None]]:
    rows = db.execute(
        select(LessonAttempt.lesson_id, LessonAttempt.status, func.max(LessonAttempt.score))
        .where(LessonAttempt.user_id == user_id)
        .group_by(LessonAttempt.lesson_id, LessonAttempt.status)
    ).all()
    out: dict[str, tuple[str, float | None]] = {}
    for lesson_id, status, score in rows:
        prev = out.get(lesson_id)
        if status == "completed":
            best = max(score or 0, (prev[1] or 0) if prev else 0)
            out[lesson_id] = ("completed", best)
        elif prev is None:
            out[lesson_id] = ("in_progress", None)
    return out


def ordered_lessons(db: Session) -> list[Lesson]:
    return list(
        db.scalars(
            select(Lesson).join(CurriculumUnit).order_by(CurriculumUnit.position, Lesson.position)
        )
    )


def unit_position(db: Session, unit_id: str | None) -> int:
    if not unit_id:
        return 0
    return db.scalar(select(CurriculumUnit.position).where(CurriculumUnit.id == unit_id)) or 0


def summarize(
    lesson: Lesson,
    statuses: dict[str, tuple[str, float | None]],
    start_pos: int,
    unit_pos: dict[str, int],
) -> LessonSummary:
    status, best = statuses.get(lesson.id, ("not_started", None))
    prereqs_done = all(statuses.get(p, ("",))[0] == "completed" for p in lesson.prerequisites)
    placed_past = unit_pos.get(lesson.unit_id, 0) <= start_pos
    return LessonSummary(
        id=lesson.id,
        unit_id=lesson.unit_id,
        position=lesson.position,
        title=lesson.title,
        summary=lesson.summary,
        difficulty=lesson.difficulty,
        estimated_minutes=lesson.estimated_minutes,
        status=status,
        best_score=best,  # type: ignore[arg-type]
        locked=not (prereqs_done or placed_past or status != "not_started"),
    )


def due_review_count(db: Session, user_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count(ReviewItem.id)).where(
                ReviewItem.user_id == user_id, ReviewItem.due_at <= now_utc()
            )
        )
        or 0
    )


def weak_concepts(db: Session, user_id: uuid.UUID, limit: int = 5) -> list[UserMastery]:
    return list(
        db.scalars(
            select(UserMastery)
            .where(
                UserMastery.user_id == user_id, UserMastery.attempts >= 2, UserMastery.mastery < 0.4
            )
            .order_by(UserMastery.mastery)
            .limit(limit)
        )
    )


def recommend(db: Session, profile: Profile) -> Recommendation:
    if not profile.onboarding_completed:
        return Recommendation(kind="onboarding", reason="Tell us about your Japanese so far.")
    if not profile.current_level:
        return Recommendation(
            kind="assessment", reason="Take a short placement check to personalise your path."
        )
    due = due_review_count(db, profile.id)
    weak = [w.concept_id for w in weak_concepts(db, profile.id)]
    statuses = lesson_statuses(db, profile.id)
    units = {u.id: u.position for u in db.scalars(select(CurriculumUnit))}
    start_pos = unit_position(db, profile.start_unit_id or LEVEL_UNITS.get(profile.current_level))
    lessons = ordered_lessons(db)

    if due >= 10:
        return Recommendation(
            kind="review",
            reason=f"You have {due} reviews due. Clearing them first keeps them fresh.",
            due_reviews=due,
            weak_concepts=weak,
        )

    def first(pred) -> Lesson | None:
        return next((lesson for lesson in lessons if pred(lesson)), None)

    in_progress = first(
        lambda le: statuses.get(le.id, ("",))[0] == "in_progress" and units[le.unit_id] >= start_pos
    )
    candidate = in_progress or first(
        lambda le: (
            units[le.unit_id] >= start_pos
            and statuses.get(le.id, ("not_started",))[0] != "completed"
            and all(
                statuses.get(p, ("",))[0] == "completed"
                or units[db.get(Lesson, p).unit_id] < start_pos
                for p in le.prerequisites
            )
        )
    )
    if weak and candidate is not None:
        weak_lesson = first(
            lambda le: (
                any(w in le.vocabulary_ids or w in le.grammar_ids for w in weak)
                and statuses.get(le.id, ("",))[0] == "completed"
            )
        )
        if weak_lesson is not None and len(weak) >= 3:
            candidate, reason = (
                weak_lesson,
                "Revisit this lesson to strengthen concepts you've been missing.",
            )
        else:
            reason = "Continue your path." if in_progress is None else "Pick up where you left off."
    elif candidate is not None:
        reason = (
            "Pick up where you left off."
            if in_progress
            else "Next lesson on your personalised path."
        )
    else:
        if due:
            return Recommendation(
                kind="review",
                reason="You've finished the available lessons — review to keep them fresh.",
                due_reviews=due,
                weak_concepts=weak,
            )
        return Recommendation(
            kind="complete",
            reason="You've completed all available lessons. Practise speaking with the tutor!",
            due_reviews=due,
            weak_concepts=weak,
        )
    return Recommendation(
        kind="lesson",
        reason=reason,
        lesson=summarize(candidate, statuses, start_pos, units),
        due_reviews=due,
        weak_concepts=weak,
    )


def lesson_score(db: Session, attempt: LessonAttempt) -> tuple[float, int]:
    """Score = mean of the latest attempt per graded exercise in this lesson attempt."""
    rows = list(
        db.scalars(
            select(ExerciseAttempt)
            .where(ExerciseAttempt.lesson_attempt_id == attempt.id)
            .order_by(ExerciseAttempt.created_at)
        )
    )
    latest: dict[str, float] = {}
    for r in rows:
        latest[r.exercise_id] = r.score
    graded = (
        db.scalar(
            select(func.count(Exercise.id)).where(
                Exercise.lesson_id == attempt.lesson_id, Exercise.type != "presentation"
            )
        )
        or 1
    )
    return round(sum(latest.values()) / graded, 3), len(latest)
