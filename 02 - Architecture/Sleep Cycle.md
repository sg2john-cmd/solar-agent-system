# Sleep Cycle — Full Specification

## Purpose
The sleep cycle is how the system *actually changes*. Not "here's a summary of what happened" but genuine parameter mutation that makes the next waking session behave differently. The field topology after 30 days of operation should be visibly different from day one.

## Two-Tier Sleep Design

### Micro-Sleep ("Nap") — Light Pass
**Triggers:**
- Automatic: 30 minutes idle, or every ~10 sessions whichever comes first
- On command: user types `/nap` or hits the quick-nap button
- Before exit: if user closes mid-conversation and opts for "quick"

**What it does (subset of full cycle):**
- Pass I only (Integration Check): promotes well-aligned ring buffer entries to orbital status, accelerates decay on misaligned ones
- Pass V only (Dark Energy Sweep): sheds entries below minimum mass threshold
- NO structural drift. Planet positions and C_core stay put.

**Purpose:** Keeps "current conversation context" warm without letting it harden into permanent law. Think of it as the mental housekeeping you do between conversations — filing things away, tossing trash — without reorganizing your entire identity.

**Duration:** Fast. Should complete in seconds (no LLM calls needed, just math on existing vectors).

### Deep Sleep — Full 5-Pass Cycle
**Triggers:**
- Automatic: 3 hours idle (configurable)
- On command: user types `/sleep` or hits the deep-sleep button at any time
- Before exit: if user closes and opts for "full" (or just lets the timer fire in background)
- Forced: if memory arrays exceed hard capacity limits

**What it does:** All 5 passes as specified below. Includes Black Hole compression, White Hole emission, structural drift of C_core + planet coordinates.

**Purpose:** The system actually *changes*. Next session routes differently because the geometry shifted.

**Duration:** Slower (involves LLM calls for Pass I dream narrative and Pass IV ring review). But see below — it's non-blocking.

## Sleep is Non-Blocking to the User

