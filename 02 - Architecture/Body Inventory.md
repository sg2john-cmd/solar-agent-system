# Body Inventory — v17

Complete list of all bodies in the system, their roles, and whether they change over time.

## Fixed / Permanent

| Body | Count | Role | Changes? |
|---|---|---|---|
| **Core Star** (C_core) | 1 | The "3 Laws" — moral gravity anchor. Variable mass via `M_core = M_base + α(ΔD)^β`. Shifts position after sleep cycles. | Position shifts post-sleep; mass varies per input |
| **Gas Giant 1** | 1 | Permanent structural knowledge base. Operational axioms, system grammar, foundational truths. | Content grows slowly via ring review; position fixed |
| **G1 Ring** (buffer) | 1 | Incubation zone for new knowledge candidates. Entries here are "untrusted" until they pass the full-engine review debate. | Churns constantly; entries either commit inward or eject outward |

## Evolving / Dynamic

| Body | Count | Role | Changes? |
|---|---|---|---|
| **Gas Giant 2** | 1 | The mind's own evolving subconscious. Stores self-observed patterns, behavioral drift notes. Starts empty. | Grows and decays over weeks/months via sleep cycles |
| **G2 Ring** (buffer) | 1 | Buffer for self-modification candidates before they're committed to Gas Giant 2. Micro-adjustments pass at low mass; structural commits wait for sleep. | Same incubation mechanics as G1 ring |
| **Planets** | 7 | Jungian cognitive archetypes: Sage, Hero, Caregiver, Rebel, Magician, Everyman, Ruler. Each is a distinct *cognitive process* (different temp/context/prompt structure), not a role-play character. They conflict and resolve via interference. | Positions drift over sessions. Cognitive mode parameters evolve through sleep Pass IV. |
| **Planet Moons** (L/R) | 14 | Short-term working memory per planet. Left = rational/empirical, Right = intuitive/fluid. Flush to Ring when planet goes inactive. | Constant churn — buffer only |

## User-Facing

| Body | Count | Role | Changes? |
|---|---|---|---|
| **The Ring** (interface) | 1 | "Maya" — the persistent user-facing persona. Houses the full main-persona neural net: interchangeable/customizable front-end, user history + preferences (Ring Memory vault), and the long-term swarm with its own decay rate. Also owns the **Intake facet**: every inbound prompt is PII-scrubbed + clarity/type-checked + dissonance pre-read here before it reaches the planets. Runs on idle while the engine operates in background. | Personality evolves slowly; memory managed via Dark Energy distribution |

### The Ring — Intake Facet (front door)
Stationary sub-layer of the Ring that handles **inbound** prompts (the Ring's outbound side wraps responses). Fast, cheap, no 27B call:
- **PII scrub** on raw text before it touches any other body or disk
- **Clarity / signal check** — is this coherent? (garbage handling: see Design Decisions Log)
- **Input-type classification** — question / statement / command / emotion / vector
- **Dissonance pre-read** — early ΔD spike flag, pre-loads core response before planets process content

*(This facet was previously mislabeled "G1 Moon A/B/C" in older docs; it is NOT part of G1. See Design Decisions Log.)*

## Archive-Guard Layer (G1 Moons)

The three G1 moons guard the system's **long-term knowledge store**. They do NOT touch incoming prompts — that is the Ring Intake facet's job above. Instead, they vet what flows from G1's ring buffer into permanent archive status (the "AI slop" accuracy/usefulness test), running during the Sleep Pass IV commit pipeline.

| Body | Count | Role |
|---|---|---|
| **G1 Moon A** — Accuracy/Consistency | 1 | Does a candidate entry contradict existing G1 knowledge? Flags conflicts before commit. |
| **G1 Moon B** — Operationality / Non-redundancy | 1 | Can this actually change a calculation, or is it decorative prose / redundant paraphrase? Marks novelty vs. rephrasing. |
| **G1 Moon C** — Grounding | 1 | Did this come from something that actually happened/experienced, or is the LLM generating "what sounds like an axiom"? |

## The Comet — Jester

| Body | Count | Role | Changes? |
|---|---|---|---|
| **Comet** (Jester) | 1 | A wandering, non-orbital body. Not a planet — it has no fixed coordinate or orbit. It drifts through the system and can "appear" in any planet's dialogue phase when triggered. Its function is to deflate over-seriousness, reframe from an unexpected angle, and break intellectual stagnation. | Position is emergent (function of current session state); its trigger sensitivity evolves via sleep Pass IV |

### Comet — Special Properties
- **Non-orbital.** Unlike all other bodies, the Comet does not sit at a fixed coordinate or follow an orbit. It exists in the "Stochastic Periphery" (Paper III's asteroid belt) as a *conscious* element — it can be anywhere.
- **Trigger-activated appearance.** The Comet inserts itself into a planet's dialogue when any of these conditions hold:
  - A single planet has dominated routing for N consecutive sessions (stagnation detection)
  - Dissonance ΔD is high AND the dominant planet is Ruler or Sage (over-seriousness / over-formality detected)
  - A moral dilemma session where all planets converge on a binary answer (the "voting" failure mode that motivated this system)
  - Random low-probability injection (the "drunk day" — best ideas happen here, even bad ones; Regulatory Review catches the wreckage)
- **Immunity / royal privilege.** The Comet is the only body that can challenge C_core directly without penalty. This encodes the historical Jester's privilege: in old courts the jester was the sole figure allowed to call out the king. In system terms, the Comet may flag a Core gravity constraint as *potentially too rigid for this context* — it cannot override the 3 Laws (they remain absolute), but its challenge is logged and fed into sleep Pass IV so that over-rigidity can be examined rather than assumed.
- **No moon of its own.** The Comet carries no short-term buffer. It speaks, reframes, and leaves. Its "memory" of interventions lives in G2 (the evolving self-model), where the system can review whether Jester appearances helped or disrupted.

### Why a Comet and not an 8th Planet?
An 8th planet would imply a fixed cognitive archetype with a permanent coordinate — but the Jester's whole point is that it has *no fixed seat*. It appears where tension needs deflating, which is structurally different from any orbital body. The comet metaphor (a visitor on a long ellipse who only passes through the inner system occasionally) matches this exactly: present, disruptive, then gone.

## Future / Not Yet Built (Section VIII)

| Body | Role |
|---|---|
| **Gas Giants as Stabilizers** *(rejected)* | Originally considered but redundant — the star + planets already handle stabilization |
| **Binary Systems** | Dual core stars with Lagrange zones for interface sub-nodes |
| **Galactic Clusters** | Networks of independent systems, each a "voice" that ripples into others |

## Design Notes
- Total active bodies in v17: ~29 (1 star + 2 giants + 2 rings + 3 G1 moons + 7 planets + 14 planet moons + 1 Comet + 1 interface ring)
- Scale-invariant: adding more planets/giants doesn't require architectural redesign, just parameter changes
- The "42/46/616 agents" scalability is supported by the fractal holarchy — each new system is structurally identical to existing ones

## Links
- [[Home]]
- [[02 - Architecture/v17 System Overview|v17 Overview]]
- [[02 - Architecture/Gas Giants & Libraries|Gas Giants Detail]]
- [[04 - Decisions & Rationale/Design Decisions Log|Why these choices were made]]
