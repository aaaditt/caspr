"""Bridge: the QWebChannel object ("caspr") the React UI talks to.

Signals fan out controller events to the page; slots serve data and window
controls. Payloads are built by the pure helpers in bridge_data.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication

from .bridge_data import bootstrap, dictionary_dict, history_list

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
    data_changed = Signal()  # history/dictionary mutated — pages should refetch

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

    @Slot(str, result="QVariantList")
    def get_history(self, query: str) -> list:
        return history_list(self._controller, query)

    @Slot(int)
    def delete_entry(self, entry_id: int) -> None:
        self._controller.history.delete(entry_id)
        self.data_changed.emit()

    @Slot(str)
    def copy_text(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)

    @Slot(str)
    def correct(self, text: str) -> None:
        from .correct import CorrectionPopup  # deferred: avoids import cycle at startup

        CorrectionPopup(self._controller, text).exec()
        self.data_changed.emit()

    @Slot(result="QVariantMap")
    def get_dictionary(self) -> dict:
        return dictionary_dict(self._controller.cfg)

    @Slot(str)
    def learn_term(self, term: str) -> None:
        self._controller.learn_term(term)
        self.data_changed.emit()

    @Slot(str)
    def forget_term(self, term: str) -> None:
        self._controller.forget_term(term)
        self.data_changed.emit()

    @Slot(str)
    def forget_rule(self, wrong: str) -> None:
        self._controller.forget_replacement(wrong)
        self.data_changed.emit()

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
