# ATLAS 🤖

**A local-first AI desktop agent for Windows.**

ATLAS is a modular AI agent designed to **understand what you ask, choose the right capability, safely perform actions on your computer, verify the result, remember useful information, and continue long-running work.**

> **The LLM is the brain, not the entire body.**

ATLAS keeps intelligence, routing, planning, execution, memory, safety, automation, and the user interface as separate systems.

> **Current status:** V1 foundation is implemented and actively tested. The core architecture is modular and the desktop UI is still being polished.

## ✨ What ATLAS Can Do

### 🗿 Agent & Missions
- Break goals into executable steps
- Execute tools and verify results
- Recover from failed steps with fallback strategies
- Produce mission completion/failure summaries
- Persistent agent state and goals
- Experience-based learning and self-evaluation
- Adaptive strategy selection

### 🧠 Intelligence & Routing
- Local or OpenAI-compatible LLM providers
- Natural-language intent routing
- Direct commands for deterministic operations
- Tool and skill selection
- Structured multi-step planning
- Context-aware responses
- Model/provider abstraction

### 🖥️ Computer Control
- Launch and manage applications/windows
- Keyboard input, key presses and hotkeys
- Mouse movement, clicking and scrolling
- Clipboard operations
- Process/system operations
- Screenshots and screen inspection
- Windows Accessibility/UI Automation support
- File operations and reversible trash/undo workflows

### 👁️ Vision
- Capture the screen
- Understand active-window/context information
- Optional OCR support
- Vision-model analysis when a compatible model is loaded
- Observe → act → observe workflows

### 🌐 Browser
- Browser automation through Playwright
- Navigation and page interaction
- Tabs and browser sessions
- Form interaction
- Downloads/uploads
- Screenshots and page extraction
- Persistent browser state where configured
- Browser action verification

### 🧠 Memory
- Persistent memory with facts, preferences, tasks, events, projects and goals
- Ranked retrieval using relevance, recency, importance and usage
- Explicit remember/forget/recall/search commands
- Experience memory
- Hybrid keyword/semantic retrieval architecture
- Context selection for agent tasks

### 🛡️ Safety & Permissions
- Hard safety boundaries for protected system locations and critical operations
- Permission manager for tool actions
- Confirmation handling for permission-sensitive operations
- ATLAS's own memory/database protected from destructive operations
- Destructive file deletion routed through reversible trash/undo where supported
- Resource and retry limits for autonomous work

### 🧩 Tools, Skills & Plugins
- Automatic discovery of tool modules in `tools/`
- Drop-in skills from `skills/`
- Trigger-based skill execution
- Tool-call logging with timing and error information
- Debugging/observability commands
- Extensible plugin architecture
- MCP integration planned for external tool ecosystems

### 🤖 Multi-Agent Architecture
ATLAS is designed to delegate specialized work without turning the main brain into a god object:

```text
                    ATLAS
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
      Research      Browser     Computer
       Agent         Agent       Agent
          │           │           │
          └───────────┼───────────┘
                      ▼
                 ATLAS result
```

The coordinator remains responsible for delegation, permissions, resource limits, result aggregation and final verification.

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
- Ready for real microphone/Whisper testing when required hardware/model is available

### 🎮 Media & Other Integrations
- Cross-platform media controls
- Minecraft-related tooling
- System tools and automation helpers

## 🏗️ Architecture

ATLAS intentionally avoids putting everything into one giant `brain.py`.

```text
                         ATLAS
                           │
                    ┌──────▼──────┐
                    │    BRAIN    │
                    │ LLM +       │
                    │ Context     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   ROUTER    │
                    │ Intent      │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   PLANNER   │
                    │ Goals/Steps │
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │   SAFETY + PERMISSIONS │
              └────────────┬────────────┘
                           │
                    ┌──────▼──────┐
                    │  EXECUTOR   │
                    └──────┬──────┘
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
      COMPUTER          BROWSER            TOOLS
          │                │                 │
          └────────────────┼─────────────────┘
                           │
                    ┌──────▼──────┐
                    │   OBSERVE   │
                    │ + VERIFY    │
                    └──────┬──────┘
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
             MEMORY                 STATE
                │                     │
                └──────────┬──────────┘
                           ▼
                      EXPERIENCE
                           │
                           ▼
                      NEXT ACTION
```

The core agent loop is:

```text
UNDERSTAND
    ↓
ROUTE
    ↓
PLAN
    ↓
CHECK PERMISSIONS
    ↓
EXECUTE
    ↓
OBSERVE
    ↓
VERIFY
    ↓
REMEMBER
    ↓
CONTINUE / FINISH / RECOVER
```

