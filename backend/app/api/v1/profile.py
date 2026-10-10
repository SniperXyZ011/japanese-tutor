from fastapi import APIRouter

from app.core.security import CurrentProfile, DbSession
from app.schemas.api import ProfileOut, ProfileUpdate, Recommendation
from app.services.assessment import LEVEL_UNITS
from app.services.learning import recommend

router = APIRouter(tags=["profile"])


@router.get("/me", response_model=ProfileOut)
def get_me(profile: CurrentProfile) -> ProfileOut:
    return ProfileOut.model_validate(profile)


@router.patch("/me", response_model=ProfileOut)
def update_me(body: ProfileUpdate, profile: CurrentProfile, db: DbSession) -> ProfileOut:
    data = body.model_dump(exclude_unset=True)
    if "onboarding" in data and body.onboarding is not None:
        profile.onboarding = body.onboarding.model_dump()
        if body.onboarding.daily_minutes:
            profile.daily_goal_minutes = body.onboarding.daily_minutes
        data.pop("onboarding")
    if "current_level" in data and data["current_level"]:
        profile.start_unit_id = LEVEL_UNITS[data["current_level"]]
    for key, value in data.items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return ProfileOut.model_validate(profile)


@router.get("/recommendation", response_model=Recommendation)
def recommendation(profile: CurrentProfile, db: DbSession) -> Recommendation:
    return recommend(db, profile)
