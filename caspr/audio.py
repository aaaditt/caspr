"""Microphone capture and audio utilities. All audio is 16 kHz mono float32 in [-1, 1]."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000


def meter_level(block: np.ndarray) -> float:
    """Map an audio block to a 0..1 level for the UI meter (full-scale sine ≈ 1.0)."""
    if block.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
    return min(1.0, rms * np.sqrt(2.0))


def load_wav_mono16k(path: Path | str) -> np.ndarray:
    """Load a 16 kHz mono 16-bit WAV as float32 in [-1, 1]."""
    with wave.open(str(path), "rb") as wf:
        if (wf.getframerate(), wf.getnchannels(), wf.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(
                f"{path}: expected 16kHz mono 16-bit WAV, got "
                f"{wf.getframerate()}Hz/{wf.getnchannels()}ch/{wf.getsampwidth() * 8}-bit"
            )
        frames = wf.readframes(wf.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
