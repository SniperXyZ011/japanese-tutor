import asyncio

import httpx
import pytest
import respx

from app.core.config import Settings
from app.services.ai.base import AIProviderError
from app.services.ai.openrouter import OpenRouterProvider


def provider():
    return OpenRouterProvider(Settings(openrouter_api_key="test-key", ai_max_retries=1))


def call(p):
    return asyncio.run(p.complete_json(task="t", system="s", messages=[{"role": "user", "content": "hi"}],
                                       max_tokens=50, context={}))


@respx.mock
def test_success_parses_json():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "model": "m", "choices": [{"message": {"content": '{"ok": true}'}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2}}))
    r = call(provider())
    assert r.data == {"ok": True} and r.input_tokens == 1


@respx.mock
def test_retry_then_fail():
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(return_value=httpx.Response(503))
    with pytest.raises(AIProviderError):
        call(provider())
    assert route.call_count == 2


@respx.mock
def test_auth_error_not_retried():
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(return_value=httpx.Response(401))
    with pytest.raises(AIProviderError):
        call(provider())
    assert route.call_count == 1


@respx.mock
def test_malformed_content():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "choices": [{"message": {"content": "not json at all"}}]}))
    with pytest.raises(AIProviderError):
        call(provider())


def test_content_validates():
    from app.seed import load_content
    units = load_content()
    assert len(units) == 6 and sum(len(u.lessons) for u in units) == 13
