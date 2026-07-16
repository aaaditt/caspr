from caspr.app import AppController
from caspr.config import Config, load_config


def _controller(tmp_path):
    cfg = Config()
    c = AppController(cfg, config_path=tmp_path / "config.json", history_path=tmp_path / "h.db")
    return c, tmp_path / "config.json"


def test_learn_term_persists(tmp_path):
    c, path = _controller(tmp_path)
    c.learn_term("Aadit")
    assert "Aadit" in c.cfg.dictionary
    assert "Aadit" in load_config(path).dictionary
    c.learn_term("Aadit")  # idempotent
    assert c.cfg.dictionary.count("Aadit") == 1


def test_learn_replacement_persists(tmp_path):
    c, path = _controller(tmp_path)
    c.learn_replacement("Adit", "Aadit")
    assert load_config(path).replacements == {"Adit": "Aadit"}
