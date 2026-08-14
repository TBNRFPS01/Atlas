"""Composer (message input) for the ATLAS interface.

Mirrors the HTML ``.composer-area``: a floating, shadowed, rounded input
with an attach button, an auto-growing textarea, voice / stop / send
buttons, attachment chips, and a small footnote. The composer owns the
voice-mode overlay toggle via callbacks into the coordinator.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import tkinter as tk
from tkinter import filedialog

from interface.theme import (
    ACCENT,
    ACCENT_HOVER,
    BACKGROUND,
    BORDER,
    BORDER_STRONG,
    CHAT_MAX_WIDTH,
    FONT_EMOJI,
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_XS,
    INK,
    INK_SOFT,
    IVORY_DEEP,
    MUTED,
    PANEL_BG,
    TEXT_MUTED,
)
from interface.widgets import RoundedButton


class Composer:
    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_send: Callable[[str, list], Any],
        on_stop: Callable[[], Any],
        on_voice: Callable[[], Any],
    ) -> None:
        self.parent = parent
        self._on_send = on_send
        self._on_stop = on_stop
        self._on_voice = on_voice
        self._attachments: list[Path] = []
        self._busy = False

        self.frame = tk.Frame(parent, bg=BACKGROUND)
        self.frame.pack(side="bottom", fill="x")

        # Gradient approximation: a thin border + soft top edge.
        edge = tk.Frame(self.frame, bg=BORDER, height=1)
        edge.pack(side="top", fill="x")

        self.wrap = tk.Frame(self.frame, bg=BACKGROUND)
        self.wrap.pack(fill="x", padx=24, pady=24)

        # Center the composer in the same column as the chat, capped at the
        # maximum message width on wide windows.
        self.column = tk.Frame(self.wrap, bg=BACKGROUND)
        self.wrap.bind("<Configure>", self._on_wrap_configure)

        # Attachments chips
        self.attachments = tk.Frame(self.column, bg=BACKGROUND)
        self.attachments.pack(fill="x", pady=(0, 8))

        # Composer box
        self.box = tk.Frame(
            self.column,
            bg=PANEL_BG,
            highlightbackground=BORDER_STRONG,
            highlightthickness=1,
        )
        self.box.pack(fill="x")

        self.btn_attach = RoundedButton(
            self.box,
            "＋",
            command=self._pick_files,
            bg=PANEL_BG,
            fg=INK_SOFT,
            hover_bg=BACKGROUND,
            font=(FONT_FAMILY, 15, "normal"),
            radius=12,
            width=40,
            height=40,
            outer_bg=PANEL_BG,
        )
        self.btn_attach.pack(side="left", padx=(8, 2), pady=8)

        self.text = tk.Text(
            self.box,
            bg=PANEL_BG,
            fg=INK,
            insertbackground=INK,
            relief="flat",
            wrap="word",
            height=1,
            font=(FONT_FAMILY, FONT_SIZE_BASE + 1),
            padx=8,
            pady=10,
            highlightthickness=0,
        )
        self.text.pack(side="left", fill="both", expand=True, padx=4)
        self.text.insert("1.0", "Message ATLAS...")
        self._placeholder = True
        self.text.bind("<FocusIn>", self._on_focus_in)
        self.text.bind("<FocusOut>", self._on_focus_out)
        self.text.bind("<KeyRelease>", self._on_key)
        self.text.bind("<Return>", self._on_enter_key)

        # Right-side buttons (voice, stop, send)
        self.btn_voice = RoundedButton(
            self.box,
            "🎙",
            command=self._on_voice,
            bg=PANEL_BG,
            fg=INK_SOFT,
            hover_bg=BACKGROUND,
            font=(FONT_EMOJI, 14, "normal"),
            radius=12,
            width=40,
            height=40,
            outer_bg=PANEL_BG,
        )
        self.btn_voice.pack(side="right", padx=(2, 6), pady=8)

        self.btn_send = RoundedButton(
            self.box,
            "↑",
            command=self.send,
            bg=ACCENT,
            fg=BACKGROUND,
            hover_bg=ACCENT_HOVER,
            font=(FONT_FAMILY, 15, "bold"),
            radius=12,
            width=40,
            height=40,
            outer_bg=PANEL_BG,
        )
        self.btn_send.pack(side="right", padx=(2, 8), pady=8)

        self.btn_stop = RoundedButton(
            self.box,
            "■",
            command=self._on_stop,
            bg=ACCENT,
            fg=BACKGROUND,
            hover_bg=ACCENT_HOVER,
            font=(FONT_FAMILY, 12, "normal"),
            radius=12,
            width=40,
            height=40,
            outer_bg=PANEL_BG,
        )
        self.btn_stop.pack(side="right", padx=(2, 8), pady=8)
        self.btn_stop.pack_forget()

        tk.Label(
            self.column,
            text="ATLAS may use local models, memory and configured tools.",
            bg=BACKGROUND,
            fg=MUTED,
            font=(FONT_FAMILY, FONT_SIZE_XS),
        ).pack(pady=(9, 0))

        self._fit_height()

    # ------------------------------------------------------------------
    # Focus / placeholder
    # ------------------------------------------------------------------
    def _on_focus_in(self, _e: tk.Event) -> None:
        if self._placeholder:
            self.text.delete("1.0", "end")
            self._placeholder = False

    def _on_focus_out(self, _e: tk.Event) -> None:
        if not self.text.get("1.0", "end-1c").strip():
            self.text.delete("1.0", "end")
            self.text.insert("1.0", "Message ATLAS...")
            self._placeholder = True

    def _on_key(self, _e: tk.Event) -> None:
        self._fit_height()

    def _fit_height(self) -> None:
        try:
            lines = int(float(self.text.index("end-1c").split(".")[0]))
        except (tk.TclError, ValueError):
            lines = 1
        lines = max(1, min(lines, 6))
        self.text.configure(height=lines)

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _on_enter_key(self, _e: tk.Event) -> str:
        # Enter sends; Shift+Enter inserts a newline.
        state = _e.state
        if state & 0x1:
            return "\x1a"
        self.send()
        return "break"

    def send(self) -> None:
        if self._busy:
            return
        text = self.get_text()
        if not text:
            return
        self.text.delete("1.0", "end")
        self._fit_height()
        attachments = self._attachments.copy()
        self.clear_attachments()
        self._on_send(text, attachments)

    def get_text(self) -> str:
        raw = self.text.get("1.0", "end-1c")
        if not raw.strip():
            return ""
        if raw.strip() == "Message ATLAS...":
            return ""
        return raw.strip()

    def focus_input(self) -> None:
        self.text.focus_set()

    def set_text(self, text: str) -> None:
        """Replace the composer contents (clears the placeholder state)."""
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self._placeholder = False
        self.text.configure(fg=INK)
        self._fit_height()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self.btn_send.pack_forget()
            self.btn_stop.pack(side="right", padx=(2, 8), pady=8)
        else:
            self.btn_stop.pack_forget()
            self.btn_send.pack(side="right", padx=(2, 8), pady=8)

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------
    def _pick_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Attach files",
            parent=self.parent.winfo_toplevel(),
        )
        for path in paths:
            self.add_attachment(Path(path))

    def add_attachment(self, path: Path) -> None:
        if path in self._attachments:
            return
        self._attachments.append(path)
        chip = tk.Frame(
            self.attachments,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=8,
            pady=4,
        )
        chip.pack(side="left", padx=(0, 8))

        tk.Label(
            chip, text="📎  " + path.name, bg=PANEL_BG, fg=INK_SOFT,
            font=(FONT_FAMILY, FONT_SIZE_XS + 1),
        ).pack(side="left")

        remove = tk.Label(
            chip, text="  ✕", bg=PANEL_BG, fg=MUTED, cursor="hand2",
            font=(FONT_FAMILY, FONT_SIZE_XS + 1),
        )
        remove.pack(side="left")
        remove.bind("<Button-1>", lambda _e: self._remove_attachment(chip, path))

    def _remove_attachment(self, chip: tk.Widget, path: Path) -> None:
        if path in self._attachments:
            self._attachments.remove(path)
        chip.destroy()

    def clear_attachments(self) -> None:
        self._attachments.clear()
        for child in self.attachments.winfo_children():
            child.destroy()

    def get_attachments(self) -> list[Path]:
        return self._attachments.copy()

    def _on_wrap_configure(self, event: tk.Event) -> None:
        # Center the composer column and cap it to the message width.
        width = min(CHAT_MAX_WIDTH, max(event.width, 240))
        self.column.place(
            in_=self.wrap,
            relx=0.5,
            y=0,
            anchor="n",
            width=width,
            height=self.column.winfo_reqheight(),
        )
