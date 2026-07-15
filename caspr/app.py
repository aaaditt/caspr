"""AppController: the state machine tying hotkeys → recorder → STT → paste.

States: loading → idle ⇄ recording → processing → idle (or error).

Threading model:
- Hotkey callbacks arrive on the keyboard hook thread.
- Model load + transcription + paste run on a single-worker executor (serialized).
- UI listens via Qt signals, which marshal cross-thread automatically.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PySide6.QtCore import QObject, Signal

from . import inject
from .audio import SAMPLE_RATE, Recorder
from .config import Config
from .dictionary import build_initial_prompt

log = logging.getLogger(__name__)

MIN_SPEECH_SECONDS = 0.3


class AppController(QObject):
    # state name, human-readable detail
    state_changed = Signal(str, str)
    input_level = Signal(float)

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self._transcriber = None
        self._recorder = Recorder(cfg.input_device, on_level=self.input_level.emit)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._lock = threading.Lock()
        self._state = "loading"
        self.paused = False

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        self._executor.submit(self._load_model)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self._set_state(self._state, "paused" if self.paused else "")

    def _load_model(self) -> None:
        from .stt import Transcriber  # heavy import off the main thread

        try:
            transcriber = Transcriber(self.cfg.model, self.cfg.device)
            # First CUDA inference compiles kernels; warm up on silence now so
            # the first real dictation isn't slow.
            transcriber.transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32))
            self._transcriber = transcriber
            self._set_state("idle", f"{self.cfg.model} on {transcriber.device}")
        except Exception as e:
            log.exception("model load failed")
            self._set_state("error", f"model load failed: {e}")

    # -- hotkey callbacks (keyboard hook thread) ---------------------------

    def on_ptt_press(self) -> None:
        with self._lock:
            if self._state != "idle" or self.paused:
                log.debug("press ignored in state=%s paused=%s", self._state, self.paused)
                return
            self._state = "recording"
        try:
            self._recorder.start()
            self.state_changed.emit("recording", "")
        except Exception as e:
            log.exception("could not start recording")
            self._set_state("idle", f"mic error: {e}")

    def on_ptt_release(self) -> None:
        with self._lock:
            if self._state != "recording":
                return
            self._state = "processing"
        audio = self._recorder.stop()
        self.state_changed.emit("processing", "")
        self._executor.submit(self._pipeline, audio)

    # -- pipeline (worker thread) ------------------------------------------

    def run_wav(self, audio: np.ndarray) -> None:
        """Debug path: run the pipeline on pre-recorded audio (--wav)."""
        with self._lock:
            self._state = "processing"
        self.state_changed.emit("processing", "")
        self._executor.submit(self._pipeline, audio)

    def _pipeline(self, audio: np.ndarray) -> None:
        try:
            if self._transcriber is None:
                self._set_state("error", "model not loaded")
                return
            audio_s = len(audio) / SAMPLE_RATE
            if audio_s < MIN_SPEECH_SECONDS:
                self._set_state("idle", "didn't catch that")
                return
            t0 = time.perf_counter()
            result = self._transcriber.transcribe(
                audio,
                language=self.cfg.language,
                initial_prompt=build_initial_prompt(self.cfg.dictionary),
            )
            if not result.text:
                self._set_state("idle", "didn't catch that")
                return
            inject.paste_text(result.text)
            total_s = time.perf_counter() - t0
            log.info(
                "dictation: %.1fs audio | infer %.2fs | total %.2fs | %r",
                audio_s, result.infer_s, total_s, result.text[:80],
            )
            self._set_state("idle", result.text[:60])
        except Exception as e:
            log.exception("pipeline failed")
            self._set_state("idle", f"error: {e}")

    # -- helpers -------------------------------------------------------------

    def _set_state(self, state: str, detail: str) -> None:
        with self._lock:
            self._state = state
        self.state_changed.emit(state, detail)
