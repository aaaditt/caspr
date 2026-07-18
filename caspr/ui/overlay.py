"""The pill: a live waveform while the mic is hot, a shimmer while transcribing,
then the transcript (with flags) for pill_linger_s. Never takes focus."""

from __future__ import annotations

import html
import math
import time
from collections import deque

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QGuiApplication, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .icons import glyph_icon
from .style import ACCENT, CORAL, FG, FLAG, SURFACE, flagged_html

FADES_ENABLED = True  # kill switch: opacity animation on translucent windows
_SHADOW = 10  # transparent margin around the capsule for the painted shadow
_BOTTOM_GAP = 16  # raw gap; visual gap is this + _SHADOW
_MIC_GLYPH = ""  # Segoe Fluent/MDL2 "Microphone"


class Waveform(QWidget):
    """Scrolling mic-level bars; a traveling shimmer in processing mode."""

    BARS = 24
    GAIN = 2.2  # RMS levels are small; scale into the visible range

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._levels: deque[float] = deque([0.0] * self.BARS, maxlen=self.BARS)
        self._display = [0.0] * self.BARS
        self._mode = "recording"
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(132, 26)

    def reset(self) -> None:
        self._levels.extend([0.0] * self.BARS)
        self._display = [0.0] * self.BARS

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def push_level(self, level: float) -> None:
        self._levels.append(min(1.0, level * self.GAIN))

    # -- animation ----------------------------------------------------------

    def showEvent(self, event) -> None:
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self) -> None:
        if self._mode == "processing":
            phase = 4.0 * time.monotonic()
            self._display = [
                0.18 + 0.14 * math.sin(2 * math.pi * i / self.BARS + phase)
                for i in range(self.BARS)
            ]
        else:
            for i, target in enumerate(self._levels):
                shown = self._display[i]
                # rise instantly, fall smoothly
                self._display[i] = target if target > shown else shown + (target - shown) * 0.35
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        w, gap = 3.0, 2.5
        h = self.height()
        mid = self.BARS / 2 - 0.5
        for i, value in enumerate(self._display):
            bar_h = 3.0 + max(0.0, min(1.0, value)) * (h - 6.0)
            x = i * (w + gap)
            alpha = int(255 - 165 * (abs(i - mid) / mid))  # fade toward edges
            top = QColor(CORAL)
            top.setAlpha(alpha)
            bottom = QColor(ACCENT)
            bottom.setAlpha(alpha)
            gradient = QLinearGradient(0, (h - bar_h) / 2, 0, (h + bar_h) / 2)
            gradient.setColorAt(0.0, top)
            gradient.setColorAt(1.0, bottom)
            painter.setBrush(gradient)
            painter.drawRoundedRect(QRectF(x, (h - bar_h) / 2, w, bar_h), w / 2, w / 2)


class Pill(QWidget):
    expand_requested = Signal(str)

    def __init__(self, cfg):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._cfg = cfg  # read pill_linger_s live so Settings changes apply instantly
        self._text = ""
        self._hiding = False

        self._glyph = QLabel()
        self._glyph.setPixmap(glyph_icon(_MIC_GLYPH, ACCENT, 16).pixmap(16, 16))
        self._glyph.setStyleSheet("background: transparent;")
        self._wave = Waveform()
        self._label = QLabel()
        self._label.setStyleSheet(f"color: {FG}; font-size: 14px; background: transparent;")
        self._label.setTextFormat(Qt.TextFormat.RichText)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22 + _SHADOW, 10 + _SHADOW, 22 + _SHADOW, 10 + _SHADOW)
        layout.setSpacing(10)
        layout.addWidget(self._glyph)
        layout.addWidget(self._wave)
        layout.addWidget(self._label)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.finished.connect(self._after_fade)

    @property
    def _linger_ms(self) -> int:
        return int(self._cfg.pill_linger_s * 1000)

    # -- slots (connected to AppController signals) -------------------------

    def on_state(self, state: str, detail: str) -> None:
        if state == "recording":
            self._text = ""
            self._wave.reset()
            self._wave.set_mode("recording")
            self._show_live()
        elif state == "processing":
            self._wave.set_mode("processing")
        elif state == "error":
            self._show_label(f"<span style='color:{FLAG}'>⚠</span> {html.escape(detail)}")
            self._hide_timer.start(max(self._linger_ms, 2500))

    def set_level(self, level: float) -> None:
        self._wave.push_level(level)

    def show_transcript(self, text: str, spans: list[tuple[int, int]]) -> None:
        if self._linger_ms <= 0:
            self._fade_out()
            return
        self._text = text
        self._show_label(flagged_html(text, spans))
        self._hide_timer.start(self._linger_ms)

    # -- presentation -------------------------------------------------------

    def _show_live(self) -> None:
        """Fixed-size glyph + waveform; geometry set once, no per-tick jumps."""
        self._hide_timer.stop()
        self._label.hide()
        self._wave.show()
        self._reposition()
        self._fade_in()

    def _show_label(self, html_text: str) -> None:
        self._hide_timer.stop()
        self._wave.hide()
        self._label.setText(html_text)
        self._label.show()
        self._reposition()
        self._fade_in()

    def _reposition(self) -> None:
        self._label.setMaximumWidth(560)
        self._label.setWordWrap(True)
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.bottom() - self.height() - _BOTTOM_GAP,
        )

    # -- fades --------------------------------------------------------------

    def _fade_in(self) -> None:
        self._hiding = False
        self._fade.stop()
        if not FADES_ENABLED:
            self.setWindowOpacity(1.0)
            self.show()
            return
        start = self.windowOpacity() if self.isVisible() else 0.0
        self.setWindowOpacity(start)  # before show() so there's no full-opacity flash
        self.show()
        self._fade.setStartValue(start)
        self._fade.setEndValue(1.0)
        self._fade.setDuration(140)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def _fade_out(self) -> None:
        if not self.isVisible():
            return
        if not FADES_ENABLED:
            self.hide()
            return
        self._hiding = True
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.setDuration(220)
        self._fade.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade.start()

    def _after_fade(self) -> None:
        if self._hiding:
            self._hiding = False
            self.hide()
            self.setWindowOpacity(1.0)

    # -- painting -----------------------------------------------------------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        body = QRectF(self.rect()).adjusted(_SHADOW, _SHADOW, -_SHADOW, -_SHADOW)
        # painted penumbra — QGraphicsDropShadowEffect is unreliable on
        # translucent top-level windows, so fake it with layered rects
        for inset, alpha, dy in ((6.0, 10, 3.0), (7.5, 16, 2.0), (9.0, 24, 1.0)):
            shadow = QRectF(self.rect()).adjusted(inset, inset + dy, -inset, -inset + dy)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(shadow, shadow.height() / 2, shadow.height() / 2)
        fill = QColor(SURFACE)
        fill.setAlpha(244)
        painter.setBrush(fill)
        painter.setPen(QColor(255, 255, 255, 18))
        painter.drawRoundedRect(body, body.height() / 2, body.height() / 2)

    def mousePressEvent(self, _event) -> None:
        if self._text:
            self.hide()
            self.expand_requested.emit(self._text)
