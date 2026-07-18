"""Model hot-reload state machine: immediate when idle, deferred mid-recording."""

from types import SimpleNamespace

import numpy as np
import pytest

import caspr.stt
from caspr.app import AppController
from caspr.config import Config


class FakeTranscriber:
    def __init__(self, model, device):
        self.model = model
        self.device = "cpu"

    def transcribe(self, audio, **kwargs):
        return SimpleNamespace(text="", infer_s=0.0)


class ImmediateExecutor:
    """Runs submitted jobs synchronously so tests are deterministic."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)

    def shutdown(self, **kwargs):
        pass


@pytest.fixture
def controller(tmp_path, monkeypatch):
    monkeypatch.setattr(caspr.stt, "Transcriber", FakeTranscriber)
    c = AppController(
        Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db"
    )
    c._executor.shutdown(wait=False, cancel_futures=True)
    c._executor = ImmediateExecutor()
    yield c


def test_reload_while_idle_runs_immediately(controller):
    states = []
    controller.state_changed.connect(lambda s, d: states.append(s))
    controller._state = "idle"
    controller.cfg.model = "base"
    controller.reload_model()
    assert states == ["loading", "idle"]
    assert controller._transcriber.model == "base"


def test_reload_while_recording_is_deferred(controller):
    states = []
    controller.state_changed.connect(lambda s, d: states.append(s))
    controller._state = "recording"
    controller.reload_model()
    assert states == []  # nothing happened yet
    assert controller._reload_pending is True
    assert controller._transcriber is None


def test_deferred_reload_drains_after_pipeline(controller):
    controller._state = "recording"
    controller.reload_model()
    states = []
    controller.state_changed.connect(lambda s, d: states.append(s))
    controller._pipeline(np.zeros(100, dtype=np.float32))  # too short → early return
    assert controller._reload_pending is False
    assert "loading" in states
    assert states[-1] == "idle"
    assert controller._transcriber is not None


def test_failed_model_load_emits_notification(controller, monkeypatch):
    def boom(model, device):
        raise RuntimeError("no such model")

    monkeypatch.setattr(caspr.stt, "Transcriber", boom)
    notifications = []
    controller.notify.connect(lambda title, body: notifications.append((title, body)))
    controller._state = "idle"
    controller.reload_model()
    assert controller._state == "error"
    assert notifications and "model" in notifications[0][0]
