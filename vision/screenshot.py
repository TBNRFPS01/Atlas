"""Screenshot capture utilities for ATLAS Vision."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import mss
except Exception:  # pragma: no cover - optional runtime dependency
    mss = None


class Screenshot:
    """Capture screenshots of the desktop or specific regions."""

    def __init__(self, monitor: int = 1) -> None:
        self.monitor = monitor
        self._sct: Any | None = None

    def _ensure_sct(self) -> Any | None:
        """Lazily initialize the mss instance."""
        if mss is None:
            return None
        if self._sct is None:
            try:
                self._sct = mss.mss()
            except Exception:
                return None
        return self._sct

    def capture(self) -> np.ndarray | None:
        """Capture the full primary monitor as a numpy array."""
        sct = self._ensure_sct()
        if sct is None:
            print("Vision: Warning - mss not available; screenshot disabled.")
            return None

        try:
            monitor = sct.monitors[self.monitor]
            raw = sct.grab(monitor)
            img = np.array(raw)
            return img[:, :, :3]  # Drop alpha channel
        except Exception as exc:
            print(f"Vision: Warning - screenshot failed: {exc}")
            return None

    def capture_region(self, left: int, top: int, width: int, height: int) -> np.ndarray | None:
        """Capture a specific rectangular region of the screen."""
        sct = self._ensure_sct()
        if sct is None:
            return None

        try:
            region = {"left": left, "top": top, "width": width, "height": height}
            raw = sct.grab(region)
            img = np.array(raw)
            return img[:, :, :3]
        except Exception as exc:
            print(f"Vision: Warning - region capture failed: {exc}")
            return None

    def save(self, path: str) -> bool:
        """Save the current screenshot to a file."""
        try:
            from PIL import Image

            img = self.capture()
            if img is None:
                return False
            Image.fromarray(img).save(path)
            return True
        except Exception as exc:
            print(f"Vision: Warning - screenshot save failed: {exc}")
            return False