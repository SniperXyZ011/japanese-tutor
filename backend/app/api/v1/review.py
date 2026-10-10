from datetime import timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.errors import NotFoundError
from app.core.security import CurrentProfile, DbSession
from app.models import GrammarConcept, ReviewItem, Vocabulary
from app.schemas.api import ReviewCard, ReviewQueueOut, ReviewSubmitIn, ReviewSubmitOut
from app.services.learning import now_utc, touch_streak
from app.services.srs import schedule_next

router = APIRouter(prefix="/review", tags=["review"])


def _card(db, r: ReviewItem) -> ReviewCard:
    if r.concept_type == "grammar":
        g = db.get(GrammarConcept, r.concept_id)
        ex = (g.examples or [{}])[0] if g else {}
        return ReviewCard(
            id=r.id,
            concept_id=r.concept_id,
            concept_type=r.concept_type,
            state=r.state,
            due_at=r.due_at,
            from_mistake=r.from_mistake,
            front=g.pattern if g else r.concept_id,
            reading=None,
            meaning=g.name if g else "",
            detail=(g.explanation if g else None),
            audio_text=ex.get("japanese"),
        )
    v = db.get(Vocabulary, r.concept_id)
    return ReviewCard(
        id=r.id,
        concept_id=r.concept_id,
        concept_type=r.concept_type,
        state=r.state,
        due_at=r.due_at,
        from_mistake=r.from_mistake,
        front=v.japanese if v else r.concept_id,
        reading=(v.reading if v and v.reading != v.japanese else None),
        meaning=v.meaning if v else "",
        detail=(f"{v.romaji} · {v.part_of_speech}" if v else None),
        audio_text=(v.japanese.replace("〜", "") if v else None),
    )


@router.get("", response_model=ReviewQueueOut)
def queue(
    profile: CurrentProfile, db: DbSession, limit: int = Query(20, ge=1, le=50)
) -> ReviewQueueOut:
    now = now_utc()
    base = select(ReviewItem).where(ReviewItem.user_id == profile.id, ReviewItem.due_at <= now)
    due = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.scalars(base.order_by(ReviewItem.from_mistake.desc(), ReviewItem.due_at).limit(limit))
    )
    return ReviewQueueOut(due_count=due, items=[_card(db, r) for r in items])


@router.post("", response_model=ReviewSubmitOut)
def submit(body: ReviewSubmitIn, profile: CurrentProfile, db: DbSession) -> ReviewSubmitOut:
    r = db.get(ReviewItem, body.review_id)
    if r is None or r.user_id != profile.id:
        raise NotFoundError("Review item")
    now = now_utc()
    s = schedule_next(
        grade=body.grade,
        now=now,
        state=r.state,
        interval_days=r.interval_days,
        ease=r.ease,
        repetitions=r.repetitions,
        lapses=r.lapses,
    )
    r.state, r.interval_days, r.ease, r.repetitions, r.lapses = (
        s.state,
        s.interval_days,
        s.ease,
        s.repetitions,
        s.lapses,
    )
    r.due_at, r.last_grade, r.last_reviewed_at = s.due_at, body.grade, now
    if body.grade in ("good", "easy") and s.interval_days >= 1:
        r.from_mistake = False
    touch_streak(profile)
    db.commit()
    return ReviewSubmitOut(
        review_id=r.id, next_due_at=r.due_at, interval_days=r.interval_days, state=r.state
    )


@router.get("/upcoming")
def upcoming(profile: CurrentProfile, db: DbSession) -> dict[str, int]:
    now = now_utc()
    q = select(func.count(ReviewItem.id)).where(ReviewItem.user_id == profile.id)
    return {
        "due_now": db.scalar(q.where(ReviewItem.due_at <= now)) or 0,
        "next_24h": db.scalar(
            q.where(ReviewItem.due_at > now, ReviewItem.due_at <= now + timedelta(days=1))
        )
        or 0,
        "total": db.scalar(q) or 0,
    }
