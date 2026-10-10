"""Load version-controlled curriculum content into the database (idempotent).

Usage: python -m app.seed
"""

import json
import logging
import random
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import CurriculumUnit, Exercise, GrammarConcept, Lesson, Vocabulary

CONTENT_DIR = Path(__file__).parent / "content"
EXERCISE_TYPES = {
    "presentation",
    "multiple_choice",
    "listening_choice",
    "ja_to_en",
    "en_to_ja",
    "typed_japanese",
    "sentence_completion",
    "sentence_ordering",
    "speaking",
}
SKILLS = {"listening", "speaking", "vocabulary", "grammar", "reading", "writing"}
logger = logging.getLogger("app.seed")


class ExerciseIn(BaseModel):
    type: str
    skill: str
    instructions: str
    prompt_ja: str | None = None
    prompt_reading: str | None = None
    prompt_romaji: str | None = None
    prompt_en: str | None = None
    audio_text: str | None = None
    choices: list[str] = Field(default_factory=list)
    answer: str | None = None
    accepted_answers: list[str] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    explanation: str = ""
    concept_ids: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> "ExerciseIn":
        if self.type not in EXERCISE_TYPES:
            raise ValueError(f"unknown exercise type {self.type}")
        if self.skill not in SKILLS:
            raise ValueError(f"unknown skill {self.skill}")
        if self.type != "presentation" and not self.answer:
            raise ValueError(f"{self.type} exercise requires an answer: {self.instructions}")
        if self.type in {"multiple_choice", "listening_choice"} and self.answer not in self.choices:
            raise ValueError(f"answer must be one of the choices: {self.instructions}")
        if self.type == "listening_choice" and not self.audio_text:
            raise ValueError("listening exercises need audio_text")
        if self.type == "sentence_ordering":
            if sorted("".join(self.choices)) != sorted((self.answer or "").replace(" ", "")):
                raise ValueError(f"ordering answer must use exactly the choices: {self.answer}")
        return self


class LessonIn(BaseModel):
    id: str
    position: int
    title: str
    summary: str = ""
    objectives: list[str]
    prerequisites: list[str] = Field(default_factory=list)
    difficulty: int = 1
    estimated_minutes: int = 10
    vocabulary_ids: list[str] = Field(default_factory=list)
    grammar_ids: list[str] = Field(default_factory=list)
    pass_score: float = 0.7
    exercises: list[ExerciseIn] = Field(min_length=1)


class UnitFile(BaseModel):
    unit: dict[str, Any]
    vocabulary: list[dict[str, Any]] = Field(default_factory=list)
    grammar: list[dict[str, Any]] = Field(default_factory=list)
    lessons: list[LessonIn]


def load_content(content_dir: Path = CONTENT_DIR) -> list[UnitFile]:
    files = sorted(
        (content_dir / "units").glob("unit-*.json"), key=lambda p: int(p.stem.split("-")[1])
    )
    units = [UnitFile.model_validate(json.loads(p.read_text(encoding="utf-8"))) for p in files]
    validate_references(units)
    return units


def validate_references(units: list[UnitFile]) -> None:
    vocab = {v["id"] for u in units for v in u.vocabulary}
    grammar = {g["id"] for u in units for g in u.grammar}
    lessons = {lesson.id for u in units for lesson in u.lessons}
    concepts = vocab | grammar
    errors: list[str] = []
    for u in units:
        for lesson in u.lessons:
            errors += [
                f"{lesson.id}: unknown prerequisite {p}"
                for p in lesson.prerequisites
                if p not in lessons
            ]
            errors += [
                f"{lesson.id}: unknown vocab {v}" for v in lesson.vocabulary_ids if v not in vocab
            ]
            errors += [
                f"{lesson.id}: unknown grammar {g}" for g in lesson.grammar_ids if g not in grammar
            ]
            for ex in lesson.exercises:
                errors += [
                    f"{lesson.id}: unknown concept {c}" for c in ex.concept_ids if c not in concepts
                ]
    if errors:
        raise ValueError("Invalid curriculum content:\n" + "\n".join(errors))


def shuffled_choices(seed_key: str, ex_type: str, choices: list[str]) -> list[str]:
    """Deterministically shuffle authored choices so the answer isn't always first."""
    if ex_type not in {"multiple_choice", "listening_choice"}:
        return list(choices)
    out = list(choices)
    random.Random(seed_key).shuffle(out)
    return out


def load_assessment_items(content_dir: Path = CONTENT_DIR) -> list[dict[str, Any]]:
    items = json.loads((content_dir / "assessment.json").read_text(encoding="utf-8"))["items"]
    for item in items:
        item["choices"] = shuffled_choices(item["id"], item["type"], item.get("choices", []))
    return items


def seed(db: Session, content_dir: Path = CONTENT_DIR) -> dict[str, int]:
    units = load_content(content_dir)
    counts = {"units": 0, "lessons": 0, "exercises": 0, "vocabulary": 0, "grammar": 0}
    for uf in units:
        for v in uf.vocabulary:
            db.merge(Vocabulary(**v))
            counts["vocabulary"] += 1
        for g in uf.grammar:
            db.merge(GrammarConcept(**g))
            counts["grammar"] += 1
        db.merge(CurriculumUnit(**uf.unit))
        counts["units"] += 1
    db.flush()
    for uf in units:
        for lesson in uf.lessons:
            data = lesson.model_dump(exclude={"exercises"})
            db.merge(Lesson(unit_id=uf.unit["id"], **data))
            db.flush()
            keep: list[str] = []
            for pos, ex in enumerate(lesson.exercises, start=1):
                ex_id = f"{lesson.id}-e{pos:02d}"
                keep.append(ex_id)
                data = ex.model_dump()
                data["choices"] = shuffled_choices(ex_id, ex.type, ex.choices)
                db.merge(Exercise(id=ex_id, lesson_id=lesson.id, position=pos, **data))
                counts["exercises"] += 1
            db.execute(
                delete(Exercise).where(Exercise.lesson_id == lesson.id, Exercise.id.not_in(keep))
            )
            counts["lessons"] += 1
    db.commit()
    return counts


def main() -> None:
    from app.db.session import SessionLocal

    logging.basicConfig(level="INFO")
    with SessionLocal() as db:
        counts = seed(db)
        total = db.scalar(select(Lesson).limit(1))
        print(f"Seeded: {counts} (lessons present: {total is not None})")


if __name__ == "__main__":
    main()
