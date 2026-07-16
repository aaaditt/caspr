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
uv sync --extra cuda
uv run caspr --install-launcher   # once: puts 'caspr' on PATH
caspr                             # launches detached (tray dot appears)
caspr --startup on                # optional: always running after login
```

Hold **right Ctrl** to talk; release to type into the focused app. After each
dictation a pill lingers at the bottom of the screen — click it to correct
words, right-click a red word to add it to your dictionary or create an
"always replace" rule. Tray → History & dictionary reviews everything.

`uv run caspr` runs attached to the terminal with console logs (dev mode).
