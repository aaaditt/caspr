"""caspr-flow entrypoint: tray app with global push-to-talk dictation.

Usage:
    caspr                       # normal: hold right-Ctrl to dictate
    caspr --wav file.wav        # debug: run pipeline once on a WAV, paste, exit
    caspr --model tiny --device cpu --hotkey f9   # config overrides for this run
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication

from .app import AppController
from .audio import load_wav_mono16k
from .config import default_config_path, load_config, save_config
from .hotkeys import PushToTalk

log = logging.getLogger("caspr")


def _setup_logging() -> None:
    log_path = default_config_path().parent / "caspr.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def _venv_gui_exe() -> Path:
    return Path(sys.executable).parent / "caspr-app.exe"


def _install_launcher() -> int:
    shim = Path.home() / "AppData/Local/Microsoft/WindowsApps/caspr.cmd"
    shim.write_text(f'@echo off\nstart "" "{_venv_gui_exe()}" %*\n', encoding="ascii")
    print(f"installed: type 'caspr' in any terminal to launch (shim at {shim})")
    return 0


def _startup_shortcut() -> Path:
    return (
        Path.home()
        / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/caspr-flow.lnk"
    )


def _set_startup(enable: bool) -> int:
    path = _startup_shortcut()
    if not enable:
        path.unlink(missing_ok=True)
        print("startup disabled")
        return 0
    import win32com.client

    shortcut = win32com.client.Dispatch("WScript.Shell").CreateShortCut(str(path))
    shortcut.TargetPath = str(_venv_gui_exe())
    shortcut.WorkingDirectory = str(Path(__file__).resolve().parent.parent)
    shortcut.Save()
    print(f"startup enabled ({path.name})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="caspr")
    parser.add_argument("--wav", type=Path, help="run pipeline once on a WAV file, then exit")
    parser.add_argument("--model", help="override Whisper model for this run")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], help="override device")
    parser.add_argument("--hotkey", help="override push-to-talk key")
    parser.add_argument(
        "--startup", choices=["on", "off"], help="enable/disable launch at login, then exit"
    )
    parser.add_argument(
        "--install-launcher",
        action="store_true",
        help="install the 'caspr' command on PATH, then exit",
    )
    args = parser.parse_args()

    if args.install_launcher:
        return _install_launcher()
    if args.startup:
        return _set_startup(args.startup == "on")

    _setup_logging()

    cfg = load_config()
    if not default_config_path().exists():
        save_config(cfg)  # write defaults so the user has a file to edit
    if args.model:
        cfg.model = args.model
    if args.device:
        cfg.device = args.device
    if args.hotkey:
        cfg.hotkey = args.hotkey

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("caspr-flow")

    lock = QLockFile(str(Path(tempfile.gettempdir()) / "caspr-flow.lock"))
    if not lock.tryLock(100):
        print("caspr-flow is already running (check the system tray)", file=sys.stderr)
        return 1

    controller = AppController(cfg)

    from .ui.tray import Tray  # after QApplication exists

    tray = Tray(controller, app)
    tray.show()

    if args.wav:
        audio = load_wav_mono16k(args.wav)
        transitions: list[str] = []

        def on_state(state: str, detail: str) -> None:
            transitions.append(state)
            if state == "error":
                print(f"WAV RESULT: error — {detail}")
                app.quit()
            elif state == "idle" and transitions.count("idle") == 1:
                controller.run_wav(audio)  # model ready → run once
            elif state == "idle":
                print(f"WAV RESULT: ok — {detail}")
                app.quit()

        controller.state_changed.connect(on_state)
    else:
        from .ui.correct import CorrectionPopup
        from .ui.overlay import Pill

        pill = Pill(cfg.pill_linger_s)
        controller.state_changed.connect(pill.on_state)
        controller.input_level.connect(pill.set_level)
        controller.dictation_done.connect(pill.show_transcript)
        pill.expand_requested.connect(
            lambda text: CorrectionPopup(controller, text).exec()
        )

        ptt = PushToTalk(cfg.hotkey, controller.on_ptt_press, controller.on_ptt_release)
        ptt.start()
        log.info("ready: hold %r to dictate", cfg.hotkey)

    controller.start()
    code = app.exec()
    controller.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
