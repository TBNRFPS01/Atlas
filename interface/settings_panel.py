"""Settings modal for the ATLAS interface.

Mirrors the HTML ``.settings-modal``: a two-column dialog with a nav rail
(General, Appearance, Model, Memory, Context, Tools, Voice, Data & Export,
Advanced) and a scrollable content area. Values are read from the backend
ConfigManager through ``config_get`` and persisted back through
``config_manager.set`` plus a JSON write on close.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import tkinter as tk
from tkinter import messagebox

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
    IVORY_DEEP,
    MUTED,
    PANEL_BG,
    TEXT_MUTED,
)
from interface.widgets import Modal, RoundedButton, Toggle


class SettingsPanel:
    def __init__(
        self,
        parent: tk.Widget,
        *,
        config_manager,
        config_path: Path,
        config_get: Callable[[str, Any], Any],
        on_saved: Callable[[], Any],
        on_manage_memory: Callable[[], Any] | None = None,
    ) -> None:
        self.parent = parent
        self.config = config_manager
        self.config_path = config_path
        self._config_get = config_get
        self._on_saved = on_saved
        self._on_manage_memory = on_manage_memory
        self._modal: Modal | None = None
        self._bindings: list[Callable[[], None]] = []
        self._on_export: Callable[[], Any] = lambda: None

    # ------------------------------------------------------------------
    def open(self) -> None:
        if self._modal is not None:
            return
        self._bindings.clear()
        self._modal = Modal(self.parent, width=840, height=560,
                            on_close=self._closed)
        self._build(self._modal.card.content)

    def _closed(self) -> None:
        self.save()
        self._modal = None

    def close(self) -> None:
        if self._modal is not None:
            self._modal.close()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def _build(self, root: tk.Frame) -> None:
        root.configure(bg=PANEL_BG)

        # Left nav rail
        nav = tk.Frame(root, bg="#F7F0E2", width=190)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)

        nav_buttons: dict[str, tk.Label] = {}
        panels: dict[str, tk.Frame] = {}

        for i, (panel_id, title) in enumerate([
            ("general", "General"),
            ("appearance", "Appearance"),
            ("model", "Model"),
            ("memory", "Memory"),
            ("context", "Context"),
            ("tools", "Tools"),
            ("voice", "Voice"),
            ("data", "Data & Export"),
            ("advanced", "Advanced"),
        ]):
            btn = tk.Label(
                nav, text=title, bg="#F7F0E2", fg=INK_SOFT,
                font=(FONT_FAMILY, FONT_SIZE_BASE), anchor="w",
                padx=14, pady=8, cursor="hand2",
            )
            btn.pack(fill="x", padx=8, pady=1)
            nav_buttons[panel_id] = btn

        # Right content area
        content_host = tk.Frame(root, bg=PANEL_BG)
        content_host.pack(side="left", fill="both", expand=True)

        for panel_id in nav_buttons:
            frame = tk.Frame(content_host, bg=PANEL_BG)
            panels[panel_id] = frame

        self._build_general(panels["general"])
        self._build_appearance(panels["appearance"])
        self._build_model(panels["model"])
        self._build_memory(panels["memory"])
        self._build_context(panels["context"])
        self._build_tools(panels["tools"])
        self._build_voice(panels["voice"])
        self._build_data(panels["data"])
        self._build_advanced(panels["advanced"])

        def _activate(panel_id: str) -> None:
            for pid, btn in nav_buttons.items():
                active = pid == panel_id
                btn.configure(
                    bg="#FFFDF8" if active else "#F7F0E2",
                    fg=ACCENT if active else INK_SOFT,
                    font=(FONT_FAMILY, FONT_SIZE_BASE, "bold" if active else "normal"),
                )
            for pid, frame in panels.items():
                frame.pack_forget()
            panels[panel_id].pack(fill="both", expand=True)

        for panel_id, btn in nav_buttons.items():
            btn.bind("<Button-1>", lambda _e, pid=panel_id: _activate(pid))

        _activate("general")

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------
    def _heading(self, parent: tk.Frame, text: str) -> None:
        tk.Label(
            parent, text=text, bg=PANEL_BG, fg=ACCENT,
            font=(FONT_FAMILY, 18, "bold"), anchor="w",
        ).pack(fill="x", pady=(8, 6))

    def _setting_row(
        self,
        parent: tk.Frame,
        title: str,
        desc: str,
        widget: tk.Widget,
    ) -> None:
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", pady=8)

        text = tk.Frame(row, bg=PANEL_BG)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=PANEL_BG, fg=INK,
                 font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"), anchor="w",
                 ).pack(fill="x")
        if desc:
            tk.Label(text, text=desc, bg=PANEL_BG, fg=MUTED,
                     font=(FONT_FAMILY, FONT_SIZE_XS + 1), anchor="w",
                     wraplength=420, justify="left").pack(fill="x")
        widget.pack(side="right")

    def _input(self, parent: tk.Frame, key: str) -> tk.Entry:
        entry = tk.Entry(
            parent, bg=BACKGROUND, fg=INK, insertbackground=INK,
            relief="flat", font=(FONT_FAMILY, FONT_SIZE_BASE),
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        entry.insert(0, str(self._config_get(key, "")))
        self._bindings.append(lambda e=entry, k=key: self.config.set(k, e.get()))
        return entry

    def _build_general(self, parent: tk.Frame) -> None:
        self._heading(parent, "General")
        history_var = tk.BooleanVar(value=bool(self._config_get("history_size", 60) or 0))
        toggle = Toggle(parent, value=history_var.get(),
                        on_change=lambda v: self.config.set("history_size", 60 if v else 0))
        self._setting_row(parent, "Conversation history",
                          "Save chats locally.", toggle)
        self._setting_row(parent, "Keyboard shortcuts",
                          "Ctrl + K opens the ATLAS command palette.",
                          tk.Frame(parent, bg=PANEL_BG))

    def _build_appearance(self, parent: tk.Frame) -> None:
        self._heading(parent, "Appearance")
        theme_frame = tk.Frame(parent, bg=PANEL_BG)
        theme_frame.pack(fill="x")
        tk.Label(theme_frame, text="Theme", bg=PANEL_BG, fg=INK,
                 font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"), anchor="w",
                 ).pack(anchor="w")
        tk.Label(theme_frame, text="Choose the ATLAS appearance.",
                 bg=PANEL_BG, fg=MUTED, font=(FONT_FAMILY, FONT_SIZE_XS + 1),
                 anchor="w").pack(anchor="w", pady=(2, 8))
        theme = tk.StringVar(value=str(self._config_get("theme", "Ivory Whisper")))
        combo = tk.OptionMenu(theme_frame, theme, "Ivory Whisper", "Dark ATLAS", "System")
        combo.config(bg=PANEL_BG, fg=INK, relief="flat",
                     highlightthickness=1, highlightbackground=BORDER,
                     activebackground=PANEL_BG, activeforeground=ACCENT,
                     font=(FONT_FAMILY, FONT_SIZE_BASE))
        combo.pack(fill="x", ipady=4)
        self._bindings.append(lambda: self.config.set("theme", theme.get()))

    def _build_model(self, parent: tk.Frame) -> None:
        self._heading(parent, "Model")
        model_frame = tk.Frame(parent, bg=PANEL_BG)
        model_frame.pack(fill="x")
        tk.Label(model_frame, text="Active model", bg=PANEL_BG, fg=INK,
                 font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"), anchor="w"
                 ).pack(anchor="w")
        tk.Label(model_frame, text="Select the model powering ATLAS.",
                 bg=PANEL_BG, fg=MUTED, font=(FONT_FAMILY, FONT_SIZE_XS + 1),
                 anchor="w").pack(anchor="w", pady=(2, 8))
        model = tk.StringVar(value=str(self._config_get("model", "local-model")))
        combo = tk.OptionMenu(model_frame, model,
                              "local-model", "Ministral 3 3B", "Qwen 3 8B",
                              "Gemma", "Llama")
        combo.config(bg=PANEL_BG, fg=INK, relief="flat",
                     highlightthickness=1, highlightbackground=BORDER,
                     activebackground=PANEL_BG, activeforeground=ACCENT,
                     font=(FONT_FAMILY, FONT_SIZE_BASE))
        combo.pack(fill="x", ipady=4)
        self._bindings.append(lambda: self.config.set("model", model.get()))

        temp_frame = tk.Frame(parent, bg=PANEL_BG)
        temp_frame.pack(fill="x", pady=12)
        tk.Label(temp_frame, text="Temperature", bg=PANEL_BG, fg=INK,
                 font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"), anchor="w"
                 ).pack(anchor="w")
        tk.Label(temp_frame, text="Controls creativity.",
                 bg=PANEL_BG, fg=MUTED, font=(FONT_FAMILY, FONT_SIZE_XS + 1),
                 anchor="w").pack(anchor="w", pady=(2, 4))
        scale = tk.Scale(
            temp_frame, from_=0.0, to=2.0, resolution=0.1, orient="horizontal",
            bg=PANEL_BG, fg=INK, troughcolor=IVORY_DEEP,
            highlightthickness=0, activebackground=ACCENT,
            font=(FONT_FAMILY, FONT_SIZE_XS + 1),
        )
        scale.set(float(self._config_get("temperature", 0.7)))
        scale.pack(fill="x")
        self._bindings.append(lambda: self.config.set("temperature", float(scale.get())))

    def _build_memory(self, parent: tk.Frame) -> None:
        self._heading(parent, "Memory")
        memory_toggle = Toggle(
            parent, value=bool(self._config_get("memory_enabled", True)),
            on_change=lambda v: self.config.set("memory_enabled", v))
        self._setting_row(parent, "Persistent memory",
                          "Store useful information locally.", memory_toggle)

        if self._on_manage_memory is not None:
            btn = RoundedButton(
                parent, "Manage Memory",
                command=self._on_manage_memory,
                bg=ACCENT, fg=BACKGROUND, hover_bg="#6B1D27",
                font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"),
                radius=12, padx=18, pady=10, outer_bg=PANEL_BG,
            )
            self._setting_row(parent, "Saved memories",
                              "Review, edit or remove stored context.", btn)

    def _build_context(self, parent: tk.Frame) -> None:
        self._heading(parent, "Context")
        context_frame = tk.Frame(parent, bg=PANEL_BG)
        context_frame.pack(fill="x")
        tk.Label(context_frame, text="Context strategy", bg=PANEL_BG, fg=INK,
                 font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"), anchor="w"
                 ).pack(anchor="w")
        tk.Label(context_frame,
                 text="Control how ATLAS retrieves conversation and project information.",
                 bg=PANEL_BG, fg=MUTED, font=(FONT_FAMILY, FONT_SIZE_XS + 1),
                 anchor="w", wraplength=420, justify="left").pack(anchor="w", pady=(2, 8))
        strategy = tk.StringVar(value=str(self._config_get("context_strategy", "Automatic")))
        combo = tk.OptionMenu(context_frame, strategy,
                              "Automatic", "Balanced", "Maximum Context")
        combo.config(bg=PANEL_BG, fg=INK, relief="flat",
                     highlightthickness=1, highlightbackground=BORDER,
                     activebackground=PANEL_BG, activeforeground=ACCENT,
                     font=(FONT_FAMILY, FONT_SIZE_BASE))
        combo.pack(fill="x", ipady=4)
        self._bindings.append(lambda: self.config.set("context_strategy", strategy.get()))

    def _build_tools(self, parent: tk.Frame) -> None:
        self._heading(parent, "Tools")
        tools = [
            ("web", "Web Search", "Search the web when required."),
            ("file", "File Access", "Read attached and project files."),
            ("vision", "Vision", "Analyze images and visual input."),
            ("system", "System Control", "Allow configured local system actions."),
        ]
        for key, title, desc in tools:
            cfg_key = f"tool_{key}_enabled"
            toggle = Toggle(parent, value=bool(self._config_get(cfg_key, True)),
                            on_change=lambda v, k=cfg_key: self.config.set(k, v))
            self._setting_row(parent, title, desc, toggle)

    def _build_voice(self, parent: tk.Frame) -> None:
        self._heading(parent, "Voice")
        voice_toggle = Toggle(
            parent, value=bool(self._config_get("voice_enabled", False)),
            on_change=lambda v: self.config.set("voice_enabled", v))
        self._setting_row(parent, "Voice input",
                          "Talk directly to ATLAS.", voice_toggle)

        tts_toggle = Toggle(
            parent, value=bool(self._config_get("tts_enabled", False)),
            on_change=lambda v: self.config.set("tts_enabled", v))
        self._setting_row(parent, "Text to speech",
                          "Let ATLAS speak responses.", tts_toggle)

    def _build_data(self, parent: tk.Frame) -> None:
        self._heading(parent, "Data & Export")
        btn = RoundedButton(
            parent, "Export Current Chat",
            command=self._on_export_click,
            bg=ACCENT, fg=BACKGROUND, hover_bg="#6B1D27",
            font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"),
            radius=12, padx=18, pady=10, outer_bg=PANEL_BG,
        )
        self._setting_row(parent, "Export conversations",
                          "Download chats as text.", btn)

    def _build_advanced(self, parent: tk.Frame) -> None:
        self._heading(parent, "Advanced")
        self._heading_small(parent, "Local server")
        tk.Label(parent,
                 text="Configure your ATLAS backend connection.",
                 bg=PANEL_BG, fg=MUTED,
                 font=(FONT_FAMILY, FONT_SIZE_XS + 1), anchor="w",
                 ).pack(anchor="w", pady=(2, 8))
        entry = self._input(parent, "endpoint")
        entry.pack(fill="x")

    def _heading_small(self, parent: tk.Frame, text: str) -> None:
        tk.Label(parent, text=text, bg=PANEL_BG, fg=INK,
                 font=(FONT_FAMILY, FONT_SIZE_BASE, "bold"), anchor="w"
                 ).pack(anchor="w", pady=(8, 2))

    # ------------------------------------------------------------------
    # Export / persistence
    # ------------------------------------------------------------------
    def _on_export_click(self) -> None:
        if self._on_export:
            self._on_export()

    def set_export_handler(self, handler: Callable[[], Any]) -> None:
        self._on_export = handler

    def save(self) -> None:
        for binding in self._bindings:
            try:
                binding()
            except Exception:
                pass
        try:
            data = self._load_config_json()
            if self.config is not None:
                for key, value in self.config._data.items():
                    data[key] = value
            with open(self.config_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass
        self._on_saved()

    def _load_config_json(self) -> dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
