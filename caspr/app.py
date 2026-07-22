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

from . import cleanup, context, inject
from .audio import SAMPLE_RATE, Recorder
from .config import Config, save_config
from .dictionary import build_initial_prompt
from .history import History
from .hotkeys import GestureInterpreter
from .replacements import apply_replacements
from .spellcheck import flag_unknown_words

log = logging.getLogger(__name__)

MIN_SPEECH_SECONDS = 0.3
# A press shorter than this is a "tap" (gesture), not a dictation hold.
HOLD_MIN_SECONDS = 0.25


class AppController(QObject):
    # state name, human-readable detail
    state_changed = Signal(str, str)
    input_level = Signal(float)
    # final injected text, flagged spans (list[tuple[int, int]])
    dictation_done = Signal(str, object)
    paused_changed = Signal(bool)
    notify = Signal(str, str)  # title, body — surfaced as a tray notification

    def __init__(self, cfg: Config, config_path=None, history_path=None):
        super().__init__()
        self.cfg = cfg
        self.config_path = config_path
        self.history = History(history_path)
        self._transcriber = None
        self._recorder = Recorder(cfg.input_device, on_level=self.input_level.emit)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._lock = threading.Lock()
        self._state = "loading"
        self._reload_pending = False
        self.paused = False
        self.handsfree = False
        self._pending_exe: str | None = None  # foreground app captured at record start
        self._gestures = GestureInterpreter(
            start=self._begin_recording,
            commit=self._commit_recording,
            cancel=self._cancel_recording,
            handsfree=self._set_handsfree,
            hold_min_s=HOLD_MIN_SECONDS,
            double_tap_s=cfg.double_tap_ms / 1000,
        )

    # -- lifecycle --------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    def start(self) -> None:
        self._executor.submit(self._load_model)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self._set_state(self._state, "paused" if self.paused else "")
        self.paused_changed.emit(self.paused)

    def reload_model(self) -> None:
        """Swap to cfg.model/cfg.device without a restart. Safe mid-transcription:
        the single-worker executor serializes the reload behind in-flight jobs.
        Mid-recording it is deferred until that dictation's pipeline finishes."""
        with self._lock:
            if self._state == "recording":
                self._reload_pending = True
                return
        self._set_state("loading", f"loading {self.cfg.model}…")
        self._executor.submit(self._load_model)

    def set_input_device(self, device: int | None) -> None:
        self._recorder.set_device(device)

    # -- learning (explicit user actions only) -----------------------------

    def learn_term(self, term: str) -> None:
        term = term.strip()
        if term and term not in self.cfg.dictionary:
            self.cfg.dictionary.append(term)
            save_config(self.cfg, self.config_path)
            log.info("dictionary += %r", term)

    def learn_replacement(self, wrong: str, right: str) -> None:
        wrong, right = wrong.strip(), right.strip()
        if wrong and right:
            self.cfg.replacements[wrong] = right
            save_config(self.cfg, self.config_path)
            log.info("replacement %r -> %r", wrong, right)

    def forget_term(self, term: str) -> None:
        if term in self.cfg.dictionary:
            self.cfg.dictionary.remove(term)
            save_config(self.cfg, self.config_path)

    def forget_replacement(self, wrong: str) -> None:
        if self.cfg.replacements.pop(wrong, None) is not None:
            save_config(self.cfg, self.config_path)

    def _load_model(self) -> None:
        from . import stt  # heavy import off the main thread

        # Free the old model first: 4 GB VRAM can't hold two at once on reload.
        self._transcriber = None
        try:
            transcriber = stt.create_transcriber(self.cfg)
            # First CUDA inference compiles kernels; warm up on silence now so
            # the first real dictation isn't slow. Cloud engines have nothing to
            # compile — a warm-up would just be a wasted, billed API request.
            if getattr(transcriber, "device", "") != "cloud":
                transcriber.transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32))
            flag_unknown_words("warmup", [])  # wordfreq loads its data lazily
            self._transcriber = transcriber
            name = getattr(transcriber, "name", self.cfg.model)
            self._set_state("idle", f"{name} on {transcriber.device}")
        except Exception as e:
            log.exception("model load failed")
            self._set_state("error", f"model load failed: {e}")
            self.notify.emit("caspr can't load the model", str(e))

    # -- hotkey callbacks (keyboard hook thread) ---------------------------

    def on_ptt_press(self) -> None:
        # The gesture layer distinguishes hold (dictation) from double-tap
        # (hands-free); when disabled, a press begins recording immediately.
        if self.cfg.handsfree_double_tap:
            self._gestures.press(time.monotonic())
        else:
            self._begin_recording()

    def on_ptt_release(self) -> None:
        if self.cfg.handsfree_double_tap:
            self._gestures.release(time.monotonic())
        else:
            self._commit_recording()

    def _begin_recording(self) -> None:
        with self._lock:
            if self._state != "idle" or self.paused:
                log.debug("press ignored in state=%s paused=%s", self._state, self.paused)
                return
            self._state = "recording"
        self._pending_exe = context.foreground_exe()  # for per-app tone
        try:
            self._recorder.start()
            self.state_changed.emit("recording", "hands-free" if self.handsfree else "")
        except Exception as e:
            log.exception("could not start recording")
            self._set_state("idle", f"mic error: {e}")
            self.notify.emit("Microphone error", str(e))

    def _commit_recording(self) -> None:
        with self._lock:
            if self._state != "recording":
                return
            self._state = "processing"
        audio = self._recorder.stop()
        self.state_changed.emit("processing", "")
        self._executor.submit(self._pipeline, audio)

    def _cancel_recording(self) -> None:
        """Stop and discard the current clip (a gesture tap, never a dictation)."""
        with self._lock:
            if self._state != "recording":
                return
            self._state = "idle"
        self._recorder.stop()
        self.state_changed.emit("idle", "")

    def _set_handsfree(self, active: bool) -> None:
        self.handsfree = active

    def reconfigure_gestures(self) -> None:
        """Rebuild the gesture interpreter after a hands-free setting change."""
        self._gestures = GestureInterpreter(
            start=self._begin_recording,
            commit=self._commit_recording,
            cancel=self._cancel_recording,
            handsfree=self._set_handsfree,
            hold_min_s=HOLD_MIN_SECONDS,
            double_tap_s=self.cfg.double_tap_ms / 1000,
        )

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
            # AI cleanup (self-correction, fillers, punctuation) before the user's
            # literal replacement rules, so those still apply to the cleaned text.
            recent = [e.final_text for e in self.history.recent(self.cfg.cleanup_context_count)]
            tone = context.tone_for(self._pending_exe, self.cfg.tone_profiles, self.cfg.tone_default)
            t_clean = time.perf_counter()
            cleaned = cleanup.clean_text(
                result.text,
                recent=recent,
                glossary=self.cfg.dictionary,
                tone=tone,
                cfg=self.cfg,
            )
            cleanup_s = time.perf_counter() - t_clean
            final = apply_replacements(cleaned, self.cfg.replacements)
            inject.inject_text(final, self.cfg.injection)
            total_s = time.perf_counter() - t0
            spans = flag_unknown_words(
                final, self.cfg.dictionary, self.cfg.flag_zipf_threshold
            )
            self.history.add(result.text, final, result.infer_s, total_s)
            log.info(
                "dictation: %.1fs audio | infer %.2fs | clean %.2fs | total %.2fs | %r",
                audio_s, result.infer_s, cleanup_s, total_s, final[:80],
            )
            self._set_state("idle", final[:60])
            self.dictation_done.emit(final, spans)
        except Exception as e:
            log.exception("pipeline failed")
            self._set_state("idle", f"error: {e}")
            self.notify.emit("Dictation failed", str(e))
        finally:
            if self._reload_pending:  # model change requested mid-recording
                self._reload_pending = False
                self._set_state("loading", f"loading {self.cfg.model}…")
                self._executor.submit(self._load_model)

    # -- helpers -------------------------------------------------------------

    def _set_state(self, state: str, detail: str) -> None:
        with self._lock:
            self._state = state
        self.state_changed.emit(state, detail)
