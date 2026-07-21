"""WebSocket server: lets the Electron shell drive the AppController.

Messages are JSON objects with a ``type`` key and optional ``id`` (for
request/response round-trips).  The server pushes events (state_changed,
input_level, etc.) to all connected clients automatically.

Usage::

    uv run caspr --server              # headless, ws://localhost:18321
    uv run caspr --server --port 9999  # custom port
"""

from __future__ import annotations

import asyncio
import json
import logging

import aiohttp
from aiohttp import web

from .app import AppController
from .config import Config, save_config
from .ui.bridge_data import (
    apply_setting,
    bootstrap,
    dictionary_dict,
    history_list,
)

log = logging.getLogger(__name__)


class JsonWsServer:
    """Thin wrapper: manages connected WebSocket clients and broadcasts events."""

    def __init__(self, controller: AppController):
        self._controller = controller
        self._clients: set[web.WebSocketResponse] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

        # Wire Qt signals → WebSocket broadcasts
        controller.state_changed.connect(self._on_state_changed)
        controller.input_level.connect(self._on_input_level)
        controller.dictation_done.connect(self._on_dictation_done)
        controller.paused_changed.connect(self._on_paused_changed)

    # -- signal handlers (run on Qt threads, schedule into asyncio) ----------

    def _broadcast(self, msg: dict) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(asyncio.ensure_future, self._send_all(msg))

    def _on_state_changed(self, state: str, detail: str) -> None:
        self._broadcast({"type": "state_changed", "state": state, "detail": detail})

    def _on_input_level(self, level: float) -> None:
        self._broadcast({"type": "input_level", "level": level})

    def _on_dictation_done(self, text: str, spans: list) -> None:
        self._broadcast({
            "type": "dictation_done",
            "text": text,
            "spans": [list(s) for s in spans],
        })

    def _on_paused_changed(self, paused: bool) -> None:
        self._broadcast({"type": "paused_changed", "paused": paused})

    def _broadcast_data_changed(self) -> None:
        self._broadcast({"type": "data_changed"})

    # -- async helpers -------------------------------------------------------

    async def _send_all(self, msg: dict) -> None:
        raw = json.dumps(msg)
        dead: list[web.WebSocketResponse] = []
        for ws in self._clients:
            try:
                await ws.send_str(raw)
            except (ConnectionResetError, ConnectionError):
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    async def _send(self, ws: web.WebSocketResponse, msg: dict) -> None:
        try:
            await ws.send_str(json.dumps(msg))
        except (ConnectionResetError, ConnectionError):
            self._clients.discard(ws)

    # -- request handlers ----------------------------------------------------

    def _handle_request(self, msg: dict) -> dict | None:
        """Synchronous dispatch for request/response messages.

        Returns a response dict (will be sent back with the same ``id``), or
        None for fire-and-forget commands.
        """
        t = msg.get("type", "")
        ctrl = self._controller

        if t == "get_bootstrap":
            return {"type": "bootstrap", "data": bootstrap(ctrl)}

        if t == "get_history":
            query = msg.get("query", "")
            return {"type": "history", "data": history_list(ctrl, query)}

        if t == "get_dictionary":
            return {"type": "dictionary", "data": dictionary_dict(ctrl.cfg)}

        if t == "set_setting":
            key, value = msg.get("key", ""), msg.get("value")
            result = apply_setting(ctrl, key, value)
            return {"type": "setting_applied", "key": key, "result": result}

        if t == "learn_term":
            ctrl.learn_term(msg.get("term", ""))
            self._broadcast_data_changed()
            return None

        if t == "forget_term":
            ctrl.forget_term(msg.get("term", ""))
            self._broadcast_data_changed()
            return None

        if t == "forget_rule":
            ctrl.forget_replacement(msg.get("wrong", ""))
            self._broadcast_data_changed()
            return None

        if t == "delete_entry":
            ctrl.history.delete(msg.get("id", 0))
            self._broadcast_data_changed()
            return None

        if t == "toggle_pause":
            ctrl.toggle_pause()
            return None

        if t == "ptt_press":
            ctrl.on_ptt_press()
            return None

        if t == "ptt_release":
            ctrl.on_ptt_release()
            return None

        if t == "copy_text":
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(msg.get("text", ""))
            return None

        if t == "set_startup":
            from .launcher import set_startup
            set_startup(msg.get("enabled", False))
            return None

        if t == "capture_hotkey":
            # Modal Qt dialog — must run on the main thread.  We use
            # QTimer.singleShot(0) to schedule it and block the asyncio
            # caller with a threading Event.
            import threading
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QDialog

            result_holder: dict = {"chord": None}
            done_event = threading.Event()

            def _show_dialog():
                from .ui.hotkey_capture import HotkeyCaptureDialog
                dlg = HotkeyCaptureDialog()
                if dlg.exec() == QDialog.DialogCode.Accepted and dlg.chord:
                    result_holder["chord"] = dlg.chord
                done_event.set()

            QTimer.singleShot(0, _show_dialog)
            done_event.wait(timeout=15)  # 10s dialog timeout + margin
            return {"type": "hotkey_captured", "chord": result_holder["chord"]}

        log.warning("unknown message type: %s", t)
        return {"type": "error", "message": f"unknown type: {t}"}

    # -- WebSocket endpoint --------------------------------------------------

    async def ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._clients.add(ws)
        log.info("client connected (%d total)", len(self._clients))
        try:
            async for raw_msg in ws:
                if raw_msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        msg = json.loads(raw_msg.data)
                    except json.JSONDecodeError:
                        await self._send(ws, {"type": "error", "message": "invalid JSON"})
                        continue
                    req_id = msg.get("id")
                    reply = self._handle_request(msg)
                    if reply is not None:
                        if req_id is not None:
                            reply["id"] = req_id
                        await self._send(ws, reply)
                elif raw_msg.type == aiohttp.WSMsgType.ERROR:
                    log.error("ws error: %s", ws.exception())
        finally:
            self._clients.discard(ws)
            log.info("client disconnected (%d remaining)", len(self._clients))
        return ws

    # -- server lifecycle ----------------------------------------------------

    async def _run(self, port: int) -> None:
        app = web.Application()
        app.router.add_get("/ws", self.ws_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", port)
        await site.start()
        log.info("WebSocket server listening on ws://127.0.0.1:%d/ws", port)
        # Run until cancelled
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    def run(self, port: int = 18321) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run(port))
        except KeyboardInterrupt:
            pass
        finally:
            self._loop.close()


