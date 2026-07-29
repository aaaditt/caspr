"""Coordinates one live-typing session: consumes audio blocks fed from the
audio callback thread, keeps a running streaming-ASR hypothesis, and keeps
the focused window's typed text in sync with it via backspace+retype.

Runs on a dedicated thread per dictation (started/joined by AppController) --
NOT the audio callback thread, so decode latency never risks dropping audio
blocks, and NOT the shared pipeline executor, since this loop must run
concurrently with the hold while that executor stays idle.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable

from .diff import compute_correction

log = logging.getLogger(__name__)

_FINISH = object()
_CANCEL = object()


class LiveTypingSession:
    """One instance per dictation hold. `feed_block` is safe to call from the
    audio callback thread; `run` must be called on its own worker thread."""

    def __init__(self, transcriber, type_text: Callable[[str], None], backspace: Callable[[int], None]):
        self._transcriber = transcriber
        self._type_text = type_text
        self._backspace = backspace
        self._queue: queue.Queue = queue.Queue()
        self.typed_text = ""

    def feed_block(self, block) -> None:
        self._queue.put(block)

    def finish(self) -> None:
        """Normal end of hold: stop consuming new audio, leave typed_text on
        screen for the caller's release-time batch reconciliation."""
        self._queue.put(_FINISH)

    def cancel(self) -> None:
        """The dictation was discarded: erase everything this session typed."""
        self._queue.put(_CANCEL)

    def run(self) -> None:
        """Blocks until finish()/cancel(). Call on a dedicated thread."""
        while True:
            item = self._queue.get()
            if item is _FINISH:
                return
            if item is _CANCEL:
                if self.typed_text:
                    self._backspace(len(self.typed_text))
                    self.typed_text = ""
                return
            hypothesis = self._transcriber.feed(item)
            if not hypothesis or hypothesis == self.typed_text:
                continue
            log.info("live hypothesis: %r", hypothesis)
            backspaces, insert = compute_correction(self.typed_text, hypothesis)
            backspaces = min(backspaces, len(self.typed_text))  # hard safety clamp
            self._backspace(backspaces)
            if insert:
                self._type_text(insert)
            self.typed_text = hypothesis
