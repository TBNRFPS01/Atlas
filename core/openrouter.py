"""OpenRouter provider for ATLAS.

OpenRouter exposes an OpenAI-compatible API, so ATLAS can use hosted models
without changing its provider-facing message format. API credentials are read
from configuration/environment and are never stored in this module.
"""

from __future__ import annotations

from typing import Any, Iterator

from openai import OpenAI


class OpenRouterProvider:
    """OpenRouter-backed LLM provider with optional model fallback routing."""

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "qwen/qwen3-32b:free"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        models: list[str] | None = None,
        base_url: str = DEFAULT_BASE_URL,
        temperature: float = 0.7,
        max_tokens: int = 512,
        site_url: str = "",
        app_name: str = "ATLAS",
    ) -> None:
        if not api_key:
            raise ValueError("OpenRouter API key is required")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model or self.DEFAULT_MODEL
        self._models = [m.strip() for m in (models or []) if m and m.strip()]
        self._temperature = temperature
        self._max_tokens = max_tokens

        headers: dict[str, str] = {"X-Title": app_name}
        if site_url:
            headers["HTTP-Referer"] = site_url

        self._client = OpenAI(
            base_url=self._base_url,
            api_key=api_key,
            default_headers=headers,
            timeout=20,
            max_retries=0,
        )

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def model(self) -> str:
        return self._model

    @property
    def models(self) -> list[str]:
        return list(self._models)

    def _kwargs(
        self,
        messages: list[dict[str, Any]],
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools

        # OpenRouter supports model fallbacks through the OpenAI-compatible
        # `models` routing field. The primary model remains the `model` value.
        fallback_models = [m for m in self._models if m != kwargs["model"]]
        if fallback_models:
            kwargs["extra_body"] = {"models": fallback_models[:3]}
        return kwargs

    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        return self._client.chat.completions.create(
            **self._kwargs(messages, model, temperature, max_tokens, stream, tools)
        )

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> Iterator[str]:
        stream = self.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            tools=tools,
        )
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0].delta, "content", None)
            if delta:
                yield delta

    def is_available(self) -> bool:
        try:
            self._client.models.list()
            return True
        except Exception:
            return False
