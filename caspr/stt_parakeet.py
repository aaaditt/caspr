"""English STT via NVIDIA Parakeet TDT 0.6B v2 (onnx-asr / onnxruntime).

Beats whisper-large-v3-turbo on English WER at a fraction of the latency.
English-only — the engine router (stt.pick_engine) keeps Whisper in charge of
Hindi and auto-detect. Parakeet has no initial-prompt biasing, so dictionary
hints don't apply on this path; replacement rules still do (downstream).
"""

from __future__ import annotations

import logging
import time

import numpy as np

from .stt import Transcription, _add_nvidia_dll_dirs

log = logging.getLogger(__name__)

_MODEL = "nemo-parakeet-tdt-0.6b-v2"


class ParakeetTranscriber:
    name = "parakeet"

    def __init__(self, device: str = "auto"):
        import onnx_asr  # heavy imports, keep them out of module load
        import onnxruntime as ort

        ort.set_default_logger_severity(3)  # per-node placement chatter off
        _add_nvidia_dll_dirs()
        available = ort.get_available_providers()
        want_cuda = device in ("auto", "cuda") and "CUDAExecutionProvider" in available
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if want_cuda
            else ["CPUExecutionProvider"]
        )
        t0 = time.perf_counter()
        self._model = onnx_asr.load_model(_MODEL, providers=providers)
        self.device = self._actual_device(fallback="cuda" if want_cuda else "cpu")
        if device == "cuda" and self.device != "cuda":
            log.warning("CUDA requested but onnxruntime fell back to CPU")
        log.info("loaded %s on %s in %.1fs", _MODEL, self.device, time.perf_counter() - t0)

    def _actual_device(self, fallback: str) -> str:
        """onnxruntime silently falls back to CPU when CUDA can't initialize —
        read what the encoder session actually runs on."""
        try:
            providers = self._model.asr._encoder.get_providers()
            return "cuda" if "CUDAExecutionProvider" in providers else "cpu"
        except AttributeError:  # onnx-asr internals moved; trust the request
            return fallback

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = None,
        initial_prompt: str | None = None,  # unsupported by Parakeet — ignored
    ) -> Transcription:
        t0 = time.perf_counter()
        text = self._model.recognize(audio.astype(np.float32), sample_rate=16000)
        return Transcription(str(text).strip(), "en", time.perf_counter() - t0)
