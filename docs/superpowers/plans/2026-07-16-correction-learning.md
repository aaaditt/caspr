# Correction & Learning UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After each dictation, a Wispr-style pill lingers showing the transcript with suspect words flagged red; clicking opens a correction popup where right-click adds words to the dictionary or creates replacement rules; a history window reviews past dictations; `caspr` launches detached from any terminal.

**Architecture:** Pure-logic modules (`spellcheck`, `replacements`, `history`) built TDD-first; UI modules (`overlay`, `correct`, `history_view`, `style`) react to `AppController` Qt signals; the pipeline gains `apply_replacements` post-STT and emits `dictation_done(final_text, spans)`. Learning mutates `config.json` immediately.

**Tech Stack:** Python 3.14 (uv venv), PySide6, wordfreq, sqlite3 (stdlib), pywin32.

## Global Constraints

- Repo: `C:\Aadit\Personal\code-ide\antigravity\caspr-flow`; run everything via `uv run …` from repo root.
- The pill must NEVER take focus: `Qt.WindowDoesNotAcceptFocus` flag + `WA_ShowWithoutActivating` attribute.
- Learning only via explicit right-click actions — free edits teach nothing.
- Replacements: whole-word, case-insensitive match, replacement inserted verbatim.
- Flagging: zipf < `cfg.flag_zipf_threshold` (default 3.0) AND not in dictionary AND alphabetic.
- All commits end with the Co-Authored-By + Claude-Session trailer used by prior commits (`git log -1` shows the format).
- After each task: `uv run ruff check caspr scripts tests` must pass and `uv run pytest -m "not slow" -q` must be green.

---

### Task 1: Config fields for learning + pill

**Files:**
- Modify: `caspr/config.py` (Config dataclass)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.replacements: dict[str, str]`, `Config.flag_zipf_threshold: float = 3.0`, `Config.pill_linger_s: float = 6.0` — used by Tasks 2, 5, 6.

- [ ] **Step 1: Write the failing test** — append to `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run** `uv run pytest tests/test_config.py -q` — expect 2 FAIL (unknown field `replacements`).
- [ ] **Step 3: Implement** — in `caspr/config.py` add to the `Config` dataclass after `dictionary`:

```python
    replacements: dict[str, str] = field(default_factory=dict)  # wrong word -> correct
    flag_zipf_threshold: float = 3.0  # words rarer than this get flagged in the UI
    pill_linger_s: float = 6.0  # 0 disables the post-dictation pill
```

- [ ] **Step 4: Run** `uv run pytest tests/test_config.py -q` — expect all PASS.
- [ ] **Step 5: Commit** `git add caspr/config.py tests/test_config.py && git commit -m "Add learning + pill config fields"` (with trailer).

### Task 2: spellcheck.py — flag unknown words

**Files:**
- Create: `caspr/spellcheck.py`
- Test: `tests/test_spellcheck.py`
- Modify: `pyproject.toml` (add `"wordfreq>=3"` to `[project] dependencies`), then `uv sync --extra cuda`.

**Interfaces:**
- Produces: `flag_unknown_words(text: str, personal_terms: Iterable[str], threshold: float = 3.0) -> list[tuple[int, int]]` — (start, end) char spans; used by Tasks 5, 6, 7, 8.

- [ ] **Step 1: Write the failing test** — `tests/test_spellcheck.py`:

```python
from caspr.spellcheck import flag_unknown_words


def _flagged_words(text, terms=(), threshold=3.0):
    return [text[s:e] for s, e in flag_unknown_words(text, terms, threshold)]


def test_rare_name_is_flagged():
    assert _flagged_words("hello Aadit here") == ["Aadit"]


def test_common_words_not_flagged():
    assert _flagged_words("we scheduled a meeting for testing tomorrow") == []


def test_dictionary_suppresses_flag():
    assert _flagged_words("hello Aadit here", terms=["aadit"]) == []


def test_contractions_and_numbers_ignored():
    assert _flagged_words("don't send 42 files") == []


def test_spans_are_correct_offsets():
    text = "ok Aadit ok"
    (s, e), = flag_unknown_words(text, [])
    assert text[s:e] == "Aadit"
```

