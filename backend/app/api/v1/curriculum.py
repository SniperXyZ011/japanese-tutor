import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentProfile, DbSession
from app.models import (
    CurriculumUnit,
    Exercise,
    ExerciseAttempt,
    GrammarConcept,
    Lesson,
    LessonAttempt,
    Vocabulary,
)
from app.schemas.api import (
    AttemptIn,
    AttemptOut,
    ExerciseOut,
    GrammarOut,
    LessonCompleteIn,
    LessonCompleteOut,
    LessonDetail,
    LessonStartOut,
    UnitOut,
    VocabularyOut,
)
from app.services.ai.service import AI
from app.services.assessment import LEVEL_UNITS
from app.services.evaluation import ExerciseSpec, evaluate
from app.services.learning import (
    apply_attempt,
    lesson_score,
    lesson_statuses,
    now_utc,
    recommend,
    summarize,
    touch_streak,
    unit_position,
)

router = APIRouter(tags=["curriculum"])


def _start_pos(db, profile) -> int:
    return unit_position(db, profile.start_unit_id or LEVEL_UNITS.get(profile.current_level or ""))


@router.get("/curriculum", response_model=list[UnitOut])
def curriculum(profile: CurrentProfile, db: DbSession) -> list[UnitOut]:
    statuses = lesson_statuses(db, profile.id)
    units = list(db.scalars(select(CurriculumUnit).order_by(CurriculumUnit.position)))
    positions = {u.id: u.position for u in units}
    start = _start_pos(db, profile)
    return [
        UnitOut(
            id=u.id,
            position=u.position,
            title=u.title,
            description=u.description,
            level=u.level,
            lessons=[summarize(le, statuses, start, positions) for le in u.lessons],
        )
        for u in units
    ]


def _active_attempt(db, user_id: uuid.UUID, lesson_id: str) -> LessonAttempt | None:
    return db.scalar(
        select(LessonAttempt)
        .where(
            LessonAttempt.user_id == user_id,
            LessonAttempt.lesson_id == lesson_id,
            LessonAttempt.status == "in_progress",
        )
        .order_by(LessonAttempt.started_at.desc())
    )


@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
def lesson_detail(lesson_id: str, profile: CurrentProfile, db: DbSession) -> LessonDetail:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise NotFoundError("Lesson")
    vocab = list(db.scalars(select(Vocabulary).where(Vocabulary.id.in_(lesson.vocabulary_ids))))
    vocab.sort(key=lambda v: lesson.vocabulary_ids.index(v.id))
    grammar = list(
        db.scalars(select(GrammarConcept).where(GrammarConcept.id.in_(lesson.grammar_ids)))
    )
    attempt = _active_attempt(db, profile.id, lesson_id)
    status = lesson_statuses(db, profile.id).get(lesson_id, ("not_started", None))[0]
    return LessonDetail(
        id=lesson.id,
        unit_id=lesson.unit_id,
        title=lesson.title,
        summary=lesson.summary,
        objectives=lesson.objectives,
        prerequisites=lesson.prerequisites,
        difficulty=lesson.difficulty,
        estimated_minutes=lesson.estimated_minutes,
        pass_score=lesson.pass_score,
        vocabulary=[VocabularyOut.model_validate(v) for v in vocab],
        grammar=[GrammarOut.model_validate(g) for g in grammar],
        exercises=[ExerciseOut.model_validate(e) for e in lesson.exercises],
        status=status,
        attempt_id=attempt.id if attempt else None,
        current_step=attempt.current_step if attempt else 0,
    )


