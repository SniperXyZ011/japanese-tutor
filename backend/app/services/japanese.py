"""Text normalization helpers for comparing Japanese and English answers."""

import re
import unicodedata

_PUNCT = re.compile(r"[\s\u3000。、，,．.！!？?「」『』（）()\[\]【】・:：;；\"'“”‘’〜~ー\-]+")
_KEEP_CHOONPU = re.compile(r"[\s\u3000。、，,．.！!？?「」『』（）()\[\]【】・:：;；\"'“”‘’〜~\-]+")
_EN_PUNCT = re.compile(r"[^\w\s']+")
_EN_ARTICLES = re.compile(r"\b(a|an|the)\b")


def katakana_to_hiragana(text: str) -> str:
    return "".join(chr(ord(ch) - 0x60) if "\u30a1" <= ch <= "\u30f6" else ch for ch in text)


def normalize_japanese(text: str, kana_insensitive: bool = True) -> str:
    """NFKC, drop spaces and punctuation; optionally fold katakana into hiragana.

    The long-vowel mark ー is kept because it changes meaning (e.g. ビル vs ビール).
    """
    t = unicodedata.normalize("NFKC", text or "").strip().lower()
    t = _KEEP_CHOONPU.sub("", t)
    if kana_insensitive:
        t = katakana_to_hiragana(t)
    return t


def normalize_english(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower().strip()
    t = t.replace("’", "'")
    t = _EN_PUNCT.sub(" ", t)
    t = _EN_ARTICLES.sub(" ", t)
    return " ".join(t.split())


def normalize_romaji(text: str) -> str:
    t = normalize_english(text).replace(" ", "").replace("-", "")
    for long_, short in (("ō", "ou"), ("ū", "uu"), ("ā", "aa"), ("ē", "ee"), ("ī", "ii")):
        t = t.replace(long_, short)
    return t


def contains_japanese(text: str) -> bool:
    return any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in text or "")


def similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()
