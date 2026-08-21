# ATLAS Evolution Principles

This document defines the engineering rules for evolving ATLAS from a capable agent into a dependable agent runtime.

## 1. Goal-First, Not Tool-First

Users should describe outcomes. ATLAS decides how to achieve them.

```text
User goal
   ↓
Intent + constraints
   ↓
Plan
   ↓
Capabilities
   ↓
Execution
```

A new tool is valuable only when it improves the system's ability to accomplish meaningful goals.

## 2. The Runtime Owns the Truth

The language model proposes reasoning. It does not own permissions, durable state, execution results, or security decisions.

ATLAS runtime components remain authoritative for:

- permissions
- safety policy
- tool execution
- task state
- verification
- audit records
- credentials
- node identity

This prevents model output from becoming an implicit security boundary.

## 3. Every Action Has a Lifecycle

Important actions should follow one consistent lifecycle:

```text
propose → authorize → execute → observe → verify → record
                         ↓
                  recover / re-plan
```

An action is not considered successful merely because a tool returned without an exception.

## 4. State Is More Than Memory

ATLAS should separate different kinds of durable state:

- facts
- preferences
- projects
- goals
- missions
- checkpoints
- action history
- outcomes
- learned strategies
- credentials/references
- system state

Each state type should have its own retention, confidence, provenance, and mutation rules where appropriate.

## 5. Evidence Before Confidence

ATLAS should prefer observed evidence over model assumptions.

For important claims, the runtime should be able to answer:

- Where did this information come from?
- When was it observed?
- Is it still valid?
- How confident is the system?
- Has the user corrected it?

Unknown should remain unknown. ATLAS must not manufacture certainty to keep a conversation moving.

## 6. Bounded Autonomy

Autonomy is a permission, not a personality trait.

Every mission should have boundaries such as:

- allowed tools
- allowed nodes
- allowed resources
- time/deadline limits
- retry limits
- spending limits where applicable
- destructive-action policy
- escalation conditions

The safest default is to pause when the required authority is missing.

## 7. Failure Is Data

A failed action should become structured information.

ATLAS should record enough context to distinguish:

- transient failure
- invalid input
- unavailable dependency
- permission denial
- environmental change
- tool bug
- incorrect plan
- verification failure

Repeated failure should increase the probability of replanning rather than blindly repeating the same action.

## 8. Skills Are Capabilities, Not Privileges

Installing or loading a skill must never automatically grant unrestricted access.

A skill declares what it can do. Runtime policy decides what it is allowed to do in the current context.

```text
Skill capability
      +
User/session authority
      +
Node policy
      +
Safety policy
      ↓
Effective permission
```

## 9. Nodes Are Resources

A device should advertise capabilities without becoming a trusted execution target by default.

Node trust should be explicit, revocable, and scoped.

A node should be able to say:

- what it can execute
- what resources it exposes
- whether it is online
- what policy applies
- what version it runs

## 10. Interfaces Stay Thin

Desktop, CLI, voice, web, and iPad interfaces should consume the same runtime APIs.

Do not duplicate planning, permissions, or execution logic inside each interface.

This keeps behavior consistent across devices.

## 11. Human Intervention Is a Feature

ATLAS should not treat asking the user as failure.

Good escalation is concise and actionable:

> "I can continue, but this requires your Google login. Sign in and tell me when you're done."

Bad escalation is a dump of internal implementation details.

## 12. Proactivity Must Earn Its Place

ATLAS should proactively surface information only when it has a reason tied to an active goal, explicit watch, or important event.

No fake activity. No pointless notifications. No autonomous busywork.

## 13. Security Must Scale With Capability

Every capability expansion should trigger a security review.

More tools means a larger attack surface. More nodes means a larger trust boundary. More memory means more sensitive state. More autonomy means more impact.

Security therefore evolves alongside capability rather than being bolted on afterward.

## 14. Observability Is Part of the Product

A user and developer should be able to understand:

- what ATLAS is doing
- what it is waiting for
- why it chose an action
- which tool/skill/node acted
- what was verified
- why it stopped
- what failed

The system should expose useful summaries without requiring raw internal traces for ordinary use.

## 15. Test the Runtime, Not Just the Tools

A growing test suite should cover interactions between systems:

- planning + permissions
- skills + sandboxing
- memory + missions
- browser + perception
- nodes + authorization
- recovery + persistence
- interfaces + runtime APIs

A feature is not complete when its isolated unit test passes. It is complete when the runtime behaves correctly around it.

## 16. Safe Evolution

ATLAS may diagnose problems and propose improvements to itself, but high-impact changes require explicit authorization.

Especially protected:

- security policy
- permission defaults
- credential handling
- destructive capabilities
- network exposure
- code execution boundaries
- update mechanisms

Self-improvement must never silently rewrite the rules that constrain self-improvement.

## 17. Graceful Degradation

Optional capabilities should fail locally.

If Spotify is unavailable, ATLAS should still work. If vision is unavailable, text/browser capabilities should remain usable. If a node disappears, tasks should pause or reroute when possible.

One broken integration should not become a broken agent.

## 18. The North-Star Test

The ultimate test for an ATLAS feature is not:

> "Can ATLAS do this?"

It is:

> **"Does this make ATLAS more capable of safely accomplishing a user's goal with less unnecessary supervision?"**

If yes, build it.

If it only adds complexity, reconsider it.
