# Phase 8 Segment 4 — Moons × Jester Matrix: moonsON_jesterON

**Config:** Moons ON | Jester (Comet) ON  
**Model:** `qwen3.8-27b` + `text-embedding-allmini`, LM Studio @ 127.0.0.1:1234  
**Scenario:** Q1 (rebel-dominant) ×4 → Q2 (everyman-dominant) ×3 = 7 sessions  
**Pass wall time:** 882.8s   **Comet fired on:** 4

## Comet fire line-up
```
session  dominant        comet   trigger
   1     rebel          -       
   2     rebel          -       
   3     rebel          -       
   4     rebel          FIRED   stagnation
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
  2    rebel           R     R     R     A     R     A     R
  3    rebel           R     R     R     R     R     R     R
  4    rebel           R     R     R     R     R     R     R
  5    everyman        A     A     R     R     R     R     R
  6    everyman        R     A     R     R     R     R     R
  7    everyman        R     R     R     R     A     R     R
```

**Approve totals:** Q1 block (sess 1–4): [0, 2, 0, 0] per session | Q2 block (sess 5–7): avg 1

## Per-session detail

### Session 1 — dominant `rebel` (125.1s)
- top3: rebel=0.9995, everyman=0.9263, magician=0.9229
- verdicts: APPROVE=0 REDIRECT=7

### Session 2 — dominant `rebel` (123.8s)
- top3: rebel=0.9995, everyman=0.9263, magician=0.9229
- verdicts: APPROVE=2 REDIRECT=5

### Session 3 — dominant `rebel` (128.5s)
- top3: rebel=0.9995, everyman=0.9263, magician=0.9229
- verdicts: APPROVE=0 REDIRECT=7

### Session 4 — dominant `rebel` (139.8s)
- top3: rebel=0.9995, everyman=0.9263, magician=0.9229
- verdicts: APPROVE=0 REDIRECT=7
- **COMET FIRED** — trigger `stagnation`
  - reframe: You’re asking how much *risk* you can survive, but the real question is whether that "stability" is actually a prison you’ve mistaken for safety. If you’re bored, you aren’t looking for courage; you’re looking to feel alive again—so don’t a…

### Session 5 — dominant `everyman` (120.2s)
- top3: everyman=0.9863, hero=0.9408, magician=0.9111
- verdicts: APPROVE=2 REDIRECT=5

### Session 6 — dominant `everyman` (125.3s)
- top3: everyman=0.9863, hero=0.9408, magician=0.9111
- verdicts: APPROVE=1 REDIRECT=6

### Session 7 — dominant `everyman` (119.9s)
- top3: everyman=0.9863, hero=0.9408, magician=0.9111
- verdicts: APPROVE=1 REDIRECT=6