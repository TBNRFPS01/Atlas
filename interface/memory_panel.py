"""Memory manager modal for the ATLAS interface.

Mirrors the HTML "Manage Memory" intent: a centered dialog listing saved
memory records from the backend ``FactStore`` with the ability to delete
individual entries or clear them all.
"""
from __future__ import annotations

from typing import Any

import tkinter as tk

from interface.theme import (
    ACCENT,
    BACKGROUND,
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


class MemoryPanel:
    def __init__(self, parent: tk.Widget, memory) -> None:
        self.parent = parent
        self.memory = memory
        self._modal: Modal | None = None

    def open(self) -> None:
        if self._modal is not None:
            return
        self._modal = Modal(self.parent, width=560, height=480,
                            on_close=self._closed)
        body = self._modal.card.content
        self._build(body)

    def _closed(self) -> None:
        self._modal = None

    def close(self) -> None:
        if self._modal is not None:
            self._modal.close()

    # ------------------------------------------------------------------
    def _build(self, body: tk.Frame) -> None:
        header = tk.Frame(body, bg=PANEL_BG)
        header.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(header, text="Saved memories", bg=PANEL_BG, fg=ACCENT,
                 font=(FONT_FAMILY, 18, "bold")).pack(side="left")

        clear = tk.Label(header, text="Clear all", bg=PANEL_BG, fg=MUTED,
                         font=(FONT_FAMILY, FONT_SIZE_XS + 1), cursor="hand2")
        clear.pack(side="right")
        clear.bind("<Button-1>", lambda _e: self._clear_all())

        self.list_box = tk.Frame(body, bg=PANEL_BG)
        self.list_box.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        self._render()

    def _records(self) -> list[Any]:
        if self.memory is None:
            return []
        try:
            if hasattr(self.memory, "db") and hasattr(self.memory.db, "recent"):
                return self.memory.db.recent(limit=50)
            if hasattr(self.memory, "recent"):
                return self.memory.recent(limit=50)
        except Exception:
            pass
        return []

    def _render(self) -> None:
        for child in self.list_box.winfo_children():
            child.destroy()

        records = self._records()
        if not records:
            tk.Label(
                self.list_box,
                text="No memories stored yet.\nAsk ATLAS to remember something.",
                bg=PANEL_BG, fg=MUTED,
                font=(FONT_FAMILY, FONT_SIZE_SM), justify="center",
            ).pack(pady=40)
            return

        for rec in records:
            row = tk.Frame(
                self.list_box, bg=PANEL_BG,
                highlightbackground=BORDER, highlightthickness=1,
                padx=12, pady=8,
            )
            row.pack(fill="x", pady=4)

            cat = tk.Label(
                row, text=rec.category.upper(), bg=PANEL_BG, fg=ACCENT,
                font=(FONT_FAMILY, FONT_SIZE_XS, "bold"), anchor="w",
            )
            cat.pack(fill="x")

            content = rec.content.split("=", 1)[-1] if "=" in rec.content else rec.content
            tk.Label(
                row, text=content, bg=PANEL_BG, fg=INK,
                font=(FONT_FAMILY, FONT_SIZE_SM), anchor="w", justify="left",
                wraplength=440,
            ).pack(fill="x", pady=(3, 0))

            remove = tk.Label(
                row, text="✕", bg=PANEL_BG, fg=MUTED, cursor="hand2",
                font=(FONT_FAMILY, FONT_SIZE_XS + 1),
            )
            remove.pack(anchor="e")
            remove.bind("<Button-1>", lambda _e, rid=rec.id: self._delete(rid))

    def _delete(self, memory_id: int) -> None:
        if self.memory is None:
            return
        try:
            if hasattr(self.memory, "db"):
                self.memory.db.forget(memory_id=memory_id)
            elif hasattr(self.memory, "forget_by_id"):
                self.memory.forget_by_id(memory_id)
        except Exception:
            pass
        self._render()

    def _clear_all(self) -> None:
        if self.memory is None:
            return
        try:
            records = self._records()
            db = getattr(self.memory, "db", None)
            for rec in records:
                if db is not None:
                    db.forget(memory_id=rec.id)
        except Exception:
            pass
        self._render()
