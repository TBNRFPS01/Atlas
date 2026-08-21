# ATLAS x SteelMC Contribution Plan

## Why this exists

SteelMC is a Rust Minecraft Java Edition server focused on vanilla parity and better use of modern multicore hardware. As of August 2026 it is **pre-alpha**. The project already has persistent multiplayer worlds, networking, inventories, commands, early gameplay systems, and a 7,500-chunk world-generation parity suite, but survival gameplay is incomplete and Fabric/Forge/NeoForge/Paper/Bukkit extensions are not compatible yet. Plugins are not available yet.

ATLAS should be capable of helping with SteelMC development **without pretending to replace a human contributor**. SteelMC explicitly requires contributors to understand and explain every line they submit, so ATLAS's role is to accelerate research, testing, profiling, debugging, documentation, and review while leaving technical ownership with the contributor.

## Target workflow

```text
SteelMC issue / goal
        ↓
ATLAS researches repository + vanilla reference
        ↓
Builds a bounded implementation plan
        ↓
Identifies affected crates/files/tests
        ↓
Implements or prepares a focused change
        ↓
Runs formatting / tests / clippy / typos
        ↓
Runs targeted parity or benchmark checks
        ↓
Reviews the diff for correctness + regressions
        ↓
Human reviews and understands the change
        ↓
Optional PR
```

## What ATLAS needs before serious SteelMC work

### 1. GitHub integration

ATLAS needs first-class repository operations:

- inspect repositories
- search code/issues/PRs
- read files and history
- inspect review comments
- create branches
- create commits
- open draft PRs
- inspect CI
- address review feedback

All write operations must use explicit authorization and produce an audit record.

### 2. Rust development environment

ATLAS should be able to run the SteelMC validation workflow in an isolated development workspace:

```text
cargo test
cargo fmt --all --check
cargo clippy -r --all-targets --all-features
typos
```

The exact repository instructions and pinned toolchain must be treated as authoritative. ATLAS should read the current contributor documentation instead of assuming commands remain unchanged.

### 3. Vanilla-reference workflow

SteelMC's contributor workflow uses generated targeted vanilla source. ATLAS needs a dedicated research path that can:

- inspect the relevant vanilla source
- locate the behavior being implemented
- compare SteelMC's current implementation
- identify missing edge cases
- preserve the project's existing design patterns

The agent should not blindly copy generated source. It should understand the behavior and implement an idiomatic Rust equivalent.

### 4. Test-first development loop

For every non-trivial change:

```text
Reproduce / define expected behavior
          ↓
Add or identify a regression test
          ↓
Implement
          ↓
Run targeted test
          ↓
Run broader validation
          ↓
Inspect diff
```

### 5. Benchmarking capability

ATLAS should eventually have a SteelBench skill capable of recording:

- server version/commit
- Minecraft version
- CPU/model
- OS
- compiler/toolchain
- JVM baseline where relevant
- world seed
- world size / region
- player simulation parameters
- entity counts
- chunk workload
- duration
- TPS/tick time
- CPU utilization
- memory usage
- allocation/heap data when available
- network throughput
- result artifacts

Never claim a performance improvement without reproducible measurements.

## High-value areas for contribution

### A. Vanilla parity

This is the safest first contribution category.

Potential work:

- missing gameplay behavior
- block behavior
- entity behavior
- commands
- inventories
- data components
- protocol behavior
- edge cases
- serialization/persistence

Each change should have a precise vanilla reference and regression coverage.

### B. Entity systems

SteelMC currently has only a small set of meaningful entity behavior. This is a major path toward survival completeness.

ATLAS could help with:

- entity lifecycle
- movement/collision
- AI state transitions
- targeting
- spawning/despawning
- persistence
- interactions
- damage/status behavior
- entity ticking

Because entity behavior is highly coupled, ATLAS should map dependencies before changing it.

### C. Gameplay systems

Progress toward usable survival:

- crafting
- farming
- drops
- block entities
- redstone
- containers
- projectiles
- fluids
- status effects
- experience
- dimensions
- structures

