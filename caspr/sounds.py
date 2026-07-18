"""Sound cues: short synthesized ticks for record start/stop.

WAVs are generated programmatically into %APPDATA%\\caspr-flow\\cues\\ on first
run — no binary assets in the repo. Playback prefers QSoundEffect (preloaded,
low-latency); winsound is the fallback for stripped Qt installs.
"""

from __future__ import annotations

import logging
import wave
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject

from .config import Config, default_config_path

log = logging.getLogger(__name__)

SAMPLE_RATE = 22050
_CUE_VERSION = 1  # bump when the synth changes so stale WAVs regenerate
_SWEEPS = {"start": (660.0, 880.0), "stop": (880.0, 560.0)}  # Hz, rising vs falling


def synth_cue(kind: str, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """An 80 ms sine sweep with a soft attack and decaying tail, float32 in [-1, 1]."""
    f0, f1 = _SWEEPS[kind]
    n = int(sample_rate * 0.08)
    t = np.arange(n) / sample_rate
    freqs = np.linspace(f0, f1, n)
    tone = np.sin(2 * np.pi * np.cumsum(freqs) / sample_rate)
    envelope = np.exp(-t * 40.0)
    attack = int(sample_rate * 0.004)
    envelope[:attack] *= np.linspace(0.0, 1.0, attack)
    return (0.5 * tone * envelope).astype(np.float32)


def ensure_cues(directory: Path | None = None) -> dict[str, Path]:
    """Write the cue WAVs if missing; return kind → path."""
    directory = Path(directory) if directory else default_config_path().parent / "cues"
    directory.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for kind in _SWEEPS:
        path = directory / f"{kind}_v{_CUE_VERSION}.wav"
        if not path.exists():
            _write_wav(path, synth_cue(kind))
        paths[kind] = path
    return paths


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(pcm.tobytes())


class SoundCues(QObject):
    """Plays the cues on state transitions; honors cfg.sound_cues live."""

    def __init__(self, cfg: Config, parent: QObject | None = None):
        super().__init__(parent)
        self._cfg = cfg
        self._paths = ensure_cues()
        self._effects = {}
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect

            for kind, path in self._paths.items():
                effect = QSoundEffect(self)  # preload now: first .play() is instant
                effect.setSource(QUrl.fromLocalFile(str(path)))
                effect.setVolume(0.3)
                self._effects[kind] = effect
        except ImportError:
            log.info("QtMultimedia unavailable; sound cues fall back to winsound")

    def on_state(self, state: str, _detail: str) -> None:
        if not self._cfg.sound_cues:
            return
        if state == "recording":
            self._play("start")
        elif state == "processing":
            self._play("stop")

    def _play(self, kind: str) -> None:
        effect = self._effects.get(kind)
        if effect is not None:
            effect.play()
            return
        try:
            import winsound

            winsound.PlaySound(
                str(self._paths[kind]),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except (ImportError, RuntimeError) as e:
            log.warning("sound cue failed: %s", e)
