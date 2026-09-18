# Phase 8 Segment 4 — Moons × Jester Matrix: moonsON_jesterOFF

**Config:** Moons ON | Jester (Comet) OFF  
**Model:** `qwen3.8-27b` + `text-embedding-allmini`, LM Studio @ 127.0.0.1:1234  
**Scenario:** Q1 (rebel-dominant) ×4 → Q2 (everyman-dominant) ×3 = 7 sessions  
**Pass wall time:** 861.6s   **Comet fired on:** (no session)

## Comet fire line-up
```
session  dominant        comet   trigger
   1     rebel          -       
   2     rebel          -       
   3     rebel          -       
   4     rebel          -       
   5     everyman       -       
   6     everyman       -       
   7     everyman       -       
```

**Expected:** with jester ON, the Jester fires on **session 4** (stagnation, streak > 3) and **does NOT fire again on sessions 5–7** after the dominant switches to everyman (streak resets + cooldown). With jester OFF, no session fires. Any other-session fire is almost certainly the ~2% `random_injection` path (no session_number passed) and is flagged in the table above.

## Phase C verdict matrix (downstream signal)
```
sess  dominant     CAREG EVERY  HERO MAGIC REBEL RULER  SAGE
------------------------------------------------------------
  1    rebel           R     R     R     R     R     R     R
  2    rebel           R     R     R     A     R     R     R
  3    rebel           R     A     A     R     A     R     R
  4    rebel           R     R     A     R     R     R     R
  5    everyman        R     A     R     R     R     R     R
  6    everyman        R     A     R     R     R     R     R
  7    everyman        R     R     R     R     R     R     R
```

**Approve totals:** Q1 block (sess 1–4): [0, 1, 3, 1] per session | Q2 block (sess 5–7): avg 0

## Per-session detail

### Session 1 — dominant `rebel` (144.6s)
- top3: rebel=0.9995, everyman=0.9263, magician=0.9229
- verdicts: APPROVE=0 REDIRECT=7

### Session 2 — dominant `rebel` (127.1s)
- top3: rebel=0.9995, everyman=0.9263, magician=0.9229
- verdicts: APPROVE=1 REDIRECT=6

### Session 3 — dominant `rebel` (113.6s)
- top3: rebel=0.9995, everyman=0.9263, magician=0.9229
- verdicts: APPROVE=3 REDIRECT=4

### Session 4 — dominant `rebel` (125.1s)
- top3: rebel=0.9995, everyman=0.9263, magician=0.9229
- verdicts: APPROVE=1 REDIRECT=6

### Session 5 — dominant `everyman` (117.2s)
- top3: everyman=0.9863, hero=0.9408, magician=0.9111
- verdicts: APPROVE=1 REDIRECT=6

### Session 6 — dominant `everyman` (115.6s)
- top3: everyman=0.9863, hero=0.9408, magician=0.9111
- verdicts: APPROVE=1 REDIRECT=6

### Session 7 — dominant `everyman` (118.2s)
- top3: everyman=0.9863, hero=0.9408, magician=0.9111
- verdicts: APPROVE=0 REDIRECT=7