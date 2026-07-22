"""Per-app tone selection: foreground exe → tone label."""

from caspr.context import foreground_exe, tone_for


def test_exact_exe_match():
    assert tone_for("slack.exe", {"slack.exe": "casual"}, "balanced") == "casual"


def test_substring_match():
    assert tone_for("slack.exe", {"slack": "casual"}, "balanced") == "casual"


def test_glob_match():
    assert tone_for("devenv.exe", {"dev*": "verbatim"}, "balanced") == "verbatim"


def test_case_insensitive():
    assert tone_for("SLACK.EXE", {"slack": "casual"}, "x") == "casual"


def test_no_match_returns_default():
    assert tone_for("notepad.exe", {"slack": "casual"}, "balanced") == "balanced"


def test_none_exe_returns_default():
    assert tone_for(None, {"slack": "casual"}, "balanced") == "balanced"


def test_empty_profiles_returns_default():
    assert tone_for("slack.exe", {}, "balanced") == "balanced"


def test_first_matching_profile_wins():
    profiles = {"slack": "casual", "slack.exe": "formal"}
    assert tone_for("slack.exe", profiles, "balanced") == "casual"


def test_foreground_exe_never_raises():
    # Real Win32 call; must degrade to None rather than crash the pipeline.
    result = foreground_exe()
    assert result is None or isinstance(result, str)
