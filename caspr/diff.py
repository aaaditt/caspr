"""Word-level diff between what's already typed and a new target hypothesis.

Used both for live corrections while a streaming ASR hypothesis firms up, and
for the one release-time reconciliation against the accurate batch model's
final text. Diffs at word granularity (never mid-word) so a word already on
screen is never half-corrected while it's still being recognized.
"""

from __future__ import annotations


def compute_correction(typed: str, target: str) -> tuple[int, str]:
    """Returns (backspace_count, text_to_type) to turn `typed` into `target`.

    Finds the longest common leading run of whole words, backspaces whatever
    of `typed` comes after that run, then types whatever of `target` comes
    after it. `backspace_count` is always <= len(typed) by construction (it
    is exactly the length of a suffix of `typed`).
    """
    typed_words = typed.split(" ") if typed else []
    target_words = target.split(" ") if target else []
    common = 0
    while (
        common < len(typed_words)
        and common < len(target_words)
        and typed_words[common] == target_words[common]
    ):
        common += 1
    kept = " ".join(typed_words[:common])
    backspace_count = len(typed) - len(kept)
    remainder = target_words[common:]
    if not remainder:
        return backspace_count, ""
    insert = " ".join(remainder)
    if kept:
        insert = " " + insert
    return backspace_count, insert