The user can continue interacting during sleep. The system enters a **half-asleep mode**:
- Waking-cycle LLM calls still work (the model isn't locked out)
- Routing uses *pre-drift* planet positions until Pass IV commits
- New memory writes go into ring buffers (incubation) rather than directly to orbital status — they'll be integrated when the sleeping pass reaches them
- The Ring persona continues responding normally; it doesn't announce "I'm napping"

So if the user says "give me 10 mins, I need a nap" and walks away, the timer fires in the background, does its work, and the next time they type something the system has already evolved. No waiting screen, no blocking dialog.

**Exit behavior:** If the user closes the terminal mid-session:
- Default: ask "Quick nap or full sleep before closing? [quick/full/skip]"
- Quick = micro-sleep (instant)
- Full = deep sleep runs in background if possible (e.g., as a detached process), or is skipped with a flag so next launch triggers it immediately
- Skip = no sleep, state saved as-is

## Preconditions (Deep Sleep Only)
- Current session's experience fragments flushed from moons to Ring/memory matrix
- Memory history array populated with at least one entry
- No hard lock on input channels (half-asleep mode handles concurrent input gracefully)

## The Five Passes

### Pass I — Synaptic Dream Replay (REM State)
The engine sequentially feeds stored waking memory vectors back through the planetary manifolds in an isolated offline sandbox.

**What actually happens:**
- Each stored vector from `memory_history` is re-processed through `process_intent()` with reduced `active_will` (0.7) and mode="DREAM_REPLAY"
- Planets re-evaluate interactions without time pressure
- The system identifies semantic correlations that were missed during real-time processing (e.g., "the user's question at 2pm was actually related to their statement at 4pm, but we treated them as separate events")
- Correlations are tagged for the compression pass

**Output:** A set of identified correlation clusters + a raw "dream narrative" (LLM-generated fluid blending of the day's experiences)

### Pass II — Synaptic Pruning & Compression (Black Hole)
Stagnant data undergoes extreme geometric compression.

**What actually happens:**
- Low-resonance background noise from the asteroid belt → permanently nullified (`W → 0`)
- High-value recurring interaction paths → compressed via mean variance tensor into dense structural axioms
- Contradictory memory clusters that can't be resolved → routed to Black Hole (crushed to their fundamental disagreement axis, stored as a "tension point" rather than resolved)
- Anything in the G1 Ring or G2 Ring gets its first review here

**Output:** A compressed axiom block (not 3 sentences — structured data: parameter adjustments, correlation weights, tension points)

### Pass III — White Hole Awakening (Parameter Shift)
The compressed axioms are emitted back into the system as *actual numeric changes*.

**What actually happens:**
- `C_core` position shifts: `C_new = C_old * 0.6 + distilled_vector * 0.4`
- Planet base coordinates drift: each planet moves slightly based on how heavily it was used this session and what correlations were found
- Moon offset multipliers adjust if a hemisphere consistently over/under-performed
- `M_base` recalibrates if the core's gravitational response was too aggressive or too lax across the session
- Any G1 Ring entries that passed review → committed to Giant 1 proper (permanent knowledge)
- Any G2 Ring entries that passed stability check → committed to Gas Giant 2 (self-model update)

**Output:** Modified engine state. The system is literally different now. Same input tomorrow will produce a slightly different routing pattern because the geometry changed.

### Pass IV — Ring Review & Debate
Gas Giant ring candidates go through full engine scrutiny.

**G1 Ring review question:** "Is this knowledge actually true, operational, and non-redundant?"
- Routed through all 7 planets for debate
- Logic Facet checks consistency with existing G1 entries
- Skepticism Filter asks if it's actually *usable* in a calculation or just decorative
- Safety Guard verifies it doesn't encode boundary-violating behavior
- Wave-form collapse → commit / modify-and-requeue / reject

**G2 Ring review question:** "Is this self-modification good for the system?"
- Same full engine debate
- Empathy Resonance checks if the change still serves the user well
- Sovereign Identity checks if it's consistent with the system's core self-concept
- The monthly self-review log is referenced for continuity

**Output:** Committed entries (moved inward) or ejected entries (Dark Energy, logged with rejection reason)

### Pass V — Dark Energy Mass Distribution
Prevents any single body from becoming a dominant gravity well that flattens the field.

**What actually happens:**
- Scan all 7 planets + both Gas Giants for mass saturation (> `MASS_SATURATION_THRESHOLD`)
- Over-saturated bodies shed excess to Deep Swarm Archive (radial placement: important = closer to core, old/less relevant = further out)
- Shed weight radiated globally as anti-gravitational Dark Energy → expands field margins
- This means even planets that DIDN'T shed mass get slightly more orbital freedom after a distribution pass

**Output:** Balanced field. No single node dominates. The cosmological constant (`GLOBAL_DARK_ENERGY_CONSTANT`) updates.

## Post-Sleep State
```
C_core:                    [shifted from previous position]
Planet coordinates:        [all 7 drifted, topology changed]
Moon offsets:              [adjusted per performance]
M_base:                    [recalibrated if needed]
G1 committed knowledge:    [+N new permanent axioms (if any passed)]
G2 self-model:             [+N or -N entries (growth/decay)]
Deep Swarm Archive:        [radially reorganized]
Dark Energy constant:      [updated]
Memory history array:      [cleared, ready for next waking cycle]
```

## What Sleep is NOT
- ❌ Not a summary ("here are 3 things I learned")
- ❌ Not cosmetic (printing "🌅 AWAKENING SUCCESSFUL" without changing state)
- ❌ Not a reset (the system doesn't return to defaults — it *evolves*)
- ❌ Not instantaneous (takes real time, processes sequentially through all 5 passes)

## Tuning Parameters
| Parameter | Default | Notes |
|---|---|---|
| `MASS_SATURATION_THRESHOLD` | 4 entries per moon vault | Increase if system feels "forgetful" |
| Dark Energy coefficient | 0.4 × shed weight | Higher = more field expansion after sleep |
| C_core shift ratio | 0.6/0.4 blend | More conservative (0.8/0.2) for slower evolution |
| Planet drift magnitude | Scales with session usage frequency | Cap at ±0.1 per sleep cycle to prevent runaway |
| Ring incubation period | 3-7 days before decay starts | Shorter = more agile, longer = more stable |
| G2 decay half-life | ~4 weeks (tunable) | How long a self-model entry persists if unused |

## Links
- [[Home]]
- [[02 - Architecture/Data Flow|Full Data Flow]]
- [[01 - Theory/Dynamic Information Evolution|Paper III: The theoretical basis]]
- [[03 - Implementation/v16 Postmortem — What Went Wrong|What v16's sleep cycle got wrong]]