@router.post("/lessons/{lesson_id}/start", response_model=LessonStartOut)
def start_lesson(lesson_id: str, profile: CurrentProfile, db: DbSession) -> LessonStartOut:
    if db.get(Lesson, lesson_id) is None:
        raise NotFoundError("Lesson")
    attempt = _active_attempt(db, profile.id, lesson_id)
    if attempt is None:
        attempt = LessonAttempt(
            user_id=profile.id,
            lesson_id=lesson_id,
            status="in_progress",
            current_step=0,
            active_seconds=0,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
    return LessonStartOut(
        attempt_id=attempt.id, current_step=attempt.current_step, status=attempt.status
    )


@router.post("/lessons/{lesson_id}/progress", response_model=LessonStartOut)
def save_progress(
    lesson_id: str, attempt_id: uuid.UUID, step: int, profile: CurrentProfile, db: DbSession
) -> LessonStartOut:
    attempt = db.get(LessonAttempt, attempt_id)
    if attempt is None or attempt.user_id != profile.id or attempt.lesson_id != lesson_id:
        raise NotFoundError("Lesson attempt")
    attempt.current_step = max(attempt.current_step, max(0, step))
    db.commit()
    return LessonStartOut(
        attempt_id=attempt.id, current_step=attempt.current_step, status=attempt.status
    )


@router.post("/lessons/{lesson_id}/complete", response_model=LessonCompleteOut)
def complete_lesson(
    lesson_id: str, body: LessonCompleteIn, profile: CurrentProfile, db: DbSession
) -> LessonCompleteOut:
    attempt = db.get(LessonAttempt, body.attempt_id)
    lesson = db.get(Lesson, lesson_id)
    if (
        attempt is None
        or lesson is None
        or attempt.user_id != profile.id
        or attempt.lesson_id != lesson_id
    ):
        raise NotFoundError("Lesson attempt")
    if attempt.status != "completed":
        score, answered = lesson_score(db, attempt)
        attempt.score = score
        attempt.status = "completed"
        attempt.completed_at = now_utc()
        attempt.current_step = len(lesson.exercises)
        attempt.active_seconds = body.active_seconds
        touch_streak(profile)
        db.commit()
    score, answered = lesson_score(db, attempt)
    return LessonCompleteOut(
        attempt_id=attempt.id,
        score=attempt.score or score,
        passed=(attempt.score or 0) >= lesson.pass_score,
        exercises_answered=answered,
        next=recommend(db, profile),
    )


@router.post("/exercises/{exercise_id}/attempt", response_model=AttemptOut)
async def attempt_exercise(
    exercise_id: str, body: AttemptIn, profile: CurrentProfile, db: DbSession, ai: AI
) -> AttemptOut:
    exercise = db.get(Exercise, exercise_id)
    if exercise is None:
        raise NotFoundError("Exercise")
    if exercise.type == "presentation":
        raise AppError(400, "not_gradable", "Presentation steps are not graded.")
    lesson_attempt = None
    if body.lesson_attempt_id:
        lesson_attempt = db.get(LessonAttempt, body.lesson_attempt_id)
        if (
            lesson_attempt is None
            or lesson_attempt.user_id != profile.id
            or lesson_attempt.lesson_id != exercise.lesson_id
        ):
            raise NotFoundError("Lesson attempt")
    result = await evaluate(
        ExerciseSpec.from_model(exercise),
        body.answer,
        input_mode=body.input_mode,
        user_id=profile.id,
        ai=ai,
    )
    row = ExerciseAttempt(
        user_id=profile.id,
        exercise_id=exercise.id,
        lesson_attempt_id=lesson_attempt.id if lesson_attempt else None,
        skill=exercise.skill,
        input_mode=body.input_mode,
        answer=body.answer,
        is_correct=result.is_correct,
        score=result.score,
        used_hint=body.used_hint,
        evaluator=result.evaluator,
        confidence=result.confidence,
        feedback=result.model_dump(),
    )
    db.add(row)
    updates = apply_attempt(db, profile, exercise, result, body.used_hint)
    if lesson_attempt is not None:
        lesson_attempt.current_step = max(lesson_attempt.current_step, exercise.position)
    touch_streak(profile)
    db.commit()
    return AttemptOut(
        attempt_id=row.id,
        evaluation=result,
        mastery_updates=updates,
        current_step=lesson_attempt.current_step if lesson_attempt else None,
    )
