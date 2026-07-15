"""Global push-to-talk hotkey via the `keyboard` library's low-level Windows hook.

Callbacks fire on the keyboard hook thread, NOT the Qt main thread — anything
touching UI must marshal across (Qt signals do this automatically).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import keyboard

log = logging.getLogger(__name__)


class PushToTalk:
    """Hold `key` to talk: on_press fires once on key-down, on_release on key-up.

    Key auto-repeat is debounced — holding the key fires on_press exactly once.
    """

    def __init__(self, key: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self._key = key
        self._on_press = on_press
        self._on_release = on_release
        self._held = False
        self._handles: list = []

    def start(self) -> None:
        self._handles.append(keyboard.on_press_key(self._key, self._handle_down))
        self._handles.append(keyboard.on_release_key(self._key, self._handle_up))
        log.info("push-to-talk armed on %r", self._key)

    def stop(self) -> None:
        for handle in self._handles:
            keyboard.unhook(handle)
        self._handles = []

    def _handle_down(self, _event) -> None:
        if self._held:
            return  # OS key auto-repeat
        self._held = True
        self._on_press()

    def _handle_up(self, _event) -> None:
        if not self._held:
            return
        self._held = False
        self._on_release()
