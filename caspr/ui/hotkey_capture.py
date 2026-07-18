"""Modal dialog that records a global hotkey chord via the keyboard library.

Qt's QKeySequenceEdit cannot see the Windows key, so we hook the same keyboard
library that arms push-to-talk — every captured name is guaranteed to be a name
PushToTalk accepts. The caller MUST stop the armed PushToTalk before opening
this dialog (MainWindow.capture_active handles that), or holding the current
chord would start a dictation mid-capture.
"""

from __future__ import annotations

import keyboard
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from ..hotkeys import ChordRecorder
from .style import APP_QSS

_TIMEOUT_MS = 10_000


class HotkeyCaptureDialog(QDialog):
    # raw events arrive on the keyboard hook thread; this signal marshals
    # them onto the GUI thread where the recorder and labels live
    _event = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set push-to-talk")
        self.setStyleSheet(APP_QSS)
        self.setModal(True)
        self.chord: str | None = None
        self._recorder = ChordRecorder()
        self._hook = None

        prompt = QLabel("Press the shortcut you want, then release.")
        hint = QLabel("Esc cancels.")
        hint.setObjectName("caption")
        self._held = QLabel("waiting…")
        self._held.setObjectName("h1")
        self._held.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(prompt)
        layout.addWidget(self._held)
        layout.addWidget(hint)
        self.setFixedWidth(360)

        self._event.connect(self._on_event)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(_TIMEOUT_MS)
        self._timeout.timeout.connect(self.reject)

    def showEvent(self, event) -> None:
        if self._hook is None:
            # suppress=False: never swallow global input, even if a bug leaves
            # the hook installed. NEVER unhook_all() — it would kill PTT hooks.
            self._hook = keyboard.hook(self._on_raw)
        self._timeout.start()
        super().showEvent(event)

    def done(self, result: int) -> None:
        # single exit point for accept/reject/close — the hook can never leak
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        self._timeout.stop()
        super().done(result)

    # -- events --------------------------------------------------------------

    def _on_raw(self, event) -> None:  # keyboard hook thread!
        if event.name:
            self._event.emit("down" if event.event_type == "down" else "up", event.name)

    def _on_event(self, kind: str, name: str) -> None:  # GUI thread
        if name == "esc":
            self.reject()
            return
        self._timeout.start()  # any activity resets the 10 s deadline
        self._recorder.feed(kind, name)
        if self._recorder.chord is not None:
            self.chord = self._recorder.chord
            self.accept()
            return
        held = self._recorder.held
        self._held.setText(" + ".join(part.title() for part in held) if held else "waiting…")
