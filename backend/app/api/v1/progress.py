from datetime import timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.security import CurrentProfile, DbSession
from app.models import (
    ConversationSession,
    Exercise,
    ExerciseAttempt,
    Lesson,
    LessonAttempt,
    ReviewItem,
    UserAssessment,
    UserMastery,
)
from app.schemas.api import SKILLS, HistoryItem, ProgressSummary, SkillProgress
from app.services.learning import due_review_count, now_utc, weak_concepts

router = APIRouter(tags=["progress"])


@router.get("/progress", response_model=ProgressSummary)
def progress(profile: CurrentProfile, db: DbSession) -> ProgressSummary:
    uid = profile.id
    completed = (
        db.scalar(
            select(func.count(func.distinct(LessonAttempt.lesson_id))).where(
                LessonAttempt.user_id == uid, LessonAttempt.status == "completed"
            )
        )
        or 0
    )
    total = db.scalar(select(func.count(Lesson.id))) or 0
    answered = (
        db.scalar(select(func.count(ExerciseAttempt.id)).where(ExerciseAttempt.user_id == uid)) or 0
    )
    correct = (
        db.scalar(
            select(func.count(ExerciseAttempt.id)).where(
                ExerciseAttempt.user_id == uid, ExerciseAttempt.is_correct.is_(True)
            )
        )
        or 0
    )
    seconds = (
        db.scalar(
            select(func.coalesce(func.sum(LessonAttempt.active_seconds), 0)).where(
                LessonAttempt.user_id == uid
            )
        )
        or 0
    )
    today_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_today = (
        db.scalar(
            select(func.coalesce(func.sum(LessonAttempt.active_seconds), 0)).where(
                LessonAttempt.user_id == uid, LessonAttempt.completed_at >= today_start
            )
        )
        or 0
    )
    reviews_done = (
        db.scalar(
            select(func.count(ReviewItem.id)).where(
                ReviewItem.user_id == uid, ReviewItem.last_reviewed_at.is_not(None)
            )
        )
        or 0
    )
    weak = weak_concepts(db, uid)
    mistakes = db.execute(
        select(ExerciseAttempt, Exercise)
        .join(Exercise)
        .where(ExerciseAttempt.user_id == uid, ExerciseAttempt.is_correct.is_(False))
        .order_by(ExerciseAttempt.created_at.desc())
        .limit(5)
    ).all()
    return ProgressSummary(
        lessons_completed=completed,
        lessons_total=total,
        exercises_answered=answered,
        accuracy=round(correct / answered, 3) if answered else None,
        learning_minutes=round(seconds / 60),
        minutes_today=round(seconds_today / 60),
        daily_goal_minutes=profile.daily_goal_minutes,
        streak_days=profile.streak_days,
        reviews_due=due_review_count(db, uid),
        reviews_completed=reviews_done,
        current_level=profile.current_level,
        concepts_needing_practice=[
            {"concept_id": w.concept_id, "skill": w.skill, "mastery": w.mastery} for w in weak
        ],
        recent_mistakes=[
            {
                "exercise_id": ex.id,
                "instructions": ex.instructions,
                "answer": a.answer,
                "expected": ex.answer,
                "skill": ex.skill,
                "created_at": a.created_at.isoformat(),
            }
            for a, ex in mistakes
        ],
    )


@router.get("/progress/skills", response_model=list[SkillProgress])
def skills(profile: CurrentProfile, db: DbSession) -> list[SkillProgress]:
    uid = profile.id
    placement = db.scalar(
        select(UserAssessment.result)
        .where(UserAssessment.user_id == uid, UserAssessment.status == "completed")
        .order_by(UserAssessment.completed_at.desc())
    )
    out = []
    for skill in SKILLS:
        n = (
            db.scalar(
                select(func.count(ExerciseAttempt.id)).where(
                    ExerciseAttempt.user_id == uid, ExerciseAttempt.skill == skill
                )
            )
            or 0
        )
        c = (
            db.scalar(
                select(func.count(ExerciseAttempt.id)).where(
                    ExerciseAttempt.user_id == uid,
                    ExerciseAttempt.skill == skill,
                    ExerciseAttempt.is_correct.is_(True),
                )
            )
            or 0
        )
        m = db.scalar(
            select(func.avg(UserMastery.mastery)).where(
                UserMastery.user_id == uid, UserMastery.skill == skill
            )
        )
        p = (placement or {}).get("skills", {}).get(skill, {}).get("score") if placement else None
        out.append(
            SkillProgress(
                skill=skill,
                accuracy=round(c / n, 3) if n else None,
                attempts=n,  # type: ignore[arg-type]
                mastery=round(float(m), 3) if m is not None else None,
                placement_score=p,
            )
        )
    return out


@router.get("/history", response_model=list[HistoryItem])
def history(
    profile: CurrentProfile,
    db: DbSession,
    limit: int = Query(30, ge=1, le=100),
    days: int = Query(30, ge=1, le=365),
) -> list[HistoryItem]:
    since = now_utc() - timedelta(days=days)
    items: list[HistoryItem] = []
    for la, lesson in db.execute(
        select(LessonAttempt, Lesson)
        .join(Lesson)
        .where(
            LessonAttempt.user_id == profile.id,
            LessonAttempt.status == "completed",
            LessonAttempt.completed_at >= since,
        )
        .order_by(LessonAttempt.completed_at.desc())
        .limit(limit)
    ):
        items.append(
            HistoryItem(
                kind="lesson",
                title=lesson.title,
                detail=f"Score {round((la.score or 0) * 100)}%",
                is_correct=(la.score or 0) >= lesson.pass_score,
                created_at=la.completed_at,
            )
        )
    for c in db.scalars(
        select(ConversationSession)
        .where(ConversationSession.user_id == profile.id, ConversationSession.created_at >= since)
        .order_by(ConversationSession.created_at.desc())
        .limit(limit)
    ):
        items.append(
            HistoryItem(
                kind="conversation",
                title=c.topic,
                detail=f"{c.turn_count} turns",
                is_correct=None,
                created_at=c.created_at,
            )
        )
    items.sort(key=lambda h: h.created_at, reverse=True)
    return items[:limit]
