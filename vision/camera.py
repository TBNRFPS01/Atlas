"""Webcam capture utilities for ATLAS Vision."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - optional runtime dependency
    cv2 = None


class Camera:
    """Capture images from a webcam or other video device."""

    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480) -> None:
        self.device_index = device_index
        self.width = width
        self.height = height
        self._cap: Any | None = None

    def _ensure_camera(self) -> Any | None:
        """Lazily open the camera device."""
        if cv2 is None:
            return None
        if self._cap is None:
            try:
                self._cap = cv2.VideoCapture(self.device_index)
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            except Exception:
                return None
        return self._cap

    def capture(self) -> np.ndarray | None:
        """Capture a single frame from the camera."""
        cap = self._ensure_camera()
        if cap is None:
            print("Vision: Warning - OpenCV not available; webcam disabled.")
            return None

        try:
            success, frame = cap.read()
            if not success:
                return None
            return frame[:, :, :3]  # Drop alpha channel if present
        except Exception as exc:
            print(f"Vision: Warning - camera capture failed: {exc}")
            return None

    def release(self) -> None:
        """Release the camera device."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None