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


def main() -> int:
    parser = argparse.ArgumentParser(prog="caspr")
    parser.add_argument("--wav", type=Path, help="run pipeline once on a WAV file, then exit")
    parser.add_argument("--model", help="override Whisper model for this run")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], help="override device")
    parser.add_argument("--hotkey", help="override push-to-talk key")
    args = parser.parse_args()

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
        ptt = PushToTalk(cfg.hotkey, controller.on_ptt_press, controller.on_ptt_release)
        ptt.start()
        log.info("ready: hold %r to dictate", cfg.hotkey)

    controller.start()
    code = app.exec()
    controller.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
