# ATLAS Evolution: Long-Term Agent Context

## Goal

Make ATLAS remember what matters across sessions and use that information correctly without inventing history.

## Context model

- **Facts**: durable information ATLAS is allowed to retain.
- **Preferences**: stable choices that influence behavior.
- **Conversations**: searchable summaries/relevant excerpts, not an unbounded transcript.
- **Past actions**: what ATLAS attempted and the outcome.
- **Strategies**: approaches that worked or failed for a task type.
- **Goals**: active, paused, blocked, completed, or abandoned objectives.
- **Provenance**: where a memory came from and when it was observed.
- **Confidence**: how strongly ATLAS should rely on a memory.
- **Correction/expiry**: stale or incorrect memories must be replaceable.

## Retrieval rules

1. Retrieve only context relevant to the current task.
2. Prefer recent, high-confidence, directly relevant memories.
3. Never treat a model-generated guess as an established fact.
4. Preserve provenance and uncertainty when they affect a decision.
5. Update memory after meaningful outcomes, not every trivial interaction.
6. Keep sensitive/destructive information behind existing permission and safety boundaries.

## Definition of done

After restarting, ATLAS should be able to correctly handle requests such as:

- "Continue what I was doing yesterday."
- "Use the approach that worked last time."
- "What did you change on the Minecraft server?"
- "Remember that this machine is the main ATLAS node."
- "Forget that old preference."

without fabricating history.

## Runtime loop

**Goal → Understand → Plan → Choose capability/node → Execute → Observe → Verify → Recover → Learn → Persist → Report**
