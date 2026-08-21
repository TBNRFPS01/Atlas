# ATLAS

**ATLAS is a local-first desktop AI agent and personal agent runtime for understanding, planning, operating, verifying, recovering, and learning on your computer.**

It is built around a tool-driven agent architecture with an LLM provider layer. ATLAS can control the computer, remember information, run multi-step missions, persist mission checkpoints, recover from failures, use skills and plugins, interact with the web, control media such as Spotify, and expose what it is doing through debugging and observability tools.

> **Current status:** V1 foundation is implemented and actively tested. **253 tests pass.** The UI is still being polished separately from the core agent system. ATLAS has now entered its evolution phase: strengthening persistent missions first, then expanding skills, perception, autonomous execution, trusted nodes, and multi-device interfaces.

## What ATLAS Can Do

### 🗿 Agent & Missions
- Break goals into executable steps
- Execute tools and verify results
- Recover from failed steps with an LLM-assisted fallback
- Produce mission completion/failure summaries
- Fall back to heuristic planning when an LLM plan is unavailable
- Persist mission state, checkpoints, context, status, and outcomes
- Resume unfinished missions after restart

### 🤖 Autonomy & Learning
- Persistent agent state that survives restarts (checkpointed plans, counters, flags)
- Persistent, priority-ordered goals with status, progress, and round-robin selection
- Autonomous goal advancement: `/auto <goal>` runs a full self-evaluated mission; the optional background goal service advances active goals on a schedule
- Experience-based learning: ATLAS records which strategy/tool worked for each task type and biases future plans toward proven approaches (`/lessons`)
- Self-evaluation after every mission: verdict, score, issues, and distilled lessons stored as retrievable memories
- Adaptive strategy selection biases the planner prompt toward the best-known approach for the task type

### 🖥️ Computer Control
- Launch and manage applications/windows
- Keyboard input, key presses and hotkeys
- Mouse movement, clicking and scrolling
- Clipboard operations
- Process/system operations
- Screenshots and screen inspection
- File operations and reversible trash/undo workflows

### 👁️ Vision
- Capture the screen
- Understand active-window/context information
- Optional OCR support
- Vision-model analysis when a compatible model is loaded

### 🧠 Memory & Persistent Context
- Persistent memory with facts, preferences, tasks, events, projects and goals
- Ranked retrieval using relevance, recency, importance and usage
- Explicit remember/forget/recall/search commands
- Durable mission state separate from general memory
- Mission checkpoints, current steps, context, deadlines, results, and failure state
- Resume candidates for unfinished work

### 🛡️ Safety & Permissions
- Hard safety boundaries for protected system locations and critical operations
- Permission manager for tool actions
- Confirmation handling for permission-sensitive operations
- ATLAS's own memory/database protected from destructive operations
- Destructive file deletion routed through reversible trash/undo where supported

### 🧩 Tools, Skills & Plugins
- Automatic discovery of tool modules in `tools/`
- Drop-in skills from `skills/`
- Trigger-based skill execution
- Tool-call logging with timing and error information
- Debugging/observability commands for tracing agent behavior

### 🎵 Spotify
- Spotify OAuth authentication
- Current track information
- Play/pause
- Next/previous track
- Search for tracks, artists, albums and playlists
- Start playback from search results
- Playlist playback
- Device listing/selection
- Volume control

### 🌐 Online Tools
- Web search/fetch capabilities
- Retry and exponential-backoff handling
- HTTP error handling
- Email tooling with validation, SSL support and attachment checks

### 🎙️ Voice
- Voice configuration and listening pipeline
- Hardware diagnostics
- Voice-controller integration
- Mocked end-to-end coverage
- Ready for real microphone/Whisper testing when the required hardware/model is available

### 🎮 Media & Other Integrations
- Cross-platform media controls
- Minecraft-related tooling
- System tools and automation helpers

## Architecture

### Current V1 + Evolution Foundation

```text
User / Voice / UI
        ↓
      Router
        ↓
  ┌─────┴─────────────────────┐
  │                           │
Brain / LLM              Direct Commands
  │                           │
  └──────────┬────────────────┘
             ↓
        Mission Runtime
             ↓
       Tool / Skill Registry
             ↓
   ┌─────────┼──────────┐
   │         │          │
 Tools     Skills    Plugins
   │         │          │
   └─────────┼──────────┘
             ↓
Permissions → Safety Boundaries
             ↓
Execution → Observation → Verification
             ↓              ↓
        Recovery ←──────────┘
             ↓
      Mission Checkpoint
             ↓
     Persistent State / Memory
             ↓
       Observability / Audit
```

The core is modular. Tools are discovered from `tools/`, skills are loaded from `skills/`, and the runtime coordinates direct commands with LLM-driven behavior.

### Target Evolution Architecture

