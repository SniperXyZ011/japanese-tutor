from app.services.japanese import (
    contains_japanese,
    katakana_to_hiragana,
    normalize_english,
    normalize_japanese,
)


def test_punctuation_and_spacing_removed():
    assert normalize_japanese(" こんにちは。 ") == normalize_japanese("こんにちは")
    assert normalize_japanese("お元気ですか？") == normalize_japanese("お元気ですか")


def test_kana_folding_keeps_long_vowel():
    assert katakana_to_hiragana("コーヒー") == "こーひー"
    assert normalize_japanese("コーヒー") == normalize_japanese("こーひー")
    assert normalize_japanese("コーヒー", False) != normalize_japanese("こーひー", False)


def test_full_width_ascii():
    assert normalize_japanese("ＡＢＣ") == normalize_japanese("abc")


def test_english_normalization():
    assert normalize_english("  Good Morning! ") == normalize_english("good morning")


def test_contains_japanese():
    assert contains_japanese("ねこ")
    assert not contains_japanese("neko")
