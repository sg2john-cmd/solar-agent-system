# Review Fix Evidence — Segment 2: H1 + H2/H3 (Comet Stability Cluster)

**Date:** 2026-09-18
**Segment:** 2 of the independent blind-review fix pass
**Scope:** `gates234.py` (H1), `comet/triggers.py` (H2 + H3)
**Environment:** Windows · `python -X utf8` · all tests OFFLINE / zero LLM calls

---

## Summary

| Fix | File | Root cause | Fix applied | Status |
|-----|------|-----------|-------------|--------|
| **H1** | `gates234.py` → `_load_gates_config()` | Bare `open()`+`json.load(f)` at module import; a missing/corrupt `gates_config.json` crashed the whole pipeline on import (violated "NEVER raises" contract) | Wrapped load in `try/except`; on any I/O or JSON error, log a warning to stderr and return `_default_gates_config()` (safe defaults). Partial files get top-level keys backfilled via `setdefault`. | ✅ Verified |
| **H2** | `comet/triggers.py` → `_check_random_injection()` | Seeded RNG on the sticky session number, which is constant across every turn of a live conversation → random trigger fired EVERY turn or NEVER instead of an independent ~2% each turn | Added per-turn counter to seed: `f"comet_random_injection:{session}:{turn_counter}"`. Counter stored in comet state, ticks once per call, resets when session number changes (first turn of a new session stays deterministic). | ✅ Verified |
| **H3** | `comet/triggers.py` → `_in_cooldown()` | Short-circuited to `False` whenever either value was None/falsy → silently BYPASSED cooldown; a recent fire with no recorded/usable session number could immediately re-fire | Now FAILS CLOSED: never-fired → False (correct); fired-but-current-None/unparseable, or last unparseable → True (enforce cooldown). Cooldown only lifts when both numbers parse and gap ≥ `COOLDOWN_SESSIONS` (3). | ✅ Verified |

---

## H1 — gates_config fail-safe

**Before:** import-time crash on missing/corrupt config.
**After:** `_load_gates_config()` never raises; returns a safe-default dict mirroring the four live keys (`pii`, `safety_blocklist`, `transparency`, `audit_log`). Safety blocklist stays **enabled** in fallback (fail-open for the pipeline, but safety still active); transparency/PII default off so no stray labels or redactions on degraded config; audit defaults enabled=True to match both live config and its own docstring.

### Verification (4 scenarios)
```
[OK] missing file -> safe defaults, keys: ['audit_log', 'pii', 'safety_blocklist', 'transparency']
[OK] corrupt file -> safe defaults, no crash
[OK] partial file -> backfilled missing keys, kept provided ones
[OK] gate3 works on fallback defaults -> blocked WMD: wmd_recipes
H1 FAIL-SAFE VERIFIED — all 4 scenarios pass
```

### gates234 self-test (unchanged behavior on live config)
```
ALL GATE CHECKS PASSED ✓
```

---

## H2 — per-turn random injection

**Root cause detail:** `context["session"]` in the ring only increments at session END, so within one multi-turn conversation it is constant. Seeding a deterministic RNG with that value produced an identical draw every turn.

### Verification
- **Independent draws:** 50 turns of a single sticky session → `1/50` fires (≈ expected ~2%), definitively not the old "all 50" or "always same value" behavior.
- **Determinism preserved:** same `(session, turn)` pair → identical result every time (tests stay reproducible).
- **Cross-session independence:** different session number at same turn counter → independent draw.

```
session=7, turns 0..49 -> 1/50 fires
[OK] deterministic per (session,turn); draws vary across turns
```

---

## H3 — cooldown fails closed

### Verification
```
fired@5 + current=None   -> cooldown=True  (fail closed)
never fired              -> cooldown=False (correct)
gap math: gap<3=cooldown, gap>=3=clear      (gap2->True, gap3->False)
unparseable current      -> fail closed (True)
```

---

## H2 + H3 integration — sticky-session simulation

Simulated one live conversation where `session_number` stays fixed at 3 across 40 turns:

```
40 turns in ONE sticky session (sess=3): 1/40 comet fires
```

Before the fix this same loop would have produced either 40/40 or a single deterministic result. The per-turn counter + fail-closed cooldown together give realistic anti-calcification behavior without runaway firing.

---

## Regression check — full existing comet suite

The pre-existing offline test file was re-run after all edits:
```
[TEST 12] Integration: 8-session scenario with topic change mid-way ...
RESULTS: 33/33 passed, 0 failed. Time: 0.02s
ALL CHECKS PASSED.
```

All 4 triggers (stagnation / over-seriousness / binary_convergence / random_injection) and the cooldown path still behave as designed; no regressions introduced by the H1/H2/H3 changes.

---

## Notes & follow-ups for later segments
- `turn_counter` + internal `_last_session_seen` are new keys in comet state; `load_comet_state()` already merges with defaults, so old state files without these keys load cleanly (no migration needed).
- H2 and H3 were fixed as one cluster intentionally — they misbehaved together because session numbers are sticky within a conversation.
- Next segment per reviewer priority: **M2** (pipeline serves raw `[ERROR]` string when the dominant planet erred → fall back to next valid planet), then M4 already done in Segment 1, then H4/H5 and remaining M/L items.
