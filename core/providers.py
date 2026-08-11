"""LLM Provider abstraction for ATLAS.

Supports multiple OpenAI-compatible providers with per-provider fallback and,
for the gateway, per-model fallback across an ordered model pool.
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    RateLimitError,
)


class ProviderError(Exception):
    """Base error for provider failures with a human-safe message."""

    def __init__(self, message: str, category: str = "unknown") -> None:
        super().__init__(message)
        self.category = category
        # Never allow the API key into the message.
        self.message = message


class ModelUnavailableError(ProviderError):
    pass


class ToolCallError(ProviderError):
    pass


def _safe_error_message(exc: Exception) -> str:
    """Build a short, key-safe error message from an exception.

    Strips any substring resembling an API key (sk-...) from the message.
    """
    msg = str(exc)
    # Aggressively scrub anything that looks like a bearer token / API key.
    import re

    msg = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", msg)
    return msg[:200]


def classify_exception(exc: Exception) -> str:
    """Categorize an exception into a coarse health category."""
    if isinstance(exc, ProviderError) and exc.category:
        return exc.category
    if isinstance(exc, AuthenticationError):
        return "authentication"
    if isinstance(exc, RateLimitError):
        return "rate_limit"
    if isinstance(exc, APITimeoutError):
        return "timeout"
    if isinstance(exc, APIConnectionError):
        return "connection"
    if isinstance(exc, NotFoundError):
        return "model_unavailable"
    if isinstance(exc, BadRequestError):
        return "bad_request"
    if isinstance(exc, ToolCallError):
        return "tool_calling"
    if isinstance(exc, ModelUnavailableError):
        return "model_unavailable"
    return "error"


@dataclass
class ModelHealth:
    """Lightweight per-model health and cooldown tracking."""

    model: str
    consecutive_failures: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0
    cooldown_until: float = 0.0
    category: str = ""
    tool_capable: bool = True

    def record_success(self, category: str = "") -> None:
        self.consecutive_failures = 0
        self.last_success = time.time()
        self.category = ""
        if category == "tool_calling":
            self.tool_capable = True

    def record_failure(self, category: str = "") -> None:
        self.consecutive_failures += 1
        self.last_failure = time.time()
        self.category = category or self.category

    def in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until


@dataclass(slots=True)
class ProviderConfig:
    """Configuration for a single LLM provider."""

    name: str
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 512
    enabled: bool = True


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Send a chat completion request."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is reachable."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Current model name."""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI SDK compatible provider (LM Studio, Gateway, etc.)."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._client = OpenAI(base_url=config.base_url, api_key=config.api_key)

    def _request_kwargs(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._config.max_tokens,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
        return kwargs

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        kwargs = self._request_kwargs(
            model or self._config.model,
            messages,
            temperature,
            max_tokens,
            stream,
            tools,
        )
        return self._client.chat.completions.create(**kwargs)

    def is_available(self) -> bool:
        try:
            self._client.models.list()
            return True
        except Exception:
            return False

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def config(self) -> ProviderConfig:
        return self._config


class LocalProvider(OpenAICompatibleProvider):
    """LM Studio local provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        api_key: str = "lm-studio",
        model: str = "local-model",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> None:
        config = ProviderConfig(
            name="local",
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            enabled=True,
        )
        super().__init__(config)


class GatewayProvider(LLMProvider):
    """AI Gateway provider (freemodelsforall.hopto.org) with per-model fallback.

    Accepts an ordered list of gateway models. Each request tries the first
    model; on failure it advances to the next model in the pool. The API key is
    never exposed in errors or logs.
    """

    DEFAULT_BASE_URL = "https://freemodelsforall.hopto.org/v1"

    def __init__(
        self,
        api_key: str,
        models: list[str] | None = None,
        base_url: str = DEFAULT_BASE_URL,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> None:
        if not api_key:
            raise ValueError("Gateway API key is required")
        self._api_key = api_key
        self._base_url = base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        # Ordered model pool (fallback order).
        self._models: list[str] = models or ["VerseMonster-Opus"]
        self._health: dict[str, ModelHealth] = {
            m: ModelHealth(model=m) for m in self._models
        }
        self._last_successful: str | None = None
        # (model, timestamp) of the last attempt to offer a safety bound.
        self._attempt_log: list[tuple[str, float]] = []

    # -- Model helpers ----------------------------------------------------

    @property
    def name(self) -> str:
        return "gateway"

    @property
    def model(self) -> str:
        return self._last_successful or (self._models[0] if self._models else "")

    @property
    def models(self) -> list[str]:
        return list(self._models)

    def set_models(self, models: list[str]) -> None:
        """Replace the ordered model pool and reset health state."""
        models = [m for m in models if m and m.strip()]
        self._models = models or ["VerseMonster-Opus"]
        self._health = {m: ModelHealth(model=m) for m in self._models}

    def get_health(self) -> dict[str, ModelHealth]:
        return dict(self._health)

    def _ordered_candidates(self) -> list[str]:
        """Ordered list of models to try, preferring last-known-working.

        The last successful model moves to the front but we periodically
        retry the configured higher-priority models via cooldown expiry.
        """
        if not self._models:
            return ["VerseMonster-Opus"]
        if self._last_successful and self._last_successful in self._models:
            ordered = [self._last_successful]
            ordered += [m for m in self._models if m != self._last_successful]
            return ordered
        return list(self._models)

    def _cooldown_for(self, health: ModelHealth, category: str) -> float:
        """Compute a temporary cooldown (seconds) for a failing model."""
        # Exponential-ish backoff, capped.
        base = min(5 * (2 ** (health.consecutive_failures - 1)), 300)
        if category == "authentication":
            # Never retry against a bad key during this session.
            return float("inf")
        if category == "model_unavailable":
            return max(base, 60)
        return base

    def _record_success(self, model: str) -> None:
        self._last_successful = model
        h = self._health.setdefault(model, ModelHealth(model=model))
        h.record_success()
        h.cooldown_until = 0.0

    def _record_failure(self, model: str, category: str) -> None:
        h = self._health.setdefault(model, ModelHealth(model=model))
        h.record_failure(category)
        h.cooldown_until = time.time() + self._cooldown_for(h, category)

    def _try_model_chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        tools: list[dict[str, Any]] | None,
    ) -> Any:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
        return self._client.chat.completions.create(**kwargs)

    def _ask_single_model(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
        tools: list[dict[str, Any]] | None,
    ) -> Any:
        try:
            response = self._try_model_chat(
                model, messages, temperature, max_tokens, False, tools
            )
            self._record_success(model)
            return response
        except Exception as exc:
            category = classify_exception(exc)
            self._record_failure(model, category)
            raise ProviderError(
                f"Gateway model '{model}' failed ({category}): {_safe_error_message(exc)}",
                category=category,
            )

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        if stream:
            raise NotImplementedError(
                "Use chat_stream for streaming with the gateway provider."
            )

        candidates = self._ordered_candidates()
        # Avoid retrying the same model indefinitely within one call.
        self._attempt_log = []

        for candidate in candidates:
            health = self._health.get(candidate, ModelHealth(model=candidate))
            # Skip models in cooldown (temporary) unless force-required.
            if health.in_cooldown():
                continue
            # Do not retry the same model twice in a single call.
            key = (candidate, round(time.time(), 2))
            if key in self._attempt_log:
                continue
            self._attempt_log.append(key)
            try:
                return self._ask_single_model(
                    candidate, messages, temperature, max_tokens, tools
                )
            except ProviderError as exc:
                if exc.category == "authentication":
                    raise  # Invalid API key; retrying other models is pointless.
                # Continue to next model.
                continue

        raise ProviderError(
            "All gateway models failed. Models attempted: "
            + ", ".join(self._models)
            + ".",
            category="all_failed",
        )

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> Iterator[str]:
        candidates = self._ordered_candidates()
        last_error: ProviderError | None = None

        for candidate in candidates:
            health = self._health.get(candidate, ModelHealth(model=candidate))
            if health.in_cooldown():
                continue
            try:
                stream = self._try_model_chat(
                    candidate, messages, temperature, max_tokens, True, tools
                )
                collected: list[str] = []
                for chunk in stream:
                    delta = getattr(chunk.choices[0].delta, "content", None)
                    if delta:
                        collected.append(delta)
                        yield delta
                self._record_success(candidate)
                return
            except Exception as exc:
                category = classify_exception(exc)
                self._record_failure(candidate, category)
                last_error = ProviderError(
                    f"Gateway model '{candidate}' streaming failed ({category}): "
                    + _safe_error_message(exc),
                    category=category,
                )
                if category == "authentication":
                    yield f"Gateway authentication failed: {_safe_error_message(exc)}"
                    return
                # Try next model.
                continue

        yield (
            f"All gateway models failed. Models attempted: {', '.join(self._models)}. "
            + (last_error.message if last_error else "")
        )

    def is_available(self) -> bool:
        try:
            self._client.models.list()
            return True
        except AuthenticationError:
            return False
        except Exception:
            return False


class MultiProvider:
    """Multi-provider with automatic provider-level fallback.

    If the primary provider is the gateway, its internal model pool is tried
    (via GatewayProvider.chat / chat_stream) before falling back to the
    secondary provider.
    """

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self._active: LLMProvider = primary

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        try:
            return self.primary.chat(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                tools=tools,
            )
        except ProviderError as primary_exc:
            if primary_exc.category == "authentication":
                raise  # Bad key; do not spin through fallback providers.
            if self.fallback is not None:
                try:
                    return self.fallback.chat(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=stream,
                        tools=tools,
                    )
                except ProviderError as fallback_exc:
                    raise ProviderError(
                        f"Primary ({self.primary.name}) failed: {primary_exc.message}. "
                        f"Fallback ({self.fallback.name}) failed: {fallback_exc.message}",
                        category="all_failed",
                    )
            raise
        except Exception as primary_exc:
            if self.fallback is not None:
                try:
                    return self.fallback.chat(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=stream,
                        tools=tools,
                    )
                except Exception as fallback_exc:
                    raise ProviderError(
                        f"Primary ({self.primary.name}) failed: {_safe_error_message(primary_exc)}. "
                        f"Fallback ({self.fallback.name}) failed: {_safe_error_message(fallback_exc)}",
                        category="all_failed",
                    )
            raise

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> Iterator[str]:
        try:
            yield from self.primary.chat_stream(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )
            return
        except ProviderError as primary_exc:
            if primary_exc.category == "authentication":
                yield f"Authentication failed: {primary_exc.message}"
                return
            if self.fallback is not None:
                yield from self.fallback.chat_stream(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                )
                return
            yield primary_exc.message

    def is_available(self) -> bool:
        return self.primary.is_available() or bool(
            self.fallback and self.fallback.is_available()
        )

    @property
    def active_provider(self) -> LLMProvider:
        return self._active

    def switch_to_fallback(self) -> bool:
        if self.fallback and self.fallback.is_available():
            self._active = self.fallback
            return True
        return False

    def reset_to_primary(self) -> bool:
        if self.primary.is_available():
            self._active = self.primary
            return True
        return False

    @property
    def name(self) -> str:
        return self._active.name

    @property
    def model(self) -> str:
        return self._active.model