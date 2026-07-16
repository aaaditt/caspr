from caspr.hotkeys import PushToTalk, parse_chord


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
