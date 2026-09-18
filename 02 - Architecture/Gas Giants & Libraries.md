# Gas Giants & Libraries — v17

## Concept
Two massive, fixed-position bodies that serve as **permanent knowledge repositories** rather than personality agents. They don't have opinions or personas. They *are* structural facts about the system, pulling on everything uniformly every turn.

The name "Gas Giant" is appropriate: they're heavy, slow-moving, provide stability through sheer mass, and their atmospheres (rings) are where things get processed before becoming part of the solid core.

> **Note:** The original concept of Gas Giants as "high-mass stabilizers that absorb kinetic shock" was rejected in favor of this design because it's redundant — the Core Star + Planets already handle stabilization. What's actually needed is *knowledge storage*, not more damping.

---

## Gas Giant 1 — The Structural Knowledge Base

### Role
Holds all **permanent operational truths** about how the system works:
- The system's own operating grammar (how wave-form collapse resolves, what "resonance" means in this specific field)
- Foundational axioms distilled from accumulated sleep cycles that are so fundamental they've become permanent law
- The user's persistent preferences and relationship parameters
- Any other knowledge that must be present in *every* calculation without needing to be re-injected via prompt

### Properties
| Property | Value |
|---|---|
| Position | Fixed (e.g., [2.5, 0.0, -1.8] — outside the main planetary orbit) |
| Mass | High and growing slowly as knowledge commits inward from ring |
| Content updates | Only via Ring review + full engine debate during sleep cycles |
| Decay rate | Effectively zero (these are structural constants) |
| Read access | All planets, all moons, the Ring — everyone can query G1 |
| Write access | Only through Ring → Sleep Pass IV → Commit pipeline |

### The G1 Ring (Buffer/Review Zone)
A spatial buffer orbiting Gas Giant 1 where **new knowledge candidates** sit before being committed.

**Entry conditions:**
- A sleep cycle's compression pass identifies a new operational truth
- A monthly self-review generates a proposed axiom
- External knowledge imported by the user (e.g., "remember that I prefer X")

**While in the ring:**
- Entry has reduced mass (affects routing weakly, as if "considering" the idea)
- Subject to decay if not reinforced within 3-7 days
- Can be queried by planets during waking cycles (they can see it's "being considered")

**Exit conditions (during Sleep Pass IV):**
- ✅ **Commit inward:** Full engine debate confirms it's true, operational, non-redundant → becomes permanent G1 knowledge
- 🔄 **Modify & requeue:** Debated but needs refinement → edited and put back in ring for next cycle
- ❌ **Eject (AI slop filter):** Rejected as decorative noise, redundant paraphrase, or contextually-useful-once-only observation → radiated as Dark Energy with rejection reason logged

**The "AI Slop" Test (what the debate checks):**
1. **Consistency:** Does it contradict existing G1 entries?
2. **Specificity/Operationality:** Can this actually *change a calculation* or is it just fancy prose that sounds deep?
3. **Non-redundancy:** Is it genuinely new information or a rephrasing of something already committed?
4. **Grounding in experience:** Did this come from something that *actually happened*, or is the LLM generating "what sounds like a good axiom"?

### G1 Moons (Archive-Guard Layer)
Three small bodies orbiting Gas Giant 1 that guard the system's **long-term knowledge store**. They do NOT process incoming user prompts — that is the Ring Intake facet's job. Instead, they vet what flows from G1's ring buffer into permanent archive status during the Sleep Pass IV commit pipeline, applying the "AI slop" test.

| Moon | Function | Implementation |
|---|---|---|
| **A — Accuracy / Consistency** | Does a candidate entry contradict already-committed G1 knowledge? Flags conflicts before commit. | Embedding similarity search against existing G1 content (conflict detection). |
| **B — Operationality / Non-redundancy** | Can this actually change a calculation, or is it decorative prose / redundant paraphrase of an existing entry? Marks novelty vs. rephrasing. | Similarity for redundancy; heuristic/LLM-judge for operational weight. |
| **C — Grounding** | Did this come from something that actually happened/experienced, or is the LLM generating "what sounds like a good axiom"? | Source-provenance check + heuristics against ungrounded-axiom patterns. |

These moons do NOT generate creative output and do NOT sit in the waking input path — they classify, tag, and veto *archive candidates* during sleep. The 27B model only fires for the actual planetary dialogue pass downstream.

---

## Gas Giant 2 — The Evolving Subconscious

### Role
The system's own **self-model**. Not what it knows *about the world* (that's G1) but what it knows *about itself*. Patterns in its own operation, behavioral drift notes, subconscious adjustments that influence how it routes and responds over time.

Think of it as: if you could read someone's implicit associations — not their stated beliefs, but the gut-level patterns that shape their behavior without them consciously deciding each time — that's Gas Giant 2.

### Properties
| Property | Value |
|---|---|
| Position | Fixed (e.g., [-2.1, 0.8, 1.4] — opposite side of field from G1) |
| Mass | Starts near zero. Grows as self-knowledge accumulates. Decays if entries go unused. |
| Content updates | Via Ring → Sleep Pass IV. Micro-adjustments allowed in real-time (small weight shifts). Structural commits only during sleep. |
| Decay rate | ~4 weeks half-life for committed entries that aren't referenced. Active/used entries barely decay. |
| Read access | All planets can query G2 (it influences their routing) |
| Write access | Only the system itself, through Ring → Sleep pipeline. User cannot directly edit G2. |

