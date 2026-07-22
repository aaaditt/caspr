# Groq Cloud STT + Smart-Cancel Toggle + Unified Live Hotkeys — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let caspr run with zero local models via Groq cloud STT, give the self-correction ("smart cancel") behaviour its own toggle, and make every keybind apply live in both the standalone and Electron builds.

**Architecture:** A new cloud STT engine slots into the existing `create_transcriber` factory (Workstream A). A new `smart_correct` flag gates the retraction clause in the cleanup prompt (Workstream B). A new Python-side `HotkeyService` owns all global hotkeys (primary PTT + four actions) with one `rearm()`, used by both the Qt entrypoint and the Electron backend, replacing Electron's release-incapable `globalShortcut` layer (Workstream C).

**Tech Stack:** Python 3.14, PySide6/Qt, `groq` SDK (already a dep), `keyboard` lib, stdlib `wave`, pytest; React/Tailwind WebUI (rebuild `webui/dist`); Electron (JS).

## Global Constraints

- **Never lose words:** cleanup failures return raw text; STT failures surface a clear notification (cloud mode has no local fallback).
- **Privacy:** `auto`/local engines never send audio off-machine; Groq-as-STT sends audio only when explicitly selected. The Groq key is write-only over the bridge — `bootstrap` exposes `groq_api_key_set: bool`, never the secret; never log its value.
- **No new Python dependency** for WAV encoding — use stdlib `wave`.
- **Reuse `groq_api_key`** for both STT and cleanup.
- **TDD:** every behaviour gets a failing test first. Tests inject fakes (fake Groq client, fake `keyboard`) — no network, no real global hooks.
- **Commit + push to origin/main** after each workstream (standing rule).
- pytest does not gate on ruff, but keep new code ruff-clean (match existing style).

---

## Workstream A — Groq cloud STT engine

### Task A1: Config field `groq_stt_model`

**Files:**
- Modify: `caspr/config.py` (add field near the Groq cleanup block, ~line 38)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.groq_stt_model: str = "whisper-large-v3-turbo"`

- [ ] **Step 1: Write the failing test** in `tests/test_config.py`:

```python
def test_groq_stt_model_default():
    assert Config().groq_stt_model == "whisper-large-v3-turbo"
```

- [ ] **Step 2: Run it, expect FAIL** (`AttributeError: 'Config' object has no attribute 'groq_stt_model'`):

`uv run pytest tests/test_config.py::test_groq_stt_model_default -v`

- [ ] **Step 3: Add the field** to `Config` after `groq_model`:

```python
groq_stt_model: str = "whisper-large-v3-turbo"  # Groq cloud transcription model
```

- [ ] **Step 4: Run it, expect PASS.**
- [ ] **Step 5: Commit** (`git add caspr/config.py tests/test_config.py`).

### Task A2: `GroqTranscriber` (WAV encode + transcribe)

**Files:**
- Create: `caspr/stt_groq.py`
- Test: `tests/test_stt_groq.py`

**Interfaces:**
- Consumes: `Config` (`groq_api_key`, `groq_stt_model`, `cleanup_timeout_s`).
- Produces:
  - `encode_wav(audio: np.ndarray, rate: int = 16000) -> bytes` (pure; 16-bit PCM mono WAV).
  - `class GroqTranscriber` with `name = "groq"`, `device = "cloud"`, and
    `transcribe(audio, language=None, initial_prompt=None) -> Transcription`.
    Constructor `GroqTranscriber(cfg, client=None)` — `client` injectable for tests;
    default lazily builds `groq.Groq(api_key=...)`. Raises `RuntimeError` if the key is blank.

- [ ] **Step 1: Write failing tests** in `tests/test_stt_groq.py`:

```python
import wave, io
import numpy as np
import pytest
from caspr.config import Config
from caspr.stt_groq import encode_wav, GroqTranscriber


def test_encode_wav_roundtrips_pcm16_mono_16k():
    audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
    raw = encode_wav(audio, rate=16000)
    with wave.open(io.BytesIO(raw)) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
        assert w.getnframes() == 5


