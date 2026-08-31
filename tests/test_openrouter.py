from core.openrouter import OpenRouterProvider


def test_openrouter_defaults_and_fallbacks():
    provider = OpenRouterProvider(
        api_key="sk-or-test",
        model="qwen/qwen3-32b:free",
        models=["qwen/qwen3-32b:free", "openrouter/free"],
    )

    assert provider.name == "openrouter"
    assert provider.model == "qwen/qwen3-32b:free"
    assert provider.models == ["qwen/qwen3-32b:free", "openrouter/free"]

    kwargs = provider._kwargs(
        messages=[{"role": "user", "content": "hello"}],
        model=None,
        temperature=0.2,
        max_tokens=100,
        stream=False,
        tools=None,
    )
    assert kwargs["model"] == "qwen/qwen3-32b:free"
    assert kwargs["extra_body"]["models"] == ["openrouter/free"]


def test_openrouter_requires_key():
    try:
        OpenRouterProvider(api_key="")
    except ValueError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("OpenRouterProvider should reject an empty API key")
