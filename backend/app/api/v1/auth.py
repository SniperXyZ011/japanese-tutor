import httpx
from fastapi import APIRouter, Response
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    CurrentProfile,
    DbSession,
    create_local_token,
    hash_password,
    verify_password,
)
from app.models import LocalUser, Profile
from app.schemas.api import AuthSession, Capabilities, LocalCredentials
from app.services.ai.service import get_provider

router = APIRouter(tags=["auth"])


def _require_local() -> None:
    if get_settings().auth_mode != "local":
        raise AppError(404, "not_found", "Local auth is disabled; sign in with Supabase.")


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=s.session_cookie_secure,
        max_age=s.local_session_ttl_hours * 3600,
        path="/",
    )


@router.get("/capabilities", response_model=Capabilities)
def capabilities() -> Capabilities:
    s = get_settings()
    provider = get_provider(s)
    return Capabilities(
        auth_mode=s.auth_mode,
        ai_provider=provider.name,
        ai_model=s.openrouter_text_model if provider.name == "openrouter" else None,
        ai_is_mock=provider.is_mock,
        tts_provider=s.tts_provider,
        stt_provider=s.stt_provider,
        max_recording_seconds=s.max_recording_seconds,
        max_conversation_turns=s.max_conversation_turns,
    )


@router.post("/auth/signup", response_model=AuthSession, status_code=201)
def signup(body: LocalCredentials, response: Response, db: DbSession) -> AuthSession:
    _require_local()
    email = body.email.lower()
    if db.scalar(select(LocalUser).where(LocalUser.email == email)):
        raise AppError(409, "email_taken", "An account with this email already exists.")
    user = LocalUser(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    db.add(Profile(id=user.id, email=email, onboarding={}))
    db.commit()
    token = create_local_token(user.id, email, get_settings())
    _set_cookie(response, token)
    return AuthSession(user_id=user.id, email=email, access_token=token)


@router.post("/auth/login", response_model=AuthSession)
def login(body: LocalCredentials, response: Response, db: DbSession) -> AuthSession:
    _require_local()
    email = body.email.lower()
    user = db.scalar(select(LocalUser).where(LocalUser.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")
    token = create_local_token(user.id, email, get_settings())
    _set_cookie(response, token)
    return AuthSession(user_id=user.id, email=email, access_token=token)


@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    response.status_code = 204
    return response


@router.delete("/me", status_code=204)
def delete_account(profile: CurrentProfile, db: DbSession, response: Response) -> Response:
    """Delete all learner data. In Supabase mode also removes the auth user when a service key is set."""
    s = get_settings()
    user_id = profile.id
    db.delete(profile)
    db.execute(delete(LocalUser).where(LocalUser.id == user_id))
    db.commit()
    if s.auth_mode == "supabase" and s.supabase_url and s.supabase_service_role_key:
        key = s.supabase_service_role_key
        try:
            httpx.delete(
                f"{s.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                timeout=10,
            )
        except httpx.HTTPError:
            pass
    response.delete_cookie(s.session_cookie_name, path="/")
    response.status_code = 204
    return response
