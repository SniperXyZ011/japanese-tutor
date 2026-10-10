"""Adaptive placement assessment: a per-skill staircase over a small curated item bank."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.seed import load_assessment_items

SKILL_ORDER = ["reading", "vocabulary", "grammar", "listening", "writing", "speaking"]
MAX_ITEMS_PER_SKILL = 3
MAX_DIFFICULTY = 4
SKILL_WEIGHTS = {
    "reading": 0.2,
    "vocabulary": 0.2,
    "grammar": 0.25,
    "listening": 0.15,
    "writing": 0.1,
    "speaking": 0.1,
}
LEVELS = {
    "absolute_beginner": ("Absolute beginner (pre-N5)", "unit-0"),
    "beginner": ("Beginner (early N5)", "unit-1"),
    "n5": ("Upper beginner (N5 range)", "unit-3"),
    "n5_plus": ("Late beginner (N5 and above)", "unit-4"),
}
LEVEL_UNITS = {k: v[1] for k, v in LEVELS.items()}


@lru_cache
def item_bank() -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in load_assessment_items()}


def _start_difficulty(skill: str, sa: dict[str, Any]) -> int:
    def pick(value: str | None, table: dict[str, int]) -> int:
        return table.get(value or "", 1)

    vocab_grammar = pick(sa.get("vocab_grammar"), {"none": 1, "basic": 1, "n5": 2, "n4_plus": 3})
    reading = max(
        pick(sa.get("hiragana"), {"none": 1, "some": 1, "fluent": 2}),
        pick(sa.get("kanji"), {"none": 1, "few": 2, "n5": 3, "n4_plus": 3}),
    )
    if skill == "reading":
        return reading
    if skill in ("vocabulary", "grammar"):
        return vocab_grammar
    if skill == "listening":
        return pick(
            sa.get("listening"),
            {"none": 1, "basic_phrases": 1, "slow_conversation": 2, "everyday": 3},
        )
    if skill == "writing":
        return min(reading, vocab_grammar)
    if skill == "speaking":
        return pick(sa.get("speaking_confidence"), {"none": 1, "low": 1, "medium": 2, "high": 3})
    return 1


def initial_state(self_assessment: dict[str, Any]) -> dict[str, Any]:
    state = {
        "skill_index": 0,
        "skills": {
            s: {
                "difficulty": _start_difficulty(s, self_assessment),
                "answered": [],
                "results": [],
                "consecutive_wrong": 0,
                "done": False,
            }
            for s in SKILL_ORDER
        },
        "current_item_id": None,
    }
    state["current_item_id"] = _choose_item(state)
    return state


def _available_difficulties(skill: str) -> list[int]:
    return sorted({i["difficulty"] for i in item_bank().values() if i["skill"] == skill})


def _choose_item(state: dict[str, Any]) -> str | None:
    while state["skill_index"] < len(SKILL_ORDER):
        skill = SKILL_ORDER[state["skill_index"]]
        s = state["skills"][skill]
        if not s["done"]:
            candidates = [
                i
                for i in item_bank().values()
                if i["skill"] == skill and i["id"] not in s["answered"]
            ]
            if candidates:
                target = s["difficulty"]
                candidates.sort(key=lambda i: (abs(i["difficulty"] - target), i["id"]))
                return candidates[0]["id"]
            s["done"] = True
        state["skill_index"] += 1
    return None


def record_answer(state: dict[str, Any], item_id: str, correct: bool) -> dict[str, Any]:
    item = item_bank()[item_id]
    skill = item["skill"]
    s = state["skills"][skill]
    s["answered"].append(item_id)
    s["results"].append({"difficulty": item["difficulty"], "correct": correct})
    levels = _available_difficulties(skill)
    top = max(levels) if levels else MAX_DIFFICULTY
    if correct:
        s["consecutive_wrong"] = 0
        if item["difficulty"] >= top:
            s["done"] = True
        s["difficulty"] = min(top, item["difficulty"] + 1)
    else:
        s["consecutive_wrong"] += 1
        if item["difficulty"] <= 1 or s["consecutive_wrong"] >= 2:
            s["done"] = True
        s["difficulty"] = max(1, item["difficulty"] - 1)
    if len(s["answered"]) >= MAX_ITEMS_PER_SKILL:
        s["done"] = True
    state["current_item_id"] = _choose_item(state)
    return state


def estimated_remaining(state: dict[str, Any]) -> int:
    remaining = 0
    for skill in SKILL_ORDER:
        s = state["skills"][skill]
        if not s["done"]:
            remaining += max(1, MAX_ITEMS_PER_SKILL - len(s["answered"]) - 1)
    return remaining


@dataclass
class SkillScore:
    skill: str
    ability: float
    score: float
    confidence: float
    items: int


def score_skill(skill: str, results: list[dict[str, Any]]) -> SkillScore:
    ability = 0.0
    inconsistent = False
    for r in results:
        d = r["difficulty"]
        if r["correct"]:
            if any(not p["correct"] and p["difficulty"] < d for p in results):
                inconsistent = True
            ability = max(ability, float(d))
        elif ability >= d:
            ability = d - 0.5
    n = len(results)
    confidence = 0.0 if n == 0 else min(0.85, 0.25 + 0.2 * n) - (0.2 if inconsistent else 0.0)
    return SkillScore(
        skill=skill,
        ability=max(0.0, ability),
        score=round(max(0.0, ability) / MAX_DIFFICULTY, 3),
        confidence=round(max(0.1, confidence) if n else 0.0, 2),
        items=n,
    )


def placement(state: dict[str, Any]) -> dict[str, Any]:
    scores = {s: score_skill(s, state["skills"][s]["results"]) for s in SKILL_ORDER}
    reading = scores["reading"].ability
    core = (scores["grammar"].ability + scores["vocabulary"].ability) / 2
    if reading <= 1:
        level = "absolute_beginner"
    elif core < 2:
        level = "beginner"
    elif core < 3:
        level = "n5"
    else:
        level = "n5_plus"
    label, unit = LEVELS[level]
    strengths = [s for s, sc in scores.items() if sc.items and sc.score >= 0.6]
    weak = [s for s, sc in scores.items() if sc.items and sc.score <= 0.35]
    overall = sum(scores[s].score * w for s, w in SKILL_WEIGHTS.items())
    if level == "absolute_beginner":
        why = "Reading kana is the foundation for everything else, so we'll start with hiragana, katakana and greetings."
    else:
        why = f"You can read kana, and your grammar/vocabulary results suggest starting at {label.lower()}."
    if weak:
        why += " We'll give extra practice in: " + ", ".join(weak) + "."
    return {
        "level": level,
        "label": label,
        "unit_id": unit,
        "overall": round(overall, 3),
        "skills": {
            s: {"score": sc.score, "confidence": sc.confidence, "items": sc.items}
            for s, sc in scores.items()
        },
        "strengths": strengths,
        "weak_areas": weak,
        "explanation": why,
    }
