"""Learned corrections: whole-word, case-insensitive; replacement text verbatim."""

from __future__ import annotations

import re


def apply_replacements(text: str, rules: dict[str, str]) -> str:
    for wrong, right in rules.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.IGNORECASE)
    return text