- [ ] **Step 2: Run** `uv run pytest tests/test_spellcheck.py -q` — expect FAIL (module missing).
- [ ] **Step 3: Implement** — `caspr/spellcheck.py`:

```python
"""Flag words likely misrecognized or unknown: rare per wordfreq and not in the
personal dictionary. Rarity beats a strict wordlist for names ("adit" is a real
but rare word — a mine entrance — and should still be flagged)."""

from __future__ import annotations

import re
from collections.abc import Iterable

from wordfreq import zipf_frequency

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def flag_unknown_words(
    text: str, personal_terms: Iterable[str], threshold: float = 3.0
) -> list[tuple[int, int]]:
    known = {t.strip().lower() for t in personal_terms}
    spans: list[tuple[int, int]] = []
    for m in _WORD_RE.finditer(text):
        word = m.group().lower()
        if word in known:
            continue
        if zipf_frequency(word, "en") < threshold:
            spans.append((m.start(), m.end()))
    return spans
```

- [ ] **Step 4: Run** `uv run pytest tests/test_spellcheck.py -q` — expect PASS. If `don't` or another common token fails, print `zipf_frequency` for it and adjust the test words, NOT the threshold.
- [ ] **Step 5: Commit** `git add pyproject.toml uv.lock caspr/spellcheck.py tests/test_spellcheck.py && git commit -m "Add wordfreq-based unknown-word flagging"` (with trailer).

### Task 3: replacements.py — learned rules

**Files:**
- Create: `caspr/replacements.py`
- Test: `tests/test_replacements.py`

**Interfaces:**
- Produces: `apply_replacements(text: str, rules: dict[str, str]) -> str` — used by Task 5.

- [ ] **Step 1: Write the failing test** — `tests/test_replacements.py`:

```python
from caspr.replacements import apply_replacements


def test_whole_word_case_insensitive():
    assert apply_replacements("hi adit and Adit", {"Adit": "Aadit"}) == "hi Aadit and Aadit"


def test_partial_words_untouched():
    assert apply_replacements("Aditya said hi", {"Adit": "Aadit"}) == "Aditya said hi"


def test_empty_rules_identity():
    assert apply_replacements("hello", {}) == "hello"


def test_multiple_rules():
    out = apply_replacements("adit met rahul", {"adit": "Aadit", "rahul": "Rahul"})
    assert out == "Aadit met Rahul"
```

- [ ] **Step 2: Run** `uv run pytest tests/test_replacements.py -q` — expect FAIL (module missing).
- [ ] **Step 3: Implement** — `caspr/replacements.py`:

```python
"""Learned corrections: whole-word, case-insensitive; replacement text verbatim."""

from __future__ import annotations

import re


def apply_replacements(text: str, rules: dict[str, str]) -> str:
    for wrong, right in rules.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.IGNORECASE)
    return text
```

- [ ] **Step 4: Run** `uv run pytest tests/test_replacements.py -q` — expect PASS.
- [ ] **Step 5: Commit** `git add caspr/replacements.py tests/test_replacements.py && git commit -m "Add whole-word replacement rules"` (with trailer).

### Task 4: history.py — SQLite store

**Files:**
- Create: `caspr/history.py`
- Test: `tests/test_history.py`

**Interfaces:**
- Produces: `History(path)`, `History.add(raw_text, final_text, infer_s, total_s) -> int`, `History.recent(limit=50) -> list[Entry]`, `History.delete(entry_id)`, dataclass `Entry(id, ts, raw_text, final_text, infer_s, total_s)`; `default_history_path() -> Path`. Used by Tasks 5, 8. Thread-safe via a connection per call.

- [ ] **Step 1: Write the failing test** — `tests/test_history.py`:

