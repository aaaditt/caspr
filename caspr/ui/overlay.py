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
        self._text = ""
        self._label = QLabel()
        self._label.setStyleSheet(
            f"color: {FG_LIGHT}; font-size: 14px; background: transparent;"
        )
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
        self.move(
            screen.center().x() - self.width() // 2,
            screen.bottom() - self.height() - 24,
        )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(BG_DARK)
        color.setAlpha(235)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = self.height() / 2
        painter.drawRoundedRect(self.rect(), radius, radius)

    def mousePressEvent(self, _event) -> None:
        if self._text:
            self.hide()
            self.expand_requested.emit(self._text)
