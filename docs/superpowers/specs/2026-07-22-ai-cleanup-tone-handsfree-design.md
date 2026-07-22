# AI Cleanup + Per-App Tone + Double-Tap Hands-Free — Design

**Date:** 2026-07-22
**Status:** Implemented (M2 cleanup + M4 tone + a hands-free variant)

## What

Three features, delivered as one new post-STT subsystem plus a hotkey gesture layer.

1. **AI cleanup stage (Groq).** After transcription, a fast Groq pass removes fillers,
   fixes punctuation/capitalization, and — the headline — **honours spoken
   self-corrections**: "meet at 5:30, actually no, 6:30" → "Let's meet at 6:30." On any
   failure (disabled, no key, timeout, error, empty reply) it returns the raw transcript,
   so a dictation is never dropped.
2. **Bounded context.** The cleanup pass receives only the last `cleanup_context_count`
   (default 10) dictations for consistency — not an unbounded history.
3. **Per-app tone profiles.** The foreground exe (via pywin32) selects a tone label that
   steers the cleanup; unmatched apps use `tone_default`.
4. **Double-tap hands-free.** Hold = push-to-talk (unchanged, zero added latency).
   Double-tap = start a hands-free session; a single tap stops it and transcribes.

## Architecture

- `caspr/cleanup.py` — `build_cleanup_messages` (pure prompt assembly) + `clean_text`
  (orchestration with never-lose-words fallback; the Groq call is injected as `complete`
  for testing, defaults to `_groq_complete`).
- `caspr/context.py` — `foreground_exe()` (defensive Win32) + `tone_for()` (pure).
- `caspr/hotkeys.py::GestureInterpreter` — pure, clock-injected classifier. Recording
  starts on press; the release classifies by hold duration; the double-tap window is
  checked lazily on the next press, so no background timer is needed.
- `caspr/app.py` — `on_ptt_press`/`on_ptt_release` route through the interpreter (when
  `handsfree_double_tap`), whose callbacks map to `_begin/_commit/_cancel_recording` and
  `_set_handsfree`. Both runtimes (standalone keyboard hook and Electron/WebSocket) funnel
  through these two methods, so the gesture works everywhere. `_pipeline` runs cleanup
  **before** `apply_replacements` (user rules still apply to cleaned text), captures the
  foreground exe at record start, and logs a `clean` stage latency.

## Config (new fields, `caspr/config.py`)

`cleanup_enabled` (True), `groq_api_key` (""), `groq_model` ("llama-3.1-8b-instant"),
`cleanup_context_count` (10), `cleanup_timeout_s` (3.0), `tone_profiles` ({}),
`tone_default` ("balanced"), `handsfree_double_tap` (True), `double_tap_ms` (400).

## Settings surface

`caspr/ui/bridge_data.py` whitelists the new keys (with coercion/validation);
`double_tap_ms`/`handsfree_double_tap` rebuild the gesture interpreter live. The Groq key
is write-only over the bridge — `bootstrap` exposes `groq_api_key_set: bool`, never the
secret. WebUI adds **AI Cleanup**, **Tone**, and hands-free rows (webui/dist rebuilt).

## Privacy

Only transcript text + last-N dictations + glossary reach Groq; audio never leaves the
machine; `cleanup_enabled=False` skips the cloud entirely.

## Latency

turbo (~1.76s) + Groq (~0.4s) ≈ ~2.2s; the timeout bounds the worst case and falls back
to raw text.

## Tests

`test_cleanup.py`, `test_context.py`, `test_gestures.py`, `test_app_cleanup.py`, plus
additions to `test_config.py` and `test_bridge_data.py`. The Groq network call is injected
in tests; the live path needs a real key.

## Not done / follow-ups

- Live Groq verification requires a key (console.groq.com) — pending.
- Command/rewrite-selected-text mode (M5) — deferred.
- Long hands-free clips transcribe in one shot; chunking deferred (YAGNI).
