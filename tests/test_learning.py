from pathlib import Path

from caspr.__main__ import _choose_shim_dir
from caspr.app import AppController
from caspr.config import Config, load_config


def test_shim_prefers_local_bin_when_on_path():
    local_bin = Path.home() / ".local" / "bin"
    assert _choose_shim_dir(f"C:\\foo;{local_bin}\\;C:\\bar") == local_bin


def test_shim_accepts_windowsapps_when_local_bin_absent():
    wa = Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps"
    assert _choose_shim_dir(f"C:\\foo;{str(wa).upper()}") == wa


def test_shim_defaults_to_local_bin_when_nothing_matches():
    assert _choose_shim_dir("C:\\foo;C:\\bar") == Path.home() / ".local" / "bin"


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


def test_forget_term_and_rule(tmp_path):
    c, path = _controller(tmp_path)
    c.learn_term("Aadit")
    c.learn_replacement("Adit", "Aadit")
    c.forget_term("Aadit")
    c.forget_replacement("Adit")
    cfg = load_config(path)
    assert cfg.dictionary == [] and cfg.replacements == {}
