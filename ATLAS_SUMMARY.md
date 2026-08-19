# ATLAS v1 Build Summary

## Objective
- Build out and harden the ATLAS local desktop assistant (C:\Users\tbn\ATLAS) toward "Level 10" readiness. Current overall rating: **8.2/10** with **191 tests passing**.
- User's prioritized ATLAS v1 roadmap (their order): **Browser → Skills → Persistent goals/state → Nodes → Multi-agent → Communication**. They added *Long-term agent state* (facts/conversations/preferences/past actions/successful+failed strategies/active goals) as the key missing piece that ties everything together.

## Autonomy & Learning Layer (NEW)
Built on the "long-term agent state" foundation. **253 tests passing.**

- **Persistent agent state** — `memory/state.py` `AgentStateStore`: SQLite key/value store (JSON values) for ATLAS-owned state that must survive restarts: counters, flags, and checkpointed mission plans (`mission.plan:<goal_id>`).
- **Autonomous goal management** — `memory/goals.py` `GoalManager`: durable goals with status lifecycle (active/paused/blocked/done/abandoned), priority, progress, parent/child, dedupe-by-title, and `pick_next()` that picks highest priority then least-recently-advanced (round-robin, no starvation).
- **Experience-based learning** — `memory/experience.py` `ExperienceStore`: per `(task_type, strategy_key)` success running-averages + run counts; `best_strategy()` returns the proven tool/approach; lessons distilled as `lesson`-category memories so they surface in model context automatically.
- **Self-evaluation** — `planner/evaluator.py` `SelfEvaluator`: verdict (success/partial/failed), 0..1 score, issues, optional LLM recommendation with heuristic fallback, and persisted lessons.
- **Adaptive strategy selection** — `planner/strategies.py` `StrategySelector`: classifies goals into task types (file/web/browser/automation/email/media/system/vision/minecraft/general) and injects a "Strategy hint" into the planner prompt, preferring proven strategies above a success threshold.
- **AutonomyController** — `core/autonomy.py`: orchestrates plan → execute → evaluate → learn → persist goal/plan for `/auto` (`consent="user"`) and background advancement (`consent="agent"`); restarts resume checkpointed plans via `create_plan_from_steps`.
- **Background goal service** — `services/goal_service.py`: optional threaded loop (config `autonomy_enabled`) that advances the next active goal up to `autonomy_max_tasks_per_cycle` steps. **Safety:** runs only when enabled; never auto-approves destructive/elevated steps (parks goal as `blocked` awaiting user confirmation); hard safety boundaries always win.
- **Router/UX** — `/auto <goal>` now creates a persistent, self-evaluated mission; new commands: `/goals` (list), `/goals add|done|pause|resume|abandon|priority|next`, `/lessons`, `/state`; `/status` and `/debug` report autonomy stats. Daily briefing includes active tracked goals.
- **Planner** — strategy-hint injection, `consent` gating, `create_plan_from_steps` for checkpoint resume, and permission/safety denials no longer retried (deterministic failures fail fast).

## Important Details
- Rating scale: **higher = better** (10 = excellent).
- User said "everything" / "yes start with it" → wants full implementation, not just advice.
- Environment: Windows 11, Python 3.12, LM Studio endpoint `http://localhost:1234/v1`. pyautogui + pygetwindow installed. **Playwright now installed** + Chromium browser downloaded (191MB). Tesseract OCR NOT installed; vision model NOT loaded; `mss` NOT installed (screenshots disabled).
- Brain client timeout `10s`/`max_retries=0`; provider client timeout `15s`/`max_retries=0` (fail-fast when LM Studio down). Provider client timeout set to `15s` with `max_retries=0`.
- Destructive actions require explicit "yes/confirm"; autonomous `/auto` acts without confirmation by design.
- Browser actions are gated at `basic` permission level — hard-safety boundaries + explicit `deny` rules enforced, but NO per-action prompt, so the agent can operate sites autonomously. (Judgment call: prompting for every navigate/click would break autonomous "operate websites" capability.)

