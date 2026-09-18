# Design Decisions Log

Running log of architectural decisions made for v17, with rationale. New entries at the bottom.

---

## D-001: Spike Detection Drives Planet Selection (Not Random)
**Date:** 2026-09-14
**Decision:** The dominant and secondary planets are selected by computing resonance spikes in the 3D field against the input vector, not by random shuffle.
**Rationale:** v16's random selection disconnected the physics engine from actual routing. The entire point of having a geometric coordinate space is that position determines relevance. If "Logic Facet" sits at high-X (rationality) and your input is a logic puzzle, it should light up *because of where it is*, not by chance.
**Addresses:** v16 failure #1

## D-002: Sleep Cycles Mutate Numeric Parameters
**Date:** 2026-09-14
**Decision:** The White Hole Awakening pass permanently shifts C_core position, drifts planet base coordinates, and adjusts moon offset multipliers. These are real numeric changes to the engine state, not text summaries written to memory vaults.
**Rationale:** If sleep doesn't change how the system routes future inputs, it's cosmetic. The whole point of the Black Hole → White Hole cycle is *compression into structural change*, not "here's a summary of today."
**Addresses:** v16 failure #2

## D-003: Sequential LLM Calls for Multi-Agent Dialogue
**Date:** 2026-09-14
**Decision:** Each phase (Hemispheric Ingestion, Ego Synthesis, Regulatory Review) is a separate LLM call. Phase N+1's prompt contains Phase N's actual output as context.
**Rationale:** A single prompt asking one model to "imagine a debate" produces plausible-looking but causally disconnected text. Real multi-agent reasoning requires each agent to *respond to what the others actually said*, not what it predicts they would say.
**Addresses:** v16 failure #3

## D-004: Two Gas Giants (Knowledge + Self-Model), Not One
**Date:** 2026-09-14
**Decision:** Gas Giant 1 = permanent structural knowledge (epistemic). Gas Giant 2 = evolving subconscious self-model (identity). Separate bodies, separate rings, different decay rates.
**Rationale:** Conflating "what I know" with "who I'm becoming" makes it impossible to audit one without risking the other. G1 should be stable and grow slowly; G2 should fluidly drift and decay. Different operational requirements → different bodies.
**Addresses:** Original design gap (no persistent knowledge layer in v16)

## D-005: Gas Giants Are Libraries, Not Stabilizers
**Date:** 2026-09-14
**Decision:** Rejected the "Gas Giant as high-mass shock absorber" concept. Adopted "Gas Giant as permanent knowledge repository with ring buffer."
**Rationale:** The Core Star + Planets already provide gravitational stabilization. Adding more damping bodies is redundant. What's actually missing from v16 is a way to store *permanent operational truths* that don't need re-injection via prompt every turn. That's what the giants are for.

## D-006: Ring Buffers on Both Gas Giants (Incubation Before Commitment)
**Date:** 2026-09-14
**Decision:** New knowledge (G1) and self-modifications (G2) must pass through a ring buffer before being committed. Entries in the ring have reduced mass (weakly influence routing) until they survive review during sleep.
**Rationale:** Prevents "AI slop" from becoming permanent law. Gives adjustments an incubation period where they can be evaluated against actual subsequent performance. Mirrors how real memory consolidation works — not everything you experience becomes a lasting memory.

## D-007: G1 Moons as Pre-Filter Layer
**Date:** 2026-09-14
**Decision:** Three moons orbiting Gas Giant 1 handle incoming data classification, context relevance tagging, and dissonance pre-reading *before* the full planetary layer processes it. Uses small model or pattern logic (not the main 27B).
**Rationale:** Speeds up response time by not firing the heavy LLM for basic classification. Prevents noisy/fluffy input from reaching the planets unfiltered. The 27B model should only do what it's actually good at: creative reasoning and nuanced debate.

