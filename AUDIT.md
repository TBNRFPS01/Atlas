# ATLAS Technical Audit

**Date:** 2026-09-20  
**Repository:** TBNRFPS01/Atlas  
**Branch:** `main`  
**Status:** V1.5 Consolidation Audit  
**Scope:** Current repository architecture, execution flow, autonomy, model/provider layer, persistence, tooling, and tests.

---

## 1. Executive Summary

ATLAS has evolved substantially since the previous August audit.

The repository is no longer a small assistant prototype. It now contains a layered agent system with:

- LLM/provider abstraction
- conversation and memory
- natural-language routing
- planning and task models
- a centralized execution pipeline
- permissions and hard safety checks
- persistent goals and agent state
- autonomous mission control
- experience/evaluation components
- agent runtime services
- skills and dynamic tools
- automation, vision, voice, plugins, scheduling, and UI
- a growing test suite and CI

The main architectural risk is therefore **not missing features**. It is **responsibility duplication and boundary erosion**.

The most important consolidation target is `core/router.py`, which is currently roughly 61 KB. ATLAS now has enough dedicated subsystems that the Router should not remain the place where every capability converges.

### Current architectural direction

The intended authority chain should be:

```
User / UI / Voice
        |
        v
      Brain
        |
        v
     Planner
        |
        v
      Router
        |
        v
ExecutionPipeline
  |      |      |
Safety Permissions Observation
        |
        v
      Tool
        |
        v
   Verification
        |
        v
 State / History / Experience
```

For autonomous work:

```
Goal
  |
  v
AutonomyController
  |
  v
Planner
  |
  v
ExecutionPipeline
  |
  v
AgentRuntime capabilities
  |
  +--> trace
  +--> context
  +--> approvals
  +--> model routing
  +--> recovery
  +--> checkpointing
```

The exact implementation still needs consolidation so that no secondary path can bypass the execution/safety boundary.

---

## 2. Current Repository Shape

The current tree contains the following major areas:

| Area | Responsibility |
|---|---|
| `core/` | Brain, routing, execution, permissions, safety, runtime, providers, autonomy, skills |
| `planner/` | Planning, strategies, tasks, evaluation |
| `memory/` | Facts, goals, persistent state, experiences, SQLite |
| `automation/` | Keyboard, mouse, clipboard, process and Windows automation |
| `services/` | Background services, scheduling, queues, monitoring |
| `skills/` | User-facing capability packages |
| `plugins/` | Plugin package boundary |
| `interface/` | GUI, CLI, panels, workers and presentation |
| `vision/` | Screen, OCR, camera and analysis |
| `voice/` | Speech input/output and controller |
| `docs/` | Architecture, development, capability and integration documentation |
| `tests/` | Automated test coverage |
| root | Entry point, configuration, documentation and packaging metadata |

This is a reasonable structure for the project's current scope.

The problem is primarily **internal ownership inside `core/`**, not the existence of these top-level packages.

---

## 3. Architecture Assessment

### 3.1 Brain

**File:** `core/brain.py`

Brain now handles:

- conversation history
- system prompting
- memory context
- memory extraction
- provider construction
- local/cloud provider selection
- streaming
- image analysis

This is workable, but Brain is becoming an infrastructure coordinator.

### Recommendation

Keep Brain responsible for **reasoning and conversation**.

Do not add execution, permissions, goals, mission management, or direct tool execution to Brain.

Longer term, provider selection should converge on the runtime's model-routing abstraction:

```
Brain -> ModelRouter -> Provider
```

Memory extraction should ideally produce structured candidates before persistence rather than treating every extracted statement as an immediately trusted fact.

---

### 3.2 Router

**File:** `core/router.py`

This is currently the largest core module, at approximately 61 KB.

That size is now the clearest architectural warning in the repository.

The Router has accumulated responsibilities that now have dedicated homes elsewhere.

### Desired responsibility

The Router should answer:

> **"What kind of request is this, and which component should handle it?"**

It should not independently own:

- all execution logic
- safety policy
- permissions
- mission state
- provider selection
- autonomous lifecycle
- every tool implementation
- extensive command-specific business logic

### Target

