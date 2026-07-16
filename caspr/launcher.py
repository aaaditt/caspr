"""Launcher plumbing: the 'caspr' PATH shim and the launch-at-login shortcut."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def venv_gui_exe() -> Path:
    return Path(sys.executable).parent / "caspr-app.exe"


def choose_shim_dir(path_env: str) -> Path:
    """Pick a shim home that is actually on PATH (WindowsApps is not guaranteed)."""
    candidates = [
        Path.home() / ".local" / "bin",  # uv's tool dir, commonly on PATH
        Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps",
    ]
    on_path = {entry.strip().rstrip("\\/").lower() for entry in path_env.split(";") if entry}
    for candidate in candidates:
        if str(candidate).lower() in on_path:
            return candidate
    return candidates[0]


def install_launcher() -> int:
    shim_dir = choose_shim_dir(os.environ.get("PATH", ""))
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "caspr.cmd"
    shim.write_text(f'@echo off\nstart "" "{venv_gui_exe()}" %*\n', encoding="ascii")
    print(f"installed: type 'caspr' in any terminal to launch (shim at {shim})")
    if str(shim_dir).lower() not in {
        e.strip().rstrip("\\/").lower() for e in os.environ.get("PATH", "").split(";")
    }:
        print(f"NOTE: {shim_dir} is not on PATH — add it for 'caspr' to resolve")
    return 0


def _startup_shortcut() -> Path:
    return (
        Path.home()
        / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/caspr-flow.lnk"
    )


def startup_enabled() -> bool:
    return _startup_shortcut().exists()


def set_startup(enable: bool) -> int:
    path = _startup_shortcut()
    if not enable:
        path.unlink(missing_ok=True)
        print("startup disabled")
        return 0
    import win32com.client

    shortcut = win32com.client.Dispatch("WScript.Shell").CreateShortCut(str(path))
    shortcut.TargetPath = str(venv_gui_exe())
    shortcut.WorkingDirectory = str(Path(__file__).resolve().parent.parent)
    shortcut.Save()
    print(f"startup enabled ({path.name})")
    return 0
