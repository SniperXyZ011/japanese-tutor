import asyncio
import uuid

from app.services.evaluation import TRANSCRIPT_NOTE, ExerciseSpec, evaluate, evaluate_deterministic


def spec(**kw):
    base = {"type": "typed_japanese", "answer": "こんにちは"}
    base.update(kw)
    return ExerciseSpec(**base)


def test_multiple_choice():
    s = spec(type="multiple_choice", answer="a", choices=["a", "b"])
    assert evaluate_deterministic(s, "a", "choice").is_correct
    r = evaluate_deterministic(s, "b", "choice")
    assert not r.is_correct and r.verdict == "incorrect"


def test_typed_japanese_exact_and_punctuation():
    assert evaluate_deterministic(spec(), "こんにちは。", "typed").is_correct


def test_accepted_alternative():
    s = spec(answer="わたしはがくせいです", accepted_answers=["がくせいです"])
    r = evaluate_deterministic(s, "がくせいです", "typed")
    assert r.is_correct and r.accepted_alternative


def test_kana_insensitive_by_default_and_strict_when_flagged():
    assert evaluate_deterministic(spec(answer="コーヒー"), "こーひー", "typed").is_correct
    strict = evaluate_deterministic(spec(answer="コーヒー", meta={"kana_strict": True}), "こーひー", "typed")
    assert strict is None or not strict.is_correct


def test_near_miss_is_almost_or_ai():
    r = evaluate_deterministic(spec(answer="ありがとうございます"), "ありがとございます", "typed")
    assert r is None or r.verdict in ("almost", "incorrect")


def test_speech_has_transcript_note():
    r = evaluate_deterministic(spec(type="speaking"), "こんにちは", "speech")
    assert r.is_correct and r.transcript_note == TRANSCRIPT_NOTE


def test_required_substrings_speaking():
    s = spec(type="speaking", answer="すしがすきです", meta={"required_substrings": ["すき"]})
    assert evaluate_deterministic(s, "ラーメンがすきです", "speech").is_correct
    assert not evaluate_deterministic(s, "ラーメンです", "speech").is_correct


def test_sentence_ordering():
    s = spec(type="sentence_ordering", answer="わたしはがくせいです", choices=["わたしは", "がくせい", "です"])
    assert evaluate_deterministic(s, "わたしはがくせいです", "typed").is_correct
    assert not evaluate_deterministic(s, "がくせいわたしはです", "typed").is_correct


def test_english_translation_alternatives():
    s = ExerciseSpec(type="ja_to_en", answer="Good morning", accepted_answers=["morning"])
    assert evaluate_deterministic(s, "good morning!", "typed").is_correct


def test_open_answer_without_ai_is_unverified_not_correct():
    s = spec(type="en_to_ja", answer="わたしはがくせいです")
    r = asyncio.run(evaluate(s, "まったくちがうぶん", input_mode="typed", user_id=uuid.uuid4(), ai=None))
    assert not r.is_correct
    assert r.verdict in ("incorrect", "unverified")
