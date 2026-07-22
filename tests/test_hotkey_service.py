"""HotkeyService: owns primary PTT + secondary action hotkeys, rebuilt live.

The keyboard hooks and PushToTalk are injected as fakes so these tests never
install a real global hook.
"""

from caspr.config import Config
from caspr.hotkey_service import HotkeyService


class FakePTT:
    def __init__(self, chord, on_press, on_release):
        self.chord = chord
        self.on_press = on_press
        self.on_release = on_release
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


class FakeKb:
    def __init__(self):
        self.added = []
        self.removed = []

    def add_hotkey(self, chord, cb, **kw):
        handle = (chord, cb)
        self.added.append(handle)
        return handle

    def remove_hotkey(self, handle):
        self.removed.append(handle)


class StubController:
    def on_ptt_press(self):
        pass

    def on_ptt_release(self):
        pass

    def toggle_dictation(self):
        pass

    def cancel_dictation(self):
        pass

    def mute_mic(self):
        pass

    def open_history(self):
        pass


def make_svc(cfg, controller=None):
    kb = FakeKb()
    ptts = []

    def factory(chord, on_press, on_release):
        p = FakePTT(chord, on_press, on_release)
        ptts.append(p)
        return p

    svc = HotkeyService(controller or StubController(), cfg, ptt_factory=factory, kb=kb)
    return svc, kb, ptts


def test_rearm_arms_primary_and_nonempty_secondaries():
    cfg = Config(
        hotkey="ctrl+windows",
        hotkey_toggle_dictation="ctrl+shift+d",
        hotkey_mute_mic="ctrl+shift+m",
    )
    svc, kb, ptts = make_svc(cfg)
    svc.rearm()
    assert ptts[-1].chord == "ctrl+windows"
    assert ptts[-1].started == 1
    assert {a[0] for a in kb.added} == {"ctrl+shift+d", "ctrl+shift+m"}  # empties skipped


def test_rearm_tears_down_previous_hooks():
    cfg = Config(hotkey="ctrl+windows", hotkey_toggle_dictation="ctrl+shift+d")
    svc, kb, ptts = make_svc(cfg)
    svc.rearm()
    svc.rearm()
    assert ptts[0].stopped == 1  # old primary torn down before rebuilding
    assert len(kb.removed) == 1  # old secondary removed
    assert len(ptts) == 2  # a fresh primary was built


def test_secondary_hotkey_invokes_controller_action():
    called = []

    class Rec(StubController):
        def toggle_dictation(self):
            called.append("toggle")

    cfg = Config(hotkey="ctrl+windows", hotkey_toggle_dictation="ctrl+shift+d")
    svc, kb, ptts = make_svc(cfg, controller=Rec())
    svc.rearm()
    _chord, cb = kb.added[0]
    cb()  # keyboard fires this on key-press
    assert called == ["toggle"]


def test_suspend_drops_all_hooks():
    cfg = Config(hotkey="ctrl+windows", hotkey_mute_mic="ctrl+shift+m")
    svc, kb, ptts = make_svc(cfg)
    svc.rearm()
    svc.suspend()
    assert ptts[-1].stopped == 1
    assert len(kb.removed) == 1
