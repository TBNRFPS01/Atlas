# ATLAS Evolution Roadmap

ATLAS has reached the point where the goal is no longer simply adding more tools. The next stage is turning ATLAS into a **personal agent runtime**: a system that can understand goals, plan work, use capabilities, operate across devices, learn from outcomes, and know when it needs the user.

## North Star

> Give ATLAS a goal, not a sequence of button presses.

ATLAS should be able to:

1. Understand intent, constraints, authority, and desired outcome.
2. Build and execute a plan using available capabilities.
3. Choose the right skill, tool, and device for each step.
4. Observe the environment and the result of important actions.
5. Verify success instead of assuming it.
6. Recover or re-plan when something fails.
7. Persist useful context across restarts.
8. Learn which strategies work for different task types.
9. Ask the user only when authority, ambiguity, credentials, or safety requires it.
10. Report what it did, what changed, what failed, and what it learned.

## Evolution Stages

### Stage 1: Capable Agent

**Status: largely achieved.**

ATLAS already has the foundations of a capable agent: planning, tool execution, verification/recovery, permissions, hard safety boundaries, memory, browser automation, Spotify, skills infrastructure, observability, and autonomous goal management.

The purpose of this stage is not to endlessly add tools. It is to make existing capabilities reliable.

### Stage 2: Persistent Agent

**Current focus.**

ATLAS should maintain a coherent long-term model of work rather than treating every launch as a fresh conversation.

- Active projects and missions
- Unfinished work and checkpoints
- Past actions and outcomes
- Successful and failed strategies
- User preferences and constraints
- Relationships between projects, goals, resources, and actions
- Reliable resume-after-restart behavior
- Explicit correction and forgetting of stale information
- Provenance and confidence for important memories

**Acceptance examples:**

- `finish that thing from yesterday`
- `what did you change on the Minecraft server?`
- `use the approach that worked last time`

ATLAS should only answer from persisted evidence when the context exists. It should ask instead of inventing missing history.

### Stage 3: Extensible Agent

Move capabilities toward a first-class drop-in skill architecture.

Each skill should declare:

- name and version
- dependencies
- permissions
- triggers/intents
- tools/actions
- configuration schema
- health/status
- compatibility requirements

Initial packaged skills:

- browser
- Spotify
- files
- system
- coding
- Minecraft

Third-party skills must be validated, isolated, and sandboxed before execution.

**Acceptance criterion:** adding a capability should not require rewriting ATLAS core routing or safety logic.

### Stage 4: Perceptive Agent

Unify tool results with actual environmental state.

- Screenshots
- OCR
- Vision model analysis
- Window/application state
- Browser DOM/state
- Tool output
- Change detection
- Before/after state comparison

ATLAS must distinguish:

> `I issued the action.`

from:

> `The intended state was actually reached.`

A failed visual or environmental verification should become a real failure signal that can trigger recovery.

### Stage 5: Trusted Agent

Make delegation safe enough for meaningful work.

- Least-privilege permissions
- Explicit destructive-action confirmation
- Hard safety boundaries
- Reversible operations where possible
- Complete action/audit traces
- Credential isolation
- Per-skill permissions
- Per-node permissions
- Clear explanations for blocked actions
- Session/task authority boundaries
- Emergency stop / autonomy pause

**North-star behavior:**

> User: `handle it.`
>
> ATLAS: handles everything within granted authority, pauses for anything outside it, and explains the boundary.

### Stage 6: Autonomous Agent

Push the existing plan → execute → evaluate → learn loop into robust long-running missions.

- Checkpoint every meaningful stage
- Resume after restart
- Detect blocked states
- Re-plan instead of repeating failed actions
- Background execution
- Deadline awareness
- Progress reporting
- Goal dependencies
- Retry budgets
- Escalation when authority or missing information is required
- Clean completion and post-mission summary

Autonomy should be bounded by explicit policy. Safety and user authority always override autonomous behavior.

### Stage 7: Multi-Device Agent

Extend ATLAS from a single-machine assistant into a trusted node runtime.

A node should have:

