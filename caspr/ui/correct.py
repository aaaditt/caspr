"""Correction popup: transcript with red squiggles on suspect words;
right-click a word to add it to the dictionary or create a replacement rule.
Only explicit actions teach — free edits change nothing permanently."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QGuiApplication, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
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
        fmt.setUnderlineColor(QColor(FLAG))
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
        hint.setObjectName("caption")

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
        right, ok = QInputDialog.getText(
            self, "Replacement", f'Always replace "{word}" with:', text=word
        )
        if ok and right.strip():
            self._controller.learn_replacement(word, right.strip())
            self._highlighter.rehighlight()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._edit.toPlainText())
