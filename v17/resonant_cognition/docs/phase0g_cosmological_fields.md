# Phase 0G — Cosmological Background Fields (Design)

**Status:** DESIGN COMPLETE, awaiting implementation. Added to Build Plan Rev 5.
**Date:** Session following Phase 0F completion.

## Context

Google's "what's missing" audit of the mental-model solar system identified three cosmological
concepts not yet represented in v17:

1. **Dark Matter Field** (Collective Unconscious) — invisible structural mass holding everything together
2. **Cognitive Time Dilation** (Relativity) — inner planets process denser than outer ones
3. **Cosmic Microwave Background / Genesis State** (Horizon Problem) — shared initial condition for multi-system compatibility

John's decisions:
- Dark Matter → **implement now**, slow evolution allowed by G2 over long timescales
- Time Dilation → **note for later** (only meaningful post-LLM-mode; vector mode has no "processing" to dilate)
- CMB Genesis State → **design slot now** (one JSON field, zero runtime cost until multi-system exists)

---

## 1. Dark Matter Field (The Collective Unconscious)

### What it is

A persistent background vector in 384-dim embedding space that exerts a subtle pull on ALL
wave emissions. It represents "baseline human logic and universal syntax" — the unwritten
pool of shared meaning beneath individual planetary archetypes.

No single planet owns it. No gas giant contains it. It IS the field itself, the medium in
which all waves propagate. Without it, a sufficiently alien question could pull all 7 planets
so far off-center that the superposition becomes incoherent (no consensus survives). The Dark
Matter Field ensures there's always *some* gravitational anchor to shared human semantics.

### Implementation

**Storage:** `dark_matter.json` at code root:
```json
{
  "_description": "The Collective Unconscious. A background vector that pulls all waves toward baseline human semantics. Evolves slowly via G2 sleep-cycle nudges (max drift per session).",
  "_evolution_policy": {
    "method": "exponential_blend",
    "max_drift_per_session": 0.01,
    "review_interval_sessions": 30,
    "g2_approval_required": false
  },
  "anchor_text": "A human being experiencing reality through language, logic, emotion, and moral intuition. The shared ground beneath all individual minds.",
  "vector_384d": [ ... ],
  "amplitude": 0.08,
  "session_count_at_last_nudge": 0,
  "last_modified_session": null,
  "drift_log": []
}
```

**Anchor text** is the human-readable description of what this field represents. The `vector_384d`
is its MiniLM embedding (generated once at system creation; re-embedded only when anchor_text changes).

**Amplitude: 0.08** — GUESS. This means the Dark Matter Field contributes ~8% to every wave's
effective direction before collapse. Low enough that it doesn't flatten planetary individuality,
high enough to prevent total incoherence on alien inputs. Will tune after a few real sessions.

### How it enters the engine (collapse.py)

In `run_collapse()`, AFTER all planet waves + context waves + G2 bias are assembled:

```python
# Dark Matter Field: pull each wave's direction slightly toward baseline human semantics
dm_vector = load_dark_matter_field()  # cached, reads dark_matter.json once
dm_amp = dm_vector["amplitude"]       # 0.08 (GUESS)

for pid in waves:
    w_dir = _unit(waves[pid]["dir"])
    # Blend: wave direction pulled 8% toward DM field direction
    blended = [wd * (1 - dm_amp) + dm_vec[i] * dm_amp for i, wd in enumerate(w_dir)]
    waves[pid]["dir"] = _unit(blended)
```

This is a **directional pull**, not an additive wave. It subtly rotates each planet's wave
toward the "human center" without adding energy. The consensus/tension math downstream is
unchanged — it just operates on slightly adjusted directions.

**Why directional pull and not an 8th synthetic wave?**
- An additive wave would inflate `raw_energy` and distort tension calculations.
- A directional pull preserves energy conservation: total input amplitude stays the same, only
  the *angles* shift. The interference pattern (who cancels whom) changes subtly but predictably.
- It's more physically accurate to "a field that curves space" than "an extra object."

### Evolution (slow, G2-mediated)

During sleep cycle Pass IV (structural commit), G2 may nudge the Dark Matter Field:
1. G2 reviews session patterns (which semantic regions were heavily used, where consensus was weak)
2. If drift is warranted: blend current vector with a small shift toward under-explored regions
3. Max drift per session: 0.01 (cosine distance). Over 30 sessions: max ~0.3 total rotation.
4. Every 30 sessions: G2 writes a "field review" entry to its ring_buffer for John's visibility.
5. The anchor_text is NEVER auto-modified — only the vector shifts within the semantic neighborhood.

