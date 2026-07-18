"""Engine routing: Parakeet only when it's safe (English pinned or forced)."""

from caspr.stt import pick_engine


def test_auto_routes_english_to_parakeet():
    assert pick_engine("auto", "en") == "parakeet"


def test_auto_keeps_autodetect_and_hindi_on_whisper():
    assert pick_engine("auto", None) == "whisper"
    assert pick_engine("auto", "hi") == "whisper"


def test_explicit_engine_always_wins():
    assert pick_engine("parakeet", None) == "parakeet"
    assert pick_engine("parakeet", "hi") == "parakeet"
    assert pick_engine("whisper", "en") == "whisper"


def test_unknown_engine_falls_back_to_auto_rules():
    assert pick_engine("something-new", "en") == "parakeet"
    assert pick_engine("something-new", None) == "whisper"
