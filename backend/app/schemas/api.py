import uuid
from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.ai import Correction, Recap, VocabNote
from app.schemas.evaluation import EvaluationResult

T = TypeVar("T")

Skill = Literal["listening", "speaking", "vocabulary", "grammar", "reading", "writing"]
SKILLS: tuple[str, ...] = ("listening", "speaking", "vocabulary", "grammar", "reading", "writing")
InputMode = Literal["typed", "speech", "choice"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# ----- Auth (local mode) -----
class LocalCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthSession(BaseModel):
    user_id: uuid.UUID
    email: str
    access_token: str


class Capabilities(BaseModel):
    auth_mode: str
    ai_provider: str
    ai_model: str | None
    ai_is_mock: bool
    tts_provider: str
    stt_provider: str
    max_recording_seconds: int
    max_conversation_turns: int


# ----- Profile -----
class OnboardingAnswers(BaseModel):
    prior_experience: Literal["none", "some_self_study", "classes", "lived_in_japan"] | None = None
    hiragana: Literal["none", "some", "fluent"] | None = None
    katakana: Literal["none", "some", "fluent"] | None = None
    kanji: Literal["none", "few", "n5", "n4_plus"] | None = None
    listening: Literal["none", "basic_phrases", "slow_conversation", "everyday"] | None = None
    speaking_confidence: Literal["none", "low", "medium", "high"] | None = None
    vocab_grammar: Literal["none", "basic", "n5", "n4_plus"] | None = None
    goals: list[str] = Field(default_factory=list, max_length=8)
    explanation_language: Literal["en"] = "en"
    daily_minutes: int | None = Field(default=None, ge=5, le=120)
    conversation_balance: Literal["more_structured", "balanced", "more_conversation"] | None = None


class ProfileOut(ORM):
    id: uuid.UUID
    email: str | None
    display_name: str | None
    onboarding: dict[str, Any]
    onboarding_completed: bool
    current_level: str | None
    start_unit_id: str | None
    explanation_language: str
    daily_goal_minutes: int
    playback_speed: float
    show_furigana: bool
    show_romaji: bool
    voice_name: str | None
    streak_days: int


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    onboarding: OnboardingAnswers | None = None
    onboarding_completed: bool | None = None
    current_level: Literal["absolute_beginner", "beginner", "n5", "n5_plus"] | None = None
    daily_goal_minutes: int | None = Field(default=None, ge=5, le=120)
    playback_speed: float | None = Field(default=None, ge=0.5, le=1.5)
    show_furigana: bool | None = None
    show_romaji: bool | None = None
    voice_name: str | None = Field(default=None, max_length=120)


# ----- Curriculum -----
class VocabularyOut(ORM):
    id: str
    japanese: str
    reading: str
    romaji: str
    meaning: str
    part_of_speech: str
    example_ja: str | None
    example_en: str | None


class GrammarOut(ORM):
    id: str
    name: str
    pattern: str
    explanation: str
    examples: list[dict[str, str]]


class ExerciseOut(ORM):
    id: str
    position: int
    type: str
    skill: str
    instructions: str
    prompt_ja: str | None
    prompt_reading: str | None
    prompt_romaji: str | None
    prompt_en: str | None
    audio_text: str | None
    choices: list[str]
    hints: list[str]
    meta: dict[str, Any]


class LessonSummary(BaseModel):
    id: str
    unit_id: str
    position: int
    title: str
    summary: str
    difficulty: int
    estimated_minutes: int
    status: Literal["not_started", "in_progress", "completed"]
    best_score: float | None
    locked: bool


class UnitOut(BaseModel):
    id: str
    position: int
    title: str
    description: str
    level: str
    lessons: list[LessonSummary]


class LessonDetail(BaseModel):
    id: str
    unit_id: str
    title: str
    summary: str
    objectives: list[str]
    prerequisites: list[str]
    difficulty: int
    estimated_minutes: int
    pass_score: float
    vocabulary: list[VocabularyOut]
    grammar: list[GrammarOut]
    exercises: list[ExerciseOut]
    status: str
    attempt_id: uuid.UUID | None
    current_step: int


class Recommendation(BaseModel):
    kind: Literal["review", "lesson", "assessment", "onboarding", "complete"]
    reason: str
    lesson: LessonSummary | None = None
    due_reviews: int = 0
    weak_concepts: list[str] = Field(default_factory=list)


class LessonStartOut(BaseModel):
    attempt_id: uuid.UUID
    current_step: int
    status: str


class LessonCompleteIn(BaseModel):
    attempt_id: uuid.UUID
    active_seconds: int = Field(default=0, ge=0, le=4 * 3600)


class LessonCompleteOut(BaseModel):
    attempt_id: uuid.UUID
    score: float
    passed: bool
    exercises_answered: int
    next: Recommendation


# ----- Exercises -----
class EvaluateIn(BaseModel):
    answer: str = Field(max_length=500)
    input_mode: InputMode = "typed"
    used_hint: bool = False


class AttemptIn(EvaluateIn):
    lesson_attempt_id: uuid.UUID | None = None


class AttemptOut(BaseModel):
    attempt_id: uuid.UUID
    evaluation: EvaluationResult
    mastery_updates: list[dict[str, Any]]
    current_step: int | None


# ----- Assessment -----
class AssessmentItemOut(BaseModel):
    id: str
    skill: Skill
    difficulty: int
    type: str
    instructions: str
    prompt_ja: str | None = None
    prompt_en: str | None = None
    audio_text: str | None = None
    choices: list[str] = Field(default_factory=list)


class AssessmentStartIn(BaseModel):
    self_assessment: OnboardingAnswers | None = None


class AssessmentAnswerIn(BaseModel):
    item_id: str
    answer: str = Field(default="", max_length=500)
    input_mode: InputMode = "typed"
    skipped: bool = False


class AssessmentProgress(BaseModel):
    assessment_id: uuid.UUID
    status: str
    answered: int
    estimated_total: int
    next_item: AssessmentItemOut | None


class SkillEstimate(BaseModel):
    skill: Skill
    score: float
    confidence: float
    items: int


class PlacementResult(BaseModel):
    assessment_id: uuid.UUID
    recommended_level: str
    recommended_level_label: str
    recommended_unit_id: str
    skills: list[SkillEstimate]
    strengths: list[str]
    weak_areas: list[str]
    explanation: str
    completed_at: datetime | None
    disclaimer: str = "This is a short informal placement, not an official JLPT assessment."


# ----- Audio -----
class TTSIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    voice: str | None = None
    speed: float = Field(default=1.0, ge=0.5, le=1.5)


class TTSOut(BaseModel):
    provider: str
    audio_url: str | None
    cached: bool
    use_browser_fallback: bool
    message: str | None = None


class TranscriptionOut(BaseModel):
    provider: str
    text: str
    confidence: float | None
    is_mock: bool


# ----- Conversations -----
class ConversationCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    mode: Literal[
        "free_conversation", "guided_lesson", "mistake_clinic", "listening", "translation"
    ] = "free_conversation"


class TurnIn(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    input_mode: Literal["typed", "speech"] = "typed"


class TurnOut(ORM):
    id: uuid.UUID
    position: int
    role: str
    text: str
    input_mode: str | None
    content: dict[str, Any]
    created_at: datetime


class ConversationOut(ORM):
    id: uuid.UUID
    topic: str
    mode: str
    status: str
    turn_count: int
    provider: str
    summary: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None


class ConversationDetail(ConversationOut):
    turns: list[TurnOut]
    turns_total: int


class TurnResult(BaseModel):
    learner_turn: TurnOut
    tutor_turn: TurnOut
    is_mock: bool


class ExplainIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    kind: Literal["grammar", "vocabulary", "sentence"] = "sentence"


class RecapOut(BaseModel):
    conversation: ConversationOut
    recap: Recap
    is_mock: bool


# ----- Review -----
class ReviewCard(BaseModel):
    id: uuid.UUID
    concept_id: str
    concept_type: str
    state: str
    due_at: datetime
    from_mistake: bool
    front: str
    reading: str | None
    meaning: str
    detail: str | None
    audio_text: str | None


class ReviewQueueOut(BaseModel):
    due_count: int
    items: list[ReviewCard]


class ReviewSubmitIn(BaseModel):
    review_id: uuid.UUID
    grade: Literal["again", "hard", "good", "easy"]


class ReviewSubmitOut(BaseModel):
    review_id: uuid.UUID
    next_due_at: datetime
    interval_days: float
    state: str


# ----- Progress -----
class SkillProgress(BaseModel):
    skill: Skill
    accuracy: float | None
    attempts: int
    mastery: float | None
    placement_score: float | None


class ProgressSummary(BaseModel):
    lessons_completed: int
    lessons_total: int
    exercises_answered: int
    accuracy: float | None
    learning_minutes: int
    minutes_today: int
    daily_goal_minutes: int
    streak_days: int
    reviews_due: int
    reviews_completed: int
    current_level: str | None
    concepts_needing_practice: list[dict[str, Any]]
    recent_mistakes: list[dict[str, Any]]


class HistoryItem(BaseModel):
    kind: Literal["exercise", "lesson", "conversation", "review"]
    title: str
    detail: str | None
    is_correct: bool | None
    created_at: datetime


__all__ = ["Correction", "VocabNote"]
