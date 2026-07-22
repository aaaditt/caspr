# Groq Cloud STT + Smart-Cancel Toggle + Unified Live Hotkeys — Design

**Date:** 2026-07-22
**Status:** Approved (design); implementation pending

## What & why

Three additions, driven by Aadit's request: let a downloader run caspr with **no local
models** (cloud STT via Groq), give the self-correction ("smart cancel") behaviour its
**own toggle**, and make **every keybind apply live** — in both the standalone and
Electron builds — without restarting.

Investigation of the current code established the real starting points:

- **STT is already polymorphic behind one factory** (`caspr/stt.py::create_transcriber`);
  every engine shares `.transcribe(audio, language=, initial_prompt=) -> Transcription`
  plus `.name`/`.device`. A cloud engine slots in without touching the pipeline.
- **Most settings already hot-reload**: model/device/engine/language (`reload_model`),
  mic (`set_input_device`), gestures (`reconfigure_gestures`), the **primary** hotkey in
  the Qt build (`__main__.py::arm`), and all cleanup/tone settings (read fresh each
  dictation). The gaps are the **secondary hotkeys** and the **Electron** re-registration.
- **The Electron build's primary push-to-talk is not wired at all**: `server.py` has
  `ptt_press`/`ptt_release` handlers but no client sends them, and Electron's
  `globalShortcut` cannot detect key-release (so it can't do hold-to-talk). The four
  secondary hotkeys landed as config + UI + an Electron skeleton in the 2026-07-19 work,
  but the **controller actions they should trigger were never implemented** (Electron maps
  them all to `toggle_pause` as placeholders).

## Workstream A — Groq cloud STT engine (choosable)

**New:** `caspr/stt_groq.py::GroqTranscriber`
- `name = "groq"`, `device = "cloud"`.
- `transcribe(audio, language=None, initial_prompt=None)`: encode the float32 @16 kHz clip
  to in-memory 16-bit PCM WAV bytes using the stdlib `wave` module (**no new dependency**),
  then `client.audio.transcriptions.create(model=cfg.groq_stt_model, file=("clip.wav",
  wav_bytes), language=language or omit, prompt=initial_prompt or omit)`; return
  `Transcription(text, language or "", infer_s)`. Lazy `from groq import Groq`.
- On failure it raises (there is no local fallback in cloud-only mode); the pipeline's
  existing `except` surfaces a notification. A missing key raises a clear
  "set your Groq API key" error rather than silently doing nothing.

**Edit:** `caspr/stt.py`
- `pick_engine`: `"groq"` is explicit-only — `auto` still resolves to parakeet/whisper so
  **audio never goes to the cloud unless the user selects Groq**.
- `create_transcriber`: `groq` branch → `GroqTranscriber(cfg)`.

**Edit:** `caspr/app.py`
- `_load_model`: skip the silence warm-up for cloud engines (nothing to compile; it would
  be a wasted billed request). Guard on `getattr(transcriber, "device", "") == "cloud"`.
  With `engine="groq"` this makes startup instant and loads **no local model / no CUDA**.

**Edit:** `caspr/config.py` — add `groq_stt_model: str = "whisper-large-v3-turbo"`.
Reuse the existing `groq_api_key`.

**Edit:** `caspr/ui/bridge_data.py` — whitelist `groq_stt_model`; expose it in `bootstrap`.
When `groq_api_key` changes **and** `engine == "groq"`, also `reload_model()` so the new
key takes effect live.

**Edit:** WebUI — add "Groq (cloud)" to the engine picker and a Groq-STT-model field in the
AI/engine settings. Rebuild `webui/dist`.

Local STT + Groq cleanup ("boost") stays exactly as-is; Groq-as-STT is an additional choice.

## Workstream B — Smart-cancel (self-correction) toggle

**Edit:** `caspr/config.py` — add `smart_correct: bool = True`.

**Edit:** `caspr/cleanup.py`
- `build_cleanup_messages(..., smart_correct: bool)`: include the retraction/"5:30 →
  actually 6:30" instruction only when `smart_correct` is true. When false, the prompt still
  fixes fillers/punctuation and applies tone, but is told to **preserve every stated value**
  (no reframing).
- `clean_text`: thread `cfg.smart_correct` into `build_cleanup_messages`.

**Edit:** `caspr/ui/bridge_data.py` — whitelist `smart_correct` (bool); expose in bootstrap.
**Edit:** WebUI — a toggle in the AI-Cleanup section, independent of `cleanup_enabled`.
Applies live (cleanup reads config fresh per dictation).

## Workstream C — Unified live hotkeys (both builds)

**New:** `caspr/hotkey_service.py::HotkeyService` — owns **all** global hotkeys in Python.
- Holds the primary `PushToTalk` (press/release → `controller.on_ptt_press/release`) and
  registers the four secondary chords via `keyboard.add_hotkey` (press-only) → controller
  actions.
- `rearm()`: tear down every hook and rebuild from current config — the single entry point
  both builds call after any hotkey change.
- `suspend()` / `resume()`: used around the modal hotkey-capture dialog (replaces the ad-hoc
  stop/re-arm in `__main__.py`).
- Optional `on_action(name)` host hook so Electron can surface/navigate its window for
  `open_history` (Qt supplies its own window-surface callback).

**New controller actions** (`caspr/app.py`) — the missing behaviours:
- `toggle_dictation()`: idle → start recording; recording → commit (tap-to-toggle, reusing
  the existing state guard). Distinct from hands-free.
- `cancel_dictation()`: discard the in-flight clip (reuses `_cancel_recording`).
- `mute_mic()`: alias to `toggle_pause()`.
- `open_history()`: emit a signal the host binds (Qt surfaces the window on History;
  Electron shows+navigates via the `on_action` broadcast).

**Edit:** `caspr/__main__.py` (Qt) — replace the inline `arm()`/capture wiring with a
`HotkeyService`; `Bridge.hotkey_changed` (widened to fire on any hotkey key) → `rearm()`.

**Edit:** `caspr/server.py` (Electron backend) — construct the same `HotkeyService` so Python
owns the hooks in server mode too (this is what finally makes Electron's primary PTT work).
When `apply_setting` reports a hotkey change, `rearm()` and broadcast a `hotkeys_changed`
event; on `open_history`, broadcast `{type:"action", name:"open_history"}`.

**Edit:** `electron/main.js` / `electron/hotkeys.js` — remove the redundant `globalShortcut`
action layer (avoids double-registration and the mis-mapped `toggle_dictation`→`toggle_pause`);
main.js listens for the `action` broadcast to show/navigate its window.

**Edit:** `caspr/ui/bridge_data.py` — `apply_setting` already returns `"hotkey"` for all five
keys; ensure the primary and secondary keys are handled uniformly and the host re-arms.

## Config summary (new fields)

| field | default | purpose |
|---|---|---|
| `groq_stt_model` | `"whisper-large-v3-turbo"` | Groq transcription model |
| `smart_correct` | `True` | toggle self-correction/retraction reframing |

(`engine` gains a `"groq"` value; `groq_api_key` is reused for both STT and cleanup.)

## Testing (TDD)

- **A:** `GroqTranscriber.transcribe` encodes valid WAV bytes and returns the client's
  `.text` (inject a fake Groq client); `pick_engine`/`create_transcriber` route `"groq"`;
  `auto` never returns `"groq"`; warm-up is skipped for `device == "cloud"`.
- **B:** `build_cleanup_messages` includes the self-correction clause iff `smart_correct`;
  `clean_text` passes the flag through; `smart_correct=False` still cleans fillers.
- **C:** `HotkeyService.rearm` tears down prior hooks before adding new ones (inject a fake
  `keyboard`/PushToTalk); the four controller actions transition state correctly
  (idle→recording→idle, cancel, pause, history signal). Bridge routing returns `"hotkey"`
  for every hotkey key and triggers a re-arm.
- Existing 121 tests stay green.

## Live/manual checks

- Set `engine=groq` + a key with **no local model present** → dictation works via cloud.
- Toggle smart-cancel off → "5:30, actually 6:30" is left intact; on → reframed.
- Change primary and each secondary hotkey in Settings → new keys work immediately, no
  restart, in **both** the `caspr` desktop build and the Electron build.

## Privacy

Groq-as-STT sends **audio** to Groq (only when explicitly selected); `auto`/local engines
never do. Cleanup still sends transcript text only. `cleanup_enabled=False` and a local
engine keep everything on-device.

## Sequencing

Ship **A + B** first (small, high-value, low-risk — one commit), then **C** (the hotkey
consolidation — its own commit). Commit + push to origin/main after each per the standing
rule.

## Out of scope

- Command/rewrite-selected-text mode (M5) — still deferred.
- Streaming/chunked cloud transcription for very long clips — one-shot for now (YAGNI).
