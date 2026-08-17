from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator

from memory.facts import FactStore
from openai import APIConnectionError, OpenAI

from core.providers import LocalProvider, GatewayProvider, MultiProvider, ProviderConfig
from utils.logger import get_logger


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
    DEFAULT_MODEL = "mistralai/ministral-3-3b"
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
        # The OpenAI client library exposes complex typed overloads that
        # Pylance sometimes flags. Treat the client as `Any` to avoid
        # spurious diagnostic noise while preserving runtime behavior.
        self.client: Any = OpenAI(
            base_url=self.endpoint,
            api_key=self.api_key,
            timeout=10,
            max_retries=0,
        )
        self.history: list[ConversationMessage] = []
        self.system_prompt = self.DEFAULT_SYSTEM_PROMPT
        self.logger = get_logger("ATLAS")
        self.provider = self._build_provider()

    def _build_provider(self):
        """Build the provider fallback stack from configuration.

        Returns ``None`` when the gateway is disabled, keeping the proven
        single-client path so the default configuration is unchanged.
        """
        if self.config is None or not self.config.get("gateway_enabled", False):
            return None

        gateway_key = self.config.get("gateway_api_key", "")
        if not gateway_key:
            return None

        gateway = GatewayProvider(
            api_key=gateway_key,
            models=self.config.get_gateway_models(),
            base_url=self.config.get("gateway_base_url", GatewayProvider.DEFAULT_BASE_URL),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        local = LocalProvider(
            base_url=self.endpoint,
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        if self.config.get("fallback_provider", "local") != "none":
            if self.config.get("primary_provider", "local") == "gateway":
                return MultiProvider(primary=gateway, fallback=local)
            return MultiProvider(primary=local, fallback=gateway)
        return gateway

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

    def _history_messages(self, context: str = "") -> list[dict[str, str]]:
        """Build a Ministral-compatible conversation history.

        Keeps exactly one optional system message, followed by alternating
        user and assistant messages. Memory context is merged into the
        system message instead of creating another system role.
        """
        messages: list[dict[str, str]] = []

        system_parts: list[str] = []

        if self.system_prompt:
            system_parts.append(self.system_prompt)

        for item in self.history:
            if item.role == MessageRole.SYSTEM:
                system_parts.append(item.content)

        if context:
            system_parts.append(f"Relevant memory context:\n{context}")

        if system_parts:
            messages.append({
                "role": "system",
                "content": "\n\n".join(system_parts),
            })

        for item in self.history:
            if item.role == MessageRole.SYSTEM:
                continue

            # Prevent duplicate consecutive user/assistant roles.
            if (
                messages
                and item.role.value in {"user", "assistant"}
                and messages[-1]["role"] == item.role.value
            ):
                messages[-1]["content"] += f"\n\n{item.content}"
            else:
                messages.append({
                    "role": item.role.value,
                    "content": item.content,
                })

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

        relevant = self.memory_store.retrieve(prompt, limit=5)
        return "\n".join(r.content for r in relevant)

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

    def _call_provider(self, operation: str, call) -> str:
        """Execute a provider call with unified error handling.

        Args:
            operation: Description of the operation for error messages (e.g., "LLM", "Vision").
            call: Callable that executes the provider request and returns a response.

        Returns:
            The extracted text response or an error message string.
        """
        try:
            return self._extract_text(call())
        except APIConnectionError:
            self.logger.warning("%s connection failed to %s", operation, self.endpoint)
            return (
                "LM Studio connection failed: unable to reach "
                f"{self.endpoint}. Start LM Studio and confirm the local server is running."
            )
        except Exception as exc:
            self.logger.error("%s request failed: %s", operation, exc)
            return f"{operation} request failed: {exc}"

    def _call_provider_stream(self, operation: str, call) -> Iterator[str]:
        """Execute a streaming provider call with unified error handling.

        Args:
            operation: Description of the operation for error messages.
            call: Callable that returns an iterator of response chunks.

        Yields:
            Response chunks or an error message.
        """
        try:
            yield from call()
        except APIConnectionError:
            self.logger.warning("%s streaming connection failed to %s", operation, self.endpoint)
            yield (
                "LM Studio connection failed: unable to reach "
                f"{self.endpoint}. Start LM Studio and confirm the local server is running."
            )
        except Exception as exc:
            self.logger.error("%s streaming request failed: %s", operation, exc)
            yield f"{operation} request failed: {exc}"

    def ask(self, prompt: str) -> str:
        """Send a single user prompt to the model and remember the response."""
        self.add_message(MessageRole.USER, prompt)
        self._extract_memories(prompt)

        context = self._memory_context(prompt)
        messages = self._history_messages()
        if context:
            messages.insert(1, {"role": "system", "content": f"Relevant memory context:\n{context}"})

        def call():
            if self.provider is not None:
                return self.provider.chat(
                    messages=messages,
                    model=self._resolve_model_name(),
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stream=False,
                )
            return self.client.chat.completions.create(
                model=self._resolve_model_name(),
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
            )

        answer = self._call_provider("LLM", call)
        if not answer.startswith("LM Studio") and not answer.startswith("LLM request"):
            self.add_message(MessageRole.ASSISTANT, answer)
            self._extract_memories(answer)
        return answer

    def ask_stream(self, prompt: str) -> Iterator[str]:
        """Stream a prompt reply from the model when the local server supports it."""
        self.add_message(MessageRole.USER, prompt)
        self._extract_memories(prompt)

        context = self._memory_context(prompt)
        messages = self._history_messages()
        if context:
            messages.insert(1, {"role": "system", "content": f"Relevant memory context:\n{context}"})

        collected: list[str] = []

        def stream_call():
            if self.provider is not None:
                return self.provider.chat_stream(
                    messages=messages,
                    model=self._resolve_model_name(),
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
            return self.client.chat.completions.create(
                model=self._resolve_model_name(),
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )

        def stream_wrapper():
            stream = stream_call()
            for chunk in stream:
                delta = getattr(chunk.choices[0].delta, "content", None)
                if delta:
                    collected.append(delta)
                    yield delta

        for delta in self._call_provider_stream("LLM", stream_wrapper):
            yield delta

        if collected:
            full = "".join(collected).strip()
            self.add_message(MessageRole.ASSISTANT, full)
            self._extract_memories(full)

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send a full message history to the model without mutating the stored conversation."""

        def call():
            payload = [{"role": "system", "content": self.system_prompt}, *messages]
            if self.provider is not None:
                return self.provider.chat(
                    messages=payload,
                    model=self._resolve_model_name(),
                    temperature=0.7,
                    max_tokens=self.max_tokens,
                    stream=False,
                )
            return self.client.chat.completions.create(
                model=self._resolve_model_name(),
                messages=payload,
                temperature=0.7,
                max_tokens=self.max_tokens,
                stream=False,
            )

        return self._call_provider("LLM chat", call)

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        """Stream a full conversation payload when the local server supports streaming."""

        def stream_call():
            payload = [{"role": "system", "content": self.system_prompt}, *messages]
            if self.provider is not None:
                return self.provider.chat_stream(
                    messages=payload,
                    model=self._resolve_model_name(),
                    temperature=0.7,
                    max_tokens=self.max_tokens,
                )
            return self.client.chat.completions.create(
                model=self._resolve_model_name(),
                messages=payload,
                temperature=0.7,
                stream=True,
            )

        def stream_wrapper():
            stream = stream_call()
            for chunk in stream:
                delta = getattr(chunk.choices[0].delta, "content", None)
                if delta:
                    yield delta

        yield from self._call_provider_stream("LLM chat", stream_wrapper)

    def analyze_image(self, image_bytes: bytes, prompt: str = "Describe what you see.") -> str:
        """Send an encoded image to a vision-capable model and return its reply.

        The image is embedded as a base64 data URL, which the OpenAI-compatible
        endpoint (LM Studio) accepts when a vision model is loaded. This is a
        standalone call and does not mutate the stored conversation history.
        """
        import base64

        def call():
            encoded = base64.b64encode(image_bytes).decode("ascii")
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                    ],
                },
            ]
            if self.provider is not None:
                return self.provider.chat(
                    messages=messages,
                    model=self._resolve_model_name(),
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stream=False,
                )
            return self.client.chat.completions.create(
                model=self._resolve_model_name(),
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
            )

        return self._call_provider("Vision", call)

