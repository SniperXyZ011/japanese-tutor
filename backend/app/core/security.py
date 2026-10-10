import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import bcrypt
import httpx
import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import Profile

logger = logging.getLogger("app.auth")

LOCAL_AUDIENCE = "jt-local"
LOCAL_ISSUER = "japanese-tutor"


class AuthError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(401, "unauthorized", message)


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str | None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_local_token(user_id: uuid.UUID, email: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "aud": LOCAL_AUDIENCE,
        "iss": LOCAL_ISSUER,
        "iat": now,
        "exp": now + timedelta(hours=settings.local_session_ttl_hours),
    }
    return jwt.encode(payload, settings.local_jwt_secret, algorithm="HS256")


def _decode_local(token: str, settings: Settings) -> CurrentUser:
    try:
        claims = jwt.decode(
            token,
            settings.local_jwt_secret,
            algorithms=["HS256"],
            audience=LOCAL_AUDIENCE,
            issuer=LOCAL_ISSUER,
        )
    except jwt.PyJWTError:
        raise AuthError("Invalid or expired session") from None
    return CurrentUser(id=uuid.UUID(claims["sub"]), email=claims.get("email"))


_jwks_clients: dict[str, jwt.PyJWKClient] = {}
_remote_cache: dict[str, tuple[float, CurrentUser]] = {}


def _supabase_jwks(settings: Settings) -> jwt.PyJWKClient:
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"  # type: ignore[union-attr]
    if url not in _jwks_clients:
        _jwks_clients[url] = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)
    return _jwks_clients[url]


def _claims_to_user(claims: dict[str, Any]) -> CurrentUser:
    if claims.get("role") not in (None, "authenticated"):
        raise AuthError("Unsupported token role")
    return CurrentUser(id=uuid.UUID(claims["sub"]), email=claims.get("email"))


def _verify_supabase_remote(token: str, settings: Settings) -> CurrentUser:
    """Fallback: ask Supabase Auth to validate the token (legacy HS256 projects without secret)."""
    key = hashlib.sha256(token.encode()).hexdigest()
    cached = _remote_cache.get(key)
    if cached and cached[0] > time.time():
        return cached[1]
    try:
        resp = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",  # type: ignore[union-attr]
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_anon_key or "",
            },
            timeout=10.0,
        )
    except httpx.HTTPError:
        raise AppError(503, "auth_unavailable", "Authentication service unavailable") from None
    if resp.status_code != 200:
        raise AuthError("Invalid or expired session")
    data = resp.json()
    user = CurrentUser(id=uuid.UUID(data["id"]), email=data.get("email"))
    _remote_cache[key] = (time.time() + 60, user)
    return user


def _decode_supabase(token: str, settings: Settings) -> CurrentUser:
    if not settings.supabase_url:
        raise AppError(500, "auth_misconfigured", "SUPABASE_URL is not configured")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise AuthError("Malformed token") from None
    alg = header.get("alg", "")
    try:
        if alg == "HS256":
            if not settings.supabase_jwt_secret:
                return _verify_supabase_remote(token, settings)
            claims = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.supabase_jwt_audience,
            )
        elif alg in ("RS256", "ES256"):
            signing_key = _supabase_jwks(settings).get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience=settings.supabase_jwt_audience,
            )
        else:
            raise AuthError("Unsupported token algorithm")
    except jwt.PyJWKClientError:
        return _verify_supabase_remote(token, settings)
    except jwt.PyJWTError:
        raise AuthError("Invalid or expired session") from None
    return _claims_to_user(claims)


def _extract_token(request: Request, settings: Settings) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    if settings.auth_mode == "local":
        return request.cookies.get(settings.session_cookie_name)
    return None


def get_current_user(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> CurrentUser:
    token = _extract_token(request, settings)
    if not token:
        raise AuthError()
    if settings.auth_mode == "local":
        return _decode_local(token, settings)
    return _decode_supabase(token, settings)


def get_profile(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Profile:
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(id=user.id, email=user.email, onboarding={})
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


CurrentProfile = Annotated[Profile, Depends(get_profile)]
DbSession = Annotated[Session, Depends(get_db)]
