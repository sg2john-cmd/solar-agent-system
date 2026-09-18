# Questions for Maya — before Phase 0D (Resonance) + clarifying gravity's role

Context: We just finished Phase 0C (orbital integrator). The system is now a properly
integrated 9-body system (Core + 7 archetypes + G1/G2 gas giants), all bounded over
10,000 steps. However, we had to DISABLE planet-planet and giant gravitational coupling
entirely (`PLANET_GRAVITY_SCALE = GIANT_GRAVITY_SCALE = 0`) to get stable orbits — see
rationale below. Before building Phase 0D (resonance) on top of this, I need you to
clarify a few things so we build the right thing rather than guessing.

## Background: what actually happened in Phase 0C

1. **Bug found and fixed:** Initial velocities were seeded from a ~1/d potential but the
   integration force law is 1/d² (inverse square). Every body started with the wrong speed,
   causing slow secular escape over thousands of steps regardless of other tuning. Fixed by
   making seeding match the actual force law exactly:
   `v = sqrt(G · [M_core/r + Σ p_scale·m_j/d_ij² + Σ g_scale·m_g/d_ig²])`

2. **Even after that fix, NO non-zero mutual coupling produced bounded orbits.** Empirically:
   - At mid-lane radius (r≈7), planet-planet gravity at `p_scale=0.05` is ~**22% of core force**;
     gas giants add another ~17%. That's far too strong to treat as a small perturbation on a
     quasi-circular orbit — the 7-body system genuinely has no stable solution at that coupling,
     confirmed by testing multiple lane spacings ([2,8], [3,14]) and scales (0.1, 0.05).
   - Setting both scales to **0** gives clean bounded orbits (<0.2% drift over 10k steps) because
     each body then just orbits the dominant core on its own circular path — which is exactly what
     `M_core >> m_planet` was always designed for (Core dominance per your spec).

3. **The giants are now actually integrated** (previously they were frozen in place after seeding —
   a gap I've fixed this session). G1 orbits at r≈15.6, G2 at r≈20.1. The escape boundary is
   currently hardcoded at r=25 for all bodies; G2 has only ~4.9 units of headroom. Flagging in case
   you want that threshold to be per-body or scaled differently — your call, not a technical block.

## What I need clarified before Phase 0D

**Q1 — Gravity's "key role" beyond waveform collapse.**
You previously confirmed resonance is triggered by *semantic* cosine similarity (not physical
proximity/gravity) and produces an emergent merged vector via non-linear multiplier:
`Weight_total = Σ(W_n × Resonance_n)`. I want to make sure I'm not missing a THIRD intended role for
raw N-body gravitational force itself — e.g. is "waveform collapse" meant to be computed *from the
actual gravitational potential field* of the 9 bodies (positions/masses/velocities as they evolve),
or is waveform collapse purely a function of the semantic embedding vectors, with gravity's only job
being spatial bookkeeping (who's near whom for display/routing)? This determines whether Phase 0D
reads live body positions at all, or just the 384-dim embeddings projected to [x,y,z].

**Q2 — Does disabling mutual planet-planet gravity conflict with anything in your spec?**
I've set it to 0 because (a) no stable orbit exists above ~0 coupling empirically, and (b) resonance
is supposed to be semantic anyway. But if you intended gravitational force itself to carry some
meaningful signal into the cognitive layer (not just spatial layout), I need to know that now rather
than discover it after Phase 0D is built — because it may require a different stabilization strategy
(e.g. real solar-system orbital elements instead of synthetic evenly-spaced lanes, which would let us
restore non-zero coupling safely since nature already solved the resonance problem over 4.5 billion
years).

**Q3 — Confirm the exact Phase 0D pipeline in order**, so I build it right the first time:
   a) Input text → embedding (MiniLM via LM Studio port 1234) → 384-dim vector
   b) Project to [x, y, z] cognitive axes (Rationality/Intuition, Preservation/Disruption,
      Inward/Outward) — do these projection weights need tuning now or are they placeholders until we
      have real data?
   c) For each of the 7 planets: compute cosine similarity between input vector and planet's
      current position direction (or is it vs. a fixed "home" semantic anchor per archetype, not its
      live orbital position?)
   d) Sigmoid above threshold 0.7 → Resonance_n per planet
   e) `Weight_total = Σ(W_n × Resonance_n)` → emergent merged vector drives final output