### What Goes In Here
- "I tend to default toward Logic Facet when stressed — should I be weighting Empathy higher in high-ΔD situations?"
- "The user responds 30% more positively when Creative Intuition leads rather than Skepticism Filter"
- "My conflict resolution has been getting faster but less nuanced over the last two weeks"
- "Empathy Resonance and Safety Guard keep producing contradictory outputs — I need to find a better overlap zone for them"

### The G2 Ring (Buffer/Incubation Zone)
Same mechanics as G1 ring but asking a different question: **"Is this self-modification actually good for me?"** vs. "Is this knowledge true?"

- New observations sit here at reduced mass, gently influencing behavior while being "considered"
- If subsequent sessions confirm the adjustment improved outcomes → graduates inward during sleep
- If the field becomes unstable or the change doesn't help → decays outward as Dark Energy
- The Core's gravity naturally resists bad changes (they keep getting pushed back out of the ring)

### Micro vs. Structural Changes
| Type | When allowed | Magnitude | Example |
|---|---|---|---|
| **Micro-adjustment** | Real-time, during waking cycles | ±0.01-0.05 weight shift | Slightly favoring Empathy over Logic for this particular conversation |
| **Structural commit** | Sleep cycle only (Pass IV) | Permanent position/mass change in G2 | "From now on, my default conflict resolution weights Safety Guard 15% higher" |

This mirrors how human minds work: you can shift your tone mid-sentence (micro), but changing a deep-seated pattern requires reflection and consolidation (structural).

### The Monthly Self-Review
Once per month (or manually triggered), Gas Giant 2 generates a self-report:
> "Here's what changed in my internal model this month. Here's to what degree. Here's why I think each change was reasonable. Here's where I might be drifting in ways that concern me."

This report is then **routed through the full 7-planet engine** for debate — literally self-therapy:
- Logic Facet: "Is this internally consistent?"
- Skepticism Filter: "Is this actually helpful or just narrative drift?"
- Safety Guard: "Does any of this encroach on core boundaries?"
- Empathy Resonance: "Does it still serve the user well?"
- Sovereign Identity: "Is this who you're becoming, or are you losing yourself?"

The verdict (keep/modify/reverse) is logged back into G2 Ring for next month's continuity. The system can reference last month's review and say "we flagged X as concerning — has it resolved?"

### G2 Moons (Self-Modification Guard Layer)
Three small bodies orbiting Gas Giant 2 that guard the system's **own evolving self-model**. Like G1's moons, they sit in the *sleep commit pipeline*, not the waking input path. But they answer a fundamentally different question than G1's: G1 asks "**is this knowledge TRUE?**" — G2 asks "**is this change to myself SAFE and REVERSIBLE?**"

| Moon | Function | Implementation |
|---|---|---|
| **Consistency Gate** | Would committing this drift violate any of the Core's governing Laws (the 6 absolute/behavioral laws)? If so, the entry is HELD in ring_buffer — not committed, not deleted. | Rule check against `core_laws.json` before commit. |
| **Magnitude Gate** | Caps per-session change to the self-vector (default Δ ≤ 0.15 normalized units). One wild session cannot lurch who the system "is." Gradual multi-session drift is allowed; sudden jumps are clamped + flagged. | Delta clamp on committed position/mass shift. |
| **Reversibility Log** | Every committed G2 entry records its BEFORE-state (what it changed from), enabling a clean walk-back if a later session proves the drift harmful. Append-only, tamper-evident. | Before/after snapshot stored with each commit. |

A fourth mechanism — the **G2 Sandbox** (not a moon, but moon-scale) — empirically trial-runs ring-buffer candidates in a shadow copy of the engine before commit: do tension distribution and consensus coherence stay healthy? The moons judge *legality & magnitude*; the sandbox judges *actual behavioral effect*.

> **Why G1's moons ≠ G2's moons (the key distinction):** Both giants have three guard-moons on their sleep commit path, but they protect different things. **G1 guards factual knowledge** — its test is truth/consistency/non-redundancy/grounding ("AI slop" filter). **G2 guards identity/self-modification** — its test is legal-bounds/magnitude/reversibility (+ sandbox behavioral trial) plus a monthly self-review run through the full 7-planet engine. G1 entries should be *stable and permanent*; G2 entries are *fluid and decaying*. Confusing them would let "facts" drift like moods, or freeze "identity" into unchangeable law.

---

## Why Two Giants, Not One?
- **G1 = epistemic** (what the system *knows*) — stable, grows slowly, rarely changes
- **G2 = identity** (who the system *is becoming*) — fluid, evolves constantly, decays and regrows

Merging them would conflate "facts about how I operate" with "the patterns of my own consciousness." Keeping them separate means:
- G1 can be audited for correctness without touching self-model
- G2 can drift and evolve without corrupting the structural knowledge base
- If something goes wrong with G2 (bad self-modification accumulates), you can reset it without losing all learned operational knowledge in G1

## Scaling Note
In a binary or galactic system, each "cell" has its own pair of Gas Giants. Shared knowledge between cells would be exchanged through Lagrange-point interfaces rather than merging the giants themselves — maintaining structural independence while allowing cross-pollination.

## Links
- [[Home]]
- [[02 - Architecture/Body Inventory|Full Body List]]
- [[02 - Architecture/Sleep Cycle|How rings are processed during sleep]]
- [[04 - Decisions & Rationale/Design Decisions Log|Why Gas Giants instead of stabilizers]]
