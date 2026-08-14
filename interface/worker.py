"""Background worker threads for the ATLAS UI.

The worker owns the thread lifecycle for backend calls (router streaming,
one-shot routing, mock replies, and voice listening). Results are pushed
back to the GUI through a callback that places events on the UI's queue,
so no tkinter widget is ever touched from a worker thread.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable


class ChatWorker:
    """Runs backend calls off the UI thread and emits results via a queue.

    ``emit`` is a callable ``emit(kind: str, payload: Any) -> None`` that
    places an event onto the GUI thread's queue. Streaming can be
    interrupted with :meth:`stop`.
    """

    def __init__(self, router, emit: Callable[[str, Any], None]) -> None:
        self.router = router
        self.emit = emit
        self._stop = threading.Event()
        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()

    def stop(self) -> None:
        """Signal any in-flight streaming call to stop producing chunks."""
        self._stop.set()

    def _begin(self) -> None:
        self._stop.clear()

    def stream(self, text: str) -> None:
        """Stream a response from the router, chunk by chunk."""

        def _work() -> None:
            self._begin()
            try:
                for chunk in self.router.stream(text):
                    if self._stop.is_set():
                        break
                    if chunk:
                        self.emit("stream_chunk", chunk)
            except Exception as exc:
                self.emit("error", str(exc))
            finally:
                self.emit("stream_done", None)

        threading.Thread(target=_work, daemon=True).start()

    def route(self, text: str) -> None:
        """Run a one-shot (non-streaming) route call."""

        def _work() -> None:
            self._begin()
            try:
                reply = self.router.route(text)
                self.emit("assistant_reply", reply)
            except Exception as exc:
                self.emit("error", str(exc))

        threading.Thread(target=_work, daemon=True).start()

    def mock(self, text: str) -> None:
        """Fallback echo reply used when no router is available."""

        def _work() -> None:
            self._begin()
            time.sleep(0.3)
            self.emit("assistant_reply", f"Echo: {text}")

        threading.Thread(target=_work, daemon=True).start()

    def listen(self, voice) -> None:
        """Capture one utterance via the voice controller and emit the text."""

        def _work() -> None:
            self._begin()
            try:
                text = voice.listen_once()
                self.emit("voice_text", text)
            except Exception as exc:
                self.emit("error", str(exc))

        threading.Thread(target=_work, daemon=True).start()
