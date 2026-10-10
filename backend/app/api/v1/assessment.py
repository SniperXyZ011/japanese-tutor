import uuid

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentProfile, DbSession
from app.models import AssessmentResponse, UserAssessment
from app.schemas.api import (
    AssessmentAnswerIn,
    AssessmentItemOut,
    AssessmentProgress,
    AssessmentStartIn,
    PlacementResult,
    SkillEstimate,
)
from app.services import assessment as engine
from app.services.ai.service import AI
from app.services.evaluation import ExerciseSpec, evaluate
from app.services.learning import now_utc

router = APIRouter(prefix="/assessment", tags=["assessment"])


def _item_out(item_id: str | None) -> AssessmentItemOut | None:
    if not item_id:
        return None
    i = engine.item_bank()[item_id]
    return AssessmentItemOut(
        id=i["id"],
        skill=i["skill"],
        difficulty=i["difficulty"],
        type=i["type"],
        instructions=i["instructions"],
        prompt_ja=i.get("prompt_ja"),
        prompt_en=i.get("prompt_en"),
        audio_text=i.get("audio_text"),
        choices=i.get("choices", []),
    )


def _progress(a: UserAssessment) -> AssessmentProgress:
    answered = sum(len(s["answered"]) for s in a.state["skills"].values())
    return AssessmentProgress(
        assessment_id=a.id,
        status=a.status,
        answered=answered,
        estimated_total=answered
        + engine.estimated_remaining(a.state)
        + (1 if a.state["current_item_id"] else 0),
        next_item=_item_out(a.state["current_item_id"]) if a.status == "in_progress" else None,
    )


def _owned(db, assessment_id: uuid.UUID, user_id: uuid.UUID) -> UserAssessment:
    a = db.get(UserAssessment, assessment_id)
    if a is None or a.user_id != user_id:
        raise NotFoundError("Assessment")
    return a


@router.post("/start", response_model=AssessmentProgress)
def start(body: AssessmentStartIn, profile: CurrentProfile, db: DbSession) -> AssessmentProgress:
    existing = db.scalar(
        select(UserAssessment)
        .where(UserAssessment.user_id == profile.id, UserAssessment.status == "in_progress")
        .order_by(UserAssessment.created_at.desc())
    )
    if existing is not None:
        return _progress(existing)
    sa = (
        body.self_assessment.model_dump()
        if body.self_assessment
        else dict(profile.onboarding or {})
    )
    a = UserAssessment(
        user_id=profile.id, status="in_progress", self_assessment=sa, state=engine.initial_state(sa)
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _progress(a)


@router.get("/{assessment_id}", response_model=AssessmentProgress)
def get_progress(
    assessment_id: uuid.UUID, profile: CurrentProfile, db: DbSession
) -> AssessmentProgress:
    return _progress(_owned(db, assessment_id, profile.id))


@router.post("/{assessment_id}/answer", response_model=AssessmentProgress)
async def answer(
    assessment_id: uuid.UUID,
    body: AssessmentAnswerIn,
    profile: CurrentProfile,
    db: DbSession,
    ai: AI,
) -> AssessmentProgress:
    a = _owned(db, assessment_id, profile.id)
    if a.status != "in_progress":
        raise AppError(409, "assessment_finished", "This assessment is already complete.")
    if body.item_id != a.state["current_item_id"]:
        raise AppError(409, "unexpected_item", "That question is not the current one.")
    item = engine.item_bank()[body.item_id]
    if body.skipped or not body.answer.strip():
        correct, score, evaluator = False, 0.0, "skipped"
    else:
        spec = ExerciseSpec(
            type=item["type"],
            answer=item["answer"],
            accepted_answers=item.get("accepted_answers", []),
            choices=item.get("choices", []),
            instructions=item["instructions"],
            prompt_en=item.get("prompt_en"),
            prompt_ja=item.get("prompt_ja"),
            meta=item.get("meta", {}),
        )
        try:
            res = await evaluate(
                spec, body.answer, input_mode=body.input_mode, user_id=profile.id, ai=ai
            )
            correct, score, evaluator = res.is_correct, res.score, res.evaluator
        except AppError:
            correct, score, evaluator = False, 0.0, "fallback"
    db.add(
        AssessmentResponse(
            assessment_id=a.id,
            item_id=item["id"],
            skill=item["skill"],
            difficulty=item["difficulty"],
            answer=body.answer,
            input_mode=body.input_mode,
            score=score,
            is_correct=correct,
            evaluator=evaluator,
        )
    )
    a.state = engine.record_answer(a.state, item["id"], correct)
    flag_modified(a, "state")
    if a.state["current_item_id"] is None:
        _finish(a, profile)
    db.commit()
    db.refresh(a)
    return _progress(a)


def _finish(a: UserAssessment, profile) -> None:
    result = engine.placement(a.state)
    a.result = result
    a.status = "completed"
    a.completed_at = now_utc()
    a.recommended_level = result["level"]
    a.recommended_unit_id = result["unit_id"]
    profile.current_level = result["level"]
    profile.start_unit_id = result["unit_id"]


@router.post("/{assessment_id}/finish", response_model=PlacementResult)
def finish_early(
    assessment_id: uuid.UUID, profile: CurrentProfile, db: DbSession
) -> PlacementResult:
    a = _owned(db, assessment_id, profile.id)
    if a.status == "in_progress":
        _finish(a, profile)
        db.commit()
    return _result(a)


@router.get("/{assessment_id}/result", response_model=PlacementResult)
def result(assessment_id: uuid.UUID, profile: CurrentProfile, db: DbSession) -> PlacementResult:
    a = _owned(db, assessment_id, profile.id)
    if a.status != "completed" or not a.result:
        raise AppError(409, "assessment_in_progress", "Finish the assessment to see your results.")
    return _result(a)


def _result(a: UserAssessment) -> PlacementResult:
    r = a.result or {}
    return PlacementResult(
        assessment_id=a.id,
        recommended_level=r["level"],
        recommended_level_label=r["label"],
        recommended_unit_id=r["unit_id"],
        skills=[SkillEstimate(skill=s, **v) for s, v in r["skills"].items()],
        strengths=r["strengths"],
        weak_areas=r["weak_areas"],
        explanation=r["explanation"],
        completed_at=a.completed_at,
    )


@router.get("", response_model=PlacementResult | None)
def latest(profile: CurrentProfile, db: DbSession) -> PlacementResult | None:
    a = db.scalar(
        select(UserAssessment)
        .where(UserAssessment.user_id == profile.id, UserAssessment.status == "completed")
        .order_by(UserAssessment.completed_at.desc())
    )
    return _result(a) if a else None