```python
from caspr.history import History


def test_add_and_recent_roundtrip(tmp_path):
    h = History(tmp_path / "h.db")
    h.add("raw one", "final one", 0.5, 1.0)
    h.add("raw two", "final two", 0.4, 0.9)
    rows = h.recent()
    assert [r.final_text for r in rows] == ["final two", "final one"]  # newest first
    assert rows[0].raw_text == "raw two"
    assert rows[0].infer_s == 0.4


def test_delete(tmp_path):
    h = History(tmp_path / "h.db")
    row_id = h.add("a", "b", 0.1, 0.2)
    h.delete(row_id)
    assert h.recent() == []


def test_persists_across_instances(tmp_path):
    History(tmp_path / "h.db").add("a", "kept", 0.1, 0.2)
    assert History(tmp_path / "h.db").recent()[0].final_text == "kept"


def test_recent_respects_limit(tmp_path):
    h = History(tmp_path / "h.db")
    for i in range(5):
        h.add(f"r{i}", f"f{i}", 0.1, 0.2)
    assert len(h.recent(limit=3)) == 3
```

- [ ] **Step 2: Run** `uv run pytest tests/test_history.py -q` — expect FAIL (module missing).
- [ ] **Step 3: Implement** — `caspr/history.py`:

```python
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
```

- [ ] **Step 4: Run** `uv run pytest tests/test_history.py -q` — expect PASS.
- [ ] **Step 5: Commit** `git add caspr/history.py tests/test_history.py && git commit -m "Add SQLite dictation history"` (with trailer).

### Task 5: Pipeline integration + learning mutators (app.py)

**Files:**
- Modify: `caspr/app.py`
- Test: `tests/test_learning.py` (mutators only; pipeline covered by e2e in Task 9)

**Interfaces:**
- Consumes: `apply_replacements`, `flag_unknown_words`, `History` from Tasks 2–4.
- Produces: `AppController.dictation_done = Signal(str, object)` (final text, spans list); `AppController.learn_term(term: str)`, `AppController.learn_replacement(wrong: str, right: str)`, `AppController.history: History`, `AppController.config_path` attr (Path | None, default None → real config). Used by Tasks 6–8.

- [ ] **Step 1: Write the failing test** — `tests/test_learning.py`:

```python
from caspr.app import AppController
from caspr.config import Config, load_config


def _controller(tmp_path):
    cfg = Config()
    c = AppController(cfg, config_path=tmp_path / "config.json",
                      history_path=tmp_path / "h.db")
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
```

- [ ] **Step 2: Run** `uv run pytest tests/test_learning.py -q` — expect FAIL (unexpected kwargs).
- [ ] **Step 3: Implement** — in `caspr/app.py`:
  - extend imports: `from .config import Config, save_config`, `from .history import History`, `from .replacements import apply_replacements`, `from .spellcheck import flag_unknown_words`.
  - `__init__` signature becomes `def __init__(self, cfg: Config, config_path=None, history_path=None):` storing `self.config_path = config_path` and `self.history = History(history_path)`; add signal `dictation_done = Signal(str, object)`.
  - add mutators:

```python
    def learn_term(self, term: str) -> None:
        term = term.strip()
        if term and term not in self.cfg.dictionary:
            self.cfg.dictionary.append(term)
            save_config(self.cfg, self.config_path)
            log.info("dictionary += %r", term)

    def learn_replacement(self, wrong: str, right: str) -> None:
        wrong, right = wrong.strip(), right.strip()
        if wrong and right:
            self.cfg.replacements[wrong] = right
            save_config(self.cfg, self.config_path)
            log.info("replacement %r -> %r", wrong, right)
```

  - in `_pipeline`, after the empty-text check replace the inject/log/idle block with:

```python
            final = apply_replacements(result.text, self.cfg.replacements)
            inject.inject_text(final, self.cfg.injection)
            total_s = time.perf_counter() - t0
            spans = flag_unknown_words(final, self.cfg.dictionary,
                                       self.cfg.flag_zipf_threshold)
            self.history.add(result.text, final, result.infer_s, total_s)
            log.info(
                "dictation: %.1fs audio | infer %.2fs | total %.2fs | %r",
                audio_s, result.infer_s, total_s, final[:80],
            )
            self._set_state("idle", final[:60])
            self.dictation_done.emit(final, spans)
```

  - in `_load_model`, before setting idle state, warm wordfreq: `flag_unknown_words("warmup", [])`.
