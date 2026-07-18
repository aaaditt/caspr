"""Bridge: the QWebChannel object ("caspr") the React UI talks to.

Signals fan out controller events to the page; slots serve data and window
controls. Payloads are built by the pure helpers in bridge_data.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal, Slot

from .bridge_data import bootstrap

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
    state_changed = Signal(str, str)
    input_level = Signal(float)
    dictation_done = Signal(str, "QVariantList")
    paused_changed = Signal(bool)

    def __init__(self, window, controller):
        super().__init__(window)
        self._window = window
        self._controller = controller
        controller.state_changed.connect(self.state_changed)
        controller.input_level.connect(self.input_level)
        controller.paused_changed.connect(self.paused_changed)
        controller.dictation_done.connect(self._relay_dictation)

    def _relay_dictation(self, text: str, spans) -> None:
        self.dictation_done.emit(text, [list(span) for span in spans])

    # -- data ----------------------------------------------------------------

    @Slot(result="QVariantMap")
    def get_bootstrap(self) -> dict:
        return bootstrap(self._controller)

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
