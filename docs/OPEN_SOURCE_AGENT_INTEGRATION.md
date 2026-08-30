# Open-source agent integrations

ATLAS tracks the user's forks of two major open-source agent runtimes as vendored Git submodules so their upstream implementations can be studied and integrated without copying unrelated applications wholesale.

## OpenClaw
- Fork: https://github.com/TBNRFPS01/openclaw
- Upstream: https://github.com/openclaw/openclaw
- Pinned commit: `a8c8c82708361d2f859f820562ae1b00cf162e93`
- License: MIT (see upstream `LICENSE` and `THIRD_PARTY_NOTICES.md`)
- Integration targets: gateway/runtime patterns, sessions, skills, plugins, channels, background jobs, workspace model, MCP/ACP interoperability, and operational security patterns.

## Open Interpreter
- Fork: https://github.com/TBNRFPS01/openinterpreter
- Upstream: https://github.com/openinterpreter/openinterpreter
- Pinned commit: `5b07159c477920c159d8892d112b480e7307f257`
- License: Apache-2.0 (verify the pinned tree's notices and dependency licenses before redistributing adapted source)
- Integration targets: execution, computer-use patterns, approvals, sandboxing, skills, MCP, hooks, and agent execution workflows.

These are intentionally tracked as Git submodules rather than copied wholesale into ATLAS. ATLAS remains the primary runtime; individual capabilities should be adapted into ATLAS-native modules with attribution and applicable license notices preserved.
