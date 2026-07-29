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
