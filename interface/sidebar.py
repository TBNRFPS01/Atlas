"""Slide-out sidebar drawer for the ATLAS interface.

Mirrors the HTML ``.sidebar``: brand header, New Chat / Temporary Chat,
conversation search, PROJECTS and TODAY/YESTERDAY history sections, and a
user footer that opens Settings. The drawer animates in from the left
with a dimmed backdrop that closes on click.
"""
from __future__ import annotations

from typing import Any, Callable

import tkinter as tk

from interface.theme import (
    ACCENT,
    BACKGROUND,
    BORDER,
    BORDER_STRONG,
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    INK,
    INK_SOFT,
    MODAL_BACKDROP,
    MUTED,
    PANEL_BG,
    SIDEBAR_ANIM_MS,
    SIDEBAR_BG,
    SIDEBAR_WIDTH,
    TEXT_MUTED,
)
from interface.widgets import Avatar, RoundedButton


class _ListButton(tk.Frame):
    """A sidebar row (project / history item) with hover and active states."""

    def __init__(
        self,
        parent: tk.Widget,
        icon: str,
        title: str,
        *,
        active: bool = False,
        on_click: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(parent, bg=SIDEBAR_BG, cursor="hand2")
        self._active = active
        self._on_click = on_click
        self._normal_bg = SIDEBAR_BG
        self._active_bg = "#F1E3E3"

        self._icon = tk.Label(
            self, text=icon, bg=SIDEBAR_BG, fg=INK_SOFT,
            font=(FONT_FAMILY, FONT_SIZE_BASE),
        )
        self._icon.pack(side="left", padx=(10, 8))

        self._title = tk.Label(
            self, text=title, bg=SIDEBAR_BG, fg=ACCENT if active else INK,
            font=(FONT_FAMILY, FONT_SIZE_BASE),
            anchor="w",
        )
        self._title.pack(side="left", fill="x", expand=True)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        for child in (self._icon, self._title):
            child.bind("<Enter>", self._on_enter)
            child.bind("<Leave>", self._on_leave)
            child.bind("<Button-1>", self._on_click)

    def _on_enter(self, _e: tk.Event) -> None:
        bg = self._active_bg if self._active else BACKGROUND
        self._set_bg(bg)

    def _on_leave(self, _e: tk.Event) -> None:
        bg = self._active_bg if self._active else SIDEBAR_BG
        self._set_bg(bg)

    def _on_click(self, _e: tk.Event) -> None:
        if self._on_click is not None:
            self._on_click()

    def _set_bg(self, bg: str) -> None:
        self.configure(bg=bg)
        self._icon.configure(bg=bg)
        self._title.configure(bg=bg)


class Sidebar:
    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_new_chat: Callable[[], Any],
        on_temporary_chat: Callable[[], Any],
        on_settings: Callable[[], Any],
    ) -> None:
        self.parent = parent
        self._on_new_chat = on_new_chat
        self._on_temporary_chat = on_temporary_chat
        self._on_settings = on_settings
        self._open = False
        self._anim_after: str | None = None

        self.backdrop = tk.Frame(parent, bg=MODAL_BACKDROP)
        self.frame = tk.Frame(parent, bg=SIDEBAR_BG, width=SIDEBAR_WIDTH)

        self._build()
        self._place_offscreen()
        self.backdrop.bind("<Button-1>", lambda _e: self.close())

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def _build(self) -> None:
        # Header
        header = tk.Frame(self.frame, bg=SIDEBAR_BG)
        header.pack(side="top", fill="x", padx=18, pady=18)
        divider = tk.Frame(self.frame, bg=BORDER, height=1)
        divider.pack(side="top", fill="x")

        brand_row = tk.Frame(header, bg=SIDEBAR_BG)
        brand_row.pack(fill="x")

        self.brand_mark = Avatar(
            header, "A", size=34, bg=ACCENT, fg=BACKGROUND,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"), outer_bg=SIDEBAR_BG,
        )
        self.brand_mark.pack(side="left", padx=(0, 10))

        tk.Label(
            header,
            text="ATLAS",
            bg=SIDEBAR_BG,
            fg=INK,
            font=(FONT_FAMILY, 14, "bold"),
        ).pack(side="left")

        self.btn_close = RoundedButton(
            header,
            "✕",
            command=self.close,
            bg=PANEL_BG,
            fg=INK_SOFT,
            hover_bg=SIDEBAR_BG,
            font=(FONT_FAMILY, 13, "normal"),
            radius=10,
            width=36,
            height=36,
            outer_bg=SIDEBAR_BG,
        )
        self.btn_close.pack(side="right")

        # New chat + temporary chat
        self.btn_new = RoundedButton(
            self.frame,
            "＋ New Chat",
            command=self._on_new_chat,
            bg=ACCENT,
            fg=BACKGROUND,
            hover_bg="#6B1D27",
            font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"),
            radius=12,
            padx=14,
            pady=12,
            outer_bg=SIDEBAR_BG,
        )
        self.btn_new.pack(side="top", fill="x", padx=18, pady=(14, 8))

        self.btn_temporary = RoundedButton(
            self.frame,
            "🕶  Temporary Chat",
            command=self._on_temporary_chat,
            bg=PANEL_BG,
            fg=INK_SOFT,
            hover_bg=BACKGROUND,
            font=(FONT_FAMILY, FONT_SIZE_BASE, "normal"),
            radius=12,
            padx=14,
            pady=10,
            border_color=BORDER,
            outer_bg=SIDEBAR_BG,
        )
        self.btn_temporary.pack(side="top", fill="x", padx=18, pady=(0, 12))

        # Search
        search_wrap = tk.Frame(self.frame, bg=SIDEBAR_BG)
        search_wrap.pack(side="top", fill="x", padx=18, pady=(0, 6))

        tk.Label(
            search_wrap,
            text="⌕",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=(FONT_FAMILY, 13),
        ).pack(side="left", padx=(10, 0), pady=(6, 0))

        self.search = tk.Entry(
            search_wrap,
            bg=BACKGROUND,
            fg=INK,
            insertbackground=INK,
            relief="flat",
            font=(FONT_FAMILY, FONT_SIZE_BASE),
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        self.search.pack(side="left", fill="x", expand=True,
                         ipady=6, ipadx=6, padx=(8, 0))
        self.search.insert(0, "Search conversations")
        self.search.bind("<FocusIn>", self._on_search_focus)
        self.search.bind("<FocusOut>", self._on_search_blur)
        self.search.bind("<KeyRelease>", self._on_search)

        # Scrollable content
        self.content = tk.Frame(self.frame, bg=SIDEBAR_BG)
        self.content.pack(side="top", fill="both", expand=True, pady=(6, 0))

        # Footer
        footer = tk.Frame(self.frame, bg=SIDEBAR_BG)
        footer.pack(side="bottom", fill="x")
        footer_divider = tk.Frame(self.frame, bg=BORDER, height=1)
        footer_divider.pack(side="bottom", fill="x")

        self.btn_user = RoundedButton(
            footer,
            "",
            command=self._on_settings,
            bg=SIDEBAR_BG,
            fg=INK,
            hover_bg=BACKGROUND,
            font=(FONT_FAMILY, FONT_SIZE_BASE, "normal"),
            radius=12,
            padx=10,
            pady=10,
            width=SIDEBAR_WIDTH - 24,
            height=54,
            outer_bg=SIDEBAR_BG,
        )
        self.btn_user.pack(fill="x", padx=12, pady=12)

        self.user_avatar = Avatar(
            self.btn_user, "U", size=34, bg="#F1E3E3", fg=ACCENT,
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            outer_bg=SIDEBAR_BG,
        )
        self.user_avatar.place(x=10, y=10)

        self.user_name = tk.Label(
            self.btn_user, text="You", bg=SIDEBAR_BG, fg=INK,
            font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"), anchor="w",
        )
        self.user_name.place(x=52, y=8)

        self.user_subtitle = tk.Label(
            self.btn_user, text="Local ATLAS", bg=SIDEBAR_BG, fg=MUTED,
            font=(FONT_FAMILY, FONT_SIZE_XS + 1), anchor="w",
        )
        self.user_subtitle.place(x=52, y=28)

        self.sections: list[tk.Widget] = []
        self._history_items: list[_ListButton] = []
        self._project_items: list[_ListButton] = []

        self._build_sections()

    def _build_sections(self) -> None:
        # Projects section
        self._section_label("PROJECTS")
        self.project_box = tk.Frame(self.content, bg=SIDEBAR_BG)
        self.project_box.pack(fill="x", padx=10)

        # Today history
        self._section_label("TODAY")
        self.today_box = tk.Frame(self.content, bg=SIDEBAR_BG)
        self.today_box.pack(fill="x", padx=10)

        # Yesterday history
        self._section_label("YESTERDAY")
        self.yesterday_box = tk.Frame(self.content, bg=SIDEBAR_BG)
        self.yesterday_box.pack(fill="x", padx=10)

    def _section_label(self, text: str) -> None:
        tk.Label(
            self.content,
            text=text,
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=(FONT_FAMILY, FONT_SIZE_XS, "bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(14, 7))

    # ------------------------------------------------------------------
    # Populate
    # ------------------------------------------------------------------
    def set_projects(self, titles: list[str]) -> None:
        for child in self.project_box.winfo_children():
            child.destroy()
        self._project_items.clear()
        for title in titles:
            item = _ListButton(
                self.project_box,
                "📁",
                title,
                on_click=lambda t=title: self._notify_open_project(t),
            )
            item.pack(fill="x", pady=1)
            self._project_items.append(item)

    def set_history(self, today: list[str], yesterday: list[str]) -> None:
        for box in (self.today_box, self.yesterday_box):
            for child in box.winfo_children():
                child.destroy()
        self._history_items.clear()
        for idx, (box, titles) in enumerate([(self.today_box, today),
                                             (self.yesterday_box, yesterday)]):
            for title in titles:
                item = _ListButton(
                    box, "💬", title,
                    active=(idx == 0 and title == titles[0]),
                    on_click=lambda t=title: self._notify_open_conversation(t),
                )
                item.pack(fill="x", pady=1)
                self._history_items.append(item)

    def set_user(self, name: str, subtitle: str) -> None:
        self.user_name.config(text=name)
        self.user_subtitle.config(text=subtitle)

    def _notify_open_project(self, _title: str) -> None:
        self.close()

    def _notify_open_conversation(self, _title: str) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def _on_search_focus(self, _e: tk.Event) -> None:
        if self.search.get() == "Search conversations":
            self.search.delete(0, "end")

    def _on_search_blur(self, _e: tk.Event) -> None:
        if not self.search.get():
            self.search.insert(0, "Search conversations")

    def _on_search(self, _e: tk.Event) -> None:
        query = self.search.get().strip().lower()
        for item in self._history_items + self._project_items:
            text = item._title.cget("text").lower()
            item.pack_forget()
            if not query or query in text:
                item.pack(fill="x", pady=1)

    # ------------------------------------------------------------------
    # Open / close animation
    # ------------------------------------------------------------------
    def open(self) -> None:
        if self._open:
            return
        self._open = True
        self.backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.backdrop.lift()
        self.frame.lift()
        self._animate_to(0)

    def close(self) -> None:
        if not self._open:
            return
        self._open = False
        self._animate_to(-SIDEBAR_WIDTH, then_hide=True)

    def toggle(self) -> None:
        if self._open:
            self.close()
        else:
            self.open()

    def _place_offscreen(self) -> None:
        self.frame.place(x=-SIDEBAR_WIDTH, y=0, relheight=1.0)

    def _animate_to(self, target_x: int, then_hide: bool = False) -> None:
        if self._anim_after is not None:
            self.parent.after_cancel(self._anim_after)
            self._anim_after = None

        start = self.frame.winfo_x()
        steps = max(1, SIDEBAR_ANIM_MS // 16)
        delta = (target_x - start) / steps

        def _step(step: int) -> None:
            if step >= steps:
                self.frame.place(x=target_x, y=0, relheight=1.0)
                if then_hide:
                    self.backdrop.place_forget()
                self._anim_after = None
                return
            self.frame.place(x=int(start + delta * step), y=0, relheight=1.0)
            self._anim_after = self.parent.after(16, lambda: _step(step + 1))

        _step(0)
