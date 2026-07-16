"""The caspr app window: Wispr-style dark shell with sidebar navigation.

Home (status + stats), Dictionary (terms/rules), History (past dictations),
Settings (hotkey/model/language/injection/pill/startup). Closing hides to tray;
the background dictation loop is untouched by this window's lifecycle.
"""

from __future__ import annotations

import getpass
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import save_config
from ..hotkeys import parse_chord
from ..launcher import set_startup, startup_enabled
from ..spellcheck import flag_unknown_words
from .correct import CorrectionPopup
from .style import ACCENT, APP_QSS, MUTED, flagged_html

_STATE_COLORS = {
    "loading": "#95a5a6",
    "idle": ACCENT,
    "recording": "#e74c3c",
    "processing": "#f39c12",
    "error": "#7f1d1d",
}

_HOTKEY_PRESETS = [
    ("Ctrl + Win", "ctrl+windows"),
    ("Right Ctrl", "right ctrl"),
    ("Ctrl + Alt", "ctrl+alt"),
]
_MODELS = [
    ("base — fastest, roughest", "base"),
    ("small — fast, accurate (default)", "small"),
    ("large-v3-turbo — best, ~3x slower", "large-v3-turbo"),
]
_LANGUAGES = [("Auto-detect", None), ("English", "en"), ("हिन्दी", "hi")]


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 14, 18, 14)
    return frame, layout


def _hotkey_hint(hotkey: str) -> str:
    pretty = " + ".join(part.title() for part in parse_chord(hotkey))
    return f"Hold {pretty} anywhere to dictate"