- [ ] **Step 4: Run** `uv run pytest -m "not slow" -q` — expect all PASS (existing suites too).
- [ ] **Step 5: Commit** `git add caspr/app.py tests/test_learning.py && git commit -m "Wire replacements, flagging, history and learning into pipeline"` (with trailer).

### Task 6: style.py + overlay pill

**Files:**
- Create: `caspr/ui/style.py`, `caspr/ui/overlay.py`
- Test: live verification in Task 9 (UI; no unit tests)

**Interfaces:**
- Consumes: spans format from Task 2.
- Produces: `style.APP_QSS: str`, `style.ACCENT`, `style.flagged_html(text, spans) -> str`; `Pill(QWidget)` with slots `set_level(float)`, `on_state(state, detail)`, `show_transcript(text, spans)` and signal `expand_requested(str)`. Used by Tasks 7–8 (QSS) and `__main__` wiring (Task 9).

- [ ] **Step 1: Implement style.py**:

```python
"""Shared look: Wispr-like — minimal, rounded, calm."""

from __future__ import annotations

import html

ACCENT = "#4a90d9"
FLAG = "#ff6b6b"
BG_DARK = "#1c1d22"
FG_LIGHT = "#f4f4f5"

APP_QSS = f"""
QWidget {{ font-family: 'Segoe UI Variable', 'Segoe UI'; font-size: 14px; }}
QDialog, QTabWidget::pane {{ background: {FG_LIGHT}; }}
QPushButton {{
    background: {ACCENT}; color: white; border: none; border-radius: 8px;
    padding: 7px 16px;
}}
QPushButton:hover {{ background: #3b7fc4; }}
QPushButton[flat="true"] {{ background: transparent; color: {ACCENT}; }}
QTextEdit, QListWidget, QLineEdit {{
    background: white; border: 1px solid #e4e4e7; border-radius: 10px; padding: 8px;
}}
QTabBar::tab {{ padding: 8px 18px; border: none; }}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
"""


def flagged_html(text: str, spans: list[tuple[int, int]]) -> str:
    """Escape text and wrap flagged spans in red for rich-text labels."""
    out, prev = [], 0
    for start, end in spans:
        out.append(html.escape(text[prev:start]))
        out.append(f'<span style="color:{FLAG};text-decoration:underline">'
                   f"{html.escape(text[start:end])}</span>")
        prev = end
    out.append(html.escape(text[prev:]))
    return "".join(out)
```

- [ ] **Step 2: Implement overlay.py** — frameless capsule, bottom-center, never focused:

```python
"""The pill: recording level while the mic is hot; transcript (with flags) for
pill_linger_s after each dictation. Never takes focus — purely glanceable."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .style import BG_DARK, FG_LIGHT, flagged_html


class Pill(QWidget):
    expand_requested = Signal(str)

    def __init__(self, linger_s: float = 6.0):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._linger_ms = int(linger_s * 1000)
        self._level = 0.0
        self._text = ""
        self._label = QLabel()
        self._label.setStyleSheet(f"color: {FG_LIGHT}; font-size: 14px; background: transparent;")
        self._label.setTextFormat(Qt.TextFormat.RichText)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 10, 22, 10)
        layout.addWidget(self._label)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    # -- slots (connected to AppController signals) -------------------------
    def on_state(self, state: str, detail: str) -> None:
        if state == "recording":
            self._text = ""
            self._label.setText("🎙 listening…")
            self._show_bottom_center()
        elif state == "processing":
            self._label.setText("✨ transcribing…")
        elif state == "error":
            self._label.setText(f"⚠ {detail}")
            self._hide_timer.start(self._linger_ms)

    def set_level(self, level: float) -> None:
        self._level = level
        dots = "●" * max(1, round(level * 8))
        self._label.setText(f"🎙 <span style='letter-spacing:2px'>{dots}</span>")
        self._resize_to_content()

    def show_transcript(self, text: str, spans: list[tuple[int, int]]) -> None:
        if self._linger_ms <= 0:
            self.hide()
            return
        self._text = text
        self._label.setText(flagged_html(text, spans))
        self._show_bottom_center()
        self._hide_timer.start(self._linger_ms)

    # -- internals -----------------------------------------------------------
    def _show_bottom_center(self) -> None:
        self._hide_timer.stop()
        self._resize_to_content()
        self.show()

    def _resize_to_content(self) -> None:
        self._label.setMaximumWidth(560)
        self._label.setWordWrap(True)
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.bottom() - self.height() - 24)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(BG_DARK)
        color.setAlpha(235)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), self.height() / 2, self.height() / 2)

    def mousePressEvent(self, _event) -> None:
        if self._text:
            self.hide()
            self.expand_requested.emit(self._text)
```

