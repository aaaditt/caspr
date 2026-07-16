import json

from caspr.config import Config, default_config_path, load_config, save_config


def test_defaults():
    cfg = Config()
    assert cfg.hotkey == "right ctrl"
    assert cfg.model == "small"
    assert cfg.device == "auto"
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


def test_replacements_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(replacements={"Adit": "Aadit"})
    save_config(cfg, path)
    assert load_config(path).replacements == {"Adit": "Aadit"}


def test_default_config_path_is_under_appdata():
    path = default_config_path()
    assert path.name == "config.json"
    assert path.parent.name == "caspr-flow"