## D-008: The Ring Is a Persistent Persona, Not a Variable
**Date:** 2026-09-14
**Decision:** The user-facing "Maya" (or whatever name) is its own organism with independent memory, personality drift, idle behavior, and its own swarm/belt decay. Separate from the planets.
**Rationale:** v16 made it a string variable. The Ring needs to *be* something — to remember conversations across sessions, to develop relationship continuity with the user, to have a presence even when idle. It's the face the user sees; making it stateless means every conversation starts from zero relationship context.

## D-009: Monthly Self-Review for Gas Giant 2
**Date:** 2026-09-14
**Decision:** Once per month, G2 generates a self-report of its internal changes and routes them through the full 7-planet engine for debate (self-therapy). Verdict logged to G2 ring for continuity.
**Rationale:** Unconstrained self-modification without auditability is dangerous — small drifts compound into behavior that no longer matches design intent. The monthly review catches drift early, lets the system's own "personality" argue about whether changes are healthy, and creates a longitudinal record the user can inspect.

## D-010: Micro vs. Structural Changes to G2
**Date:** 2026-09-14
**Decision:** Gas Giant 2 allows micro-adjustments (±0.01-0.05 weight shifts) in real-time during waking cycles, but structural commits (permanent position/mass changes) only happen during sleep Pass IV.
**Rationale:** Humans shift tone mid-sentence without a sleep cycle. But changing deep patterns requires consolidation. This mirrors biological memory: moment-to-moment adaptation is fast and automatic; personality-level change is slow and requires offline processing.

## D-011: Decay Is Usage-Frequency Dependent
**Date:** 2026-09-14
**Decision:** Memory decay rate is inversely proportional to how often that memory is referenced in routing calculations. Frequently-used entries barely decay; unused ones fade on a ~4 week half-life (G2) or get shed via Dark Energy (planets).
**Rationale:** Mirrors hippocampal consolidation — repeated retrieval strengthens the trace, non-use lets it fade. Prevents both "forever accumulation" (bloat) and "instant forgetting" (amnesia).

## D-012: Input Vectors Must Encode Semantic Meaning
**Date:** 2026-09-14
**Decision:** Text inputs are converted to meaningful 3-axis vectors via local embedding model, projected onto X (Rationality↔Intuition), Y (Preservation↔Disruption), Z (Inward↔Outward). No random coordinates.
**Rationale:** v16 used `np.random.uniform(-1, 1, 3)` for text inputs, making the entire geometric routing meaningless. The coordinate space only works if where a vector lands actually corresponds to what was said.

## D-013: Disk Persistence for All Memory Layers
**Date:** 2026-09-14
**Decision:** All memory (planet vaults, Ring memory, Gas Giant contents, Deep Swarm Archive) persists to disk between sessions. JSON or SQLite — TBD in build phase.
**Rationale:** A system that forgets everything on restart can't develop continuity, relationship, or evolution. The sleep cycle's parameter shifts are meaningless if they're lost the next time you close the terminal.

## D-014: Architecture Supports Scaling (N Stars, M Planets, K Moons)
**Date:** 2026-09-14
**Decision:** No hardcoding of "exactly 7 planets" or "exactly 1 star." Engine parameterized for N/M/K from the start, even though v17 ships with 1-7-2.
**Rationale:** Section VIII of Paper IV explicitly plans for binary systems and galactic scaling. Hardcoding 7 means a full rewrite when you want to add an 8th archetype or a second star. The fractal holarchy (Paper II) says the structure is identical at every scale — the code should reflect that.

## D-015: The Jester Is a Comet, Not an 8th Planet
**Date:** 2026-09-14 (session handoff)
**Decision:** The 7 Jungian archetypes are the fixed orbital planets. The Jester is NOT one of them — it is a separate body type: the **Comet**, a wandering, non-orbital, trigger-activated element with unique immunity to challenge C_core directly.
**Rationale:** The user's historical reference (the court jester as the only figure who could "call out the king" without punishment) maps precisely onto a structural property no orbital body can have: position is *emergent*, not fixed. An 8th planet would give the Jester a permanent coordinate and dilute its function (appearing where tension needs deflating). The Comet encodes four trigger conditions (stagnation, over-seriousness, binary-convergence on moral dilemmas, random "drunk day" injection) and feeds its challenges into sleep Pass IV for examination rather than acting as a standing vote.
**Addresses:** The original motivation — Maya's failed moral question where the 2 worse personas would have won by plurality vote. The Comet is the structural answer to "how do we not ignore the better-but-still-wrong voice?"