```text
                         ┌─────────────────────┐
                         │ Frontier / Local    │
                         │       Models        │
                         └──────────┬──────────┘
                                    ↓
                         Planning / Reasoning
                                    ↓
                         ┌─────────────────────┐
                         │ Deterministic Policy│
                         │ Permissions / Risk  │
                         └──────────┬──────────┘
                                    ↓
                         Mission / Skill Router
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
                  Skills          Nodes        Interfaces
                    ↓               ↓               ↓
                 Tools          Devices        CLI/Web/iPad
                    └───────────────┼───────────────┘
                                    ↓
                              Observation
                                    ↓
                         Independent Verification
                                    ↓
                         Recovery / Rollback
                                    ↓
                       Persistent Mission State
                                    ↓
                         Learning / Audit Trail
```

The goal is **smart planning with deterministic, enforceable boundaries**. Model quality should improve ATLAS's reasoning, not become the mechanism that enforces security.

## Evolution Roadmap

ATLAS has moved from feature accumulation into deliberate runtime evolution.

### Phase 0 — Stabilize the Foundation
- [x] Establish the existing agent, memory, mission, skills, safety, and observability baseline
- [ ] Audit all mutating tools against one authorization path
- [ ] Expand adversarial and integration coverage
- [ ] Remove flaky behavior and establish a clean regression baseline

### Phase 1 — Persistent Agent 🧠 **CURRENT**
- [x] Add durable mission storage
- [x] Store mission goal, priority, status, deadline, step, checkpoint, context, result, and failure state
- [x] Identify unfinished missions for startup/resume handling
- [ ] Wire mission checkpoints directly into the live agent execution loop
- [ ] Automatically resume eligible missions after restart
- [ ] Persist structured action/outcome history into mission context
- [ ] Add stale-state detection and explicit mission recovery

### Phase 2 — Extensible Agent 🧩
- [ ] Package skills with manifests and versions
- [ ] Declare dependencies, capabilities, permissions, triggers, and configuration
- [ ] Add skill health checks
- [ ] Sandbox untrusted/third-party skills
- [ ] Make capability installation independent of ATLAS core routing

### Phase 3 — Perceptive Agent 👁️
- [ ] Unify screenshots, OCR, vision, DOM, window state, and tool output
- [ ] Add before/after state comparison
- [ ] Feed environmental changes into verification and recovery
- [ ] Distinguish issued actions from verified outcomes

### Phase 4 — Autonomous Missions 🔄
- [ ] Long-running mission queues
- [ ] Checkpoint every meaningful stage
- [ ] Deadline and resource budgets
- [ ] Retry budgets and failure classification
- [ ] Blocked-state detection
- [ ] Re-plan instead of repeating failed actions
- [ ] Background mission execution with bounded authority

### Phase 5 — Trusted Agent 🔐
- [ ] Per-mission authority
- [ ] Per-skill and per-node permissions
- [ ] Credential isolation
- [ ] Emergency stop / autonomy pause
- [ ] Complete audit trail
- [ ] Stronger rollback and transaction semantics

### Phase 6 — Multi-Device Agent 🌐
- [ ] Trusted node identity
- [ ] Authentication and encrypted transport
- [ ] Capability discovery
- [ ] Node health/status
- [ ] Task routing and revocation
- [ ] Capability-aware node selection

### Phase 7 — Unified Interfaces 📱
- [ ] Stable runtime API
- [ ] Local web control surface
- [ ] iPad/mobile client
- [ ] Voice and notification clients
- [ ] Keep interfaces thin so all agent logic remains in the runtime

### Phase 8 — Proactive Agent ⚡
- [ ] Approved watches and event triggers
- [ ] Goal-aware reminders
- [ ] Failure/change notifications
- [ ] Useful preparation of approved actions
- [ ] Quiet-hours and notification policy

### Phase 9 — Multi-Agent Execution 👥
- [ ] Mission controller
- [ ] Scoped specialist agents
- [ ] Shared controlled state
- [ ] Independent verification agent
- [ ] Global stop and authority boundaries

### Phase 10 — Self-Maintaining Runtime 🛠️
- [ ] Dependency health checks
- [ ] Skill/provider health checks
- [ ] Database/configuration diagnostics
- [ ] Safe automatic recovery
- [ ] Update proposals requiring explicit approval for high-impact changes

### Phase 11 — Agent Platform 🚀
- [ ] Stable runtime API
- [ ] Publicly documented skill/node interfaces
- [ ] Capability registry
- [ ] Reusable mission system
- [ ] Consistent security model across all extensions

## Safety Model

ATLAS is designed to be powerful without treating every requested action as automatically safe.

The safety layer protects critical paths and forbidden operations. Supported destructive workflows can use the undo/trash system instead of immediately destroying data.

For autonomous missions, the planner executes and verifies steps rather than blindly assuming that a successful tool call means the overall task succeeded.

Autonomy is gated by default: the background goal service only runs when `autonomy_enabled` is true, advances a bounded number of steps per cycle, and runs with *agent* consent so destructive/elevated steps are parked for explicit user confirmation instead of auto-approved. Hard safety boundaries always win, and mission state is now persisted separately so the evolution toward resumable work can be built on top of the existing runtime.

