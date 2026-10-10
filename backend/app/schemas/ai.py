from pydantic import BaseModel, Field, field_validator


def _clip(v: object, n: int) -> object:
    return v[:n] if isinstance(v, str) else v


class VocabNote(BaseModel):
    japanese: str = Field(max_length=60)
    reading: str | None = Field(default=None, max_length=60)
    meaning: str = Field(max_length=120)


class Correction(BaseModel):
    has_error: bool = False
    corrected: str | None = Field(default=None, max_length=300)
    explanation: str | None = Field(default=None, max_length=600)


class TutorReply(BaseModel):
    japanese: str = Field(min_length=1, max_length=400)
    reading: str | None = Field(default=None, max_length=600)
    english: str = Field(min_length=1, max_length=600)
    correction: Correction = Field(default_factory=Correction)
    new_vocabulary: list[VocabNote] = Field(default_factory=list, max_length=5)
    follow_up_hint: str | None = Field(default=None, max_length=300)

    @field_validator("new_vocabulary", mode="before")
    @classmethod
    def _limit_vocab(cls, v: object) -> object:
        return v[:5] if isinstance(v, list) else v


class AIEvaluation(BaseModel):
    is_correct: bool
    score: float = Field(ge=0, le=1)
    meaning: str | None = Field(default=None, max_length=400)
    grammar: str | None = Field(default=None, max_length=400)
    naturalness: str | None = Field(default=None, max_length=400)
    corrected_answer: str | None = Field(default=None, max_length=300)
    explanation: str = Field(default="", max_length=800)
    accepted_alternative: bool = False
    confidence: float = Field(default=0.5, ge=0, le=1)
    follow_up: str | None = Field(default=None, max_length=300)

    @field_validator("score", "confidence", mode="before")
    @classmethod
    def _clamp(cls, v: object) -> object:
        if isinstance(v, int | float):
            return max(0.0, min(1.0, float(v)))
        return v

    @field_validator("explanation", mode="before")
    @classmethod
    def _clip_expl(cls, v: object) -> object:
        return _clip(v, 800)


class Example(BaseModel):
    japanese: str
    reading: str | None = None
    english: str


class Explanation(BaseModel):
    title: str = Field(max_length=160)
    explanation: str = Field(max_length=1500)
    examples: list[Example] = Field(default_factory=list, max_length=4)

    @field_validator("examples", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return v[:4] if isinstance(v, list) else v


class Recap(BaseModel):
    summary: str = Field(max_length=800)
    strengths: list[str] = Field(default_factory=list, max_length=5)
    improvements: list[str] = Field(default_factory=list, max_length=5)
    vocabulary: list[VocabNote] = Field(default_factory=list, max_length=10)
    corrections: list[Correction] = Field(default_factory=list, max_length=10)

    @field_validator("strengths", "improvements", "vocabulary", "corrections", mode="before")
    @classmethod
    def _limit(cls, v: object) -> object:
        return v[:10] if isinstance(v, list) else v
