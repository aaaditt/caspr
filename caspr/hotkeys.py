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


def pretty_chord(chord: str) -> str:
    """"ctrl+windows" → "Ctrl + Windows" for user-facing labels."""
    return " + ".join(part.title() for part in parse_chord(chord))


MODIFIERS = {"ctrl", "alt", "shift", "windows"}
_SIDED = {
    "left ctrl": "ctrl",
    "right ctrl": "ctrl",
    "left alt": "alt",
    "right alt": "alt",
    "alt gr": "alt",
    "left shift": "shift",
    "right shift": "shift",
    "left windows": "windows",
    "right windows": "windows",
}
_MOD_ORDER = ("ctrl", "alt", "shift", "windows")


def canonical_key(name: str) -> str:
    """Collapse sided modifiers ("left windows" → "windows") to match how
    keyboard.on_press_key("windows") aliases both sides."""
    return _SIDED.get(name.strip().lower(), name.strip().lower())


class ChordRecorder:
    """Builds a chord string from raw down/up key events.

    Finalization: a non-modifier pressed while modifiers are held completes the
    chord immediately ("ctrl+space" needs no clean release); otherwise the chord
    is the largest held set, finalized when everything is released (this is what
    makes modifier-only chords like "ctrl+windows" capturable).
    """

    def __init__(self):
        self._down: set[str] = set()
        self._max_held: set[str] = set()
        self.chord: str | None = None

    @property
    def held(self) -> list[str]:
        """Currently held keys in canonical chord order (for live UI feedback)."""
        return _ordered(self._down)

    def feed(self, kind: str, name: str) -> None:
        if self.chord is not None:
            return
        key = canonical_key(name)
        if kind == "down":
            self._down.add(key)
            if key not in MODIFIERS and self._down & MODIFIERS:
                self.chord = "+".join(_ordered(self._down))
                return
            if len(self._down) > len(self._max_held):
                self._max_held = set(self._down)
        elif kind == "up":
            self._down.discard(key)
            if not self._down and self._max_held:
                self.chord = "+".join(_ordered(self._max_held))


def _ordered(keys: set[str]) -> list[str]:
    mods = [m for m in _MOD_ORDER if m in keys]
    return mods + sorted(k for k in keys if k not in MODIFIERS)


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
