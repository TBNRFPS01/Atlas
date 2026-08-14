"""Small runtime fixes for ATLAS's desktop UI.

Kept separate from the generated UI modules so the fixes are easy to audit.
"""
from __future__ import annotations


def apply() -> None:
    """Install defensive fixes before the UI is constructed."""
    from interface.gui import ATLASGUI

    def stop_generation(self) -> None:
        worker = self._worker_handle()
        worker.stop()
        self._pending_chunks.clear()
        self._stop_thinking()
        # Do not leave the composer permanently locked if a backend generator
        # stalls after cancellation. A later stream_done event is harmless.
        self.streaming = False
        self._set_busy(False)
        self.show_toast("Generation stopped")

    ATLASGUI.stop_generation = stop_generation
