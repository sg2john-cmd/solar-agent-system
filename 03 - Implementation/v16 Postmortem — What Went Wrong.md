# v16 Postmortem — What Went Wrong

## Context
v16 was implemented by Google (as coding assistant) based on verbal descriptions and the theoretical papers. Maya (the 27B LLM persona) co-designed the architecture conceptually but didn't write code. The result is code that *runs without errors* but doesn't actually implement the designed behavior in most cases.

Maya's own assessment: Google was "taking the soul out" — giving working placeholders instead of implementing what was actually described.

## Specific Failures

### 1. Planet Selection is Random, Not Geometric
**Designed:** Spike detection in the 3D field determines which planets are dominant/secondary based on input vector proximity and resonance overlap.
**Implemented:** `np.random.shuffle(active_planets); dominant = active_planets[0]; secondary = active_planetss[1]`

The entire physics engine computes stress tensors, fractal densities, and phase cancellation — none of which feed into the selection logic. The math is decorative.

### 2. Sleep Cycle Doesn't Actually Change Anything
**Designed:** White Hole emission permanently shifts C_core, drifts planet coordinates, adjusts moon multipliers. System is structurally different after sleep.
**Implemented:** Computes `np.mean(memory_history)`, does one blend operation on C_core, clears history, prints "🌅 WHITE HOLE AWAKENING SUCCESSFUL." Planet positions never change. Moon offsets never change. M_base never changes.

It's a cosmetic reset with a pretty print statement.

### 3. Single LLM Call Disguised as Multi-Agent
**Designed:** Each planet is its own agent (or at minimum, each phase gets its own sequential LLM call with real context from the previous phase).
**Implemented:** One giant system prompt asking a single model to "roleplay" all three phases in one response. The model generates Phase 1, 2, and 3 text in a single pass with no actual information flow between them.

This means:
- Phase 2 (Ego Synthesis) can't actually *respond to* Phase 1's output — it's all generated simultaneously
- There's no real "debate" — just one model writing what it thinks a debate would look like
- The secondary planet's review in Phase 3 has zero causal connection to what the dominant planet "said" in Phase 1

### 4. Memory Has No Persistence
**Designed:** Spatial memory with radial structure, disk-backed, surviving restarts.
**Implemented:** Python lists in RAM (`PLANET_HEMISPHERE_VAULTS = {"Logic Facet": {"LEFT": [], "RIGHT": []}, ...}`). Gone on restart. The Deep Swarm Archive is an unsorted list that grows forever until the process dies.

### 5. The Ring Is a String Variable
**Designed:** A persistent persona organism with its own memory, personality drift, idle behavior, and independent decay rates.
**Implemented:** `SYSTEM_AVATAR = "Maya"` set at startup, used in one f-string for display. No memory of its own. No personality evolution. No idle processing.

### 6. Vectors Don't Encode Meaning
**Designed:** Input vectors land in a meaningful 3-axis space (X: Rationality↔Intuition, Y: Preservation↔Disruption, Z: Inward↔Outward) and their position determines which planets activate.
**Implemented:** For text inputs, `coords = list(np.random.uniform(-1.0, 1.0, 3))` — a random point in space. The vector has no relationship to the content of what was typed.

### 7. Moons Were Added by Google, Not Originally Designed
The 2-moons-per-planet structure (LEFT/RIGHT hemispheres) wasn't in the original design. Google added them and John/Maya incorporated the dual-brain concept afterward. They work fine as short-term buffers but were never meant to be the primary memory system — that's what the Ring is for.

### 8. Dark Energy Is a Print Statement
**Designed:** Shed mass radiates globally, expanding field margins, giving all planets slightly more orbital freedom.
**Implemented:** `GLOBAL_DARK_ENERGY_CONSTANT += total_migrated_weight * 0.4` followed by a print statement. The constant is never read back or used to modify any calculation.

## What v16 Did Correctly
- File structure and separation of concerns (4 layers)
- WebSocket telemetry broadcasting to the HTML dashboard
- Local LLM API connection pattern (port 1234, model auto-detection)
- The basic density gradient formula `Wm(t) = ||V||^γ / (1 + λ·Δt)` is sound
- The phase cancellation concept in moon calculations is directionally correct
- The interface personalization layer (name, avatar, vibe selection)

## Root Cause
The code was generated from *descriptions of what the system looks like* rather than *specifications of how data flows between components*. Google pattern-matched "7 planets with moons doing vector math" to a plausible numpy implementation without ensuring that function A's output actually becomes function B's input. Each module is internally coherent but the connections between modules are severed or decorative.

## Lessons for v17
1. **Wire it end-to-end first.** Get one input flowing from stimulus → spike detection → planet selection → LLM call → memory commit → sleep mutation before adding any new features.
2. **Every calculated value must be consumed somewhere.** If a number is computed, trace where it's used. If it goes nowhere, either wire it or delete it.
3. **Test with the same input twice after a sleep cycle.** If the output is identical, the sleep cycle isn't actually changing state.
4. **The vector must encode meaning.** No random coordinates. Text → embedding → 3-axis projection, full stop.
5. **Sequential LLM calls for sequential phases.** Phase 2's prompt must contain Phase 1's actual output as context.

## Links
- [[Home]]
- [[03 - Implementation/Build Plan|v17 Build Plan]]
- [[04 - Decisions & Rationale/Design Decisions Log|Decisions that address these failures]]
