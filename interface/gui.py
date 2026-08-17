"""ATLAS desktop graphical interface coordinator.

Composes the premium warm-ivory UI components (topbar, slide-out
sidebar, chat, composer, voice overlay, command palette, settings and
memory modals) and wires them to the existing ATLAS backend without
touching its internals: router streaming, brain history, memory store,
massive tool registry, and the optional voice controller.

Worker-thread results are marshalled back to the Tk event loop through a
queue polled by :meth:`_poll_events`.
"""
from __future__ import annotations

import json
import queue
import time
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from interface.chat import ChatMessage, ChatView
from interface.command_palette import CommandPalette
from interface.composer import Composer
from interface.memory_panel import MemoryPanel
from interface.settings_panel import SettingsPanel
from interface.sidebar import Sidebar
from interface.theme import (
    BACKGROUND,
    INK,
)
from interface.topbar import TopBar
from interface.voice_overlay import VoiceOverlay
from interface.widgets import Toast
from interface.worker import ChatWorker


class ATLASGUI:
    """Application coordinator: composes components and manages the event loop."""

    def __init__(
        self,
        router=None,
        brain=None,
        memory=None,
        voice_controller=None,
        config_manager=None,
        tool_registry=None,
    ) -> None:
        self.router = router
        self.brain = brain
        self.memory = memory
        self.voice = voice_controller
        self.config = config_manager
        self.registry = tool_registry

        self._config_path = Path("config.json")

        self.messages: list[ChatMessage] = []
        self.streaming = False
        self.busy = False
        self.temporary_mode = False
        self._thinking_after: str | None = None
        self._thinking_dots = ""

        self._event_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._worker: ChatWorker | None = None
        self._closing = False
        self._pending_chunks: list[str] = []
        self._chunk_after: str | None = None
        self._poll_after: str | None = None

        self._build_window()

    def create_new_project(self) -> None:
        """Create a real ATLAS project folder on disk."""
        name = simpledialog.askstring("New Project", "Project name:", parent=self.root)
        if not name:
            return
        name = name.strip().replace(" ", "_")
        if not name:
            return
        folder = Path.home() / ".atlas" / "projects" / name
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.show_toast(f"Could not create project: {exc}")
            return
        self.show_toast(f"Project created: {folder}")

    # ------------------------------------------------------------------
    # Window construction
    # ------------------------------------------------------------------
    def _build_window(self) -> None:
        self.root = tk.Tk()
        self.root.title("ATLAS")
        self.root.configure(bg=BACKGROUND)
        self.root.geometry("1280x800")
        self.root.minsize(920, 620)

        self.toast = Toast(self.root)

        # Top bar
        self.topbar = TopBar(
            self.root,
            on_menu=self.toggle_sidebar,
            on_command=self.open_command_palette,
            on_export=self.export_conversation,
            on_settings=self.open_settings,
        )

        # Voice overlay sits above chat; hidden until voice mode starts.
        self.voice_overlay = VoiceOverlay(
            self.root,
            on_cancel=self.exit_voice_mode,
            on_orb=self.exit_voice_mode,
        )

        # Chat area (fills remaining space)
        self.chat = ChatView(
            self.root,
            self.messages,
            on_copy=self.copy_text,
            on_edit=self.edit_message,
            on_regenerate=self.regenerate,
            on_toast=self.show_toast,
            on_suggestion=self.use_suggestion,
        )

        # Composer pinned to bottom
        self.composer = Composer(
            self.root,
            on_send=self.send_message,
            on_stop=self.stop_generation,
            on_voice=self.start_voice_mode,
        )

        # Slide-out sidebar
        self.sidebar = Sidebar(
            self.root,
            on_new_chat=self.new_conversation,
            on_temporary_chat=self.temporary_chat,
            on_settings=self.open_settings,
        )

        # Command palette
        self.palette = CommandPalette(
            self.root,
            on_new=self.new_conversation,
            on_project=self.create_new_project,
            on_temporary=self.temporary_chat,
            on_voice=self.start_voice_mode,
            on_settings=self.open_settings,
        )

        # Settings / memory modals
        self.settings = SettingsPanel(
            self.root,
            config_manager=self.config,
            config_path=self._config_path,
            config_get=self._config_get,
            on_saved=self._render_sidebar_info,
            on_manage_memory=self.open_memory,
        )
        self.settings.set_export_handler(self.export_conversation)

        self.memory_panel = MemoryPanel(self.root, self.memory)

        self._bind_events()
        self._render_sidebar_info()
        self._poll_events()

    # ------------------------------------------------------------------
    # Events & bindings
    # ------------------------------------------------------------------
    def _bind_events(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Control-k>", lambda _e: self.open_command_palette())
        self.root.bind("<Control-K>", lambda _e: self.open_command_palette())
        self.root.bind("<Escape>", self._on_escape)

    def _on_escape(self, _e: tk.Event) -> None:
        if self._closing:
            return
        # Modals handle their own Escape; also close sidebar / voice here.
        self.sidebar.close()
        if self.voice_overlay_is_visible():
            self.exit_voice_mode()

    @property
    def text_input(self) -> tk.Text:
        return self.composer.text

    def _on_close(self) -> None:
        self._closing = True
        self._stop_thinking()
        if self._poll_after is not None:
            try:
                self.root.after_cancel(self._poll_after)
            except tk.TclError:
                pass
            self._poll_after = None
        if self.voice is not None and hasattr(self.voice, "stop"):
            try:
                self.voice.stop()
            except Exception:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _poll_events(self) -> None:
        if self._closing:
            return
        try:
            while True:
                kind, payload = self._event_queue.get_nowait()
                self._handle_event(kind, payload)
        except queue.Empty:
            pass
        try:
            self._poll_after = self.root.after(50, self._poll_events)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Conversation actions
    # ------------------------------------------------------------------
    def new_conversation(self) -> None:
        if self.streaming or self.busy:
            self.show_toast("ATLAS is still working")
            return
        self.temporary_mode = False
        self._clear_all()
        self.show_toast("New conversation")

    def temporary_chat(self) -> None:
        if self.streaming or self.busy:
            return
        self.temporary_mode = True
        self._clear_all()
        self.show_toast("Temporary chat · History and memory disabled")

    def _clear_all(self) -> None:
        if self.brain is not None and hasattr(self.brain, "clear_history"):
            try:
                self.brain.clear_history()
            except Exception:
                pass
        self.messages.clear()
        self.chat.clear()
        self.composer.focus_input()

    def clear_history(self) -> None:
        self.new_conversation()

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def use_suggestion(self, title: str) -> None:
        self.composer.set_text(title)
        self.composer.focus_input()

    def send_message(self, text: str, attachments: list = None) -> None:
        attachments = attachments or []
        text = text.strip()
        if not text or self.busy or self.streaming:
            return

        full_text = text
        if attachments:
            context = [self._read_attachment(p) for p in attachments]
            context = [c for c in context if c]
            if context:
                full_text = text + "\n\n[Attached context]\n" + "\n---\n".join(context)

        self.chat.hide_welcome()
        self._add_user_message(text)
        self._set_busy(True)

        if self.router is not None and hasattr(self.router, "stream"):
            self._stream_from_router(full_text)
        elif self.router is not None and hasattr(self.router, "route"):
            self._route_once(full_text)
        else:
            self._reply_mock(full_text)

    def _read_attachment(self, path: Path) -> str:
        try:
            if path.suffix.lower() in {".txt", ".md", ".py", ".json", ".csv", ".log", ".ini", ".yaml", ".yml"}:
                return path.read_text(encoding="utf-8", errors="ignore")[:6000]
            return f"[File attached: {path.name}]"
        except Exception:
            return f"[File attached: {path.name}]"

    def edit_message(self, text: str) -> None:
        # HTML behaviour: restore the text into the composer.
        self.composer.set_text(text)
        self.composer.focus_input()

    def regenerate(self) -> None:
        if self.streaming or self.busy:
            return
        last_user = next((m for m in reversed(self.messages) if m.role == "user"), None)
        if last_user is None:
            return
        # Drop the trailing assistant message (and its user turn) from the
        # brain history so the model context does not drift.
        if self.brain is not None and hasattr(self.brain, "history"):
            try:
                from core.brain import MessageRole

                hist = self.brain.history
                while hist and hist[-1].role == MessageRole.ASSISTANT:
                    hist.pop()
                if hist and hist[-1].role == MessageRole.USER:
                    hist.pop()
            except Exception:
                pass
        # Remove the last assistant row from the view
        if self.messages and self.messages[-1].role == "assistant":
            self.messages.pop()
            self.chat.remove_last_row()

        self._set_busy(True)
        if self.router is not None and hasattr(self.router, "stream"):
            self._stream_from_router(last_user.content)
        elif self.router is not None and hasattr(self.router, "route"):
            self._route_once(last_user.content)
        else:
            self._reply_mock(last_user.content)

    # ------------------------------------------------------------------
    # Backend integration paths
    # ------------------------------------------------------------------
    def _worker_handle(self) -> ChatWorker:
        if self._worker is None:
            self._worker = ChatWorker(self.router, self._enqueue)
        return self._worker

    def _route_once(self, text: str) -> None:
        self._worker_handle().route(text)

    def _stream_from_router(self, text: str) -> None:
        self.streaming = True
        self.composer.set_busy(True)
        self.chat.render_message(ChatMessage("assistant", ""), append=True)
        self._start_thinking()
        self._worker_handle().stream(text)

    def _reply_mock(self, text: str) -> None:
        self._worker_handle().mock(text)

    def stop_generation(self) -> None:
        self._worker_handle().stop()
        self._stop_thinking()

    # ------------------------------------------------------------------
    # UI rendering of backend results
    # ------------------------------------------------------------------
    def _handle_event(self, kind: str, payload: Any) -> None:
        if kind == "assistant_reply":
            reply = payload or ""
            if self._append_to_last(reply):
                self._set_busy(False)
            self._finish_turn()
        elif kind == "stream_chunk":
            self._pending_chunks.append(payload or "")
            self._schedule_flush()
        elif kind == "stream_done":
            self._stop_thinking()
            self._flush_chunks()
            self.streaming = False
            self._set_busy(False)
            self._finish_turn()
        elif kind == "error":
            msg = payload or "An unknown error occurred."
            self._stop_thinking()
            self._set_busy(False)
            self._append_to_last(f"\n\n[Error] {msg}")
            self.streaming = False
            self.show_toast("Something went wrong")
        elif kind == "voice_text":
            self.exit_voice_mode()
            text = payload or ""
            if text:
                self.composer.set_text(text)
                self.composer.focus_input()

    def _schedule_flush(self) -> None:
        if self._chunk_after is not None:
            return
        self._chunk_after = self.root.after(30, lambda: self._flush_chunks())

    def _flush_chunks(self) -> None:
        self._chunk_after = None
        chunks = self._pending_chunks
        if not chunks:
            return
        self._pending_chunks = []
        text = "".join(chunks)
        self._append_to_last(text)

    def _append_to_last(self, text: str) -> bool:
        if not text:
            return False
        if not self.messages:
            self.messages.append(ChatMessage("assistant", text))
        elif self.messages[-1].role != "assistant":
            self.messages.append(ChatMessage("assistant", text))
        else:
            self.messages[-1].content += text
        self.chat.update_last_message()
        return True

    def _start_thinking(self) -> None:
        self._thinking_dots = ""
        self._thinking_tick()

    def _thinking_tick(self) -> None:
        if not self.streaming:
            return
        if self._pending_chunks:
            # Content is arriving; drop the thinking placeholder.
            return
        self._thinking_dots = (self._thinking_dots + ".")[:3]
        self.chat.set_thinking(self._thinking_dots)
        self._thinking_after = self.root.after(400, self._thinking_tick)

    def _stop_thinking(self) -> None:
        if self._thinking_after is not None:
            try:
                self.root.after_cancel(self._thinking_after)
            except tk.TclError:
                pass
            self._thinking_after = None
        if self._chunk_after is not None:
            try:
                self.root.after_cancel(self._chunk_after)
            except tk.TclError:
                pass
            self._chunk_after = None

    def _finish_turn(self) -> None:
        last = self.messages[-1] if self.messages else None
        if last is not None and last.role == "assistant" and last.content:
            if not self.temporary_mode:
                self._brain_add("assistant", last.content)
            self._throttled_speak(last.content)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.composer.set_busy(busy)

    def _enqueue(self, kind: str, payload: Any) -> None:
        self._event_queue.put((kind, payload))

    def _add_user_message(self, text: str) -> None:
        if not self.temporary_mode:
            self._brain_add("user", text)
        self.messages.append(ChatMessage("user", text))
        self.chat.render_message(self.messages[-1], append=True)

    def _brain_add(self, role: str, content: str) -> None:
        if self.brain is None or not hasattr(self.brain, "add_message") \
                or not content:
            return
        try:
            from core.brain import MessageRole

            try:
                role_value = MessageRole(role)
            except ValueError:
                role_value = MessageRole.USER if role == "user" else MessageRole.ASSISTANT
            self.brain.add_message(role_value, content)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Voice integration
    # ------------------------------------------------------------------
    def start_voice_mode(self) -> None:
        if self.streaming or self.busy:
            self.show_toast("ATLAS is still working")
            return
        if self.voice is None:
            self.show_toast("Voice controller not available")
            return
        self.composer.frame.pack_forget()
        self.voice_overlay.show("Listening...")
        self._worker_handle().listen(self.voice)

    def exit_voice_mode(self) -> None:
        self.voice_overlay.hide()
        self.composer.frame.pack(side="bottom", fill="x")

    def voice_overlay_is_visible(self) -> bool:
        return bool(self.voice_overlay.frame.winfo_ismapped())

    def _throttled_speak(self, text: str) -> None:
        if self.voice is None or not getattr(self.voice, "enabled", False):
            return
        try:
            self.voice.speaker.speak(text)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Sidebar info
    # ------------------------------------------------------------------
    def _render_sidebar_info(self) -> None:
        model = self._config_get("model", "local-model")
        self.sidebar.set_user("You", f"Local ATLAS · {model}")

        projects: list[str] = []
        today: list[str] = []
        yesterday: list[str] = []
        now_day = time.localtime().tm_yday

        if self.memory is not None:
            try:
                records = self.memory.recent(limit=40)
                for rec in records:
                    title = rec.content.split("=", 1)[-1] if "=" in rec.content else rec.content
                    title = title[:40]
                    if rec.category == "project":
                        if title not in projects:
                            projects.append(title)
                    else:
                        rec_day = self._record_day(rec)
                        target = today if rec_day == now_day else yesterday
                        if title not in target:
                            target.append(title)
            except Exception:
                pass
        if self.brain is not None and hasattr(self.brain, "history"):
            try:
                for item in reversed(self.brain.history):
                    if str(getattr(item.role, "value", item.role)) == "user":
                        title = item.content[:40]
                        if title not in today:
                            today.insert(0, title)
            except Exception:
                pass

        if not projects:
            projects = ["ATLAS"]
        if not today and not yesterday:
            today = ["Current conversation"]

        self.sidebar.set_projects(projects[:10])
        self.sidebar.set_history(today[:20], yesterday[:10])

    @staticmethod
    def _record_day(rec: Any) -> int:
        try:
            stamp = getattr(rec, "created_at", "") or ""
            import datetime

            dt = datetime.datetime.fromisoformat(stamp)
            return dt.timetuple().tm_yday
        except Exception:
            return -1

    # ------------------------------------------------------------------
    # Sidebar / modal toggles
    # ------------------------------------------------------------------
    def toggle_sidebar(self) -> None:
        self.sidebar.toggle()

    def open_command_palette(self) -> None:
        self.sidebar.close()
        if self.palette._modal is None:
            self.palette.open()

    def open_settings(self) -> None:
        self.sidebar.close()
        if self.settings._modal is None:
            self.settings.open()

    def open_memory(self) -> None:
        self.memory_panel.open()

    # ------------------------------------------------------------------
    # Copy / export
    # ------------------------------------------------------------------
    def copy_text(self, text: str) -> None:
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.show_toast("Copied")

    def export_conversation(self) -> None:
        lines = ["ATLAS conversation", "=" * 20, ""]
        for msg in self.messages:
            who = "You" if msg.role == "user" else "ATLAS"
            lines.append(f"{who}: {msg.content}")
            lines.append("")
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export conversation",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="atlas-conversation.txt",
        )
        if not path:
            return
        try:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            self.show_toast("Conversation exported")
        except Exception as exc:
            messagebox.showerror("Export", f"Could not export:\n{exc}")

    def show_toast(self, text: str) -> None:
        self.toast.show(text)

    # ------------------------------------------------------------------
    # Config access
    # ------------------------------------------------------------------
    def _config_get(self, key: str, default: Any = None) -> Any:
        if self.config is not None and hasattr(self.config, "get"):
            try:
                return self.config.get(key, default)
            except Exception:
                pass
        data = self._load_config_json()
        return data.get(key, default)

    def _load_config_json(self) -> dict[str, Any]:
        try:
            with open(self._config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_settings(self) -> None:
        """Persist the settings form; kept as a passthrough for backward use."""
        self.settings.save()

    # ------------------------------------------------------------------
    # Entrypoint
    # ------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()


def launch_ui(**kwargs: Any) -> None:
    """Construct and run the ATLAS GUI inside Tk's main loop."""
    gui = ATLASGUI(**kwargs)
    gui.run()