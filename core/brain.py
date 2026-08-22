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
    """Central LLM communication wrapper for ATLAS."""
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

    def __init__(self, model: str | None = None, endpoint: str | None = None,
                 api_key: str | None = None, stream: bool = True,
                 history_limit: int = DEFAULT_HISTORY_LIMIT, memory_store: FactStore | None = None,
                 temperature: float = 0.7, max_tokens: int = 512, config_manager=None) -> None:
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
        # Some LM Studio chat templates reject the system role. Keep the
        # instruction content but fold it into the first user message by default.
        # Set LM_STUDIO_SYSTEM_ROLE=true when the loaded model supports system.
        self.use_system_role = os.getenv("LM_STUDIO_SYSTEM_ROLE", "false").lower() == "true"
        self.client: Any = OpenAI(base_url=self.endpoint, api_key=self.api_key, timeout=10, max_retries=0)
        self.history: list[ConversationMessage] = []
        self.system_prompt = self.DEFAULT_SYSTEM_PROMPT
        self.logger = get_logger("ATLAS")
        self.provider = self._build_provider()

    def _build_provider(self):
        if self.config is None or not self.config.get("gateway_enabled", False):
            return None
        gateway_key = self.config.get("gateway_api_key", "")
        if not gateway_key:
            return None
        gateway = GatewayProvider(api_key=gateway_key, models=self.config.get_gateway_models(),
                                  base_url=self.config.get("gateway_base_url", GatewayProvider.DEFAULT_BASE_URL),
                                  temperature=self.temperature, max_tokens=self.max_tokens)
        local = LocalProvider(base_url=self.endpoint, api_key=self.api_key, model=self.model,
                              temperature=self.temperature, max_tokens=self.max_tokens)
        if self.config.get("fallback_provider", "local") != "none":
            if self.config.get("primary_provider", "local") == "gateway":
                return MultiProvider(primary=gateway, fallback=local)
            return MultiProvider(primary=local, fallback=gateway)
        return gateway

    def add_message(self, role: MessageRole, content: str) -> None:
        self.history.append(ConversationMessage(role=role, content=content))
        self.trim_history()

    def trim_history(self) -> None:
        if len(self.history) > self.history_limit:
            del self.history[:len(self.history) - self.history_limit]

    def clear_history(self) -> None:
        self.history.clear()

    def set_system_prompt(self, prompt: str) -> None:
        self.system_prompt = prompt

    def _resolve_model_name(self) -> str:
        if self.model != self.DEFAULT_MODEL:
            return self.model
        try:
            available = self.client.models.list()
            data = getattr(available, "data", None) or []
            if data and data[0].id:
                self.model = data[0].id
                return self.model
        except Exception:
            pass
        return self.model

    def _history_messages(self, context: str = "") -> list[dict[str, str]]:
        """Build messages without unsupported system roles unless explicitly enabled."""
        messages: list[dict[str, str]] = []
        system_parts: list[str] = []
        if self.system_prompt:
            system_parts.append(self.system_prompt)
        for item in self.history:
            if item.role == MessageRole.SYSTEM:
                system_parts.append(item.content)
        if context:
            system_parts.append(f"Relevant memory context:\n{context}")
        system_text = "\n\n".join(system_parts)

        if self.use_system_role and system_text:
            messages.append({"role": "system", "content": system_text})

        for item in self.history:
            if item.role == MessageRole.SYSTEM:
                continue
            role = item.role.value
            content = item.content
            if not self.use_system_role and not messages and role == "user" and system_text:
                content = f"{system_text}\n\nUser request:\n{content}"
            if messages and role in {"user", "assistant"} and messages[-1]["role"] == role:
                messages[-1]["content"] += f"\n\n{content}"
            else:
                messages.append({"role": role, "content": content})
        return messages

    def _extract_text(self, response: Any) -> str:
        choice = getattr(response, "choices", [None])[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        return content.strip() if isinstance(content, str) else "No response returned."

    def _memory_context(self, prompt: str) -> str:
        if self.memory_store is None:
            return ""
        return "\n".join(r.content for r in self.memory_store.retrieve(prompt, limit=5))

    def _extract_memories(self, prompt: str) -> None:
        if self.memory_store is None:
            return
        normalized = prompt.strip()
        if len(normalized) < 6 or normalized.lower() in {"hi", "hello", "hey", "thanks", "thank you", "good morning", "good night"}:
            return
        for pattern, key in self.MEMORY_PATTERNS:
            match = pattern.search(normalized)
            if match:
                value = match.group(1).strip()
                existing = self.memory_store.recall(key)
                if existing is None:
                    self.memory_store.remember(key, value, category="fact")
                elif existing != value:
                    self.memory_store.update(key, value, category="fact")
                return

    def _call_provider(self, operation: str, call) -> str:
        try:
            return self._extract_text(call())
        except APIConnectionError:
            self.logger.warning("%s connection failed to %s", operation, self.endpoint)
            return f"LM Studio connection failed: unable to reach {self.endpoint}. Start LM Studio and confirm the local server is running."
        except Exception as exc:
            self.logger.error("%s request failed: %s", operation, exc)
            return f"{operation} request failed: {exc}"

    def _call_provider_stream(self, operation: str, call) -> Iterator[str]:
        try:
            yield from call()
        except APIConnectionError:
            self.logger.warning("%s streaming connection failed to %s", operation, self.endpoint)
            yield f"LM Studio connection failed: unable to reach {self.endpoint}. Start LM Studio and confirm the local server is running."
        except Exception as exc:
            self.logger.error("%s streaming request failed: %s", operation, exc)
            yield f"{operation} request failed: {exc}"

    def ask(self, prompt: str) -> str:
        self.add_message(MessageRole.USER, prompt)
        self._extract_memories(prompt)
        messages = self._history_messages(self._memory_context(prompt))
        def call():
            if self.provider is not None:
                return self.provider.chat(messages=messages, model=self._resolve_model_name(), temperature=self.temperature, max_tokens=self.max_tokens, stream=False)
            return self.client.chat.completions.create(model=self._resolve_model_name(), messages=messages, temperature=self.temperature, max_tokens=self.max_tokens, stream=False)
        answer = self._call_provider("LLM", call)
        if not answer.startswith("LM Studio") and not answer.startswith("LLM request"):
            self.add_message(MessageRole.ASSISTANT, answer)
            self._extract_memories(answer)
        return answer

    def ask_stream(self, prompt: str) -> Iterator[str]:
        self.add_message(MessageRole.USER, prompt)
        self._extract_memories(prompt)
        messages = self._history_messages(self._memory_context(prompt))
        collected: list[str] = []
        def stream_call():
            if self.provider is not None:
                return self.provider.chat_stream(messages=messages, model=self._resolve_model_name(), temperature=self.temperature, max_tokens=self.max_tokens)
            return self.client.chat.completions.create(model=self._resolve_model_name(), messages=messages, temperature=self.temperature, max_tokens=self.max_tokens, stream=True)
        def stream_wrapper():
            for chunk in stream_call():
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
        def call():
            payload = list(messages)
            if self.use_system_role:
                payload.insert(0, {"role": "system", "content": self.system_prompt})
            elif payload and payload[0].get("role") == "user":
                payload[0] = {**payload[0], "content": f"{self.system_prompt}\n\nUser request:\n{payload[0].get('content', '')}"}
            if self.provider is not None:
                return self.provider.chat(messages=payload, model=self._resolve_model_name(), temperature=0.7, max_tokens=self.max_tokens, stream=False)
            return self.client.chat.completions.create(model=self._resolve_model_name(), messages=payload, temperature=0.7, max_tokens=self.max_tokens, stream=False)
        return self._call_provider("LLM chat", call)

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        def stream_call():
            payload = list(messages)
            if self.use_system_role:
                payload.insert(0, {"role": "system", "content": self.system_prompt})
            elif payload and payload[0].get("role") == "user":
                payload[0] = {**payload[0], "content": f"{self.system_prompt}\n\nUser request:\n{payload[0].get('content', '')}"}
            if self.provider is not None:
                return self.provider.chat_stream(messages=payload, model=self._resolve_model_name(), temperature=0.7, max_tokens=self.max_tokens)
            return self.client.chat.completions.create(model=self._resolve_model_name(), messages=payload, temperature=0.7, stream=True)
        def stream_wrapper():
            for chunk in stream_call():
                delta = getattr(chunk.choices[0].delta, "content", None)
                if delta:
                    yield delta
        yield from self._call_provider_stream("LLM chat", stream_wrapper)

    def analyze_image(self, image_bytes: bytes, prompt: str = "Describe what you see.") -> str:
        import base64
        def call():
            encoded = base64.b64encode(image_bytes).decode("ascii")
            user_content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}]
            messages = [{"role": "user", "content": user_content}]
            if self.use_system_role:
                messages.insert(0, {"role": "system", "content": self.system_prompt})
            else:
                user_content.insert(0, {"type": "text", "text": self.system_prompt})
            if self.provider is not None:
                return self.provider.chat(messages=messages, model=self._resolve_model_name(), temperature=self.temperature, max_tokens=self.max_tokens, stream=False)
            return self.client.chat.completions.create(model=self._resolve_model_name(), messages=messages, temperature=self.temperature, max_tokens=self.max_tokens, stream=False)
        return self._call_provider("Vision", call)
