"""AppController integration: cleanup in the pipeline + the double-tap gesture."""

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
    monkeypatch.setattr(caspr.app.inject, "inject_text", lambda text, mode: injected.append(text))
    yield c
    # no real executor/threads to clean up


injected: list[str] = []


def _transcriber(text):
    return SimpleNamespace(transcribe=lambda audio, **kw: SimpleNamespace(text=text, infer_s=0.0))


def test_pipeline_cleans_then_applies_replacements(controller, monkeypatch):
    injected.clear()
    controller._transcriber = _transcriber("meet at 5 30 actually 6 30 with adit")
    controller.cfg.groq_api_key = "gsk_x"
    controller.cfg.replacements = {"adit": "Aadit"}
    monkeypatch.setattr(
        caspr.app.cleanup, "clean_text", lambda raw, **kw: "Meet at 6:30 with adit."
    )
    controller._pipeline(SAMPLE)
    # cleanup ran first, then the whole-word replacement on the cleaned text
    assert injected == ["Meet at 6:30 with Aadit."]
    entry = controller.history.recent(1)[0]
    assert entry.raw_text == "meet at 5 30 actually 6 30 with adit"  # original STT
    assert entry.final_text == "Meet at 6:30 with Aadit."


def test_pipeline_passes_bounded_recent_context(controller, monkeypatch):
    injected.clear()
    for i in range(15):
        controller.history.add(f"raw{i}", f"final{i}", 0.0, 0.0)
    controller._transcriber = _transcriber("new text")
    controller.cfg.groq_api_key = "gsk_x"
    controller.cfg.cleanup_context_count = 10
    seen = {}
    monkeypatch.setattr(
        caspr.app.cleanup, "clean_text",
        lambda raw, **kw: seen.update(kw) or "cleaned",
    )
    controller._pipeline(SAMPLE)
    assert len(seen["recent"]) == 10  # bounded, not all 15


def test_pipeline_disabled_cleanup_injects_raw(controller, monkeypatch):
    injected.clear()
    controller._transcriber = _transcriber("plain raw text")
    controller.cfg.cleanup_enabled = False
    controller.cfg.groq_api_key = "gsk_x"
    # real clean_text, but disabled → returns raw without any network
    controller._pipeline(SAMPLE)
    assert injected == ["plain raw text"]


def test_load_model_skips_warmup_for_cloud(controller, monkeypatch):
    import caspr.stt as stt

    class Cloud:
        name, device = "groq", "cloud"

        def transcribe(self, *a, **k):
            raise AssertionError("cloud engine must not be warmed up with a billed call")

    monkeypatch.setattr(stt, "create_transcriber", lambda cfg: Cloud())
    controller._load_model()
    assert controller._transcriber is not None
    assert controller.state == "idle"


def test_gesture_hold_runs_a_dictation(controller, monkeypatch):
    subs = []
    monkeypatch.setattr(controller, "_pipeline", lambda audio: subs.append(audio))
    controller._state = "idle"
    controller.cfg.handsfree_double_tap = True
    clock = [0.0]
    monkeypatch.setattr(caspr.app.time, "monotonic", lambda: clock[0])
    controller.on_ptt_press()
    clock[0] = 0.5
    controller.on_ptt_release()  # held 0.5s → dictation
    assert controller._recorder.started == 1
    assert len(subs) == 1


def test_gesture_double_tap_toggles_handsfree(controller, monkeypatch):
    subs = []
    monkeypatch.setattr(controller, "_pipeline", lambda audio: subs.append(audio))
    controller._state = "idle"
    controller.cfg.handsfree_double_tap = True
    clock = [0.0]
    monkeypatch.setattr(caspr.app.time, "monotonic", lambda: clock[0])

    controller.on_ptt_press()  # tap 1
    clock[0] = 0.1
    controller.on_ptt_release()
    clock[0] = 0.2
    controller.on_ptt_press()  # tap 2, within window
    clock[0] = 0.3
    controller.on_ptt_release()
    assert controller.handsfree is True
    assert subs == []  # hands-free recording, nothing processed yet

    clock[0] = 2.0
    controller.on_ptt_press()  # stop tap
    clock[0] = 2.1
    controller.on_ptt_release()
    assert controller.handsfree is False
    assert len(subs) == 1


def test_handsfree_stop_resets_gesture_so_hold_works_again(controller, monkeypatch):
    injected.clear()
    controller._transcriber = _transcriber("hi")
    controller._state = "idle"
    controller.cfg.handsfree_double_tap = True
    clock = [0.0]
    monkeypatch.setattr(caspr.app.time, "monotonic", lambda: clock[0])

    controller.on_ptt_press()  # tap 1
    clock[0] = 0.1
    controller.on_ptt_release()
    clock[0] = 0.2
    controller.on_ptt_press()  # tap 2 → hands-free on
    clock[0] = 0.3
    controller.on_ptt_release()
    assert controller.handsfree is True

    clock[0] = 2.0
    controller.on_ptt_press()  # stop → real pipeline runs, injects, resets gesture
    assert controller.handsfree is False
    assert injected == ["hi"]
    assert controller._gestures._state == "idle"  # session_finished fired in _pipeline
    clock[0] = 2.05
    controller.on_ptt_release()  # swallowed / ignored, no phantom recording

    # A normal hold now works again — back to normal mode.
    injected.clear()
    clock[0] = 3.0
    controller.on_ptt_press()
    clock[0] = 3.5
    controller.on_ptt_release()
    assert injected == ["hi"]
