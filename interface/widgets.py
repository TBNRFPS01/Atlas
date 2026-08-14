"""Reusable tkinter widget primitives for the ATLAS interface.

Most controls are drawn on ``tk.Canvas`` so they can have rounded
corners, precise hover states, and the premium polish of the HTML
prototype. Everything here is theme-agnostic: colors are passed in and
callers source them from :mod:`interface.theme`.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Callable

from interface.theme import (
    ACCENT,
    ACCENT_HOVER,
    BACKGROUND,
    BORDER,
    BORDER_STRONG,
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_XS,
    INK,
    INK_SOFT,
    IVORY,
    IVORY_DEEP,
    IVORY_PANEL,
    MODAL_BACKDROP,
    PANEL_BG,
    TEXT_MUTED,
)


def round_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float = 12,
    **kwargs: Any,
) -> int:
    """Draw a filled rounded rectangle and return its canvas item id."""
    radius = max(0.0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def round_rect_asym(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    r_tl: float = 12,
    r_tr: float = 12,
    r_br: float = 12,
    r_bl: float = 12,
    **kwargs: Any,
) -> int:
    """Draw a filled rounded rectangle with per-corner radii."""
    points = [
        x1 + r_tl, y1,
        x2 - r_tr, y1,
        x2, y1,
        x2, y1 + r_tr,
        x2, y2 - r_br,
        x2, y2,
        x2 - r_br, y2,
        x1 + r_bl, y2,
        x1, y2,
        x1, y2 - r_bl,
        x1, y1 + r_tl,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class RoundedButton(tk.Canvas):
    """A canvas-drawn rounded button with hover feedback.

    Sizes itself from text metrics unless ``width``/``height`` are given.
    Supports a border (``border_color``) and per-state fill via the
    ``hover_bg`` / ``active_bg`` arguments.
    """

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "",
        command: Callable[[], Any] | None = None,
        *,
        bg: str = PANEL_BG,
        fg: str = INK,
        hover_bg: str = BACKGROUND,
        font: tuple[str, int, str] = (FONT_FAMILY, FONT_SIZE_BASE, "normal"),
        radius: float = 12,
        padx: int = 12,
        pady: int = 8,
        width: int | None = None,
        height: int | None = None,
        border_color: str | None = None,
        active_bg: str | None = None,
        outer_bg: str = IVORY_DEEP,
        cursor: str = "hand2",
    ) -> None:
        self._text = text
        self._command = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._active_bg = active_bg or hover_bg
        self._font = font
        self._radius = radius
        self._padx = padx
        self._pady = pady
        self._border_color = border_color
        self._outer_bg = outer_bg
        self._state = "normal"

        f = tkfont.Font(font=font)
        text_w = f.measure(text)
        text_h = f.metrics("linespace")
        w = width if width is not None else text_w + padx * 2 + 4
        h = height if height is not None else text_h + pady * 2 + 2

        super().__init__(
            parent,
            width=w,
            height=h,
            bg=outer_bg,
            highlightthickness=0,
            bd=0,
            cursor=cursor,
        )
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda _e: self._draw())

    # ------------------------------------------------------------------
    def _draw(self, state: str | None = None) -> None:
        state = state or self._state
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2 or h <= 2:
            return

        if state == "active":
            fill = self._active_bg
        elif state == "hover":
            fill = self._hover_bg
        else:
            fill = self._bg

        round_rect(
            self, 1, 1, w - 1, h - 1, self._radius,
            fill=fill,
            outline=self._border_color,
            width=1 if self._border_color is not None else 0,
        )

        f = tkfont.Font(font=self._font)
        cx = w / 2
        cy = h / 2
        self.create_text(cx, cy, text=self._text, fill=self._fg,
                         font=self._font, anchor="center")

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw()

    def set_bg(self, bg: str) -> None:
        self._bg = bg
        self._draw()

    def set_command(self, command: Callable[[], Any] | None) -> None:
        self._command = command

    # ------------------------------------------------------------------
    def _on_enter(self, _e: tk.Event) -> None:
        if self._state != "active":
            self._state = "hover"
            self._draw()

    def _on_leave(self, _e: tk.Event) -> None:
        if self._state != "active":
            self._state = "normal"
            self._draw()

    def _on_press(self, _e: tk.Event) -> None:
        self._state = "active"
        self._draw()

    def _on_release(self, _e: tk.Event) -> None:
        was_active = self._state == "active"
        self._state = "hover"
        self._draw()
        if was_active and self._command is not None:
            self.after(10, self._command)


class Avatar(tk.Canvas):
    """A circular avatar with a centered glyph."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "A",
        *,
        size: int = 34,
        bg: str = ACCENT,
        fg: str = IVORY_DEEP,
        font: tuple[str, int, str] = (FONT_FAMILY, 12, "bold"),
        outer_bg: str = IVORY_DEEP,
        cursor: str = "",
    ) -> None:
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=outer_bg,
            highlightthickness=0,
            bd=0,
            cursor=cursor or "arrow",
        )
        self._text = text
        self._bg = bg
        self._fg = fg
        self._font = font
        self._size = size
        self._draw()
        self.bind("<Configure>", lambda _e: self._draw())

    def _draw(self) -> None:
        self.delete("all")
        s = self._size
        round_rect(self, 1, 1, s - 1, s - 1, s / 2, fill=self._bg, outline="")
        self.create_text(s / 2, s / 2, text=self._text, fill=self._fg,
                         font=self._font, anchor="center")


