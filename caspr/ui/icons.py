"""Painted app identity: window/taskbar icon, tray state icons, sidebar glyphs.

Everything is drawn with QPainter at runtime — no binary assets in the repo.
Call only after a QApplication exists (QPixmap needs one).
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)

from .style import BG, CORAL, ACCENT, STATE_COLORS, SURFACE

_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _paint_mic(painter: QPainter, size: float) -> None:
    """Mic capsule + cradle arc + stand in the coral→amber Velvet gradient."""
    s = size
    gradient = QLinearGradient(0, s * 0.18, 0, s * 0.80)
    gradient.setColorAt(0.0, QColor(CORAL))
    gradient.setColorAt(1.0, QColor(ACCENT))

    pen = QPen(QColor(ACCENT))
    pen.setWidthF(max(1.0, s * 0.07))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)

    body = QRectF(s * 0.38, s * 0.18, s * 0.24, s * 0.34)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(body, body.width() / 2, body.width() / 2)

    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    cradle = QRectF(s * 0.30, s * 0.28, s * 0.40, s * 0.40)
    painter.drawArc(cradle, 180 * 16, -180 * 16)  # opens upward, hugs the capsule
    painter.drawLine(QPointF(s * 0.50, s * 0.68), QPointF(s * 0.50, s * 0.78))
    painter.drawLine(QPointF(s * 0.40, s * 0.80), QPointF(s * 0.60, s * 0.80))


def _app_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    gradient = QLinearGradient(0, 0, 0, size)
    gradient.setColorAt(0.0, QColor(SURFACE))
    gradient.setColorAt(1.0, QColor(BG))
    painter.setBrush(gradient)
    painter.setPen(QColor("#3a2c22"))
    radius = size * 0.22
    inset = max(0.5, size * 0.02)
    painter.drawRoundedRect(
        QRectF(inset, inset, size - 2 * inset, size - 2 * inset), radius, radius
    )

    _paint_mic(painter, size)
    painter.end()
    return pixmap


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    icon = QIcon()
    for size in _SIZES:
        icon.addPixmap(_app_pixmap(size))
    return icon


@lru_cache(maxsize=None)
def tray_icon(state: str) -> QIcon:
    """App glyph with a state-colored badge dot in the bottom-right corner."""
    size = 32
    pixmap = _app_pixmap(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    badge = QRectF(size * 0.56, size * 0.56, size * 0.40, size * 0.40)
    painter.setBrush(QColor(BG))  # ring separating badge from the glyph
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(badge)
    color = STATE_COLORS.get(state, STATE_COLORS["idle"])
    painter.setBrush(QColor(color))
    painter.drawEllipse(badge.adjusted(2, 2, -2, -2))
    painter.end()
    return QIcon(pixmap)


@lru_cache(maxsize=1)
def _glyph_family() -> str:
    families = set(QFontDatabase.families())
    if "Segoe Fluent Icons" in families:  # Windows 11
        return "Segoe Fluent Icons"
    return "Segoe MDL2 Assets"  # Windows 10 fallback, same codepoints


@lru_cache(maxsize=None)
def glyph_icon(codepoint: str, color: str, px: int = 16) -> QIcon:
    """Render a Segoe Fluent/MDL2 glyph (e.g. "") as an icon."""
    scale = 2  # draw at 2x so high-DPI taskbars/lists stay crisp
    pixmap = QPixmap(px * scale, px * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont(_glyph_family())
    font.setPixelSize(int(px * scale * 0.9))
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, codepoint)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)
