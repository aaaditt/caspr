"""Dictation history in SQLite. A connection per call keeps it trivially
thread-safe (writes come from the pipeline worker, reads from the UI thread)."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .config import default_config_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dictations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    raw_text TEXT NOT NULL,
    final_text TEXT NOT NULL,
    infer_s REAL NOT NULL,
    total_s REAL NOT NULL
)
"""


@dataclass
class Entry:
    id: int
    ts: float
    raw_text: str
    final_text: str
    infer_s: float
    total_s: float


def default_history_path() -> Path:
    return default_config_path().parent / "history.db"


class History:
    def __init__(self, path: Path | None = None):
        self._path = Path(path) if path else default_history_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def add(self, raw_text: str, final_text: str, infer_s: float, total_s: float) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO dictations (ts, raw_text, final_text, infer_s, total_s)"
                " VALUES (?, ?, ?, ?, ?)",
                (time.time(), raw_text, final_text, infer_s, total_s),
            )
            assert cur.lastrowid is not None  # always set after INSERT
            return cur.lastrowid

    def recent(self, limit: int = 50) -> list[Entry]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT id, ts, raw_text, final_text, infer_s, total_s"
                " FROM dictations ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Entry(*row) for row in rows]

    def delete(self, entry_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM dictations WHERE id = ?", (entry_id,))