class _FakeTranscriptions:
    def __init__(self, holder): self._h = holder
    def create(self, **kwargs):
        self._h.update(kwargs)
        return type("T", (), {"text": "hello world"})()


class _FakeGroq:
    def __init__(self): self.audio = type("A", (), {"transcriptions": _FakeTranscriptions(self.__dict__.setdefault("seen", {}))})()


def test_transcribe_sends_wav_and_returns_text():
    fake = _FakeGroq()
    cfg = Config(groq_api_key="gsk_x", engine="groq")
    t = GroqTranscriber(cfg, client=fake)
    result = t.transcribe(np.zeros(1600, dtype=np.float32), language="en")
    assert result.text == "hello world"
    assert fake.seen["model"] == "whisper-large-v3-turbo"
    assert fake.seen["language"] == "en"
    fname, data = fake.seen["file"]
    assert fname.endswith(".wav") and isinstance(data, bytes)


def test_transcribe_requires_key():
    with pytest.raises(RuntimeError):
        GroqTranscriber(Config(groq_api_key=""), client=object()).transcribe(
            np.zeros(1600, dtype=np.float32)
        )
```

- [ ] **Step 2: Run, expect FAIL** (module missing): `uv run pytest tests/test_stt_groq.py -v`
- [ ] **Step 3: Implement `caspr/stt_groq.py`:**

```python
"""Cloud speech-to-text via Groq's Whisper API. No local model, no CUDA.

Only used when the user explicitly selects engine="groq" — audio never leaves
the machine on auto/local engines.
"""
from __future__ import annotations

import io
import time
import wave

import numpy as np

from .stt import Transcription


def encode_wav(audio: np.ndarray, rate: int = 16000) -> bytes:
    """float32 [-1, 1] mono → 16-bit PCM WAV bytes (in memory)."""
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


class GroqTranscriber:
    name = "groq"
    device = "cloud"

    def __init__(self, cfg, client=None):
        self._model = cfg.groq_stt_model
        self._timeout = cfg.cleanup_timeout_s
        key = (cfg.groq_api_key or "").strip()
        if not key:
            self._error = "set your Groq API key in Settings to use cloud transcription"
        else:
            self._error = ""
        self._client = client
        self._key = key

    def _ensure_client(self):
        if self._error:
            raise RuntimeError(self._error)
        if self._client is None:
            from groq import Groq  # lazy: keep import off module load
            self._client = Groq(api_key=self._key)
        return self._client

    def transcribe(self, audio: np.ndarray, language=None, initial_prompt=None) -> Transcription:
        client = self._ensure_client()
        wav = encode_wav(audio)
        t0 = time.perf_counter()
        kwargs = {"model": self._model, "file": ("clip.wav", wav)}
        if language:
            kwargs["language"] = language
        if initial_prompt:
            kwargs["prompt"] = initial_prompt
        resp = client.audio.transcriptions.create(**kwargs)
        text = (getattr(resp, "text", "") or "").strip()
        return Transcription(text, language or "", time.perf_counter() - t0)
```

Note: `transcribe` calls `_ensure_client()`, so `test_transcribe_requires_key` (blank key) raises `RuntimeError` when `transcribe` runs.

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit.**

### Task A3: Route `engine="groq"`

**Files:**
- Modify: `caspr/stt.py` (`pick_engine` ~line 30, `create_transcriber` ~line 42)
- Test: `tests/test_stt_groq.py` (append)

**Interfaces:**
- Consumes: `GroqTranscriber` (A2).
- Produces: `pick_engine("groq", ...) == "groq"`; `pick_engine("auto", ...)` never returns `"groq"`; `create_transcriber(cfg)` returns a `GroqTranscriber` when `cfg.engine == "groq"`.

- [ ] **Step 1: Write failing tests:**

```python
from caspr.stt import pick_engine, create_transcriber

