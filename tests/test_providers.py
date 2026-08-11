"""Tests for GatewayProvider multi-model fallback, tool schemas, and security."""

import os
import time
from types import SimpleNamespace

import pytest

from core.providers import (
    GatewayProvider,
    LocalProvider,
    MultiProvider,
    ProviderError,
)


def _ok_response(content: str = "hello") -> SimpleNamespace:
    choice = SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=None)
    )
    return SimpleNamespace(choices=[choice])


class _FakeCompletions:
    def __init__(self, handler):
        self._handler = handler
        self.last_kwargs = None

    def create(self, *args, **kwargs):
        self.last_kwargs = kwargs
        return self._handler(kwargs)


class _FakeChat:
    def __init__(self, handler):
        self.completions = _FakeCompletions(handler)


class _FakeModels:
    def __init__(self, names):
        self._names = names

    def list(self):
        return SimpleNamespace(data=[SimpleNamespace(id=n) for n in self._names])


class _FakeClient:
    def __init__(self, handler=None, model_names=None):
        self.chat = _FakeChat(handler or (lambda kw: _ok_response()))
        self.models = _FakeModels(model_names or ["gpt-5.6-luna"])


def _provider(models, handler, model_names=None):
    """Create a GatewayProvider with a fake client driving the given handler."""
    p = GatewayProvider(api_key="sk-gtw-test", models=models)
    p._client = _FakeClient(handler=handler, model_names=model_names)
    return p


def test_first_model_succeeds() -> None:
    seen = []
    p = _provider(["m1", "m2"], lambda kw: (seen.append(kw["model"]) or _ok_response()))
    resp = p.chat([{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "hello"
    assert seen == ["m1"]  # Only the first model attempted.
    assert p.model == "m1"


def test_first_fails_second_succeeds() -> None:
    seen = []

    def handler(kw):
        seen.append(kw["model"])
        if kw["model"] == "m1":
            raise ProviderError("boom", category="rate_limit")
        return _ok_response()

    p = _provider(["m1", "m2"], handler)
    resp = p.chat([{"role": "user", "content": "hi"}])
    assert seen == ["m1", "m2"]
    assert resp.choices[0].message.content == "hello"
    assert p.model == "m2"


def test_multiple_fail_before_success() -> None:
    seen = []

    def handler(kw):
        seen.append(kw["model"])
        if kw["model"] in ("m1", "m2", "m3"):
            raise ProviderError("down", category="model_unavailable")
        return _ok_response()

    p = _provider(["m1", "m2", "m3", "m4"], handler)
    resp = p.chat([{"role": "user", "content": "hi"}])
    assert seen == ["m1", "m2", "m3", "m4"]
    assert p.model == "m4"


def test_all_models_fail() -> None:
    def handler(kw):
        raise ProviderError("down", category="model_unavailable")

    p = _provider(["m1", "m2"], handler)
    with pytest.raises(ProviderError) as exc:
        p.chat([{"role": "user", "content": "hi"}])
    # Both models named; API key never appears.
    assert "m1" in exc.value.message and "m2" in exc.value.message
    assert "sk-gtw-test" not in exc.value.message


def test_invalid_api_key_does_not_retry_all(models_cat="authentication"):
    seen = []

    def handler(kw):
        seen.append(kw["model"])
        raise ProviderError("bad key", category="authentication")

    p = _provider(["m1", "m2"], handler)
    with pytest.raises(ProviderError) as exc:
        p.chat([{"role": "user", "content": "hi"}])
    # Retrying other models with a bad key is pointless.
    assert seen == ["m1"]
    assert exc.value.category == "authentication"


def test_tool_schemas_pass_through_tools_parameter() -> None:
    captured = {}

    def handler(kw):
        captured.update(kw)
        return _ok_response()

    p = _provider(["m1"], handler)
    tools = [{"type": "function", "function": {"name": "system"}}]
    p.chat([{"role": "user", "content": "hi"}], tools=tools)
    assert captured.get("tools") == tools


def test_model_success_health_tracking() -> None:
    p = _provider(["m1"], lambda kw: _ok_response())
    p.chat([{"role": "user", "content": "hi"}])
    h = p.get_health()["m1"]
    assert h.consecutive_failures == 0
    assert h.last_success > 0


def test_model_failure_enters_cooldown() -> None:
    def handler(kw):
        raise ProviderError("overloaded", category="rate_limit")

    p = _provider(["m1"], handler)
    with pytest.raises(ProviderError):
        p.chat([{"role": "user", "content": "hi"}])
    h = p.get_health()["m1"]
    assert h.consecutive_failures >= 1
    assert h.in_cooldown()


def test_streaming_fallback_to_next_model() -> None:
    seen = []

    def handler(kw):
        seen.append(kw["model"])
        raise ProviderError("connection lost", category="connection")

    p = _provider(["m1", "m2"], handler)
    # Monkeypatch the stream result.
    pieces = list(p.chat_stream([{"role": "user", "content": "hi"}], tools=None))
    # Both failed -> no useful text, error surfaced.
    assert seen == ["m1", "m2"]
    assert any("m1" in s and "m2" in s for s in pieces)


def test_local_provider_still_works() -> None:
    p = LocalProvider(model="local-model")

    def handler(kw):
        assert kw["model"] == "local-model"
        return _ok_response()

    p._client = _FakeClient(handler=handler)
    resp = p.chat([{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "hello"


def test_gateway_to_local_fallback() -> None:
    gw = _provider(["m1"], lambda kw: (
        (_ for _ in ()).throw(ProviderError("down", category="model_unavailable"))
    ))
    local = LocalProvider(model="local-model")

    def local_handler(kw):
        assert kw["model"] == "local-model"
        return _ok_response()

    local._client = _FakeClient(handler=local_handler)
    mp = MultiProvider(primary=gw, fallback=local)
    resp = mp.chat([{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "hello"


def test_api_key_never_in_errors() -> None:
    def handler(kw):
        raise ProviderError(
            "sk-gtw-secret-token caused failure", category="error"
        )

    p = _provider(["m1", "m2"], handler)
    with pytest.raises(ProviderError) as exc:
        p.chat([{"role": "user", "content": "hi"}])
    assert "sk-gtw-secret-token" not in exc.value.message
    # Default error path too.
    p2 = _provider(["m1"], lambda kw: (_ for _ in ()).throw(
        RuntimeError("boom sk-gtw-topsecret 500")))
    p2._api_key = "sk-gtw-topsecret"
    try:
        p2.chat([{"role": "user", "content": "hi"}])
    except ProviderError as e:
        assert "sk-gtw-topsecret" not in e.message