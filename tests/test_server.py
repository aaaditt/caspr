"""Server (Electron backend) re-arms hotkeys live on a hotkey setting change."""

from caspr.app import AppController
from caspr.config import Config
from caspr.server import JsonWsServer


class FakeService:
    def __init__(self):
        self.rearmed = 0

    def rearm(self):
        self.rearmed += 1


def _server(tmp_path, svc):
    controller = AppController(
        Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db"
    )
    return controller, JsonWsServer(controller, service=svc)


def test_set_setting_hotkey_rearms(tmp_path):
    svc = FakeService()
    controller, server = _server(tmp_path, svc)
    try:
        reply = server._handle_request(
            {"type": "set_setting", "key": "hotkey_mute_mic", "value": "ctrl+alt+m"}
        )
        assert reply["result"] == "hotkey"
        assert svc.rearmed == 1
    finally:
        controller.shutdown()


def test_set_setting_nonhotkey_does_not_rearm(tmp_path):
    svc = FakeService()
    controller, server = _server(tmp_path, svc)
    try:
        server._handle_request({"type": "set_setting", "key": "sound_cues", "value": False})
        assert svc.rearmed == 0
    finally:
        controller.shutdown()