def test_pick_engine_groq_explicit_only():
    assert pick_engine("groq", "en") == "groq"
    assert pick_engine("groq", None) == "groq"
    assert pick_engine("auto", "en") != "groq"
    assert pick_engine("auto", None) != "groq"

def test_create_transcriber_builds_groq():
    cfg = Config(engine="groq", groq_api_key="gsk_x")
    t = create_transcriber(cfg)
    assert t.name == "groq" and t.device == "cloud"
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Edit `stt.py`:**

In `pick_engine`, add before the parakeet/whisper line:
```python
    if engine == "groq":
        return "groq"
```
(keep `if engine in ("parakeet", "whisper"): return engine` as-is; `auto` still falls through to parakeet/whisper only.)

In `create_transcriber`, add a branch:
```python
    resolved = pick_engine(cfg.engine, cfg.language)
    if resolved == "groq":
        from .stt_groq import GroqTranscriber
        return GroqTranscriber(cfg)
    if resolved == "parakeet":
        from .stt_parakeet import ParakeetTranscriber
        return ParakeetTranscriber(cfg.device)
    return Transcriber(cfg.model, cfg.device)
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit.**

### Task A4: Skip warm-up for cloud engines

**Files:**
- Modify: `caspr/app.py` `_load_model` (~line 125-142)
- Test: `tests/test_app_cleanup.py` (append) or a new focused test file.

**Interfaces:**
- Consumes: `AppController`, `create_transcriber`.
- Produces: `_load_model` does **not** call `transcriber.transcribe(...)` when `transcriber.device == "cloud"`.

- [ ] **Step 1: Write failing test** (monkeypatch `create_transcriber` to return a fake whose `.transcribe` raises if called, `device="cloud"`; assert `_load_model` reaches `idle` without calling it). Sketch:

```python
def test_load_model_skips_warmup_for_cloud(controller, monkeypatch):
    class Cloud:
        name, device = "groq", "cloud"
        def transcribe(self, *a, **k): raise AssertionError("cloud warmup must be skipped")
    import caspr.stt as stt
    monkeypatch.setattr(stt, "create_transcriber", lambda cfg: Cloud())
    controller._load_model()
    assert controller._transcriber is not None
    assert controller.state == "idle"
```

- [ ] **Step 2: Run, expect FAIL** (AssertionError from warmup).
- [ ] **Step 3: Edit `_load_model`** — guard the warm-up lines:

```python
            transcriber = stt.create_transcriber(self.cfg)
            if getattr(transcriber, "device", "") != "cloud":
                # First CUDA inference compiles kernels; warm up on silence.
                transcriber.transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32))
            flag_unknown_words("warmup", [])
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit.**

### Task A5: Bridge — whitelist `groq_stt_model`, reload on key change when cloud, bootstrap

**Files:**
- Modify: `caspr/ui/bridge_data.py` (`_SETTING_KEYS`, `apply_setting`, `bootstrap`)
- Test: `tests/test_bridge_data.py`

**Interfaces:**
- Produces: setting `groq_stt_model` (non-empty str) persists; `groq_api_key` change returns `"reload"` when `cfg.engine == "groq"`; `bootstrap["groq_stt_model"]` present.

- [ ] **Step 1: Failing tests** (fake controller with `.cfg`, `.config_path`, and a `reload_model` spy):

