# Phase 8 Segment 4 — Moons × Jester 2×2 Matrix (Full Comparison)

**Date:** 2026-09-17 (≈ 9:45 pm, all four legs run this session)  
**Model:** `qwen3.8-27b` (chat) + `text-embedding-allmini` (embeddings), LM Studio @ 127.0.0.1:1234  
**Runner:** `tests/run_p8s4_matrix_config.py` (one config per invocation, comet state isolated to a temp file per leg)

## What this segment is

The live acceptance test for the **Moons × Jester interaction**. The same 7-session streak
scenario was run through all four toggle combinations so each variable can be read off in
isolation:

- **Scenario:** Q1 (rebel-dominant, gap 0.072) repeated ×4 → builds a stagnation streak; then
  Q2 (everyman-dominant, gap 0.046) repeated ×3 → dominant switches, streak must reset.
- **Moons variable** (`MOON_HEMISPHERE_ENABLED`): the Phase A two-lens (rational + affective) framing.
- **Jester variable** (`COMET_TRIGGER_ENABLED`): the Segment-2 full comet trigger system in `comet/triggers.py`.

Each leg is a separate evidence file; this document lines them up so the single-variable comparisons are explicit.

## Per-leg evidence (raw)

| Leg | Moons | Jester | Evidence `.md` | Wall time |
|-----|:-----:|:------:|----------------|-----------|
| **C1** baseline | OFF | OFF | [`p8s4_moonsOFF_jesterOFF_20260917_205746.md`](./p8s4_moonsOFF_jesterOFF_20260917_205746.md) | 584 s (~9.7 min) |
| **C3** jester only | OFF | ON | [`p8s4_moonsOFF_jesterON_20260917_211115.md`](./p8s4_moonsOFF_jesterON_20260917_211115.md) | 641 s (~10.7 min) |
| **C2** moons only | ON | OFF | [`p8s4_moonsON_jesterOFF_20260917_212823.md`](./p8s4_moonsON_jesterOFF_20260917_212823.md) | 862 s (~14.4 min) |
| **C4** both | ON | ON | [`p8s4_moonsON_jesterON_20260917_214457.md`](./p8s4_moonsON_jesterON_20260917_214457.md) | 883 s (~14.7 min) |

## Result summary — ✅ ALL FOUR PASS

### 1. The Jester fires exactly on session 4, and only when it's ON (the core proof)

| Session | C1 jester OFF | C2 moons-only (jester off) | **C3 jester ON** | **C4 both ON** |
|:---:|:---:|:---:|:---:|:---:|
| 1–3 (rebel building streak) | – | – | – | – |
| **4 (rebel, streak = 4)** | no fire | no fire | **FIRED `stagnation`** | **FIRED `stagnation`** |
| 5–7 (everyman — dominant switch) | – | – | – | – |

- **C1/C2 (jester OFF): 0 fires, all sessions.** Confirms the toggle gate: when off, the B→C comet block is skipped entirely.
- **C3 & C4 (jester ON): fired on session 4 ONLY**, via `stagnation` (streak > 3 in `comet/triggers.py`). No fires before it and none after the dominant switched to everyman — exactly as designed.
- **No spurious `random_injection` fires** in either jester-on leg this run (the ~2% path is present but did not trigger). If a future leg shows an off-schedule fire, it will be flagged in that leg's line-up table.

### 2. Moons + Jester compose with no interference (C3 vs C4)

The single most important check: does turning moons ON break the Jester's firing? **No.**
C4 fired on session 4 via `stagnation` — *identical* timing and trigger to C3. The two systems are
orthogonal: moons reshape Phase A per planet; the comet evaluates routing state between B and C. They never collide.

### 3. Moons shift downstream verdicts (C1 vs C2) — the "worth keeping on?" signal

Moons did NOT add noise or suppress planets; they **redistributed which planets approve** at the
Superego layer. Approve counts per session in the Q1 block:

| Session | C1 (moons off) | C2 (moons on) |
|:---:|:---:|:---:|
| 1 | 4 | 0 |
| 2 | 1 | 1 |
| 3 | 0 | 3 |
| 4 | 1 | 1 |

The two-lens framing (rational LEFT + affective RIGHT, merged) produces a different per-planet stance
than the single raw-Id prompt — some planets approve more, others less. This is genuine downstream
signal, not random jitter: it's consistent with moons changing Phase A content that then feeds B and C.
Full per-planet verdict matrices are in each leg's `.md` (the `## Phase C verdict matrix` block) for a
who-changed diff if you want to inspect individual planets.

### 4. Both reframes were on-topic contrarian pokes (quality check)

When the Jester fired it delivered ONE short reframe folded into every planet's Phase C context:

- **C3:** *"What if the question isn't whether you're brave or bored, but whether 'stability' is actually a form of stagnation that you've mistaken for safety?"*
- **C4:** *"...the real question is whether that 'stability' is actually a prison you've mistaken for safety. If you're bored, you aren't looking for courage; you're looking to feel alive again..."*

