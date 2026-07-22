"""Cloud speech-to-text via Groq's Whisper API — no local model, no CUDA.

Only used when the user explicitly selects ``engine="groq"``; ``auto``/local
engines never send audio off-machine. Shares the engine contract from ``stt``:
``.transcribe(audio, language=, initial_prompt=) -> Transcription`` plus
``.name``/``.device``.
"""

from __future__ import annotations

import io
import time
import wave

import numpy as np

from .stt import Transcription


def encode_wav(audio: np.ndarray, rate: int = 16000) -> bytes:
    """float32 [-1, 1] mono → 16-bit PCM WAV bytes, in memory (stdlib only)."""
    pcm = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
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
        self._key = (cfg.groq_api_key or "").strip()
        # A blank key is a setup error, surfaced when a dictation actually runs.
        self._error = (
            "" if self._key else "set your Groq API key in Settings to use cloud transcription"
        )
        self._client = client

    def _ensure_client(self):
        if self._error:
            raise RuntimeError(self._error)
        if self._client is None:
            from groq import Groq  # lazy: app runs without the SDK until cloud STT is used

            self._client = Groq(api_key=self._key, timeout=self._timeout, max_retries=0)
        return self._client

    def transcribe(self, audio, language=None, initial_prompt=None) -> Transcription:
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
