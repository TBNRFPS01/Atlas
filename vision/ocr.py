"""Optical character recognition for ATLAS Vision."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import pytesseract
except Exception:  # pragma: no cover - optional runtime dependency
    pytesseract = None

try:
    import cv2
except Exception:  # pragma: no cover - optional runtime dependency
    cv2 = None


class OCR:
    """Extract text from images using Tesseract OCR."""

    def __init__(self, lang: str = "eng") -> None:
        self.lang = lang

    def extract(self, image: np.ndarray | None) -> str:
        """Extract text from an image array."""
        if image is None:
            return ""

        if pytesseract is None:
            print("Vision: Warning - pytesseract not available; OCR disabled.")
            return ""

        try:
            if cv2 is not None:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            text = pytesseract.image_to_string(gray, lang=self.lang)
            return text.strip()
        except Exception as exc:
            print(f"Vision: Warning - OCR failed: {exc}")
            return ""

    def extract_from_file(self, path: str) -> str:
        """Extract text from an image file."""
        if pytesseract is None:
            return ""

        try:
            return pytesseract.image_to_string(path, lang=self.lang).strip()
        except Exception as exc:
            print(f"Vision: Warning - OCR file failed: {exc}")
            return ""