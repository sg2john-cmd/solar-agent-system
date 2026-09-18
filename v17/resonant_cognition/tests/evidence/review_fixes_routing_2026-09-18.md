# Evidence: Independent Blind Review — Routing Guard Fixes (3 degenerate-case bugs)

**Date:** 2026-09-18 12:46 GMTST
**Scope:** Three reviewer "documents-bug" tests that exercised `routing.py` arithmetic and were still red when M2/guard verification surfaced them. All three are edge-case degeneracies in the routing field math (NOT regressions from any prior change — they pre-date it). Each is now guarded in source AND flipped to assert the fixed state.
**Working dir:** `A:\AI\Solar_Agent_System\v17\resonant_cognition`

## What Changed (all in `routing.py`)

### 1. Segment-3 all-zero amplitude crash (`_smoke()`, ~line 507)
- **Was:** `max_amp, min_amp = max(amps_rt), min(a for a in amps_rt if a > 0)` → raised `ValueError: min() arg is an empty sequence` when EVERY routed amplitude clamped to exactly zero (input equidistant from / far from all centers — the "no dominant planet" case).
- **Now:** `min_pos = min((a for a in amps_rt if a > 0), default=C.EPSILON)`; `top_spread = max_amp / max(min_pos, C.EPSILON)`. No positives → zero-spread field instead of a crash. Normal (mixed) case is byte-for-byte unchanged (`test_single_zero_amplitude_does_not_crash_smoke` still pins it).

### 2. angular_z degenerate spread (~line 248)
- **Was:** `sd = (...) or 1e-9`; when all 7 centers are equidistant, `sd == 0`, so `(d - mu)/1e-9` divided float noise (~1e-17) by 1e-9 → planet ranking decided by dict order / roundoff, not geometry.
- **Now:** if the cohort spread `sd < 1e-9` (degenerate), fall back to ALL-EQUAL `z = 0.0`. Threshold is `1e-9`, deliberately NOT `C.EPSILON` (=0.1) — that constant is a softening length in a different geometric unit domain and would zero out legitimate small spreads. Real-spread case unchanged.

### 3. core_bend discontinuity at r≈0 (~line 214)
- **Was:** `if r < 1e-9: return _unit(input_vec), {"bend_frac": 0.0, ...}` — a HARD 0.0 that made bend_frac step from ~0.025 (just above the guard) to exactly 0.0 (below it), contradicting its own "gentle / never overwhelms identity" docstring.
- **Now:** the guard returns the SAME squashed, bounded `bend_frac` (`force/(1+force*BEND_K) ≤ k^-1`) instead of forcing 0.0, but skips the toward-core unit-direction blend (at r≈0 the input IS the core position — no meaningful direction). Continuous as r→0, still capped at ~k^-1 so it never overwhelms semantic identity (RULER-COLLAPSE guard intact).

## Verification Output (all green)

### 1. The three flipped routing tests
```
$ python -X utf8 -m unittest \
    tests.test_bug_routing_smoke_segment3_zero_amplitude \
    tests.test_bug_routing_angular_z_degenerate_sd \
    tests.test_bug_routing_core_bend_discontinuity_at_zero -v
test_all_zero_amplitudes_do_not_crash_smoke ... ok
test_single_zero_amplitude_does_not_crash_smoke ... ok
test_documented_fallback_behaviour ... ok
test_equal_distances_yield_exactly_zero_zscores ... ok
test_near_equal_distances_produce_bounded_zscores ... ok
test_bend_frac_is_continuous_across_the_zero_guard ... ok
test_bend_frac_is_monotonically_bounded_near_zero ... ok

Ran 7 tests in 0.038s
OK        (EXIT_CODE=0)
```
Note: `test_bend_frac_is_continuous_across_the_zero_guard` passing confirms the fix genuinely produces a continuous bend_frac across the guard — it is not merely an assertion flip; the source was measured to be monotone-bounded in the sweep.

### 2. Full discovery sweep (no regressions)
```
$ python -X utf8 -m unittest discover -s tests -p 'test_*.py'
Ran 15 tests in 18.191s
OK        (EXIT_CODE=0)   ← was "FAILED (failures=3)" before this fix
```

## Also cleaned up (cosmetic, same pass)
- `tests/test_bug_memory_pii_guard_never_raises.py`: stale `"FAILING TEST"` docstring header → corrected to REGRESSION GUARD (FLIPPED); the test itself already passed (H2). No behaviour change.
- `collapse.py` `_load_planet_identity()`: `json.load(open(f, ...))` → proper `with open(...) as fh:` context manager, clearing a pre-existing `ResourceWarning: unclosed file`. No behaviour change.

## Status
All three routing degenerate-case guards landed; the full suite is now 15/15 green. These were always-red "documents-bug" tests (an earlier note claiming "routing tests passing" was imprecise) — now genuinely fixed and verified.
