"""JSON-safe payload builders and setting routing for the web bridge.
Pure functions, unit-tested."""

from __future__ import annotations

import getpass

from ..audio import list_input_devices
from ..config import save_config
from ..history import Entry
from ..hotkeys import parse_chord, pretty_chord
from ..launcher import startup_enabled
from ..spellcheck import flag_unknown_words

_SETTING_KEYS = {
    "model",
    "device",
    "engine",
    "language",
    "injection",
    "pill_linger_s",
    "sound_cues",
    "input_device",
    "hotkey",
    "hotkey_toggle_dictation",
    "hotkey_cancel_dictation",
    "hotkey_mute_mic",
    "hotkey_open_history",
}

_OPTIONAL_HOTKEY_KEYS = {
    "hotkey_toggle_dictation",
    "hotkey_cancel_dictation",
    "hotkey_mute_mic",
    "hotkey_open_history",
}


def apply_setting(controller, key: str, value) -> str:
    """Persist one setting and trigger its side effect.

    Returns the follow-up performed: "reload" (model/device hot-reload),
    "mic" (recorder device swap), "hotkey" (caller must re-arm), or "".
    Unknown keys and invalid values are ignored (returns "").
    """
    if key not in _SETTING_KEYS:
        return ""
    if key == "language":
        value = value or None
    elif key == "input_device":
        value = None if value is None else int(value)
    elif key == "pill_linger_s":
        value = float(value)
    elif key == "sound_cues":
        value = bool(value)
    elif key == "hotkey":
        if not isinstance(value, str) or not parse_chord(value):
            return ""
    elif key in _OPTIONAL_HOTKEY_KEYS:
        if not isinstance(value, str):
            return ""
        if value and not parse_chord(value):
            return ""
    setattr(controller.cfg, key, value)
    save_config(controller.cfg, controller.config_path)
    # language steers auto engine routing, so it reloads too
    if key in ("model", "device", "engine", "language"):
        controller.reload_model()
        return "reload"
    if key == "input_device":
        controller.set_input_device(value)
        return "mic"
    if key == "hotkey" or key in _OPTIONAL_HOTKEY_KEYS:
        return "hotkey"
    return ""


def entry_dict(entry: Entry, cfg) -> dict:
    spans = flag_unknown_words(entry.final_text, cfg.dictionary, cfg.flag_zipf_threshold)
    return {
        "id": entry.id,
        "ts": entry.ts,
        "text": entry.final_text,
        "spans": [[start, end] for start, end in spans],
    }


def history_list(controller, query: str = "") -> list[dict]:
    query = query.strip()
    entries = (
        controller.history.search(query) if query else controller.history.recent(limit=200)
    )
    return [entry_dict(e, controller.cfg) for e in entries]


def dictionary_dict(cfg) -> dict:
    return {
        "terms": list(cfg.dictionary),
        "rules": [{"wrong": wrong, "right": right} for wrong, right in cfg.replacements.items()],
    }


def bootstrap(controller) -> dict:
    """Everything the React app needs on load, in one round trip."""
    cfg = controller.cfg
    stats = controller.history.stats()
    return {
        "user": getpass.getuser().title(),
        "state": controller.state,
        "paused": controller.paused,
        "hotkey": cfg.hotkey,
        "hotkey_pretty": pretty_chord(cfg.hotkey),
        "hotkey_toggle_dictation": cfg.hotkey_toggle_dictation,
        "hotkey_toggle_dictation_pretty": pretty_chord(cfg.hotkey_toggle_dictation),
        "hotkey_cancel_dictation": cfg.hotkey_cancel_dictation,
        "hotkey_cancel_dictation_pretty": pretty_chord(cfg.hotkey_cancel_dictation),
        "hotkey_mute_mic": cfg.hotkey_mute_mic,
        "hotkey_mute_mic_pretty": pretty_chord(cfg.hotkey_mute_mic),
        "hotkey_open_history": cfg.hotkey_open_history,
        "hotkey_open_history_pretty": pretty_chord(cfg.hotkey_open_history),
        "model": cfg.model,
        "device": cfg.device,
        "engine": cfg.engine,
        "language": cfg.language or "",
        "injection": cfg.injection,
        "pill_linger_s": cfg.pill_linger_s,
        "sound_cues": cfg.sound_cues,
        "input_device": cfg.input_device,
        "mics": [{"index": index, "name": name} for index, name in list_input_devices()],
        "startup": startup_enabled(),
        "stats": {
            "today": stats.today_count,
            "words": stats.total_words,
            "avg_s": stats.avg_total_s,
        },
        "recent": [entry_dict(e, cfg) for e in controller.history.recent(limit=5)],
    }
