"""Groq cloud STT: WAV encoding + the transcribe contract.

The Groq client is injected so these tests never hit the network.
"""

import io
import wave

import numpy as np
import pytest

from caspr.config import Config
from caspr.stt import create_transcriber, pick_engine
from caspr.stt_groq import GroqTranscriber, encode_wav


def test_encode_wav_roundtrips_pcm16_mono_16k():
    audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
    raw = encode_wav(audio, rate=16000)
    with wave.open(io.BytesIO(raw)) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
        assert w.getnframes() == 5


class _FakeTranscriptions:
    def __init__(self):
        self.seen = {}

    def create(self, **kwargs):
        self.seen = kwargs
        return type("Resp", (), {"text": "hello world"})()


class _FakeGroq:
    def __init__(self):
        self.audio = type("Audio", (), {})()
        self.audio.transcriptions = _FakeTranscriptions()


def test_transcribe_sends_wav_and_returns_text():
    fake = _FakeGroq()
    cfg = Config(groq_api_key="gsk_x", engine="groq")
    t = GroqTranscriber(cfg, client=fake)
    result = t.transcribe(np.zeros(1600, dtype=np.float32), language="en")
    assert result.text == "hello world"
    seen = fake.audio.transcriptions.seen
    assert seen["model"] == "whisper-large-v3-turbo"
    assert seen["language"] == "en"
    fname, data = seen["file"]
    assert fname.endswith(".wav") and isinstance(data, bytes)


def test_transcribe_requires_key():
    t = GroqTranscriber(Config(groq_api_key=""), client=object())
    with pytest.raises(RuntimeError):
        t.transcribe(np.zeros(1600, dtype=np.float32))


# -- routing (Task A3) -------------------------------------------------------


def test_pick_engine_groq_explicit_only():
    assert pick_engine("groq", "en") == "groq"
    assert pick_engine("groq", None) == "groq"
    assert pick_engine("auto", "en") != "groq"
    assert pick_engine("auto", None) != "groq"


def test_create_transcriber_builds_groq():
    cfg = Config(engine="groq", groq_api_key="gsk_x")
    t = create_transcriber(cfg)
    assert t.name == "groq" and t.device == "cloud"


def test_create_transcriber_falls_back_to_whisper_when_parakeet_missing(monkeypatch):
    import sys
    import types

    import caspr.stt as stt

    # Simulate the optional 'parakeet' extra not installed: importing the class fails.
    fake_mod = types.ModuleType("caspr.stt_parakeet")  # lacks ParakeetTranscriber
    monkeypatch.setitem(sys.modules, "caspr.stt_parakeet", fake_mod)

    built = {}

    class FakeWhisper:
        def __init__(self, model, device):
            built["model"] = model
            self.name, self.device = model, device

    monkeypatch.setattr(stt, "Transcriber", FakeWhisper)
    cfg = Config(engine="parakeet", model="base", device="cpu")
    t = create_transcriber(cfg)
    assert built["model"] == "base"  # fell back to Whisper instead of crashing
    assert t.name == "base"
