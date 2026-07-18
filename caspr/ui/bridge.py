"""Bridge: the QWebChannel object ("caspr") the React UI talks to.

Window controls only for now; data/settings slots land with the live bridge.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Slot

_EDGES = {
    "left": Qt.Edge.LeftEdge,
    "right": Qt.Edge.RightEdge,
    "top": Qt.Edge.TopEdge,
    "bottom": Qt.Edge.BottomEdge,
    "topleft": Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
    "topright": Qt.Edge.TopEdge | Qt.Edge.RightEdge,
    "bottomleft": Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
    "bottomright": Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
}


class Bridge(QObject):
    def __init__(self, window, controller):
        super().__init__(window)
        self._window = window
        self._controller = controller

    # -- window controls (frameless chrome) ---------------------------------

    @Slot()
    def win_minimize(self) -> None:
        self._window.showMinimized()

    @Slot()
    def win_close(self) -> None:
        self._window.hide()  # caspr keeps running in the tray

    @Slot()
    def win_drag(self) -> None:
        handle = self._window.windowHandle()
        if handle is not None:
            handle.startSystemMove()  # native move — Aero snap keeps working

    @Slot(str)
    def win_resize(self, edge: str) -> None:
        handle = self._window.windowHandle()
        edges = _EDGES.get(edge)
        if handle is not None and edges is not None:
            handle.startSystemResize(edges)
