import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.core.security import CurrentProfile, DbSession
from app.models import ConversationSession, ConversationTurn
from app.schemas.ai import Explanation
from app.schemas.api import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ExplainIn,
    Page,
    RecapOut,
    TurnIn,
    TurnOut,
    TurnResult,
)
from app.services.ai.base import AIUnavailableError
from app.services.ai.service import AI, AIService
from app.services.learning import now_utc, touch_streak

router = APIRouter(tags=["conversations"])


def _require_ai(ai: AIService) -> None:
    if not ai.available:
        raise AIUnavailableError()


def _owned(db, cid: uuid.UUID, uid: uuid.UUID) -> ConversationSession:
    c = db.get(ConversationSession, cid)
    if c is None or c.user_id != uid:
        raise NotFoundError("Conversation")
    return c


def _add_turn(
    db, c: ConversationSession, role: str, text: str, input_mode: str | None, content: dict
) -> ConversationTurn:
    pos = (
        db.scalar(
            select(func.max(ConversationTurn.position)).where(ConversationTurn.session_id == c.id)
        )
        or 0
    ) + 1
    t = ConversationTurn(
        session_id=c.id, position=pos, role=role, text=text, input_mode=input_mode, content=content
    )
    db.add(t)
    c.turn_count = pos
    return t


def _history(db, c: ConversationSession) -> list[tuple[str, str]]:
    turns = db.scalars(
        select(ConversationTurn)
        .where(ConversationTurn.session_id == c.id)
        .order_by(ConversationTurn.position)
    )
    return [(t.role, t.text) for t in turns]


@router.get("/conversations", response_model=Page[ConversationOut])
def list_conversations(
    profile: CurrentProfile,
    db: DbSession,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> Page[ConversationOut]:
    q = select(ConversationSession).where(ConversationSession.user_id == profile.id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(ConversationSession.created_at.desc()).limit(limit).offset(offset))
    return Page(
        items=[ConversationOut.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/conversations", response_model=ConversationDetail, status_code=201)
async def create_conversation(
    body: ConversationCreate, profile: CurrentProfile, db: DbSession, ai: AI
) -> ConversationDetail:
    _require_ai(ai)
    c = ConversationSession(
        user_id=profile.id,
        topic=body.topic.strip(),
        mode=body.mode,
        status="active",
        turn_count=0,
        provider=ai.provider.name,
    )
    db.add(c)
    db.flush()
    reply, _ = await ai.tutor_reply(
        profile.id,
        level=profile.current_level or "absolute_beginner",
        topic=c.topic,
        mode=c.mode,
        history=[],
        user_text=None,
    )
    _add_turn(db, c, "tutor", reply.japanese, None, {**reply.model_dump(), "is_mock": ai.is_mock})
    touch_streak(profile)
    db.commit()
    return get_conversation(c.id, profile, db)


@router.get("/conversations/{cid}", response_model=ConversationDetail)
def get_conversation(
    cid: uuid.UUID, profile: CurrentProfile, db: DbSession, limit: int = 100, offset: int = 0
) -> ConversationDetail:
    c = _owned(db, cid, profile.id)
    turns = list(
        db.scalars(
            select(ConversationTurn)
            .where(ConversationTurn.session_id == c.id)
            .order_by(ConversationTurn.position)
            .limit(limit)
            .offset(offset)
        )
    )
    return ConversationDetail(
        **ConversationOut.model_validate(c).model_dump(),
        turns=[TurnOut.model_validate(t) for t in turns],
        turns_total=c.turn_count,
    )


@router.post("/conversations/{cid}/turns", response_model=TurnResult)
async def add_turn(
    cid: uuid.UUID, body: TurnIn, profile: CurrentProfile, db: DbSession, ai: AI
) -> TurnResult:
    c = _owned(db, cid, profile.id)
    if c.status != "active":
        raise AppError(409, "conversation_closed", "This conversation has ended.")
    if c.turn_count >= get_settings().max_conversation_turns:
        raise AppError(
            409, "turn_limit", "This conversation reached its turn limit. Start a new one."
        )
    _require_ai(ai)
    history = _history(db, c)
    reply, _ = await ai.tutor_reply(
        profile.id,
        level=profile.current_level or "absolute_beginner",
        topic=c.topic,
        mode=c.mode,
        history=history,
        user_text=body.text.strip(),
    )
    learner = _add_turn(
        db,
        c,
        "learner",
        body.text.strip(),
        body.input_mode,
        {"correction": reply.correction.model_dump()},
    )
    db.flush()
    tutor = _add_turn(
        db, c, "tutor", reply.japanese, None, {**reply.model_dump(), "is_mock": ai.is_mock}
    )
    touch_streak(profile)
    db.commit()
    db.refresh(learner)
    db.refresh(tutor)
    return TurnResult(
        learner_turn=TurnOut.model_validate(learner),
        tutor_turn=TurnOut.model_validate(tutor),
        is_mock=ai.is_mock,
    )


@router.post("/conversations/{cid}/finish", response_model=RecapOut)
async def finish(cid: uuid.UUID, profile: CurrentProfile, db: DbSession, ai: AI) -> RecapOut:
    c = _owned(db, cid, profile.id)
    if c.summary:
        from app.schemas.ai import Recap

        return RecapOut(
            conversation=ConversationOut.model_validate(c),
            recap=Recap.model_validate(c.summary),
            is_mock=c.provider == "mock",
        )
    _require_ai(ai)
    recap, _ = await ai.recap(profile.id, topic=c.topic, turns=_history(db, c))
    c.summary = recap.model_dump()
    c.status = "completed"
    c.completed_at = now_utc()
    db.commit()
    db.refresh(c)
    return RecapOut(conversation=ConversationOut.model_validate(c), recap=recap, is_mock=ai.is_mock)


@router.post("/explain", response_model=Explanation)
async def explain(body: ExplainIn, profile: CurrentProfile, ai: AI) -> Explanation:
    _require_ai(ai)
    out, _ = await ai.explain(
        profile.id,
        text=body.text,
        kind=body.kind,
        level=profile.current_level or "absolute_beginner",
    )
    return out
