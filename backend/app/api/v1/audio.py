from fastapi import APIRouter, File, UploadFile

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import CurrentProfile
from app.schemas.api import TranscriptionOut, TTSIn, TTSOut

router = APIRouter(prefix="/audio", tags=["audio"])
ALLOWED_AUDIO = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/m4a",
}


@router.post("/tts", response_model=TTSOut)
def tts(body: TTSIn, profile: CurrentProfile) -> TTSOut:
    """Server TTS is not configured (browser speech chosen for the MVP); the client should speak locally."""
    return TTSOut(
        provider=get_settings().tts_provider,
        audio_url=None,
        cached=False,
        use_browser_fallback=True,
        message="Using your browser's Japanese voice.",
    )


@router.post("/transcribe", response_model=TranscriptionOut)
async def transcribe(profile: CurrentProfile, file: UploadFile = File(...)) -> TranscriptionOut:
    s = get_settings()
    content_type = (file.content_type or "").split(";")[0].strip()
    if content_type not in ALLOWED_AUDIO:
        raise AppError(
            415, "unsupported_audio", "Unsupported audio format.", {"content_type": content_type}
        )
    data = await file.read(s.max_upload_bytes + 1)
    if len(data) > s.max_upload_bytes:
        raise AppError(413, "audio_too_large", "Recording is too large.")
    if len(data) < 100:
        raise AppError(422, "audio_empty", "The recording appears to be empty.")
    if s.stt_provider == "mock":
        return TranscriptionOut(provider="mock", text="こんにちは", confidence=None, is_mock=True)
    raise AppError(
        501,
        "stt_not_configured",
        "Server transcription is not configured. Use in-browser speech recognition or type your answer.",
    )
