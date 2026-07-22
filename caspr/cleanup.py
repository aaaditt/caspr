"""AI cleanup stage: a fast Groq pass that turns raw dictation into polished text.

Two responsibilities, split for testability:
- ``build_cleanup_messages`` — pure prompt assembly (no network).
- ``clean_text`` — orchestrates the call with a hard never-lose-words guarantee:
  on *any* failure (disabled, no key, timeout, exception, empty reply) it returns
  the raw transcript unchanged, so a dictation is never dropped by cleanup.

Privacy: only transcript text, the last-N dictations, and the glossary are sent;
audio never leaves the machine, and ``cleanup_enabled=False`` skips the cloud entirely.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence

log = logging.getLogger(__name__)

_INTRO = (
    "You clean up dictated speech into polished written text. Fix capitalization, "
    "spacing and punctuation, and remove filler words (um, uh, er, like, you know). "
)
# Included only when smart-correct is on: reframe spoken self-corrections.
_SELF_CORRECT = (
    "When the speaker corrects themselves — retracts or changes a value, name, "
    "time, or phrase, signalled by cues like 'actually', 'no wait', 'I mean', "
    "'sorry', 'scratch that', or 'never mind' — keep ONLY their final intended "
    "version and delete both the retracted words and the correction cue. "
)
# Included instead when smart-correct is off: keep everything the speaker said.
_PRESERVE = (
    "Preserve every stated value, name, and phrase exactly as spoken; do not remove, "
    "reorder, or drop content even if the speaker seems to change their mind. "
)
_OUTRO = (
    "Never add facts, never answer questions, never explain — only rewrite what was "
    "said. Preserve the speaker's meaning and language. Match the requested tone and "
    "prefer the glossary spellings. Output only the cleaned text, nothing else."
)


def _system_prompt(smart_correct: bool) -> str:
    return _INTRO + (_SELF_CORRECT if smart_correct else _PRESERVE) + _OUTRO


def build_cleanup_messages(
    raw: str,
    *,
    recent: Sequence[str],
    glossary: Iterable[str],
    tone: str,
    smart_correct: bool = True,
) -> list[dict[str, str]]:
    """Assemble the system+user messages for the cleanup call.

    ``smart_correct`` toggles the self-correction (retraction) behaviour; when
    off, the prompt still cleans fillers/punctuation but preserves every value.
    """
    parts: list[str] = [f"Tone: {tone}"]

    terms = [t.strip() for t in glossary if t and t.strip()]
    if terms:
        parts.append("Glossary (preferred spellings): " + ", ".join(terms))

    context = [line.strip() for line in recent if line and line.strip()]
    if context:
        joined = "\n".join(f"- {line}" for line in context)
        parts.append("Recent dictations, for style/name consistency only:\n" + joined)

    parts.append("Transcript to clean:\n" + raw)
    return [
        {"role": "system", "content": _system_prompt(smart_correct)},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def clean_text(
    raw: str,
    *,
    recent: Sequence[str],
    glossary: Iterable[str],
    tone: str,
    cfg,
    complete: Callable[[list[dict[str, str]], object], str] | None = None,
) -> str:
    """Return a cleaned version of ``raw``, or ``raw`` unchanged on any failure.

    ``complete`` performs the actual model call ``(messages, cfg) -> str``; it is
    injected in tests and defaults to the Groq client.
    """
    if not cfg.cleanup_enabled or not cfg.groq_api_key.strip() or not raw.strip():
        return raw

    recent = list(recent)[: cfg.cleanup_context_count]
    messages = build_cleanup_messages(
        raw, recent=recent, glossary=glossary, tone=tone, smart_correct=cfg.smart_correct
    )
    complete = complete or _groq_complete
    try:
        cleaned = complete(messages, cfg)
    except Exception:
        log.warning("cleanup call failed; falling back to raw text", exc_info=True)
        return raw
    cleaned = (cleaned or "").strip()
    return cleaned or raw


def _groq_complete(messages: list[dict[str, str]], cfg) -> str:
    """Real Groq call. Imported lazily so the app runs without the SDK/key."""
    from groq import Groq

    client = Groq(api_key=cfg.groq_api_key, timeout=cfg.cleanup_timeout_s, max_retries=0)
    resp = client.chat.completions.create(
        model=cfg.groq_model,
        messages=messages,
        temperature=0,
        max_tokens=1024,
    )
    return resp.choices[0].message.content or ""
