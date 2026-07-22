"""Double-tap hands-free gesture classifier.

Pure logic, clock injected via the timestamps passed to press()/release():
- a hold (>= hold_min) is a normal dictation → commit
- a short tap is discarded → cancel, and may begin a double-tap
- two short taps within double_tap_s → hands-free on; the next tap → hands-free off
"""

from caspr.hotkeys import GestureInterpreter


def _interp(hold_min_s=0.25, double_tap_s=0.4):
    log = []
    gi = GestureInterpreter(
        start=lambda: log.append("start"),
        commit=lambda: log.append("commit"),
        cancel=lambda: log.append("cancel"),
        handsfree=lambda active: log.append(f"hf:{active}"),
        hold_min_s=hold_min_s,
        double_tap_s=double_tap_s,
    )
    return gi, log


def test_hold_is_a_normal_dictation():
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.5)
    assert log == ["start", "commit"]


def test_hold_boundary_is_inclusive():
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.25)  # exactly hold_min → still a dictation
    assert log == ["start", "commit"]


def test_short_tap_is_discarded_not_committed():
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.1)
    assert log == ["start", "cancel"]


def test_double_tap_starts_handsfree():
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.1)   # tap 1
    gi.press(0.2)
    gi.release(0.3)   # tap 2, within 0.4s
    assert log == ["start", "cancel", "start", "cancel", "hf:True", "start"]


def test_tap_then_hold_is_a_dictation_not_handsfree():
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.1)   # tap 1
    gi.press(0.2)
    gi.release(0.6)   # held 0.4s ≥ hold_min → normal dictation
    assert log == ["start", "cancel", "start", "commit"]


def test_two_taps_too_far_apart_are_two_separate_gestures():
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.1)   # stray tap
    gi.press(1.0)     # 0.9s later — outside the window
    gi.release(1.5)   # a normal hold
    assert log == ["start", "cancel", "start", "commit"]
    assert "hf:True" not in log


def test_handsfree_stops_on_next_tap():
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.1)
    gi.press(0.2)
    gi.release(0.3)   # → hands-free on
    log.clear()
    gi.press(2.0)
    gi.release(2.1)   # any tap ends hands-free and processes the clip
    assert log == ["commit", "hf:False"]


def test_handsfree_stops_even_on_a_long_press():
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.1)
    gi.press(0.2)
    gi.release(0.3)   # hands-free on
    log.clear()
    gi.press(2.0)
    gi.release(5.0)   # long press still just stops it
    assert log == ["commit", "hf:False"]


def test_handsfree_stop_swallows_extra_taps_until_session_done():
    # Stopping deactivates on the press; the release and any follow-up taps
    # (e.g. a double-tap-to-stop) are swallowed so no phantom recording starts.
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.1)
    gi.press(0.2)
    gi.release(0.3)   # hands-free on
    log.clear()
    gi.press(2.0)     # stop → deactivate immediately
    assert log == ["commit", "hf:False"]
    gi.release(2.05)  # swallowed
    gi.press(2.1)     # 2nd tap of a double-tap-to-stop → swallowed
    gi.release(2.15)  # swallowed
    assert log == ["commit", "hf:False"]  # nothing new


def test_session_finished_returns_to_normal_mode():
    gi, log = _interp()
    gi.press(0.0)
    gi.release(0.1)
    gi.press(0.2)
    gi.release(0.3)   # hands-free on
    gi.press(2.0)     # stop
    gi.release(2.1)
    log.clear()
    gi.session_finished()  # controller: the clip's pipeline finished
    gi.press(3.0)          # normal hold works again
    gi.release(3.5)
    assert log == ["start", "commit"]


def test_session_finished_is_a_noop_when_idle():
    gi, log = _interp()
    gi.session_finished()
    assert log == []
    gi.press(0.0)
    gi.release(0.5)
    assert log == ["start", "commit"]
