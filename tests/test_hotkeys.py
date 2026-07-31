from caspr.hotkeys import ChordRecorder, ClickHoldGesture, PushToTalk, canonical_key, parse_chord


def test_parse_chord_splits_and_normalizes():
    assert parse_chord("Ctrl + Windows") == ["ctrl", "windows"]
    assert parse_chord("right ctrl") == ["right ctrl"]
    assert parse_chord("ctrl++") == ["ctrl"]


def _ptt(chord="ctrl+windows"):
    events = []
    ptt = PushToTalk(chord, lambda: events.append("press"), lambda: events.append("release"))
    return ptt, events


def test_full_chord_fires_press_once():
    ptt, events = _ptt()
    ptt._handle_down("ctrl")
    assert events == []  # partial chord: nothing yet
    ptt._handle_down("windows")
    assert events == ["press"]
    ptt._handle_down("windows")  # OS key auto-repeat
    ptt._handle_down("ctrl")
    assert events == ["press"]


def test_any_key_up_releases_once():
    ptt, events = _ptt()
    ptt._handle_down("ctrl")
    ptt._handle_down("windows")
    ptt._handle_up("ctrl")
    assert events == ["press", "release"]
    ptt._handle_up("windows")  # second key up: no double release
    assert events == ["press", "release"]


def test_partial_press_then_release_fires_nothing():
    ptt, events = _ptt()
    ptt._handle_down("ctrl")
    ptt._handle_up("ctrl")
    assert events == []


def test_single_key_chord_still_works():
    ptt, events = _ptt("right ctrl")
    ptt._handle_down("right ctrl")
    ptt._handle_up("right ctrl")
    assert events == ["press", "release"]


def test_canonical_key_collapses_sides():
    assert canonical_key("left windows") == "windows"
    assert canonical_key("Right Ctrl") == "ctrl"
    assert canonical_key("space") == "space"


def test_recorder_modifier_only_chord_finalizes_on_release():
    r = ChordRecorder()
    r.feed("down", "ctrl")
    r.feed("down", "left windows")
    assert r.chord is None  # still held
    r.feed("up", "ctrl")
    assert r.chord is None  # one key still down
    r.feed("up", "left windows")
    assert r.chord == "ctrl+windows"


def test_recorder_modifier_plus_key_finalizes_at_keydown():
    r = ChordRecorder()
    r.feed("down", "ctrl")
    r.feed("down", "space")
    assert r.chord == "ctrl+space"  # no clean release needed


def test_recorder_canonical_modifier_order():
    r = ChordRecorder()
    r.feed("down", "left windows")  # windows first…
    r.feed("down", "ctrl")
    r.feed("up", "left windows")
    r.feed("up", "ctrl")
    assert r.chord == "ctrl+windows"  # …but ctrl leads in the chord string


def test_recorder_single_plain_key():
    r = ChordRecorder()
    r.feed("down", "f9")
    r.feed("up", "f9")
    assert r.chord == "f9"


def test_recorder_up_without_down_yields_nothing():
    r = ChordRecorder()
    r.feed("up", "ctrl")
    assert r.chord is None


def test_recorder_frozen_after_finalizing():
    r = ChordRecorder()
    r.feed("down", "ctrl")
    r.feed("down", "space")
    r.feed("down", "alt")  # after the chord is set, further input is ignored
    assert r.chord == "ctrl+space"


def test_recorder_held_reports_live_keys_in_order():
    r = ChordRecorder()
    r.feed("down", "right windows")
    r.feed("down", "ctrl")
    assert r.held == ["ctrl", "windows"]


def _click_gesture():
    events = []
    g = ClickHoldGesture(
        start=lambda: events.append("start"), commit=lambda: events.append("commit")
    )
    return g, events


def test_hold_commits_on_release_after_hold_min():
    g, events = _click_gesture()
    g.press(0.0)
    assert events == ["start"]
    g.release(0.30)  # >= 0.25 default hold_min
    assert events == ["start", "commit"]


def test_quick_click_leaves_session_open():
    g, events = _click_gesture()
    g.press(0.0)
    g.release(0.10)  # < hold_min
    assert events == ["start"]  # no commit -- stays recording


def test_second_press_of_any_length_closes_open_session():
    g, events = _click_gesture()
    g.press(0.0)
    g.release(0.10)  # opens the session
    g.press(5.0)  # any later press closes it immediately, on press
    assert events == ["start", "commit"]
    g.release(5.05)  # the stop-click's own release is a no-op
    assert events == ["start", "commit"]


def test_hold_min_boundary_exactly_at_threshold_commits():
    g, events = _click_gesture()
    g.press(0.0)
    g.release(0.25)  # exactly hold_min: >= means "commit now"
    assert events == ["start", "commit"]


def test_extra_press_while_already_pressed_is_ignored():
    g, events = _click_gesture()
    g.press(0.0)
    g.press(0.05)  # stray extra down event while already pressed
    assert events == ["start"]
    g.release(0.30)
    assert events == ["start", "commit"]