Gradually reduce Router into an orchestration/routing layer.

Do **not** rewrite it in one pass. Extract stable responsibilities behind existing abstractions and keep behavior tests green.

---

### 3.3 ExecutionPipeline

**File:** `core/execution.py`

This is now one of the most important architectural boundaries in ATLAS.

The execution model follows the intended philosophy:

```
Intent
 -> Action
 -> Permissions
 -> Hard Safety
 -> Execution
 -> Observation
 -> Verification
 -> History
```

This should become the **single authoritative execution boundary**.

### Critical invariant

No component should be able to execute an external/system action by bypassing the execution pipeline.

That includes:

- Brain
- AutonomyController
- Planner
- Subagents
- AgentRuntime
- Skills
- UI commands

They may request an action. They should not independently perform privileged execution.

---

### 3.4 AgentRuntime

**File:** `core/agent_runtime.py`

AgentRuntime provides useful cross-cutting capabilities:

- tracing
- context management
- approvals
- subagents
- model routing
- recovery
- checkpointing
- sandbox abstraction

This is a good complement to the existing execution architecture.

### Important limitation

The current `Sandbox` abstraction must **not** be considered a hard security sandbox merely because it runs subprocesses through a wrapper.

If network isolation, filesystem isolation, or read-only behavior is not actually enforced by the operating system, those settings are policy metadata rather than security guarantees.

Likewise, retry-based recovery is not the same as intelligent replanning.

### Rule

AgentRuntime provides capabilities.

It must not become a second execution engine.

---

### 3.5 AutonomyController

**File:** `core/autonomy.py`

AutonomyController is the mission lifecycle layer.

Its responsibilities are appropriate for:

- creating/resuming autonomous goals
- selecting work
- advancing tasks
- checkpointing
- evaluating completion
- recording experience
- safely pausing when approval is required

This fits above Planner and ExecutionPipeline.

### Known correctness risks

1. **Finalized task metadata**
   Finalization logic must preserve the actual tool/action metadata when recording completed tasks. Losing the tool name weakens experience learning and diagnostics.

2. **Checkpoint granularity**
   Checkpoints should be written after each completed task or atomically with task progress. Saving only after a multi-task batch can cause completed work to repeat after a crash.

3. **Approval state**
   Approval detection should use structured task/result state, not string matching such as `"requires user confirmation"`.

### Target lifecycle

```
ACTIVE
  |
  +--> PAUSED
  |
  +--> BLOCKED
  |
  +--> DONE
  |
  +--> FAILED
```

A restart should preserve enough information to continue from the last verified state without repeating already-completed destructive actions.

---

## 4. Persistence

The current persistence model is much more mature than the previous audit described.

### User memory

`memory/facts.py` and `memory/database.py`

Responsible for user-facing facts and memory.

### Goals

`memory/goals.py`

Provides persistent goals with:

- status
- priority
- progress
- source
- parent relationships
- timestamps
- metadata

### Agent state

`memory/state.py`

Provides persistent ATLAS-owned state and checkpoint storage.

### Experience

`memory/experience.py`

Provides a basis for learning from previous executions.

### Architectural rule

Keep these concepts separate:

- **Facts:** what ATLAS believes about the user/world
- **Goals:** what ATLAS is trying to accomplish
- **Agent state:** runtime/mission progress
- **Experience:** what happened during previous work

Do not collapse all four into a generic "memory" object.

---

## 5. Planning

The current planner area contains:

- `planner.py`
- `task.py`
- `strategies.py`
- `evaluator.py`

This is now a real planning subsystem rather than the simple rule-based planner described in the previous audit.

The Planner should own:

- decomposition
- sequencing
- strategy selection
- task representation

The Planner should **not** own final permissions or privileged execution.

### Target

```
Planner: "Here is what should happen."
ExecutionPipeline: "Here is whether and how it may happen."
```

This distinction is fundamental to keeping autonomy safe and predictable.

---

## 6. Model / Provider Architecture

The repository now contains several provider/model-related modules, including:

- `core/providers.py`
- `core/openrouter.py`
- `core/smart_provider.py`
- `core/smart_router.py`
- `core/runtime_api.py`

This supports the project's goal of interchangeable local/cloud brains.

