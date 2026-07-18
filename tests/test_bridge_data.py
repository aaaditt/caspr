"""Bridge payloads must be JSON-serializable and complete."""

import json

from caspr.app import AppController
from caspr.config import Config
from caspr.history import Entry
from caspr.ui.bridge_data import bootstrap, dictionary_dict, entry_dict, history_list

BOOT_KEYS = {
    "user", "state", "paused", "hotkey", "hotkey_pretty", "model", "device",
    "language", "injection", "pill_linger_s", "sound_cues", "input_device",
    "mics", "startup", "stats", "recent",
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
