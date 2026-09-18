# Test Suite — Resonant Cognition v17

Concrete evidence of proof-of-concept for each phase/segment. Each test file is
self-contained, prints clear PASS/FAIL lines, and exits with code 0 (all pass)
or 1 (any failure). Designed to be re-run as the system grows — regressions show up here first.

## Running Tests

All tests require LM Studio running at `127.0.0.1:1234` with both the embedding model
(`text-embedding-allmini`) and a main chat model loaded.

```bash
# Run a single phase's test suite:
python -X utf8 tests/test_phase_a.py      # Phase 3 Seg 1 — Id Fires (5 runs / ~28 LLM calls)
python -X utf8 tests/test_phase_b.py      # Phase 3 Seg 2 — Ego Synthesis (1 A+B run / 14 LLM calls)
python -X utf8 tests/test_routing.py       # Phase 1 — Routing/spike detection (embedding only)

# Or run the top-level runner for everything:
python -X utf8 tests/run_all.py
```

## Test Files by Phase

| File | Phase / Segment | What it proves | LLM calls? |
|------|-----------------|----------------|------------|
| `test_phase_a.py` | P3 Seg 1 — Id Fires | All-7 emit, distinct voices, archetype signatures, no-silence invariant, timing budget | Yes (~28) |
| `test_phase_b.py` | P3 Seg 2 — Ego Synthesis | All-7 emit in B, planets name each other (core claim), B≠A (no parrot), agree+pushback language, A+B timing | Yes (14) |
| `test_phase_c.py` | P3 Seg 3 — Superego / Regulatory Review | Pipeline stability (6 runs ×7 valid verdicts), no-silence + not-uniform (anti-majority), **dependency redirects strictly MORE than neutral** (core claim), redirects are gravity-not-walls | Yes (~126) |
| `test_routing.py` | **Phase 1 — COMPLETE** (all 4 segments) | **20/20 checks PASS:** field centers move with FIELD_POSITION_WEIGHT knob, per-planet weights all-7-nonzero on every sample, routed consensus differs from Phase-0 while `routed_weights=None` stays byte-identical, Q4 resonance multiplier gentle + reversible, Ring Intake PII/garbage filter, **equal-mass/sigma A/B: top-2 ranking identical BASE vs pure-geometry NEUTRAL** (live geometry drives ranking; mass/σ fine-tune only) | No (embedding only) |
| `test_multi.py` | Phase 0D — Collapse | 5-scenario waveform: multi/creative, focused, moral-dilemma, chaos, quiet-factual | No (vector math) |
| `test_multiturn.py` | Phase 0F — Memory | Tension shifts across repeated questions (+125% observed) | No (embedding only) |
| `test_comet_trigger.py` | P3 Seg 4 — Comet B→C basic trigger (LOGIC) | Streak fires exactly on N-th (3rd) straight session, streak-break resets, no-dominant/corrupt-state graceful reset, dominant-planet selection, prompt well-formedness, default toggle OFF | No (pure logic) |
| `test_comet_llm.py` | P3 Seg 4 — Comet B→C basic trigger (LLM half) | End-to-end with REAL routed weights + live model: fires EXACTLY on the 3rd consecutive same-dominant session, non-empty contrarian reframe produced, injected voice does NOT break Phase C verdicts (21/21 valid), different-dominant question resets streak and does NOT fire | Yes (~90) |
| `test_phase_a_moons.py` | P3 Seg 5 — Moon-hemisphere two-lens framing (LLM) | Moons toggle ON: all-7 merged Id responses non-empty every run, LEFT/RIGHT lenses genuinely distinct (21/21), merge is NOT an echo of either single lens (weave did real work), anti-silence invariant holds in moons mode | Yes (~63) |
| `test_sleep.py` | **Phase 5 — COMPLETE** (closes the phase; S8 relabelled **S7b**, ratified by John 2026-09-18) | **9/9 checks PASS:** copies live `planets/`, `core/`, `memory/`, `ring/`, `core_laws.json`, `gates_config.json` to a temp dir (live files stay read-only, hash-verified untouched at end of run), then runs real `deep_sleep()` against that copy — all 7 planets + core move on disk (`state_changed=True`, the v16 failure #2 signal); cognitive_mode stays unchanged with no G2 suggestion; REAL `core_laws.json`/`gates_config.json` byte-identical; semantic anchors untouched (identity clobber guard). TEST 2 is a negative control proving the check can FAIL: zero-input jitter run still moves positions, and an identity-commit simulation (monkeypatched `_apply_commit_to_disk`) correctly registers as "no change" instead of falsely passing | No (zero LLM) |
| `test_memory_write.py` | **Phase 4 — COMPLETE** (all 5 segments) | **21/21 checks PASS:** one live chamber session → memory entry written to disk NEAR dominant planet's orbital position (within jitter cap, proves "identity travels with position"); restart-recovery from disk alone (no amnesia); PII held on ALL store files — Layer A: cleaned turn text has no raw values anywhere; Layer B: guard fired in isolation on RAW input → `pii_redacted_types` audit field present listing TYPES only (`['phone_us','email']`), `[REDACTED]` token where scrubbed, raw email+phone in NO store file; decay sweep on real entries (300-day-old sinks to compression queue, fresh periphery survives) | Yes (~30 / ~85s) |

## Observational Runs (NOT pass/fail tests — human-review evidence)

These are `run_*` runners, **not** the self-checking `test_*` files above. They make many LLM calls to produce a *transcript* for John to read and judge by eye; they print what happened but do not assert PASS/FAIL against a threshold (no exit-code gate). Keep them named `run_` so `run_all.py` doesn't treat them as graded tests.

| File | What it produces | LLM calls? |
|------|------------------|------------|
| `run_complex_chamber.py` | Full A+B+C chamber transcript over 10 complex questions (moons OFF), one dated sample in `evidence/complex_chamber_*` | Yes (~210) |
| `run_complex_chamber_ab.py` | **Moons A/B comparison:** same 10 questions run twice — moons OFF then moons ON (comet forced OFF both passes so the only variable is moons). Writes two full transcripts + a side-by-side `evidence/complex_ab_comparison_*` with verdict matrices and a per-question shift summary. Restores both toggles to OFF in `finally`. | Yes (~420) |
| `run_e2e_light.py` | **Light end-to-end pipeline runner (the "one question through the whole system" proof-of-concept artifact):** chains every ALREADY-BUILT piece in order — Ring Intake (`gate1_filter`) → routing+collapse (`routed_collapse`, all 7 waves) → full chamber A+B+C (`run_phase_a_b_c`). Segment 2 suite fires three prompts covering all three intake outcomes: **A** normal question (full happy path), **B** PII line (email scrubbed but still coherent → routes through), **C** char-spam garbage (rejected at Ring Intake, quiet-but-logging, zero LLM calls). Each run writes one dated labelled transcript + prints an anti-silence self-check. No exit-code gate. | Yes (~168 = 2 full chamber runs; C is free) |

- **Windows launch:** John runs these via `run_ab.bat` → `_run_ab_tee.ps1`, which tees the console into a UTF-8 log (PowerShell's default `Tee-Object` is UTF-16 and mangles em-dashes/planet names in editors). The `.bat` exists because this dev shell is bash but John runs Windows cmd — plain `python ... | tee` won't work on his side.
- **Evidence:** the moons A/B deliverables are `tests/evidence/complex_ab_comparison_<timestamp>.txt` (+ matching `complex_ab_moonsOFF_*`, `complex_ab_moonsON_*`). Two runs so far:
  - Run 1 — `..._20260916_225402.txt`: **26 → 15** total APPROVE verdicts, ≥1 planet shifted on all 10/10 questions; anti-silence held.
  - Run 2 — `..._20260917_095647.txt` (launched detached/unbuffered): **18 → 14** APPROVE, ≥1 planet shifted on 9/10 (Q7 unchanged); anti-silence held again.

  Two-run pattern confirmed: moons ON tilts the chamber more regulatory/corrective without silencing any planet. See **D-022**. (Note: `complex_ab_run_live.log` is UTF-16 from Run 1's original `Tee-Object`; the `.ps1` wrapper was fixed afterwards — prefer it or a detached unbuffered launch for clean UTF-8 logs.)
- **Phase 5 sleep-cycle evidence** (`sleep.py` module self-tests S1–S7a + `test_sleep.py` critical acceptance test (originally "S8", relabelled **S7b**), all zero LLM):
  - Full-suite run (S1–S6 + S7a in one file): `s7a_moons_integrity_selftest_20260917_133637.log` — Segment 7a block: G1/G2 moons, committed_entries, self-model moons, sandbox mechanism, growth_policy, and both giants' ring_buffer entries all untouched through a real `deep_sleep()`; `core_laws.json`/`gates_config.json` byte-identical.
  - S7b acceptance test (the Build Plan's "record file A → trigger deep sleep → values must be numerically different" check, run against a copy of the LIVE seed snapshot): first clean run after the Part B negative-control fix `s7b_acceptance_selftest_20260917_134830.log`, repeat confirmations `..._134846.log` and `..._135012.log`. All three: 9/9 checks passed. (No failing S7b log was kept — the Part B failure was caught and fixed within the same session before any evidence file was treated as final.)
  - Live-runtime half of the acceptance test (typing during sleep → watchkeeper responds; next session routes on new positions) is Phase 8 integration scope, not a disk-state check.
- **Phase 1 routing evidence:** `tests/evidence/routing_segment4_<timestamp>.log` — full 20/20 PASS output from `test_routing.py` including the geometry-vs-constants A/B table. First (and closing) run: `routing_segment4_20260917_101208.log`. Phase 1 is now COMPLETE; see Build Plan Phase 1 completion notes.

### Light end-to-end evidence (`run_e2e_light.py`)

One labelled transcript per prompt, written to `tests/evidence/`, grouping the three layers (RAW INPUT → RING INTAKE → ROUTING+COLLAPSE → CHAMBER A/B/C) plus a trailing anti-silence self-check. This is the headline "watch it do the thing" artifact for the git-repo proof-of-concept.

- **Segment 1 smoke** (one normal prompt, happy path): `e2e_light_20260917_102349.txt`. All 7 planets emitted in A/B/C; Phase C came back REDIRECT × 7 (corrective tilt — a known observation, not an error).
- **Segment 2 suite** (`run_e2e_light.py`, run id `20260917_103732`): three distinct transcripts + one console log:
  - `e2e_light_a_normal_20260917_103732.txt` — happy path, all 7 planets non-silenced at every layer; Phase C REDIRECT × 7.
  - `e2e_light_b_pii_scrub_20260917_103732.txt` — PII line: email redacted to `[REDACTED]`, clarity 0.729 → still routed through the full chamber (proves scrub-without-reject on a coherent prompt).
  - `e2e_light_c_garbage_reject_20260917_103732.txt` — char-spam: rejected at Ring Intake (clarity 0.05), quiet-but-logging, zero LLM calls.
  - Console log: `e2e_light_segment2_run.log`.

  **Note:** an email-bearing line is *not* auto-rejected — gate1's clarity check scores it coherent enough to proceed (that's why B routes through). A distinct out-path per prompt was added so two fast runs can't collide on the same second and overwrite each other (caught during Segment 2's first run, before evidence was lost).

## Future Tests (will appear as we build)

- `test_comet_full.py` — P8: full 4-condition trigger refinement (stagnation / over-seriousness / binary convergence / random 2%)

## Conventions

- Each test file is standalone (no shared fixtures yet; will refactor if we hit >10 files).
- Tests that make LLM calls are marked in the table above — they take longer and need the model loaded.
- Soft checks (keyword matching, etc.) use a lower threshold to account for temperature-driven paraphrasing.
- All tests print a summary line: `RESULTS: N passed, M failed` followed by ✅ or ⚠️.
- **Evidence logs:** long LLM suites should be tee'd into `tests/evidence/` as a timestamped log for proof-of-concept records, e.g. `tests/evidence/evidence_phase_c_<timestamp>.log`. These are captured output (one dated sample per run), not source — keep them to build up the pattern over time; prune only if they pile up.
  - The `.py` files are the repeatable *recipe*; each log in `evidence/` is a dated *measurement*. Both belong in the repo: tests prove how we verify, logs prove what actually happened across runs.
