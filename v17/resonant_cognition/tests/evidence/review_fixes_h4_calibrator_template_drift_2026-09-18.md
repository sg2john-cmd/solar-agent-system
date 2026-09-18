# Review Fix — H4: calibrator template drift (config destruction)

**Segment 4 of the independent blind-review fix pass.** Date: 2026-09-18. Status: **DONE / verified**.

## The bug
`calibrate_axes.py::build_constants()` used to emit `constants.py` from a **fixed f-string template**.
That template had drifted behind the live file across Phases 1–8, so re-running calibration would have
**silently deleted every feature toggle added after Phase 0H**:

- `RESONANCE_MULTIPLIER_ENABLED` / `_THRESHOLD`, `FIELD_POSITION_WEIGHT`, `FIELD_DISTANCE_METRIC`, `SIGMA_SCALE` (Phase 1)
- `MOON_HEMISPHERE_*`, `COMET_TRIGGER_*`, `COMET_CONSECUTIVE_SESSIONS/REFIRE_STEP/MAX_TOKENS` (Phase 3)
- `MEMORY_MASS_BASE`, `DOMINANCE_ZONE_RATIO`, `MEMORY_POSITION_JITTER` (Phase 4)
- `RING_IDLE_BEHAVIOR_*`, `RING_SELF_REVIEW_*` (Phase 6)
- `G1_FILTER_MOONS_ENABLED`, `G2_MAGNITUDE_CAP/ESCAPE_THRESHOLD/SANDBOX_*/TIER2_ANCHOR_MIGRATION` (Phase 7)
- `EMBED_RETRIES`, `EMBED_RETRY_BACKOFF_S`, `EMBEDDING_DIM` (M2 embedding retry)

It also carried two **stale values** that would have been force-reverted:
`WATCHKEEPER_COUNT = 2` (live is 3 — sleep.py self-test asserts ==3, "prevents binary deadlock") and
an absent `RESONANCE_MULTIPLIER_ENABLED` (live is deliberately `True`).

Running the calibrator to refresh just three axis vectors would therefore have wiped all safety rails.

## The fix
Stopped templating entirely. `build_constants()` now:
1. Reads the **current** `constants.py`.
2. Surgically replaces **only** the three `AXIS_* = [...]` vector lines with freshly-calibrated values
   (regex, line-scoped, preserves leading indent + trailing whitespace so output is byte-identical except for the vectors).
3. Raises `RuntimeError` if any expected axis line is missing — it refuses to clobber a malformed file.

Everything else (all toggles, comments, `SEMANTIC_ANCHORS`) passes through verbatim → regenerating is idempotent and non-destructive. Module docstring + `main()` print message updated to match; stale template body removed (`calibrate_axes.py` 329 → 215 lines).

## Verification (NO LM Studio call, live constants.py NOT written)
Ran the template function in isolation only (importing does not trigger `main()`, so no network/file side effects):

```
PASS: calibrate_axes.py parses cleanly (ast.parse)
PASS: old fixed-template body removed (no PLANET_MASSES / {fmt_vec(ax[...])} present)
PASS: 364 non-axis lines byte-for-byte identical to live constants.py
       -> every Phase 1-8 toggle, comment and SEMANTIC_ANCHORS entry survives
PASS: exactly the 3 AXIS_* vectors replaced with freshly-calibrated unit vectors
PASS: spot-checked load-bearing toggles survived (RESONANCE_MULTIPLIER_ENABLED=True,
       WATCHKEEPER_COUNT=3, G1_FILTER_MOONS/COMET/MOON_HEMISPHERE=False, EMBED_RETRIES=3,
       RING_SELF_REVIEW/G2_SANDBOX=False)
PASS: idempotent — re-running build_constants() on its own output is a fixed point
PASS: malformed constants.py (no AXIS_* lines) -> RuntimeError; refuses to clobber
PASS: module imports cleanly; __main__ guard present so import never fires calibration
```

## Why it was tested this way
Running `python -X utf8 calibrate_axes.py` for real would POST to LM Studio MiniLM and overwrite
`constants.py` + planet JSONs. The fix only needs the *string transformation* proven, so it was unit-tested in
isolation with synthetic 384-dim axis vectors — deterministic, offline, no files touched.

## Notes / decisions (not yet user-approved)
- Chose **read-and-replace** over "hardcode the full toggle set into a new template" because it is inherently
  non-drift: future toggles added to `constants.py` are automatically preserved without anyone updating the calibrator.
- Trailing-whitespace/indentation of each axis line is preserved so repeated runs produce byte-stable output.

**Next (remaining review items):** H5 (`g2_sandbox.py::try_candidate()` baseline-wave vec mismatch),
M1 (fragile `dir()` guards in pipeline diagnostics), M3 (`g2_moon_consistency` doc vs code magnitude-only check),
M5 (Gate 3 output only checks chosen planet, not all 7), L1–L5 hygiene (incl. stray repo-root `nul` artifact).
