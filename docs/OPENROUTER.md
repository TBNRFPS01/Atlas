# OpenRouter

ATLAS can use OpenRouter as its primary cloud model provider with LM Studio as the local fallback.

## Setup

1. Create an OpenRouter API key from the OpenRouter dashboard.
2. Store it in the environment, never in `config.json` or source code.

PowerShell for the current terminal:

```powershell
$env:OPENROUTER_API_KEY="sk-or-v1-..."
```

For a persistent user-level setting:

```powershell
[Environment]::SetEnvironmentVariable("OPENROUTER_API_KEY", "sk-or-v1-...", "User")
```

Restart PowerShell after setting a persistent variable.

## Default routing

The default configuration is:

```text
Primary:  OpenRouter
Model:    qwen/qwen3-32b:free
Fallback: LM Studio
```

If the OpenRouter key is missing or the cloud provider cannot be constructed, ATLAS continues with its local provider.

## Choosing a model

Set `openrouter_model` in `config.json` or use:

```powershell
$env:ATLAS_OPENROUTER_MODEL="qwen/qwen3.8-flash"
```

OpenRouter uses the `provider/model` model ID format. Free Qwen models can use the `:free` suffix when OpenRouter lists that variant.

## Fallback models

`openrouter_models` is a comma-separated ordered list. ATLAS sends the additional models to OpenRouter's native `models` routing field so OpenRouter can fail over between compatible endpoints/models.

Example:

```json
{
  "openrouter_model": "qwen/qwen3.8-flash",
  "openrouter_models": "qwen/qwen3.8-flash,qwen/qwen3-32b:free,openrouter/free"
}
```

## Privacy

ATLAS keeps the API key local and does not put it into Git. Requests sent through OpenRouter are cloud requests, so do not route private/local-only tasks to the cloud model unless you are comfortable sending that context to the selected provider.

For private work, set `primary_provider` to `local` or use the local model directly.
