"""End-to-end check: caspr --wav should paste the fixture transcript into
whatever window has focus. This harness provides that window and verifies
the text arrives — exercising STT, clipboard swap, and Ctrl+V injection.

Run:  uv run python scripts/e2e_paste_check.py
Note: keep hands off keyboard/mouse while it runs (~15s); it must hold focus.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QPlainTextEdit

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "testing_one_two_three.wav"
TIMEOUT_MS = 90_000


def main() -> int:
    app = QApplication(sys.argv)
    edit = QPlainTextEdit()
    edit.setWindowTitle("caspr e2e paste target — do not touch")
    edit.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    edit.resize(520, 180)
    edit.show()
    edit.raise_()
    edit.activateWindow()
    edit.setFocus()

    proc = subprocess.Popen(
        [sys.executable, "-m", "caspr", "--wav", str(FIXTURE), "--model", "tiny"],
        cwd=ROOT,
    )

    elapsed = {"ms": 0}
    result = {"code": 1}

    def finish(code: int, message: str) -> None:
        result["code"] = code
        print(message)
        if proc.poll() is None:
            proc.terminate()
        app.quit()

    def poll() -> None:
        elapsed["ms"] += 500
        text = edit.toPlainText().strip()
        if text:
            ok = "testing" in text.lower() and ("1" in text or "one" in text.lower())
            finish(0 if ok else 1, f"{'PASS' if ok else 'FAIL'}: pasted text = {text!r}")
        elif proc.poll() is not None and elapsed["ms"] > 2_000:
            finish(1, f"FAIL: caspr exited (code {proc.returncode}) without pasting")
        elif elapsed["ms"] >= TIMEOUT_MS:
            finish(1, "FAIL: timed out waiting for paste")

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(500)

    app.exec()
    return result["code"]


if __name__ == "__main__":
    sys.exit(main())
