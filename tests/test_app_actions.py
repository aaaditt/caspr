"""AppController secondary actions driven by the hotkey service."""

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
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1
        return SAMPLE

    def set_device(self, device):
        pass


@pytest.fixture
def controller(tmp_path, monkeypatch):
    c = AppController(Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db")
    c._executor.shutdown(wait=False, cancel_futures=True)
    c._executor = ImmediateExecutor()
    c._recorder = FakeRecorder()
    monkeypatch.setattr(caspr.app.inject, "inject_text", lambda text, mode: None)
    yield c


def test_toggle_dictation_starts_then_commits(controller, monkeypatch):
    subs = []
    monkeypatch.setattr(controller, "_pipeline", lambda audio: subs.append(audio))
    controller._state = "idle"
    controller.toggle_dictation()
    assert controller.state == "recording"
    assert controller._recorder.started == 1
    controller.toggle_dictation()
    assert len(subs) == 1  # committed the clip


def test_toggle_dictation_noop_while_processing(controller):
    controller._state = "processing"
    controller.toggle_dictation()
    assert controller.state == "processing"


def test_cancel_dictation_discards(controller):
    controller._state = "recording"
    controller._recorder.start()
    controller.cancel_dictation()
    assert controller.state == "idle"
    assert controller._recorder.stopped == 1


def test_mute_mic_toggles_pause(controller):
    assert controller.paused is False
    controller.mute_mic()
    assert controller.paused is True
    controller.mute_mic()
    assert controller.paused is False


def test_open_history_emits_signal(controller):
    seen = []
    controller.open_history_requested.connect(lambda: seen.append(True))
    controller.open_history()
    assert seen == [True]
