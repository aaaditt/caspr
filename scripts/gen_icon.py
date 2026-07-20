"""Generate a static icon.png for the Electron tray from the same art as the Qt app."""

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
size = 256
pixmap = QPixmap(size, size)
pixmap.fill(Qt.GlobalColor.transparent)
painter = QPainter(pixmap)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)

# Background
g = QLinearGradient(0, 0, 0, size)
g.setColorAt(0.0, QColor("#1f1714"))
g.setColorAt(1.0, QColor("#151110"))
painter.setBrush(g)
painter.setPen(QColor("#3a2c22"))
r = size * 0.22
painter.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), r, r)

# Mic capsule
g2 = QLinearGradient(0, size * 0.18, 0, size * 0.80)
g2.setColorAt(0.0, QColor("#D75C32"))
g2.setColorAt(1.0, QColor("#D2A050"))
body = QRectF(size * 0.38, size * 0.18, size * 0.24, size * 0.34)
painter.setPen(Qt.PenStyle.NoPen)
painter.setBrush(g2)
painter.drawRoundedRect(body, body.width() / 2, body.width() / 2)

# Cradle + stand
pen = QPen(QColor("#D2A050"))
pen.setWidthF(max(1.0, size * 0.07))
pen.setCapStyle(Qt.PenCapStyle.RoundCap)
painter.setPen(pen)
painter.setBrush(Qt.BrushStyle.NoBrush)
cradle = QRectF(size * 0.30, size * 0.28, size * 0.40, size * 0.40)
painter.drawArc(cradle, 180 * 16, -180 * 16)
painter.drawLine(QPointF(size * 0.50, size * 0.68), QPointF(size * 0.50, size * 0.78))
painter.drawLine(QPointF(size * 0.40, size * 0.80), QPointF(size * 0.60, size * 0.80))

painter.end()

out = Path(__file__).resolve().parent.parent / "electron" / "icon.png"
pixmap.save(str(out))
print(f"saved {out}")
