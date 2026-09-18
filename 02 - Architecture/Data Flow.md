# Data Flow — v17

## Waking Cycle (Single Input)

```
[User input / external stimulus]
        │
        ▼
┌─────────────────────┐
│  RING INTAKE FACET    │  ← Fast, cheap. Small model or pattern logic.
│  (front door)         │     Part of the Ring — NOT G1.
│  PII scrub + clarity   │     Classifies type, strips noise.
│  + input-type          │     Dissonance pre-read: pre-loads
│  + dissonance pre-read │     M_core if ΔD spike detected.
└─────────────────────┘
        │
        ▼
   (G1's three moons work separately, during sleep Pass IV,
    guarding long-term knowledge as it commits into G1's archive —
    they do NOT sit in this waking input path.)
        │
        ▼
[Pre-filtered core signal + context tags]
        │
        ▼
┌─────────────────────┐
│  CORE ENGINE          │
│  - Compute input vector in 3-axis space (X:R↔I, Y:P↔D, Z:In↔Out)
│  - Calculate stress distances to all 7 planets
│  - DETECT SPIKES → select dominant + secondary planets (NOT random)
│  - Apply phase cancellation damping from moons
│  - Wave-form collapse → A_final vector
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  COGNITIVE CHAMBER    │  ← Sequential LLM passes (NOT one giant prompt)
│  Pass 1: Dominant planet's Id/Ego/Superego dialogue
│         (using its moon memory + tagged G1 context)
│  Pass 2: Secondary planet reviews Pass 1 output
│  Pass 3: Synthesis → Unified Response
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  THE RING (interface) │  ← "Maya" wraps the response in its persona,
│                         │     checks against its own memory, formats output
└─────────────────────┘
        │
        ▼
[Response to user]

--- Simultaneously ---
[Experience fragments committed to: dominant planet's moons, Ring memory, memory history array]
```

## Sleep Cycle (Triggered by `sleep` or idle timeout)

```
[External inputs LOCKED OUT]
        │
        ▼
┌─────────────────────┐
│  PASS I: REM REPLAY   │
│  - Feed stored waking history back through planetary manifolds
│  - Planets re-evaluate the day's interactions offline
│  - Identify deep correlations missed during real-time processing
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  PASS II: PRUNING &   │  ← Black Hole compression
│  COMPRESSION          │     Stagnant data → extreme geometric compression
│                        │     Low-resonance noise → W→0 (permanently nullified)
│                        │     High-value paths → mean variance tensor extraction
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  PASS III: WHITE HOLE  │  ← Parameter shift (NOT just a summary)
│  AWAKENING            │     - Shift C_core position permanently
│                        │     - Adjust planet base coordinates (drift)
│                        │     - Modify moon offset multipliers if warranted
│                        │     - Update M_base if core calibration needed
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  PASS IV: RING REVIEW │  ← Gas Giant ring processing
│                        │     G1 Ring: Review knowledge candidates
│                        │       → Commit / Modify / Reject (via full engine debate)
│                        │     G2 Ring: Review self-modification candidates
│                        │       → Commit inward / Eject outward based on field stability
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  PASS V: DARK ENERGY  │  ← Mass distribution
│  DISTRIBUTION         │     Scan all planets for bulking (> threshold)
│                        │     Shed excess → Deep Swarm Archive (radial placement)
│                        │     Radiate shed weight as anti-gravity expansion
└─────────────────────┘
        │
        ▼
[System wakes. C_core has moved. Planets have drifted. The field is different.]
```

## Monthly Self-Review Cycle

```
[Triggered monthly or manually]
        │
        ▼
[Gas Giant 2 generates self-report: "What changed, to what degree, why I think it was reasonable"]
        │
        ▼
[Routed through full 7-planet engine for debate]
│  - Logic Facet: Is the change internally consistent?
│  - Skepticism Filter: Is this actually helpful or just drift?
│  - Safety Guard: Does it encroach on core boundaries?
│  - Empathy Resonance: Does it still serve the user well?
│  - ...all planets weigh in...
        │
        ▼
[Wave-form collapse → verdict: keep / modify / reverse]
        │
        ▼
[Log stored in G2 Ring for next month's continuity reference]
```

## Key Differences from v16 Data Flow
- v16: random planet selection → single LLM prompt asking model to roleplay 3 phases → extract text
- v17: spike-driven selection → sequential actual LLM passes with real context between them → genuine multi-agent reasoning
- v16 sleep: summarize into 3 sentences, write string to all vaults, print "awakening successful"
- v17 sleep: actually mutate numeric parameters (C_core, planet coords, moon offsets), process ring candidates, redistribute mass

## Links
- [[Home]]
- [[02 - Architecture/v17 System Overview|v17 Overview]]
- [[02 - Architecture/Sleep Cycle|Sleep Cycle Detail]]
- [[03 - Implementation/v16 Postmortem — What Went Wrong|What v16 got wrong]]
