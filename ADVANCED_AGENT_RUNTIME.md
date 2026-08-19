# ATLAS Advanced Agent Runtime

ATLAS already has a working V1 agent foundation. This layer adds the infrastructure needed to grow it toward a full general-purpose agent runtime without replacing the existing Router, Planner, tools, skills, memory, safety, or autonomy systems.

## Added

- **Agent runtime composition** in `core/agent_runtime.py`
  - execution tracing
  - persistent JSONL traces
  - context budgeting/compaction
  - human-in-the-loop approval gates
  - subagent/team delegation
  - bounded recovery with backoff
  - capability-aware model selection
  - resumable runtime checkpoints
  - bounded subprocess sandbox hooks
- **MCP-compatible tool adapter** in `core/mcp.py`
  - tool discovery
  - schema metadata
  - transport-neutral tool calls
  - in-memory transport for tests and local bridges
- **Persistent background scheduler** in `services/scheduler.py`
  - recurring jobs
  - persisted state
  - bounded due-job execution
  - failure tracking
- **Versioned skill registry** in `core/skill_registry.py`
  - skill manifests
  - versions
  - dependencies metadata
  - capability indexing
  - validation before loading

## Safety note

The sandbox is intentionally conservative. It uses a dedicated temporary workspace, `shell=False`, bounded output, and timeouts. The `allow_network` field is a policy declaration, not a claim of OS-level network isolation. Real network/CPU/RAM isolation should use a container, VM, or platform sandbox backend before untrusted code is executed autonomously.

The approval gate also never auto-approves an action. Existing ATLAS safety and permission rules remain the authority for actual tool execution.

## Next wiring targets

The new runtime is deliberately composable. The next integration work is to connect it to the existing Router/Planner execution path, then add specialized built-in subagents for research, coding, browser, vision, and verification. After that, the MCP adapter can bridge external tool servers and the scheduler can feed bounded background goals through the existing autonomy controller.

This keeps the existing working architecture intact instead of replacing it with a second agent framework.