Each subsystem has a clear responsibility. `brain.py` should provide model intelligence, not own tools, safety, memory, browser automation, scheduling or mission management.

## 📋 Planning

Simple requests can execute directly. Complex requests become structured plans.

Example:

```text
"Find my newest Minecraft screenshot and open it."

        ↓

1. Search screenshots
2. Filter Minecraft images
3. Sort by modification time
4. Select newest
5. Open file
6. Verify it opened
```

Plans can contain steps, dependencies, checkpoints, timeouts, retry policies and completion criteria.

## ⚙️ Execution Pipeline

Every meaningful action should pass through the execution system:

```text
Action
  ↓
Permission
  ↓
Safety
  ↓
Execute
  ↓
Observe
  ↓
Verify
  ↓
Success?
 ├── YES → continue
 └── NO  → recover
```

The execution layer provides retries, timeouts, checkpoints, verification, failure handling, loop detection, execution history, dry-run support and cancellation.

## 🎯 Persistent Work

ATLAS can maintain work beyond a single message:

```text
Project
 └── Goal
      └── Task
           ├── Plan
           ├── State
           ├── Attempts
           ├── Checkpoints
           ├── Evidence
           └── Result
```

This allows missions to pause, resume, recover from failures and maintain progress across sessions.

## ⏰ Background Tasks

The architecture supports long-running work through workers and scheduling:

- One-time jobs
- Delayed jobs
- Recurring jobs
- Conditional jobs
- Background missions
- Persistent queues
- Restart recovery

## 🔌 MCP & Plugins

ATLAS is designed to support standardized external capabilities through MCP and its plugin/skill architecture.

External capabilities should be validated and permissioned rather than automatically trusted.

## 🔐 Safety Model

ATLAS is designed to be powerful without treating every requested action as automatically safe.

```text
SAFE
├── Read files
├── Search
├── Open applications
└── Browse

CONFIRM
├── Edit files
├── Download files
├── Send messages
└── Change settings

DANGEROUS
├── Delete important files
├── Execute unrestricted commands
├── Modify system configuration
└── Other high-impact actions
```

Hard safety boundaries always win. Autonomous missions never bypass required destructive/elevated confirmation.

## ↩️ Recovery & Verification

ATLAS does not treat a successful tool call as proof that the requested result happened.

```text
ACTION
  ↓
OBSERVE
  ↓
VERIFY
  ↓
SUCCESS?
```

When something fails:

```text
Failure
  ↓
Classify
  ↓
Retry
  ↓
Alternative strategy
  ↓
Verify
  ↓
Ask user if blocked
```

Repeated actions are tracked to help prevent infinite loops.

## 🩺 Diagnostics

ATLAS includes diagnostics for checking the local environment and agent configuration.

Example:

```text
atlas doctor

✓ Python
✓ Database
✓ LLM endpoint
✓ Model
✓ Browser
✓ Playwright
✓ Windows UI Automation
⚠ OCR unavailable
⚠ Vision model unavailable
```

## 🖥️ Interfaces

ATLAS supports a CLI-oriented workflow and a graphical interface under active development.

Useful commands include:

```text
/help
/status
/doctor
```

The UI can expose safe execution information such as:

```text
ATLAS
━━━━━━━━━━━━━━━━━━━━
🧠 Processing request
🔧 Using browser.navigate
🌐 Opening page
✓ Verified
━━━━━━━━━━━━━━━━━━━━
Task complete
```

ATLAS exposes actions and results, not private chain-of-thought.

## 🧪 Testing

ATLAS has an automated test suite covering areas including:

- Automation and computer control
- Tool dispatch
- Brain/provider behavior
- Routing
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

## 📁 Project Structure

```text
ATLAS/
├── core/              # Routing, providers, safety, permissions, execution
├── brain/             # LLM intelligence and context interfaces
├── planner/           # Mission planning, verification and recovery
├── tools/             # Discoverable tool integrations
├── skills/            # Drop-in ATLAS skills
├── memory/            # Persistent memory and retrieval
├── automation/        # Computer/clipboard/accessibility automation
├── browser/           # Browser automation and sessions
├── vision/            # Screen understanding and OCR/vision helpers
├── voice/             # Voice configuration and hardware support
├── agents/            # Specialized agent/delegation support
├── missions/          # Persistent projects, goals and tasks
├── interface/         # GUI and settings UI
├── tests/             # Automated test suite
└── .github/workflows/ # CI
```

## 🗺️ Roadmap

### Phase 1: Foundation

- [x] Persistent agent state
- [x] Goal management
- [x] Experience-based learning
- [x] Self-evaluation
- [x] Adaptive strategy selection
- [x] Safety and permissions
- [x] Execution pipeline
- [x] Verification and recovery
- [x] Skills and plugins

