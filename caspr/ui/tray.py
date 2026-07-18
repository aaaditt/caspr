"""System tray icon: app glyph with a state-colored badge + pause/quit menu."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from collections.abc import Callable

from ..app import AppController
from .icons import tray_icon
from .style import STATE_COLORS


class Tray(QSystemTrayIcon):
    def __init__(
        self,
        controller: AppController,
        app: QApplication,
        on_open: Callable[[], None] | None = None,
    ):
        super().__init__(tray_icon("loading"))
        self._controller = controller
        self._on_open = on_open
        self._icons = {state: tray_icon(state) for state in STATE_COLORS}

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
        self._last_state = "loading"
        controller.state_changed.connect(self._on_state)
        controller.paused_changed.connect(self._on_paused)
        controller.notify.connect(self._on_notify)

    def _on_notify(self, title: str, body: str) -> None:
        self.showMessage(title, body, QSystemTrayIcon.MessageIcon.Warning, 6000)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger and self._on_open:
            self._on_open()

    def _toggle_pause(self) -> None:
        self._controller.toggle_pause()

    def _on_paused(self, paused: bool) -> None:
        self._pause_action.setText("Resume" if paused else "Pause")
        self.setIcon(self._icons["paused" if paused else self._last_state])

    def _on_state(self, state: str, detail: str) -> None:
        self._last_state = state
        if not self._controller.paused:
            self.setIcon(self._icons.get(state, self._icons["idle"]))
        label = state if not detail else f"{state} — {detail}"
        self._status_action.setText(label[:80])
        self.setToolTip(f"caspr-flow: {label[:120]}")
