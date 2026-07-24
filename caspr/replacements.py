"""Learned corrections: whole-word, case-insensitive; replacement text verbatim."""

from __future__ import annotations

import re


def apply_replacements(text: str, rules: dict[str, str]) -> str:
    """Apply all replacement rules to *text*, returning the corrected string."""
    for wrong, right in rules.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.IGNORECASE)
    return text


def apply_replacements_counted(text: str, rules: dict[str, str]) -> tuple[str, int]:
    """Like :func:`apply_replacements` but also returns the total substitution count."""
    total = 0
    for wrong, right in rules.items():
        text, n = re.subn(rf"\b{re.escape(wrong)}\b", right, text, flags=re.IGNORECASE)
        total += n
    return text, total
