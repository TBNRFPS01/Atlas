# ATLAS v2 Technical Audit

**Date:** 2026-08-05
**Auditor:** Senior Engineer
**Status:** Complete

---

## 1. Architecture Overview

ATLAS v2 is a modular local desktop AI assistant built around the OpenAI SDK and LM Studio. The architecture follows a layered design:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         main.py (CLI entry)                       │
├──────────────┬──────────────┬──────────────┬──────────────────────┤
│   core/      │   memory/    │   tools/     │   services/          │
│  Brain       │  FactStore   │  Registry    │  EventManager        │
│  Router      │  MemoryDB    │  Tool (ABC)  │  HealthMonitor       │
│  Personality │              │  SystemTool  │  PluginManager       │
│  EventBus    │              │  FileTool    │  ProviderMonitor     │
│  PluginLoader│              │  WebTool     │  VoiceService        │
├──────────────┼──────────────┼──────────────┼──────────────────────┤
│  planner/    │  automation/ │  vision/     │  voice/              │
│  Planner     │  Keyboard    │  Screenshot  │  Microphone          │
│  Task        │  Mouse       │  OCR         │  Listener            │
│              │  Windows     │  Camera      │  Speaker             │
│              │  Process     │  Analyzer    │  Controller          │
│              │  Clipboard   │              │                      │
└──────────────┴──────────────┴──────────────┴──────────────────────┘
```

### Module Connections

| Source | Destination | Purpose |
|--------|-------------|---------|
| `main.py` | `Brain` | LLM communication |
| `main.py` | `Router` | Request routing |
| `main.py` | `FactStore` | Memory storage |
| `main.py` | `ToolRegistry` | Tool discovery |
| `main.py` | `PluginManager` | Plugin loading |
| `main.py` | `VoiceController` | Optional voice input/output |
| `Router` | `Brain` | Ask/stream chat completion |
| `Router` | `FactStore` | Memory CRUD |
| `Router` | Hard-coded tools | System/file/web/minecraft dispatch |
| `Brain` | `FactStore` | Auto-extract memories from conversation |
| `Brain` | OpenAI client | LM Studio endpoint (`http://localhost:1234/v1`) |
| `Planner` | `Router` | Task execution via routing |
| `Planner` | `ToolRegistry` | Tool execution (limited) |
| `VoiceController` | `Microphone` | Record audio |
| `VoiceController` | `Listener` | Transcribe speech (faster-whisper) |
| `VoiceController` | `Router` | Send transcribed text |
| `VoiceController` | `Speaker` | Play TTS responses (pyttsx3) |

**Key Finding:** The Router bypasses ToolRegistry entirely — tools discovered via registry are never used in the main routing path. This is a major architectural defect.

---

## 2. Implemented Features

| Feature | Status | Notes |
|---------|--------|-------|
| CLI chat interface | ✅ Working | Basic REPL with streaming |
| LM Studio integration | ✅ Working | Uses OpenAI SDK, local endpoint |
| Conversation history | ✅ Working | In-memory with size limit (60 messages) |
| Memory (SQLite) | ✅ Working | Key-value with categories, importance, keyword search |
| Auto-memory extraction | ⚠️ Buggy | Regex pattern recall logic is broken |
| Tool system | ⚠️ Partial | Registry works but not integrated with Router |
| File tool | ⚠️ Partial | Reads only, no write/organization |
| System info tool | ✅ Working | Basic hardware info |
| Web tool | ❌ Stub | No real search/fetch |
| Minecraft tool | ❌ Stub | No real integration |
| Planner | ⚠️ Basic | Rule-based decomposition only (5 keywords) |
| Automation (keyboard/mouse) | ✅ Working | pyautogui wrapper |
| Window management | ✅ Working | pygetwindow + psutil |
| Process management | ✅ Working | psutil wrapper |
| Clipboard | ✅ Working | pyautogui clipboard |
| Vision (screenshot) | ✅ Working | mss + numpy |
| Vision (OCR) | ⚠️ Partial | Tesseract wrapper, requires system install |
| Vision (camera) | ✅ Working | OpenCV wrapper |
| Vision (LLM analysis) | ❌ Not implemented | Stub only; requires vision-capable model |
| Voice (speech-to-text) | ✅ Working | faster-whisper (local) |
| Voice (text-to-speech) | ✅ Working | pyttsx3 (offline) |
| Voice (push-to-talk) | ⚠️ Windows-only | Uses ctypes.windll (not cross-platform) |
| Plugins | ⚠️ Scaffold | Discovery works, no runtime integration |
| Health monitoring | ⚠️ Buggy | Missing `Callable` import |
| Config management | ✅ Working | JSON + env var overrides (not fully integrated) |
| Event bus | ✅ Working | Simple pub/sub |
| Tests | ⚠️ Sparse | Basic smoke tests only |
| GUI | ❌ Stub | `interface/gui.py` is a placeholder |