```python
def test_groq_stt_model_setting(controller):
    assert apply_setting(controller, "groq_stt_model", "whisper-large-v3") == ""
    assert controller.cfg.groq_stt_model == "whisper-large-v3"

def test_groq_stt_model_rejects_blank(controller):
    apply_setting(controller, "groq_stt_model", "whisper-large-v3")
    assert apply_setting(controller, "groq_stt_model", "") == ""
    assert controller.cfg.groq_stt_model == "whisper-large-v3"  # unchanged

def test_key_change_reloads_when_engine_is_groq(controller):
    controller.cfg.engine = "groq"
    assert apply_setting(controller, "groq_api_key", "gsk_new") == "reload"

def test_bootstrap_exposes_groq_stt_model(controller):
    assert bootstrap(controller)["groq_stt_model"] == controller.cfg.groq_stt_model
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Edit `bridge_data.py`:**
  - Add `"groq_stt_model"` to `_SETTING_KEYS`.
  - In `apply_setting`, add coercion (reuse the `groq_model` pattern — reject non-str/blank):
    ```python
    elif key == "groq_stt_model":
        if not isinstance(value, str) or not value.strip():
            return ""
    ```
  - After `setattr(...); save_config(...)`, extend the key-change block so a Groq key change reloads the cloud engine:
    ```python
    if key == "groq_api_key" and controller.cfg.engine == "groq":
        controller.reload_model()
        return "reload"
    ```
    (place after the existing model/device/engine/language reload block).
  - In `bootstrap`, add `"groq_stt_model": cfg.groq_stt_model,`.

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit.**

### Task A6: WebUI — engine picker + Groq STT model field

**Files:**
- Modify: `webui/src/bridge.ts` and `webui/src/state.tsx` (add `groq_stt_model: string` to `Bootstrap` + `MOCK_BOOT`).
- Modify: `webui/src/pages/Settings.tsx` (add `"groq"` → "Groq (cloud)" to the engine options; add a Groq-STT-model text/select field shown when engine is groq; note that cloud sends audio to Groq).
- Rebuild: `cd webui && npm run build` (commits `webui/dist`).

- [ ] **Step 1:** Add `groq_stt_model` to the `Bootstrap` interface and `MOCK_BOOT`.
- [ ] **Step 2:** Add the engine option and model field in `Settings.tsx`, calling `set_setting("engine", "groq")` and `set_setting("groq_stt_model", value)`.
- [ ] **Step 3:** `npm run build`; verify `webui/dist` updated.
- [ ] **Step 4:** Manual: launch, pick Groq engine — confirm it round-trips (test_style.py still green).
- [ ] **Step 5: Commit** (`git add webui/`), then **push** (end of Workstream A + B bundle, see B4).

---

## Workstream B — Smart-cancel (self-correction) toggle

### Task B1: Config field `smart_correct`

**Files:** Modify `caspr/config.py`; Test `tests/test_config.py`.

- [ ] **Step 1: Failing test:** `assert Config().smart_correct is True`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Add** `smart_correct: bool = True  # reframe spoken self-corrections` after the tone fields.
- [ ] **Step 4: PASS.** **Step 5: Commit.**

### Task B2: Cleanup prompt honours `smart_correct`

**Files:**
- Modify: `caspr/cleanup.py` (`build_cleanup_messages`, `clean_text`)
- Test: `tests/test_cleanup.py`

**Interfaces:**
- Produces: `build_cleanup_messages(raw, *, recent, glossary, tone, smart_correct)` — system prompt contains the retraction clause iff `smart_correct`. `clean_text` reads `cfg.smart_correct`.

- [ ] **Step 1: Failing tests:**

```python
def test_messages_include_self_correction_when_on():
    msgs = build_cleanup_messages("x", recent=[], glossary=[], tone="balanced", smart_correct=True)
    sys = msgs[0]["content"].lower()
    assert "scratch that" in sys or "never mind" in sys  # retraction cues present

def test_messages_omit_self_correction_when_off():
    msgs = build_cleanup_messages("x", recent=[], glossary=[], tone="balanced", smart_correct=False)
    sys = msgs[0]["content"].lower()
    assert "scratch that" not in sys
    assert "preserve" in sys  # told to keep every stated value
```

- [ ] **Step 2: Run, expect FAIL** (signature lacks `smart_correct`).
- [ ] **Step 3: Implement:** split the `_SYSTEM` prompt into a base (fillers/punctuation/tone/glossary/output-only) + a conditional retraction paragraph. When `smart_correct` is False, append a "preserve every stated value; do not remove or reorder content" instruction instead. Thread `smart_correct` from `clean_text` (default `cfg.smart_correct`).
- [ ] **Step 4: Run full `tests/test_cleanup.py`, expect PASS** (fix any existing call sites that now need the kwarg — `clean_text` supplies it internally, so existing tests that call `clean_text` are unaffected; only direct `build_cleanup_messages` callers need the new kwarg).
- [ ] **Step 5: Commit.**

