"""Personal dictionary → Whisper initial_prompt.

Whisper biases decoding toward vocabulary present in initial_prompt, which is how
custom terms ("caspr", names, jargon) survive transcription. The prompt window is
~224 tokens, so terms are capped by a character budget; earlier terms win.
"""

from __future__ import annotations

from collections.abc import Iterable

MAX_PROMPT_CHARS = 500
_PREFIX = "Glossary: "


def build_initial_prompt(terms: Iterable[str]) -> str | None:
    seen: set[str] = set()
    cleaned: list[str] = []
    for term in terms:
        term = term.strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            cleaned.append(term)
    if not cleaned:
        return None

    kept: list[str] = []
    length = len(_PREFIX)
    for term in cleaned:
        extra = len(term) + (2 if kept else 0)  # ", " separator
        if length + extra > MAX_PROMPT_CHARS:
            break
        kept.append(term)
        length += extra
    return _PREFIX + ", ".join(kept)