---

## 3. Critical Bugs & Broken Logic

### 3.1 Memory Extraction Broken (HIGH)
**File:** `core/brain.py:160-164`

```python
existing = self.memory_store.recall(key)  # key is the regex pattern string
if not existing:
    self.memory_store.remember(key, value)
```

`recall(key)` does `WHERE content LIKE '{key}=%'`. But `content` stores the extracted value, not the regex pattern. The regex pattern `\bmy name is\s+([A-Za-z]+)` stored as key means the SQL LIKE will never match.

**Result:** Auto-memory extraction never updates existing memories; creates duplicates every time. Memory bloat is guaranteed.

**Fix:** Use category-based recall or store the key as a separate column.

---

### 3.2 Router Bypasses ToolRegistry (HIGH)
**File:** `core/router.py:144-165`

`_dispatch_tool()` hard-codes imports:

```python
if "system" in lowered:
    from tools.system import get_system_info
    return get_system_info()
elif "file" in lowered:
    from tools.file_tool import FileTool
    return FileTool().describe()
# etc.
```

**Result:** Tools discovered via `ToolRegistry.discover()` are never used. New tools cannot be added without modifying `_dispatch_tool()`.

**Fix:** Refactor to use `ToolRegistry.get()` and pattern matching from metadata.

---

### 3.3 HealthMonitor Missing Import (HIGH)
**File:** `services/health_monitor.py:17`

```python
self._checks: dict[str, Callable[[], bool]] = {}
```

`Callable` is used but never imported. `from typing import Callable` is missing.

**Result:** `NameError: name 'Callable' is not defined` at runtime.

**Fix:** Add `from typing import Callable`.

---

### 3.4 ConfigManager Not Passed to Brain (MEDIUM)
**File:** `main.py:47`

```python
brain = Brain()  # No config passed
```

`Brain` reads only from env vars (`LM_STUDIO_*`). The `config.json` values for model, temperature, max_tokens, history_size are ignored. Only used for startup screen display.

**Result:** User settings in `config.json` don't affect LLM behavior.

**Fix:** Pass `ConfigManager` to `Brain` and use its values.

---

### 3.5 Brain.stream Logic Confusion (LOW)
**File:** `core/brain.py:66`

`Brain.stream` is a bool set in `__init__`. In `main.py:83`, it checks `brain.stream`. In `Router.stream`, it checks `self.brain.stream`. The Router's `stream` method only streams for plain chat prompts (not commands/memory/tools). But the `stream` param is never passed from main, so it uses the default `True`.

**Result:** Works but inconsistent and misleading.

**Fix:** Unify streaming behavior or remove redundancy.

---

### 3.6 Voice Push-to-Talk Windows-Only (MEDIUM)
**File:** `voice/controller.py:117-124`

```python
def _is_push_to_talk_down(self) -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(key_code) & 0x8000)
```

`ctypes.windll` only exists on Windows. On Linux/macOS this fails (imported but not guarded).

**Result:** Voice controller crashes on non-Windows systems.

**Fix:** Guard with `if sys.platform == "win32"` and provide fallback (e.g., keyboard module).

---

### 3.7 FileTool Only Reads (MEDIUM)
**File:** `tools/file_tool.py:15-17`

```python
def execute(self, *args, **kwargs) -> str:
    path = args[0] if args else ""
    return Path(path).read_text(encoding="utf-8") if path else "No path provided."
```

Description says "Read, write, and organize files." But only reads. No write, no organization.

**Result:** Users cannot create or modify files via ATLAS.

**Fix:** Implement write/append/delete methods in `FileTool`.

---

### 3.8 Planner Decomposition is Rule-Based (MEDIUM)
**File:** `planner/planner.py:38-54`

`_decompose()` matches only 5 keywords: "open", "type", "click", "screenshot", "search". Everything else becomes `["Process goal: {goal}"]`.

