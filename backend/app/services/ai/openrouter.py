import asyncio
import logging
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.services.ai.base import AIProviderError, AIResult, parse_json_loose

logger = logging.getLogger("app.ai.openrouter")

_RETRYABLE = {408, 429, 500, 502, 503, 504}


class OpenRouterProvider:
    """OpenRouter chat-completions client (OpenAI-compatible API).

    Only text generation is used. Audio is handled by separate providers because not every
    OpenRouter model supports audio input/output.
    """

    name = "openrouter"
    is_mock = False

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required for the OpenRouter provider")
        self._settings = settings
        self.model = settings.openrouter_text_model
        self._client = client

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": self._settings.openrouter_app_name,
        }
        if self._settings.openrouter_site_url:
            headers["HTTP-Referer"] = self._settings.openrouter_site_url
        return headers

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        url = f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions"
        timeout = httpx.Timeout(self._settings.ai_timeout_seconds, connect=10.0)
        if self._client is not None:
            return await self._client.post(
                url, json=payload, headers=self._headers(), timeout=timeout
            )
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, json=payload, headers=self._headers())

    async def complete_json(
        self,
        *,
        task: str,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        context: dict[str, Any] | None = None,
    ) -> AIResult:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        }
        attempts = 1 + max(0, self._settings.ai_max_retries)
        start = time.perf_counter()
        last_error: str = "unknown"
        for attempt in range(attempts):
            try:
                resp = await self._post(payload)
            except httpx.TimeoutException:
                last_error = "timeout"
            except httpx.HTTPError as exc:
                last_error = f"network:{type(exc).__name__}"
            else:
                if resp.status_code == 200:
                    return self._parse(resp, start)
                last_error = f"http_{resp.status_code}"
                if resp.status_code not in _RETRYABLE:
                    detail = _error_message(resp)
                    raise AIProviderError(
                        f"OpenRouter rejected the request ({resp.status_code}): {detail}",
                        code="ai_provider_rejected",
                    )
            if attempt < attempts - 1:
                await asyncio.sleep(0.6 * (attempt + 1))
        logger.warning("openrouter_failed task=%s error=%s", task, last_error)
        if last_error == "timeout":
            raise AIProviderError("The AI tutor took too long to respond.", code="ai_timeout")
        raise AIProviderError("The AI tutor is temporarily unavailable.")

    def _parse(self, resp: httpx.Response, start: float) -> AIResult:
        body = resp.json()
        if "error" in body:
            raise AIProviderError(f"OpenRouter error: {body['error'].get('message', 'unknown')}")
        try:
            text = body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise AIProviderError("Unexpected response format from OpenRouter.") from None
        try:
            data = parse_json_loose(text)
        except ValueError:
            raise AIProviderError(
                "The AI returned an invalid response. Please try again.", code="ai_invalid_output"
            ) from None
        usage = body.get("usage") or {}
        return AIResult(
            data=data,
            provider=self.name,
            model=body.get("model", self.model),
            is_mock=False,
            latency_ms=int((time.perf_counter() - start) * 1000),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            raw_text=text,
        )


def _error_message(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("error", {}).get("message", ""))[:200]
    except ValueError:
        return resp.text[:200]
