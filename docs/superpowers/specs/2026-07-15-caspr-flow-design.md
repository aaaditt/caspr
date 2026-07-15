# caspr-flow — Design

**Date:** 2026-07-15
**Status:** Approved (brainstormed and reviewed section-by-section with Aadit)

## What

A personal, daily-driver voice dictation app for Windows in the style of Wispr Flow:
hold a hotkey anywhere, speak, release — polished text appears at the cursor.
Inspired by [VoiceInk](https://github.com/Beingpax/VoiceInk) (macOS, Swift, GPL-3.0 —
reference for ideas only, no code reuse).

## Decisions

| Question | Decision |
|---|---|
| Platform | Windows first (dev machine: GTX 1650 4GB, i5-10300H) |
| Goal | Personal daily tool — no installer/billing polish |
| Speech-to-text | Local `faster-whisper` — private, free, offline |
| AI cleanup | Groq LLM on transcript *text only* (free tier, ~300–500ms) |
| Stack | Python + PySide6, single process |
| Scope | Full Wispr-style feature set over milestones; wake-word out of scope |

## Architecture

Single PySide6 process. Qt owns the tray icon, overlay pill, settings/history windows,
and event loop. Audio capture, Whisper inference, and LLM calls run in worker threads
so the UI never blocks. Each subsystem is a module with one job and a narrow interface:

```
caspr/
├── __main__.py      # entry: QApplication + wiring, single-instance lock
├── app.py           # AppController state machine: idle→recording→transcribing→cleaning→pasting
├── config.py        # JSON config in %APPDATA%\caspr-flow\
├── hotkeys.py       # global push-to-talk (right-Ctrl hold) via low-level keyboard hook
├── audio.py         # sounddevice InputStream, 16kHz mono float32, level meter
├── stt.py           # faster-whisper: large-v3-turbo int8 CUDA, fallback small int8 CPU
├── cleanup.py       # Groq: fillers, punctuation, self-corrections, tone profiles
├── inject.py        # SendInput unicode typing (default); clipboard-swap Ctrl+V fallback
├── context.py       # foreground exe → app/tone profile
├── dictionary.py    # personal vocab → Whisper initial_prompt + cleanup prompt
├── history.py       # SQLite: raw, cleaned, app, timestamps, stage latencies
└── ui/              # tray.py, overlay.py, settings.py, history_view.py
```

**Core flow:** hotkey down → record (overlay shows live level) → hotkey up →
Whisper (audio stays in memory, never leaves the machine) → active-app tone profile →
Groq cleanup (3s timeout → fall back to raw text) → SendInput unicode injection
(clipboard never touched; revised from clipboard-swap after an e2e-observed
restore race) → history row → overlay fades.

**Latency target:** text lands ≤ ~1.5s after key release. Every stage timed and logged.

## Milestones

1. **M1 — Core loop:** tray, hotkey → record → local Whisper → paste raw text.
2. **M2 — Magic layer:** Groq cleanup + raw fallback; overlay pill.
3. **M3 — Memory:** dictionary, SQLite history + viewer, settings UI.
4. **M4 — Context:** per-app tone profiles.
5. **M5 — Command mode:** rewrite selected text per spoken instruction.
6. **M6 — Flourishes:** hands-free VAD mode, multilingual, stats, launch-at-login.

## Error handling

Never lose words, never block the user:

- Groq slow/down → paste raw Whisper text
- Paste blocked (elevated app) → text stays in clipboard + tray notification
- Silent/empty audio → discard, overlay "didn't catch that"
- No CUDA → CPU + smaller model automatically
- Mic vanished → tray notification, re-enumerate devices

## Testing

- Unit tests for pure logic: config, prompt/dictionary construction, history.
- STT smoke test: SAPI-TTS-generated WAV fixture through the tiny model.
- Manual end-to-end per milestone: dictate into Notepad, Chrome, Windows Terminal.
- Built-in per-stage latency logging as the regression detector.

## Privacy line

Audio never leaves the machine. Only transcript text goes to Groq. A "raw mode"
toggle skips the cloud entirely.
