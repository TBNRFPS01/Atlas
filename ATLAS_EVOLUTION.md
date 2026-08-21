# ATLAS Evolution Roadmap

ATLAS has reached the point where the goal is no longer simply adding more tools. The next stage is turning ATLAS into a **personal agent runtime**: a system that can understand goals, plan work, use capabilities, operate across devices, learn from outcomes, and know when it needs the user.

## North Star

> Give ATLAS a goal, not a sequence of button presses.

ATLAS should be able to:

1. Understand the user's intent and constraints.
2. Build and execute a plan using available capabilities.
3. Observe the result of each important action.
4. Verify success instead of assuming it.
5. Recover or re-plan when something fails.
6. Persist useful context across restarts.
7. Learn which strategies work for different task types.
8. Ask the user only when authority, ambiguity, credentials, or safety requires it.
9. Report what it did and why.

## 1. Long-term Agent Context

Continue expanding persistent state beyond simple facts and conversations.

- Active projects and missions
- Unfinished work and checkpoints
- Past actions and outcomes
- Successful and failed strategies
- User preferences and constraints
- Relationships between projects, goals, and resources
- Reliable resume-after-restart behavior
- Explicit correction and forgetting of stale information

**Goal:** requests such as `finish that thing from yesterday` should become normal ATLAS operations when the required context exists.

## 2. Packaged Skills

Move capabilities toward a drop-in skill architecture.

Each skill should declare:

- name and version
- dependencies
- permissions
- triggers/intents
- tools/actions
- configuration
- health/status information

Initial packaged skills:

- browser
- Spotify
- files
- system
- coding
- Minecraft

Third-party skills must be validated and sandboxed before execution.

**Goal:** adding a capability should not require rewriting the ATLAS core.

## 3. Nodes / Device Runtime

Extend ATLAS from a single-machine assistant into a trusted multi-device runtime.

A node should have:

- stable identity
- authentication and authorization
- encrypted transport
- capability discovery
- health/status
- task routing
- revocation

Example topology:

```text
                 ATLAS
                   |
        +----------+----------+
        |          |          |
      ZBook       iPad      Desktop
      brain       UI       GPU/work
```

The runtime should select a node based on capability, availability, permissions, and task requirements.

## 4. Perception

Unify tool results with visual and environmental state.

- Screenshots
- OCR
- Vision model analysis
- Window/application state
- Browser DOM/state
- Tool output
- Change detection

ATLAS should distinguish between **"I issued the action"** and **"the intended state was actually reached."**

## 5. Autonomous Missions

Keep the existing plan → execute → evaluate → learn loop and push it toward robust long-running missions.

- Checkpoint every meaningful stage
- Resume after restart
- Detect blocked states
- Re-plan instead of repeating failed actions
- Schedule/background execution
- Deadline awareness
- Progress reporting
- User escalation when authority or missing information is required

Safety and explicit user authority always override autonomy.

## 6. Trust Layer

Make ATLAS safe enough that users can delegate meaningful work.

- Least-privilege permissions
- Explicit destructive-action confirmation
- Hard safety boundaries
- Reversible operations where possible
- Complete action/audit traces
- Credential isolation
- Per-skill permissions
- Per-node permissions
- Clear explanation of blocked actions

**Goal:** the user should be able to say `handle it` without wondering what ATLAS might accidentally destroy.

## 7. Communication Surface

Eventually expose the same ATLAS runtime through multiple interfaces without duplicating the agent logic.

- Desktop UI
- CLI
- Voice
- Local web UI
- iPad/mobile node
- Notifications

The interface is a client. **ATLAS itself remains the runtime.**

## 8. Future: Multi-agent Execution

Only after skills, state, nodes, and trust are mature.

Potential roles:

- planner
- researcher
- executor
- verifier
- specialist agents

Agents should share controlled state and permissions rather than receiving unrestricted access.

## Implementation Order

1. **Skills packaging + sandboxing**
2. **Strengthen long-term state and mission resume**
3. **Node identity/authentication/transport**
4. **Perception integration**
5. **Long-running autonomous missions**
6. **Unified communication clients, including iPad**
7. **Multi-agent execution**

## Definition of "ATLAS is mature"

ATLAS is mature when a user can give it a meaningful goal, leave it alone, and return to a trustworthy explanation of what happened:

```text
Goal
  ↓
Understand
  ↓
Plan
  ↓
Choose skills + node
  ↓
Execute
  ↓
Observe
  ↓
Verify
  ↓
Recover / re-plan if needed
  ↓
Persist outcome + learn
  ↓
Report / escalate only when necessary
```

The objective is **capability with control**, not maximum autonomy for its own sake.
