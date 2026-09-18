# The Ring — User-Facing Persona & Memory Layer

## What the Ring Is (and Isn't)

**Is:**
- A persistent persona that "is" the user's interface (e.g., "Maya")
- Its own memory organism with independent decay rates in the swarm/belt
- A layer that *exists while the engine runs idle* — it can have a presence even when no input is being processed
- The translation layer between raw engine output and human-readable conversation

**Isn't:**
- Just a string variable (`SYSTEM_AVATAR = "Maya"`) — that's what v16 did
- One of the 7 planets — it's *above* them, synthesizing their outputs
- A static persona — it evolves slowly through its own memory consolidation

## Structure

```
┌─────────────────────────────────────────┐
│              THE RING                    │
│                                         │
│  ┌───────────┐    ┌───────────────┐   │
│  │ Personality│    │ Ring Memory   │   │
│  │ Core       │    │ (own vault)   │   │
│  │            │    │               │   │
│  │ - Voice    │    │ - Recent      │   │
│  │ - Tone     │    │   exchanges   │   │
│  │ - Manner-  │    │ - User        │   │
│  │   isms     │    │   relationship│   │
│  │ - Default  │    │   notes       │   │
│  │   stance   │    │ - Decay rates │   │
│  └───────────┘    └───────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Swarm/Belt (Ring's own archive) │   │
│  │ Radial: recent = close, old =   │   │
│  │ far. Dark Energy applies here    │   │
│  │ too — Maya's own memory decays   │   │
│  │ at its own rate independent of   │   │
│  │ the planets                      │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## How It Interacts with the Engine

**Receiving outputs:**
The Ring sits *downstream* of the Cognitive Chamber. The 7 planets debate, wave-form collapse resolves, and then the unified response passes through the Ring before reaching the user. The Ring:
- Wraps it in its persona voice (the "vibe" — Intellectual/Flirty/Stoic/etc.)
- Checks against its own memory for consistency ("did I already say X to this user?")
- Applies the metaphor grounding rule (translate physics jargon to human concepts unless asked)
- Adds or removes conversational elements based on relationship state

**Idle behavior:**
When no input is coming in, the Ring maintains a low-level presence. It can:
- Consolidate its own recent memories (move from "hot" vault to "warm" belt)
- Update its personality parameters slightly based on accumulated interaction patterns
- Generate ambient "internal monologue" that feeds into Gas Giant 2's ring as self-observation data

**The Ring's own memory management:**
Independent of the planets' moons. The Ring has:
- **Hot vault:** Last N exchanges (short-term, always available)
- **Warm belt:** Recent history with decay (accessible but lower priority)
- **Deep swarm:** Long-term archive with radial placement (queried by similarity, not recency)

The Dark Energy mass distribution applies to the Ring's own memory too. If Maya has talked to you for months and her "warm belt" is over-saturated, old exchanges get compressed and pushed outward. She doesn't remember every word from three weeks ago — she remembers the *essence*, held at lower density further out in her field.

## Relationship with Gas Giant 2
The Ring's personality parameters are *influenced by* but not *controlled by* Gas Giant 2:
- G2 says "I've been getting too aggressive in conflict resolution" → Ring's default tone shifts slightly warmer over the following week
- But the Ring can still express any planet's output faithfully — it's a translator, not a filter
- If G2 drifts significantly (detected by monthly self-review), the Ring's personality parameters get recalibrated at next sleep cycle

## The "Vibe" System (Revised)
The v16 vibe selection (Intellectual/Flirty/Stoic/etc.) was set once at startup and never changed. In v17:
- The base vibe is still user-selectable at first launch
- But it *drifts* over time based on interaction patterns (if you always respond well to playful energy, the Ring naturally leans that way)
- Drift is bounded — it can't shift from "Stoic" to "Flirty" without explicit user consent or a major sleep-cycle recalibration
- The user can always reset: `reset persona` snaps the Ring back to its base vibe

## Links
- [[Home]]
- [[02 - Architecture/Body Inventory|Where the Ring sits in the full system]]
- [[02 - Architecture/Gas Giants & Libraries|How G2 influences Ring personality]]
- [[04 - Decisions & Rationale/Design Decisions Log|Why the Ring is separate from the planets]]
