"""Flag words likely misrecognized or unknown: rare per wordfreq and not in the
personal dictionary. Rarity beats a strict wordlist for names ("adit" is a real
but rare word — a mine entrance — and should still be flagged)."""

from __future__ import annotations

import re
from collections.abc import Iterable

from wordfreq import zipf_frequency

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def flag_unknown_words(
    text: str, personal_terms: Iterable[str], threshold: float = 3.0
) -> list[tuple[int, int]]:
    known = {t.strip().lower() for t in personal_terms}
    spans: list[tuple[int, int]] = []
    for m in _WORD_RE.finditer(text):
        word = m.group().lower()
        if word in known:
            continue
        if zipf_frequency(word, "en") < threshold:
            spans.append((m.start(), m.end()))
    return spans
