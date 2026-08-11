"""Vision analyzer for image understanding using LLM vision models."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - optional runtime dependency
    cv2 = None


class VisionAnalyzer:
    """Analyze screenshots or images using LLM vision capabilities."""

    def __init__(self, brain: Any | None = None) -> None:
        self.brain = brain

    def analyze(self, image: np.ndarray | None, prompt: str = "Describe what you see.") -> str:
        """Analyze an image and return a description or answer to a prompt."""
        if image is None:
            return "No image to analyze."

        if self.brain is None:
            return "Vision analyzer requires a brain instance."

        try:
            if cv2 is not None:
                _, buffer = cv2.imencode(".png", image)
                image_bytes = buffer.tobytes()
            else:
                import io
                import PIL.Image

                buffer = io.BytesIO()
                PIL.Image.fromarray(image).save(buffer, format="PNG")
                image_bytes = buffer.getvalue()

            return self.brain.analyze_image(image_bytes, prompt)
        except Exception as exc:
            print(f"Vision: Warning - image analysis failed: {exc}")
            return f"Analysis failed: {exc}"

    def describe(self, image: np.ndarray | None) -> str:
        """Return a natural language description of the image content."""
        return self.analyze(image, "Describe this image in detail.")

    def find_text(self, image: np.ndarray | None) -> str:
        """Find and return any visible text in the image."""
        return self.analyze(image, "Extract all visible text from this image.")

    def count_objects(self, image: np.ndarray | None) -> str:
        """Count distinct objects visible in the image."""
        return self.analyze(image, "Count the number of distinct objects in this image.")