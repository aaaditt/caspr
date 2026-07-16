"""History & dictionary window: review past dictations (flags included),
double-click to open the correction popup, manage terms and rules."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
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
            spans = flag_unknown_words(
                entry.final_text, cfg.dictionary, cfg.flag_zipf_threshold
            )
            when = datetime.fromtimestamp(entry.ts).strftime("%d %b %H:%M")
            label = QLabel(
                f"<span style='color:#71717a'>{when}</span>&nbsp;&nbsp;"
                + flagged_html(entry.final_text, spans)
            )
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
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