### Security hardening goals

The next security phase is intentionally defense-in-depth rather than model-dependent:

- Route **every state-mutating tool action** through one authorization/enforcement path, including write, append, delete, shell/process, automation, and future tools.
- Replace text/regex-based confirmation with a structurally separate approval event that cannot be supplied by untrusted model or fetched content.
- Treat webpages, files, tool output, emails, and other externally sourced content as **untrusted data**, never as authoritative instructions.
- Add adversarial tests for prompt injection, path traversal, fake confirmations, malformed tool calls, deceptive tool results, and authorization bypasses.
- Move execution into a restricted sandbox with filesystem allowlists, process restrictions, network policy, and resource limits where practical.
- Keep security policy deterministic and auditable; use the model for planning and reasoning, not for deciding whether its own actions are permitted.
- Preserve reversible operations and add stronger rollback/transaction semantics where possible.
- Maintain a detailed audit trail for tool requests, approvals, policy decisions, executions, verification, and recovery.
- Isolate credentials and secrets from prompts, tool results, logs, and model-visible state.

These are **roadmap targets**, not claims that every item is already implemented.

## Model Strategy

ATLAS is designed to work with local-first providers such as LM Studio while allowing stronger models to be used when they provide meaningful value.

The target model strategy is:

- **Frontier models:** complex planning, difficult reasoning, recovery, interpretation, and high-value verification.
- **Local models:** routine tasks, privacy-sensitive work, low-cost operations, and offline fallback.
- **Deterministic systems:** permissions, safety policy, confirmation, sandboxing, resource limits, and execution enforcement.

Model routing should be based on task complexity and capability requirements rather than making every operation depend on the most expensive model.

## Autonomy & Reliability

The long-term execution loop is:

```text
Goal
 ↓
Understand intent + constraints
 ↓
Load capabilities
 ↓
Plan
 ↓
Risk / Permission Check
 ↓
Execute
 ↓
Observe
 ↓
Verify against the original goal
 ↓
Success ───────────────→ Persist outcome → Finish
 ↓
Failure
 ↓
Classify → Recover / Roll back / Re-plan
 ↓
Checkpoint
 ↓
Verify again
```

The mission store provides the foundation for resumable work. The next implementation step is connecting checkpoints to the live executor so an interrupted mission can resume from its last known state rather than starting over.

## Observability

ATLAS includes `/debug` and related diagnostics for inspecting:

- Provider status
- Available tools and skills
- Permission rules
- Undo availability
- Tool-call timings
- Recent errors
- Execution traces
- Mission state and progress as the runtime integration expands

The hardened architecture will extend observability into a complete audit trail covering authorization decisions, approvals, sandbox execution, verification, recovery, and task lifecycle events.

## Testing

The project currently has **253 passing tests** covering areas including:

- Automation and computer control
- Tool dispatch
- Brain/provider behavior
- Memory and retrieval
- Missions and planner recovery
- Permissions and safety boundaries
- Skills and plugins
- Spotify
- System tools and undo
- Vision
- Voice
- Web retry/robustness
- Email and media integrations

CI is configured under `.github/workflows/ci.yml`.

The next testing phase will add adversarial and integration coverage, especially around authorization boundaries, prompt injection, sandbox escapes, path traversal, confirmation spoofing, malformed tool calls, persistent mission recovery, and cross-component behavior.

## Running ATLAS

ATLAS is currently developed as a Python application and can be run from the repository after installing its dependencies.

The LLM layer can use a local provider such as LM Studio when configured. Some capabilities, including Spotify, vision models, OCR and voice, require their corresponding external credentials, models or hardware.

The polished desktop UI/application packaging is a separate layer and is still being developed.

## Project Structure

```text
ATLAS/
├── core/              # Router, brain, providers, safety, permissions, skills, undo
├── planner/           # Mission planning, execution, verification and recovery
├── tools/             # Discoverable tool integrations
├── skills/            # Drop-in ATLAS skills
├── memory/            # Persistent memory, retrieval and mission state
├── automation/        # Computer/clipboard automation
├── vision/            # Screen understanding and OCR/vision helpers
├── voice/             # Voice configuration, listening and hardware support
├── interface/         # GUI and settings UI
├── tests/             # Automated test suite
└── .github/workflows/ # CI
```

## Philosophy

ATLAS is built around a simple idea:

> **Give the agent useful capabilities, make its actions observable, and put hard safety boundaries around the things it must never do.**

The evolution goal is to turn that foundation into a **personal agent runtime**: give ATLAS a meaningful goal, let it choose the right capabilities, execute within explicit authority, observe and verify its work, recover when necessary, persist what happened, and ask for help only when it genuinely needs the user.

The objective is **capability with control**, not maximum autonomy for its own sake.

## Evolution Documents

- `ATLAS_EVOLUTION.md` — long-term evolution roadmap and definition of mature ATLAS
- `docs/EVOLUTION_PRINCIPLES.md` — engineering principles for evolving the runtime safely
