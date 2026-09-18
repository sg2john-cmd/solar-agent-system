# M1 — pipeline.py: Fragile `dir()` Guards in Diagnostics

**Date:** 2026-09-18  
**Segment:** Review Fix Pass, Segment 6 (M1) of the independent blind review  
**Reviewer priority position:** After H5; first of the M-tier fixes.

---

## Problem

Four occurrences of `'varname' in dir()` were used as guards before referencing
`top_pid`, `resonance_scores`, and `action_state` inside `process_input()`. This idiom is:

1. **Unusual and non-idiomatic** — `dir()` at function scope returns local names, but it's a dynamic namespace query that can behave unexpectedly under refactoring (e.g., if the variable were assigned in a nested comprehension or deleted).
2. **Silently wrong for `top_pid`** — when both `phase_c` and `phase_b` are empty/None, `top_pid` was never assigned at all, so `'top_pid' in dir()` returned False *by accident* of the guard working. But if someone refactored to assign `top_pid = ""` earlier (a natural cleanup), the guard would still return True and serve an empty string instead of None.
3. **Inconsistent with codebase style** — the rest of pipeline.py uses plain variable references after guaranteed assignment; these four were the only exceptions.

---

## Fix Applied (`pipeline.py`)

### 1. `top_pid` safe-default initialization (line ~298)
```python
# Before:
if phase_c:
    top_pid, primary_response = _pick_primary(phase_c, routed_weights)
elif phase_b:
    top_pid, primary_response = _pick_primary(phase_b, routed_weights)

# After:
top_pid = None   # M1: safe default; overwritten when phase_c or phase_b is non-empty
if phase_c:
    top_pid, primary_response = _pick_primary(phase_c, routed_weights)
elif phase_b:
    top_pid, primary_response = _pick_primary(phase_b, routed_weights)
```

### 2. Both `gate4_log` calls — removed guard (lines ~329, ~359)
```python
# Before:
"top_planet": top_pid if 'top_pid' in dir() else None,

# After:
"top_planet": top_pid,
```

### 3. Return dict — `resonance_scores` and `action_state` (lines ~371–372)
Both variables are **always** assigned inside the try/except block at Step 5 (either the
success path or the exception handler), so no initialization change was needed there.
Simply removed the guards:
```python
# Before:
"resonance": resonance_scores if 'resonance_scores' in dir() else {},
"action_state": action_state if 'action_state' in dir() else None,

# After:
"resonance": resonance_scores,
"action_state": action_state,
```

---

## Verification

**Command:** `python -X utf8 pipeline.py --smoke`  
**Wall time:** 0.1 s — fully offline, no LM Studio required.

```
================================================================
PIPELINE SMOKE TEST (offline — gates + ring only)
================================================================
[✓] Gate 3 (input): benign text passes
[✓] Pipeline: WMD input → blocked_input (refusal: 'Maya: [ring] I can't help with that...')
[✓] Pipeline: nonsense input → blocked_input (clarity)
[✓] Gate 2: transparency label present on output
[✓] Ring inbound: session #None, 0 recent topics
[✓] Gate 4: 10 recent events logged (types: gate3_block_input, gate1_reject, gate1_result, input_received)
[✓] Smoke cleanup: removed 5 audit entries (tag-based=True, legacy_fallback=False)

================================================================
PIPELINE SMOKE TEST PASSED ✓ (offline path verified)
================================================================
```

**Exit code:** 0  
**`in dir()` occurrences remaining in pipeline.py:** 0 (confirmed via grep)

---

## Consistency Note

The M2 fix (`_is_valid_response` / `_pick_primary`) was added in Segment 3 of this review pass. This M1 fix removes the last remaining `dir()`-style guards that predated it, making the diagnostics section fully consistent with the rest of the file. No behaviour change — all four variables were already guaranteed to be assigned on every code path that reaches their use sites; this just makes that guarantee explicit and safe against future refactoring.
