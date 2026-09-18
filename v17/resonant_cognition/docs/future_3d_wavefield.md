# FUTURE PHASE — 3D Propagating Wave-Field ("Quantum Engine")

**Status: SHELVED (by John's decision). Not built now. DO NOT lose this rationale.**
This is a design north-star, not current scope. The minimal vector-collapse engine that ships in
Phase 0D/0E is the *1-input-at-a-time* special case of what is described here.

## John's core vision (verbatim intent, lightly normalized)
The whole system was modeled on the human mind plus a "quantum-engine" effect:
- Every brain/mind is **a point in space giving off quantum waves**.
- Where those waves **interact and overlap**, they superpose; where they oppose, they cancel.
- **"Waveform collapse"** happens when the pattern is *observed* — the act of observation collapses
  the interference field into what we perceive as a definite "reality" / answer.

> (John: "every brain is a point in space giving off quantum waves ... where those waves interact and
> 'wave form collapse' causes what we perceive as our reality to manifest." — actual physics term for the
> wave emission was forgotten; the *structure* of the idea is captured above.)

## The key detail that makes it "not just one point"
Real water waves (John's 7-stones-in-a-pond example) do **NOT** join at a single point. Each stone emits
a circular wavefront; the fronts **intersect many times**, producing a full interference field of peaks and
nulls spread across space. The "answer" is read from that whole pattern:
- **Peaks / surviving amplitude**  → consensus (what remains).
- **Nulls / cancelled amplitude**  → tension & dissonance (what was lost — the debate), but only count a
  null as meaningful when it came from two *high-amplitude* opposing sources (see collapse.py polarity-aware tension).

So the system is fundamentally a **field**, and the per-input vector-collapse we ship now is the minimal,
hardware-friendly reduction of that field to one observation.

## What building the full version would require (for future scope)
1. A spatial grid (3D, matching the engine's planet positions) + a wave equation / superposition integrator.
2. Each archetype = an emitter at its orbital position with amplitude ~ cognitive weight W_planet and a
   semantic direction; different "stone strengths" to test how dominance shifts the pattern.
3. Observation/collapse = sampling the field: report peak locations (consensus) + null locations (debate nodes).
4. Translation of "peak at planet X dominates" → words is the **Ring** job (LLM frontend), NOT the engine's.

## Why it was shelved NOW
- It is a genuine simulation/graphics project, not cognitive-engine progress — building it first would repeat
  the recurring stall ("perfect foundation before anything works") that has already burned agent sessions.
- The vector-collapse engine + per-pair cancellation map deliver the SAME conceptual result (consensus vs tension)
  at near-zero cost and run on John's local hardware today, so we validate the *cognition* first, then scale up
  to the full field once the routing behavior is confirmed correct.

## Connection to current code
- `collapse.py` (Phase 0D/E) = the minimal collapse. Its per-pair cancellation map is the vector-form of the
  "7 stones intersections."
- The 3D version would consume the same planet positions/masses and add a grid integrator around them; it does
  NOT invalidate the semantic anchors or resonance math already built — those become the *emitter parameters*.
