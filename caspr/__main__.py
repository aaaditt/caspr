"""caspr-flow entrypoint: app window + tray + global push-to-talk dictation.

Usage:
    caspr                       # open the app window; hold Ctrl+Win to dictate
    caspr --wav file.wav        # debug: run pipeline once on a WAV, paste, exit
    caspr --model tiny --device cpu --hotkey f9   # config overrides for this run

Single instance: the first process listens on a QLocalServer; a second `caspr`
just tells it to surface the window and exits.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from .app import AppController
from .audio import load_wav_mono16k
from .config import default_config_path, load_config, save_config
from .hotkeys import PushToTalk
from .launcher import install_launcher, set_startup

log = logging.getLogger("caspr")

_SERVER_NAME = "caspr-flow"


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
        return install_launcher()
    if args.startup:
        return set_startup(args.startup == "on")

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

    try:  # give caspr its own taskbar identity instead of the Python interpreter's
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("aaaditt.caspr")
    except (AttributeError, OSError):
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("caspr-flow")

    from .ui.icons import app_icon  # after QApplication exists

    app.setWindowIcon(app_icon())

    server = None
    if not args.wav:  # debug runs stay out of the single-instance protocol
        # Already running? Tell that instance to surface its window and bow out.
        probe = QLocalSocket()
        probe.connectToServer(_SERVER_NAME)
        if probe.waitForConnected(300):
            probe.write(b"show")
            probe.flush()
            probe.waitForBytesWritten(300)
            probe.disconnectFromServer()
            print("caspr is already running — surfaced its window")
            return 0

        QLocalServer.removeServer(_SERVER_NAME)  # clear stale socket after a crash
        server = QLocalServer()
        server.listen(_SERVER_NAME)

    controller = AppController(cfg)

    from .ui.tray import Tray  # after QApplication exists

    if args.wav:
        tray = Tray(controller, app)
        tray.show()
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
        from .ui.main_window import MainWindow
        from .ui.overlay import Pill

        window = MainWindow(controller)
        tray = Tray(controller, app, on_open=window.surface)
        tray.show()
        assert server is not None  # non-wav mode always listens
        server.newConnection.connect(
            lambda: (server.nextPendingConnection(), window.surface())
        )

        pill = Pill(cfg)
        controller.state_changed.connect(pill.on_state)
        controller.input_level.connect(pill.set_level)
        controller.dictation_done.connect(pill.show_transcript)
        pill.expand_requested.connect(
            lambda text: CorrectionPopup(controller, text).exec()
        )

        from .sounds import SoundCues

        cues = SoundCues(cfg)
        controller.state_changed.connect(cues.on_state)

        ptt_holder: dict[str, PushToTalk] = {}

        def arm(chord: str) -> None:
            if "ptt" in ptt_holder:
                ptt_holder["ptt"].stop()
            ptt_holder["ptt"] = PushToTalk(
                chord, controller.on_ptt_press, controller.on_ptt_release
            )
            ptt_holder["ptt"].start()

        arm(cfg.hotkey)
        window.hotkey_changed.connect(arm)
        window.surface()
        log.info("ready: hold %r to dictate", cfg.hotkey)

    controller.start()
    code = app.exec()
    controller.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
