"""Per-app context: which app has focus → which tone the cleanup should use.

``foreground_exe`` reads the active window's process name via Win32 (pywin32,
already a dependency). Any failure degrades to ``None`` so a tone lookup never
breaks a dictation. ``tone_for`` is pure and unit-tested.
"""

from __future__ import annotations

import fnmatch
import logging
import os

log = logging.getLogger(__name__)


def foreground_exe() -> str | None:
    """Lowercased exe name of the foreground window's process (e.g. ``"slack.exe"``),
    or ``None`` if it can't be determined."""
    try:
        import win32api
        import win32con
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            return None
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            try:
                path = win32process.QueryFullProcessImageName(handle, 0)
            except AttributeError:  # older pywin32
                path = win32process.GetModuleFileNameEx(handle, 0)
        finally:
            win32api.CloseHandle(handle)
        return os.path.basename(path).lower() if path else None
    except Exception:
        log.debug("foreground_exe lookup failed", exc_info=True)
        return None


def tone_for(exe: str | None, profiles: dict[str, str], default: str) -> str:
    """Map a foreground exe to a tone label. A profile key matches when it is a
    substring of the exe name or matches it as a glob; first match wins."""
    if not exe or not profiles:
        return default
    name = exe.lower()
    for pattern, tone in profiles.items():
        p = (pattern or "").strip().lower()
        if p and (p in name or fnmatch.fnmatch(name, p)):
            return tone
    return default
