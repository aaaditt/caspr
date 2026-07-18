"""Microphone capture and audio utilities. All audio is 16 kHz mono float32 in [-1, 1]."""

from __future__ import annotations

import logging
import wave
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


def list_input_devices() -> list[tuple[int, str]]:
    """Input devices as (global index, name). Filtered to the WASAPI host API so
    each mic appears once (PortAudio lists MME/DirectSound duplicates too);
    global indices remain valid InputStream device args."""
    import sounddevice as sd  # deferred so unit tests don't need PortAudio

    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        wasapi = next(
            (i for i, api in enumerate(hostapis) if "wasapi" in api["name"].lower()),
            None,
        )
        return [
            (i, d["name"])
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0 and (wasapi is None or d["hostapi"] == wasapi)
        ]
    except Exception as e:
        log.warning("could not enumerate input devices: %s", e)
        return []


def meter_level(block: np.ndarray) -> float:
    """Map an audio block to a 0..1 level for the UI meter (full-scale sine ≈ 1.0)."""
    if block.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
    return min(1.0, rms * np.sqrt(2.0))


class Recorder:
    """Collects mic audio between start() and stop(). One recording at a time.

    on_level (optional) is called from the audio callback thread with a 0..1
    meter value per block — keep it cheap and thread-safe (e.g. emit a Qt signal).
    """

    MAX_SECONDS = 120  # safety cap so a stuck key can't grow memory forever

    def __init__(self, device: int | None = None, on_level=None):
        self._device = device
        self._on_level = on_level
        self._blocks: list[np.ndarray] = []
        self._stream = None

    def set_device(self, device: int | None) -> None:
        """Takes effect at the next start(); an in-flight recording finishes
        on the old device."""
        self._device = device

    def start(self) -> None:
        import sounddevice as sd  # deferred so unit tests don't need PortAudio

        if self._stream is not None:
            return
        self._blocks = []
        max_blocks = self.MAX_SECONDS * 10  # ~100ms blocks

        def callback(indata, frames, time_info, status):
            if status:
                log.warning("audio callback status: %s", status)
            if len(self._blocks) < max_blocks:
                self._blocks.append(indata[:, 0].copy())
            if self._on_level is not None:
                self._on_level(meter_level(indata[:, 0]))

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=SAMPLE_RATE // 10,
            device=self._device,
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._blocks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(self._blocks)
        self._blocks = []
        return audio


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