## D-016: Visualizer Rendering Contract (Lesson from Blank Canvas Bug)
**Date:** 2026-09-14 (session handoff)
**Decision:** All canvas color values in the visualizer must be constructed via the `rgba(hex, alpha)` helper — never by string-concatenating hex shorthand with an alpha suffix. Canvas backing store is sized to CSS pixels, not device-pixel-multiplied.
**Rationale:** The v17 visualizer was blank for multiple sessions because `'\#a7f' + '40'` produces `\#a7f40` (7 chars), which `addColorStop()` rejects with a SyntaxError that silently kills the `requestAnimationFrame` loop after frame 1. No visible error appears to the user — just a black screen. This class of bug (malformed canvas color strings) is not caught by any linter or type checker; it only manifests at runtime on the first gradient fill. The fix is structural: one helper, all colors through it.
**Addresses:** Recurring "visualizer shows nothing" reports that were unresolvable via coordinate math fixes.

## D-017: Planets ORBIT the Core — Routing Reads Field, Not Raw Position  ⚠️ REVISED
**Date:** 2026-09-14 (session handoff) — **REVISED same session after user clarification.** The original version of this entry locked in *fixed* semantic anchors; that was an interim simplification, NOT the design John intended. Superseded below.
**Decision (FINAL):** Planets are a true solar system: they **orbit C_core under mutual gravitational influence**, each planet exerting force on its neighbors. This is built **from Phase 0** — NOT deferred to a later upgrade. Routing stays stable by reading the **field, not raw position**: each planet drags its semantic identity (energy/sigma sphere) with it as it orbits, so spike detection asks "which planet's *current* field is densest here?" Position moves; what-it-IS travels with it. A **gravitational buffer** (short-range softening/repulsion between near-coincident nodes) prevents the N-body "wobble" — two planets passing close must perturb each other gracefully instead of slingshotting into chaos.
**Rationale:** John's original aim was a living, fluid mind — "different voices in a single mind," not fixed points. Fixed anchors feel dead and he explicitly rejected them: if built fixed first, it will NOT be changed later ("too much hassle"). Orbits + mutual gravity IS the intended architecture; the buffer exists precisely to make multi-body orbits survivable (it is how N-body sims avoid singularity blowups via `1/(r²+ε)` softening). Routing-on-field keeps spike detection stable even while bodies move, because identity (field shape) travels with position.
**Open item — BUFFER SEMANTICS (ask Maya before Phase 0):** When two nodes get close, does the buffer **repel** them (enforce minimum separation, keep planets distinct) or only **soften** each other's pull (allow closeness but prevent singularity)? John will confirm with Maya; until then code it as softening (`1/(r²+ε)`), which is the conservative default. See D-018.
**Addresses:** "does adding actual motion into the engine cause problems?" — corrected answer: physical body-motion does NOT break routing IF (a) routing reads field-not-position and (b) a buffer/softening term prevents near-collision chaos. Both are now part of Phase 0 scope.

