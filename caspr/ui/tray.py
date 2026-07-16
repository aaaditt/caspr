"""System tray icon: colored dot per state + pause/quit menu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from collections.abc import Callable

from ..app import AppController

_STATE_COLORS = {
    "loading": "#95a5a6",
    "idle": "#4a90d9",
    "recording": "#e74c3c",
    "processing": "#f39c12",
    "error": "#7f1d1d",
}


def _dot_icon(color: str) -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()
    return QIcon(pixmap)


class Tray(QSystemTrayIcon):
    def __init__(
        self,
        controller: AppController,
        app: QApplication,
        on_open: Callable[[], None] | None = None,
    ):
        super().__init__(_dot_icon(_STATE_COLORS["loading"]))
        self._controller = controller
        self._on_open = on_open
        self._icons = {state: _dot_icon(color) for state, color in _STATE_COLORS.items()}

        menu = QMenu()
        self._status_action = QAction("loading model…")
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        menu.addSeparator()

        self._pause_action = QAction("Pause")
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        if on_open is not None:
            open_action = QAction("Open caspr", menu)
            open_action.triggered.connect(on_open)
            menu.addAction(open_action)
            self.activated.connect(self._on_activated)

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.setToolTip("caspr-flow — loading model…")
        controller.state_changed.connect(self._on_state)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger and self._on_open:
            self._on_open()

    def _toggle_pause(self) -> None:
        self._controller.toggle_pause()
        self._pause_action.setText("Resume" if self._controller.paused else "Pause")

    def _on_state(self, state: str, detail: str) -> None:
        self.setIcon(self._icons.get(state, self._icons["idle"]))
        label = state if not detail else f"{state} — {detail}"
        self._status_action.setText(label[:80])
        self.setToolTip(f"caspr-flow: {label[:120]}")