**Result:** No LLM-based decomposition, no multi-step plans beyond one task.

**Fix:** Use `Brain.ask()` to decompose goals via LLM.

---

### 3.9 Missing Dependency Manifest (HIGH)
No `requirements.txt` or `pyproject.toml`. Project dependencies are implicit from imports.

**Result:** Fresh installs fail. Users must guess dependencies.

**Fix:** Create `requirements.txt` with pinned versions.

---

### 3.10 Duplicate Tool Implementations (LOW)

| Function-based | Class-based |
|----------------|-------------|
| `tools/system.py` | `tools/system_tool.py` |
| `tools/web.py` | `tools/web_tool.py` |
| `tools/files.py` | `tools/file_tool.py` |

Router uses the function versions; ToolRegistry uses the class versions. They overlap and diverge.

**Fix:** Merge into class-based tools only and update Router.

---

## 4. Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Memory extraction creates duplicates | Memory bloat, unreliable recall | High (on every user message) | Fix `recall` logic |
| Router bypasses tool registry | New tools never route to users | High (no extensibility) | Refactor Router |
| Missing imports cause crashes | `HealthMonitor` unusable | High (import error on startup) | Add `from typing import Callable` |
| Config ignored | User settings don't apply | Medium (env vars still work) | Pass `ConfigManager` to `Brain` |
| Voice crashes on non-Windows | Linux/macOS users can't use voice | Medium | Guard with `if sys.platform == "win32"` |
| No dependency manifest | Hard to install/reproduce | Medium | Add `requirements.txt` |
| FileTool writes missing | User can't create/modify files | Medium | Implement write/append/delete |
| Planner stuck on simple rules | Complex goals fail | Low (only used for automation) | Add LLM-based decomposition |

---

## 5. Project Structure Scalability

### Strengths
- Clear separation of concerns (core, memory, tools, services, etc.)
- Abstract base class for tools (`Tool`) with metadata
- Plugin discovery system (scaffold)
- Config manager with environment overrides
- Event bus for pub/sub
- Modular design allows independent development

### Weaknesses
- Router is a monolith (194 lines) with hard-coded logic
- ToolRegistry exists but Router doesn't use it
- Plugin system doesn't integrate with runtime
- No clear boundaries between "core" and "services"
- Tests are minimal and don't cover edge cases
- No type safety beyond Python 3.12 features (no mypy/pyright)
- `__init__.py` files are empty in most modules

### Scalability Recommendation
Refactor Router to use a plugin-based dispatch system where tools register their own route patterns. This would allow new tools to be added without modifying Router code.

---

## 6. Dependencies & Missing Packages

### Required Dependencies (Implicit from Imports)

| Package | Usage |
|---------|-------|
| `openai>=1.0.0` | LLM client |
| `numpy` | Audio/vision data |
| `sounddevice` | Microphone recording |
| `faster-whisper` | Speech-to-text |
| `pyttsx3` | Text-to-speech |
| `pyautogui` | Keyboard/mouse/clipboard automation |
| `psutil` | Process management |
| `pygetwindow` | Window management |
| `mss` | Screenshot capture |
| `opencv-python` | Camera/vision |
| `pytesseract` | OCR |
| `Pillow` | Image handling |
| `soundfile` | Audio file I/O (optional) |

### Missing
- No `requirements.txt` or `pyproject.toml`
- No installation instructions
- No version pins — may break with newer releases

### Recommendations
1. Create `requirements.txt` with pinned versions
2. Create `pyproject.toml` for modern packaging
3. Add `setup.py` for editable install (`pip install -e .`)
4. Document required system dependencies (Tesseract-OCR, etc.)

---

## 7. What Is Ready for v1

| Component | Ready? | Notes |
|-----------|--------|-------|
| CLI conversation | ✅ | Works with LM Studio local endpoint |
| Memory (manual) | ✅ | `remember`, `recall`, `forget`, `search` commands work |
| System info | ✅ | `/status`, `/tools` commands |
| File reading | ✅ | Basic file read (but not via proper tool routing) |
| Automation primitives | ✅ | Keyboard, mouse, windows, process, clipboard |
| Screenshot capture | ✅ | mss-based capture |
| Voice (offline) | ✅ | Whisper + TTS (on Windows) |
| Config loading | ✅ | Reads `config.json` (but not applied to all components) |
| Modular structure | ✅ | Clean separation of modules |
| Event bus | ✅ | Simple pub/sub working |

