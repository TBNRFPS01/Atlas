# Third-party components

ATLAS includes ATLAS-native implementations informed by open-source projects
that were inspected in the author's forks. No third-party project is copied
wholesale into ATLAS; adapted implementations remain subject to their source
licenses and notices.

## Hearth

- Hearth: https://github.com/0pen-Sourcer/Hearth
- Fork inspected during integration: https://github.com/TBNRFPS01/Hearth
- License: MIT
- Relevant ideas: Windows accessibility, desktop control, dynamic tools, and
  bounded agent execution.

The accessibility implementation in `automation/accessibility.py` is an
independent ATLAS implementation rather than a verbatim copy of Hearth's
source.

## OpenClaw

- OpenClaw: https://github.com/openclaw/openclaw
- ATLAS fork: https://github.com/TBNRFPS01/openclaw
- License: MIT; see the upstream `LICENSE` and `THIRD_PARTY_NOTICES.md`.
- Relevant ideas: gateway/runtime architecture, skills, channels, nodes, and
  plugin-oriented execution.

## Open Interpreter

- Open Interpreter: https://github.com/openinterpreter/openinterpreter
- ATLAS fork: https://github.com/TBNRFPS01/openinterpreter
- License: Apache-2.0
- Relevant ideas: provider abstraction, computer-use execution, approvals,
  sandboxing, and agent harness patterns.

## OpenAgentd

- OpenAgentd: https://github.com/lthoangg/openagentd
- ATLAS fork: https://github.com/TBNRFPS01/OpenAgent
- License: Apache-2.0
- Relevant ideas: lead/worker agents, specialist delegation, provider/model
  fallback, editable memory, coding workspaces, tool inspection, and
  diagnostics.

## Web Agent

- Web Agent: https://github.com/kaizenetwork/web-agent
- ATLAS fork: https://github.com/TBNRFPS01/web-agent
- License: MIT (verify the exact upstream revision before redistributing any
  adapted source)
- Relevant ideas: planning, reflection, persistent knowledge, skill/tool
  selection, and bounded tool loops.

## OwnOrbit AI

- OwnOrbit AI: https://github.com/TBNRFPS01/ownorbit-ai
- Upstream project: https://github.com/OwnOrbitAI/OwnOrbit
- License: MIT (verify the exact upstream revision before redistributing any
  adapted source)
- Relevant ideas: generated tools, diagnostics, state inspection, rollback,
  and autonomous task support.

## MIRA

MIRA was inspected for architecture and routing ideas, but its AGPL-3.0
licensing is intentionally not incorporated into ATLAS source. In particular,
ATLAS does not vendor or copy MIRA's implementation.

- ATLAS fork: https://github.com/TBNRFPS01/MIRA
- License: AGPL-3.0
- Relevant ideas retained as independent designs: reasoning-aware routing,
  provider health, MCP integration, sub-agents, and audit trails.

## Other inspected forks

Additional user forks were reviewed for ideas where relevant, including
`airi`, `SmartiAI-Agent-for-Windows`, `felix`, `monaw`, `OpenNivara`, `xopc`,
`alfred`, `ATTACKSHARK`, and `launcher-`. Their code is not automatically
vendored into ATLAS; each component must be evaluated for compatibility,
security, and license requirements before source adaptation.