- Stable identity
- Authentication and authorization
- Encrypted transport
- Capability discovery
- Health/status
- Task routing
- Revocation
- Local permission policy

Example topology:

```text
                 ATLAS Runtime
                       |
          +------------+------------+
          |            |            |
        ZBook         iPad        Desktop
        brain          UI        GPU/work
```

ATLAS should select a node based on capability, availability, permissions, latency, and task requirements.

The iPad should be a **client/node**, not a second copy of ATLAS logic.

### Stage 8: Unified Interface

Expose the same runtime through multiple clients without duplicating agent logic.

- Desktop UI
- CLI
- Voice
- Local web UI
- iPad/mobile interface
- Notifications
- Future integrations

The interface is a client. **ATLAS remains the runtime.**

This is where the iPad control surface belongs:

```text
📱 iPad
   ↓
Local network / authenticated transport
   ↓
🤖 ATLAS Runtime
   ↓
PC / browser / skills / devices
```

### Stage 9: Proactive Agent

ATLAS should eventually be able to notice useful opportunities without becoming annoying.

- Watch approved conditions
- Detect failures or important changes
- Remind about active goals
- Surface blocked missions
- Prepare useful actions before being asked
- Suggest next steps based on active projects
- Respect quiet hours and notification policy

**Rule:** proactive does not mean intrusive. ATLAS should never manufacture work merely to appear active.

### Stage 10: Multi-Agent Execution

Only after skills, state, perception, nodes, autonomy, and trust are mature.

Potential controlled roles:

- planner
- researcher
- executor
- verifier
- specialist agents

Agents should share controlled state and scoped permissions rather than receiving unrestricted access.

A multi-agent task should still have one accountable mission controller that can stop the entire operation.

### Stage 11: Self-Maintaining Runtime

ATLAS should eventually be able to maintain its own operational health without modifying its safety foundations autonomously.

- Dependency health checks
- Skill health checks
- Provider availability checks
- Configuration validation
- Database integrity checks
- Automatic recovery of safe transient failures
- Diagnostics and repair suggestions
- Version/compatibility awareness
- Safe update proposals

ATLAS may diagnose and prepare changes. High-impact code, security, permission, or policy changes should require explicit approval.

### Stage 12: Agent Platform

The final evolution is not simply a bigger assistant. It is a reusable runtime that can host capabilities, devices, missions, and interfaces.

Core separation:

```text
                 ATLAS Runtime
                       |
       +---------------+---------------+
       |               |               |
    Skills           Nodes          Interfaces
       |               |               |
   tools/actions   devices/apps     CLI/Web/iPad
```

The LLM is the reasoning component. ATLAS owns orchestration, state, permissions, execution, verification, recovery, and accountability.

## Cross-Cutting Requirements

Every stage must preserve these properties:

- **Safety:** deny unsafe actions regardless of model intent.
- **Authority:** actions require the appropriate user/session/node permission.
- **Observability:** important actions produce inspectable traces.
- **Verification:** success is based on observed state, not model confidence alone.
- **Recoverability:** failures should become structured signals, not silent corruption.
- **Persistence:** meaningful progress survives restarts.
- **Privacy:** credentials and sensitive state stay scoped and protected.
- **Testability:** new behavior receives deterministic tests and integration coverage.
- **Graceful degradation:** missing optional dependencies should disable only the affected capability.

## Implementation Order

1. **Strengthen persistent state and mission resume**
2. **Package and sandbox skills**
3. **Integrate unified perception**
4. **Harden autonomous long-running missions**
5. **Build node identity, authorization, and encrypted transport**
6. **Build unified communication clients, including the iPad**
7. **Add proactive goal/event handling**
8. **Add controlled multi-agent execution**
9. **Add safe self-maintenance**
10. **Stabilize ATLAS as an agent platform**

## Definition of Mature ATLAS

ATLAS is mature when a user can give it a meaningful goal, leave it alone, and return to a trustworthy explanation of what happened:

```text
Goal
  ↓
Understand intent + constraints
  ↓
Load capabilities
  ↓
Choose skills + node
  ↓
Plan
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
