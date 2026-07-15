"""Local speech-to-text via faster-whisper (CTranslate2).

Device "auto" tries CUDA first (GTX 1650: int8_float16) and falls back to CPU int8.
The NVIDIA pip wheels (nvidia-cublas-cu12, nvidia-cudnn-cu12) ship the DLLs
CTranslate2 needs on Windows; they must be registered via os.add_dll_directory
before the model loads.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class Transcription:
    text: str
    language: str
    infer_s: float  # wall-clock inference time


def _add_nvidia_dll_dirs() -> None:
    spec = find_spec("nvidia")
    if spec is None or not spec.submodule_search_locations:
        return
    for root in spec.submodule_search_locations:
        for bin_dir in Path(root).glob("*/bin"):
            os.add_dll_directory(str(bin_dir))


class Transcriber:
    def __init__(self, model_name: str = "large-v3-turbo", device: str = "auto"):
        from faster_whisper import WhisperModel  # heavy import, keep it out of module load

        attempts = {
            "auto": [("cuda", "int8_float16"), ("cpu", "int8")],
            "cuda": [("cuda", "int8_float16")],
            "cpu": [("cpu", "int8")],
        }[device]

        _add_nvidia_dll_dirs()
        last_error: Exception | None = None
        for dev, compute_type in attempts:
            try:
                t0 = time.perf_counter()
                self._model = WhisperModel(model_name, device=dev, compute_type=compute_type)
                self.device = dev
                log.info(
                    "loaded %s on %s/%s in %.1fs",
                    model_name, dev, compute_type, time.perf_counter() - t0,
                )
                return
            except Exception as e:  # CT2 raises RuntimeError/OSError on missing CUDA bits
                log.warning("failed to load %s on %s: %s", model_name, dev, e)
                last_error = e
        raise RuntimeError(f"could not load Whisper model {model_name!r}") from last_error

    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> Transcription:
        t0 = time.perf_counter()
        # Greedy decoding: ~2-3x faster than the beam_size=5 default and fine for
        # dictation. Not conditioning on previous text avoids repetition loops.
        segments, info = self._model.transcribe(
            audio,
            language=language,
            initial_prompt=initial_prompt,
            beam_size=1,
            condition_on_previous_text=False,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return Transcription(text, info.language, time.perf_counter() - t0)
