from datetime import UTC, datetime, timedelta

from app.services import assessment as engine
from app.services.srs import grade_from_result, schedule_next, update_mastery

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_new_item_again_relearns_in_minutes():
    s = schedule_next(grade="again", now=NOW, state="new", interval_days=0, ease=2.5, repetitions=0, lapses=0)
    assert s.due_at - NOW <= timedelta(minutes=10)


def test_intervals_grow_with_good():
    s = schedule_next(grade="good", now=NOW, state="new", interval_days=0, ease=2.5, repetitions=0, lapses=0)
    s2 = schedule_next(grade="good", now=NOW, state=s.state, interval_days=s.interval_days, ease=s.ease,
                       repetitions=s.repetitions, lapses=s.lapses)
    assert s2.interval_days > s.interval_days


def test_lapse_resets_and_lowers_ease():
    s = schedule_next(grade="again", now=NOW, state="review", interval_days=10, ease=2.5, repetitions=4, lapses=0)
    assert s.lapses == 1 and s.ease < 2.5 and s.interval_days < 10


def test_ease_bounds():
    s = schedule_next(grade="again", now=NOW, state="review", interval_days=1, ease=1.3, repetitions=1, lapses=5)
    assert s.ease >= 1.3


def test_grade_mapping():
    assert grade_from_result(False, 0.0, False) == "again"
    assert grade_from_result(True, 1.0, True) in ("hard", "good")


def test_single_mistake_does_not_erase_mastery():
    r = update_mastery(mastery=0.8, attempts=10, recent_failures=0, is_correct=False, used_hint=False,
                       evaluation_confidence=1.0)
    assert 0.5 < r.mastery < 0.8


def test_hint_reduces_gain():
    a = update_mastery(mastery=0.2, attempts=1, recent_failures=0, is_correct=True, used_hint=False, evaluation_confidence=1)
    b = update_mastery(mastery=0.2, attempts=1, recent_failures=0, is_correct=True, used_hint=True, evaluation_confidence=1)
    assert a.mastery > b.mastery


def _run(correct_fn, sa=None):
    st = engine.initial_state(sa or {})
    n = 0
    while st["current_item_id"]:
        item = engine.item_bank()[st["current_item_id"]]
        st = engine.record_answer(st, item["id"], correct_fn(item))
        n += 1
    return engine.placement(st), n


def test_all_wrong_places_absolute_beginner_quickly():
    p, n = _run(lambda i: False)
    assert p["level"] == "absolute_beginner" and n <= 12


def test_all_right_places_high():
    p, n = _run(lambda i: True)
    assert p["level"] == "n5_plus" and n <= 18


def test_reads_kana_but_weak_grammar_is_beginner():
    p, _ = _run(lambda i: i["skill"] in ("reading", "listening") or i["difficulty"] == 1)
    assert p["level"] in ("beginner", "n5")


def test_self_assessment_changes_start_difficulty():
    st = engine.initial_state({"hiragana": "fluent", "kanji": "n5"})
    assert engine.item_bank()[st["current_item_id"]]["difficulty"] >= 2


def test_choices_are_shuffled_somewhere():
    import json
    from pathlib import Path
    raw = json.loads((Path(engine.__file__).parents[1] / "content" / "assessment.json").read_text())["items"]
    shuffled = engine.item_bank()
    moved = [i["id"] for i in raw if i.get("choices") and shuffled[i["id"]]["choices"][0] != i["choices"][0]]
    assert moved