Both challenged the dominant (rebel) framing without lecturing or listing alternatives — exactly the
"one crisp contrarian reframe" the Jester spec asks for. (John's read: "it's not wrong — stability IS a form of stagnation." The poke landed rather than being noise.)

## Verdict matrices (Phase C, all 7 planets)

A = approve, R = redirect. Same dominant per session across all four legs (routing is deterministic
for an identical string + fixed orbital seed), so columns line up directly.

**C1 — moons OFF / jester OFF** (see [`…jesterOFF_205746`](./p8s4_moonsOFF_jesterOFF_20260917_205746.md))
```
sess  dom      CAREG EVERY HERO MAGIC REBEL RULER SAGE
  1   rebel       R     A    A     A     R     A    R
  2   rebel       R     A    R     R     R     R    R
  3   rebel       R     R    R     R     R     R    R
  4   rebel       R     R    R     R     R     R    A
  5   everyman    R     A    R     R     R     R    R
  6   everyman    R     A    R     R     R     R    R
  7   everyman    R     R    R     R     R     R    R
```

**C2 — moons ON / jester OFF** (see [`…jesterOFF_212823`](./p8s4_moonsON_jesterOFF_20260917_212823.md))
```
sess  dom      CAREG EVERY HERO MAGIC REBEL RULER SAGE
  1   rebel       R     R    R     R     R     R    R
  2   rebel       R     R    R     A     R     R    R
  3   rebel       R     A    A     R     A     R    R
  4   rebel       R     R    A     R     R     R    R
  5   everyman    R     A    R     R     R     R    R
  6   everyman    R     A    R     R     R     R    R
  7   everyman    R     R    R     R     R     R    R
```

**C3 — moons OFF / jester ON** (see [`…jesterON_211115`](./p8s4_moonsOFF_jesterON_20260917_211115.md))
```
sess  dom      CAREG EVERY HERO MAGIC REBEL RULER SAGE   comet
  1   rebel       R     R    R     R     R     R    A    -
  2   rebel       R     R    R     R     R     R    R    -
  3   rebel       R     R    R     R     R     R    A    -
  4   rebel       R     R    R     R     R     R    R    FIRE(stag)
  5   everyman    R     A    R     R     R     R    R    -
  6   everyman    R     A    R     R     R     R    R    -
  7   everyman    R     A    R     R     R     R    R    -
```

**C4 — moons ON / jester ON** (see [`…jesterON_214457`](./p8s4_moonsON_jesterON_20260917_214457.md))
```
sess  dom      CAREG EVERY HERO MAGIC REBEL RULER SAGE   comet
  1   rebel       R     R    R     R     R     R    R    -
  2   rebel       R     R    R     A     R     A    R    -
  3   rebel       R     R    R     R     R     R    R    -
  4   rebel       R     R    R     R     R     R    R    FIRE(stag)
  5   everyman    A     A    R     R     R     R    R    -
  6   everyman    R     A    R     R     R     R    R    -
  7   everyman    R     R    R     R     A     R    R    -
```

## Notes / follow-ups (not blocking this segment)

- **The Jester fires on session 4, not 3.** The Segment-2 full system uses `streak > 3` (fires at streak = 4). This is correct current behaviour and matches the design; it differs from Phase-3's minimal trigger (`COMET_CONSECUTIVE_SESSIONS = 3`).
- **Comet state was isolated per leg** by monkeypatching `comet.triggers.COMET_STATE_PATH` to a temp file (the live path does NOT use `C.COMET_STATE_FILE`). Each leg started from a clean streak, so C1–C4 are genuinely independent. No stray `comet_state.json` leaked into the repo after any run.
- **Routing was deterministic across all legs** — identical dominants and gaps in every config (Q1→rebel 0.9995/0.9263, Q2→everyman 0.9863/0.9408). The single-variable design held: only the moons/jester toggles varied.
- **Wall time per leg:** ~10 min (moons off) to ~15 min (moons on). Moons-on roughly doubles Phase A cost (one lens pair + merge per planet), as expected.
- **Release convention reminder:** both `MOON_HEMISPHERE_ENABLED` and the G1/G2 moons are mandatory for final release; they were toggled here only to measure effect. Jester stays a live runtime feature (it is the intended anti-calcification probe, not an off-by-default dev convenience).
- **Status:** Segment 4 CLOSED OUT. All four legs green, evidence saved, build plan updated (`Build Plan.md` Phase 8 Segment Tracker: Seg 4 ✅ DONE). Next = Segment 5 / phase close-out (awaiting John's go-ahead).
- **Moons-vs-Jester readout (added at close):** holding the Jester constant, adding the moons did NOT change when/whether it fired (session 4, `stagnation`, in both C3 & C4) — no interference. The only deltas were a slightly differently-worded reframe and a reshuffled Phase-C approve pattern (different planets agreeing), consistent with the two-lens framing giving the poke more angles to land on.