class Toggle(tk.Canvas):
    """A pill togg le switch (mirrors the HTML ``.switch`` element)."""

    def __init__(
        self,
        parent: tk.Widget,
        value: bool = False,
        on_change: Callable[[bool], Any] | None = None,
        *,
        outer_bg: str = IVORY_DEEP,
    ) -> None:
        super().__init__(
            parent,
            width=45,
            height=26,
            bg=outer_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._value = value
        self._on_change = on_change
        self._track_bg_on = ACCENT
        self._track_bg_off = IVORY_DEEP
        self._knob = IVORY_PANEL
        self._draw()
        self.bind("<Button-1>", self._toggle)

    def _toggle(self, _e: tk.Event | None = None) -> None:
        self._value = not self._value
        self._draw()
        if self._on_change is not None:
            self._on_change(self._value)

    def _draw(self) -> None:
        self.delete("all")
        w, h = 45, 26
        track = self._track_bg_on if self._value else self._track_bg_off
        round_rect(self, 0, 0, w - 1, h - 1, h / 2, fill=track, outline="")
        knob_x = 24 if self._value else 4
        round_rect(self, knob_x, 3, knob_x + 20, 23, 10,
                   fill=self._knob, outline="")

    def get(self) -> bool:
        return self._value

    def set(self, value: bool) -> None:
        self._value = value
        self._draw()


class Toast:
    """A centered bottom pill notification (mirrors the HTML ``.toast``)."""

    def __init__(self, root: tk.Widget) -> None:
        self._root = root
        self._label = tk.Label(
            root,
            text="",
            bg=INK,
            fg=IVORY,
            font=(FONT_FAMILY, 10),
            padx=15,
            pady=9,
        )
        self._after_id: str | None = None

    def show(self, text: str) -> None:
        if self._after_id is not None:
            self._root.after_cancel(self._after_id)
            self._after_id = None
        self._label.config(text=text)
        self._label.place(relx=0.5, rely=1.0, anchor="s", y=-110)
        self._label.lift()
        self._after_id = self._root.after(2200, self._hide)

    def _hide(self) -> None:
        self._after_id = None
        self._label.place_forget()


class Card(tk.Frame):
    """A rounded-surface card that hosts a content frame.

    Drawn on a canvas so it owns rounded corners and a hairline border.
    Content is placed inside ``self.content`` (a normal tk.Frame).
    """

    def __init__(
        self,
        master: tk.Widget,
        *,
        radius: float = 20,
        border_color: str = BORDER_STRONG,
        bg: str = PANEL_BG,
        backdrop_bg: str = MODAL_BACKDROP,
    ) -> None:
        super().__init__(master, bg=backdrop_bg)
        self._radius = radius
        self._border_color = border_color
        self._bg = bg
        self._backdrop = backdrop_bg

        self.canvas = tk.Canvas(self, bg=backdrop_bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.content = tk.Frame(self.canvas, bg=bg)
        self._window_id = self.canvas.create_window(
            radius, radius, window=self.content, anchor="nw"
        )
        self.canvas.bind("<Configure>", self._redraw)

    def _redraw(self, _e: tk.Event | None = None) -> None:
        self.canvas.delete("shape")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        r = self._radius
        if w <= 2 or h <= 2:
            return
        self.canvas.tag_lower(
            round_rect(
                self.canvas, 0, 0, w - 1, h - 1, r,
                fill=self._bg, outline=self._border_color, width=1,
            ),
            "all",
        )
        self.canvas.coords(self._window_id, r, r)
        self.canvas.itemconfigure(
            self._window_id,
            width=max(w - 2 * r, 10),
            height=max(h - 2 * r, 10),
        )


class Modal(tk.Toplevel):
    """A frameless, full-window modal with a dimmed backdrop.

    Covers the parent window so the surrounding application stays visible
    under a dim overlay (matching the HTML modal-backdrop). Closes on
    Escape or when clicking the backdrop outside the centered card.
    """

    def __init__(
        self,
        parent: tk.Widget,
        width: int,
        height: int,
        on_close: Callable[[], Any] | None = None,
        *,
        backdrop_bg: str = MODAL_BACKDROP,
        margin: int = 32,
    ) -> None:
        super().__init__(parent)
        self._on_close = on_close or (lambda: None)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(bg=backdrop_bg)
        self._margin = margin

        parent.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        self._backdrop_bg = backdrop_bg
        self.geometry(f"{pw}x{ph}+{px}+{py}")

        self.card = Card(
            self,
            radius=20,
            border_color=BORDER_STRONG,
            bg=PANEL_BG,
            backdrop_bg=backdrop_bg,
        )
        self.card.place(
            relx=0.5, rely=0.5, anchor="center",
            width=min(width, pw - 2 * margin),
            height=min(height, ph - 2 * margin),
        )

        self.bind("<Escape>", lambda _e: self.close())
        self.bind("<Button-1>", self._on_backdrop_click)
        self.bind("<Configure>", self._on_configure)

        self.deiconify()
        self.lift()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()

    def _on_configure(self, _e: tk.Event) -> None:
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2 or h <= 2:
            return
        self.card.place(
            relx=0.5, rely=0.5, anchor="center",
            width=min(w - 2 * self._margin, w),
            height=min(h - 2 * self._margin, h),
        )

    def _on_backdrop_click(self, event: tk.Event) -> None:
        try:
            x = event.x_root - self.winfo_rootx()
            y = event.y_root - self.winfo_rooty()
            card_w = self.card.winfo_width()
            card_h = self.card.winfo_height()
            cx = (self.winfo_width() - card_w) / 2
            cy = (self.winfo_height() - card_h) / 2
            if not (cx <= x <= cx + card_w and cy <= y <= cy + card_h):
                self.close()
        except tk.TclError:
            pass

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self._on_close is not None:
            self._on_close()