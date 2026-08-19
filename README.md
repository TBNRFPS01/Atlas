# ATLAS

**ATLAS is a local-first desktop AI agent for understanding, planning, operating, verifying, and recovering on your computer.**

It is built around a tool-driven agent architecture with an LLM provider layer. ATLAS can control the computer, remember information, run multi-step missions, recover from failures, use skills and plugins, interact with the web, control media such as Spotify, and expose what it is doing through debugging and observability tools.

> **Current status:** V1 foundation is implemented and actively tested. **253 tests pass.** The UI is still being polished separately from the core agent system.

## What ATLAS Can Do

### 🗿 Agent & Missions
- Break goals into executable steps
- Execute tools and verify results
- Recover from failed steps with an LLM-assisted fallback
- Produce mission completion/failure summaries
- Fall back to heuristic planning when an LLM plan is unavailable

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

### 🧠 Memory
- Persistent memory with facts, preferences, tasks, events, projects and goals
- Ranked retrieval using relevance, recency, importance and usage
- Explicit remember/forget/recall/search commands

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
        Tool Registry
             ↓
   ┌─────────┼──────────┐
   │         │          │
 Tools     Skills    Plugins
   │
   ↓
Permissions → Safety Boundaries
   ↓
Execution → Verification → Recovery
   ↓
Observability / Memory / Undo
```

The core is modular. Tools are discovered from `tools/`, skills are loaded from `skills/`, and the router coordinates direct commands with LLM-driven behavior.

## Safety Model

ATLAS is designed to be powerful without treating every requested action as automatically safe.

The safety layer protects critical paths and forbidden operations. Supported destructive workflows can use the undo/trash system instead of immediately destroying data.

For autonomous missions, the planner executes and verifies steps rather than blindly assuming that a successful tool call means the overall task succeeded.

Autonomy is gated by default: the background goal service only runs when `autonomy_enabled` is true, advances a bounded number of steps per cycle, and runs with *agent* consent so destructive/elevated steps are parked for explicit user confirmation instead of auto-approved. Hard safety boundaries always win, and every mission's plan is checkpointed so a restart resumes the same goal rather than restarting it.

## Debugging & Observability

ATLAS includes `/debug` and related diagnostics for inspecting:

- Provider status
- Available tools and skills
- Permission rules
- Undo availability
- Tool-call timings
- Recent errors
- Execution traces

This is intended to make failures explainable instead of turning the agent into a black box.

## Testing

The project currently has **161 passing tests** covering areas including:

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
├── memory/            # Persistent memory and retrieval
├── automation/        # Computer/clipboard automation
├── vision/            # Screen understanding and OCR/vision helpers
├── voice/             # Voice configuration, listening and hardware support
├── interface/         # GUI and settings UI
├── tests/             # Automated test suite
└── .github/workflows/ # CI
```

## Roadmap

The core V1 foundation is already in place. The main remaining work is product polish and real-environment validation rather than building the underlying architecture from scratch.

- [x] Persistent agent state, goal management, experience-based learning, self-evaluation, and adaptive strategy selection
- [x] Harden autonomous confirmation semantics (background runs never auto-approve destructive steps)
- [ ] Finish and polish the desktop UI
- [ ] Run full real-hardware voice E2E testing
- [ ] Validate vision with a loaded vision model and OCR setup
- [ ] Continue expanding edge-case/integration tests
- [ ] Package ATLAS as a polished desktop application

## Philosophy

ATLAS is built around a simple idea:

> **Give the agent useful capabilities, make its actions observable, and put hard safety boundaries around the things it must never do.**

The goal is not just to make an LLM answer questions. The goal is to make it capable of **doing useful work on the computer while remaining understandable, testable, and recoverable.**
