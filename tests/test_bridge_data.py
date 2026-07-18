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