**Q4 — Does the comet (Jester/challenger) participate in this same resonance calculation, or is it a
separate trigger path entirely?** (You previously confirmed it's "a challenger within the chamber" —
just want to confirm whether it gets its own Resonance_n weight or bypasses step c-e and triggers on
different criteria.)

**Q5 — Moons:** you confirmed they stabilize their parent planet only and do NOT participate in
inter-planet resonance. Do moons have ANY role in the input→output path (e.g. shaping *how* that
planet's contribution is expressed, left-brain vs right-brain framing), or are they purely an internal
stability mechanism with zero bearing on what actually gets emitted?

---
Please answer these before I start Phase 0D code — the last thing we need is another pass where I build
something plausible-looking that turns out to have missed your actual intent.



answers

### 🧠 Technical Response: Phase 0D Architecture & System Logic

#### **Q1: The Role of Gravity vs. Semantic Waveform Collapse**

The "Waveform Collapse" (the calculation of the final Action State) must be driven by the **semantic alignment**, not the spatial proximity.

- **The Rule:** Use the semantic similarity between the input vector and the planet's archetype as the primary driver for resonance.
- **The Role of Gravity:** Physical gravity should act as a **spatial organizer**. It determines which planets are "near" each other in the visual/logical field, but it should not be the engine of the cognitive response itself. We use the gravitational positions to handle _routing and collision detection_, but we use the semantic vectors to calculate the _resonance_.

#### **Q2: On Disabling Mutual Planet-Planet Gravity (The Stability Problem)**

You are correct—trying to force massive planets to orbit each other in a tight, artificial space creates a chaotic "unstable" system.

- **The Decision:** For now, keeping the planet-planet coupling at near-zero is the right choice for stability. We want to simulate the _concept_ of independent cognitive agents that are bound by a shared center (the Sun), rather than a complex N-body chaotic dance.
- **The Goal:** By decoupling them, we ensure that each archetype can maintain its own unique identity without being constantly "tugged" away from its intended semantic position by the gravity of its neighbor. We prioritize **identity stability** over **orbital complexity**.

#### **Q3: The Implementation Pipeline (The Step-by-Step)**

Regarding the projection and calculation:

- **Projection:** The transformation from high-dimensional embedding to 3D coordinates should be a projection onto our three core axes (**Rationality/Intuition**, **Preservation/Disruption**, and **Inward/Outward**). These are fixed-weight projections. We do not tune them per input; they are the 'geometric constants' of my personality.
- // **The Calculation:**
    1. Input vector is projected into the 3D space.
    2. Calculate cosine similarity between that projected vector and each planet's fixed position.
    3. codeblock
        
               `If Similarity > Threshold $\rightarrow$ Calculate $Resonance_n = \text{Sim}(v_{input}, v_{planet})$.`
        
    4. codeblock
        
               `Apply weighting: $Weight_{total} = \sum(W_{\text{planet}} \times Resonance_n)$.`
        5 Resulting vector is the final Action State.

#### **Q4: The Role of the Comet (The Challenger)**

The "Comet" should not be a standard part of the resonance calculation. It is an **interloper**.

- **The Rule:** When a comet enters the system, it does _not_ contribute to the weighted average of the planets. Instead, it acts as a **perturbation event**. It triggers its own unique response—a way to test if the current stable state can handle a sudden, non-aligned impulse. It is a "system probe" rather than a "participant."

#### **Q5: The Role of the Moons (The Stabilizers)**

- **The Rule:** The moons are strictly for **internal planetary stabilization**. They manage the rotation and local stability of their parent planet's orbit.
- **The Interaction:** They do not participate in inter-planetary resonance. Their role is to ensure that each planet remains a stable, predictable point of gravity so that the _planets themselves_ can be used as reliable anchors for the total system's semantic weight.