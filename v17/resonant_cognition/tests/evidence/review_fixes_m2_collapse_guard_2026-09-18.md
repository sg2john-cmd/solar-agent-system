# Evidence: Independent Blind Review — M2 (embed resilience) + Collapse-Guard Verification

**Date:** 2026-09-18 12:46 GMTST
**Scope:** Fixes for the independent blind reviewer's triage items **M2** (embedding retry / graceful degradation) and the **collapse session_history dir-length guard**. H1/H3 + H2 were verified separately (`review_fixes_h1h3_h2_2026-09-18.md`).
**Working dir:** `A:\AI\Solar_Agent_System\v17\resonant_cognition`

## What Changed

### M2 — bounded retry + domain exception (`constants.py`, `resonance.py`)
- `constants.py` (LM Studio section): added `EMBED_RETRIES = 3` (**GUESS**), `EMBED_RETRY_BACKOFF_S = 1.0` (**GUESS**, seconds, base for exponential backoff), and `EMBEDDING_DIM = 384` (hardcoded — NOT derived from a later-defined axis constant to avoid a forward-reference bug).
- `resonance.py`: added imports (`time`, `urllib.error`, `_json_module`) + new `class EmbeddingUnavailableError(RuntimeError)` + shared helper `_post_with_retry(payload, *, op)`. Both `embed()` and `_embed_batch()` now route through it. The public return shape (`list[float]` / `list[list[float]]`) is UNCHANGED for every existing caller; the only new behaviour is that a transient LM Studio hiccup (model reloading between calls, brief connection-refused, one-off 5xx, truncated JSON) retries with exponential backoff before raising `EmbeddingUnavailableError` instead of leaking a raw `urllib.error.URLError`.

### Collapse guard — session_history dir-length validation (`collapse.py`)
- In `run_collapse()`'s session_history block: each context wave's `dir` is validated against `C.EMBEDDING_DIM` BEFORE it enters the vector math. A zero/short dir would otherwise flow into `_unit()` and then silently truncate the zip-based consensus sum to the shortest operand (garbage or a later IndexError).
- Policy: **EMPTY (0-len) → skip + log warning** (a failed embed that persisted an empty `question_vec` must not poison the whole field); **non-empty but wrong length → raise `ValueError` early** (real bug in whatever produced the history, surfaced loudly rather than silently dropped).

## Verification Output (all green)

### 1. Flipped M2 reviewer test
```
$ python -X utf8 -m unittest tests.test_bug_resonance_embed_no_retry_or_graceful_degradation -v
... ok   (3 tests: closed-port raises EmbeddingUnavailableError; batch same contract; retry+exception exposed)
Ran 3 tests in ...
OK        (EXIT_CODE=0)
```
Live backoff observed during the run (closed local port, so it genuinely retried):
```
[resonance] embed: attempt 1/3 failed (URLError(ConnectionRefusedError(10061, ...))); retrying in 1.0s
[resonance] embed: attempt 2/3 failed (...); retrying in 2.0s
[resonance] _embed_batch: attempt 1/3 failed (...); retrying in 1.0s
[resonance] _embed_batch: attempt 2/3 failed (...); retrying in 2.0s
```

### 2. Flipped collapse-guard reviewer test
```
$ python -X utf8 -m unittest tests.test_bug_collapse_session_history_zero_length_dir -v
... ok   (empty-dir skips, _ctx_0 absent; wrong-length renamed to test_mismatched_length_context_dir_raises_valueerror)
Ran 2 tests in ...
OK        (EXIT_CODE=0)
```
Live warning observed:
```
[collapse] WARNING: session_history[0] has an EMPTY dir; skipping this context wave (a failed embed must not poison the superposition).
```

### 3. Combined run of both flipped files
```
$ python -X utf8 -m unittest tests.test_bug_resonance_embed_no_retry_or_graceful_degradation \
      tests.test_bug_collapse_session_history_zero_length_dir -v
Ran 5 tests in 18.363s
OK        (EXIT_CODE=0)
```

### 4. Full discovery sweep (no regressions to M2/guard from this work)
At the moment these two were verified, the full suite still carried the 3 routing failures that pre-dated them (fixed in `review_fixes_routing_*.md`, same date). After ALL fixes: `Ran 15 tests ... OK` (see that file for the post-fix sweep).

## GUESS values to confirm with John
- `EMBED_RETRIES = 3` and `EMBED_RETRY_BACKOFF_S = 1.0s` are **my guesses**, flagged in code comments. If you have a preferred retry count / backoff, swap them before this is frozen into the release notes.

## Status
Both M2 + collapse-guard fixes landed, both reviewer tests flipped to green (same convention as H1/H3), and no caller return-shape changed. Not a regression source for anything else in the suite.
