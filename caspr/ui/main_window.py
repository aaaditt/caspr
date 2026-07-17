"""The caspr app window: Wispr-style dark shell with sidebar navigation.

Home (status + stats), Dictionary (terms/rules), History (past dictations),
Settings (hotkey/model/language/injection/pill/startup). Closing hides to tray;
the background dictation loop is untouched by this window's lifecycle.
"""

from __future__ import annotations

import getpass
from datetime import datetime

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
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
    QMenu,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import save_config
from ..hotkeys import parse_chord
from ..launcher import set_startup, startup_enabled
from ..spellcheck import flag_unknown_words
from ..timefmt import rel_time
from .correct import CorrectionPopup
from .icons import app_icon, glyph_icon
from .style import APP_QSS, MUTED, flagged_html

# Segoe Fluent / MDL2 glyphs for the sidebar
_PAGE_GLYPHS = {
    "Home": "",
    "Dictionary": "",
    "History": "",
    "Settings": "",
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


def _empty_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("caption")
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.hide()
    return label


def _hotkey_hint(hotkey: str) -> str:
    pretty = " + ".join(part.title() for part in parse_chord(hotkey))
    return f"Hold {pretty} anywhere to dictate"


def _repolish(widget: QWidget) -> None:
    """Re-evaluate QSS after a dynamic property change (Qt caches otherwise)."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


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
        self._sidebar.setIconSize(QSize(16, 16))
        self._pages = QStackedWidget()
        for name, page in (
            ("Home", self._home_page()),
            ("Dictionary", self._dictionary_page()),
            ("History", self._history_page()),
            ("Settings", self._settings_page()),
        ):
            self._sidebar.addItem(
                QListWidgetItem(glyph_icon(_PAGE_GLYPHS[name], MUTED, 16), name)
            )
            self._pages.addWidget(page)
        self._sidebar.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._sidebar.setCurrentRow(0)

        brand = QHBoxLayout()
        brand.setContentsMargins(18, 16, 18, 8)
        brand.setSpacing(8)
        brand_glyph = QLabel()
        brand_glyph.setPixmap(app_icon().pixmap(20, 20))
        brand_name = QLabel("caspr")
        brand_name.setObjectName("brandName")
        brand.addWidget(brand_glyph)
        brand.addWidget(brand_name)
        brand.addStretch()

        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebarFrame")
        sidebar_frame.setFixedWidth(170)
        sidebar_column = QVBoxLayout(sidebar_frame)
        sidebar_column.setContentsMargins(0, 0, 0, 0)
        sidebar_column.setSpacing(0)
        sidebar_column.addLayout(brand)
        sidebar_column.addWidget(self._sidebar)

        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(sidebar_frame)
        shell.addWidget(self._pages, 1)

        self._tick_timer = QTimer(self)  # keeps relative timestamps fresh
        self._tick_timer.setInterval(30_000)
        self._tick_timer.timeout.connect(self.refresh)

        self._last_state = ("loading", "")
        controller.state_changed.connect(self._on_state)
        controller.paused_changed.connect(self._on_paused)
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
        self._tick_timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._tick_timer.stop()
        super().hideEvent(event)

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

        self._greeting = QLabel()
        self._greeting.setObjectName("h1")
        layout.addWidget(self._greeting)

        status_card, status_layout = _card()
        row = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_dot.setObjectName("statusDot")
        self._status_dot.setProperty("state", "loading")
        self._status_text = QLabel("loading model…")
        row.addWidget(self._status_dot)
        row.addWidget(self._status_text)
        row.addStretch()
        status_layout.addLayout(row)
        self._hint = QLabel(_hotkey_hint(self._controller.cfg.hotkey))
        self._hint.setObjectName("muted")
        status_layout.addWidget(self._hint)
        layout.addWidget(status_card)

        stats_row = QHBoxLayout()
        self._stat_labels: list[QLabel] = []
        for caption in ("dictations today", "words dictated", "avg latency"):
            card, card_layout = _card()
            value = QLabel("—")
            value.setObjectName("statValue")
            cap = QLabel(caption)
            cap.setObjectName("caption")
            card_layout.addWidget(value)
            card_layout.addWidget(cap)
            stats_row.addWidget(card)
            self._stat_labels.append(value)
        layout.addLayout(stats_row)

        recent_caption = QLabel("Recent")
        recent_caption.setObjectName("caption")
        layout.addWidget(recent_caption)
        self._recent = QVBoxLayout()
        layout.addLayout(self._recent)
        layout.addStretch()
        return page

    def _refresh_home(self) -> None:
        hour = datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        self._greeting.setText(f"Good {part}, {getpass.getuser().title()}")
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
            label = QLabel(
                f"<span style='color:{MUTED}'>{rel_time(entry.ts)}</span>&nbsp;&nbsp;"
                + flagged_html(entry.final_text, spans)
            )
            label.setTextFormat(Qt.TextFormat.RichText)
            self._recent.addWidget(label)

    def _on_state(self, state: str, detail: str) -> None:
        self._last_state = (state, detail)
        if self._controller.paused:
            return  # keep showing the paused chip until resumed
        self._status_dot.setProperty("state", state)
        _repolish(self._status_dot)
        self._status_text.setText(detail or state)

    def _on_paused(self, paused: bool) -> None:
        if paused:
            self._status_dot.setProperty("state", "paused")
            self._status_text.setText("paused — push-to-talk off")
        else:
            state, detail = self._last_state
            self._status_dot.setProperty("state", state)
            self._status_text.setText(detail or state)
        _repolish(self._status_dot)

    # -- Dictionary -------------------------------------------------------------

    def _dictionary_page(self) -> QWidget:
        page = QWidget()
        self._terms = QListWidget()
        self._rules = QListWidget()
        self._terms_empty = _empty_label("Words you teach caspr appear here.")
        self._rules_empty = _empty_label(
            "Right-click a flagged word in a correction to add a rule."
        )
        self._new_term = QLineEdit()
        self._new_term.setPlaceholderText("Add a word caspr should know…")
        self._new_term.returnPressed.connect(self._add_term)
        remove_term = QPushButton("Remove term")
        remove_term.clicked.connect(self._remove_term)
        remove_rule = QPushButton("Remove rule")
        remove_rule.clicked.connect(self._remove_rule)

        cols = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        terms_caption = QLabel("Dictionary terms")
        terms_caption.setObjectName("caption")
        left.addWidget(terms_caption)
        left.addWidget(self._terms_empty)
        left.addWidget(self._terms)
        left.addWidget(self._new_term)
        left.addWidget(remove_term)
        rules_caption = QLabel("Replacement rules")
        rules_caption.setObjectName("caption")
        right.addWidget(rules_caption)
        right.addWidget(self._rules_empty)
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
        self._terms_empty.setVisible(not cfg.dictionary)
        self._rules_empty.setVisible(not cfg.replacements)

    # -- History -----------------------------------------------------------------

    def _history_page(self) -> QWidget:
        page = QWidget()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search dictations…")
        self._search.textChanged.connect(lambda _: self._refresh_history())
        self._dictations = QListWidget()
        self._dictations.itemDoubleClicked.connect(self._open_correction)
        self._dictations.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._dictations.customContextMenuRequested.connect(self._history_menu)
        self._history_empty = _empty_label("")
        hint = QLabel("Double-click to correct · right-click to copy or delete.")
        hint.setObjectName("caption")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)
        layout.addWidget(self._search)
        layout.addWidget(self._history_empty)
        layout.addWidget(self._dictations)
        layout.addWidget(hint)
        return page

    def _open_correction(self, item: QListWidgetItem) -> None:
        _, text = item.data(Qt.ItemDataRole.UserRole)
        CorrectionPopup(self._controller, text, self).exec()
        self.refresh()

    def _history_menu(self, pos) -> None:
        item = self._dictations.itemAt(pos)
        if item is None:
            return
        entry_id, text = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        copy_action = menu.addAction("Copy text")
        correct_action = menu.addAction("Correct…")
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(self._dictations.mapToGlobal(pos))
        if chosen is copy_action:
            QGuiApplication.clipboard().setText(text)
        elif chosen is correct_action:
            self._open_correction(item)
        elif chosen is delete_action:
            self._controller.history.delete(entry_id)
            self.refresh()

    def _refresh_history(self) -> None:
        cfg = self._controller.cfg
        query = self._search.text().strip()
        entries = (
            self._controller.history.search(query)
            if query
            else self._controller.history.recent()
        )
        self._dictations.clear()
        for entry in entries:
            spans = flag_unknown_words(entry.final_text, cfg.dictionary, cfg.flag_zipf_threshold)
            label = QLabel(
                f"<span style='color:{MUTED}'>{rel_time(entry.ts)}</span>&nbsp;&nbsp;"
                + flagged_html(entry.final_text, spans)
            )
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            label.setToolTip(datetime.fromtimestamp(entry.ts).strftime("%d %b %Y %H:%M"))
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, (entry.id, entry.final_text))
            item.setSizeHint(label.sizeHint())
            self._dictations.addItem(item)
            self._dictations.setItemWidget(item, label)
        if not entries:
            self._history_empty.setText(
                "No matches."
                if query
                else f"Nothing here yet — {_hotkey_hint(cfg.hotkey).lower()}."
            )
        self._history_empty.setVisible(not entries)

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
                note_label.setObjectName("note")
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