- [ ] **Step 3: Sanity-run** `uv run python -c "from caspr.ui import overlay, style"` — expect no import errors. `uv run ruff check caspr` — clean.
- [ ] **Step 4: Commit** `git add caspr/ui/style.py caspr/ui/overlay.py && git commit -m "Add Wispr-style pill overlay and shared stylesheet"` (with trailer).

### Task 7: Correction popup

**Files:**
- Create: `caspr/ui/correct.py`

**Interfaces:**
- Consumes: `AppController.learn_term/learn_replacement/cfg` (Task 5), `flag_unknown_words` (Task 2), `style.APP_QSS` (Task 6).
- Produces: `CorrectionPopup(controller, text, parent=None)` QDialog; used by Task 8 (history double-click) and Task 9 wiring.

- [ ] **Step 1: Implement** — `caspr/ui/correct.py`:

```python
"""Correction popup: transcript with red squiggles on suspect words;
right-click a word to add it to the dictionary or create a replacement rule.
Only explicit actions teach — free edits change nothing permanently."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication, QTextCharFormat, QSyntaxHighlighter
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QInputDialog, QLabel, QPushButton, QTextEdit, QVBoxLayout,
)

from ..spellcheck import flag_unknown_words
from .style import APP_QSS, FLAG


class _FlagHighlighter(QSyntaxHighlighter):
    def __init__(self, document, controller):
        super().__init__(document)
        self._controller = controller

    def highlightBlock(self, text: str) -> None:
        fmt = QTextCharFormat()
        fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        fmt.setUnderlineColor(FLAG)
        cfg = self._controller.cfg
        for start, end in flag_unknown_words(text, cfg.dictionary, cfg.flag_zipf_threshold):
            self.setFormat(start, end - start, fmt)


class CorrectionPopup(QDialog):
    def __init__(self, controller, text: str, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Correct dictation")
        self.setStyleSheet(APP_QSS)
        self.resize(520, 220)

        self._edit = QTextEdit()
        self._edit.setPlainText(text)
        self._edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._edit.customContextMenuRequested.connect(self._context_menu)
        self._highlighter = _FlagHighlighter(self._edit.document(), controller)

        hint = QLabel("Right-click a flagged word to teach caspr. Edits here are yours to copy.")
        hint.setStyleSheet("color: #71717a; font-size: 12px;")

        copy_btn = QPushButton("Copy corrected")
        copy_btn.clicked.connect(self._copy)
        close_btn = QPushButton("Close")
        close_btn.setProperty("flat", True)
        close_btn.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(close_btn)
        buttons.addWidget(copy_btn)
        layout = QVBoxLayout(self)
        layout.addWidget(self._edit)
        layout.addWidget(hint)
        layout.addLayout(buttons)

    def _word_under(self, pos) -> str:
        cursor = self._edit.cursorForPosition(pos)
        cursor.select(cursor.SelectionType.WordUnderCursor)
        return cursor.selectedText().strip()

    def _context_menu(self, pos) -> None:
        menu = self._edit.createStandardContextMenu()
        word = self._word_under(pos)
        if word and word.isalpha():
            menu.addSeparator()
            add = QAction(f'Add "{word}" to dictionary', menu)
            add.triggered.connect(lambda: self._learn_term(word))
            menu.addAction(add)
            repl = QAction(f'Always replace "{word}" → …', menu)
            repl.triggered.connect(lambda: self._learn_replacement(word))
            menu.addAction(repl)
        menu.exec(self._edit.mapToGlobal(pos))

    def _learn_term(self, word: str) -> None:
        self._controller.learn_term(word)
        self._highlighter.rehighlight()

    def _learn_replacement(self, word: str) -> None:
        right, ok = QInputDialog.getText(self, "Replacement", f'Always replace "{word}" with:',
                                         text=word)
        if ok and right.strip():
            self._controller.learn_replacement(word, right.strip())
            self._highlighter.rehighlight()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._edit.toPlainText())
```

