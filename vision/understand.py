"""Screen understanding for ATLAS.

Captures the active screen and produces a human-readable description that
combines (when available) the active window title, an LLM vision description,
and OCR text. Designed to degrade gracefully: if no vision model or OCR engine
is available, it still returns whatever context it could gather.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from vision.screenshot import Screenshot


def _ocr_text(img) -> str:
    """Best-effort OCR using pytesseract, returning '' when unavailable."""
    try:
        import pytesseract  # type: ignore
        from PIL import Image

        return pytesseract.image_to_string(Image.fromarray(img)).strip()
    except Exception:
        return ""


def describe_screen(brain=None, with_ocr: bool = False) -> str:
    """Capture the screen and return a combined description string."""
    img = Screenshot().capture()
    if img is None:
        return "Unable to capture the screen."

    parts: list[str] = []

    # Active window context (cheap, always available on desktop).
    try:
        from tools.automation_tool import AutomationTool

        ctx = AutomationTool().execute(action="context_window")
        if ctx:
            parts.append(f"Active window: {ctx}")
    except Exception:
        pass

    # Vision model description (only if a model is reachable).
    if brain is not None and hasattr(brain, "analyze_image"):
        try:
            from io import BytesIO

            from PIL import Image

            buf = BytesIO()
            Image.fromarray(img).save(buf, format="PNG")
            description = brain.analyze_image(buf.getvalue(), "Describe this screen briefly.")
            if description and all(b not in description.lower() for b in ("request failed", "connection failed", "error")):
                parts.append(f"Vision: {description}")
        except Exception:
            pass

    if with_ocr:
        text = _ocr_text(img)
        if text:
            parts.append(f"OCR: {text[:500]}")

    if not parts:
        return "Screen captured but no description model or OCR is available."
    return "\n".join(parts)


def save_screenshot() -> str:
    """Save a screenshot to the ATLAS screenshots folder and return its path."""
    img = Screenshot().capture()
    if img is None:
        return ""
    folder = Path.home() / ".atlas" / "screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"screenshot-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
    try:
        from PIL import Image

        Image.fromarray(img).save(path)
        return str(path)
    except Exception:
        return ""
