from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator

from memory.facts import FactStore
from openai import APIConnectionError, OpenAI

from core.providers import LocalProvider, GatewayProvider, MultiProvider, ProviderConfig


class MessageRole(str, Enum):
    """Supported conversation roles for ATLAS history."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(slots=True)
class ConversationMessage:
    """A single message in ATLAS conversation history."""

    role: MessageRole
    content: str


class Brain:
    """Central LLM communication wrapper for ATLAS.

    The class uses the official OpenAI Python SDK against LM Studio's
    local OpenAI-compatible endpoint and keeps conversation history inside
    the Brain layer.
    """

    DEFAULT_ENDPOINT = "http://localhost:1234/v1"
    DEFAULT_MODEL = "local-model"
    DEFAULT_SYSTEM_PROMPT = (
        "You are ATLAS, a calm, intelligent, honest, helpful, and professional "
        "desktop assistant. Speak naturally and never pretend to perform actions "
        "you cannot verify."
    )
    DEFAULT_HISTORY_LIMIT = 60
    MEMORY_PATTERNS = (
        (re.compile(r"\bmy name is\s+([A-Za-z][A-Za-z' -]+)", re.IGNORECASE), "name"),
        (re.compile(r"\bi use\s+([A-Za-z0-9_. -]+)", re.IGNORECASE), "uses"),
        (re.compile(r"\bmy favourite game is\s+([A-Za-z0-9_. -]+)", re.IGNORECASE), "game"),
        (re.compile(r"\bmy favorite game is\s+([A-Za-z0-9_. -]+)", re.IGNORECASE), "game"),
        (re.compile(r"\bmy school is\s+([A-Za-z0-9_. -]+)", re.IGNORECASE), "school"),
        (re.compile(r"\bi have\s+([0-9]+\s*(?:gb|tb|mb)\s+ram)", re.IGNORECASE), "ram"),
    )

    def __init__(
        self,
        model: str | None = None,
        endpoint: str | None = None,
        api_key: str | None = None,
        stream: bool = True,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
        memory_store: FactStore | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        config_manager=None,
    ) -> None:
        # Load from config if provided
        self.config = config_manager
        if self.config is not None:
            model = model or self.config.get("model")
            endpoint = endpoint or os.getenv("LM_STUDIO_BASE_URL", self.DEFAULT_ENDPOINT)
            stream = stream if stream is not None else self.config.get("stream", True)
            history_limit = history_limit or self.config.get("history_size", self.DEFAULT_HISTORY_LIMIT)
            temperature = self.config.get("temperature", 0.7)
            max_tokens = self.config.get("max_tokens", 512)
        else:
            endpoint = endpoint or os.getenv("LM_STUDIO_BASE_URL", self.DEFAULT_ENDPOINT)
            temperature = temperature or 0.7
            max_tokens = max_tokens or 512

        self.endpoint = endpoint
        self.api_key = api_key or os.getenv("LM_STUDIO_API_KEY", "lm-studio")
        self.stream = stream if stream is not None else os.getenv("LM_STUDIO_STREAM", "true").lower() == "true"
        self.model = model or os.getenv("LM_STUDIO_MODEL") or self.DEFAULT_MODEL
        self.history_limit = history_limit or self.DEFAULT_HISTORY_LIMIT
        self.memory_store = memory_store or FactStore()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = OpenAI(base_url=self.endpoint, api_key=self.api_key)
        self.history: list[ConversationMessage] = []
        self.system_prompt = self.DEFAULT_SYSTEM_PROMPT

    def add_message(self, role: MessageRole, content: str) -> None:
        """Append a role-tagged message to the conversation history."""
        self.history.append(ConversationMessage(role=role, content=content))
        self.trim_history()

    def trim_history(self) -> None:
        """Prune older messages when the conversation becomes too large."""
        if len(self.history) > self.history_limit:
            excess = len(self.history) - self.history_limit
            del self.history[:excess]

    def clear_history(self) -> None:
        """Clear all in-memory conversation history."""
        self.history.clear()

    def set_system_prompt(self, prompt: str) -> None:
        """Update the system identity prompt for future turns."""
        self.system_prompt = prompt

    def _resolve_model_name(self) -> str:
        """Prefer the configured model, otherwise discover the loaded LM Studio model."""
        if self.model != self.DEFAULT_MODEL:
            return self.model

        try:
            available = self.client.models.list()
            data = getattr(available, "data", None) or []
            if data:
                model_name = data[0].id
                if model_name:
                    self.model = model_name
                    return model_name
        except Exception:
            pass

        return self.model

    def _history_messages(self) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": self.system_prompt}]
        for item in self.history:
            messages.append({"role": item.role.value, "content": item.content})
        return messages

    def _extract_text(self, response: Any) -> str:
        choice = getattr(response, "choices", [None])[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        return "No response returned."

    def _memory_context(self, prompt: str) -> str:
        """Search memory for relevant facts and inject only the highest-value subset."""
        if self.memory_store is None:
            return ""

        relevant = []
        for term in re.findall(r"[A-Za-z0-9]+", prompt):
            if len(term) < 3:
                continue
            for item in self.memory_store.search(term):
                if item not in relevant:
                    relevant.append(item)

        return "\n".join(relevant[:5])

    def _extract_memories(self, prompt: str) -> None:
        """Persist notable user facts without storing greetings or duplicates."""
        if self.memory_store is None:
            return

        normalized = prompt.strip()
        if len(normalized) < 6:
            return

        lowered = normalized.lower()
        if lowered in {"hi", "hello", "hey", "thanks", "thank you", "good morning", "good night"}:
            return

        for pattern, key in self.MEMORY_PATTERNS:
            match = pattern.search(normalized)
            if not match:
                continue

            value = match.group(1).strip()
            existing = self.memory_store.recall(key)
            if existing is None:
                self.memory_store.remember(key, value, category="fact")
            elif existing != value:
                self.memory_store.update(key, value, category="fact")
            return

    def ask(self, prompt: str) -> str:
        """Send a single user prompt to the model and remember the response."""
        self.add_message(MessageRole.USER, prompt)
        self._extract_memories(prompt)

        try:
            context = self._memory_context(prompt)
            messages = self._history_messages()
            if context:
                messages.insert(1, {"role": "system", "content": f"Relevant memory context:\n{context}"})

            response = self.client.chat.completions.create(
                model=self._resolve_model_name(),
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
            )
            answer = self._extract_text(response)
            self.add_message(MessageRole.ASSISTANT, answer)
            self._extract_memories(answer)
            return answer
        except APIConnectionError:
            return (
                "LM Studio connection failed: unable to reach "
                f"{self.endpoint}. Start LM Studio and confirm the local server is running."
            )
        except Exception as exc:
            return f"LM Studio request failed: {exc}"

    def ask_stream(self, prompt: str) -> Iterator[str]:
        """Stream a prompt reply from the model when the local server supports it."""
        self.add_message(MessageRole.USER, prompt)
        self._extract_memories(prompt)

        try:
            context = self._memory_context(prompt)
            messages = self._history_messages()
            if context:
                messages.insert(1, {"role": "system", "content": f"Relevant memory context:\n{context}"})

            stream = self.client.chat.completions.create(
                model=self._resolve_model_name(),
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            collected: list[str] = []
            for chunk in stream:
                delta = getattr(chunk.choices[0].delta, "content", None)
                if delta:
                    collected.append(delta)
                    yield delta

            self.add_message(MessageRole.ASSISTANT, "".join(collected).strip())
            self._extract_memories("".join(collected).strip())
        except APIConnectionError:
            yield (
                "LM Studio connection failed: unable to reach "
                f"{self.endpoint}. Start LM Studio and confirm the local server is running."
            )
        except Exception as exc:
            yield f"LM Studio request failed: {exc}"

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send a full message history to the model without mutating the stored conversation."""
        try:
            response = self.client.chat.completions.create(
                model=self._resolve_model_name(),
                messages=[{"role": "system", "content": self.system_prompt}, *messages],
                temperature=0.7,
                stream=False,
            )
            return self._extract_text(response)
        except APIConnectionError:
            return (
                "LM Studio connection failed: unable to reach "
                f"{self.endpoint}. Start LM Studio and confirm the local server is running."
            )
        except Exception as exc:
            return f"LM Studio request failed: {exc}"

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        """Stream a full conversation payload when the local server supports streaming."""
        try:
            stream = self.client.chat.completions.create(
                model=self._resolve_model_name(),
                messages=[{"role": "system", "content": self.system_prompt}, *messages],
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:
                delta = getattr(chunk.choices[0].delta, "content", None)
                if delta:
                    yield delta
        except APIConnectionError:
            yield (
                "LM Studio connection failed: unable to reach "
                f"{self.endpoint}. Start LM Studio and confirm the local server is running."
            )
        except Exception as exc:
            yield f"LM Studio request failed: {exc}"
