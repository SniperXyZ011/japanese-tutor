import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.errors import AppError


class AIUnavailableError(AppError):
    def __init__(self, message: str = "AI features are not configured on this server.") -> None:
        super().__init__(503, "ai_unavailable", message)


class AIProviderError(AppError):
    def __init__(self, message: str, code: str = "ai_provider_error") -> None:
        super().__init__(502, code, message)


@dataclass
class AIResult:
    data: dict[str, Any]
    provider: str
    model: str | None
    is_mock: bool
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_text: str = field(default="", repr=False)


class LLMProvider(Protocol):
    name: str
    model: str | None
    is_mock: bool

    async def complete_json(
        self,
        *,
        task: str,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        context: dict[str, Any] | None = None,
    ) -> AIResult: ...


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def parse_json_loose(text: str) -> dict[str, Any]:
    """Parse model output that should be a JSON object, tolerating code fences or prose."""
    if not text:
        raise ValueError("empty response")
    cleaned = _FENCE.sub("", text.strip()).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object found") from None
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


class NullProvider:
    name = "none"
    model = None
    is_mock = False

    async def complete_json(self, **_: Any) -> AIResult:
        raise AIUnavailableError(
            "AI is not configured. Set OPENROUTER_API_KEY (and optionally OPENROUTER_TEXT_MODEL)."
        )