However, multiple routing abstractions create a potential duplication problem.

### Target

There should eventually be one authoritative decision point for:

> **Which model/provider should handle this request?**

A clean direction is:

```
Brain
  |
  v
ModelRouter
  |
  +--> LocalProvider
  +--> OpenRouterProvider
  +--> GatewayProvider
```

Other provider-selection logic should either delegate to this layer or become a specialized policy beneath it.

---

## 7. Skills, Tools and Plugins

ATLAS now has three distinct extension concepts:

### Tools

Low-level executable capabilities.

### Skills

Higher-level user-facing capabilities built from tools and logic.

### Plugins

External/integrated extension boundary.

This separation is useful.

The key requirement is that all executable capabilities eventually converge on the same permission/safety/execution machinery.

A new skill must not become a secret second route around `ExecutionPipeline`.

---

## 8. Safety and Permissions

Current dedicated modules include:

- `core/permissions.py`
- `core/safety.py`
- `core/execution.py`

This is a major improvement over the previous architecture.

### Required invariant

```
Every external action
        |
        v
Permission check
        |
        v
Hard safety check
        |
        v
Execution
        |
        v
Observation
        |
        v
Verification
```

No LLM response, planner result, skill, plugin, or autonomous agent should be treated as permission to execute by itself.

---

## 9. Services and Background Work

The repository contains services for:

- scheduling
- task queues
- daily briefing
- goals
- memory cleanup
- provider monitoring
- health monitoring
- plugins
- voice

These are useful, but background services increase lifecycle complexity.

### Rule

Background services should submit work to the same core orchestration/execution path used by interactive requests.

Avoid creating separate "background execution" implementations.

---

## 10. UI / Interface

The interface is now a substantial subsystem rather than the GUI stub described by the old audit.

Current areas include:

- chat
- GUI
- sidebar
- topbar
- command palette
- composer
- settings
- memory panel
- workers
- voice overlay
- theme/layout

This should remain a presentation layer.

The UI should call application/runtime APIs rather than directly manipulating internal execution state.

---

## 11. Documentation Drift

The previous `AUDIT.md` was dated **2026-08-05** and described an earlier architecture.

Several findings from that document are now stale, including:

- missing `requirements.txt`
- Router completely bypassing the newer execution architecture
- planner being only a five-keyword decomposer
- GUI being a placeholder
- lack of persistent goals/agent state
- absence of AgentRuntime
- absence of AutonomyController
- early-stage plugin/provider architecture

Those should not be treated as current blockers.

### Documentation rule

Whenever a major architectural layer lands, update:

1. `docs/architecture.md`
2. `AUDIT.md`
3. relevant README sections

Otherwise the documentation becomes a historical snapshot instead of an engineering guide.

---

## 12. Current Risk Register

| Risk | Severity | Current assessment |
|---|---|---|
| Router is too large | HIGH | Main consolidation target |
| Multiple execution paths | HIGH | Must enforce one execution boundary |
| Duplicate provider-routing logic | MEDIUM | Consolidate around ModelRouter |
| Autonomous checkpoint correctness | HIGH | Must be crash-safe |
| Structured approval state | HIGH | Replace string-based detection |
| Sandbox overclaiming | HIGH | Not a hard OS security boundary |
| Brain responsibility growth | MEDIUM | Keep it focused on reasoning |
| Documentation drift | MEDIUM | Previous audit is substantially stale |
| Service/background path divergence | MEDIUM | Must use common orchestration |
| Test coverage around autonomy | HIGH | Needs failure/restart/approval cases |

---

## 13. V1.5 Consolidation Plan

### Phase A: Freeze architecture

Do not add major new subsystems.

Define and document these authorities:

- Brain = reasoning
- Planner = planning
- Router = routing
- ExecutionPipeline = execution authority
- Permissions/Safety = policy gates
- AgentRuntime = runtime capabilities
- AutonomyController = mission lifecycle
- GoalManager = persistent goals
- AgentStateStore = persistent runtime state
- ExperienceStore = execution history/learning
- ModelRouter = model/provider selection

### Phase B: Shrink Router

Extract existing responsibilities into the abstractions already present.

