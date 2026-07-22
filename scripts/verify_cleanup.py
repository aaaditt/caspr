"""Live check for the AI cleanup / self-correction feature.

Run it after setting your Groq key (get one free at https://console.groq.com):

    PowerShell:  $env:GROQ_API_KEY="gsk_..."; uv run python scripts/verify_cleanup.py
    Git Bash:    GROQ_API_KEY="gsk_..." uv run python scripts/verify_cleanup.py

It sends a few dictation-style transcripts through the real Groq pass and prints
the cleaned result, so you can see the self-correction ("5:30 -> actually 6:30")
and filler removal working end to end. No mic or GUI needed.
"""

import os

from caspr.cleanup import clean_text
from caspr.config import Config

EXAMPLES = [
    "hey there let's meet tomorrow at 5 30 or actually never mind let's meet at 6 30",
    "um so I think we should uh ship the feature on friday you know",
    "send it to john no wait send it to sarah instead",
]


def main() -> None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise SystemExit("Set GROQ_API_KEY first (see the docstring at the top).")
    cfg = Config(groq_api_key=key)  # defaults: enabled, llama-3.1-8b-instant
    print(f"model: {cfg.groq_model}\n")
    for raw in EXAMPLES:
        cleaned = clean_text(raw, recent=[], glossary=[], tone="balanced", cfg=cfg)
        print(f"raw    : {raw}")
        print(f"cleaned: {cleaned}\n")


if __name__ == "__main__":
    main()
