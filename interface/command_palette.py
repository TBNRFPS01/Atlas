"""Command palette for the ATLAS interface.

Mirrors the HTML ``.command-palette``: a centered modal with a search
input and a filtered list of commands (New Chat, New Project, Temporary
Chat, Start Voice Mode, Open Settings). Opened with Ctrl+K.
"""
from __future__ import annotations

from typing import Any, Callable

import tkinter as tk

from interface.theme import (
    ACCENT,
    BORDER,
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    INK,
    INK_SOFT,
    MUTED,
    PANEL_BG,
    TEXT_MUTED,
)
from interface.widgets import Modal


class CommandPalette:
    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_new: Callable[[], Any],
        on_project: Callable[[], Any],
        on_temporary: Callable[[], Any],
        on_voice: Callable[[], Any],
        on_settings: Callable[[], Any],
    ) -> None:
        self.parent = parent
        self._actions = {
            "new": on_new,
            "project": on_project,
            "temporary": on_temporary,
            "voice": on_voice,
            "settings": on_settings,
        }
        self._modal: Modal | None = None

    def open(self) -> None:
        if self._modal is not None:
            return
        self._modal = Modal(self.parent, width=620, height=420,
                            on_close=self._closed)
        body = self._modal.card.content

        self.search = tk.Entry(
            body,
            bg=PANEL_BG,
            fg=INK,
            insertbackground=INK,
            relief="flat",
            font=(FONT_FAMILY, 14),
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        self.search.pack(fill="x", padx=18, pady=(16, 4), ipady=8)
        self.search.insert(0, "Search ATLAS...")
        self.search.bind("<FocusIn>", self._on_focus_in)
        self.search.bind("<FocusOut>", self._on_focus_out)
        self.search.bind("<KeyRelease>", self._on_search)
        self.search.focus_set()

        self.list_box = tk.Frame(body, bg=PANEL_BG)
        self.list_box.pack(fill="both", expand=True, padx=8, pady=(6, 12))

        self._rows: list[tuple[tk.Frame, str]] = []
        commands = [
            ("new", "＋", "New Chat", "Start a fresh conversation"),
            ("project", "📁", "New Project", "Organize chats, files and context"),
            ("temporary", "🕶", "Temporary Chat", "No history or persistent memory"),
            ("voice", "🎙", "Start Voice Mode", "Talk directly to ATLAS"),
            ("settings", "⚙", "Open Settings", "Memory, models, tools and more"),
        ]
        for action, icon, name, desc in commands:
            self._rows.append(self._command_row(self.list_box, action, icon, name, desc))

    def _closed(self) -> None:
        self._modal = None

    def close(self) -> None:
        if self._modal is not None:
            self._modal.close()

    def _command_row(
        self,
        parent: tk.Widget,
        action: str,
        icon: str,
        name: str,
        desc: str,
    ) -> tuple[tk.Frame, str]:
        row = tk.Frame(parent, bg=PANEL_BG, cursor="hand2")
        row.pack(fill="x", pady=2)

        icon_bg = tk.Frame(row, bg="#F1E3E3", width=32, height=32)
        icon_bg.pack(side="left", padx=(10, 12))
        icon_bg.pack_propagate(False)
        tk.Label(icon_bg, text=icon, bg="#F1E3E3", fg=ACCENT,
                 font=(FONT_FAMILY, 13)).pack(expand=True)

        text = tk.Frame(row, bg=PANEL_BG)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=name, bg=PANEL_BG, fg=INK,
                 font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"), anchor="w"
                 ).pack(fill="x")
        tk.Label(text, text=desc, bg=PANEL_BG, fg=MUTED,
                 font=(FONT_FAMILY, FONT_SIZE_XS + 1), anchor="w"
                 ).pack(fill="x")

        def _enter(_e: tk.Event) -> None:
            row.configure(bg="#F7F0E2")
            for child in row.winfo_children():
                child.configure(bg="#F7F0E2")

        def _leave(_e: tk.Event) -> None:
            row.configure(bg=PANEL_BG)
            for child in row.winfo_children():
                child.configure(bg=PANEL_BG)

        def _click(_e: tk.Event) -> None:
            self.close()
            handler = self._actions.get(action)
            if handler is not None:
                self.parent.after(80, handler)

        row.bind("<Enter>", _enter)
        row.bind("<Leave>", _leave)
        row.bind("<Button-1>", _click)
        for child in row.winfo_children():
            child.bind("<Enter>", _enter)
            child.bind("<Leave>", _leave)
            child.bind("<Button-1>", _click)
        return row, action

    # ------------------------------------------------------------------
    def _on_focus_in(self, _e: tk.Event) -> None:
        if self.search.get() == "Search ATLAS...":
            self.search.delete(0, "end")

    def _on_focus_out(self, _e: tk.Event) -> None:
        if not self.search.get():
            self.search.insert(0, "Search ATLAS...")

    def _on_search(self, _e: tk.Event) -> None:
        query = self.search.get().strip().lower()
        for row, action in self._rows:
            if query in action or query in self._row_text(row):
                row.pack(fill="x", pady=2)
            else:
                row.pack_forget()

    def _row_text(self, row: tk.Frame) -> str:
        text = " ".join(
            lbl.cget("text")
            for child in row.winfo_children()
            for lbl in child.winfo_children()
            if isinstance(lbl, tk.Label)
        ).lower()
        return text