Do not rewrite behavior unnecessarily.

Priority:

1. tool/action dispatch
2. command handling
3. memory operations
4. autonomous operations
5. provider/model decisions
6. miscellaneous helpers

Each extraction should preserve tests.

### Phase C: Harden autonomy

Add tests for:

- crash after task completion
- restart/resume
- blocked approval
- denied approval
- failed verification
- retry
- goal completion
- duplicate execution prevention

### Phase D: Enforce execution boundary

Audit every path that can call:

- subprocess
- filesystem mutation
- keyboard/mouse automation
- process management
- browser actions
- external APIs
- plugins

Each should converge on the permission/safety/execution boundary.

### Phase E: Consolidate model routing

Choose one authoritative provider-selection path.

Keep provider implementations interchangeable.

### Phase F: Documentation synchronization

Update architecture diagrams and contributor documentation after the consolidation.

---

## 14. What NOT To Do

Do not:

- rewrite ATLAS from scratch
- create another mega-orchestrator
- add another memory system
- add another model router
- add another execution pipeline
- move everything into one "agent" class
- make AgentRuntime execute tools directly
- let autonomy bypass safety for convenience
- add features simply because the repository is already modular

The architecture already has most of the pieces.

The next gain comes from **making the pieces agree about who is in charge**.

---

## 15. Definition of Done for V1.5

ATLAS V1.5 should satisfy:

- [ ] One authoritative execution path
- [ ] One authoritative model-selection path
- [ ] Router is substantially smaller and focused
- [ ] Planner cannot bypass execution policy
- [ ] Autonomy cannot bypass execution policy
- [ ] Skills/tools/plugins share the same safety boundary
- [ ] Autonomous checkpoints survive crashes without repeating completed work
- [ ] Approval state is structured
- [ ] Verification results are persisted
- [ ] Experience records retain action/tool metadata
- [ ] AgentRuntime remains a capability layer
- [ ] Brain remains focused on reasoning/conversation
- [ ] Architecture documentation matches the implementation
- [ ] Regression tests cover the above invariants

---

## 16. Final Assessment

**ATLAS is no longer suffering primarily from missing architecture. It is suffering from architectural overlap.**

That is a much better problem to have.

The current system has enough infrastructure for the next stage:

```
                 ATLAS
                   |
        ┌──────────┴──────────┐
        |                     |
     Reasoning             Mission
      Brain            AutonomyController
        |                     |
     Planner  <---------------+
        |
      Router
        |
 ExecutionPipeline
   /     |      \
Safety Permissions Verification
        |
       Tool
        |
     Observation
        |
   State / History
```

The V1.5 objective should therefore be:

> **Consolidate, enforce boundaries, make recovery correct, and reduce accidental complexity.**

Not "add another 10,000 lines."

---

## Appendix: Current Core Inventory

### Core
- `agent_runtime.py`
- `application_registry.py`
- `autonomy.py`
- `brain.py`
- `builtin_agents.py`
- `dynamic_tools.py`
- `events.py`
- `execution.py`
- `logging_utils.py`
- `mcp.py`
- `natural_router.py`
- `openrouter.py`
- `orchestrator.py`
- `permissions.py`
- `personality.py`
- `plugins.py`
- `providers.py`
- `reflection.py`
- `router.py`
- `runtime_api.py`
- `safety.py`
- `skill_manager.py`
- `skill_registry.py`
- `skills.py`
- `smart_provider.py`
- `smart_router.py`
- `spotify_auth.py`
- `subagents.py`
- `undo.py`

### Planner
- `planner.py`
- `task.py`
- `strategies.py`
- `evaluator.py`

### Memory
- `database.py`
- `facts.py`
- `goals.py`
- `state.py`
- `experience.py`

### Services
- scheduler
- task queue
- goal service
- provider monitor
- health monitor
- memory cleanup
- daily briefing
- plugin manager
- voice service

---

**Audit conclusion:** ATLAS has reached the point where **consolidation is more valuable than expansion**. The existing architecture is capable of supporting the planned Browser → Skills → Persistent State → Nodes → Multi-Agent → Communication roadmap, provided execution, model selection, state, and mission ownership are kept unambiguous.
