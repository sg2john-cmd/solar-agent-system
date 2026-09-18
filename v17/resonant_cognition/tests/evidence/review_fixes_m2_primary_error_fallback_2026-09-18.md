# Review Fix Evidence — Segment 3: M2 (Primary Response Error Fallback)

**Date:** 2026-09-18
**Segment:** 3 of the independent blind-review fix pass
**Scope:** `pipeline.py` → primary-response selection in `process_input()`
**Environment:** Windows · `python -X utf8` · all tests OFFLINE / zero LLM calls

---

## The bug (M2)

In `process_input()`, the final user answer is built from the **highest-weighted planet's Phase C output**:

```python
top_pid = max(routed_weights, key=routed_weights.get)   # dominant by raw weight
primary_response = phase_c[top_pid].get("response", "")  # ← could be "[ERROR] ..."
```

If that dominant planet had errored during Phase C (LLM call failed → `error=True`, `verdict="UNKNOWN"`, `response="[ERROR] {msg}"`), the pipeline handed the **raw `[ERROR] ...` string straight to the user** as their answer. The "first available response" fallback loop was also error-blind, so it could pick another errored planet too.

## The fix

Added two small helpers inside `process_input()` and rewired both the Phase C and Phase B branches through them:

- **`_is_valid_response(data)`** — True only for a usable body: non-empty (≥10 chars), not flagged `error=True`, not `verdict=="UNKNOWN"`, and not `[ERROR]`-prefixed.
- **`_pick_primary(phase, weights)`** — walks planets in **descending routed weight** (preserving "dominant voice" intent) and returns the first *valid* one. Only if none are valid does it return empty, at which point the caller substitutes a graceful `[ring] I couldn't form a coherent response to that.` message and logs `chamber_all_errored` for audit.

Net behavior:
1. Dominant valid → chosen exactly as before (no regression).
2. Dominant errored → falls back to next-highest-weighted **valid** planet.
3. Only low-weight planets valid → walks all the way down to them.
4. All errored/empty → graceful message, never a raw `[ERROR]` string.

---

## Verification (offline, zero LLM) — 4 scenarios

Representative Phase C dicts mirroring the real per-planet shape (`{response, verdict, error}`):

| Scenario | Setup | Result |
|----------|-------|--------|
| **A** dominant errored | hero(0.9)=ERR, sage(0.6)=OK, ruler(0.3)=ERR | picked **sage**; response is real text, not `[ERROR]` ✅ |
| **B** only lowest valid | hero/sage=ERR, ruler(0.3)=OK | walked down to **ruler**; clean text ✅ |
| **C** all errored | two ERR planets | returns `('', '')` → caller serves graceful message; raw error never served ✅ |
| **D** normal case | hero(0.9)=valid, sage=valid | picked **hero**, exact string preserved (no regression) ✅ |

```
=== M2 scenario A: dominant planet ERRORED -> must fall back ===   [OK] fell back past errored dominant to next valid planet
=== M2 scenario B: ONLY the lowest-weighted is valid ===           [OK] walked all the way down to the only valid planet
=== M2 scenario C: ALL errored -> graceful, never raw error ===    [OK] final served would be graceful message
=== M2 scenario D: normal case unchanged (dominant valid) ===      [OK] dominant valid planet still chosen as before
ALL M2 SCENARIOS PASS — no raw [ERROR] string ever served; falls back by weight.
```

## Regression check — pipeline offline smoke test
```
PIPELINE SMOKE TEST PASSED ✓ (offline path verified)
   Gate 3 / Gate 1 clarity / WMD block / Gate 2 label / Ring inbound / Gate 4 audit all green
```

`import pipeline` also succeeds, confirming the edit is syntactically sound and doesn't disturb module load.

---

## Notes for later segments
- The graceful-fallback branch now emits a `chamber_all_errored` Gate 4 event, so "all 7 planets failed" becomes visible in the audit log (useful when debugging hardware/context issues like the earlier LM Studio context-length failures).
- This is a pure selection-logic change; no new LLM calls, no prompt changes, no config/toggle added. Behavior identical whenever every planet succeeds.
- Next per reviewer priority: **H4** (`calibrate_axes.py` template drift — re-running `build_constants()` drops Phase 1–8 flags), then H5 (g2_sandbox baseline-wave key mismatch) and remaining M/L items.
