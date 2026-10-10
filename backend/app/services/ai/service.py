import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, TypeVar

from fastapi import Depends
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models import ApiUsageLog
from app.schemas.ai import AIEvaluation, Explanation, Recap, TutorReply
from app.services.ai.base import AIProviderError, AIResult, LLMProvider, NullProvider
from app.services.ai.mock import MockProvider
from app.services.ai.openrouter import OpenRouterProvider

logger = logging.getLogger("app.ai")
T = TypeVar("T", bound=BaseModel)

TUTOR_SYSTEM = """You are a patient, encouraging Japanese tutor for an English-speaking learner.
Learner level: {level}. Conversation topic: {topic}. Mode: {mode}.{focus}
Rules:
- Reply in natural, grammatically correct Japanese suited to the learner's level (polite です/ます \
form for beginners). Keep replies to 1-2 short sentences and end with a simple question that \
keeps the conversation going.
- Introduce at most 2 new words per turn.
- If the learner's last message contains an important error, set correction.has_error=true, give \
the corrected version of ONLY the learner's latest message (never include your own text) and a short English explanation. Do not flag purely stylistic choices. \
Accept valid alternative phrasings.
- The learner's message may come from speech recognition and contain transcription errors; do not \
treat obvious recognition artefacts as grammar errors.
- reading: the full reply in hiragana/katakana only.
Return ONLY a JSON object: {{"japanese": str, "reading": str, "english": str, "correction": \
{{"has_error": bool, "corrected": str|null, "explanation": str|null}}, "new_vocabulary": \
[{{"japanese": str, "reading": str, "meaning": str}}], "follow_up_hint": str|null}}"""

EVAL_SYSTEM = """You evaluate a Japanese learner's answer to an exercise. Be fair and precise.
Rubric: (1) meaning matches the task, (2) grammatical correctness, (3) naturalness, (4) uses the \
required target grammar/vocabulary if specified. Accept valid alternatives: different word order, \
kanji vs kana spellings, polite vs casual if the task does not require one, minor punctuation or \
spacing. Do not mark wrong only because it differs from the reference answers. If the input came \
from speech recognition, ignore likely transcription artefacts and do not judge pronunciation.
Return ONLY a JSON object: {"is_correct": bool, "score": number 0-1, "meaning": str, \
"grammar": str, "naturalness": str, "corrected_answer": str|null, "explanation": str (short, \
English), "accepted_alternative": bool, "confidence": number 0-1, "follow_up": str|null}"""

EXPLAIN_SYSTEM = """You explain Japanese {kind} to an English-speaking learner at level {level}.
Be concise (under 120 words), accurate and practical. Give up to 3 short natural examples.
Return ONLY a JSON object: {{"title": str, "explanation": str, "examples": [{{"japanese": str, \
"reading": str, "english": str}}]}}"""

RECAP_SYSTEM = """Summarise a short Japanese practice conversation for the learner in English.
List up to 3 strengths, up to 3 things to improve, up to 6 useful vocabulary items from the \
conversation and the most important corrections. Be encouraging and specific.
Return ONLY a JSON object: {"summary": str, "strengths": [str], "improvements": [str], \
"vocabulary": [{"japanese": str, "reading": str, "meaning": str}], "corrections": \
[{"has_error": true, "corrected": str, "explanation": str}]}"""


def get_provider(settings: Settings) -> LLMProvider:
    provider = settings.resolved_ai_provider
    if provider == "openrouter":
        return OpenRouterProvider(settings)
    if provider == "mock":
        return MockProvider()
    return NullProvider()


