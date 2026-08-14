"""Top navigation bar for the ATLAS interface.

Mirrors the HTML ``.topbar``: a frosted ivory strip with the brand title
on the left and the command / export / settings actions on the right.
"""
from __future__ import annotations

from typing import Any, Callable

import tkinter as tk

from interface.theme import (
    BACKGROUND,
    BORDER,
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_LG,
    FONT_SIZE_XS,
    INK,
    INK_SOFT,
    MUTED,
    PANEL_BG,
    TEXT_MUTED,
)
from interface.widgets import RoundedButton


class TopBar:
    """Builds the header strip and exposes its action buttons."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_menu: Callable[[], Any],
        on_command: Callable[[], Any],
        on_export: Callable[[], Any],
        on_settings: Callable[[], Any],
    ) -> None:
        self.frame = tk.Frame(parent, bg=BACKGROUND, height=68)
        self.frame.pack(side="top", fill="x")
        self.frame.pack_propagate(False)

        divider = tk.Frame(self.frame, bg=BORDER, height=1)
        divider.pack(side="bottom", fill="x")

        # Left: hamburger + brand
        self.btn_menu = RoundedButton(
            self.frame,
            "☰",
            command=on_menu,
            bg=PANEL_BG,
            fg=INK_SOFT,
            hover_bg=BACKGROUND,
            font=(FONT_FAMILY, 15, "normal"),
            radius=10,
            width=36,
            height=36,
            outer_bg=BACKGROUND,
        )
        self.btn_menu.pack(side="left", padx=(16, 6), pady=14)

        brand_row = tk.Frame(self.frame, bg=BACKGROUND)
        brand_row.pack(side="left")

        tk.Label(
            brand_row,
            text="ATLAS",
            bg=BACKGROUND,
            fg=INK,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
        ).pack(side="left")

        tk.Label(
            brand_row,
            text="  Local Intelligence",
            bg=BACKGROUND,
            fg=MUTED,
            font=(FONT_FAMILY, FONT_SIZE_XS + 1, "normal"),
        ).pack(side="left")

        # Right: actions
        actions = tk.Frame(self.frame, bg=BACKGROUND)
        actions.pack(side="right", padx=16)

        self.btn_command = RoundedButton(
            actions,
            "⌘",
            command=on_command,
            bg=PANEL_BG,
            fg=INK_SOFT,
            hover_bg=BACKGROUND,
            font=(FONT_FAMILY, 14, "normal"),
            radius=10,
            width=36,
            height=36,
            outer_bg=BACKGROUND,
        )
        self.btn_command.pack(side="right", padx=2)

        self.btn_export = RoundedButton(
            actions,
            "⇩",
            command=on_export,
            bg=PANEL_BG,
            fg=INK_SOFT,
            hover_bg=BACKGROUND,
            font=(FONT_FAMILY, 14, "normal"),
            radius=10,
            width=36,
            height=36,
            outer_bg=BACKGROUND,
        )
        self.btn_export.pack(side="right", padx=2)

        self.btn_settings = RoundedButton(
            actions,
            "⚙",
            command=on_settings,
            bg=PANEL_BG,
            fg=INK_SOFT,
            hover_bg=BACKGROUND,
            font=(FONT_FAMILY, 14, "normal"),
            radius=10,
            width=36,
            height=36,
            outer_bg=BACKGROUND,
        )
        self.btn_settings.pack(side="right", padx=2)
