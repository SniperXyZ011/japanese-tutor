from functools import lru_cache
from typing import Literal
from urllib.parse import quote, unquote

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _encode_password(url: str) -> str:
    """Percent-encode a DB password pasted with raw special characters (e.g. '@', '#', '$')."""
    scheme, sep, rest = url.partition("://")
    if not sep or "@" not in rest:
        return url
    creds, _, host = rest.rpartition("@")
    user, colon, password = creds.partition(":")
    if not colon:
        return url
    return f"{scheme}://{user}:{quote(unquote(password), safe='')}@{host}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Japanese Tutor API"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    database_url: str = "postgresql+psycopg://jt:jt@localhost:5432/japanese_tutor"

    # Authentication
    auth_mode: Literal["supabase", "local"] = "local"
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None
    supabase_jwt_audience: str = "authenticated"
    local_jwt_secret: str = "dev-only-change-me-dev-only-change-me"
    local_session_ttl_hours: int = 24 * 7
    session_cookie_name: str = "jt_session"
    session_cookie_secure: bool = False

    # AI (OpenRouter)
    ai_provider: Literal["openrouter", "mock", "none"] | None = None
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_text_model: str = "google/gemini-2.5-flash"
    openrouter_tts_model: str | None = None
    openrouter_stt_model: str | None = None
    openrouter_site_url: str | None = None
    openrouter_app_name: str = "Japanese Tutor"
    ai_timeout_seconds: float = 30.0
    ai_max_output_tokens: int = 700
    ai_max_retries: int = 1

    # Audio
    tts_provider: Literal["browser", "mock"] = "browser"
    stt_provider: Literal["browser", "mock"] = "browser"
    audio_storage_dir: str = "./storage/audio"
    max_recording_seconds: int = 30
    max_upload_bytes: int = 5 * 1024 * 1024

    # Usage controls
    ai_requests_per_minute: int = 12
    ai_requests_per_day: int = 300
    max_conversation_turns: int = 40

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("database_url", mode="before")
    @classmethod
    def _psycopg_driver(cls, v: object) -> object:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = "postgresql://" + v[len("postgres://") :]
            if v.startswith("postgresql://"):
                v = "postgresql+psycopg://" + v[len("postgresql://") :]
            v = _encode_password(v)
        return v

    @property
    def resolved_ai_provider(self) -> str:
        if self.ai_provider:
            return self.ai_provider
        if self.openrouter_api_key:
            return "openrouter"
        return "none" if self.app_env == "production" else "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
