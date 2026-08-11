# ATLAS

ATLAS is a modular local desktop assistant foundation built around the official OpenAI Python SDK and LM Studio.

## Structure

- `core/` contains the conversation engine, personality, and routing logic.
- `memory/` contains the SQLite-backed memory layer.
- `tools/` contains tool interfaces and integrations.
- `voice/` and `interface/` are reserved for future expansions.

## Run

```powershell
cd C:\Users\tbn\ATLAS
py -3.12 main.py
```

## Notes

- The local LM Studio endpoint is `http://localhost:1234/v1`.
- The code is designed to stay modular and easy to extend.
