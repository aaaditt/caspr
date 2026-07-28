# Live Streaming Dictation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make caspr type words live while the dictation hotkey is held, using a local streaming ASR engine, while keeping the existing accurate batch model (Parakeet/Whisper) as the one-time source of truth for the final text on release.

**Architecture:** A stateful local streaming decoder (vosk, chosen via Task 1's spike) consumes the same 100ms audio blocks `Recorder` already produces and returns a growing hypothesis string. Each hypothesis is word-diffed (`compute_correction`) against what's currently typed in the focused window, and only the changed tail is backspaced+retyped. On release, the existing batch pipeline runs exactly as today (transcribe → cleanup → replacements) and one final diff reconciles the screen to that trusted result. The streaming engine never decides the final text — it only makes the in-progress experience feel alive.

**Tech Stack:** Python 3.14 (uv-managed venv, editable install — code changes apply on process restart, no rebuild), `vosk` (new dependency, Kaldi-based streaming ASR), existing `caspr/audio.py` (Recorder), `caspr/inject.py` (Windows SendInput), pytest.

## Global Constraints

- Run tests with `.venv/Scripts/python.exe -m pytest` — NOT `uv run pytest` (uv's sync step fails with a file-lock error if caspr-app.exe is running).
- This is an editable install (`_editable_impl_caspr_flow.pth`): editing files under `caspr/` takes effect the next time the app process starts. No build/packaging step exists or is needed.
- Live typing only ever runs when `cfg.injection == "type"` (SendInput). It is fundamentally incompatible with `cfg.injection == "clipboard"` (a whole-buffer paste, not incremental) — when clipboard mode is active, skip live typing entirely and fall back to today's single full inject at release. This is a new, explicit condition not spelled out in the design doc's prose but required by how `inject.py` works; call it out in code with a one-line comment, not a config toggle (YAGNI — no new setting).
- No new config fields, no Settings UI changes. The streaming engine loads unconditionally in `_load_model()`; failure to load degrades silently to today's behavior (per the design doc's safety invariants) — there is no user-facing on/off switch for this feature.
- Match existing patterns: lazy imports for heavy/optional dependencies (see `stt_parakeet.py`, `stt_groq.py`), dependency injection for testability (see `GroqTranscriber(cfg, client=None)`), `logging.getLogger(__name__)` per module, `from __future__ import annotations`.
- Commit after each task (small, scoped commits — this repo's convention per `git log`, e.g. `fix(cleanup): ...`, `feat(config): ...`). Push to `origin/main` only once, after Task 8 (final live verification) — landing intermediate not-yet-integrated states on `main` is worse than one slightly larger push at the end, per this being a single feature arc.
- `Recorder`, `AppController`, and `inject.py`'s SendInput calls have zero existing unit tests for their OS/hardware-boundary logic (confirmed: no `tests/test_inject.py` exists; `tests/test_audio_level.py` only tests the pure `meter_level` function, not `Recorder` itself). Follow this project's existing convention: don't invent a new testing bar for these boundaries that the codebase doesn't already hold itself to. Test the pure logic (`compute_correction`, `LiveTypingSession`, the vosk adapter's JSON-parsing) with fakes/injection; leave the literal `SendInput`/`sounddevice.InputStream` calls untested, exactly as `type_text`/`Recorder.start` are today.

---

### Task 1: Spike — pick the streaming ASR engine

**Files:**
- Create: `scripts/spike_streaming_engine.py` (throwaway, not part of the app — do not import it from `caspr/`)
- Create: `docs/superpowers/specs/2026-07-28-streaming-engine-spike-results.md` (the decision record)

**Interfaces:**
- Produces: a written decision — "vosk" or "sherpa-onnx" or "neither (fallback to rolling batch re-transcribe)" — that Task 4 depends on. If "neither", stop after this task and tell the user; Tasks 4 onward assume a stateful streaming decoder exists and would need re-scoping.

This is exploratory, not TDD — per the test-driven-development skill, throwaway spikes are an explicit exception.

- [ ] **Step 1: Install and try vosk first (simplest candidate)**

```bash
.venv/Scripts/python.exe -m pip install vosk
```

Download a small English model from vosk's official models page (`https://alphacephei.com/vosk/models` — look for `vosk-model-small-en-us-0.15.zip`, ~40MB). Unzip it to:

```
%APPDATA%\caspr-flow\models\vosk-model-small-en-us-0.15\
```

- [ ] **Step 2: Write the spike script**

```python
"""Throwaway benchmark: does vosk (and optionally sherpa-onnx) give usable
live-typing latency/accuracy on this machine? Not part of the app.

Usage: .venv/Scripts/python.exe scripts/spike_streaming_engine.py <path_to_wav>
The wav must be 16kHz mono 16-bit PCM (use caspr.audio.load_wav_mono16k's
format — record one with the app, or `ffmpeg -ar 16000 -ac 1 -sample_fmt s16`).
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from caspr.audio import load_wav_mono16k, SAMPLE_RATE  # noqa: E402


def chunks(audio: np.ndarray, block_size: int = SAMPLE_RATE // 10):
    for i in range(0, len(audio), block_size):
        yield audio[i : i + block_size]


def bench_vosk(audio: np.ndarray, model_dir: str) -> None:
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    t_load = time.perf_counter()
    model = Model(model_dir)
    print(f"vosk model load: {time.perf_counter() - t_load:.2f}s")

    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(False)
    latencies = []
    last_partial = ""
    for block in chunks(audio):
        pcm = (np.clip(block, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        t0 = time.perf_counter()
        rec.AcceptWaveform(pcm)
        partial = json.loads(rec.PartialResult()).get("partial", "")
        latencies.append(time.perf_counter() - t0)
        if partial != last_partial:
            print(f"  partial: {partial!r}")
            last_partial = partial
    final = json.loads(rec.FinalResult()).get("text", "")
    print(f"vosk final: {final!r}")
    print(f"vosk per-chunk latency: mean={np.mean(latencies)*1000:.1f}ms max={np.max(latencies)*1000:.1f}ms")


if __name__ == "__main__":
    wav_path = sys.argv[1]
    audio = load_wav_mono16k(wav_path)
    model_dir = str(Path.home() / "AppData/Roaming/caspr-flow/models/vosk-model-small-en-us-0.15")
    bench_vosk(audio, model_dir)
```

- [ ] **Step 3: Run it against 3-4 real dictation clips**

Record a few clips of varying length with the live app first (or reuse any existing test fixture WAVs under `tests/fixtures/` if present), then:

```bash
.venv/Scripts/python.exe scripts/spike_streaming_engine.py path/to/clip.wav
```

Judge against these concrete bars (from the design doc's intent — live typing must feel "alive", not laggy):
- Per-chunk latency mean should be well under 100ms (the block period itself) — if it's not, live typing will visibly lag behind speech.
- The final vosk transcript's rough word accuracy should be usable as a live preview (it does NOT need to match Parakeet/Whisper — the batch model reconciles it at release regardless).
- No crashes, no missing/garbled `pip install` on Python 3.14/Windows.

- [ ] **Step 4 (only if vosk fails the bars above): try sherpa-onnx**

```bash
.venv/Scripts/python.exe -m pip install sherpa-onnx
```

Pick a streaming zipformer English model from k2-fsa/sherpa-onnx's own pretrained-models documentation (search their GitHub repo/docs site for "streaming-transducer" pretrained models — pick a small/fast English one) and note the exact model name and files downloaded. Add a second `bench_sherpa(audio, encoder, decoder, joiner, tokens)` function to the spike script using `sherpa_onnx.OnlineRecognizer.from_transducer(...)`, `recognizer.create_stream()`, `stream.accept_waveform(...)`, `recognizer.decode_stream(stream)` in the same per-chunk loop shape as `bench_vosk`, and compare the same metrics.

- [ ] **Step 5: Write the decision doc**

Create `docs/superpowers/specs/2026-07-28-streaming-engine-spike-results.md` recording: which engine was chosen, the measured latency/accuracy numbers, the exact model file(s) and where they're stored, and why (or, if neither worked, that finding and the fallback plan per the original design doc). The rest of this plan assumes **vosk won** (it's simpler, has no external model-file pinning risk, and is the design doc's first-listed candidate) — if the spike instead picks sherpa-onnx, Task 4 needs its adapter written against the same `StreamingEngine`/`StreamingTranscriber` interface using the sherpa-onnx calls sketched in Step 4 instead of the vosk ones below; every other task is unaffected either way.

- [ ] **Step 6: Commit**

```bash
git add scripts/spike_streaming_engine.py docs/superpowers/specs/2026-07-28-streaming-engine-spike-results.md
git commit -m "spike: benchmark vosk streaming ASR for live-typing latency/accuracy"
```

---

### Task 2: `compute_correction` — the diff/reconciliation algorithm

**Files:**
- Create: `caspr/diff.py`
- Test: `tests/test_diff.py`

**Interfaces:**
- Produces: `compute_correction(typed: str, target: str) -> tuple[int, str]` — used by Task 5 (`live_typing.py`) and Task 7 (`app.py`'s release-time reconciliation).

This is pure logic, TDD, no dependency on Task 1's outcome.

- [ ] **Step 1: Write the failing tests**

```python
from caspr.diff import compute_correction


def test_identical_text_is_a_noop():
    assert compute_correction("meet at 6:30", "meet at 6:30") == (0, "")


def test_appends_new_words_to_empty_typed():
    assert compute_correction("", "hello") == (0, "hello")


def test_appends_new_words_after_existing_typed():
    assert compute_correction("meet at", "meet at six") == (0, " six")


def test_corrects_a_tail_word():
    backspaces, insert = compute_correction("meet at six thirty", "meet at 6:30")
    assert backspaces == len(" six thirty")
    assert insert == " 6:30"


def test_full_replacement_when_no_shared_prefix():
    backspaces, insert = compute_correction("foo bar", "baz qux")
    assert backspaces == len("foo bar")
    assert insert == "baz qux"


def test_backspace_count_never_exceeds_typed_length():
    backspaces, _ = compute_correction("hi", "a completely different and much longer sentence")
    assert backspaces <= len("hi")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_diff.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'caspr.diff'`

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_diff.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all existing tests + 6 new ones pass.

- [ ] **Step 6: Commit**

```bash
git add caspr/diff.py tests/test_diff.py
git commit -m "feat(diff): add compute_correction word-level diff for live typing"
```

---

### Task 3: `inject.backspace` — the missing injection primitive

**Files:**
- Modify: `caspr/inject.py`

**Interfaces:**
- Produces: `backspace(count: int) -> None`, used by Task 5 (`live_typing.py`) and Task 7 (`app.py`).

No test for this task — see Global Constraints (`type_text` itself has no test; this is the same OS-boundary class of function).

- [ ] **Step 1: Add the virtual-key constant and function**

In `caspr/inject.py`, after `_SENDINPUT_CHUNK = 256` add:

```python
_VK_BACK = 0x08
```

After `type_text`, add:

```python
def backspace(count: int) -> None:
    """Send `count` Backspace key presses into the focused window via SendInput."""
    if count <= 0:
        return
    events: list[_INPUT] = []
    for _ in range(count):
        for flags in (0, _KEYEVENTF_KEYUP):
            inp = _INPUT()
            inp.type = _INPUT_KEYBOARD
            inp.ki = _KEYBDINPUT(_VK_BACK, 0, flags, 0, None)
            events.append(inp)
    for start in range(0, len(events), _SENDINPUT_CHUNK):
        chunk = events[start : start + _SENDINPUT_CHUNK]
        array = (_INPUT * len(chunk))(*chunk)
        sent = ctypes.windll.user32.SendInput(len(chunk), array, ctypes.sizeof(_INPUT))
        if sent != len(chunk):
            raise OSError(f"SendInput injected {sent}/{len(chunk)} backspace events")
```

- [ ] **Step 2: Run the full suite (nothing should break — this is additive)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests still pass (no new tests added this task).

- [ ] **Step 3: Commit**

```bash
git add caspr/inject.py
git commit -m "feat(inject): add backspace() primitive for live-typing corrections"
```

---

### Task 4: `caspr/stt_streaming.py` — the streaming engine wrapper

**Files:**
- Create: `caspr/stt_streaming.py`
- Test: `tests/test_stt_streaming.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `class StreamingTranscriber` (protocol-ish base): `.feed(block: np.ndarray) -> str | None`, `.finalize() -> str`
  - `class StreamingEngine` (protocol-ish base): `.new_stream() -> StreamingTranscriber`
  - `create_streaming_engine(cfg) -> StreamingEngine | None` — used by Task 7 (`app.py._load_model`). Returns `None` on any failure (missing dependency, missing model files) — callers must treat `None` as "skip live typing this session."

- [ ] **Step 1: Write the failing tests**

```python
"""Streaming STT wrapper: unit-tested via a fake vosk recognizer (no real
vosk/model download needed — same injection pattern as GroqTranscriber's
`client=` param in stt_groq.py)."""

import numpy as np

from caspr.stt_streaming import VoskStream, create_streaming_engine


class FakeRecognizer:
    """Duck-types vosk.KaldiRecognizer's 3 methods this module calls."""

    def __init__(self, partials: list[str], final: str):
        self._partials = list(partials)
        self._final = final
        self.fed_pcm: list[bytes] = []

    def AcceptWaveform(self, pcm: bytes) -> bool:
        self.fed_pcm.append(pcm)
        return False

    def PartialResult(self) -> str:
        import json

        partial = self._partials.pop(0) if self._partials else ""
        return json.dumps({"partial": partial})

    def FinalResult(self) -> str:
        import json

        return json.dumps({"text": self._final})


def test_vosk_stream_returns_hypothesis_only_when_it_changes():
    rec = FakeRecognizer(partials=["hello", "hello", "hello world"], final="hello world")
    stream = VoskStream(rec)
    block = np.zeros(1600, dtype=np.float32)
    assert stream.feed(block) == "hello"
    assert stream.feed(block) is None  # unchanged partial -> no update
    assert stream.feed(block) == "hello world"


def test_vosk_stream_converts_float32_to_int16_pcm():
    rec = FakeRecognizer(partials=["x"], final="x")
    stream = VoskStream(rec)
    block = np.array([1.0, -1.0, 0.0], dtype=np.float32)
    stream.feed(block)
    pcm = rec.fed_pcm[0]
    values = np.frombuffer(pcm, dtype="<i2")
    assert values[0] == 32767  # +1.0 clamped to int16 max
    assert values[1] == -32767  # -1.0 -> int16 min-ish (via clip then scale)
    assert values[2] == 0


def test_vosk_stream_finalize_returns_final_result_text():
    rec = FakeRecognizer(partials=[], final="the final text")
    stream = VoskStream(rec)
    assert stream.finalize() == "the final text"


def test_create_streaming_engine_returns_none_when_vosk_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "vosk":
            raise ImportError("no vosk installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from caspr.config import Config

    assert create_streaming_engine(Config()) is None


def test_vosk_streaming_engine_raises_when_model_dir_missing(tmp_path):
    import pytest

    from caspr.stt_streaming import VoskStreamingEngine

    with pytest.raises(FileNotFoundError):
        VoskStreamingEngine(model_dir=tmp_path / "does-not-exist")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stt_streaming.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'caspr.stt_streaming'`

- [ ] **Step 3: Implement**

```python
"""Local streaming (incremental) STT for live-typing while the hotkey is held.

Unlike stt_parakeet.py/stt_groq.py's one-shot .transcribe(), this exposes a
stateful chunk-in/partial-out decoder: StreamingEngine.new_stream() returns a
StreamingTranscriber good for exactly one dictation, fed 100ms float32 blocks
as they arrive from Recorder, returning the growing hypothesis text after
each block (or None when it hasn't changed since the last call).

Never the source of truth for the final injected text -- see live_typing.py
and AppController._pipeline's release-time reconciliation against the
existing accurate batch model. Any failure here (missing dependency, missing
model files) must degrade to "no live typing this session", never crash a
dictation -- see create_streaming_engine's broad except.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

_MODEL_DIR_NAME = "vosk-model-small-en-us-0.15"


def _default_model_dir() -> Path:
    from .config import default_config_path

    return default_config_path().parent / "models" / _MODEL_DIR_NAME


class VoskStream:
    """One instance per dictation. Wraps a vosk.KaldiRecognizer."""

    def __init__(self, recognizer):
        self._rec = recognizer
        self._last = ""

    def feed(self, block: np.ndarray) -> str | None:
        pcm = (np.clip(block, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        self._rec.AcceptWaveform(pcm)
        partial = json.loads(self._rec.PartialResult()).get("partial", "")
        if partial and partial != self._last:
            self._last = partial
            return partial
        return None

    def finalize(self) -> str:
        text = json.loads(self._rec.FinalResult()).get("text", "")
        return text or self._last


class VoskStreamingEngine:
    """Loads the vosk model once; call new_stream() per dictation (cheap)."""

    name = "vosk"

    def __init__(self, model_dir: str | Path | None = None):
        from vosk import Model

        path = Path(model_dir) if model_dir else _default_model_dir()
        if not path.exists():
            raise FileNotFoundError(
                f"vosk model not found at {path} -- download {_MODEL_DIR_NAME}.zip "
                f"from https://alphacephei.com/vosk/models and unzip it there"
            )
        self._model = Model(str(path))

    def new_stream(self) -> VoskStream:
        from vosk import KaldiRecognizer

        rec = KaldiRecognizer(self._model, 16000)
        rec.SetWords(False)
        return VoskStream(rec)


def create_streaming_engine(cfg):
    """Best-effort: any failure disables live typing for the session without
    blocking dictation itself. `cfg` is accepted (unused today) so a future
    config knob doesn't change this function's call sites."""
    try:
        from vosk import SetLogLevel

        SetLogLevel(-1)  # silence vosk's C++ stderr logging
        return VoskStreamingEngine()
    except Exception:
        log.warning("streaming engine unavailable; live typing disabled", exc_info=True)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_stt_streaming.py -v`
Expected: PASS (all 5 tests). Note: these tests never import the real `vosk` package for the `VoskStream` tests (fake recognizer only); the two `create_streaming_engine` tests exercise the real import path and will return `None` on a machine without vosk installed/model downloaded, which is exactly the fallback behavior being tested.

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add caspr/stt_streaming.py tests/test_stt_streaming.py
git commit -m "feat(stt): add vosk-backed streaming transcriber for live typing"
```

---

### Task 5: `caspr/live_typing.py` — the session loop

**Files:**
- Create: `caspr/live_typing.py`
- Test: `tests/test_live_typing.py`

**Interfaces:**
- Consumes: `compute_correction(typed, target) -> (int, str)` from Task 2.
- Produces: `class LiveTypingSession(transcriber, type_text, backspace)` with `.feed_block(block)`, `.finish()`, `.cancel()`, `.run()`, and the `.typed_text` attribute — used by Task 7 (`app.py`).

`run()` blocks on an internal queue until `finish()`/`cancel()` is called — safe to call directly (synchronously) in tests since a test controls exactly what's enqueued before calling it.

- [ ] **Step 1: Write the failing tests**

```python
from caspr.live_typing import LiveTypingSession


class FakeTranscriber:
    def __init__(self, hypotheses):
        self._hyps = list(hypotheses)

    def feed(self, block):
        return self._hyps.pop(0) if self._hyps else None


def _session(hypotheses):
    typed_calls = []
    backspace_calls = []
    session = LiveTypingSession(
        FakeTranscriber(hypotheses),
        type_text=typed_calls.append,
        backspace=backspace_calls.append,
    )
    return session, typed_calls, backspace_calls


def test_applies_a_diff_for_each_new_hypothesis():
    session, typed, backspaces = _session(["meet", "meet at"])
    session.feed_block("block1")
    session.feed_block("block2")
    session.finish()
    session.run()
    assert typed == ["meet", " at"]
    assert backspaces == [0, 0]
    assert session.typed_text == "meet at"


def test_unchanged_hypothesis_is_a_noop():
    session, typed, backspaces = _session(["hello", None, "hello"])
    session.feed_block("b1")
    session.feed_block("b2")
    session.feed_block("b3")
    session.finish()
    session.run()
    assert typed == ["hello"]  # only the first, real change


def test_finish_leaves_typed_text_on_screen():
    session, typed, backspaces = _session(["hi"])
    session.feed_block("b1")
    session.finish()
    session.run()
    assert session.typed_text == "hi"
    assert backspaces == [0]  # no erasure on a normal finish


def test_cancel_erases_everything_typed_this_session():
    session, typed, backspaces = _session(["hello world"])
    session.feed_block("b1")
    session.cancel()
    session.run()
    assert backspaces[-1] == len("hello world")
    assert session.typed_text == ""


def test_cancel_with_nothing_typed_yet_does_not_backspace():
    session, typed, backspaces = _session([])
    session.cancel()
    session.run()
    assert backspaces == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_live_typing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'caspr.live_typing'`

- [ ] **Step 3: Implement**

```python
"""Coordinates one live-typing session: consumes audio blocks fed from the
audio callback thread, keeps a running streaming-ASR hypothesis, and keeps
the focused window's typed text in sync with it via backspace+retype.

Runs on a dedicated thread per dictation (started/joined by AppController) --
NOT the audio callback thread, so decode latency never risks dropping audio
blocks, and NOT the shared pipeline executor, since this loop must run
concurrently with the hold while that executor stays idle.
"""

from __future__ import annotations

import queue
from collections.abc import Callable

from .diff import compute_correction

_FINISH = object()
_CANCEL = object()


class LiveTypingSession:
    """One instance per dictation hold. `feed_block` is safe to call from the
    audio callback thread; `run` must be called on its own worker thread."""

    def __init__(self, transcriber, type_text: Callable[[str], None], backspace: Callable[[int], None]):
        self._transcriber = transcriber
        self._type_text = type_text
        self._backspace = backspace
        self._queue: queue.Queue = queue.Queue()
        self.typed_text = ""

    def feed_block(self, block) -> None:
        self._queue.put(block)

    def finish(self) -> None:
        """Normal end of hold: stop consuming new audio, leave typed_text on
        screen for the caller's release-time batch reconciliation."""
        self._queue.put(_FINISH)

    def cancel(self) -> None:
        """The dictation was discarded: erase everything this session typed."""
        self._queue.put(_CANCEL)

    def run(self) -> None:
        """Blocks until finish()/cancel(). Call on a dedicated thread."""
        while True:
            item = self._queue.get()
            if item is _FINISH:
                return
            if item is _CANCEL:
                if self.typed_text:
                    self._backspace(len(self.typed_text))
                    self.typed_text = ""
                return
            hypothesis = self._transcriber.feed(item)
            if not hypothesis or hypothesis == self.typed_text:
                continue
            backspaces, insert = compute_correction(self.typed_text, hypothesis)
            backspaces = min(backspaces, len(self.typed_text))  # hard safety clamp
            if backspaces:
                self._backspace(backspaces)
            if insert:
                self._type_text(insert)
            self.typed_text = hypothesis
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_live_typing.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add caspr/live_typing.py tests/test_live_typing.py
git commit -m "feat(live-typing): add LiveTypingSession diff-and-correct loop"
```

---

### Task 6: `Recorder.set_block_callback` — expose raw blocks

**Files:**
- Modify: `caspr/audio.py:47-103` (the `Recorder` class)

**Interfaces:**
- Produces: `Recorder.set_block_callback(cb: Callable[[np.ndarray], None] | None)` — used by Task 7 (`app.py`).

No test for this task — see Global Constraints (`Recorder`'s existing callback wiring, `on_level`, has no test either; it requires a real `sounddevice.InputStream`).

- [ ] **Step 1: Add the callback slot and wire it into the existing audio callback**

In `caspr/audio.py`, modify `Recorder.__init__` (currently lines 56-60):

```python
    def __init__(self, device: int | None = None, on_level=None):
        self._device = device
        self._on_level = on_level
        self._on_block = None
        self._blocks: list[np.ndarray] = []
        self._stream = None
```

Add a new method right after `set_device`:

```python
    def set_block_callback(self, cb) -> None:
        """`cb(block: np.ndarray)` is called with each raw ~100ms float32 block
        as it arrives, in addition to the normal on_level meter callback. Set
        to None to stop receiving blocks. Takes effect immediately, even for
        an in-flight recording."""
        self._on_block = cb
```

Modify the `callback` closure inside `start()` (currently lines 75-81) to also invoke it:

```python
        def callback(indata, frames, time_info, status):
            if status:
                log.warning("audio callback status: %s", status)
            block = indata[:, 0].copy()
            if len(self._blocks) < max_blocks:
                self._blocks.append(block)
            if self._on_level is not None:
                self._on_level(meter_level(block))
            if self._on_block is not None:
                self._on_block(block)
```

(Note: `block` is now computed once and reused for `self._blocks.append`, `meter_level`, and `self._on_block` instead of calling `indata[:, 0].copy()` / `indata[:, 0]` twice — a small simplification that falls out naturally here.)

- [ ] **Step 2: Run the full suite (additive change, nothing should break)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add caspr/audio.py
git commit -m "feat(audio): expose raw blocks via Recorder.set_block_callback"
```

---

### Task 7: `AppController` wiring

**Files:**
- Modify: `caspr/app.py`
- Test: Create `tests/test_app_live_typing.py`

**Interfaces:**
- Consumes: `create_streaming_engine(cfg)` (Task 4), `LiveTypingSession` (Task 5), `Recorder.set_block_callback` (Task 6), `inject.backspace` (Task 3), `compute_correction` (Task 2 — used directly in `_pipeline`'s reconciliation).
- Produces: `AppController._streaming_engine`, `AppController._live_session` (readable by tests/future code).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app_live_typing.py`:

```python
"""AppController integration: live typing during a hold, reconciled at release."""

from types import SimpleNamespace

import numpy as np
import pytest

import caspr.app
from caspr.app import AppController
from caspr.config import Config

SAMPLE = np.zeros(8000, dtype=np.float32)  # ~0.5s > MIN_SPEECH_SECONDS


class ImmediateExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)

    def shutdown(self, **kwargs):
        pass


class FakeRecorder:
    def __init__(self):
        self.started = 0
        self._block_cb = None

    def start(self):
        self.started += 1

    def stop(self):
        return SAMPLE

    def set_device(self, device):
        pass

    def set_block_callback(self, cb):
        self._block_cb = cb

    def feed(self, block):
        if self._block_cb is not None:
            self._block_cb(block)


class FakeStream:
    def __init__(self, hypotheses):
        self._hyps = list(hypotheses)

    def feed(self, block):
        return self._hyps.pop(0) if self._hyps else None


class FakeStreamingEngine:
    def __init__(self, hypotheses):
        self._hypotheses = hypotheses

    def new_stream(self):
        return FakeStream(self._hypotheses)


injected: list = []


@pytest.fixture
def controller(tmp_path, monkeypatch):
    c = AppController(Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db")
    c._executor.shutdown(wait=False, cancel_futures=True)
    c._executor = ImmediateExecutor()
    c._recorder = FakeRecorder()
    injected.clear()
    monkeypatch.setattr(caspr.app.inject, "inject_text", lambda text, mode: injected.append(("full", text)))
    monkeypatch.setattr(caspr.app.inject, "type_text", lambda text: injected.append(("type", text)))
    monkeypatch.setattr(caspr.app.inject, "backspace", lambda n: injected.append(("backspace", n)))
    monkeypatch.setattr(caspr.app.cleanup, "clean_text", lambda raw, **kw: raw)
    yield c


def _transcriber(text):
    return SimpleNamespace(transcribe=lambda audio, **kw: SimpleNamespace(text=text, infer_s=0.0))


def test_live_typing_diffs_each_hypothesis_as_it_arrives(controller):
    controller._transcriber = _transcriber("meet at six thirty")
    controller._streaming_engine = FakeStreamingEngine(["meet", "meet at", "meet at six thirty"])
    controller._begin_recording()
    for _ in range(3):
        controller._recorder.feed(np.zeros(1600, dtype=np.float32))
    controller._commit_recording()
    type_events = [e for kind, e in injected if kind == "type"]
    assert type_events[:2] == ["meet", " at"]
    assert all(kind != "full" for kind, _ in injected)  # never fell back to a full inject


def test_live_typing_reconciles_against_batch_result_on_release(controller, monkeypatch):
    controller._transcriber = _transcriber("meet at six thirty")
    monkeypatch.setattr(caspr.app.cleanup, "clean_text", lambda raw, **kw: "Meet at 6:30.")
    controller._streaming_engine = FakeStreamingEngine(["meet at six thirty"])
    controller._begin_recording()
    controller._recorder.feed(np.zeros(1600, dtype=np.float32))
    controller._commit_recording()
    assert ("type", "meet at six thirty") in injected  # live-typed first
    backspace_total = sum(n for kind, n in injected if kind == "backspace")
    assert backspace_total > 0  # release-time reconciliation corrected it
    assert injected[-1][0] == "type"  # ends with the corrected text typed in


def test_cancel_erases_live_typed_text(controller):
    controller._transcriber = _transcriber("hello")
    controller._streaming_engine = FakeStreamingEngine(["hello"])
    controller._begin_recording()
    controller._recorder.feed(np.zeros(1600, dtype=np.float32))
    controller._cancel_recording()
    assert ("backspace", len("hello")) in injected


def test_streaming_engine_unavailable_falls_back_to_full_inject_at_release(controller):
    controller._transcriber = _transcriber("plain text")
    controller._streaming_engine = None
    controller._begin_recording()
    assert controller._live_session is None
    controller._commit_recording()
    assert injected == [("full", "plain text")]


def test_clipboard_injection_mode_skips_live_typing(controller):
    controller._transcriber = _transcriber("plain text")
    controller.cfg.injection = "clipboard"
    controller._streaming_engine = FakeStreamingEngine(["plain"])
    controller._begin_recording()
    assert controller._live_session is None
    controller._recorder.feed(np.zeros(1600, dtype=np.float32))
    controller._commit_recording()
    assert injected == [("full", "plain text")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app_live_typing.py -v`
Expected: FAIL — `AttributeError: 'AppController' object has no attribute '_streaming_engine'` (or similar; the wiring doesn't exist yet).

- [ ] **Step 3: Implement the wiring**

In `caspr/app.py`, add imports (alongside the existing ones at the top):

```python
from .diff import compute_correction
from .live_typing import LiveTypingSession
```

In `AppController.__init__` (after `self._pending_exe: str | None = None`), add:

```python
        self._streaming_engine = None  # loaded in _load_model; None disables live typing
        self._live_session: LiveTypingSession | None = None
        self._live_thread: threading.Thread | None = None
```

In `_load_model`, after the line `self._transcriber = transcriber` (and before `name = getattr(...)`), add:

```python
            from . import stt_streaming

            self._streaming_engine = stt_streaming.create_streaming_engine(self.cfg)
```

Modify `_begin_recording` — after the existing `self._recorder.start()` call succeeds (i.e. inside the `try` block, right after `self._recorder.start()`), add:

```python
            if self._streaming_engine is not None and self.cfg.injection == "type":
                try:
                    stream = self._streaming_engine.new_stream()
                    self._live_session = LiveTypingSession(stream, inject.type_text, inject.backspace)
                    self._recorder.set_block_callback(self._live_session.feed_block)
                    self._live_thread = threading.Thread(target=self._live_session.run, daemon=True)
                    self._live_thread.start()
                except Exception:
                    log.warning("failed to start live typing this session", exc_info=True)
                    self._live_session = None
            else:
                self._live_session = None
```

Modify `_commit_recording` — replace:

```python
    def _commit_recording(self) -> None:
        with self._lock:
            if self._state != "recording":
                return
            self._state = "processing"
        audio = self._recorder.stop()
        self.state_changed.emit("processing", "")
        self._executor.submit(self._pipeline, audio)
```

with:

```python
    def _commit_recording(self) -> None:
        with self._lock:
            if self._state != "recording":
                return
            self._state = "processing"
        audio = self._recorder.stop()
        self._recorder.set_block_callback(None)
        if self._live_session is not None:
            self._live_session.finish()
            self._live_thread.join(timeout=5.0)
        self.state_changed.emit("processing", "")
        self._executor.submit(self._pipeline, audio)
```

Modify `_cancel_recording` — replace:

```python
    def _cancel_recording(self) -> None:
        """Stop and discard the current clip (a gesture tap, never a dictation)."""
        with self._lock:
            if self._state != "recording":
                return
            self._state = "idle"
        self._recorder.stop()
        self.state_changed.emit("idle", "")
```

with:

```python
    def _cancel_recording(self) -> None:
        """Stop and discard the current clip (a gesture tap, never a dictation)."""
        with self._lock:
            if self._state != "recording":
                return
            self._state = "idle"
        self._recorder.stop()
        self._recorder.set_block_callback(None)
        if self._live_session is not None:
            self._live_session.cancel()
            self._live_thread.join(timeout=5.0)
            self._live_session = None
        self.state_changed.emit("idle", "")
```

Finally, in `_pipeline`, replace the single line:

```python
            inject.inject_text(final, self.cfg.injection)
```

with:

```python
            if self._live_session is not None:
                backspaces, insert_text = compute_correction(self._live_session.typed_text, final)
                backspaces = min(backspaces, len(self._live_session.typed_text))
                if backspaces:
                    inject.backspace(backspaces)
                if insert_text:
                    inject.type_text(insert_text)
                self._live_session = None
            else:
                inject.inject_text(final, self.cfg.injection)
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app_live_typing.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all tests pass, including the pre-existing `tests/test_app_cleanup.py` tests (they never set `_streaming_engine`, so it defaults to `None` and they hit the unchanged `else: inject.inject_text(...)` branch — identical to today's behavior).

- [ ] **Step 6: Commit**

```bash
git add caspr/app.py tests/test_app_live_typing.py
git commit -m "feat(app): wire live typing into the dictation hold, reconciled at release"
```

---

### Task 8: Live/manual verification, then push

**Files:** none (verification only)

- [ ] **Step 1: Install vosk and the model in the real environment (if Task 1 used a throwaway venv/location, do it for real here)**

```bash
.venv/Scripts/python.exe -m pip install vosk
```

Confirm the model directory exists at `%APPDATA%\caspr-flow\models\vosk-model-small-en-us-0.15\` (downloaded in Task 1).

Add `vosk` to `pyproject.toml`'s dependencies (check how `groq`/`onnx-asr` are declared — likely under `[project.dependencies]` or an optional extra per Aadit's extras refactor; match that pattern) so a fresh `uv sync` installs it.

- [ ] **Step 2: Fully quit and relaunch caspr-app**

Exit via the tray icon (not just closing a window), then relaunch, so `_load_model` picks up the new streaming engine.

- [ ] **Step 3: Dictate a short phrase, watch it type live**

Hold the hotkey, say a few words, watch them appear on screen word-by-word instead of all at once after release.

- [ ] **Step 4: Dictate something the streaming engine likely mis-hears**

Say something with a number, name, or unusual word. Confirm the release-time reconciliation corrects it in one clean diff with no leftover wrong words on screen.

- [ ] **Step 5: Cancel a dictation mid-hold**

Trigger the cancel hotkey (or a short gesture tap) while live-typed text is on screen; confirm it's fully backspaced away.

- [ ] **Step 6: Confirm clipboard injection mode still works exactly as before**

In Settings, switch injection to "clipboard", dictate, confirm one full paste at release with no live typing attempted (no partial words appear mid-hold).

- [ ] **Step 7: Simulate streaming failure**

Temporarily rename the vosk model directory, relaunch, dictate — confirm dictation still works exactly as it does today (one full inject at release, no live typing, no crash, a warning in the logs).

- [ ] **Step 8: Push**

```bash
git push origin main
```
