"""Frameless host window for the React UI (QtWebEngine + QWebChannel).

Loads webui/dist in production; set CASPR_UI_DEV=1 to load the Vite dev
server (http://localhost:5173) for hot reload while designing.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .bridge import Bridge

_VELVET_BG = "#151110"


class Shell(QWidget):
    hotkey_changed = Signal(str)
    capture_active = Signal(bool)

    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("caspr")
        self.resize(940, 600)
        self.setMinimumSize(760, 480)

        self._view = QWebEngineView(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        page = self._view.page()
        page.setBackgroundColor(QColor(_VELVET_BG))  # no white flash on first paint
        self._channel = QWebChannel(page)
        self._bridge = Bridge(self, controller)
        self._channel.registerObject("caspr", self._bridge)
        page.setWebChannel(self._channel)

        self._round_corners()

        if os.environ.get("CASPR_UI_DEV"):
            self._view.load(QUrl("http://localhost:5173/"))
        else:
            dist = Path(__file__).resolve().parents[2] / "webui" / "dist" / "index.html"
            self._view.load(QUrl.fromLocalFile(str(dist)))

    def _round_corners(self) -> None:
        """Windows 11 native rounded corners + shadow for the frameless window."""
        try:
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            preference = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()),
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(preference),
                ctypes.sizeof(preference),
            )
        except (AttributeError, OSError):
            pass  # Windows 10: square corners, still fine

    # -- window behavior ----------------------------------------------------

    def surface(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()  # caspr keeps running in the tray
