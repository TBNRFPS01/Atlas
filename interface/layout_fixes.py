"""Targeted Tk layout corrections for the ATLAS desktop UI.

The component API stays unchanged.  These fixes correct three geometry
problems in the original port:

* suggestion cards had propagation disabled without a height, collapsing them
  to divider-like lines;
* the composer used ``place`` for its column, so the placed children did not
  contribute to the parent's requested height and the entire composer could
  collapse;
* Tk does not support alpha on a Frame, so the sidebar's HTML-style backdrop
  became a fully opaque dark sheet and hid the application behind it.
"""
from __future__ import annotations

import tkinter as tk


def apply_layout_fixes() -> None:
    from interface.chat import ChatView
    from interface.composer import Composer
    from interface.sidebar import Sidebar
    from interface.theme import CHAT_MAX_WIDTH, SIDEBAR_WIDTH

    if getattr(ChatView, "_atlas_layout_fixed", False):
        return

    # ------------------------------------------------------------------
    # Welcome suggestion cards: explicit height is required when geometry
    # propagation is disabled.
    # ------------------------------------------------------------------
    original_card = ChatView._suggestion_card

    def fixed_card(self, parent, title, subtitle):
        card = original_card(self, parent, title, subtitle)
        card.configure(width=280, height=96)
        card.pack_propagate(False)
        card.grid_propagate(False)
        return card

    ChatView._suggestion_card = fixed_card

    # ------------------------------------------------------------------
    # Composer: placed children do not affect the requested height of wrap.
    # Reserve that height explicitly and keep the centered column responsive.
    # ------------------------------------------------------------------
    def fixed_wrap_configure(self, event):
        self.column.update_idletasks()
        width = min(CHAT_MAX_WIDTH, max(event.width - 48, 240))
        required = max(self.column.winfo_reqheight(), 72)
        self.wrap.configure(height=required)
        self.column.place(
            in_=self.wrap,
            relx=0.5,
            y=0,
            anchor="n",
            width=width,
            height=required,
        )

    Composer._on_wrap_configure = fixed_wrap_configure

    # ------------------------------------------------------------------
    # Sidebar: CSS uses a translucent backdrop. A Tk Frame is opaque, so do
    # not place it over the application. The drawer itself remains an overlay
    # and is still closed by its own close button / Escape / menu toggle.
    # ------------------------------------------------------------------
    def fixed_open(self):
        if self._open:
            return
        self._open = True
        self.backdrop.place_forget()
        self.frame.lift()
        self._animate_to(0)

    Sidebar.open = fixed_open

    # Ensure a drawer opened before the animation has a deterministic size.
    original_place_offscreen = Sidebar._place_offscreen

    def fixed_place_offscreen(self):
        original_place_offscreen(self)
        self.frame.place_configure(width=SIDEBAR_WIDTH)

    Sidebar._place_offscreen = fixed_place_offscreen
    ChatView._atlas_layout_fixed = True