def run_server(cfg: Config, port: int = 18321) -> int:
    """Entry point for ``caspr --server``.  Starts the controller + WS server."""
    import sys
    import threading

    from PySide6.QtWidgets import QApplication

    # We still need a QApplication for the pill overlay and clipboard.
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("caspr-flow")

    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("aaaditt.caspr")
    except (AttributeError, OSError):
        pass

    from .ui.icons import app_icon
    app.setWindowIcon(app_icon())

    controller = AppController(cfg)

    # Pill overlay — stays as a Qt widget
    from .ui.overlay import Pill
    from .ui.correct import CorrectionPopup

    pill = Pill(cfg)
    controller.state_changed.connect(pill.on_state)
    controller.input_level.connect(pill.set_level)
    controller.dictation_done.connect(pill.show_transcript)
    pill.expand_requested.connect(
        lambda text: CorrectionPopup(controller, text).exec()
    )

    # Sound cues
    from .sounds import SoundCues
    cues = SoundCues(cfg)
    controller.state_changed.connect(cues.on_state)

    # WebSocket server runs in a background thread
    ws_server = JsonWsServer(controller)
    ws_thread = threading.Thread(target=ws_server.run, args=(port,), daemon=True)
    ws_thread.start()

    controller.start()
    log.info("caspr server mode: pill + WS on port %d", port)

    code = app.exec()
    controller.shutdown()
    return code
