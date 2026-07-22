"""Bridge payloads must be JSON-serializable and complete."""

import json

from caspr.app import AppController
from caspr.config import Config, load_config
from caspr.history import Entry
from caspr.ui.bridge_data import (
    apply_setting,
    bootstrap,
    dictionary_dict,
    entry_dict,
    history_list,
)

BOOT_KEYS = {
    "user", "state", "paused", "hotkey", "hotkey_pretty", "model", "device",
    "engine", "language", "injection", "pill_linger_s", "sound_cues",
    "input_device", "mics", "startup", "stats", "recent",
    "hotkey_toggle_dictation", "hotkey_toggle_dictation_pretty",
    "hotkey_cancel_dictation", "hotkey_cancel_dictation_pretty",
    "hotkey_mute_mic", "hotkey_mute_mic_pretty",
    "hotkey_open_history", "hotkey_open_history_pretty",
}


def test_entry_dict_is_json_safe():
    entry = Entry(id=7, ts=1_000.5, raw_text="raw", final_text="hello zzxqv", infer_s=0.1, total_s=0.4)
    d = entry_dict(entry, Config())
    json.dumps(d)  # must not raise
    assert d["id"] == 7 and d["text"] == "hello zzxqv"
    assert all(isinstance(span, list) and len(span) == 2 for span in d["spans"])
    assert d["spans"], "zzxqv should be flagged as unknown"


def test_history_list_searches_or_lists(tmp_path):
    controller = AppController(
        Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db"
    )
    try:
        controller.history.add("raw", "alpha note", 0.1, 0.2)
        controller.history.add("raw", "beta note", 0.1, 0.2)
        assert [e["text"] for e in history_list(controller)] == ["beta note", "alpha note"]
        assert [e["text"] for e in history_list(controller, "alpha")] == ["alpha note"]
        json.dumps(history_list(controller))
    finally:
        controller.shutdown()


def test_dictionary_dict_shape():
    cfg = Config(dictionary=["caspr"], replacements={"Adit": "Aadit"})
    d = dictionary_dict(cfg)
    json.dumps(d)
    assert d == {"terms": ["caspr"], "rules": [{"wrong": "Adit", "right": "Aadit"}]}