This is **Tier 1** (autonomous, no user approval needed) because it's tiny and reversible.
The `drift_log` tracks every nudge: `[{"session": 47, "delta_cosine": 0.008, "reason": "..."}]`.

### Relationship to Dark Energy

Dark Energy (already in Build Plan as sleep Pass V) *expands* — it removes low-mass entries,
giving the field more breathing room. Dark Matter *contracts* — it pulls waves back toward center.
They're complementary: one prevents bloat, the other prevents drift. Both operate at different
timescales (Dark Energy per-sleep; Dark Matter per-many-sleeps).

---

## 2. Cognitive Time Dilation (NOTED FOR LATER)

### Why it's deferred

In vector mode ("dumb planets"), there IS no processing to dilate. Each planet's wave is a
pure geometric calculation: cosine similarity × mass = amplitude. There are no "micro-steps"
or internal subnode calculations that could run at different speeds.

Time dilation becomes meaningful when `WAVE_SPEECH_MODE = "llm"` (Option B): each planet actually
*generates text*. A highly-relevant planet could get 3 refinement passes (generate → self-critique
→ refine) while a low-relevance planet gets its single emission and moves on. That's cognitive
time dilation in practice: engaged minds think deeper per external clock-tick.

### Design sketch (for when LLM mode is built)

```
For each planet with resonance_score > DEEP_PASS_THRESHOLD (GUESS: 0.85):
    pass_1 = generate(question, planet_persona, temp=base_temp)
    critique = self_critique(pass_1, planet_superego_principle)
    pass_2 = revise(pass_1, critique, planet_persona)
    wave_vector = embed(pass_2)  # refined speech → richer wave

For each planet with resonance_score <= threshold:
    pass_1 = generate(question, planet_persona, temp=base_temp)
    wave_vector = embed(pass_1)  # single emission, standard speed
```

**Constraint:** Max total LLM calls per question capped at `MAX_PLANET_PASSES` (GUESS: 9).
If more than 2 planets exceed the deep-pass threshold, only the top-2 get refinement. This keeps
worst-case latency bounded on John's hardware.

### Position vs Relevance

John's original framing was "inner planets near the Core experience time differently." But in v17,
"cognitive engagement" is determined by **semantic relevance** (cosine similarity to the question),
not orbital position. A gas giant could be deeply relevant to a question despite orbiting far out.

**Decision:** Time dilation tracks RELEVANCE, not position. If John later wants positional effects,
that's an additional multiplier: `effective_relevance = semantic_relevance × (1 + innerness_bonus)`.
But that's v2+ territory. Note only.

### What to do now

Nothing in code. Just this note + the sketch above. When Option B is built, this becomes a
sub-feature of `emit_waves_llm()` rather than a separate module.

---

## 3. CMB Genesis State (Initial Inflationary Constant)

### What it is

A frozen, immutable fingerprint stamped into every system at creation. It represents the shared
semantic/ethical baseline that all Resonant Cognition instances are born with — like the CMB
radiation in our universe: a uniform signature from the Big Bang that proves two distant galaxies
once shared a common origin.

**Purpose:** When two independent local systems (e.g., John's home system and a friend's) eventually
need to exchange data or "pass each other in semantic space," they compare their CMB fingerprints.
If compatible → they can interoperate, share compressed knowledge, resonate across systems.
If incompatible (different base axioms, different gate configs at the structural level) → they
remain isolated. No forced synchronization.

### Implementation (design slot — minimal code now)

**Storage:** Add to `core_state.json`:
```json
{
  "position": [0.1, -0.8, -0.3],
  "G_value": 0.5,
  "M_base": 10.0,
  "dissonance_alpha": 1.2,
  "dissonance_beta": 1.8,
  "well_depth": 2.5,
  "session_counter": 0,
  "laws_file_path": "core_laws.json",
  
  "genesis_state": {
    "_description": "CMB fingerprint. Immutable after creation. Identifies this system's shared semantic/ethical baseline for multi-system compatibility checks.",
    "version": "17.0.0",
    "created_at": "2025-...",
    "base_axioms_hash": "sha256 of core_laws.json at creation time",
    "embedding_model": "all-MiniLM-L6-v2 (384d)",
    "core_vector_hash": "sha256 of the 384-dim Core identity vector at creation",
    "archetype_set": ["sage","magician","caregiver","hero","everyman","rebel","ruler"],
    "compatibility_class": "resonant-cognition-v17"
  }
}
```