- [ ] **Step 2: Sanity-run** `uv run python -c "from caspr.ui import correct"` and `uv run ruff check caspr` — clean.
- [ ] **Step 3: Commit** `git add caspr/ui/correct.py && git commit -m "Add correction popup with right-click learning"` (with trailer).

### Task 8: History window + tray menu entry

**Files:**
- Create: `caspr/ui/history_view.py`
- Modify: `caspr/ui/tray.py`

**Interfaces:**
- Consumes: `History.recent/delete` (Task 4), `CorrectionPopup` (Task 7), `flagged_html` (Task 6), controller mutators (Task 5).
- Produces: `HistoryWindow(controller)` QWidget with Dictations + Dictionary tabs; tray menu gains "History & dictionary".

- [ ] **Step 1: Implement** — `caspr/ui/history_view.py`:

```python
"""History & dictionary window: review past dictations (flags included),
double-click to open the correction popup, manage terms and rules."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)

from ..spellcheck import flag_unknown_words
from .correct import CorrectionPopup
from .style import APP_QSS, flagged_html


class HistoryWindow(QWidget):
    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Window)
        self._controller = controller
        self.setWindowTitle("caspr — history & dictionary")
        self.setStyleSheet(APP_QSS)
        self.resize(640, 480)

        tabs = QTabWidget()
        tabs.addTab(self._dictations_tab(), "Dictations")
        tabs.addTab(self._dictionary_tab(), "Dictionary")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    def showEvent(self, event) -> None:
        self._reload()
        super().showEvent(event)

    # -- dictations ---------------------------------------------------------
    def _dictations_tab(self) -> QWidget:
        page = QWidget()
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._open_correction)
        hint = QLabel("Double-click a dictation to correct it / teach words.")
        hint.setStyleSheet("color: #71717a; font-size: 12px;")
        layout = QVBoxLayout(page)
        layout.addWidget(self._list)
        layout.addWidget(hint)
        return page

    def _open_correction(self, item: QListWidgetItem) -> None:
        CorrectionPopup(self._controller, item.data(Qt.ItemDataRole.UserRole), self).exec()
        self._reload()

    # -- dictionary ----------------------------------------------------------
    def _dictionary_tab(self) -> QWidget:
        page = QWidget()
        self._terms = QListWidget()
        self._rules = QListWidget()
        self._new_term = QLineEdit()
        self._new_term.setPlaceholderText("Add a word caspr should know…")
        self._new_term.returnPressed.connect(self._add_term)
        remove_term = QPushButton("Remove term")
        remove_term.clicked.connect(self._remove_term)
        remove_rule = QPushButton("Remove rule")
        remove_rule.clicked.connect(self._remove_rule)

        cols = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        left.addWidget(QLabel("Dictionary terms"))
        left.addWidget(self._terms)
        left.addWidget(self._new_term)
        left.addWidget(remove_term)
        right.addWidget(QLabel("Replacement rules"))
        right.addWidget(self._rules)
        right.addWidget(remove_rule)
        cols.addLayout(left)
        cols.addLayout(right)
        layout = QVBoxLayout(page)
        layout.addLayout(cols)
        return page

    def _add_term(self) -> None:
        self._controller.learn_term(self._new_term.text())
        self._new_term.clear()
        self._reload()

    def _remove_term(self) -> None:
        item = self._terms.currentItem()
        if item:
            self._controller.forget_term(item.text())
            self._reload()

    def _remove_rule(self) -> None:
        item = self._rules.currentItem()
        if item:
            self._controller.forget_replacement(item.data(Qt.ItemDataRole.UserRole))
            self._reload()

    # -- data ------------------------------------------------------------------
    def _reload(self) -> None:
        cfg = self._controller.cfg
        self._list.clear()
        for entry in self._controller.history.recent():
            spans = flag_unknown_words(entry.final_text, cfg.dictionary,
                                       cfg.flag_zipf_threshold)
            when = datetime.fromtimestamp(entry.ts).strftime("%d %b %H:%M")
            label = QLabel(f"<span style='color:#71717a'>{when}</span>&nbsp;&nbsp;"
                           + flagged_html(entry.final_text, spans))
            label.setTextFormat(Qt.TextFormat.RichText)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry.final_text)
            item.setSizeHint(label.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, label)
        self._terms.clear()
        self._terms.addItems(cfg.dictionary)
        self._rules.clear()
        for wrong, right in cfg.replacements.items():
            item = QListWidgetItem(f"{wrong} → {right}")
            item.setData(Qt.ItemDataRole.UserRole, wrong)
            self._rules.addItem(item)
```

