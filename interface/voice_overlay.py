"""Voice-mode overlay for the ATLAS interface.

Mirrors the HTML ``.voice-overlay``: a bottom panel with a pulsing orb,
a status line, an animated equalizer wave, and a cancel button. The
coordinator drives it from the voice backend worker thread.
"""
from __future__ import annotations

from typing import Any, Callable

import tkinter as tk

from interface.theme import (
    ACCENT,
    BACKGROUND,
    BORDER,
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_XS,
    INK,
    INK_SOFT,
    MUTED,
    PANEL_BG,
    TEXT_MUTED,
)
from interface.widgets import Avatar


class VoiceOverlay:
    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_cancel: Callable[[], Any],
        on_orb: Callable[[], Any],
    ) -> None:
        self.parent = parent
        self._on_cancel = on_cancel
        self._on_orb = on_orb

        self.frame = tk.Frame(parent, bg=BACKGROUND)
        self._bars: list[int] = []
        self._wave_after: str | None = None
        self._pulse_after: str | None = None

        self._build()

    def _build(self) -> None:
        self.frame.pack(side="bottom", fill="x")
        self.frame.pack_forget()

        wrap = tk.Frame(self.frame, bg=BACKGROUND)
        wrap.pack(fill="x", padx=24, pady=24)

        self.panel = tk.Frame(
            wrap,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            height=210,
        )
        self.panel.pack(fill="x")
        self.panel.pack_propagate(False)

        center = tk.Frame(self.panel, bg=PANEL_BG)
        center.pack(expand=True)

        self.orb = Avatar(
            center, "🎙", size=76, bg=ACCENT, fg=BACKGROUND,
            font=("Segoe UI Emoji", 22, "normal"), outer_bg=PANEL_BG,
        )
        self.orb.pack(pady=(16, 8))
        self.orb.bind("<Button-1>", lambda _e: self._on_orb())

        self.status = tk.Label(
            center, text="Listening...", bg=PANEL_BG, fg=ACCENT,
            font=(FONT_FAMILY, 15, "bold"),
        )
        self.status.pack(pady=(4, 8))

        self.wave = tk.Canvas(
            center, bg=PANEL_BG, highlightthickness=0, width=120, height=26
        )
        self.wave.pack(pady=(0, 6))

        self.cancel = tk.Label(
            center,
            text="Cancel voice mode",
            bg=PANEL_BG,
            fg=MUTED,
            font=(FONT_FAMILY, FONT_SIZE_XS + 1),
            cursor="hand2",
        )
        self.cancel.pack(pady=(4, 14))
        self.cancel.bind("<Button-1>", lambda _e: self._on_cancel())

    # ------------------------------------------------------------------
    # Show / hide
    # ------------------------------------------------------------------
    def show(self, status: str = "Listening...") -> None:
        self.status.config(text=status)
        self.frame.pack(side="bottom", fill="x")
        self.frame.lift()
        self._start_animation()

    def hide(self) -> None:
        self.frame.pack_forget()
        self._stop_animation()

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def _start_animation(self) -> None:
        self._draw_bars()
        self._pulse_after = self.parent.after(0, self._pulse_tick)
        self._wave_tick()

    def _stop_animation(self) -> None:
        if self._wave_after is not None:
            self.parent.after_cancel(self._wave_after)
            self._wave_after = None
        if self._pulse_after is not None:
            self.parent.after_cancel(self._pulse_after)
            self._pulse_after = None

    def _draw_bars(self) -> None:
        self.wave.delete("all")
        heights = [8, 16, 24, 13, 20]
        self._bars.clear()
        for i, h in enumerate(heights):
            x = 10 + i * 26
            bar = self.wave.create_rectangle(
                x, 26 - h, x + 4, 26,
                fill=ACCENT, outline="",
            )
            self._bars.append(bar)

    def _wave_tick(self) -> None:
        import random

        for i, bar in enumerate(self._bars):
            h = random.randint(8, 26)
            x0 = 10 + i * 26
            self.wave.coords(bar, x0, 26 - h, x0 + 4, 26)
        self._wave_after = self.parent.after(140, self._wave_tick)

    def _pulse_tick(self) -> None:
        if self._pulse_after is not None:
            self.parent.after_cancel(self._pulse_after)
            self._pulse_after = None
        self._pulse_toggle = not getattr(self, "_pulse_toggle", False)
        try:
            self.orb.itemconfigure("all", width=3 if self._pulse_toggle else 0)
        except tk.TclError:
            pass
        self._pulse_after = self.parent.after(900, self._pulse_tick)
