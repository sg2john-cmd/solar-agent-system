# Phase 8 Segment 2 — Comet Trigger System (Full): Offline Unit Test

**Date:** 2026-09-17 (≈ 8:50 pm)  
**Raw log:** [`p8s2_comet_triggers_offline_20260917_205000.log`](./p8s2_comet_triggers_offline_20260917_205000.log)  
**Test file:** `tests/test_comet_triggers_full.py` (offline, pure logic — **no LLM calls**)  
**Result:** ✅ **33/33 checks passed**, 0 failed. Runtime < 0.05 s.

## What this segment is

The full implementation of the Jester / Comet — a perturbation event and system probe, NOT a
resonance participant. It fires only when one of its four trigger conditions (per the authoritative
spec `comet/jester.json`) is met, delivers ONE contrarian reframe, then fades. This segment builds
the trigger logic as **pure math + tiny state I/O** so it can be verified offline and deterministically;
the live "actually call a Jester voice and fold into Phase C" path is exercised in Segment 4's
multi-session E2E acceptance test under the `--comet` flag.

## The four triggers (per jester.json)

| # | Trigger | Weight / Prob. | Condition | Fires when |
|---|---------|----------------|-----------|------------|
| 1 | `stagnation` | 0.8 | same dominant planet + similar topic | >3 consecutive sessions (on the 4th) |
| 2 | `over_seriousness` | 0.7 | sustained Ruler+Caregiver dominance, no creative input | >5 consecutive sessions (on the 6th) |
| 3 | `binary_convergence` | 0.9 | two planets in direct opposition (align < −0.6), unresolved | >2 consecutive sessions for the SAME pair (on the 3rd) |
| 4 | `random_injection` | p=0.02 / weight 0.4 | anti-calcification randomness | ~2% per session, deterministic seed by session number |

When **multiple** triggers are simultaneously eligible in one turn, the **highest activation_weight wins**.
A **3-session cooldown** (GUESS — tunable via `COOLDOWN_SESSIONS` in `comet/triggers.py`) prevents re-firing.

## Test coverage (12 groups → 33 checks)

| Group | What it proves | Result |
|-------|----------------|--------|
| TEST 1 | Default toggle OFF — existing A/B/C path byte-identical | ✅ |
| TEST 2 | No/empty input data → comet never fires; returns a clean 4-tuple | ✅ |
| TEST 3 | Stagnation fires on the correct session (4th) and then enters cooldown | ✅ |
| TEST 4 / 4b | Over-seriousness tracked; creative planet (magician) resets the serious streak to 0 | ✅ |
| TEST 5 | Binary convergence: no fire in sessions 1–2, fires on 3rd consecutive opposition | ✅ |
| TEST 6 | Random injection deterministic per seed; ~2% rate over 500 sessions (measured 0.032) | ✅ |
| TEST 7 | Cooldown blocks re-fire at gap<3; gap=3 passes the cooldown gate | ✅ |
| TEST 8 | **Weight priority:** both BC (0.9) and stagnation (0.8) eligible → BC wins | ✅ *(fixed this session)* |
| TEST 9 | State file resilience: missing/corrupt JSON → safe defaults; save/reload round-trips | ✅ |
| TEST 10 | Topic fingerprint deterministic + sensitive to planet & question changes; empty-safe | ✅ |
| TEST 11 | jester.json loads with the 4 trigger definitions and correct weights/probability | ✅ |
| TEST 12 | Integration: 8-session scenario with a mid-way topic change — fires, then no immediate re-fire after reset | ✅ |

## Bug found & fixed during this segment (root cause)

**TEST 8 (weight priority) failed at baseline:** it pre-seeded stagnation to streak=4 (eligible to fire
on the next call) but left the binary-convergence counters at zero. Because `_check_binary_convergence`
sets `exchanges = 1` on *first sight* of an opposing pair and only fires at `>2`, BC could never qualify
within that single call — so stagnation (0.8) won by default, masking the tiebreak logic.

This was a **test-setup error, not a logic bug.** The real behavior is correct: on its first turn BC has
genuinely only been "unresolved for 1 session" and must not yet fire. The fix seeds the state so that BOTH
triggers are simultaneously eligible on the call under test — pre-seed `binary_opp_pair="ruler|rebel"` and
`binary_opp_exchanges=2`, so this turn increments BC to 3 (fires) while stagnation also fires (streak→5).
With both candidates present, weight-based selection correctly returns **`binary_convergence` at 0.9**. No
production code changed — only the test's pre-seed and a clarifying comment.

## Notes / follow-ups (not blocking this segment)

- **No live LLM test needed here.** The trigger logic is pure math/state; the full E2E (comet actually
  invoking the Jester voice + folding into Phase C) lands in Segment 4's acceptance run with `--comet`.
- **Topic fingerprint is a GUESS-level approximation** — MD5 of `(dominant_pid + first_8_content_words)`,
  not semantic. It catches "same question to same planet" patterns; flagged as upgradable to embeddings later.
- **3-session cooldown and the `>N` thresholds are GUESS values** from jester.json's intent — all tunable
  via constants in `comet/triggers.py` without touching framework code.
- Old Phase 3 comet functions remain in `cognitive_chamber.py` for backward compatibility with
  `tests/test_comet_trigger.py` (still passing). The new full system lives in `comet/triggers.py`.
