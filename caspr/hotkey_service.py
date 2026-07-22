"""One owner for every global hotkey, shared by both runtimes.

The standalone Qt entrypoint and the Electron backend both build a
``HotkeyService`` so Python holds the keyboard hooks in either case — Electron's
``globalShortcut`` can't detect key-release, so it can't drive hold-to-talk.
Any hotkey change is applied live by a single ``rearm()``; no restart needed.

The primary push-to-talk chord uses ``PushToTalk`` (press *and* release, for
hold-to-talk); the four optional action chords are press-only and call the
matching controller method. ``keyboard`` and ``PushToTalk`` are injected so the
service is unit-testable without a real global hook.
"""

from __future__ import annotations

import logging

import keyboard

from .hotkeys import PushToTalk

log = logging.getLogger(__name__)

# config field -> AppController method invoked on press
_ACTIONS = {
    "hotkey_toggle_dictation": "toggle_dictation",
    "hotkey_cancel_dictation": "cancel_dictation",
    "hotkey_mute_mic": "mute_mic",
    "hotkey_open_history": "open_history",
}


class HotkeyService:
    def __init__(self, controller, cfg, *, ptt_factory=PushToTalk, kb=keyboard):
        self._controller = controller
        self._cfg = cfg
        self._ptt_factory = ptt_factory
        self._kb = kb
        self._ptt = None
        self._handles: list = []

    def rearm(self) -> None:
        """Tear down every hook and rebuild from the current config."""
        self._teardown()
        self._ptt = self._ptt_factory(
            self._cfg.hotkey,
            self._controller.on_ptt_press,
            self._controller.on_ptt_release,
        )
        self._ptt.start()
        for field, method in _ACTIONS.items():
            chord = getattr(self._cfg, field, "")
            if not chord:
                continue
            callback = getattr(self._controller, method)
            try:
                self._handles.append(self._kb.add_hotkey(chord, callback))
            except Exception as e:  # keyboard raises on an unparseable chord
                log.warning("could not bind %s=%r: %s", field, chord, e)

    def suspend(self) -> None:
        """Drop all hooks — used while the modal capture dialog owns the keyboard."""
        self._teardown()

    def resume(self) -> None:
        self.rearm()

    def stop(self) -> None:
        self._teardown()

    def _teardown(self) -> None:
        if self._ptt is not None:
            self._ptt.stop()
            self._ptt = None
        for handle in self._handles:
            try:
                self._kb.remove_hotkey(handle)
            except (KeyError, ValueError):
                pass
        self._handles = []
