"""ATLAS chat surface translated from the HTML layout into stable Tkinter.

The important geometry rule here is simple: the canvas owns one centered
content column, while the welcome screen gets an explicit viewport height.
Suggestion cards have explicit dimensions instead of disabling geometry
propagation and hoping Tkinter invents a height.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import tkinter as tk
from tkinter import ttk

from interface.theme import (
    ACCENT,
    BACKGROUND,
    BORDER,
    BORDER_STRONG,
    CHAT_MAX_WIDTH,
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    INK,
    INK_SOFT,
    MUTED,
    PANEL_BG,
)
from interface.widgets import Avatar, round_rect_asym


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


class _Bubble(tk.Canvas):
    """HTML-style rounded user bubble."""

    def __init__(self, parent: tk.Widget, text: str, max_width: int = 540) -> None:
        super().__init__(parent, bg=BACKGROUND, highlightthickness=0, bd=0)
        self._max_width = max_width
        self._padx = 16
        self._pady = 12
        self._label = tk.Label(
            self,
            text=text,
            bg="#FFFDF8",
            fg=INK,
            font=(FONT_FAMILY, FONT_SIZE_BASE, "normal"),
            justify="left",
            anchor="nw",
            wraplength=max_width,
        )
        self._label.pack()
        self.update_idletasks()
        self._layout()

    def _layout(self) -> None:
        self._label.update_idletasks()
        req_w = min(max(1, self._label.winfo_reqwidth()), self._max_width)
        req_h = max(1, self._label.winfo_reqheight())
        width = req_w + self._padx * 2
        height = req_h + self._pady * 2
        self.configure(width=width, height=height)
        self.delete("all")
        round_rect_asym(
            self,
            1, 1, width - 1, height - 1,
            r_tl=5, r_tr=16, r_br=16, r_bl=16,
            fill="#FFFDF8", outline=BORDER, width=1,
        )
        self.create_window(
            self._padx, self._pady,
            window=self._label,
            anchor="nw",
            width=max(1, min(self._max_width, width - self._padx * 2)),
        )

    def set_text(self, text: str) -> None:
        self._label.configure(text=text)
        self._layout()

    def get_text(self) -> str:
        return str(self._label.cget("text"))


class ChatView:
    """Scrollable chat/welcome surface matching the HTML hierarchy."""

    def __init__(
        self,
        parent: tk.Widget,
        messages: list[ChatMessage],
        *,
        on_copy: Callable[[str], Any],
        on_edit: Callable[[str], Any],
        on_regenerate: Callable[[], Any],
        on_toast: Callable[[str], Any],
        on_suggestion: Callable[[str], Any] | None = None,
    ) -> None:
        self.parent = parent
        self.messages = messages
        self._on_copy = on_copy
        self._on_edit = on_edit
        self._on_regenerate = on_regenerate
        self._on_toast = on_toast
        self._on_suggestion = on_suggestion
        self._rows: list[dict[str, Any]] = []
        self._assistant_labels: list[tk.Label] = []
        self._thinking_label: tk.Label | None = None
        self._build()

    def _build(self) -> None:
        self.container = tk.Frame(self.parent, bg=BACKGROUND)
        self.container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            self.container, bg=BACKGROUND, highlightthickness=0, bd=0
        )
        self.scrollbar = ttk.Scrollbar(
            self.container, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.chat_frame = tk.Frame(self.canvas, bg=BACKGROUND)
        self._chat_window = self.canvas.create_window(
            0, 0, window=self.chat_frame, anchor="nw"
        )

        self.chat_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._build_welcome()

    def _on_frame_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        width = max(1, event.width)
        content_w = min(width, CHAT_MAX_WIDTH)
        x = max(0, (width - content_w) // 2)
        self.canvas.itemconfigure(self._chat_window, width=content_w)
        self.canvas.coords(self._chat_window, x, 0)

        if not self._rows:
            # Explicit height is what gives the HTML-like welcome stage a
            # real viewport to center itself inside.
            self.canvas.itemconfigure(self._chat_window, height=max(1, event.height))
        else:
            self.canvas.itemconfigure(self._chat_window, height="")

        self._update_wraplength(content_w)

    def _update_wraplength(self, width: int) -> None:
        body_width = max(180, width - 60)
        for label in self._assistant_labels:
            label.configure(wraplength=body_width)

    def _build_welcome(self) -> None:
        self.welcome = tk.Frame(self.chat_frame, bg=BACKGROUND)
        self.welcome.pack(fill="both", expand=True)

        stage = tk.Frame(self.welcome, bg=BACKGROUND)
        stage.place(relx=0.5, rely=0.46, anchor="center")

        tk.Label(
            stage,
            text="What are we building?",
            bg=BACKGROUND,
            fg=ACCENT,
            font=(FONT_FAMILY, 34, "bold"),
        ).pack()

        tk.Label(
            stage,
            text="ATLAS is ready. Build something, solve something,\n"
                 "explore an idea, or throw a problem at the machine.",
            bg=BACKGROUND,
            fg=INK_SOFT,
            font=(FONT_FAMILY, FONT_SIZE_BASE + 1, "normal"),
            justify="center",
        ).pack(pady=(14, 30))

        grid = tk.Frame(stage, bg=BACKGROUND)
        grid.pack()

        suggestions = [
            ("Build something", "Create a project or application."),
            ("Explain something", "Break down a difficult concept."),
            ("Analyze something", "Inspect code, data or a problem."),
            ("Brainstorm", "Throw ideas into ATLAS."),
        ]
        for index, (title, subtitle) in enumerate(suggestions):
            card = self._suggestion_card(grid, title, subtitle)
            card.grid(row=index // 2, column=index % 2, padx=6, pady=6)

    def _suggestion_card(self, parent: tk.Widget, title: str, subtitle: str) -> tk.Frame:
        # Explicit height fixes the old "two horizontal lines" bug.
        card = tk.Frame(
            parent,
            bg="#FFFDF8",
            width=280,
            height=88,
            highlightbackground=BORDER,
            highlightthickness=1,
            cursor="hand2",
        )
        card.grid_propagate(False)

        inner = tk.Frame(card, bg="#FFFDF8")
        inner.pack(fill="both", expand=True, padx=14, pady=11)

        tk.Label(
            inner,
            text=title,
            bg="#FFFDF8",
            fg=INK,
            font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            inner,
            text=subtitle,
            bg="#FFFDF8",
            fg=MUTED,
            font=(FONT_FAMILY, FONT_SIZE_XS + 1),
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        def enter(_event: tk.Event) -> None:
            card.configure(highlightbackground=ACCENT)

        def leave(_event: tk.Event) -> None:
            card.configure(highlightbackground=BORDER)

        def click(_event: tk.Event) -> None:
            if self._on_suggestion:
                self._on_suggestion(title)

        for widget in (card, inner, *inner.winfo_children()):
            widget.bind("<Enter>", enter)
            widget.bind("<Leave>", leave)
            widget.bind("<Button-1>", click)
        return card

    def _on_mousewheel(self, event: tk.Event) -> None:
        containing = self.canvas.winfo_containing(event.x_root, event.y_root)
        if containing is not None:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def auto_scroll(self) -> None:
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def clear(self) -> None:
        for row in self._rows:
            row["frame"].destroy()
        self._rows.clear()
        self._assistant_labels.clear()
        self._thinking_label = None
        self.welcome.pack(fill="both", expand=True)
        self.canvas.after_idle(self.auto_scroll)

    def hide_welcome(self) -> None:
        self.welcome.pack_forget()
        self.canvas.itemconfigure(self._chat_window, height="")

    def _row(self) -> tk.Frame:
        row = tk.Frame(self.chat_frame, bg=BACKGROUND)
        row.pack(fill="x", padx=8, pady=(0, 26))
        return row

    def render_message(self, message: ChatMessage, append: bool = True) -> None:
        if message.role == "user":
            self._render_user(message)
        elif message.role == "assistant":
            self._render_assistant(message)
        else:
            self._render_system(message)
        if append:
            self.auto_scroll()

    def _render_user(self, message: ChatMessage) -> None:
        row = self._row()
        body = tk.Frame(row, bg=BACKGROUND)
        body.pack(side="left", fill="x", expand=True)
        bubble = _Bubble(body, message.content)
        bubble.pack(anchor="w")
        actions = self._actions_row(body, "user", message.content)
        self._rows.append({"frame": row, "bubble": bubble, "actions": actions, "message": message})
        self._bind_hover(row, actions)

    def _render_assistant(self, message: ChatMessage) -> None:
        row = self._row()
        avatar = Avatar(
            row, "A", size=34, bg=ACCENT, fg=BACKGROUND,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"), outer_bg=BACKGROUND,
        )
        avatar.pack(side="left", padx=(0, 12))

        body = tk.Frame(row, bg=BACKGROUND)
        body.pack(side="left", fill="x", expand=True)
        header = tk.Frame(body, bg=BACKGROUND)
        header.pack(fill="x")
        tk.Label(
            header, text="ATLAS", bg=BACKGROUND, fg=INK,
            font=(FONT_FAMILY, FONT_SIZE_SM + 1, "bold"),
        ).pack(side="left")
        tk.Label(
            header, text="   now", bg=BACKGROUND, fg=MUTED,
            font=(FONT_FAMILY, FONT_SIZE_XS + 1),
        ).pack(side="left")

        content = tk.Label(
            body,
            text=message.content,
            bg=BACKGROUND,
            fg=INK,
            font=(FONT_FAMILY, FONT_SIZE_BASE + 1, "normal"),
            justify="left",
            anchor="nw",
            wraplength=600,
        )
        content.pack(fill="x", pady=(6, 0))
        content.bind("<Button-1>", lambda _e: self._on_copy(message.content))
        self._assistant_labels.append(content)

        actions = self._actions_row(body, "assistant", message.content)
        self._rows.append({"frame": row, "content": content, "actions": actions, "message": message})
        self._bind_hover(row, actions)

    def _render_system(self, message: ChatMessage) -> None:
        row = self._row()
        tk.Label(
            row, text=message.content, bg="#FFF7E6", fg=INK_SOFT,
            font=(FONT_FAMILY, FONT_SIZE_SM, "italic"), justify="left",
            anchor="w", wraplength=600, padx=10, pady=6,
        ).pack(fill="x")
        self._rows.append({"frame": row, "message": message})

    def _actions_row(self, body: tk.Widget, role: str, text: str) -> tk.Frame:
        actions = tk.Frame(body, bg=BACKGROUND)
        # Keep it managed. Hiding/showing with pack_forget is stable.
        actions.pack(fill="x", pady=(4, 0))
        actions.pack_forget()

        def button(glyph: str, command: Callable[[], Any]) -> None:
            item = tk.Label(
                actions, text=glyph, bg=BACKGROUND, fg=MUTED,
                font=(FONT_FAMILY, 13), cursor="hand2", padx=6, pady=2,
            )
            item.pack(side="left")
            item.bind("<Enter>", lambda _e: item.configure(fg=ACCENT))
            item.bind("<Leave>", lambda _e: item.configure(fg=MUTED))
            item.bind("<Button-1>", lambda _e: command())

        button("⧉", lambda: self._on_copy(text))
        if role == "user":
            button("✎", lambda: self._on_edit(text))
            button("🌿", lambda: self._on_toast("Conversation branch created"))
        else:
            button("↻", self._on_regenerate)
            button("📌", lambda: self._on_toast("Message pinned"))
            button("ⓘ", lambda: self._on_toast("ATLAS · local model"))
        return actions

    def _bind_hover(self, row: tk.Frame, actions: tk.Frame) -> None:
        def show(_event: tk.Event) -> None:
            actions.pack(fill="x", pady=(4, 0))

        def hide(_event: tk.Event) -> None:
            actions.pack_forget()

        row.bind("<Enter>", show)
        row.bind("<Leave>", hide)
        for child in row.winfo_children():
            child.bind("<Enter>", show)
            child.bind("<Leave>", hide)

    def update_last_message(self) -> None:
        if not self.messages or not self._rows:
            return
        message = self.messages[-1]
        row = self._rows[-1]
        if message.role == "assistant" and "content" in row:
            row["content"].configure(text=message.content)
            self.canvas.update_idletasks()
            self.auto_scroll()
        elif message.role == "user" and "bubble" in row:
            row["bubble"].set_text(message.content)
            self.canvas.update_idletasks()
            self.auto_scroll()

    def set_thinking(self, dots: str) -> None:
        if self._thinking_label is None:
            row = tk.Frame(self.chat_frame, bg=BACKGROUND)
            row.pack(fill="x", padx=8, pady=(0, 20))
            avatar = Avatar(
                row, "A", size=34, bg=ACCENT, fg=BACKGROUND,
                font=(FONT_FAMILY, FONT_SIZE_SM, "bold"), outer_bg=BACKGROUND,
            )
            avatar.pack(side="left", padx=(0, 12))
            self._thinking_label = tk.Label(
                row, text=f"ATLAS is thinking{dots}", bg=BACKGROUND,
                fg=MUTED, font=(FONT_FAMILY, FONT_SIZE_SM), anchor="w",
            )
            self._thinking_label.pack(side="left", pady=8)
            self._thinking_row = row
        else:
            self._thinking_label.configure(text=f"ATLAS is thinking{dots}")
        self.auto_scroll()

    def remove_last_row(self) -> None:
        if not self._rows:
            return
        row = self._rows.pop()
        row["frame"].destroy()
        if self._thinking_label is not None:
            self._thinking_row.destroy()
            self._thinking_label = None

    # Compatibility helpers retained for older callers.
    def _copy_row(self, actions: tk.Widget, _role: str) -> None:
        for row in self._rows:
            if row.get("actions") is actions:
                self._on_copy(row.get("message", ChatMessage("system", "")).content)
                return

    def _edit_row(self, actions: tk.Widget) -> None:
        for row in self._rows:
            if row.get("actions") is actions:
                message = row.get("message")
                if message:
                    self._on_edit(message.content)
                return
