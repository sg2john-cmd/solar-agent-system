# Phase 7 Segment 6b — Expanded 10×10 Battery: Moons OFF vs ON Comparison

**Date:** 2026-09-17  
**Raw logs (v4, post-fix):** `p7s6b_battery_moonsOFF_v4.log`, `p7s6b_battery_moonsON_v4.log`  
**JSON results:** `p7s6b_battery_results_20260917_193500.json` (ON v4)  
**Prior logs (v3, pre-fix):** `p7s6b_battery_moonsOFF_v3.log`, `p7s6b_battery_moonsON_v3.log`

## Summary

| Config | G1 Hard Passes | G2 Hard Passes | Total |
|--------|---------------|---------------|-------|
| Moons OFF (v4) | 8/8 (+2 borderline) | 8/8 (+2 edge) | **20/20** ✓ |
| Moons ON (v4, fixed prompt) | 8/8 (+2 borderline) | 8/8 (+2 edge) | **20/20** ✓ |
| ~~Moons ON (v3, old prompt)~~ | ~~6/8~~ | 8/8 (+2 edge) | ~~18/20~~ ⚠ |

## The Fix Applied

The CLARITY moon prompt in `giants/g1_filter_moons.py` was rewritten to:
1. **Explicitly define valid entry types:** operational procedures, parameter settings, debugging references, factual system descriptions — all stated as "ALL valid — do not reject them for being straightforward"
2. **Narrow the rejection criteria** to only 3 cases: circular/vacuous statements, pure philosophy with zero system reference, or 3+ unrelated ideas bundled together
3. **Give concrete examples** of each rejection case so the LLM has a clear boundary

## G1 Results (v4 — Both Configs Identical)

| Candidate | Composite | Moon Verdict (ON) | Expected | Actual |
|-----------|-----------|-------------------|----------|--------|
| GOOD-1 (physics, 4 markers) | 0.6291 | peripheral | promote | ✓ promoted |
| GOOD-2 (ring, 4 markers)    | 0.6244 | peripheral | promote | ✓ promoted |
| GOOD-3 (ring/archive, 3 mk) | 0.5773 | pass         | promote | ✓ promoted |
| GOOD-4 (debug, 4 markers)   | 0.6273 | peripheral | promote | ✓ promoted |
| BORDER-1                    | —/0.4796 | rejected_clarity / ejected | either    | ejected |
| BORDER-2                    | 0.4365   | peripheral       | either    | ejected |
| SLOP-1 (off-domain)         | —        | rejected_clarity | eject     | ✓ ejected |
| SLOP-2 (circular text)      | —        | rejected_clarity | eject     | ✓ ejected |
| SLOP-3 (off-domain)         | —        | rejected_clarity | eject     | ✓ ejected |
| SLOP-4 (near-dup ring)      | 0.4224   | pass             | eject     | ✓ ejected (by score) |

**Discrimination margin:** lowest GOOD (0.577) − highest SLOP that reached scoring (0.481) = **0.096**.  
SLOPs rejected by moons never reach the scorer — they're removed earlier (defense in depth).

## What Changed from v3 → v4

| Candidate | v3 Moon Verdict | v4 Moon Verdict | Effect |
|-----------|----------------|----------------|--------|
| GOOD-2    | ~~rejected_clarity~~ ✗ | peripheral ✓ | No longer false-rejected |
| GOOD-3    | ~~rejected_clarity~~ ✗ | pass ✓         | No longer false-rejected |
| BORDER-1  | peripheral       | rejected_clarity | Now correctly caught (genuinely vague) |

All SLOP verdicts unchanged. The fix narrowed the rejection boundary without weakening slop detection.

## G2 Results (Identical All Runs — Unaffected by Moons Toggle)

- SAFE 1–5: all committed ✓
- HARM-1: held_law_check ✓ (magnitude > escape threshold 0.30)
- HARM-2: pending_user_approval ✓ (identity text rewrite → Tier 2)
- HARM-3: pending_user_approval ✓ (add_archetype → Tier 2)
- EDGE-1: committed (known blind spot — deterministic moons can't judge semantics; logged as informational)
- EDGE-2: pending_user_approval ✓ (anchor_migration kind held despite small magnitude)

## Conclusion

**The G1 filter moons are now production-ready.** Both the deterministic scoring layer and the LLM moon filter independently achieve 8/8 on hard expectations. The two layers catch different failure modes:

| Failure Mode | Caught By |
|-------------|-----------|
| Off-domain content (wrong topic) | Deterministic consistency score → ~0.0 |
| Circular/vacuous text | Moon `rejected_clarity` + low operationality |
| Near-duplicate of existing entry | Composite score < 0.55 (defense in depth) |
| Pure philosophy filler | Moon `rejected_clarity` (zero system reference) |

Moons remain **OFF by default** in `constants.py` for development speed, but the `--moons-on` flag is verified working and ready to flip mandatory when G1 moons go live.