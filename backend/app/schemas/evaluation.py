from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["correct", "almost", "incorrect", "unverified"]
Evaluator = Literal["deterministic", "ai", "mock_ai", "fallback"]


class EvaluationResult(BaseModel):
    is_correct: bool
    score: float = Field(ge=0, le=1)
    verdict: Verdict
    feedback: str
    corrected_answer: str | None = None
    expected_answers: list[str] = Field(default_factory=list)
    explanation: str | None = None
    accepted_alternative: bool = False
    meaning: str | None = None
    grammar: str | None = None
    naturalness: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    evaluator: Evaluator = "deterministic"
    transcript_note: str | None = None
    follow_up: str | None = None
