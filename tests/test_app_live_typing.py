"""AppController integration: live typing during a hold, reconciled at release."""

from types import SimpleNamespace

import numpy as np
import pytest

import caspr.app
from caspr.app import AppController
from caspr.config import Config

SAMPLE = np.zeros(8000, dtype=np.float32)  # ~0.5s > MIN_SPEECH_SECONDS


class ImmediateExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)

    def shutdown(self, **kwargs):
        pass


class FakeRecorder:
    def __init__(self):
        self.started = 0
        self._block_cb = None

    def start(self):
        self.started += 1

    def stop(self):
        return SAMPLE

    def set_device(self, device):
        pass

    def set_block_callback(self, cb):
        self._block_cb = cb

    def feed(self, block):
        if self._block_cb is not None:
            self._block_cb(block)


class FakeStream:
    def __init__(self, hypotheses):
        self._hyps = list(hypotheses)

    def feed(self, block):
        return self._hyps.pop(0) if self._hyps else None


class FakeStreamingEngine:
    def __init__(self, hypotheses):
        self._hypotheses = hypotheses

    def new_stream(self):
        return FakeStream(self._hypotheses)


injected: list = []


@pytest.fixture
def controller(tmp_path, monkeypatch):
    c = AppController(Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db")
    c._executor.shutdown(wait=False, cancel_futures=True)
    c._executor = ImmediateExecutor()
    c._recorder = FakeRecorder()
    injected.clear()
    monkeypatch.setattr(caspr.app.inject, "inject_text", lambda text, mode: injected.append(("full", text)))
    monkeypatch.setattr(caspr.app.inject, "type_text", lambda text: injected.append(("type", text)))
    monkeypatch.setattr(caspr.app.inject, "backspace", lambda n: injected.append(("backspace", n)))
    monkeypatch.setattr(caspr.app.cleanup, "clean_text", lambda raw, **kw: raw)
    yield c


def _transcriber(text):
    return SimpleNamespace(transcribe=lambda audio, **kw: SimpleNamespace(text=text, infer_s=0.0))


def test_live_typing_diffs_each_hypothesis_as_it_arrives(controller):
    controller._transcriber = _transcriber("meet at six thirty")
    controller._streaming_engine = FakeStreamingEngine(["meet", "meet at", "meet at six thirty"])
    controller._state = "idle"
    controller._begin_recording()
    for _ in range(3):
        controller._recorder.feed(np.zeros(1600, dtype=np.float32))
    controller._commit_recording()
    type_events = [e for kind, e in injected if kind == "type"]
    assert type_events[:2] == ["meet", " at"]
    assert all(kind != "full" for kind, _ in injected)  # never fell back to a full inject


def test_live_typing_reconciles_against_batch_result_on_release(controller, monkeypatch):
    controller._transcriber = _transcriber("meet at six thirty")
    monkeypatch.setattr(caspr.app.cleanup, "clean_text", lambda raw, **kw: "Meet at 6:30.")
    controller._streaming_engine = FakeStreamingEngine(["meet at six thirty"])
    controller._state = "idle"
    controller._begin_recording()
    controller._recorder.feed(np.zeros(1600, dtype=np.float32))
    controller._commit_recording()
    assert ("type", "meet at six thirty") in injected  # live-typed first
    backspace_total = sum(n for kind, n in injected if kind == "backspace")
    assert backspace_total > 0  # release-time reconciliation corrected it
    assert injected[-1][0] == "type"  # ends with the corrected text typed in


def test_cancel_erases_live_typed_text(controller):
    controller._transcriber = _transcriber("hello")
    controller._streaming_engine = FakeStreamingEngine(["hello"])
    controller._state = "idle"
    controller._begin_recording()
    controller._recorder.feed(np.zeros(1600, dtype=np.float32))
    controller._cancel_recording()
    assert ("backspace", len("hello")) in injected


def test_streaming_engine_unavailable_falls_back_to_full_inject_at_release(controller):
    controller._transcriber = _transcriber("plain text")
    controller._streaming_engine = None
    controller._state = "idle"
    controller._begin_recording()
    assert controller._live_session is None
    controller._commit_recording()
    assert injected == [("full", "plain text")]


def test_clipboard_injection_mode_skips_live_typing(controller):
    controller._transcriber = _transcriber("plain text")
    controller.cfg.injection = "clipboard"
    controller._streaming_engine = FakeStreamingEngine(["plain"])
    controller._state = "idle"
    controller._begin_recording()
    assert controller._live_session is None
    controller._recorder.feed(np.zeros(1600, dtype=np.float32))
    controller._commit_recording()
    assert injected == [("full", "plain text")]
