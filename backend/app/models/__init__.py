import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid, utcnow


class LocalUser(TimestampMixin, Base):
    """Credentials for AUTH_MODE=local (development/self-hosted only)."""

    __tablename__ = "local_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(80))
    onboarding: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_level: Mapped[str | None] = mapped_column(String(40))
    start_unit_id: Mapped[str | None] = mapped_column(String(40))
    explanation_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    daily_goal_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    playback_speed: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    show_furigana: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_romaji: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    voice_name: Mapped[str | None] = mapped_column(String(120))
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_active_date: Mapped[date | None] = mapped_column(Date)


class CurriculumUnit(TimestampMixin, Base):
    __tablename__ = "curriculum_units"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    level: Mapped[str] = mapped_column(String(20), default="N5", nullable=False)

    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="unit", order_by="Lesson.position", cascade="all, delete-orphan"
    )


class Lesson(TimestampMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("unit_id", "position"),)

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    unit_id: Mapped[str] = mapped_column(
        ForeignKey("curriculum_units.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    objectives: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    prerequisites: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    vocabulary_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    grammar_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    pass_score: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    content_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    unit: Mapped[CurriculumUnit] = relationship(back_populates="lessons")
    exercises: Mapped[list["Exercise"]] = relationship(
        back_populates="lesson", order_by="Exercise.position", cascade="all, delete-orphan"
    )


class Exercise(TimestampMixin, Base):
    __tablename__ = "exercises"
    __table_args__ = (UniqueConstraint("lesson_id", "position"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    skill: Mapped[str] = mapped_column(String(20), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_ja: Mapped[str | None] = mapped_column(Text)
    prompt_reading: Mapped[str | None] = mapped_column(Text)
    prompt_romaji: Mapped[str | None] = mapped_column(Text)
    prompt_en: Mapped[str | None] = mapped_column(Text)
    audio_text: Mapped[str | None] = mapped_column(Text)
    choices: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    accepted_answers: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    hints: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    concept_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    lesson: Mapped[Lesson] = relationship(back_populates="exercises")


class Vocabulary(TimestampMixin, Base):
    __tablename__ = "vocabulary"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    japanese: Mapped[str] = mapped_column(String(80), nullable=False)
    reading: Mapped[str] = mapped_column(String(80), nullable=False)
    romaji: Mapped[str] = mapped_column(String(80), nullable=False)
    meaning: Mapped[str] = mapped_column(String(200), nullable=False)
    part_of_speech: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    jlpt_level: Mapped[str] = mapped_column(String(10), default="N5", nullable=False)
    example_ja: Mapped[str | None] = mapped_column(Text)
    example_en: Mapped[str | None] = mapped_column(Text)


class GrammarConcept(TimestampMixin, Base):
    __tablename__ = "grammar_concepts"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    pattern: Mapped[str] = mapped_column(String(120), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    jlpt_level: Mapped[str] = mapped_column(String(10), default="N5", nullable=False)
    examples: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list, nullable=False)


class UserAssessment(TimestampMixin, Base):
    __tablename__ = "user_assessments"
    __table_args__ = (Index("ix_user_assessments_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    self_assessment: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    recommended_level: Mapped[str | None] = mapped_column(String(40))
    recommended_unit_id: Mapped[str | None] = mapped_column(String(40))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    responses: Mapped[list["AssessmentResponse"]] = relationship(
        back_populates="assessment",
        order_by="AssessmentResponse.created_at",
        cascade="all, delete-orphan",
    )


class AssessmentResponse(Base):
    __tablename__ = "assessment_responses"
    __table_args__ = (UniqueConstraint("assessment_id", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    item_id: Mapped[str] = mapped_column(String(60), nullable=False)
    skill: Mapped[str] = mapped_column(String(20), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    input_mode: Mapped[str] = mapped_column(String(20), default="typed", nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluator: Mapped[str] = mapped_column(String(20), default="deterministic", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    assessment: Mapped[UserAssessment] = relationship(back_populates="responses")


class UserMastery(TimestampMixin, Base):
    __tablename__ = "user_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "concept_id", "skill"),
        Index("ix_user_mastery_user_score", "user_id", "mastery"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[str] = mapped_column(String(80), nullable=False)
    concept_type: Mapped[str] = mapped_column(String(20), nullable=False)
    skill: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    independent_successes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hint_uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recent_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewItem(TimestampMixin, Base):
    __tablename__ = "review_queue"
    __table_args__ = (
        UniqueConstraint("user_id", "concept_id"),
        Index("ix_review_queue_user_due", "user_id", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[str] = mapped_column(String(80), nullable=False)
    concept_type: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="learning", nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ease: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lapses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_grade: Mapped[str | None] = mapped_column(String(10))
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    from_mistake: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class LessonAttempt(TimestampMixin, Base):
    __tablename__ = "lesson_attempts"
    __table_args__ = (Index("ix_lesson_attempts_user_lesson", "user_id", "lesson_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"
    __table_args__ = (Index("ix_exercise_attempts_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id: Mapped[str] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True, nullable=False
    )
    lesson_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lesson_attempts.id", ondelete="SET NULL"), index=True
    )
    skill: Mapped[str] = mapped_column(String(20), nullable=False)
    input_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    used_hint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evaluator: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    feedback: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ConversationSession(TimestampMixin, Base):
    __tablename__ = "conversation_sessions"
    __table_args__ = (Index("ix_conversation_sessions_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(30), default="free_conversation", nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    turns: Mapped[list["ConversationTurn"]] = relationship(
        back_populates="session",
        order_by="ConversationTurn.position",
        cascade="all, delete-orphan",
    )


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    __table_args__ = (UniqueConstraint("session_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str | None] = mapped_column(String(20))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    session: Mapped[ConversationSession] = relationship(back_populates="turns")


class AudioAsset(TimestampMixin, Base):
    __tablename__ = "audio_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    voice: Mapped[str | None] = mapped_column(String(120))
    speed: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(300), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)


class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"
    __table_args__ = (Index("ix_api_usage_logs_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(60))
    request_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