def _controller(tmp_path, monkeypatch):
    c = AppController(Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db")
    calls = []
    monkeypatch.setattr(c, "reload_model", lambda: calls.append("reload"))
    monkeypatch.setattr(c, "set_input_device", lambda d: calls.append(("mic", d)))
    return c, calls


def test_apply_setting_model_reloads_and_persists(tmp_path, monkeypatch):
    c, calls = _controller(tmp_path, monkeypatch)
    try:
        assert apply_setting(c, "model", "base") == "reload"
        assert calls == ["reload"]
        assert load_config(tmp_path / "cfg.json").model == "base"
    finally:
        c.shutdown()


def test_apply_setting_mic_and_language_coercion(tmp_path, monkeypatch):
    c, calls = _controller(tmp_path, monkeypatch)
    try:
        assert apply_setting(c, "input_device", 9) == "mic"
        assert calls == [("mic", 9)]
        # "" persists as None; language now reloads because it steers routing
        assert apply_setting(c, "language", "") == "reload"
        assert c.cfg.language is None
        assert apply_setting(c, "engine", "parakeet") == "reload"
        assert calls == [("mic", 9), "reload", "reload"]
        assert apply_setting(c, "input_device", None) == "mic"
        assert c.cfg.input_device is None
    finally:
        c.shutdown()


def test_apply_setting_rejects_unknown_and_bad_hotkey(tmp_path, monkeypatch):
    c, calls = _controller(tmp_path, monkeypatch)
    try:
        assert apply_setting(c, "not_a_key", 1) == ""
        assert apply_setting(c, "hotkey", "++") == ""
        assert c.cfg.hotkey == "ctrl+windows"  # untouched
        assert apply_setting(c, "hotkey", "ctrl+alt") == "hotkey"
        assert c.cfg.hotkey == "ctrl+alt"
        assert calls == []
    finally:
        c.shutdown()


def test_bootstrap_shape(tmp_path):
    controller = AppController(
        Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db"
    )
    try:
        controller.history.add("raw", "words here", 0.1, 0.3)
        boot = bootstrap(controller)
        json.dumps(boot)  # must not raise
        assert BOOT_KEYS <= set(boot)
        assert boot["hotkey_pretty"] == "Ctrl + Windows"
        assert boot["stats"]["today"] == 1
        assert boot["recent"][0]["text"] == "words here"
    finally:
        controller.shutdown()


def test_apply_setting_optional_hotkeys_accept_empty_and_valid(tmp_path, monkeypatch):
    c, calls = _controller(tmp_path, monkeypatch)
    try:
        assert apply_setting(c, "hotkey_mute_mic", "ctrl+alt+m") == "hotkey"
        assert c.cfg.hotkey_mute_mic == "ctrl+alt+m"
        assert apply_setting(c, "hotkey_mute_mic", "") == "hotkey"
        assert c.cfg.hotkey_mute_mic == ""
        assert apply_setting(c, "hotkey_cancel_dictation", "++") == ""
        assert c.cfg.hotkey_cancel_dictation == ""  # rejected, untouched
        assert calls == []
    finally:
        c.shutdown()


def test_bootstrap_includes_optional_hotkeys_unbound_by_default(tmp_path):
    controller = AppController(
        Config(), config_path=tmp_path / "cfg.json", history_path=tmp_path / "h.db"
    )
    try:
        boot = bootstrap(controller)
        assert boot["hotkey_mute_mic"] == ""
        assert boot["hotkey_mute_mic_pretty"] == ""
    finally:
        controller.shutdown()


def test_apply_setting_cleanup_fields_persist_and_coerce(tmp_path, monkeypatch):
    c, calls = _controller(tmp_path, monkeypatch)
    try:
        assert apply_setting(c, "cleanup_enabled", 0) == ""
        assert c.cfg.cleanup_enabled is False
        assert apply_setting(c, "groq_api_key", "  gsk_secret  ") == ""
        assert c.cfg.groq_api_key == "gsk_secret"
        assert apply_setting(c, "groq_model", "llama-3.3-70b-versatile") == ""
        assert c.cfg.groq_model == "llama-3.3-70b-versatile"
        assert apply_setting(c, "cleanup_context_count", "8") == ""
        assert c.cfg.cleanup_context_count == 8
        assert apply_setting(c, "tone_default", "formal") == ""
        assert c.cfg.tone_default == "formal"
        assert load_config(tmp_path / "cfg.json").groq_api_key == "gsk_secret"
        assert calls == []  # none of these hot-reload the model
    finally:
        c.shutdown()


def test_apply_setting_tone_profiles_validated(tmp_path, monkeypatch):
    c, calls = _controller(tmp_path, monkeypatch)
    try:
        assert apply_setting(c, "tone_profiles", {"slack.exe": "casual"}) == ""
        assert c.cfg.tone_profiles == {"slack.exe": "casual"}
        assert apply_setting(c, "tone_profiles", "not-a-dict") == ""  # rejected
        assert c.cfg.tone_profiles == {"slack.exe": "casual"}  # untouched
        assert apply_setting(c, "tone_profiles", {"x": 3}) == ""  # non-str value rejected
        assert c.cfg.tone_profiles == {"slack.exe": "casual"}
    finally:
        c.shutdown()


def test_apply_setting_double_tap_reconfigures_gesture(tmp_path, monkeypatch):
    c, calls = _controller(tmp_path, monkeypatch)
    try:
        assert apply_setting(c, "double_tap_ms", 350) == ""
        assert c.cfg.double_tap_ms == 350
        assert c._gestures._double_tap == 0.35  # live-applied, no restart
        assert apply_setting(c, "handsfree_double_tap", False) == ""
        assert c.cfg.handsfree_double_tap is False
    finally:
        c.shutdown()


def test_bootstrap_exposes_cleanup_without_leaking_key(tmp_path):
    controller = AppController(
        Config(groq_api_key="gsk_topsecret"),
        config_path=tmp_path / "cfg.json",
        history_path=tmp_path / "h.db",
    )
    try:
        boot = bootstrap(controller)
        json.dumps(boot)
        assert boot["cleanup_enabled"] is True
        assert boot["groq_api_key_set"] is True
        assert "groq_api_key" not in boot  # secret never echoed to the UI
        assert boot["groq_model"] == "llama-3.1-8b-instant"
        assert boot["cleanup_context_count"] == 10
        assert boot["tone_default"] == "balanced"
        assert boot["handsfree_double_tap"] is True
        assert boot["double_tap_ms"] == 400
        assert boot["tone_profiles"] == {}
    finally:
        controller.shutdown()