class AIService:
    def __init__(self, db: Session, settings: Settings, provider: LLMProvider) -> None:
        self.db = db
        self.settings = settings
        self.provider = provider

    @property
    def available(self) -> bool:
        return self.provider.name != "none"

    @property
    def is_mock(self) -> bool:
        return self.provider.is_mock

    def _check_limits(self, user_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        base = select(func.count(ApiUsageLog.id)).where(ApiUsageLog.user_id == user_id)
        minute = self.db.scalar(base.where(ApiUsageLog.created_at >= now - timedelta(minutes=1)))
        if (minute or 0) >= self.settings.ai_requests_per_minute:
            self._log(user_id, "rate_limit", "rate_limited", 0, error_code="per_minute")
            raise AppError(429, "rate_limited", "Too many AI requests. Please wait a moment.")
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day = self.db.scalar(base.where(ApiUsageLog.created_at >= day_start))
        if (day or 0) >= self.settings.ai_requests_per_day:
            self._log(user_id, "rate_limit", "rate_limited", 0, error_code="daily_budget")
            raise AppError(429, "daily_limit", "Daily AI usage limit reached. Try again tomorrow.")

    def _log(
        self,
        user_id: uuid.UUID | None,
        operation: str,
        status: str,
        latency_ms: int,
        result: AIResult | None = None,
        error_code: str | None = None,
    ) -> None:
        self.db.add(
            ApiUsageLog(
                user_id=user_id,
                provider=self.provider.name,
                operation=operation,
                model=(result.model if result else self.provider.model),
                status=status,
                latency_ms=latency_ms,
                input_tokens=result.input_tokens if result else None,
                output_tokens=result.output_tokens if result else None,
                error_code=error_code,
            )
        )
        self.db.commit()

    async def _call(
        self,
        user_id: uuid.UUID,
        *,
        task: str,
        system: str,
        messages: list[dict[str, str]],
        schema: type[T],
        context: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> tuple[T, AIResult]:
        self._check_limits(user_id)
        try:
            result = await self.provider.complete_json(
                task=task,
                system=system,
                messages=messages,
                max_tokens=max_tokens or self.settings.ai_max_output_tokens,
                context=context,
            )
        except AppError as exc:
            self._log(user_id, task, "error", 0, error_code=exc.code)
            raise
        try:
            parsed = schema.model_validate(result.data)
        except ValidationError:
            logger.warning("ai_invalid_schema task=%s provider=%s", task, self.provider.name)
            self._log(user_id, task, "error", result.latency_ms, result, "invalid_schema")
            raise AIProviderError(
                "The AI returned an unexpected response. Please try again.",
                code="ai_invalid_output",
            ) from None
        logger.info(
            "ai_call task=%s provider=%s model=%s latency_ms=%s in=%s out=%s",
            task,
            self.provider.name,
            result.model,
            result.latency_ms,
            result.input_tokens,
            result.output_tokens,
        )
        self._log(user_id, task, "ok", result.latency_ms, result)
        return parsed, result

    async def tutor_reply(
        self,
        user_id: uuid.UUID,
        *,
        level: str,
        topic: str,
        mode: str,
        history: list[tuple[str, str]],
        user_text: str | None,
        focus: str | None = None,
    ) -> tuple[TutorReply, AIResult]:
        messages = [
            {"role": "assistant" if role == "tutor" else "user", "content": text}
            for role, text in history[-12:]
        ]
        if user_text:
            messages.append({"role": "user", "content": user_text})
        else:
            messages.append(
                {"role": "user", "content": "(Start the conversation with a simple greeting.)"}
            )
        system = TUTOR_SYSTEM.format(
            level=level,
            topic=topic,
            mode=mode,
            focus=f"\nLesson focus: {focus}." if focus else "",
        )
        return await self._call(
            user_id,
            task="tutor_reply",
            system=system,
            messages=messages,
            schema=TutorReply,
            context={
                "user_text": user_text or "",
                "assistant_turns": sum(1 for r, _ in history if r == "tutor"),
            },
        )

    async def evaluate_open_answer(
        self,
        user_id: uuid.UUID,
        *,
        instructions: str,
        prompt: str | None,
        expected: list[str],
        answer: str,
        input_mode: str,
        target: list[str] | None = None,
    ) -> tuple[AIEvaluation, AIResult]:
        payload = {
            "instructions": instructions,
            "prompt": prompt,
            "reference_answers": expected,
            "target_grammar_or_vocabulary": target or [],
            "learner_answer": answer,
            "input_mode": input_mode,
        }
        return await self._call(
            user_id,
            task="evaluate_answer",
            system=EVAL_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            schema=AIEvaluation,
            context={"answer": answer, "expected": expected},
            max_tokens=500,
        )

    async def explain(
        self, user_id: uuid.UUID, *, text: str, kind: str, level: str
    ) -> tuple[Explanation, AIResult]:
        return await self._call(
            user_id,
            task="explain",
            system=EXPLAIN_SYSTEM.format(kind=kind, level=level),
            messages=[{"role": "user", "content": text}],
            schema=Explanation,
            context={"text": text},
            max_tokens=500,
        )

    async def recap(
        self, user_id: uuid.UUID, *, topic: str, turns: list[tuple[str, str]]
    ) -> tuple[Recap, AIResult]:
        transcript = "\n".join(f"{'Tutor' if r == 'tutor' else 'Learner'}: {t}" for r, t in turns)
        return await self._call(
            user_id,
            task="recap",
            system=RECAP_SYSTEM,
            messages=[{"role": "user", "content": f"Topic: {topic}\n\n{transcript}"}],
            schema=Recap,
            context={},
            max_tokens=700,
        )


def get_ai_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AIService:
    return AIService(db, settings, get_provider(settings))


AI = Annotated[AIService, Depends(get_ai_service)]