class MainWindow(QWidget):
    hotkey_changed = Signal(str)

    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Window)
        self._controller = controller
        self.setWindowTitle("caspr")
        self.setStyleSheet(APP_QSS)
        self.resize(880, 560)

        self._sidebar = QListWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(170)
        self._pages = QStackedWidget()
        for name, page in (
            ("Home", self._home_page()),
            ("Dictionary", self._dictionary_page()),
            ("History", self._history_page()),
            ("Settings", self._settings_page()),
        ):
            self._sidebar.addItem(name)
            self._pages.addWidget(page)
        self._sidebar.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._sidebar)
        shell.addWidget(self._pages, 1)

        controller.state_changed.connect(self._on_state)
        controller.dictation_done.connect(lambda *_: self.refresh())

    # -- window behavior ----------------------------------------------------

    def surface(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()  # caspr keeps running in the tray

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        self._refresh_home()
        self._refresh_dictionary()
        self._refresh_history()

    # -- Home -----------------------------------------------------------------

    def _home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        hour = datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        greeting = QLabel(f"Good {part}, {getpass.getuser().title()}")
        greeting.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(greeting)

        status_card, status_layout = _card()
        row = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {_STATE_COLORS['loading']}; font-size: 16px;")
        self._status_text = QLabel("loading model…")
        row.addWidget(self._status_dot)
        row.addWidget(self._status_text)
        row.addStretch()
        status_layout.addLayout(row)
        self._hint = QLabel(_hotkey_hint(self._controller.cfg.hotkey))
        self._hint.setStyleSheet(f"color: {MUTED};")
        status_layout.addWidget(self._hint)
        layout.addWidget(status_card)

        stats_row = QHBoxLayout()
        self._stat_labels: list[QLabel] = []
        for caption in ("dictations today", "words dictated", "avg latency"):
            card, card_layout = _card()
            value = QLabel("—")
            value.setStyleSheet("font-size: 26px; font-weight: 700;")
            cap = QLabel(caption)
            cap.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
            card_layout.addWidget(value)
            card_layout.addWidget(cap)
            stats_row.addWidget(card)
            self._stat_labels.append(value)
        layout.addLayout(stats_row)

        recent_caption = QLabel("Recent")
        recent_caption.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        layout.addWidget(recent_caption)
        self._recent = QVBoxLayout()
        layout.addLayout(self._recent)
        layout.addStretch()
        return page

    def _refresh_home(self) -> None:
        stats = self._controller.history.stats()
        self._stat_labels[0].setText(str(stats.today_count))
        self._stat_labels[1].setText(f"{stats.total_words:,}")
        self._stat_labels[2].setText(f"{stats.avg_total_s:.1f}s" if stats.avg_total_s else "—")
        while (item := self._recent.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        cfg = self._controller.cfg
        for entry in self._controller.history.recent(limit=5):
            spans = flag_unknown_words(entry.final_text, cfg.dictionary, cfg.flag_zipf_threshold)
            label = QLabel(flagged_html(entry.final_text, spans))
            label.setStyleSheet(f"color: {MUTED};")
            label.setTextFormat(Qt.TextFormat.RichText)
            self._recent.addWidget(label)

    def _on_state(self, state: str, detail: str) -> None:
        self._status_dot.setStyleSheet(
            f"color: {_STATE_COLORS.get(state, ACCENT)}; font-size: 16px;"
        )
        self._status_text.setText(detail or state)

    # -- Dictionary -------------------------------------------------------------

    def _dictionary_page(self) -> QWidget:
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
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addLayout(cols)
        return page

    def _add_term(self) -> None:
        self._controller.learn_term(self._new_term.text())
        self._new_term.clear()
        self._refresh_dictionary()

    def _remove_term(self) -> None:
        item = self._terms.currentItem()
        if item:
            self._controller.forget_term(item.text())
            self._refresh_dictionary()

    def _remove_rule(self) -> None:
        item = self._rules.currentItem()
        if item:
            self._controller.forget_replacement(item.data(Qt.ItemDataRole.UserRole))
            self._refresh_dictionary()

    def _refresh_dictionary(self) -> None:
        cfg = self._controller.cfg
        self._terms.clear()
        self._terms.addItems(cfg.dictionary)
        self._rules.clear()
        for wrong, right in cfg.replacements.items():
            item = QListWidgetItem(f"{wrong} → {right}")
            item.setData(Qt.ItemDataRole.UserRole, wrong)
            self._rules.addItem(item)

    # -- History -----------------------------------------------------------------

    def _history_page(self) -> QWidget:
        page = QWidget()
        self._dictations = QListWidget()
        self._dictations.itemDoubleClicked.connect(self._open_correction)
        hint = QLabel("Double-click a dictation to correct it / teach words.")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addWidget(self._dictations)
        layout.addWidget(hint)
        return page

    def _open_correction(self, item: QListWidgetItem) -> None:
        CorrectionPopup(self._controller, item.data(Qt.ItemDataRole.UserRole), self).exec()
        self.refresh()

    def _refresh_history(self) -> None:
        cfg = self._controller.cfg
        self._dictations.clear()
        for entry in self._controller.history.recent():
            spans = flag_unknown_words(entry.final_text, cfg.dictionary, cfg.flag_zipf_threshold)
            when = datetime.fromtimestamp(entry.ts).strftime("%d %b %H:%M")
            label = QLabel(
                f"<span style='color:{MUTED}'>{when}</span>&nbsp;&nbsp;"
                + flagged_html(entry.final_text, spans)
            )
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry.final_text)
            item.setSizeHint(label.sizeHint())
            self._dictations.addItem(item)
            self._dictations.setItemWidget(item, label)

    # -- Settings -----------------------------------------------------------------

    def _settings_page(self) -> QWidget:
        cfg = self._controller.cfg
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        def row(caption: str, control: QWidget, note: str = "") -> None:
            line = QHBoxLayout()
            label = QLabel(caption)
            label.setFixedWidth(160)
            line.addWidget(label)
            line.addWidget(control, 1)
            if note:
                note_label = QLabel(note)
                note_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
                line.addWidget(note_label)
            layout.addLayout(line)

        hotkey = QComboBox()
        for label_text, value in _HOTKEY_PRESETS:
            hotkey.addItem(label_text, value)
        hotkey.setCurrentIndex(
            max(0, next((i for i, (_, v) in enumerate(_HOTKEY_PRESETS) if v == cfg.hotkey), 0))
        )
        hotkey.currentIndexChanged.connect(
            lambda i: self._save(hotkey="ctrl+windows" if i < 0 else hotkey.itemData(i))
        )
        row("Push-to-talk", hotkey)

        model = QComboBox()
        for label_text, value in _MODELS:
            model.addItem(label_text, value)
        model.setCurrentIndex(
            max(0, next((i for i, (_, v) in enumerate(_MODELS) if v == cfg.model), 1))
        )
        model.currentIndexChanged.connect(lambda i: self._save(model=model.itemData(i)))
        row("Whisper model", model, "restart to apply")

        language = QComboBox()
        for label_text, value in _LANGUAGES:
            language.addItem(label_text, value)
        language.setCurrentIndex(
            max(0, next((i for i, (_, v) in enumerate(_LANGUAGES) if v == cfg.language), 0))
        )
        language.currentIndexChanged.connect(lambda i: self._save(language=language.itemData(i)))
        row("Language", language, "restart to apply")

        injection = QComboBox()
        injection.addItem("Type (SendInput)", "type")
        injection.addItem("Clipboard paste", "clipboard")
        injection.setCurrentIndex(0 if cfg.injection == "type" else 1)
        injection.currentIndexChanged.connect(lambda i: self._save(injection=injection.itemData(i)))
        row("Text injection", injection)

        linger = QDoubleSpinBox()
        linger.setRange(0.0, 30.0)
        linger.setSingleStep(0.5)
        linger.setSuffix(" s")
        linger.setValue(cfg.pill_linger_s)
        linger.valueChanged.connect(lambda v: self._save(pill_linger_s=v))
        row("Pill linger", linger, "0 disables the pill")

        startup = QCheckBox("Launch caspr when you log in")
        startup.setChecked(startup_enabled())
        startup.toggled.connect(lambda on: set_startup(on))
        layout.addWidget(startup)

        layout.addStretch()
        return page

    def _save(self, **changes) -> None:
        cfg = self._controller.cfg
        for key, value in changes.items():
            setattr(cfg, key, value)
        save_config(cfg, self._controller.config_path)
        if "hotkey" in changes:
            self._hint.setText(_hotkey_hint(cfg.hotkey))
            self.hotkey_changed.emit(cfg.hotkey)
