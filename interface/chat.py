"""Chat area for the ATLAS interface.

Mirrors the HTML ``.chat-scroll`` / ``.welcome-stage`` / ``.message``:
a centered conversation column (max ~900px) with an avatar per message,
a warm user bubble, plain assistant text, hover-reveal actions, a
centered welcome screen before the first message, and streaming updates.

``messages`` is a caller-owned list of :class:`ChatMessage`; rendering
lives here. The composer lives in :mod:`interface.composer`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from interface.theme import (
    ACCENT,
    BACKGROUND,
    BORDER,
    BORDER_STRONG,
    CHAT_MAX_WIDTH,
    FONT_EMOJI,
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    INK,
    INK_SOFT,
    IVORY_DEEP,
    MUTED,
    PANEL_BG,
    TEXT_MUTED,
)
from interface.widgets import Avatar, round_rect_asym


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)


class _Bubble(tk.Canvas):
    """A rounded user-message bubble with asymmetric corner radii."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        *,
        max_width: int = 540,
        font: tuple[str, int, str] = (FONT_FAMILY, FONT_SIZE_BASE, "normal"),
    ) -> None:
        super().__init__(parent, bg=BACKGROUND, highlightthickness=0, bd=0)
        self._font = font
        self._max_width = max_width
        self._padx = 16
        self._pady = 12

        self._label = tk.Label(
            self,
            text=text,
            bg=PANEL_BG,
            fg=INK,
            font=font,
            justify="left",
            anchor="nw",
            wraplength=max_width,
            cursor="hand2",
        )
        self._label.update_idletasks()
        self._layout()
        self.bind("<Configure>", lambda _e: self._layout())

    def _layout(self) -> None:
        req_w = min(self._label.winfo_reqwidth(), self._max_width)
        req_h = self._label.winfo_reqheight()
        cw = req_w + self._padx * 2
        ch = req_h + self._pady * 2
        self.configure(width=cw, height=ch)
        self.delete("all")
        round_rect_asym(
            self, 1, 1, cw - 1, ch - 1,
            r_tl=5, r_tr=16, r_br=16, r_bl=16,
            fill=PANEL_BG, outline=BORDER, width=1,
        )
        self._label.configure(wraplength=self._max_width)
        self.create_window(
            self._padx, self._pady, window=self._label,
            anchor="nw", width=self._max_width,
        )

    def set_text(self, text: str) -> None:
        self._label.config(text=text)
        self._label.update_idletasks()
        self._layout()

    def get_text(self) -> str:
        return self._label.cget("text")