- [ ] **Step 2: Add forget mutators** to `caspr/app.py` next to the learn ones:

```python
    def forget_term(self, term: str) -> None:
        if term in self.cfg.dictionary:
            self.cfg.dictionary.remove(term)
            save_config(self.cfg, self.config_path)

    def forget_replacement(self, wrong: str) -> None:
        if self.cfg.replacements.pop(wrong, None) is not None:
            save_config(self.cfg, self.config_path)
```

  And extend `tests/test_learning.py`:

```python
def test_forget_term_and_rule(tmp_path):
    c, path = _controller(tmp_path)
    c.learn_term("Aadit")
    c.learn_replacement("Adit", "Aadit")
    c.forget_term("Aadit")
    c.forget_replacement("Adit")
    cfg = load_config(path)
    assert cfg.dictionary == [] and cfg.replacements == {}
```

- [ ] **Step 3: Modify tray** — in `caspr/ui/tray.py` `__init__` after the pause action:

```python
        history_action = QAction("History && dictionary", menu)
        history_action.triggered.connect(self._show_history)
        menu.addAction(history_action)
```

  with the slot + import (`from .history_view import HistoryWindow`):

```python
    def _show_history(self) -> None:
        if not hasattr(self, "_history_window"):
            self._history_window = HistoryWindow(self._controller)
        self._history_window.show()
        self._history_window.raise_()
        self._history_window.activateWindow()
```

- [ ] **Step 4: Run** `uv run pytest -m "not slow" -q` (all PASS incl. new forget test) and `uv run ruff check caspr` (clean).
- [ ] **Step 5: Commit** `git add caspr/ui/history_view.py caspr/ui/tray.py caspr/app.py tests/test_learning.py && git commit -m "Add history & dictionary window"` (with trailer).

### Task 9: Wiring, detached launcher, startup toggle, verification

**Files:**
- Modify: `caspr/__main__.py`, `pyproject.toml`, `README.md`
- Test: extend `scripts/e2e_paste_check.py` expectations only if broken; live verification checklist below.

**Interfaces:**
- Consumes: `Pill` (Task 6), `CorrectionPopup` (Task 7), controller signals (Task 5).
- Produces: `caspr` on PATH (detached), `caspr --startup on|off`, `caspr --install-launcher`.

- [ ] **Step 1: pyproject** — add gui-scripts section next to `[project.scripts]`:

```toml
[project.gui-scripts]
caspr-app = "caspr.__main__:main"
```

  Run `uv sync --extra cuda` to regenerate `caspr-app.exe`.
