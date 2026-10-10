"""Deterministic mock AI provider for development without an API key and for tests.

Every response is flagged with is_mock so the UI can label it clearly.
"""

from typing import Any

from app.services.ai.base import AIResult
from app.services.japanese import normalize_japanese, similarity

_TUTOR_SCRIPT = [
    ("こんにちは！お名前は何ですか？", "おなまえはなんですか", "Hello! What is your name?"),
    (
        "はじめまして。どこから来ましたか？",
        "どこからきましたか",
        "Nice to meet you. Where are you from?",
    ),
    ("そうですか。趣味は何ですか？", "しゅみはなんですか", "I see. What are your hobbies?"),
    (
        "いいですね。毎日日本語を勉強しますか？",
        "まいにちにほんごをべんきょうしますか",
        "Nice. Do you study Japanese every day?",
    ),
    (
        "すごいですね！今日は何を食べましたか？",
        "きょうはなにをたべましたか",
        "Great! What did you eat today?",
    ),
]


class MockProvider:
    name = "mock"
    model = "mock-tutor"
    is_mock = True

    async def complete_json(
        self,
        *,
        task: str,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        context: dict[str, Any] | None = None,
    ) -> AIResult:
        ctx = context or {}
        handler = getattr(self, f"_{task}", self._default)
        return AIResult(data=handler(ctx), provider=self.name, model=self.model, is_mock=True)

    def _tutor_reply(self, ctx: dict[str, Any]) -> dict[str, Any]:
        idx = int(ctx.get("assistant_turns", 0)) % len(_TUTOR_SCRIPT)
        ja, reading, en = _TUTOR_SCRIPT[idx]
        user_text = str(ctx.get("user_text", ""))
        has_error = bool(user_text) and not user_text.rstrip().endswith(
            ("です", "です。", "ます", "ます。")
        )
        return {
            "japanese": ja,
            "reading": reading,
            "english": en,
            "correction": {
                "has_error": has_error,
                "corrected": (user_text.rstrip("。") + "です。") if has_error else None,
                "explanation": (
                    "[Mock] In polite speech, end statements with です or ます."
                    if has_error
                    else None
                ),
            },
            "new_vocabulary": [],
            "follow_up_hint": "[Mock] Try answering with a full sentence ending in です.",
        }

    def _evaluate_answer(self, ctx: dict[str, Any]) -> dict[str, Any]:
        answer = normalize_japanese(str(ctx.get("answer", "")))
        expected = [normalize_japanese(a) for a in ctx.get("expected", [])]
        best = max((similarity(answer, e) for e in expected), default=0.0)
        correct = best >= 0.75
        return {
            "is_correct": correct,
            "score": round(best, 2),
            "meaning": "[Mock] Meaning appears to match." if correct else "[Mock] Meaning differs.",
            "grammar": "[Mock] Not analysed by a real model.",
            "naturalness": "[Mock] Not analysed by a real model.",
            "corrected_answer": (ctx.get("expected") or [None])[0],
            "explanation": "[Mock] This is a simulated evaluation. Configure OpenRouter for real feedback.",
            "accepted_alternative": False,
            "confidence": 0.4,
            "follow_up": None,
        }

    def _explain(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": f"[Mock] About: {ctx.get('text', '')}"[:120],
            "explanation": "[Mock] A real explanation will appear once OpenRouter is configured.",
            "examples": [],
        }

    def _recap(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": "[Mock] You practised a short conversation in Japanese.",
            "strengths": ["[Mock] You kept the conversation going."],
            "improvements": ["[Mock] Practise ending sentences with です/ます."],
            "vocabulary": [],
            "corrections": [],
        }

    def _default(self, ctx: dict[str, Any]) -> dict[str, Any]:
        return {"message": "[Mock] response"}
