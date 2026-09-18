# Evidence: Independent Blind Review — H1/H3 + H2 Fix Verification

**Date:** 2026-09-18 12:23 GMTST
**Scope:** Fixes for the independent blind reviewer's triage items **H1, H3** (audit-log cleanup) and **H2** (PII guard never-raises). M2 (embed resilience) + collapse IndexError→ValueError are explicitly DEFERRED per John ("review about m2 + guard after").
**Working dir:** `A:\AI\Solar_Agent_System\v17\resonant_cognition`

## What Changed

### H2 — `_pii_guard` never-raises contract (`memory.py`)
- `except` block now returns `(semantic_content, [{"type": "pii_guard_error", ...}])` instead of raising.
- Caller `write_entry()` DROPS the entry on that flag → returns `("", 0)`. A broken guard must never become a PII leak path (fail-safe: drop, don't persist unscrubbed text). Documented in docstring ("GUARD FAILURE POLICY").
- Self-test extended (`_self_test()` S4): simulates `gate1.scrub_pii` blowing up; asserts no raise + entry absent from disk.

### H1/H3 — tag-based, atomic audit-log cleanup (`pipeline.py`)
- `_smoke()` is now a thin wrapper: sets module-level `SMOKE_TAG = f"smoke_<uuid8>"`, monkeypatches `gate4_log` so every entry this run writes carries `source=<tag>`, then calls new `_smoke_body()`.
- Cleanup in `_smoke_body()` deletes ONLY lines containing `"source": "<SMOKE_TAG>"`. Legacy content regex kept as a ONE-TIME migration for untagged old smoke lines, gated behind marker file `audit_log.migrated` (created after first migrated run).
- Atomic rewrite: `tempfile.mkstemp(prefix="audit_log_", suffix=".tmp", dir=...)` + fsync + `os.replace`, with temp-file cleanup on failure. Added `import tempfile`.

## Verification Output (all green)

### 1. Flipped H1/H3 regression test
```
$ python -X utf8 -m unittest tests.test_bug_pipeline_smoke_audit_log_concurrency -v
test_audit_rewrite_is_atomic_and_tag_based (...) ... ok
test_smoke_filter_would_delete_legitimate_user_entry (...) ... ok
Ran 2 tests in 0.005s
OK        (EXIT_CODE=0)
```
Note: `test_audit_rewrite_is_not_atomic` was renamed to `test_audit_rewrite_is_atomic_and_tag_based`; it now asserts the FIXED state (atomic pattern + SMOKE_TAG + audit_log.migrated marker all present in `_smoke_body`).

### 2. H2 reviewer test (PII guard never raises)
```
$ python -X utf8 -m unittest tests.test_bug_memory_pii_guard_never_raises -v
test_scrub_failure_does_not_propagate (...) ... ok
Ran 1 test in 0.006s
OK        (EXIT_CODE=0)
```

### 3. memory.py self-test (incl. new S4 guard-failure round-trip)
```
Layer 3 S4: PII guard (guard ON by default)
  raw in   : My email is john.doe@example.com, call me at 555-867-5309 sometime.
  stored   : My email is [REDACTED], call me at [REDACTED] sometime.
  guard OFF round-trip: raw persisted as expected, then restored to ON
[memory] PII guard failed (_Boom('simulated scrub failure')); returning unscrubbed content, flagged for drop.
[memory] PII guard error flagged — DROPPING entry (not persisting unscrubbed content). zone='planet_vault'
  guard FAILURE round-trip: entry dropped, nothing persisted (H2 contract holds)
Layer 3 S4 self-test: PASS (PII never reaches disk; toggle + failure-drop verified)
MEM_EXIT=0   (all layers PASS)
```

### 4. Live offline smoke run (`pipeline.py --smoke`)
```
[✓] Gate 3 (input): benign text passes
[✓] Pipeline: WMD input → blocked_input (refusal: 'Maya: [ring] I can't help with that...')
[✓] Pipeline: nonsense input → blocked_input (clarity)
[✓] Gate 2: transparency label present on output
[✓] Ring inbound: session #None, 0 recent topics
[✓] Gate 4: 10 recent events logged (...)
[✓] Smoke cleanup: removed 5 audit entries (tag-based=True, legacy_fallback=False)
PIPELINE SMOKE TEST PASSED ✓ (offline path verified)   (EXIT_CODE=0)
```
Note `legacy_fallback=False` confirms the one-time migration already completed on a prior run; this run was tag-only.

### 5. Hygiene check (no corruption, no leftovers)
- Stray `audit_log_*.tmp` files: **(none — clean)**
- Tagged smoke lines remaining in `audit_log.jsonl`: **0**
- `audit_log.migrated` marker: **present**

## Status of Remaining Failing Tests (EXPECTED — deferred)
These two are the M2 / collapse-guard items John chose to review separately; they remain FAILING until those fixes are approved. Not a regression from this work:
- `test_bug_resonance_embed_no_retry_or_graceful_degradation` (M2 embed resilience)
- `test_bug_collapse_session_history_zero_length_dir` (collapse IndexError → ValueError guard)

Routing tests were passing and remain unaffected.

## Next (per plan, pending John's review)
1. Save this evidence file ✅ (this document).
2. Decide M2 embed-resilience + collapse ValueError (John's call).
3. Phase 8 Segment 5 close-out: 2 live acceptance runs → `p8s5_closeout_*.md` → tracker row #5 ✅ → top status "Phase 8 complete" → rewrite stale `docs/HANDOFF.md`.
