"""Task-aware provider adapter for ATLAS.

This is an ATLAS-native integration layer inspired by routing/failover patterns
from the user's agent forks. It keeps the Brain API unchanged while selecting
local/cloud providers per request and falling back safely when a provider fails.
"""
from __future__ import annotations

from typing import Any, Iterator

from core.smart_router import SmartRouter


class SmartProvider:
    """Route each Brain request to the best available configured provider."""

    def __init__(
        self,
        providers: dict[str, Any],
        *,
        local_model: str | None = None,
        cloud_model: str | None = None,
        prefer_local: bool = True,
    ) -> None:
        self.providers = {name: provider for name, provider in providers.items() if provider is not None}
        self.router = SmartRouter(
            local_model=local_model,
            fast_model=cloud_model,
            reasoning_model=cloud_model,
            coding_model=cloud_model,
            vision_model=cloud_model,
            prefer_local=prefer_local,
        )

    @property
    def name(self) -> str:
        return "smart"

    @property
    def model(self) -> str:
        return "auto"

    def _available(self) -> set[str]:
        available: set[str] = set()
        for name, provider in self.providers.items():
            try:
                if provider.is_available():
                    available.add(name)
            except Exception:
                # Health state is still useful when availability probes fail.
                if name in self.router.health and self.router.health[name].available():
                    available.add(name)
        return available

    @staticmethod
    def _prompt_from_messages(messages: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for message in messages[-4:]:
            content = message.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    elif isinstance(item, dict) and item.get("type") == "image_url":
                        parts.append("[image]")
        return "\n".join(parts)

    def _choose(self, messages: list[dict[str, Any]]) -> tuple[Any, str, str | None]:
        prompt = self._prompt_from_messages(messages)
        available = self._available()
        decision = self.router.choose(prompt, available)
        provider = self.providers.get(decision.provider)
        if provider is None:
            # Deterministic fallback if the selected provider disappeared.
            for name in ("local", "openrouter", "gateway"):
                candidate = self.providers.get(name)
                if candidate is not None:
                    return candidate, name, None
            raise RuntimeError("No AI providers are configured")
        return provider, decision.provider, decision.model

    def chat(self, messages: list[dict[str, Any]], model: str | None = None,
             temperature: float | None = None, max_tokens: int | None = None,
             stream: bool = False, tools: list[dict[str, Any]] | None = None) -> Any:
        provider, name, selected_model = self._choose(messages)
        try:
            response = provider.chat(
                messages=messages,
                model=model or selected_model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                tools=tools,
            )
            self.router.record_success(name)
            return response
        except Exception:
            self.router.record_failure(name)
            # Cloud failure should transparently fall back to local when safe.
            if name != "local" and "local" in self.providers and self.router.health.get("local", type("H", (), {"available": lambda s: True})()).available():
                return self.providers["local"].chat(
                    messages=messages,
                    model=None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    tools=tools,
                )
            raise

    def chat_stream(self, messages: list[dict[str, Any]], model: str | None = None,
                    temperature: float | None = None, max_tokens: int | None = None,
                    tools: list[dict[str, Any]] | None = None) -> Iterator[str]:
        provider, name, selected_model = self._choose(messages)
        try:
            for chunk in provider.chat_stream(
                messages=messages,
                model=model or selected_model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            ):
                yield chunk
            self.router.record_success(name)
            return
        except Exception:
            self.router.record_failure(name)
            if name != "local" and "local" in self.providers:
                yield from self.providers["local"].chat_stream(
                    messages=messages,
                    model=None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                )
                return
            raise

    def is_available(self) -> bool:
        return bool(self._available())