### Phase 2: Computer Agent

- [x] Application discovery
- [x] Application launching
- [x] Desktop interaction
- [x] Windows Accessibility integration
- [ ] Complete observe → act → verify computer loop
- [ ] Stronger vision/OCR integration

### Phase 3: Agent Intelligence

- [ ] Full LLM intent router
- [ ] Structured planner
- [ ] Dynamic replanning
- [ ] Hybrid semantic/keyword memory retrieval
- [ ] Context compression
- [ ] Advanced stuck detection
- [ ] Advanced recovery strategies

### Phase 4: Persistent Agent

- [ ] Project/task hierarchy
- [ ] Persistent background workers
- [ ] Scheduler
- [ ] Mission restart recovery
- [ ] Long-running autonomous work

### Phase 5: Ecosystem

- [ ] MCP client
- [ ] Advanced skill lifecycle
- [ ] Plugin SDK
- [ ] Subagents
- [ ] Agent delegation
- [ ] External communication channels

### Phase 6: Polish

- [ ] Mission dashboard
- [ ] Activity tracing
- [ ] Advanced diagnostics
- [ ] Performance optimization
- [ ] Expanded end-to-end testing
- [ ] Polished desktop packaging

## 🌱 Open-Source Inspiration & Thanks

ATLAS is part of a much larger open-source AI-agent ecosystem.

Several projects have provided useful ideas and inspiration while developing ATLAS:

- **Hearth** — desktop automation, Windows interaction, browser capabilities and local-agent architecture.
- **Alfred** — intent routing, tool selection, skills, memory, browser sessions and agent orchestration.
- **Felix** — agent runtime architecture, memory retrieval, skills, subagents and provider abstraction.
- **xopc** — persistent projects, tasks, workflows, long-running work and durable agent state.
- **Monaw** — local agent infrastructure, sandboxing, scheduled tasks, MCP integration and operational security concepts.
- **OpenAgent** — agent workflows, retrieval, orchestration and user-visible execution concepts.
- **The open-source MCP ecosystem** — standardized tool and integration interfaces.

ATLAS does **not** claim ownership of these projects. Where source code is reused, ATLAS follows the applicable project's license and preserves required copyright, license, attribution and NOTICE information.

Some projects are used only for architectural research because their licenses do not permit the type of code reuse ATLAS requires.

A huge thank-you to the developers who make their work available to the open-source community. 🛠️

See `THIRD_PARTY.md` for project-specific licensing notes.

## 🔒 Privacy

ATLAS is designed with local-first operation in mind. Depending on configuration, data can include conversation context, memory, mission state, tool results, local file metadata and application information.

Users should review their model-provider configuration before sending sensitive information to external services.

Credentials and secrets should never be exposed to the LLM unnecessarily.

## ⚡ Quick Start

### Requirements

Typical requirements include:

- Windows
- Python
- An OpenAI-compatible LLM endpoint
- A configured model
- SQLite
- Optional browser/automation dependencies

### Start ATLAS

```powershell
python main.py
```

or, depending on your installation:

```powershell
atlas
```

The LLM layer can use a local provider such as LM Studio when configured. Some capabilities, including Spotify, vision models, OCR and voice, require their corresponding external credentials, models or hardware.

## 🧭 Philosophy

ATLAS follows a few simple principles:

### 1. Local-first

Keep computation and data local whenever practical.

### 2. Modular

Every subsystem should have one clear responsibility.

### 3. Deterministic when possible

Don't ask an LLM to solve a problem that a reliable program can solve directly.

### 4. Intelligent when necessary

Use the model for language understanding, planning, interpretation and decisions where deterministic rules aren't enough.

### 5. Safe by default

High-impact actions require appropriate permission.

### 6. Observable

Users should know what ATLAS is doing.

### 7. Recoverable

Failures should produce recovery attempts, not silent chaos.

### 8. Extensible

New capabilities should be installable without rewriting the core.

### 9. Verifiable

ATLAS should check whether its actions actually worked.

### 10. No God Objects

No single file should own the entire agent.

Especially not:

```text
brain.py
```

😂

## 🚀 Vision

The long-term goal is not to create another chatbot.

The goal is to create a **general-purpose local computer agent** that can:

```text
Understand what you mean
        ↓
Figure out what needs to happen
        ↓
Make a plan
        ↓
Ask permission when necessary
        ↓
Use the computer
        ↓
Observe what happened
        ↓
Verify the result
        ↓
Recover when things fail
        ↓
Remember useful information
        ↓
Continue working
```

ATLAS should feel less like a chat window and more like a **capable local computer companion**.

---

**ATLAS**  
*Local intelligence. Real tools. Actual agency.* 🤖