### Task B3: Bridge — whitelist + bootstrap `smart_correct`

**Files:** Modify `caspr/ui/bridge_data.py`; Test `tests/test_bridge_data.py`.

- [ ] **Step 1: Failing tests:**
```python
def test_smart_correct_setting(controller):
    assert apply_setting(controller, "smart_correct", False) == ""
    assert controller.cfg.smart_correct is False

def test_bootstrap_exposes_smart_correct(controller):
    assert bootstrap(controller)["smart_correct"] == controller.cfg.smart_correct
```
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3:** Add `"smart_correct"` to `_SETTING_KEYS`; coerce with the existing bool branch (`elif key in ("sound_cues", "cleanup_enabled", "handsfree_double_tap", "smart_correct"): value = bool(value)`); add `"smart_correct": cfg.smart_correct,` to `bootstrap`.
- [ ] **Step 4: PASS.** **Step 5: Commit.**

### Task B4: WebUI — smart-cancel toggle + rebuild + push

**Files:** Modify `webui/src/bridge.ts`, `webui/src/state.tsx` (`smart_correct: boolean`), `webui/src/pages/Settings.tsx` (toggle in AI-Cleanup section, independent of `cleanup_enabled`). Rebuild `webui/dist`.

- [ ] **Step 1:** Add `smart_correct` to `Bootstrap` + `MOCK_BOOT`.
- [ ] **Step 2:** Add the toggle calling `set_setting("smart_correct", value)`.
- [ ] **Step 3:** `npm run build`.
- [ ] **Step 4:** `uv run pytest` — full suite green.
- [ ] **Step 5: Commit A6 + B4 webui + this**, then **push origin/main** (Workstream A + B complete).

---

## Workstream C — Unified live hotkeys (both builds)

### Task C1: Controller actions

**Files:**
- Modify: `caspr/app.py` (add methods after `_cancel_recording`; add `open_history_requested = Signal()` near the other signals)
- Test: `tests/test_app_actions.py` (new)

**Interfaces:**
- Produces on `AppController`:
  - `toggle_dictation()` — idle→begin recording; recording→commit; else no-op.
  - `cancel_dictation()` — if recording, discard (calls `_cancel_recording`).
  - `mute_mic()` — calls `toggle_pause()`.
  - `open_history_requested` Signal (no args) + `open_history()` that emits it.

- [ ] **Step 1: Failing tests** (reuse the `controller` fixture pattern from `test_app_cleanup.py` — ImmediateExecutor + FakeRecorder):

```python
def test_toggle_dictation_starts_then_commits(controller, monkeypatch):
    subs = []
    monkeypatch.setattr(controller, "_pipeline", lambda audio: subs.append(audio))
    controller._state = "idle"
    controller.toggle_dictation()
    assert controller.state == "recording"
    controller.toggle_dictation()
    assert len(subs) == 1  # committed

def test_cancel_dictation_discards(controller):
    controller._state = "recording"
    controller._recorder.start()
    controller.cancel_dictation()
    assert controller.state == "idle"

def test_mute_mic_toggles_pause(controller):
    assert controller.paused is False
    controller.mute_mic()
    assert controller.paused is True

def test_open_history_emits(controller):
    seen = []
    controller.open_history_requested.connect(lambda: seen.append(True))
    controller.open_history()
    assert seen == [True]
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the four methods + the signal. `toggle_dictation` reuses `_begin_recording`/`_commit_recording`. `cancel_dictation` calls `_cancel_recording`. `mute_mic` calls `toggle_pause`. `open_history` emits the signal.
- [ ] **Step 4: PASS.** **Step 5: Commit.**

### Task C2: `HotkeyService`

**Files:**
- Create: `caspr/hotkey_service.py`
- Test: `tests/test_hotkey_service.py`

**Interfaces:**
- Consumes: `AppController` (`on_ptt_press`, `on_ptt_release`, `toggle_dictation`, `cancel_dictation`, `mute_mic`, `open_history`), `Config` (the five hotkey fields), `PushToTalk`.
- Produces:
  - `HotkeyService(controller, cfg, ptt_factory=PushToTalk, kb=keyboard)` — `kb`/`ptt_factory` injectable.
  - `rearm()` — tears down every prior hook, then arms the primary `PushToTalk` and each non-empty secondary chord via `kb.add_hotkey`.
  - `suspend()` / `resume()` — stop all hooks / re-arm (for the capture dialog).
  - `stop()` — tear down.

- [ ] **Step 1: Failing tests** (fake `kb` recording `add_hotkey`/`remove_hotkey`; fake `PushToTalk` recording start/stop):

```python
class FakePTT:
    instances = []
    def __init__(self, chord, on_press, on_release):
        self.chord, self.started, self.stopped = chord, 0, 0
        FakePTT.instances.append(self)
    def start(self): self.started += 1
    def stop(self): self.stopped += 1