**These can ship as v1** with the understanding that voice is Windows-only and memory extraction is manual.

---

## 8. What Should Be Delayed Until v2

| Component | Reason |
|-----------|--------|
| Vision LLM analysis | Requires vision-capable model (not in local LM Studio typically) |
| Web search | Requires API key (Google/Bing) or scraping infrastructure |
| Full plugin ecosystem | Need plugin SDK, isolation, security model |
| GUI | Complex UI work; CLI is sufficient for v1 |
| Multi-provider support | OpenRouter, Ollama, etc. — scope creep for v1 |
| Advanced planner (LLM-based) | Needs better prompt engineering and task decomposition |
| Push-to-talk on Linux/macOS | Need cross-platform hotkey library |
| Memory consolidation | Background thread + algorithm refinement |
| Telemetry/analytics | Privacy and user opt-in decisions |
| Cross-platform voice | Requires different backends per OS |

---

## 9. Prioritized Roadmap

### Phase 1: Critical Fixes (Week 1)

| Priority | Task | File(s) | Effort |
|----------|------|---------|--------|
| P0 | Fix memory extraction recall logic | `core/brain.py` | 2h |
| P0 | Add missing `Callable` import | `services/health_monitor.py` | 5m |
| P0 | Create `requirements.txt` | Root | 1h |
| P0 | Guard Windows-specific voice code | `voice/controller.py` | 1h |

**Deliverable:** ATLAS runs without crashing on all platforms and memory doesn't bloat.

---

### Phase 2: Router & Tool Integration (Week 2)

| Priority | Task | File(s) | Effort |
|----------|------|---------|--------|
| P1 | Refactor Router to use `ToolRegistry` | `core/router.py`, `tools/registry.py` | 4h |
| P1 | Add `Router.register_tool()` method | `core/router.py` | 1h |
| P1 | Remove hard-coded tool dispatch | `core/router.py` | 1h |
| P1 | Merge duplicate tool files | `tools/*.py` | 2h |

**Deliverable:** Router uses ToolRegistry; new tools can be added without code changes.

---

### Phase 3: Core Stability (Week 3)

| Priority | Task | File(s) | Effort |
|----------|------|---------|--------|
| P2 | Pass `ConfigManager` to `Brain` | `main.py`, `core/brain.py` | 2h |
| P2 | Implement `FileTool.write()` | `tools/file_tool.py` | 2h |
| P2 | Add proper error handling for missing deps | All modules with optional imports | 3h |
| P2 | Add `--debug` flag with verbose logging | `main.py`, `utils/logger.py` | 2h |

**Deliverable:** Config works as expected; file tool supports write; debug mode available.

---

### Phase 4: Feature Expansion (Week 4-5)

| Priority | Task | File(s) | Effort |
|----------|------|---------|--------|
| P3 | Add LLM-based planner decomposition | `planner/planner.py` | 4h |
| P3 | Implement web search (DuckDuckGo or custom) | `tools/web_tool.py` | 4h |
| P3 | Add memory consolidation and cleanup | `memory/database.py`, `services/memory_cleanup.py` | 3h |
| P3 | Expand test coverage (unit + integration) | `tests/` | 6h |

**Deliverable:** Planner handles complex goals; web tool works; memory self-maintains.

---

### Phase 5: Polish & Release (Week 6)

| Priority | Task | File(s) | Effort |
|----------|------|---------|--------|
| P4 | Create `pyproject.toml` with entry points | Root | 2h |
| P4 | Add `--install-deps` or `setup.py` | Root | 1h |
| P4 | Documentation (user guide, API reference) | `docs/` | 6h |
| P4 | Version bump and tag | Root | 30m |

**Deliverable:** ATLAS v1.0 released with proper packaging and documentation.

---

## 10. Summary

ATLAS v2 has a **strong modular foundation** with many features already implemented (conversation, memory, tools, voice, automation, vision, planner). The CLI works today with LM Studio.

### Critical Blockers for v1

1. **Memory extraction duplicates facts** (broken recall logic) — P0
2. **Router ignores ToolRegistry** (tools never route) — P0
3. **Missing `Callable` import** crashes HealthMonitor — P0
4. **Voice controller uses Windows-only APIs** — P0

### Recommendation

Fix Phase 1 and Phase 2 issues immediately, then ship v1.0 with the understanding that advanced features (vision, web, plugins, GUI) are v2.

---

