"""Inject text into whatever window has focus.

Primary method: SendInput with KEYEVENTF_UNICODE — synthesizes the text as key
events in one batched syscall. No clipboard involvement, so the user's clipboard
is never touched and there is no restore race (a clipboard-swap Ctrl+V is
processed asynchronously by the target app, so restoring the old clipboard on a
timer can win the race and paste stale content — observed in e2e).

Fallback method ("clipboard" in config): clipboard-swap + Ctrl+V, for apps that
ignore synthetic typing. Restores text clipboard content only, after a settle
delay — inherently racy, which is why it is not the default.
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes

import keyboard
import win32clipboard
import win32con

log = logging.getLogger(__name__)

# How long the target app gets to read the clipboard before we restore it.
_PASTE_SETTLE_S = 0.4

# --- SendInput unicode typing -------------------------------------------------

_INPUT_KEYBOARD = 1
_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP = 0x0002
_SENDINPUT_CHUNK = 256  # events per SendInput call

_ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("padding", ctypes.c_byte * 32)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def type_text(text: str) -> None:
    """Type `text` into the focused window via batched unicode key events."""
    # Edit controls expect Enter as carriage return.
    text = text.replace("\r\n", "\n").replace("\n", "\r")
    events: list[_INPUT] = []
    utf16 = text.encode("utf-16-le")
    code_units = [int.from_bytes(utf16[i:i + 2], "little") for i in range(0, len(utf16), 2)]
    for cu in code_units:
        for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
            inp = _INPUT()
            inp.type = _INPUT_KEYBOARD
            inp.ki = _KEYBDINPUT(0, cu, flags, 0, None)
            events.append(inp)
    for start in range(0, len(events), _SENDINPUT_CHUNK):
        chunk = events[start:start + _SENDINPUT_CHUNK]
        array = (_INPUT * len(chunk))(*chunk)
        sent = ctypes.windll.user32.SendInput(len(chunk), array, ctypes.sizeof(_INPUT))
        if sent != len(chunk):
            raise OSError(f"SendInput injected {sent}/{len(chunk)} events")


def inject_text(text: str, method: str = "type") -> None:
    if method == "clipboard":
        paste_text(text)
    else:
        type_text(text)


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
