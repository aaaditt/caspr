# caspr-flow

Hold a key, speak, release — polished text appears at your cursor, in any Windows app.

A personal Wispr Flow–style dictation tool: local Whisper for speech-to-text
(your audio never leaves the machine), a fast LLM pass for cleanup, and
clipboard-swap paste into whatever has focus.

## Status

Milestone 1 (core loop) — in progress. See
[docs/superpowers/specs/2026-07-15-caspr-flow-design.md](docs/superpowers/specs/2026-07-15-caspr-flow-design.md)
for the full design.

## Quick start

```powershell
uv sync
uv run caspr
```

Hold **right Ctrl** to talk; release to transcribe and paste.