class ChatView:
    """Renders the welcome screen and the message stream."""

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
        self._assistant_labels: list[tk.Widget] = []

        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
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

        def _on_frame_config(_e: Any) -> None:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        self.chat_frame.bind("<Configure>", _on_frame_config)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._build_welcome()

    def _build_welcome(self) -> None:
        self.welcome = tk.Frame(self.chat_frame, bg=BACKGROUND)
        self.welcome.pack(fill="both", expand=True, pady=60)

        inner = tk.Frame(self.welcome, bg=BACKGROUND)
        inner.pack(expand=True)

        tk.Label(
            inner,
            text="What are we building?",
            bg=BACKGROUND,
            fg=ACCENT,
            font=(FONT_FAMILY, 28, "bold"),
        ).pack()

        tk.Label(
            inner,
            text="ATLAS is ready. Build something, solve something,\n"
                 "explore an idea, or throw a problem at the machine.",
            bg=BACKGROUND,
            fg=INK_SOFT,
            font=(FONT_FAMILY, FONT_SIZE_BASE + 1, "normal"),
            justify="center",
        ).pack(pady=(14, 30))

        grid = tk.Frame(inner, bg=BACKGROUND)
        grid.pack()

        suggestions = [
            ("Build something", "Create a project or application."),
            ("Explain something", "Break down a difficult concept."),
            ("Analyze something", "Inspect code, data or a problem."),
            ("Brainstorm", "Throw ideas into ATLAS."),
        ]
        for i, (title, subtitle) in enumerate(suggestions):
            card = self._suggestion_card(grid, title, subtitle)
            card.grid(row=i // 2, column=i % 2, padx=6, pady=6)

    def _suggestion_card(self, parent: tk.Widget, title: str, subtitle: str) -> tk.Widget:
        card = tk.Frame(
            parent,
            bg="#FFFDF8",
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=14,
            pady=12,
            cursor="hand2",
            width=280,
        )
        card.pack_propagate(False)

        tk.Label(
            card, text=title, bg="#FFFDF8", fg=INK,
            font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"), anchor="w",
        ).pack(fill="x")

        tk.Label(
            card, text=subtitle, bg="#FFFDF8", fg=MUTED,
            font=(FONT_FAMILY, FONT_SIZE_XS + 1), anchor="w", justify="left",
        ).pack(fill="x", pady=(3, 0))

        def _enter(_e: tk.Event) -> None:
            card.configure(bg="#FFFDF8")
            card.configure(highlightbackground=ACCENT)
            for child in card.winfo_children():
                child.configure(bg="#FFFDF8")

        def _leave(_e: tk.Event) -> None:
            card.configure(highlightbackground=BORDER)
            for child in card.winfo_children():
                child.configure(bg="#FFFDF8")

        def _click(_e: tk.Event) -> None:
            if self._on_suggestion is not None:
                self._on_suggestion(title)

        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)
        card.bind("<Button-1>", _click)
        for child in card.winfo_children():
            child.bind("<Enter>", _enter)
            child.bind("<Leave>", _leave)
            child.bind("<Button-1>", _click)
        return card

    # ------------------------------------------------------------------
    # Canvas geometry
    # ------------------------------------------------------------------
    def _on_canvas_configure(self, event: tk.Event) -> None:
        width = event.width
        content_w = min(width, CHAT_MAX_WIDTH)
        x = (width - content_w) // 2
        self.canvas.itemconfigure(self._chat_window, width=content_w)
        self.canvas.coords(self._chat_window, x, 0)
        # When the conversation is empty the chat frame should fill the
        # canvas so the welcome screen stays vertically centred.
        if not self._rows:
            self.canvas.itemconfigure(self._chat_window, height=event.height)
        self._update_assistant_wraplength(content_w)

    def _update_assistant_wraplength(self, width: int) -> None:
        body_w = max(width - 34 - 60, 160)
        for widget in self._assistant_labels:
            if isinstance(widget, tk.Label):
                widget.configure(wraplength=body_w)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def _on_mousewheel(self, event: tk.Event) -> None:
        canvas = self.canvas
        if canvas.winfo_containing(event.x_root, event.y_root):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def auto_scroll(self) -> None:
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def clear(self) -> None:
        for row in self._rows:
            row["frame"].destroy()
        self._rows.clear()
        self._assistant_labels.clear()
        self.welcome.pack(fill="both", expand=True, pady=60)

    def hide_welcome(self) -> None:
        self.welcome.pack_forget()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def render_message(self, message: ChatMessage, append: bool = True) -> None:
        if message.role == "user":
            self._render_user(message)
        elif message.role == "assistant":
            self._render_assistant(message)
        else:
            self._render_system(message)
        if append:
            self.auto_scroll()

    def _row(self) -> tk.Frame:
        row = tk.Frame(self.chat_frame, bg=BACKGROUND)
        row.pack(fill="x", padx=8, pady=(0, 26))
        return row

    def _render_user(self, message: ChatMessage) -> None:
        row = self._row()
        body = tk.Frame(row, bg=BACKGROUND)
        body.pack(side="left", fill="x", expand=True)

        bubble = _Bubble(body, message.content)
        bubble.pack(anchor="w")

        actions = self._actions_row(body, "user")
        self._rows.append({"frame": row, "bubble": bubble, "actions": actions})
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
            wraplength=560,
            cursor="hand2",
        )
        content.pack(fill="x", pady=(6, 0))
        content.bind("<Button-1>", lambda _e: self._on_copy(message.content))
        self._assistant_labels.append(content)

        actions = self._actions_row(body, "assistant")
        self._rows.append({"frame": row, "content": content, "actions": actions})
        self._bind_hover(row, actions)

    def _render_system(self, message: ChatMessage) -> None:
        row = self._row()
        tk.Label(
            row,
            text=message.content,
            bg="#FFF7E6",
            fg=INK_SOFT,
            font=(FONT_FAMILY, FONT_SIZE_SM, "italic"),
            justify="left",
            anchor="w",
            wraplength=600,
            padx=10,
            pady=6,
        ).pack(fill="x")

    def _actions_row(self, body: tk.Widget, role: str) -> tk.Frame:
        actions = tk.Frame(body, bg=BACKGROUND)
        actions.pack(fill="x", pady=(4, 0))
        actions.pack_forget()

        def _action_button(glyph: str, tooltip: str, command: Callable[[], Any]) -> None:
            btn = tk.Label(
                actions,
                text=glyph,
                bg=BACKGROUND,
                fg=MUTED,
                font=(FONT_FAMILY, 13),
                cursor="hand2",
                padx=6,
                pady=2,
            )
            btn.pack(side="left")
            btn.bind("<Enter>", lambda _e: btn.configure(fg=ACCENT))
            btn.bind("<Leave>", lambda _e: btn.configure(fg=MUTED))
            btn.bind("<Button-1>", lambda _e: command())
            btn._tooltip = tooltip  # type: ignore[attr-defined]

        if role == "user":
            _action_button("⧉", "Copy", lambda: self._copy_row(actions, role))
            _action_button("✎", "Edit", lambda: self._edit_row(actions))
            _action_button("🌿", "Branch", lambda: self._on_toast("Conversation branch created"))
        else:
            _action_button("⧉", "Copy", lambda: self._copy_row(actions, role))
            _action_button("↻", "Regenerate", self._on_regenerate)
            _action_button("📌", "Pin", lambda: self._on_toast("Message pinned"))
            _action_button("ⓘ", "Info", lambda: self._on_toast("ATLAS · local model"))
        return actions

    def _bind_hover(self, row: tk.Frame, actions: tk.Frame) -> None:
        def _show(_e: tk.Event) -> None:
            actions.pack(fill="x", pady=(4, 0))

        def _hide(_e: tk.Event) -> None:
            actions.pack_forget()

        row.bind("<Enter>", _show)
        row.bind("<Leave>", _hide)
        for child in row.winfo_children():
            child.bind("<Enter>", _show)
            child.bind("<Leave>", _hide)

    def update_last_message(self) -> None:
        if not self.messages:
            return
        last = self.messages[-1]
        if not self._rows:
            return
        row = self._rows[-1]
        if "bubble" in row:
            row["bubble"].set_text(last.content)
        elif "content" in row:
            row["content"].configure(text=last.content)
        self.auto_scroll()

    def set_thinking(self, dots: str) -> None:
        if not self._rows:
            return
        row = self._rows[-1]
        if "content" in row:
            row["content"].configure(text=f"Thinking{dots}")

    def remove_last_row(self) -> None:
        """Destroy and forget the most recently rendered message row."""
        if not self._rows:
            return
        row = self._rows.pop()
        if "content" in row:
            try:
                self._assistant_labels.remove(row["content"])
            except ValueError:
                pass
        try:
            row["frame"].destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Row lookups
    # ------------------------------------------------------------------
    def _row_for_actions(self, actions: tk.Frame, role: str) -> tuple[str, Any]:
        for row in self._rows:
            if row["actions"] is actions:
                key = "bubble" if "bubble" in row else "content"
                text = row[key].get_text() if hasattr(row[key], "get_text") \
                    else row[key].cget("text")
                return role, text
        return role, ""

    def _copy_row(self, actions: tk.Frame, role: str) -> None:
        _role, text = self._row_for_actions(actions, role)
        self._on_copy(text)

    def _edit_row(self, actions: tk.Frame) -> None:
        _role, text = self._row_for_actions(actions, "user")
        self._on_edit(text)