Prioritize systems that unlock many downstream behaviors rather than isolated novelty features.

### D. Performance engineering

SteelMC's architecture deliberately keeps gameplay logic synchronous while moving packet processing, chunk scheduling/generation, and chunk sending outside the main gameplay tick. ATLAS should therefore profile before proposing additional parallelism.

Useful work:

- identify tick hotspots
- measure lock contention
- inspect allocation patterns
- benchmark chunk generation
- benchmark chunk sending
- benchmark packet processing
- detect regressions
- investigate deadlocks
- evaluate cache-friendly data structures

Do not parallelize gameplay merely because parallelism sounds faster. Correctness and deterministic tick semantics come first.

### E. World generation

Worldgen is already a strong part of SteelMC. Future work should protect its parity suite while improving performance and correctness.

ATLAS can help:

- reproduce mismatched chunks
- minimize failing seeds
- compare generated data
- classify parity failures
- benchmark changes
- add regression cases

### F. Plugin architecture

**Not the first priority.** SteelMC's own project philosophy is to mature the server before freezing an extension API.

ATLAS should help research plugin requirements and document likely API boundaries, but should not force a premature API design into the repository.

## ATLAS skills to build

### `steelmc-research`

Repository + vanilla behavior investigation.

Inputs:

- issue/goal
- crate/module
- relevant game behavior

Outputs:

- behavior summary
- affected code
- vanilla reference
- dependency map
- test plan

### `steelmc-dev`

Controlled Rust implementation workflow.

Capabilities:

- create branch
- edit files
- format
- compile
- run targeted tests
- inspect diagnostics
- generate focused diff

Permissions should be scoped to the SteelMC workspace.

### `steelmc-test`

Run and classify project validation.

```text
unit test
integration test
parity test
lint
format
static analysis
```

### `steelmc-bench`

Reproducible performance measurement and comparison.

No benchmark result should be accepted without recording the environment and workload.

### `steelmc-review`

Review a change for:

- vanilla correctness
- Rust correctness
- concurrency hazards
- error handling
- performance regressions
- test coverage
- unnecessary complexity
- API stability
- security issues

### `steelmc-pr`

Prepare a human-reviewable PR package:

- concise title
- motivation
- implementation summary
- test results
- benchmark results if applicable
- known limitations
- risk assessment

ATLAS should not silently publish changes.

## First contribution strategy

When we eventually work on SteelMC, do **not** start by attempting a giant subsystem rewrite.

Start with one small, measurable issue:

1. Find an incomplete behavior.
2. Reproduce it.
3. Find the corresponding vanilla behavior.
4. Add a focused test.
5. Implement the smallest correct Rust change.
6. Run SteelMC's full validation commands.
7. Review the diff.
8. Benchmark if performance is relevant.
9. Have the human contributor understand the entire change.
10. Open a focused PR if the result is good.

## Non-negotiable ATLAS rules

- Never claim a feature exists without verifying the current repository state.
- Never fabricate benchmark numbers.
- Never submit code the user cannot explain.
- Never bypass repository permissions.
- Never treat model output as a security decision.
- Never use autonomous PR generation as a substitute for human review.
- Never make broad refactors when a focused fix is sufficient.
- Always preserve reproducibility.
- Always record test results.
- Always distinguish measured performance from theoretical performance.

## Long-term goal

The goal is not to make ATLAS "code SteelMC for us." The goal is to make ATLAS an excellent **engineering copilot/agent runtime** for a demanding Rust codebase:

```text
Research
  ↓
Understand
  ↓
Plan
  ↓
Implement
  ↓
Test
  ↓
Benchmark
  ↓
Review
  ↓
Human approval
  ↓
Contribution
```

That workflow is also a stress test for ATLAS itself. If ATLAS can reliably support work on a complex, performance-sensitive, correctness-heavy open-source project while remaining auditable and bounded, it is moving toward the agent runtime described in `ATLAS_EVOLUTION.md`.
