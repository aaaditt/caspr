"""Paste text into whatever window has focus, via clipboard swap.

Clipboard-swap beats simulated typing: atomic, fast for long text, and works in
Electron apps and terminals where per-keystroke injection is flaky. The user's
existing clipboard text is saved and restored around the Ctrl+V. (v1 restores
text content only — image/file clipboard contents are not preserved.)
"""

from __future__ import annotations

import logging
import time

import keyboard
import win32clipboard
import win32con

log = logging.getLogger(__name__)

# How long the target app gets to read the clipboard before we restore it.
_PASTE_SETTLE_S = 0.15


def _open_clipboard_with_retry(attempts: int = 10) -> None:
    # Another process holding the clipboard makes OpenClipboard fail transiently.
    for i in range(attempts):
        try:
            win32clipboard.OpenClipboard()
            return
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(0.02)


def get_clipboard_text() -> str | None:
    _open_clipboard_with_retry()
    try:
        if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return None
        return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


def set_clipboard_text(text: str) -> None:
    _open_clipboard_with_retry()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def paste_text(text: str) -> None:
    """Set clipboard to `text`, send Ctrl+V to the focused window, restore clipboard."""
    saved = None
    try:
        saved = get_clipboard_text()
    except Exception:
        log.warning("could not read existing clipboard; it will not be restored")
    set_clipboard_text(text)
    keyboard.send("ctrl+v")
    time.sleep(_PASTE_SETTLE_S)
    if saved is not None:
        try:
            set_clipboard_text(saved)
        except Exception:
            log.warning("could not restore clipboard")