- [ ] **Step 2: __main__.py** — add args and wiring. New args in the parser:

```python
    parser.add_argument("--startup", choices=["on", "off"],
                        help="enable/disable launch at login, then exit")
    parser.add_argument("--install-launcher", action="store_true",
                        help="install the 'caspr' command on PATH, then exit")
```

  Handle them before creating QApplication:

```python
    if args.install_launcher:
        return _install_launcher()
    if args.startup:
        return _set_startup(args.startup == "on")
```

  Helpers (module level):

```python
def _venv_gui_exe() -> Path:
    return Path(sys.executable).parent / "caspr-app.exe"


def _install_launcher() -> int:
    shim = Path.home() / "AppData/Local/Microsoft/WindowsApps/caspr.cmd"
    shim.write_text(f'@echo off\nstart "" "{_venv_gui_exe()}" %*\n', encoding="ascii")
    print(f"installed: type 'caspr' in any terminal to launch (shim at {shim})")
    return 0


def _startup_shortcut() -> Path:
    return (Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"
            / "Startup/caspr-flow.lnk")


def _set_startup(enable: bool) -> int:
    path = _startup_shortcut()
    if not enable:
        path.unlink(missing_ok=True)
        print("startup disabled")
        return 0
    import win32com.client

    shortcut = win32com.client.Dispatch("WScript.Shell").CreateShortCut(str(path))
    shortcut.TargetPath = str(_venv_gui_exe())
    shortcut.WorkingDirectory = str(Path(__file__).resolve().parent.parent)
    shortcut.Save()
    print(f"startup enabled ({path.name})")
    return 0
```

  UI wiring after `tray.show()` (normal mode only, inside the `else:` branch):

```python
        from .ui.correct import CorrectionPopup
        from .ui.overlay import Pill

        pill = Pill(cfg.pill_linger_s)
        controller.state_changed.connect(pill.on_state)
        controller.input_level.connect(pill.set_level)
        controller.dictation_done.connect(pill.show_transcript)
        pill.expand_requested.connect(
            lambda text: CorrectionPopup(controller, text).exec()
        )
```

- [ ] **Step 3: README** — replace Quick start with:

```markdown
## Quick start

```powershell
uv sync --extra cuda
uv run caspr --install-launcher   # once: puts 'caspr' on PATH
caspr                             # launches detached (tray dot appears)
caspr --startup on                # optional: always running after login
```

Hold **right Ctrl** to talk; release to type into the focused app. After each
dictation a pill lingers at the bottom of the screen — click it to correct
words, right-click a red word to add it to your dictionary or create an
"always replace" rule. Tray → History & dictionary reviews everything.
```

- [ ] **Step 4: Automated verification** — `uv run pytest -q` all green; `uv run ruff check caspr scripts tests` clean; `uv run python scripts/e2e_paste_check.py` 3× PASS (pipeline unchanged for --wav mode: replacements/history run, pill skipped in wav mode since wiring is in the else branch).
- [ ] **Step 5: Live verification (Aadit)** — `caspr` from a terminal: terminal is immediately free, tray dot appears; dictate "hello this is Aadit" → pill lingers, "Aadit" red until added; click pill → right-click Aadit → Add to dictionary; dictate again → recognized (or add a replacement rule); tray → History shows both dictations; `caspr --startup on` then check shell:startup.
- [ ] **Step 6: Commit** `git add -A && git commit -m "Add pill/popup wiring, detached launcher, startup toggle"` (with trailer).

## Self-Review Notes

- Spec coverage: pill (T6), popup + right-click learning (T7), history + dictionary mgmt (T8), flagging (T2), replacements (T3), config (T1), pipeline + explicit-only learning (T5), launcher/startup/aesthetics (T6 QSS + T9). ✓
- `forget_term`/`forget_replacement` used by T8 are defined in T8 Step 2. ✓
- Types consistent: spans are `list[tuple[int, int]]` everywhere; `dictation_done(str, object)` carries spans as `object` (Qt signature limitation). ✓