## Work State
### Completed
- **Browser Agent (NEW, #1 priority)** — `tools/browser_tool.py` using Playwright (sync API, lazy-launched Chromium, headless default). Actions: `navigate, click, type, fill, scroll, back, forward, reload, get_text, get_html, get_links, eval_js, screenshot, wait_for, status, close`. Each action has built-in verification (element visible, navigation complete, load state). Structured result `{success, data, error, screenshot_path}` rendered to text. Text/selector fallback resolution (`text=...` when CSS misses).
- **Session persistence** — cookies + localStorage saved to `~/.atlas/browser/storage.json` on navigate/click/type, restored on launch (login sessions survive restarts). Screenshots saved to `~/.atlas/browser/screenshots/`.
- **Router integration** — `_browser_request()` + `_build_browser_args()` (parses "browser navigate to X", "click on Y", "browser type SEL with TEXT", "fill SEL with TEXT", "scroll up/down N", "browser status", "read the page", "close browser"). Wired into `_dispatch_tool` (before email/web), `/browser` help + `/browser <cmd>` command, and `_TOOL_TRIGGER_PHRASES`. Gated via `_authorize("browser", action, basic)`.
- **Brain refactored**: `_call_provider()` / `_call_provider_stream()` extracted (was 5 duplicate try/except).
- **Permission layer** (`core/permissions.py`): allow/ask/deny, destructive registry, pre-auth.
- **Hard safety** (`core/safety.py`): protected dirs, forbidden actions, db guard; enforced in router + planner; deny beats allow.
- **Undo** (`core/undo.py`): file deletes → trash + undo; clipboard records previous.
- **Memory retrieval**: `database.retrieve()` blended scoring; `facts.retrieve()` delegates; `brain._memory_context()` uses it.
- **Planner**: `_verify_task()`, `_recover_task()`, `run_plan()`, `run_mission()` with verdict counts.
- **Spotify**: `core/spotify_auth.py` (OAuth) + `tools/spotify_tool.py`; router `spotify` commands.
- **Web retry/backoff** (`_open_with_retry`), **email robustness** (SSL/regex/attachments), **media cross-platform** keys, **voice hardware test**, **vision understand**, **skills drop-in** (`core/skills.py`), **observability** (`/debug` + call log + trace).
- **Tests: 191 passing** (was 164 → +27 browser): `test_browser_tool.py` (19, full mock coverage), `test_router_browser.py` (8, parse + dispatch + deny + unloaded). Real end-to-end smoke test against example.com passed (navigate, get_text, status, close).

### Blocked
- `mss` not installed → `/screen`, `/vision`, screenshots disabled at runtime (browser screenshots work independently via Playwright).
- No vision model loaded → image descriptions unavailable.
- No Spotify credentials → Spotify returns "not authenticated".
- No Tesseract OCR → OCR fallback returns empty.
- No mic + Whisper → Voice E2E not testable (pipeline mocked).

## Next Move
1. **#2 Skill packaging** (user's next priority): package skills as folders (`skills/spotify/`, `skills/minecraft/`, `skills/browser/`, `skills/coding/`) declaring `name, version, dependencies, permissions, triggers, tools`. Add sandboxing before allowing third-party skills.
2. **#3 Persistent goals/state** layer (the key glue): extend memory with past actions, successful/failed strategies, active goals so "finish that thing from yesterday" works across sessions.
3. **#4 Device/node system**: auth, authz, encrypted transport on top of existing event manager.
4. Postpone multi-agent (#5) and communication channels (#6) per user's explicit ordering.
5. Install `mss` + load vision model to close environment gaps.

## Relevant Files
- `tools/browser_tool.py` — NEW. Playwright browser automation, 16 actions, session persistence, structured results.
- `core/router.py` — `_browser_request`, `_build_browser_args`, `/browser` command, browser trigger phrases, basic-level gate.
- `tools/web_tool.py` — research/fetch (unchanged, still used for "search web").
- `core/permissions.py` — PermissionManager (browser gated basic).
- `core/safety.py` — HardSafety (browser navigate still subject to hard-safety check).
- `tests/test_browser_tool.py` — 19 tests (mocked Playwright).
- `tests/test_router_browser.py` — 8 tests (parse/dispatch/deny/unloaded).
- `tools/registry.py` — auto-discovers BrowserTool on import.