class FakeKb:
    def __init__(self): self.added, self.removed = [], []
    def add_hotkey(self, chord, cb, **kw):
        h = (chord, cb); self.added.append(h); return h
    def remove_hotkey(self, h): self.removed.append(h)

def test_rearm_arms_primary_and_secondaries():
    cfg = Config(hotkey="ctrl+windows", hotkey_toggle_dictation="ctrl+shift+d",
                 hotkey_mute_mic="ctrl+shift+m")
    kb = FakeKb(); FakePTT.instances = []
    svc = HotkeyService(_StubController(), cfg, ptt_factory=FakePTT, kb=kb)
    svc.rearm()
    assert FakePTT.instances[-1].chord == "ctrl+windows"
    assert FakePTT.instances[-1].started == 1
    assert len(kb.added) == 2  # only the two non-empty secondary chords

def test_rearm_tears_down_previous():
    cfg = Config(hotkey="ctrl+windows", hotkey_toggle_dictation="ctrl+shift+d")
    kb = FakeKb(); FakePTT.instances = []
    svc = HotkeyService(_StubController(), cfg, ptt_factory=FakePTT, kb=kb)
    svc.rearm(); svc.rearm()
    assert FakePTT.instances[0].stopped == 1   # old primary torn down
    assert len(kb.removed) == 1                 # old secondary removed
