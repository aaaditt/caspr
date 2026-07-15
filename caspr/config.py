"""App configuration: a dataclass persisted as JSON in %APPDATA%\\caspr-flow\\."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class Config:
    hotkey: str = "right ctrl"
    # "small" hits ~0.55s/clip on a GTX 1650 (int8_float16, greedy); "large-v3-turbo"
    # is ~1.76s if accuracy matters more than latency.
    model: str = "small"
    device: str = "auto"  # auto | cuda | cpu
    language: str | None = None  # None = let Whisper auto-detect
    input_device: int | None = None  # None = system default microphone
    injection: str = "type"  # "type" (SendInput unicode) | "clipboard" (swap + Ctrl+V)
    dictionary: list[str] = field(default_factory=list)


def default_config_path() -> Path:
    base = Path(os.environ.get("APPDATA", str(Path.home())))
    return base / "caspr-flow" / "config.json"


def load_config(path: Path | None = None) -> Config:
    path = Path(path) if path else default_config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Config()
    known = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in raw.items() if k in known})


def save_config(cfg: Config, path: Path | None = None) -> None:
    path = Path(path) if path else default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
