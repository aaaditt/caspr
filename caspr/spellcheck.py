"""Flag words likely misrecognized or unknown: rare per wordfreq and not in the
personal dictionary. Rarity beats a strict wordlist for names ("adit" is a real
but rare word — a mine entrance — and should still be flagged).

Requires the optional ``spellcheck`` extra (``uv sync --extra spellcheck``).
Without it, this module silently returns no flagged spans.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

try:
    from wordfreq import zipf_frequency
except ImportError:  # optional dep not installed
    zipf_frequency = None  # type: ignore[assignment]

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

# Words with a Zipf frequency below this value are considered rare / unknown.
DEFAULT_ZIPF_THRESHOLD: float = 3.0


def flag_unknown_words(
    text: str, personal_terms: Iterable[str], threshold: float = DEFAULT_ZIPF_THRESHOLD
) -> list[tuple[int, int]]:
    if zipf_frequency is None:  # 'spellcheck' extra not installed
        return []
    known = {t.strip().lower() for t in personal_terms}
    spans: list[tuple[int, int]] = []
    for m in _WORD_RE.finditer(text):
        word = m.group().lower()
        if word in known:
            continue
        if zipf_frequency(word, "en") < threshold:
            spans.append((m.start(), m.end()))
    return spans


def is_known_word(word: str, personal_terms: Iterable[str], threshold: float = DEFAULT_ZIPF_THRESHOLD) -> bool:
    """Return True if *word* is common enough or listed in *personal_terms*."""
    if zipf_frequency is None:
        return True  # can't tell — assume fine
    if word.strip().lower() in {t.strip().lower() for t in personal_terms}:
        return True
    return zipf_frequency(word, "en") >= threshold