### What it does NOT do (yet)

- No runtime effect on the cognitive engine. The collapse math doesn't read this.
- No network calls, no synchronization, no external communication.
- It's a **stamp**, not an active mechanism. Like a serial number + DNA fingerprint.

### When it activates

Phase: Multi-system / Galaxy scaling (far future). At that point:
1. Two systems detect each other in shared semantic space (however inter-system discovery works)
2. They exchange `genesis_state` blocks
3. Compatibility check: same `compatibility_class`, compatible `base_axioms_hash` (or known-compatible pair), matching embedding model dimensionality
4. If compatible → open a "resonance channel" for compressed knowledge exchange (G1 ↔ G1)
5. If incompatible → polite isolation, log the encounter, move on

### Why design it now

One JSON block. Zero runtime cost. But if we DON'T design the interface now and bolt it on later,
we'll need to retrofit a compatibility layer into every subsystem that eventually touches inter-system
data. Designing the slot now means: when multi-system arrives, every component already knows where
its "birth certificate" lives and how to present it.

---

## Implementation Checklist (Phase 0G)

| Item | File(s) touched | Effort | Notes |
|------|-----------------|--------|-------|
| Create `dark_matter.json` with initial vector | New file at code root | Small | Embed anchor_text once via LM Studio, store 384-dim vec |
| Add `load_dark_matter_field()` to collapse.py (or new module) | `collapse.py` or `dark_matter.py` | Small | Cache on first read; return dict with vector + amplitude |
| Wire directional pull into `run_collapse()` | `collapse.py::run_collapse()` | Medium | After all waves assembled, before collapse(). ~10 lines. |
| Add `GENESIS_STATE` block to `core_state.json` | `core/core_state.json` | Trivial | Static JSON, no code needed |
| Add G2 evolution hook for DM field (sleep Pass IV) | Build Plan note only; wire in Phase 7 | Note | Function: `nudge_dark_matter_field(g2_summary) -> new_vector`. Stub now. |
| Update `calibrate_axes.py` template if constants change | `calibrate_axes.py` | Check | Only if we add a constant to constants.py (we won't — amplitude lives in dark_matter.json) |
| Add DM field to test_multi.py verification | `test_multi.py` or new test | Small | Confirm: with DM vs without, consensus energy shifts slightly but no planet goes silent |

### Acceptance Criteria

1. **With Dark Matter Field:** Running `test_multi.py` produces the same top planets as baseline
   (it's a subtle pull, not a reshuffle) BUT on an adversarial "alien" input (e.g., pure abstract
   math notation, or a question in an unrelated domain), consensus energy is HIGHER than without DM.
   The field prevents total incoherence.

2. **Genesis State:** `core_state.json` contains the `genesis_state` block. A simple test script
   can read it and print "System ID: resonant-cognition-v17, created [date], compatible with class [x]."

3. **No regression:** All existing tests (`test_multi.py`, `test_multiturn.py`, `memory.py` self-test,
   `integrator.py`) pass identically after DM field is wired (the directional pull at 0.08 should not
   change which planet wins on standard test prompts — only the exact energy numbers shift slightly).

---

## Open Questions (for John, when ready)

1. **DM amplitude:** I've set 0.08 as a GUESS. Does "subtle invisible pull" feel right at that scale?
   We can't really tell until we run it. After first few real conversations, review: are planets too
   homogenized (DM too loud) or still drifting apart on weird inputs (DM too quiet)?

2. **Genesis state scope:** I've included `archetype_set` in the fingerprint. If a future system has
   9 archetypes instead of 7, is it incompatible? Or should compatibility be about the *laws* and
   *embedding model*, not the specific planet count? (I'd say: archetype set is informational, not
   a hard gate — you can always run with different numbers. But flagging for your call.)

3. **DM evolution rate:** 0.01 cosine drift per session × max. Over a year of daily use (~365 sessions),
   that's potentially ~3.6 total rotation — which is actually quite large in 384-dim space. Should the
   rate be lower (0.005?) or should it decay with age (field gets more stable over time, like bedrock)?