```

(`_StubController` exposes the six action methods as no-ops.)

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement `hotkey_service.py`** — an `_ACTIONS` map of `{config_field: controller_method_name}` for the four secondary keys; `rearm()` clears then rebuilds; store PTT + secondary handles for teardown.
- [ ] **Step 4: PASS.** **Step 5: Commit.**

### Task C3: Wire the Qt entrypoint

**Files:** Modify `caspr/__main__.py` (replace the inline `arm()`/`ptt_holder`/`capture_active` block, ~lines 176-191) and `caspr/ui/bridge.py` / `caspr/ui/shell.py` if needed so any hotkey change re-arms.

**Interfaces:** Consumes `HotkeyService`. The `hotkey_changed` signal must fire for **any** hotkey key (currently only relays the primary). Simplest: rename/repurpose to a no-arg `hotkeys_changed` that triggers `service.rearm()`.

- [ ] **Step 1:** In `bridge.py::set_setting`, emit `hotkeys_changed` when `apply_setting(...) == "hotkey"` (no chord payload needed). Relay through `Shell` like the current `hotkey_changed`.
- [ ] **Step 2:** In `__main__.py`, build `service = HotkeyService(controller, cfg); service.rearm()`; connect `window.hotkeys_changed` → `service.rearm`; connect `window.capture_active` → `service.suspend`/`service.resume`; connect `controller.open_history_requested` → surface the window on History.
- [ ] **Step 3:** Manual smoke: `uv run python -m caspr`, hold primary → dictate; set a toggle hotkey in Settings → it starts/stops dictation immediately; change it → new key works with no restart.
- [ ] **Step 4:** `uv run pytest` green. **Step 5: Commit.**

### Task C4: Wire the Electron backend (server mode)

**Files:** Modify `caspr/server.py` (construct `HotkeyService`; re-arm + broadcast on hotkey changes; broadcast `open_history` action).

**Interfaces:** `JsonWsServer` gains a reference to the `HotkeyService`; the `set_setting` handler re-arms and broadcasts when `apply_setting` returns `"hotkey"`.

- [ ] **Step 1:** In `run_server`, after building the controller, create `service = HotkeyService(controller, cfg); service.rearm()`. Pass `service` into `JsonWsServer` (or arm from within it).
- [ ] **Step 2:** In `_handle_request` `set_setting` branch: if `apply_setting(...) == "hotkey"`, `self._service.rearm()` and `self._broadcast({"type": "hotkeys_changed"})`.
- [ ] **Step 3:** Connect `controller.open_history_requested` → `self._broadcast({"type": "action", "name": "open_history"})`.
- [ ] **Step 4:** `uv run pytest` green (no new unit test strictly required here — logic is covered by C2/A5; a light integration test of the `set_setting` branch calling `rearm` may be added if convenient). **Step 5: Commit.**

### Task C5: Electron JS — drop the redundant shortcut layer, react to actions

**Files:** Modify `electron/main.js` (remove `hotkeyManager.registerActions` at bootstrap; listen on `wsClient.on('event')` for `{type:"action", name:"open_history"}` → show+navigate window; keep window-show behaviour). Modify/remove `electron/hotkeys.js` (no longer needed — Python owns hooks). Update `electron/preload.js` if any hotkey plumbing is now dead.

- [ ] **Step 1:** Remove the `registerActions({...})` call and the `HotkeyManager` construction/teardown; keep `capture-hotkey` (still a Python Qt dialog over WS).
- [ ] **Step 2:** In `wsClient.on('event')`, handle `type === 'action' && name === 'open_history'` → `mainWindow.show(); mainWindow.webContents.send('navigate', 'history')`.
- [ ] **Step 3:** Manual (if Electron is set up): `npm start`, hold primary → dictates via Python hook; set a hotkey in Settings → applies without restart.
- [ ] **Step 4: Commit.**

### Task C6: Docs + memory

**Files:** Modify `README.md` (Groq-only mode setup: pick "Groq (cloud)", paste key, no local model; note live-settings/hotkeys); the design/plan docs already exist.

- [ ] **Step 1:** README: add a short "Cloud-only mode (no GPU)" section and a note that all settings/hotkeys apply live.
- [ ] **Step 2:** `uv run pytest` full suite green.
- [ ] **Step 3: Commit + push origin/main** (Workstream C complete).
- [ ] **Step 4:** Update auto-memory `caspr-flow-project.md` with a dated entry (Groq STT engine, smart_correct toggle, unified HotkeyService live in both builds).

---

## Self-Review

**Spec coverage:**
- A (Groq STT engine, choosable, no warm-up, reuse key, `auto` never cloud) → A1–A6. ✓
- B (smart_correct toggle, independent of cleanup_enabled, live) → B1–B4. ✓
- C (HotkeyService both builds, four controller actions, live re-arm, Electron fix, drop globalShortcut) → C1–C6. ✓
- Privacy/never-lose-words/no-new-dep/write-only key → captured in Global Constraints and enforced per task (encode_wav stdlib, key not echoed, cloud raises on failure). ✓

**Placeholder scan:** No TBD/TODO; test code and signatures are concrete. WebUI steps describe exact `set_setting` keys and files. ✓

**Type consistency:** `GroqTranscriber(cfg, client=None)`, `encode_wav(audio, rate=16000) -> bytes`, `Transcription(text, language, infer_s)` (matches `stt.py`), `build_cleanup_messages(..., smart_correct)`, `HotkeyService(controller, cfg, ptt_factory, kb)` with `rearm/suspend/resume/stop`, `open_history_requested` Signal + `open_history()` — used consistently across tasks. ✓
