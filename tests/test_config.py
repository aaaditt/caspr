import json

from caspr.config import Config, default_config_path, load_config, save_config


def test_defaults():
    cfg = Config()
    assert cfg.hotkey == "ctrl+windows"
    assert cfg.model == "small"
    assert cfg.device == "auto"
    assert cfg.engine == "auto"
    assert cfg.language is None
    assert cfg.dictionary == []


def test_load_missing_file_returns_defaults(tmp_path):
    cfg = load_config(tmp_path / "config.json")
    assert cfg == Config()


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(hotkey="f9", model="small", device="cpu", dictionary=["caspr", "Aadit"])
    save_config(cfg, path)
    assert load_config(path) == cfg


def test_load_ignores_unknown_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"hotkey": "f9", "some_future_key": 42}), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.hotkey == "f9"
    assert cfg.model == Config().model


def test_load_corrupt_file_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_config(path) == Config()


def test_learning_defaults():
    cfg = Config()
    assert cfg.replacements == {}
    assert cfg.flag_zipf_threshold == 3.0
    assert cfg.pill_linger_s == 6.0
    assert cfg.sound_cues is True


def test_replacements_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(replacements={"Adit": "Aadit"})
    save_config(cfg, path)
    assert load_config(path).replacements == {"Adit": "Aadit"}


def test_default_config_path_is_under_appdata():
    path = default_config_path()
    assert path.name == "config.json"
    assert path.parent.name == "caspr-flow"


def test_cleanup_defaults():
    cfg = Config()
    assert cfg.cleanup_enabled is True
    assert cfg.groq_api_key == ""
    assert cfg.groq_model == "llama-3.1-8b-instant"
    assert cfg.cleanup_context_count == 10
    assert cfg.cleanup_timeout_s == 3.0
    assert cfg.tone_profiles == {}
    assert cfg.tone_default == "balanced"
    assert cfg.handsfree_double_tap is True
    assert cfg.double_tap_ms == 400


def test_cleanup_settings_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(
        cleanup_enabled=False,
        groq_api_key="gsk_secret",
        groq_model="llama-3.3-70b-versatile",
        cleanup_context_count=5,
        tone_profiles={"slack.exe": "casual", "outlook.exe": "formal"},
        tone_default="formal",
        handsfree_double_tap=False,
        double_tap_ms=350,
    )
    save_config(cfg, path)
    assert load_config(path) == cfg
