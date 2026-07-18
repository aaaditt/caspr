"""JSON-safe payload builders for the web bridge. Pure functions, unit-tested."""

from __future__ import annotations

import getpass

from ..audio import list_input_devices
from ..history import Entry
from ..hotkeys import pretty_chord
from ..launcher import startup_enabled
from ..spellcheck import flag_unknown_words


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
        "model": cfg.model,
        "device": cfg.device,
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
