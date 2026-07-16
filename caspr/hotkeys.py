"""Global push-to-talk via the `keyboard` library's low-level Windows hook.

Supports chords ("ctrl+windows") and single keys ("right ctrl"): on_press fires
once when every chord part is held; on_release when any part lifts. Modifier-only
chords are ideal — they type nothing into the focused app, and because another
key goes down while Win is held, Windows suppresses the Start menu.

Callbacks fire on the keyboard hook thread, NOT the Qt main thread — anything
touching UI must marshal across (Qt signals do this automatically).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import keyboard

log = logging.getLogger(__name__)


def parse_chord(chord: str) -> list[str]:
    """Split a chord string on '+' into normalized key names."""
    return [part.strip().lower() for part in chord.split("+") if part.strip()]


class PushToTalk:
    """Hold every key of `chord` to talk; releasing any of them stops."""

    def __init__(self, chord: str, on_press: Callable[[], None], on_release: Callable[[], None]):
        self._parts = parse_chord(chord)
        self._on_press = on_press
        self._on_release = on_release
        self._down: set[str] = set()
        self._held = False
        self._handles: list = []

    def start(self) -> None:
        for part in self._parts:
            self._handles.append(
                keyboard.on_press_key(part, lambda _e, p=part: self._handle_down(p))
            )
            self._handles.append(
                keyboard.on_release_key(part, lambda _e, p=part: self._handle_up(p))
            )
        log.info("push-to-talk armed on %r", "+".join(self._parts))

    def stop(self) -> None:
        for handle in self._handles:
            keyboard.unhook(handle)
        self._handles = []
        self._down.clear()
        self._held = False

    def _handle_down(self, part: str) -> None:
        self._down.add(part)
        if self._held:
            return  # OS key auto-repeat while chord held
        if self._down.issuperset(self._parts):
            self._held = True
            self._on_press()

    def _handle_up(self, part: str) -> None:
        self._down.discard(part)
        if not self._held:
            return
        self._held = False
        self._on_release()
