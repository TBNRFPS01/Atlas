# ATLAS Agent Capability Matrix

This document turns the comparison of open-source agent projects into an ATLAS implementation plan.

## Relevant reference projects

ATLAS is not trying to clone any single project. The following projects are useful reference points for specific capabilities:

| Project | Reference area | ATLAS takeaway |
|---|---|---|
| Hearth | Local desktop agent, Windows, browser, files, voice, memory | First-class computer-use integration |
| AGNT | Goals, workflows, subagents, plugins, traces, durable state | Durable agent runtime |
| xopc | Goals, workflows, triggers, persistent state | Long-running work |
| Hermes Agent | Memory, skills, learning, subagents, scheduled work | Operational learning loop |
| Felix | Lazy skills/memory, retrieval, MCP, providers | Context-efficient extensibility |
| Atlas / desktop agents | Screen understanding and direct desktop control | GUI grounding |
| UI-TARS | Visual GUI grounding and computer actions | Observe/act computer loop |
| Browser Use | Browser-agent infrastructure | First-class browser execution |
| Open Interpreter | General execution, computer use, sandboxing, MCP | Controlled execution environment |
| Goose | Desktop/CLI/API, MCP, providers, workflows | Tool ecosystem and extensibility |
| Agent Zero | Skills, agent hierarchy, extensibility | Self-contained agent capabilities |
| OpenHands | Autonomous software engineering | Coding-agent workflow |
| Aider | Codebase mapping, edits, tests, Git | Reliable coding loop |
| AutoGen / agent frameworks | Agent messaging and orchestration | Bounded subagent delegation |

## The 12 major capability gaps

### Tier 1: agent core

1. **Real intent router**
   - Classify chat, web, computer, browser, files, apps, and missions.
   - Prefer deterministic routing for unambiguous commands.
   - Use the model only when deterministic routing is insufficient.
   - Return structured intent + confidence rather than free-form routing text.

2. **Planner and replanner**
   - Convert a goal into typed steps.
   - Track dependencies and completion criteria.
   - Replan after verified failures.
   - Keep planning separate from `brain.py`.

3. **Unified agent loop**
   - `understand -> route -> plan -> authorize -> execute -> observe -> verify -> remember -> continue`.
   - Support cancellation and bounded iteration.

4. **First-class computer-use subsystem**
   - Accessibility/UI Automation first.
   - DOM/native semantics where available.
   - Vision/OCR fallback.
   - Coordinate actions only as a last resort.
   - Always expose observation and verification hooks.

5. **First-class browser agent**
   - Persistent sessions and tabs.
   - DOM extraction and page state.
   - Navigation, forms, downloads/uploads.
   - Authentication state where configured.
   - Browser-specific verification.

6. **Persistent mission/workflow runtime**
   - Projects, goals, tasks, steps, checkpoints, evidence and result.
   - Pause/resume.
   - Restart recovery.
   - Durable state independent of chat history.

### Tier 2: agent maturity

7. **Operational learning loop**
   - Record action outcomes.
   - Evaluate success/failure.
   - Store reusable lessons.
   - Select better strategies on future attempts.
   - Do not modify model weights or expose private chain-of-thought.

8. **Lazy/hybrid memory retrieval**
   - Keyword + semantic retrieval.
   - Relevance, recency and importance ranking.
   - Load only relevant memories into context.
   - Deduplicate and consolidate memories.

9. **Coding agent**
   - Inspect repository.
   - Plan changes.
   - Edit files.
   - Run tests.
   - Read failures.
   - Iterate.
   - Show diffs.
   - Require permission for commits/destructive changes.

10. **Background worker + scheduler**
    - One-time, delayed and recurring jobs.
    - Persistent queue.
    - Pause/resume/cancel.
    - Survive application restart.

11. **Bounded subagent delegation**
    - Specialized research/browser/computer/coding agents.
    - Isolated context.
    - Explicit tool permissions.
    - Resource/time limits.
    - Result aggregation and final verification by ATLAS.

12. **MCP/plugin ecosystem**
    - Discover and register external tools.
    - Validate schemas and dependencies.
    - Permission every capability.
    - Lifecycle/version handling.

## Cross-cutting requirements

Every new capability should respect these rules:

- **No god objects:** `brain.py` owns model intelligence only.
- **Safety before execution:** authorization happens before high-impact actions.
- **Verification after execution:** a successful function return is not proof of success.
- **Bounded autonomy:** retries, timeouts, budgets and loop detection are mandatory.
- **Observable actions:** record safe action/result traces without exposing private chain-of-thought.
- **Persistent state is not memory:** mission progress belongs in state; user facts belong in memory.
- **Deterministic first:** do not use an LLM where a reliable program can decide the answer.
- **Provider agnostic:** the agent runtime should not depend on one model provider.

## Implementation order

1. Intent router
2. Planner/replanner
3. Unified agent loop
4. Computer-use observe/act/verify loop
5. Browser agent
6. Hybrid/lazy memory retrieval
7. Persistent mission runtime
8. Operational learning
9. Coding agent
10. Background workers and scheduler
11. Bounded subagents
12. MCP/plugin ecosystem

The goal is not to maximize the number of features. The goal is to make the central loop reliable enough that existing ATLAS tools become coordinated capabilities instead of a collection of disconnected commands.
