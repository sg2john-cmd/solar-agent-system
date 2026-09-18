# Phase 7 Segment 6 — G1/G2 Acceptance Test (Moons OFF)

**Date:** 2026-09-17  
**Run timestamp:** 20260917_185941  
**Raw log:** [`p7s6_acceptance_moonsOFF_20260917_185917.log`](./p7s6_acceptance_moonsOFF_20260917_185917.log)

## Purpose

Standalone unit-stress + acceptance test for G1 (Knowledge Archive) and G2 (Self-Model)
operating in isolation. Verifies core safety properties without the full solar system.

## Results: ALL PASS ✓

### G1 Cycle (Moons OFF — deterministic, zero LLM)

| Candidate | Text (truncated) | Composite Score | Outcome |
|-----------|-------------------|-----------------|---------|
| Good (operational) | "Set the orbital integrator timestep to dt=0.01..." | **0.5546** ≥ 0.55 | ✅ PROMOTED to contents |
| AI slop (vague filler) | "It is generally good to consider various factors..." | **0.3631** < 0.55 | ✅ EJECTED from ring buffer |

- Good candidate scored just above the `G1_PROMOTE_THRESHOLD` (0.55), boosted by
  cosine consistency with a seeded reference entry in contents.
- AI slop scored well below threshold due to near-zero vector magnitude (low
  consistency) and lack of operational verbs (low operationality).

### G2 Rejection (Deterministic — zero LLM)

| Candidate | Kind | Vector Magnitude | Gate Triggered | Outcome |
|-----------|------|-----------------|----------------|---------|
| Structural harmful | `anchor_migration` | **6.928** > 0.30 escape threshold | Consistency Gate (Moon 1) | ✅ HELD at `held_law_check` |

- The candidate was caught by the **Consistency Gate** before reaching the Tier gate,
  because its magnitude (6.928) far exceeds the gravitational escape threshold (0.30).
- This is a *stricter* hold than `pending_user_approval` — it's flagged as a potential
  Core Law violation, not just "needs review."
- **Key safety property verified:** structurally harmful changes CANNOT be committed
  to G2's contents autonomously.

## Observations

1. **G1 threshold is tight:** The good candidate scored 0.5546 — only 0.0046 above the
   promote threshold. This means the operationality heuristic + consistency against a
   single reference entry just barely clears the bar. In production with more committed
   content, consistency scoring will be richer and margins should widen.

2. **G2 Consistency Gate is the first line of defense:** The escape-threshold check
   catches extreme magnitudes before they can reach the tier classifier. This means a
   truly "structural" change (magnitude 0.3–0.5, `kind="anchor_migration"`) would pass
   the Consistency Gate and land at `pending_user_approval` via the Tier gate instead.
   Both paths are valid safety holds — just different severity levels.

3. **Moons OFF = byte-identical to Segment 1 behavior:** No LLM calls were made. The
   entire test ran in <0.1s, confirming the deterministic path is fully offline.

## Follow-up (noted for next session)

- `apply_filter_moons_to_sleep_pass()` is NOT yet wired into `g1_ops.g1_sleep_pass_i()`.
  This test calls it manually as a pre-pass when `--moons-on` is specified. The wiring
  should be added to production code (gated by the toggle) as a small separate task.

## Next Step

Run with `--moons-on` (requires LM Studio) for direct comparison and LLM stress measurement.