## Appendix A: File Inventory

### Core (`core/`)
- `brain.py` — LLM wrapper, memory extraction, streaming
- `router.py` — Request routing, command parsing, memory ops
- `personality.py` — ATLAS persona definition
- `events.py` — Event bus
- `logging_utils.py` — Basic logger setup
- `plugins.py` — Plugin loader (scaffold)

### Memory (`memory/`)
- `facts.py` — FactStore wrapper
- `database.py` — SQLite memory engine with categories

### Tools (`tools/`)
- `base.py` — Tool ABC and ToolMetadata
- `registry.py` — ToolRegistry with auto-discovery
- `system.py` / `system_tool.py` — System info (duplicate)
- `files.py` / `file_tool.py` — File ops (duplicate)
- `web.py` / `web_tool.py` — Web stub (duplicate)
- `minecraft.py` — Minecraft stub

### Planner (`planner/`)
- `planner.py` — Goal decomposition, task execution
- `task.py` — Task model with status and retry logic

### Automation (`automation/`)
- `keyboard.py` — Keyboard simulation
- `mouse.py` — Mouse control
- `windows.py` — Window management
- `process.py` — Process management
- `clipboard.py` — Clipboard operations

### Vision (`vision/`)
- `screenshot.py` — Screen capture
- `ocr.py` — Tesseract OCR wrapper
- `camera.py` — Webcam capture
- `analyzer.py` — LLM vision stub

### Voice (`voice/`)
- `microphone.py` — sounddevice recorder
- `listener.py` — faster-whisper STT
- `speaker.py` — pyttsx3 TTS
- `controller.py` — Push-to-talk coordinator
- `config.py` — Voice constants

### Services (`services/`)
- `event_manager.py` — Thread-safe event bus
- `health_monitor.py` — Component health (buggy)
- `plugin_manager.py` — Plugin lifecycle (scaffold)
- `provider_monitor.py` — LLM provider availability
- `memory_cleanup.py` — Background cleanup
- `voice_service.py` — Voice background service

### Config (`config/`)
- `manager.py` — ConfigManager with JSON + env

### Utils (`utils/`)
- `logger.py` — Logger setup

### Tests (`tests/`)
- `test_memory.py`, `test_router.py`, `test_brain.py`, `test_tools.py`, `test_config.py`

---

## Appendix B: Configuration Schema

`config.json` currently supports:

```json
{
  "model": "local-model",
  "temperature": 0.7,
  "max_tokens": 512,
  "history_size": 60,
  "voice_enabled": false,
  "memory_enabled": true,
  "debug_mode": true,
  "theme": "dark"
}
```

**Missing from config but used in code:**
- `voice_rate` (default 180)
- `voice_volume` (default 1.0)
- `voice_language` (default "en")
- `whisper_model` (default "tiny")
- `sample_rate` (default 16000)
- `record_seconds` (default 4)
- `push_to_talk_key` (default "F8")
- `vision_enabled` (default false)
- `ocr_enabled` (default false)
- `planner_enabled` (default true)
- `event_log_level` (default "INFO")

---

## Appendix C: Environment Variables

| Variable | Config Key |
|----------|------------|
| `LM_STUDIO_BASE_URL` | `endpoint` |
| `LM_STUDIO_MODEL` | `model` |
| `LM_STUDIO_TEMPERATURE` | `temperature` |
| `LM_STUDIO_MAX_TOKENS` | `max_tokens` |
| `LM_STUDIO_HISTORY_SIZE` | `history_size` |
| `VOICE_ENABLED` | `voice_enabled` |
| `MEMORY_ENABLED` | `memory_enabled` |
| `DEBUG_MODE` | `debug_mode` |
| `THEME` | `theme` |
| `VOICE_RATE` | `voice_rate` |
| `VOICE_VOLUME` | `voice_volume` |
| `VOICE_LANGUAGE` | `voice_language` |
| `WHISPER_MODEL` | `whisper_model` |
| `SAMPLE_RATE` | `sample_rate` |
| `RECORD_SECONDS` | `record_seconds` |
| `PUSH_TO_TALK_KEY` | `push_to_talk_key` |
| `VISION_ENABLED` | `vision_enabled` |
| `OCR_ENABLED` | `ocr_enabled` |
| `PLANNER_ENABLED` | `planner_enabled` |
| `EVENT_LOG_LEVEL` | `event_log_level` |

---

*End of Audit*