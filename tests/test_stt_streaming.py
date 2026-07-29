"""Streaming STT wrapper: unit-tested via a fake vosk recognizer (no real
vosk/model download needed — same injection pattern as GroqTranscriber's
`client=` param in stt_groq.py)."""

import numpy as np

from caspr.stt_streaming import VoskStream, create_streaming_engine


class FakeRecognizer:
    """Duck-types vosk.KaldiRecognizer's 3 methods this module calls."""

    def __init__(self, partials: list[str], final: str):
        self._partials = list(partials)
        self._final = final
        self.fed_pcm: list[bytes] = []

    def AcceptWaveform(self, pcm: bytes) -> bool:
        self.fed_pcm.append(pcm)
        return False

    def PartialResult(self) -> str:
        import json

        partial = self._partials.pop(0) if self._partials else ""
        return json.dumps({"partial": partial})

    def FinalResult(self) -> str:
        import json

        return json.dumps({"text": self._final})


def test_vosk_stream_returns_hypothesis_only_when_it_changes():
    rec = FakeRecognizer(partials=["hello", "hello", "hello world"], final="hello world")
    stream = VoskStream(rec)
    block = np.zeros(1600, dtype=np.float32)
    assert stream.feed(block) == "hello"
    assert stream.feed(block) is None  # unchanged partial -> no update
    assert stream.feed(block) == "hello world"


def test_vosk_stream_converts_float32_to_int16_pcm():
    rec = FakeRecognizer(partials=["x"], final="x")
    stream = VoskStream(rec)
    block = np.array([1.0, -1.0, 0.0], dtype=np.float32)
    stream.feed(block)
    pcm = rec.fed_pcm[0]
    values = np.frombuffer(pcm, dtype="<i2")
    assert values[0] == 32767  # +1.0 clamped to int16 max
    assert values[1] == -32767  # -1.0 -> int16 min-ish (via clip then scale)
    assert values[2] == 0


def test_vosk_stream_finalize_returns_final_result_text():
    rec = FakeRecognizer(partials=[], final="the final text")
    stream = VoskStream(rec)
    assert stream.finalize() == "the final text"


def test_create_streaming_engine_returns_none_when_vosk_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "vosk":
            raise ImportError("no vosk installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from caspr.config import Config

    assert create_streaming_engine(Config()) is None


def test_vosk_streaming_engine_raises_when_model_dir_missing(tmp_path):
    import pytest

    from caspr.stt_streaming import VoskStreamingEngine

    with pytest.raises(FileNotFoundError):
        VoskStreamingEngine(model_dir=tmp_path / "does-not-exist")