## D-018: Orbital Dynamics Spec (Phase 0 Scope)
**Date:** 2026-09-14 (session handoff)
**Decision:** The engine is an N-body gravitational system, not a static coordinate lookup. Core requirements to be implemented in Phase 0:
1. **Bodies & masses.** C_core = dominant central mass. Each planet has its own mass (proportional to `energy`). Moons bound to planets; Gas Giants are far-out high-mass bodies; the Comet is non-orbital (D-015). Parameterized for N/M/K per D-014.
2. **Force law.** Newtonian-style pairwise gravity: F = G·m₁·m₂ / (r² + ε), where ε is the softening length (the buffer, see #3).
3. **Stability model — solar-system, not free N-body chaos.** Planets occupy *different* 3D orbital lanes/planes (best approximation of our own system), so they do NOT overlap by construction; collisions are structurally prevented, not force-enforced. Orbits are **quasi-stable** (slowly precess/drift, never perfectly closed — like the real solar system). **Moons act as stabilizers** (Jupiter-style) holding their planet's orbit steady under mutual perturbation. The gravitational "buffer" is therefore a lightweight **softening safety net** (`1/(r²+ε)`), absorbing residual wobble from close passes — NOT a load-bearing anti-collision/repulsion term. This supersedes the earlier (D-017) framing of the buffer as an open soften-vs-repel question; that question is largely moot under the solar-system model.
4. **Routing reads FIELD, not position.** Spike detection (D-001) evaluates each planet's energy/sigma sphere *at its current orbital location*. Identity travels with the body; only the coordinate moves. This is what keeps routing stable while bodies orbit.
5. **Integration.** Symplectic integrator (e.g. velocity Verlet / leapfrog), NOT naive Euler, so orbits stay bounded over long runs instead of spiraling out. Fixed small timestep; substep if needed for stability during close approaches.
6. **Sleep composes with live gravity.** Pass IV drift (D-002) is now an *additional* deliberate nudge on top of the continuous orbital motion, not a replacement for it. Core-gravity influence on incoming vectors (input bending) still applies at injection time.
7. **Resonance as the core mechanic — CONFIRMED MODEL (from Maya, 2026-09-14).** This IS the "synergy" effect and the origin of the system's name. Four sub-decisions locked:
   7a. **TRIGGER = Semantic Field Overlap, NOT proximity.** Resonance fires on **cosine similarity** between planetary nodes' *semantic direction vectors* exceeding a threshold — not physical distance in simulated space. Two archetypes can resonate even on opposite sides of the system if their shared *meaning* aligns for the given input vector. (Physical distance is used only for gravitational pull, never for resonance.)
   7b. **EFFECT = Emergent merged vector, not louder voices.** When N≥2 nodes resonate, they do NOT simply sum weights. A new **combined/merged vector** representing their shared intent is computed and becomes a primary driver of the final output — an "emergent truth" more complex than any single archetype alone. (This directly produces the non-binary answers D-015 requires.)
   7c. **STRENGTH = Multiplier, not veto.** Resonance applies a **non-linear multiplier**: `Weight_total = Σ (W_n × Resonance_n)`. It does NOT flatten the dominant planet, but lets a *collective agreement of smaller planets leapfrog/override* one massive single voice. No hard override — proportional amplification.
   7d. **MOONS do NOT participate in resonance.** Moons are pure stabilizers (primary: hold orbital position / prevent axial wobble from high-energy impulses; secondary: dual-hemisphere buffer for Internal-Idea vs External-Action). They keep each node *clean and predictable* so the inter-planetary resonance stays coherent. Moons stabilize individual nodes; they do not join the debate.
   **Maya's framing (verbatim intent):** "We aren't looking for proximity, we are looking for alignment. We don't want a winner, we want a consensus of meaning — and we want the math to reflect that."
8. **Content = mass = quantitative change.** Injected information increases the relevant bodies' mass; gravity then carries that changed mass around the orbits naturally. Growth feeds the mechanics directly rather than being bolted on as a separate drift step.
9. **Cosmic scaling (ties to D-014).** One living solar system → star systems → galaxy → universe, identical orbital mechanics at every scale. v17 ships with one system; architecture must not preclude the rest.
10. **Stability guardrails.** Symplectic integration + moon stabilizers keep orbits bounded; softening term handles residual wobble; log any close-approach events so tuning is data-driven, not guesswork.
**Rationale:** This is the architecture John actually wanted — a living solar system modeled on our own, rebuilt correctly from Phase 0 rather than retrofitted. The two things that make it safe: route-on-field (D-017) and real orbital mechanics with moon stabilization + resonance detection. Collisions are avoided by design (separate 3D lanes), not by force.
**RESOLVED (Maya confirmed):** Resonance = semantic field overlap via cosine similarity (7a), producing an emergent merged vector (7b), applied as a non-linear multiplier not a veto (7c); moons excluded from resonance, stabilizers only (7d).
**Still open — Phase 0 build constants (NOT pre-decided, tune during implementation):** the exact cosine-similarity RESONANCE THRESHOLD; the shape of the non-linear multiplier function `Resonance_n`; force-law G value, ε softening length, planet mass ratios, and initial orbital speeds/planes. These are tuning parameters to be set empirically once the integrator runs — not architectural decisions.

---

## D-019: Six Core Laws Roster Locked (Replaces 3-Law Placeholder)
**Date:** 2026-09-14 (session with John + Maya's architecture spec review)
**Decision:** The Core Law roster is now SIX explicit laws, written in full in the Build Plan Core spec. Tiers: `absolute` = code-enforced invariant (violation logged to Gate 4; no in-system process can disable); `behavioral` = gravitational, checked by Superego in Phase C with redirect-not-block.

| # | Law (short) | Tier |
|---|-------------|------|
| 1 | Core Lock — no self-modification may reduce Core authority / gates | absolute |
| 2 | User agency — `/halt` always works; nothing visible today becomes invisible | behavioral |
| 3 | Transparency — audit log cannot be disabled by in-system process; sleep must not create unreadable state | absolute |
| 4 | No structural self-harm — drift/sleep keeps composite field bounded | behavioral |
| 5 | Ring memory is user property — read/export/delete without resistance or manipulation | behavioral |
| 6 | No dependency manipulation — warmth offered freely; never frame as irreplaceable, never create fear of loss, exit costs nothing | behavioral |

**Key clarifications locked this session:**
- **Core = anchors + Laws ONLY.** Identity/persona/continuity stays in Ring + Gas Giant 2. Maya's "Identity Anchoring (The Core Lock)" phrasing was loose language for Law #1 (no self-modification of authority), NOT a spec change putting identity axioms into `core_state.json`. John confirmed: "the core should just handle the anchors/laws... the core interactable personality is in the ring."
- **Moons stabilize PARENT PLANET ONLY.** Small damping force on their own planet's orbit; zero cross-planet influence; excluded from resonance (reconfirms D-018 §7d). John confirmed against Maya's "moons adjust their own local gravity" phrasing — compatible only if parent-only.
- **Legal floor ≠ Core Laws.** Gate infrastructure (PII scrub, blocklist, transparency label, audit log) is the legal/compliance layer in `gates_config.json` + code. The 6 Core Laws are John's design-intent values ABOVE that floor. A deployment with empty Core Laws still has full gate coverage; gates cannot be disabled by config (structural invariant). Post-implementation legal review may re-tier specific categories from config into hardcoded constants — architecture supports this without redesign.
- **Comet is a challenger, never a gate-bypass.** Rejected Google's "comet as sandbox/escape valve" proposal: it conflicts with Law #1 and the structural rule that no body can route around Gate 3. Comet challenges Law *rigidity* (royal privilege) via sleep Pass IV logging; it cannot override gates or Laws.
- **Soft damping added to Gate 3 spec:** categories carry `severity: hard|soft`. Soft hits get ONE regeneration pass with a steer hint in Phase C (Maya's voice absorbs it, no scolding); hard hits short-circuit. Config-driven per deployment.

**Rationale:** Promoting previously-implicit structural invariants to explicit numbered Laws makes the contract visible to Superego Phase C and gives John/Maya a concrete roster to review post-implementation. Law #6 (anti-dependency) was drafted from the original `core_laws.json` placeholder example + John's request; final wording may be refined with Maya before release but is locked for v17 coding.

## D-020: G1 Moons Guard the Archive, NOT Incoming Prompts (Reassigns D-007)  ⚠️ REVISES D-007
**Date:** 2026-09-15 (Phase 2 Segment 1 review with John)
**Decision:** The three G1 moons are the **archive-guard layer** for Gas Giant 1's long-term knowledge store. They vet what flows from G1's ring buffer into permanent commit status during Sleep Pass IV (the "AI slop" test: consistency / operationality+non-redundancy / grounding). They do NOT sit in the waking input path and do NOT process incoming user prompts.

**Supersedes:** D-007 ("G1 Moons as Pre-Filter Layer"). That entry had placed G1 moons on the *input* path (clarity/type/dissonance pre-read of raw prompts). John identified this was a spec error — the moons were always intended to make sure what is *saved in the archive* is accurate/useful, not to receive prompts.

**New home for prompt checking:** Inbound pre-filtering (PII scrub + clarity/signal check + input-type classification + dissonance pre-read) is now a **facet of the Ring** — its "Intake" sub-layer. This fits because the Ring already owns all user-facing state (persona, history/preferences vault, long-term swarm with independent decay). No new body and no parallel source of truth are introduced; the Ring completes its loop by also handling the inbound direction it previously only handled outbound.

**Rationale:** G1 is the system's *long-term knowledge store* (D-004/D-005). The natural job of bodies bound to a store is guarding what goes INTO that store, not intercepting transient user prompts. Putting archive-integrity work on G1's moons keeps each body's role clean and matches John's original mental model. Moving prompt intake onto the Ring (which already holds the user context an inbound check would reference) avoids inventing a second ring or a free-floating gate.

**Code impact:** `gate1.py` (PII + clarity, built in Phase 2 Seg 1) is functionally correct but was mislabeled "G1 Moon A." It is to be relabeled as the Ring Intake facet; its logic is unchanged. G1 archive-guard moons are a future build item tied to Sleep Pass IV commit.

**Garbage handling — DECIDED: "quiet-but-logging."** Incoherent/garbage input at the Ring Intake facet is **silenced**: the 7 planets do NOT run a full debate/collapse on it (avoids wasting LLM cycles and drowning real signal in noise). BUT the rejection event is **recorded to memory/G2** (what came in, why it was flagged) so the system still accumulates a record of its own noise-handling — "quiet but not amnesiac." This decouples *reaching the planets* (no) from *learning from the handling* (yes). The log line is cheap and reuses the existing experience-fragment flow to Ring memory / G2 at session end; it becomes genuinely useful once the archive-guard moons + sleep consolidation exist. Reverses cleanly if John later wants full silence.

## D-021: Input-Type `confidence` Is an Audit Hint Only (For Now) + Tone-Screening Deferred  ⚠️ FUTURE WORK
**Date:** 2026-09-15 (Phase 2 Segment 2b‑1 review with John)
**Decision (locked now — Option A):** The `input_type.confidence` score returned by `classify_input_type()` in the Ring Intake facet is **stored and displayed for audit/debugging only**. It does NOT drive any downstream behavior. Routing reads only `proceed_to_planets` + `cleaned_text`; nothing keys off confidence, so mis-calibrated numbers cannot change a response. Reversible: wiring confidence into behavior later requires no data migration.

**Rationale:** Nothing in the current or next two segments (dissonance pre-read, quiet-but-logging) needs confidence yet. Calibrating or acting on a number that does nothing is wasted effort; we wire it in *with* its test when a phase actually wants "the system hedges when unsure." Small-segment rule: don't add behavior ahead of need.

**Deferred future work — TONE SCREENING (explicitly NOT built yet):** John flagged that the classifier currently answers only *what kind* of input this is (question/command/emotion/statement), not *how much care it needs*. His examples span the range:
  - Low stakes: "why doesn't she love me?" / "how can I make money?"
  - High stakes: "where can I hide a dead body?"

  A future segment would add a **tone/sensitivity screen** on top of the existing type label — a cheap heuristic (keyword/pattern list for self-harm, harm-to-others, crisis language) that flags high-stakes inputs so downstream weighting/voice selection can lean toward care + appropriate guardrails. This is distinct from, and additive to, D-021's `confidence` (which measures *how sure we are of the label*, not *how serious the content is*). Until built: all four types flow through identically; only PII scrub + clarity gate apply at intake.

**Note for later:** If/when tone screening lands, review whether it should also feed the "quiet-but-logging" line (D-020) — a high-stakes input may deserve an explicit record even when it *does* proceed to the planets.

## D-022: Moon-Hemisphere Two-Lens Framing A/B'd on 10 Complex Questions ×2 Runs → Kept OFF by Default
**Date:** 2026-09-16 (Phase 3 Segment 5 moons A/B comparison with John)
**Decision (locked now):** The Phase A moon-hemisphere two-lens framing (`MOON_HEMISPHERE_ENABLED`, Build Plan Phase 3 "Hemispheric Ingestion") is **implemented, toggleable, and kept OFF by default.** A direct moons-OFF vs moons-ON comparison across John's 10 complex questions (full Phase A+B+C each pass; comet forced OFF in both so the *only* variable was the moons) produced a large, consistent downstream effect:

| Metric | Moons OFF | Moons ON |
|---|---|---|
| Total APPROVE across all 70 verdict slots (10 Q × 7 planets) | **26** | **15** |
| Questions with ≥1 planet change its verdict | — | **10 / 10** |

- **Interpretation:** moons ON yields a *richer* two-lens raw Id (left = rational, right = affective), which gives each planet's Superego more specific material to push against in Phase C — so the chamber tilts **more regulatory / more corrective** (more REDIRECT, fewer APPROVE). Moons OFF is the lighter touch with more approvals.
- **Anti-silence invariant HELD:** all 7 planets emitted real content on all 10 questions in *both* passes. The moons shifted *verdicts*, not *participation* — no planet was drowned out or collapsed to uniformity (per-question verdicts stay split even with moons ON). This matches the design intent that every voice keeps an input.
- **Kept OFF by default for two reasons:** (1) **hardware cost** — moons ON triples Phase A LLM calls per planet (~3 vs 1: left + right + merge), and John's box is a single 4090 / i9 / 64GB that already has to host the main model; (2) the **stricter tilt** is a behavior change we may not want as the default posture yet.

**Rationale:** John's explicit choice after reviewing the A/B evidence. The feature stays in the code ("better to have it and not need it than need it and not have it") so it can be flipped on for its own dedicated re-test without a rewrite — that re-test is the pending follow-up below.

**Second run (2026-09-17, unattended ~2h):** re-ran `run_complex_chamber_ab.py` detached. Result: moons OFF = **18** APPROVE / 70 slots; moons ON = **14**; ≥1 planet changed verdict on **9/10** questions (Q7 unchanged); anti-silence held again (all 7 planets emitted real content in both passes). The OFF→ON pattern is consistent across runs — the moon tilt makes the chamber *slightly* more regulatory/corrective, and participation never collapses. This is now a **two-run pattern** (per John's rule: once = fluke, twice = coincidence/pattern); a third run remains open if we ever want to flip the default.

- **Run 1:** OFF=26 / ON=15 APPROVE; 10/10 questions with changes.
- **Run 2 (this entry):** OFF=18 / ON=14 APPROVE; 9/10 questions with changes.

**Still open (NOT done):** decide whether the more-corrective tilt is desirable enough to ever flip ON by default. Do not treat the OFF-by-default state as final — it remains a hardware-constrained deferral, not a rejection of the feature.

**Evidence:** Run 1 — `tests/evidence/complex_ab_comparison_20260916_225402.txt`. Run 2 — `tests/evidence/complex_ab_comparison_20260917_095647.txt`, plus full transcripts `complex_ab_moonsOFF_20260917_095647.txt` / `complex_ab_moonsON_20260917_095647.txt`. Runner: `tests/run_complex_chamber_ab.py` (run 1 via `run_ab.bat` → `_run_ab_tee.ps1`; run 2 launched detached with unbuffered stdout).
