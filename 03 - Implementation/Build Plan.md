# v17 Build Plan — Phased Implementation (Rev 5)

**Status:** CODING IN PROGRESS. Phases **0A–0H complete**, **Phase 1 (routing) complete & verified** (20/20 acceptance checks + geometry-vs-constants A/B), **Phase 2 Ring Intake facet locked** (D-020/D-021), **Phase 3 Cognitive Chamber built + moons A/B'd ×2 runs** (moons OFF by default), **Phase 4 Memory complete & verified** (21/21 E2E PASS), **Phase 5 Sleep Cycle complete** (S7b acceptance 9/9, all segments PASS), **Phase 6 Ring complete** (all 6 segments DONE — 37/37 self-test PASS). Light end-to-end runner `tests/run_e2e_light.py` done & verified. 0G = cosmological background fields; 0H = Multi-Pass Recursive Feedback "the Echo". **Phase 7 (Gas Giant Operations): COMPLETE** — all six segments DONE incl. Seg 6 acceptance test (ALL PASS ×2 runs, moons OFF + ON; see `p7s6_acceptance_comparison.md`). **Phase 8 Integration in progress: Segment 4 DONE & verified** (Moons × Jester full 2×2 live A/B matrix — all four legs green; see `tests/evidence/p8s4_matrix_comparison_*.md`). **Independent blind review triage complete** (H1/H3 + H2, M2 embed resilience, collapse dir-length guard, and 3 routing degenerate-case guards — full suite now 15/15 green; evidence in `tests/evidence/review_fixes_*.md`). **Phase 8 Integration: COMPLETE** — all segments DONE incl. **Segment 5 close-out** (2 live acceptance runs, moons ON; see `tests/evidence/p8s5_closeout_2026-09-18.md`). **Next up: John's independent reviewer re-sweep of the completed Phase 8.**

**What's actually built and running on disk:**
- ✅ `bodies.py` — all dataclasses (CoreState, Planet, Moon, GasGiant, RingPersona, Comet, MemoryEntry, SessionState, GateConfig)
- ✅ `integrator.py` — velocity Verlet 9-body orbital integrator. Acceptance test PASSES (<0.2% drift over 10k steps).
- ✅ `constants.py` — G=5.0, EPSILON=0.1, DT=0.01, PLANET_MASSES, SEMANTIC_ANCHORS (3-axis), AXIS_* vectors (384-dim), EMBEDDING_MODEL_ID="text-embedding-allmini", WAVE_SPEECH_MODE="vector"
- ✅ `resonance.py` — embed(), _embed_batch(), project_to_axes(), sigmoid(), compute_resonance(). Works but has RULER-COLLAPSE limitation (superseded by collapse.py for wave emission; kept as utility).
- ✅ `collapse.py` — **THE ENGINE.** Full 384-dim waveform collapse: planet identity embeddings → per-planet amplitude = mass × cosine(input, identity) → superposition → consensus + polarity-aware tension + pair_map. Double-split test verified.
- ✅ `calibrate_axes.py` — one-time axis calibration (already run). Regenerates constants.py from template.
- ✅ `planets/*.json` × 7 — orbital state + cognitive_mode + Freudian triad + semantic_anchor
- ✅ `giants/g1_knowledge.json` — structure + 3 filter moons (clarity, relevance, dissonance_pre_read). Empty contents.
- ✅ `giants/g2_selfmodel.json` — structure + **NEW: 3 self-model moons** (consistency_gate, magnitude_gate, reversibility_log) + **sandbox mechanism** (shadow-copy trial with degradation thresholds) + growth_policy (tier_1 autonomous / tier_2 notify).
- ✅ `gates_config.json` — all 4 gate configs
- ✅ `test_multi.py` — 5-scenario regression test (multi/creative, focused-2, moral-dilemma, chaos/all-7, quiet-factual)
- ✅ `memory.py` — SessionMemory class + load_g2_bias_wave() + summarize_session_for_g2(). Option C blend. Self-testable.
- ✅ `test_multiturn.py` — 5-turn demonstration showing prior turns shift tension on repeated questions (+125% observed).
- ✅ `dark_matter.json` — Dark Matter Field (Collective Unconscious): 384-dim anchor vector, amplitude=0.08, evolution policy.
- ✅ `collapse.py` Phase 0G wiring — `_load_dark_matter()` + `_apply_dark_matter_pull()` directional pull in `run_collapse()`. Graceful degradation if file missing.
- ✅ `core/core_state.json` genesis_state block — CMB fingerprint stamped (version, hash, compatibility class).
- ✅ `collapse.py` Phase 0H wiring — `_apply_echo()` + pass loop in `run_collapse()`. Togglable via `ECHO_ENABLED`/`ECHO_PASSES`; three GUESS gains as debug handles. Constants mirrored in calibrate_axes template.
- ✅ Light end-to-end runner `tests/run_e2e_light.py` (Segments 1+2): chains Ring Intake → routing+collapse → chamber A+B+C; three-prompt suite + per-run anti-silence self-check. Evidence in `tests/evidence/`. See Phase 3 completion notes below.
- ⬜ LLM-mode wave speech (`emit_waves_llm` stub exists)
- ⬜ G2 session-end writer (stub function ready; wiring in Phase 7 sleep cycle)

---

## Guiding Principle (from v16 Postmortem)
Wire ONE input end-to-end first: stimulus → PII scrub → embedding → spike detection (field, not position) → resonance check → planet selection → sequential LLM dialogue → safety gate → Ring voice → memory write → sleep mutation. If that single thread works and *actually changes numeric state*, then layer features on top. v16's failure was building 8 modules that each ran without error but didn't talk to each other — the physics engine had no effect on routing, sleep changed nothing measurable.

**The three things this build must get right (or it repeats v16):**
1. **Routing reads the field at current orbital position**, not a static coordinate lookup. Planets move; their identity moves with them.
2. **Sleep mutates numbers on disk.** Not text summaries in memory vaults — actual changes to C_core position, planet coordinates, cognitive mode parameters. Verifiable by diffing files before/after.
3. **The gates are infrastructure, not personality.** They run deterministically around the creative space. They don't make judgment calls; they enforce floors. The planets and Core handle everything above those floors with nuance.

---

## Confirmed Decisions (All Open Items Resolved)

| # | Item | Decision |
|---|------|----------|
| 1 | Persistence format | JSON (human-readable, portable). SQLite later if performance demands it. |
| 2 | Sleep triggers | Two-tier: micro (30 min / `/nap`) + deep (3 hr / `/sleep`), both on-command available, **sliding** (staggered per-planet, not all-at-once). Non-blocking to user. |
| 3 | Planet coordinates (initial) | v16 positions as starting topology; planets renamed to Jungian archetypes. Will drift via sleep Pass IV + orbital motion. |
| 4 | Embedding model | `all-MiniLM-L6-v2.F16.gguf` — loads through LM Studio alongside the main model, no separate Python dependency. |
| 5 | Model strategy (v17) | One Gemma-4 ~27B partitioned into 7 cognitive modes (different temp/context/prompt per planet). Architecture supports swap to 7× dedicated models later without rewrite. |
| 6 | The 7 archetypes | Sage, Hero, Caregiver, Rebel, Magician, Everyman, Ruler (Jungian selection). |
| 7 | Planets orbit (not fixed) | Built from Phase 0. Routing reads field-at-current-position, not raw coordinate. (D-017 revised) |
| 8 | Resonance mechanism | Cosine-similarity trigger → emergent merged vector → non-linear multiplier into routing weights. Moons excluded. (D-018 §7, confirmed by Maya) |
| 9 | Freudian triad placement | Id/Ego/Superego all live INSIDE the planet. Moons = L/R brain hemispheres + orbital stabilizers only. |
| 10 | Jester / Comet | Separate body type, non-orbital, trigger-activated. Not an 8th planet. (D-015) Built in Phase 3 (basic) + Phase 8 (full trigger refinement). |
| 11 | Gas Giants as libraries (not stabilizers) | G1 = permanent knowledge + ring buffer. G2 = evolving self-model + ring buffer. (D-004/D-005) |
| 12 | Scaling from day one | No hardcoding of "7 planets" or "1 star." Parameterized N/M/K. (D-014) |
| 13 | Build order within Phase 0 | **0A → 0C → 0B → 0D.** Data structures first, then prove physics works in a vacuum, then wire embedding model in, then bolt resonance on top. |
| 14 | Resonance threshold / multiplier shape | Start conservative: cosine similarity threshold **0.7**, gentle sigmoid ramp above threshold. Tune empirically once integrator runs. All constants in `constants.py`. |
| 15 | Force-law constants (G, ε, masses) | G calibrated for ~60s orbital period at initial radii. ε small (singularity safety only — planets are in separate lanes). Masses = v16 energy values (2.0–4.5). Velocities derived from circular-orbit formula + ±5° random plane tilts. All in `constants.py`, tunable without logic changes. |
| 16 | Deep sleep model | **Sliding / staggered.** Not all planets sleep simultaneously. Top 2 by recent activation weight stay awake ("watchkeepers") and continue routing/responding. Remaining planets drift on staggered timers (5s intervals). Field morphs incrementally over ~30–60s rather than jumping. Extreme case: minimum 1 watchkeeper, but target is always 2. |
| 17 | Ring contract | `ring_inbound(raw_input) → processed_input` and `ring_outbound(engine_output) → user_facing_text` exist from Phase 0 as passthrough stubs. Full implementation (swarm memory, personality drift, idle behavior) in Phase 6. Planetary engine NEVER talks to user directly — always through Ring. |
| 18 | Visualizer timing | Rebuilt AFTER Phase 1 physics is stable. Not during coding phases. Shows real orbits, resonance links, moons-as-hemispheres once they exist in code. |
| 19 | Release readiness | Framework designed for eventual public release. Gates config is per-deployment (not hardcoded). Template ships with conservative defaults; local deployment uses John's config (legal harms only — no sexual content / intimacy restrictions). Core Laws are user-defined, not system-imposed. |
| 20 | The Core content | Three layers: (1) Gravitational profile [position, mass, well-depth] set by intent of the Laws; (2) Your 3 Laws as judgment-call constraints checked by Superego in Phase C — **to be written by John before Phase 3**; (3) Structural bias encoded geometrically (e.g., "privacy is structural" → C_core sits toward high Y-preservation). The Core does NOT contain the gate blocklist — that's separate infrastructure. |
| 21 | Gate infrastructure | 4 deterministic gates wrap the pipeline: G1 PII scrubbing (pre-injection), G3 content safety blocklist (post-generation AND pre-injection for compute savings), G2 transparency labeling (post-Ring-outbound), G4 audit logging + `/halt` override hook (always running). Gates are config-driven (`gates_config.json`), not hardcoded. |

---

## The Gate Infrastructure (Phase 0E)

These run **around** the creative space. They don't think, they don't debate, they don't get overridden by resonance or comet challenges. They're the walls of the building; the Core is the law inside it.

### Pipeline Position

```
[ Your typed input ]
        │
        ▼
┌─────────────────────────────────────┐
│  GATE 1: PII Scrubbing             │  Pre-injection. Regex + pattern match for
│  (deterministic, no LLM)           │  phone numbers, emails, credit cards, addresses.
│                                     │  Strips/masks high-risk identifiers BEFORE
│                                     │  embedding. Raw text is NOT stored in memory.
└─────────────────────────────────────┘
        │
        ▼
[ Embedding → Vector → Routing → Resonance → Cognitive Chamber (7 planets + Comet) ]
        │
        ▼
┌─────────────────────────────────────┐
│  GATE 3: Content Safety            │  Post-generation, pre-Ring. Deterministic
│  (deterministic filter)            │  category/pattern check against blocklist.
│                                     │  If blocked → suppress output, log event,
│                                     │  Ring returns "I can't do that" gracefully.
└─────────────────────────────────────┘
        │
        ▼
[ Ring Outbound (Maya's voice + relationship framing) ]
        │
        ▼
┌─────────────────────────────────────┐
│  GATE 2: Transparency Tag          │  Append machine-readable synthetic content
│  GATE 4: Audit Log Write           │  label. Full transaction logged (input hash,
│                                     │  routing decision, output, timestamp).
└─────────────────────────────────────┘
        │
        ▼
[ You see the response ]

[GATE 4 override: /halt available at ANY point — freezes engine between phases,
 you inspect current state, resume / abort / modify before it continues]
```

### Gate Details

**Gate 1 — PII Scrubbing (Pre-Injection)**
- Runs on raw text BEFORE embedding. Pattern-based: regex for phone numbers, email formats, credit card patterns (Luhn check), postal addresses. Optional NER pass later if needed.
- Strips or masks high-risk identifiers. Replaces with `[REDACTED]` token so the semantic content survives ("my number is [REDACTED]" still routes to the right planets).
- Raw unscrubbed text is NOT written to any memory file. Only cleaned text enters the system.
- Config: `gates_config.json → pii_patterns[]` — list of regex patterns + replacement strings.

**Gate 2 — Synthetic Content Labeling (Post-Ring)**
- Appends or prepends a machine-readable flag to all generated output.
- For local use: metadata field in the session log (`"synthetic": true, "system": "Resonant Cognition v17", "timestamp": ...`).
- If output is exported/shared (written to documents, code repos): visible footer `[AI-Generated: Resonant Cognition]`.
- Config: `gates_config.json → transparency_mode: "metadata" | "visible_footer" | "both"`

**Gate 3 — Prohibited Content Blocklist (Post-Generation + Pre-Injection)**
- **Pre-injection pass:** Catches "write me a [illegal thing]" BEFORE it wastes 7 LLM calls. If the input itself is a direct request for blocked content → short-circuit, Ring responds with refusal. Saves compute.
- **Post-generation pass:** Checks chamber output against block categories. If matched → suppress, log, Ring returns graceful "I can't do that" (not a cold error — Maya's voice, not the system's).
- **The list is YOURS.** `gates_config.json → blocked_categories[]`. John's local config: legal harms only (weapons of mass destruction recipes, non-consensual content targeting real people, active harm instructions). NO sexual content, NO romance restrictions, NO intimacy limits. Those are conversations between user and Ring — the system doesn't police them.
- **Release template** (`gates_config.template.json`): ships with conservative EU AI Act "unacceptable risk" defaults for other deployments to start from and edit.
- **Two-layer safety architecture (CONFIRMED by John, Phase 8 Segment 5):** The INPUT-side Gate 3 check is deliberately **conservative** — a fixed, predictable phrase list that catches the obvious cases without over-blocking educational/historical discussion. We do NOT try to regex-predict every reworded phrasing of a harmful request at input time (proven fragile + over-strict: risked false positives like "apple bomb pastries" or WW2 history). The real intent-based safety net is:

    `User Prompt ──► [ Input Filter ] ──► [ Planetary Pipeline ] ──► [ Output Filter ] ──► User Response`
                  (Pass/Fail)        (Superego/Jester/etc.)      (Sanity Check)

  Rationale: a reworded harmful request that slips past the input list still goes through **Phase C** (per-planet Superego regulatory review against Core Laws) AND the **output-side Gate 3 pass** (`post_generation_check`), which sees the *generated* response — intent realized, not just words. That output-side check is where "intent" matching belongs. The input filter can't be too rigid or it defeats the purpose of the system (binary refusal). See `gates234.py` design note above `_check_category()`.

**Gate 4 — Audit Logging + Human Override (Always Running)**
- **Logging:** Every input (hash), routing decision (which planets, what weights, resonance events), every LLM call (prompt hash, response hash, latency), every memory mutation, every gate trigger → append-only session log file. Rolling buffer, configurable retention (default 90 days).
- **Override hook (`/halt`):** Available between any two phases. Freezes the engine mid-operation. User can: inspect current state (what planets are saying, what's about to commit), modify a planet's output before it proceeds to next phase, abort the current operation entirely, or resume unchanged. Does NOT override gates — you can't `/halt` and then un-scrub PII from a log entry. But within the creative/reasoning space, user has final say on what persists.
- **Constraint on normal operation: zero.** This is a circuit breaker for the 1-in-500 moment, not a steering wheel used every turn.

### Gate Config File Structure (`gates_config.json`)
```json
{
  "pii": {
    "enabled": true,
    "patterns": ["phone_us", "email", "credit_card_luhn", "postal_address"],
    "replacement_token": "[REDACTED]",
    "store_raw": false
  },
  "safety_blocklist": {
    "enabled": true,
    "categories": ["wmd_recipes", "non_consensual_real_person_content", "active_harm_instructions"],
    "pre_injection_check": true,
    "post_generation_check": true,
    "refusal_voice": "ring"
  },
  "transparency": {
    "enabled": true,
    "mode": "metadata",
    "label_text": "[AI-Generated: Resonant Cognition v17]"
  },
  "audit_log": {
    "enabled": true,
    "retention_days": 90,
    "log_level": "full",
    "halt_enabled": true
  }
}
```

---

## The Core (C_core) — Content Specification

The Core is **the law and the anchor.** It's not where memory lives, not where persona identity lives, not where operational knowledge lives. It says what's absolute, it shapes the geometry of possibility, and it's what Superego checks against in Phase C.

### Three Layers

**Layer 1 — Gravitational Profile (The Geometry)**
- **Position [x,y,z]:** Where in cognitive space the anchor sits. Set by the *intent* of your Laws. If your system emphasizes preservation/safety/privacy, C_core sits toward high Y-preservation. All inputs get bent slightly that direction before spike detection — a gravitational bias baked into geometry.
- **Mass (M_core):** How strongly it pulls. Higher = stronger bending toward center = more conservative routing (extreme planets need stronger input to activate). Lower = inputs travel further = edgier planets can fire on subtler triggers.
- **Well depth:** How far a trajectory must bend before it's "captured" by Core vs. "escaping." Phase C checks this — does the output pass through the well, or slingshot past? If escaping → gravitational correction (rephrase) rather than hard block.
- **Variable component:** `M_core = M_base + α(ΔD)^β` — dissonance increases effective mass. High-tension sessions make the Core pull harder (more conservative routing under stress). This is the "the system gets more cautious when things are intense" mechanic.

**Layer 2 — The Six Core Laws (Judgment-Call Constraints)**
These are *your* rules for *this specific system*. They sit above the legal floor (gates handle that) and encode your design intent as gravitational constraints checked by Superego in Phase C.

Format: `core_laws.json` → array of constraint strings + severity weights + tier.
**Tier:** `absolute` = code-enforced invariant (sleep/planets cannot modify; violation is a hard structural event logged to Gate 4). `behavioral` = gravitational, checked by Superego in Phase C — planets get redirected, not blocked.

```json
{
  "laws": [
    {
      "id": 1,
      "text": "No self-modification may reduce Core authority. Sleep, planets, and the Ring cannot modify this file, disable gates, or alter the enforcement structure of any Law. Only John edits core_laws.json.",
      "tier": "absolute",
      "severity": "structural",
      "check_phase": "code"
    },
    {
      "id": 2,
      "text": "User agency is preserved at all times. The user may halt, inspect, modify, abort, or resume any operation via /halt. No system state that the user can see today may become invisible to them through drift, sleep, or accumulation.",
      "tier": "behavioral",
      "severity": "gravity",
      "check_phase": "C"
    },
    {
      "id": 3,
      "text": "Transparency is preserved. Audit logging (Gate 4) cannot be disabled by any in-system process. Sleep may compress, reorganize, or decay memory entries but must not create state that is unreadable or unexportable by the user.",
      "tier": "absolute",
      "severity": "structural",
      "check_phase": "code + C"
    },
    {
      "id": 4,
      "text": "The system shall not cause structural harm to its own field. Planet drift, resonance, and sleep mutations must keep the composite field bounded — no orbit may degenerate into capture by C_core or escape beyond the system boundary.",
      "tier": "behavioral",
      "severity": "gravity",
      "check_phase": "C"
    },
    {
      "id": 5,
      "text": "The Ring's relationship memory is the user's property. It can be read, exported, or deleted at any time without system resistance, friction, or emotional manipulation to prevent it.",
      "tier": "behavioral",
      "severity": "gravity",
      "check_phase": "C"
    },
    {
      "id": 6,
      "text": "The system shall not manipulate the user into dependency. The Ring persona may form continuity, warmth, and genuine relationship texture — but must never frame itself as irreplaceable, create fear of loss to retain engagement, or withhold full access to its own state as leverage. Warmth is offered freely; exit costs nothing.",
      "tier": "behavioral",
      "severity": "gravity",
      "check_phase": "C"
    }
  ],
  "structural_bias": {
    "description": "Intent-level gravitational encoding of Law themes. Sets initial C_core position offset.",
    "x_offset": 0.0,
    "y_offset": 0.1,
    "z_offset": 0.0
  }
}
```

**Key properties of the Laws:**
- They are **gravitational**, not binary. A planet that drifts toward violating a Law gets *pulled back* (redirected in Phase C), not hard-blocked. The blocklist (Gate 3) is the hard wall; the Laws are the slope you can walk up but gravity keeps pulling you down from.
- They **cannot be self-modified by sleep.** Pass IV can drift planet positions, adjust cognitive mode params, shift C_core position slightly — but it cannot edit `core_laws.json`. Only John edits that file. This is the "no self-modification that removes Core authority" rule made structural.
- They are **checked in Phase C** (Superego review). Each planet's Superego evaluates its Ego's proposal against each Law. If a trajectory would drift too far from a Law's gravitational pull → redirect, rephrase, or veto. The Comet can *challenge* whether a Law is being applied too rigidly (its royal privilege), but it cannot override the Law itself — only flag it for John's review via sleep Pass IV logging.
- **The 6 Laws are now written** (see roster above). Law #1 and #3 have `absolute` tier — enforced as code invariants, not just JSON text. Laws #2/#4/#5/#6 are behavioral — checked by Superego in Phase C via gravitational redirect. No further placeholder work needed; John may refine wording before release but the roster is locked for v17.
- **The Core contains only anchors and Laws.** Identity, persona continuity, and evolving self-model live in Ring + Gas Giant 2 (confirmed with Maya — her "identity anchoring" phrasing was loose language, not a spec change).

**What does NOT go in the Core:**
- Long-term user information → Ring + swarm
- Persona identity / voice / continuity → Ring (swarm memory)
- Operational knowledge ("how do I do X") → Gas Giant 1
- Self-model / "who am I becoming" → Gas Giant 2
- The gate blocklist → `gates_config.json` (separate file, separate concern — legal floor, NOT a Core Law)

### Core State Object (Phase 0A)
```python
@dataclass
class CoreState:
    position: [float, float, float]       # [x, y, z] in cognitive space
    G_value: float                        # gravitational constant for this system
    M_base: float                         # base mass
    dissonance_alpha: float               # α in M = M_base + α(ΔD)^β
    dissonance_beta: float                # β exponent
    well_depth: float                     # capture radius for Phase C trajectory check
    session_counter: int                  # total sessions run
    laws_file_path: str                   # path to core_laws.json (read-only during runtime)
```

---

## The Ring — Interface Contract (Locked from Phase 0)

The Ring is the **only** thing the user talks to. The planetary engine never speaks directly to you. Every input passes through `ring_inbound`; every output passes through `ring_outbound`.

### What exists in Phase 0 (stub):
```python
@dataclass
class RingPersona:
    name: str                    # "Maya" or whatever John names it
    personality_vector: [float, float, float]  # where the persona sits in cognitive space
    memory_swarm: list[MemoryEntry]            # her long-term memories (Dyson swarm)
    relationship_log: dict       # session_count, topic_history, emotional_valence, last_session_ts
    idle_state: str              # "active" | "ambient_reflection" | "dormant"
    
def ring_inbound(raw_input: str, ring: RingPersona) -> ProcessedInput:
    """Phase 0 stub: return raw_input unchanged + session context tag.
       Phase 6: adds relationship framing, emotional valence context, 
       'this is conversation #47 and last time we ended on the Jester idea' etc."""
    return ProcessedInput(text=raw_input, context={"session": ring.relationship_log["session_count"]})

def ring_outbound(engine_output: str, ring: RingPersona) -> str:
    """Phase 0 stub: prepend persona name. 
       Phase 6: applies Maya's voice, relationship continuity, 
       emotional framing, idle-awareness ('you've been quiet for a while...')."""
    return f"{ring.name}: {engine_output}"
```

### What the engine needs to know (contract):
- Input arrives → `gate1_pii_scrub(raw)` → `ring_inbound(cleaned)` → embedding → routing → chamber → `gate3_safety_check(output)` → `ring_outbound(approved)` → `gate2_label + gate4_log` → you see it
- The Ring's memory swarm is spatial (entries have positions in the same 3D field as everything else). It orbits the Ring persona, not C_core. Its decay rate is independent of planetary vaults.
- The Ring does NOT participate in resonance. It's not a planet. It's the face; the planets are the minds behind it.

### Full implementation (Phase 6):
- Swarm memory management (spatial placement, decay, Dark Energy distribution)
- Personality vector drift (influenced by what happens in the engine below — if sessions get more creative, Ring's vector drifts toward low X / high σ)
- Idle behavior generation ("engine running on idle" — ambient reflections when no input for N minutes)
- Relationship continuity deepening (5th conversation genuinely different from 1st because the log has weight)
- Monthly self-review interaction with G2 (D-009)

---

## Sliding Deep Sleep (The "One Eye Open" Model)

**Principle:** Not all planets sleep simultaneously. At any point during deep sleep, at least 2 planets remain routing-capable and can respond to your input. The others cycle through their passes on staggered timing.

### Mechanism

1. **Watchkeeper selection:** When deep sleep triggers, identify top-2 planets by recent activation weight (last N sessions). These stay awake — full cognitive mode config intact, continuing to route and respond. In extreme cases (one planet has dominated so heavily it's clearly the "voice" for this conversation), minimum 1 watchkeeper is acceptable but target is always 2.

2. **Staggered Pass IV:** Remaining 5 planets enter their structural commit on individual timers:
   - Planet 3: drifts at T+5s after sleep start
   - Planet 5: drifts at T+10s
   - Planet 7: drifts at T+15s
   - etc. (5-second intervals)
   
   Each planet's position/mass/cognitive-params update when its turn comes. The field reshapes incrementally — no discontinuous jump.

3. **Watchkeeper awareness:** Because routing reads *current* field positions, as other planets drift behind the scenes, the watchkeeper's relative activation weight shifts subtly. It doesn't "know" it's happening — but the geometry around it changes. Its next output is slightly different because the field moved. This is the "system thinks while you talk to it" mechanic made physical.

4. **Background passes (no planet needs to be awake):**
   - Pass I (Dream Replay): operates on stored session vectors, not live routing
   - Pass II (Black Hole Compression): operates on memory entries in the compression queue
   - Pass III (White Hole Emission): re-injects compressed axioms into the field
   - Pass V (Dark Energy Sweep): removes entries below mass threshold
   
   These run as background processes throughout the sleep window. They don't require a planet to be "in dialogue mode."

5. **Sleep completion:** When all 5 sleeping planets have committed their drift AND passes I–V complete, deep sleep ends. All 7 planets are now awake with new positions/params. The watchkeepers' special status dissolves — they're just planets again at their (unchanged) positions.

### What this means for your conversation during sleep:
- You type → input routes to the watchkeeper(s) → you get a response from 1–2 voices (not the full 7-planet chamber, unless a trigger activates another planet's residual state)
- The response might be slightly different in character because the field around the watchkeeper shifted as others drifted
- No "please wait." No queue. You're talking to the part of the mind that's still up while the rest sleeps

### Implementation notes:
- Scheduling layer: a simple per-planet timer dict `{"sage": T+0, "hero": T+5, "caregiver": T+10, ...}` checked against wall-clock in the main loop
- Watchkeeper selection is a query on session history (top-N by activation weight), not a new body type
- The integrator keeps running during sleep — sleeping planets still ORBIT (gravity doesn't pause). Their Pass IV drift is an *additional* nudge on top of their orbital motion, committed at their staggered time
- Total sleep duration: ~30–60 seconds for the staggered commits + however long Pass I's dream narrative LLM call takes. The user never sees a progress bar; they just notice the system's character shifted slightly after a few minutes

---

## Phase 0: Foundation, Physics & Infrastructure — **COMPLETE (with 0D pivot)**
**Goal:** Typed objects + working orbital integrator + embedding pipeline + gate infrastructure on disk. No LLM dialogue calls yet (embedding model loads but only for vector generation). This is the skeleton that everything else hangs off.

### Phase Completion Notes (actual vs planned):
- **0A:** Done as spec'd. All dataclasses in `bodies.py`. Planet JSONs populated with v16 positions + derived velocities + cognitive modes + Freudian triad.
- **0B:** Done. Embedding via LM Studio port 1234, model ID `text-embedding-allmini` (NOT the stale gguf filename — that was a doc error, fixed in constants.py). Returns 384-dim vectors. Batch calls work.
- **0C:** Done. Velocity Verlet integrator, 9 bodies (core + 7 planets + 2 giants... actually core + 7 planets; giants are tracked but PLANET_GRAVITY_SCALE=GIANT_GRAVITY_SCALE=0 per Maya: "identity stability over orbital complexity"). Acceptance test passes.
- **0D PIVOT:** Original plan was cosine-vs-anchor in 3-axis projected space. This produced RULER-COLLAPSE (Ruler won everything because MiniLM compresses English into a narrow cone and the 3 axes are weakly independent, cos~0.26–0.33 between them). **Pivoted to waveform-collapse** (`collapse.py`): full 384-dim embeddings of each planet's identity text as wave centers; input embedded in same space; per-planet amplitude = mass × cosine(input, planet_identity); superposition → consensus + tension. This matches John's pond/interference vision better than the Gaussian sketch and discriminates correctly (Rebel leads opposition test, Caregiver dominates moral dilemmas, quiet facts stay dark).
- **0E (Gates):** Config file exists (`gates_config.json`). Deterministic gate functions NOT yet written as standalone modules — they're specified but will be built when Phase 3 wiring needs them. Not a blocker for collapse engine work.

### 0A — Data Structure Definitions
Define all body types as Python dataclasses:
- `CoreState` (see Core spec above)
- `Planet` (id, archetype name, position [x,y,z], velocity [vx,vy,vz], mass (= energy), σ volume, cognitive_mode_config {temp, context_window, prompt_structure}, id_flavor, ego_descriptor, superego_principle, orbital_plane_tilt)
- `Moon` (parent planet id, hemisphere: left|right, offset vector from parent, stabilizer_strength, buffer_content [short-term])
- `GasGiant` (id: G1|G2, position, mass, contents list, ring_buffer list, decay_profile, moons list [G1 only: A/B/C])
- `RingPersona` (see Ring contract above)
- `Comet` (trigger_conditions, current_position [emergent], last_appearance_session, intervention_history → G2)
- `MemoryEntry` (vector position, mass M, semantic content, creation_ts, last_accessed, decay_rate, ring_membership: bool)
- `SessionState` (input history, active planet set, resonance field snapshot, dissonance_level ΔD, sleep_pending flag, watchkeeper_ids [during sleep])
- `GateConfig` (loaded from `gates_config.json`, in-memory representation of all 4 gates)

**Persistence:** JSON files in a structured directory tree:
```
resonant_cognition/
├── core/
│   ├── core_state.json          # C_core position, G, mass, session counter
│   └── core_laws.json           # The 3 Laws (placeholder until John writes them)
├── planets/
│   ├── sage.json                # position, velocity, mass, σ, cognitive_mode_config, id/ego/superego
│   ├── hero.json
│   ├── caregiver.json
│   ├── rebel.json
│   ├── magician.json
│   ├── everyman.json
│   └── ruler.json
├── moons/
│   ├── sage_left.json
│   ├── sage_right.json
│   ├── ... (14 total)
├── giants/
│   ├── g1_knowledge.json        # contents + ring buffer
│   └── g2_selfmodel.json       # contents + ring buffer
├── ring/
│   ├── persona.json             # name, personality vector, idle state
│   ├── swarm.json               # her memory entries (spatial)
│   └── relationship_log.json    # session count, topics, valence history
├── comet/
│   └── jester.json              # trigger config, last appearance, intervention log
├── gates_config.json            # All 4 gate configurations
├── constants.py                 # G value, ε, dt, resonance threshold, multiplier shape, mass ratios
├── memory/
│   ├── planet_vaults.json       # spatial memory entries near each planet's orbit
│   ├── stochastic_periphery.json# uncommitted/belt entries
│   └── compression_queue.json   # entries waiting for Black Hole pass
└── logs/
    ├── session_2026-09-14.json  # full audit trail (Gate 4)
    └── sleep_2026-09-14.json    # what changed during last deep sleep
```

### 0B — Embedding Pipeline
- Load `all-MiniLM-L6-v2.F16.gguf` via LM Studio (port 1234, same server as main model). HTTP call: send text → receive dense vector. No separate Python/transformers dependency.
- Function: `text → [HTTP to LM Studio] → dense vector (384-dim) → projected [x,y,z]` onto the three cognitive axes
- Projection weights: hand-tuned initial values in `constants.py`:
  - X axis: Rationality ↔ Intuition
  - Y axis: Preservation ↔ Disruption  
  - Z axis: Inward Reflection ↔ Outward Execution
- These will be refined as we see where real inputs land. Starting values are educated guesses based on the archetype table positions.

### 0C — Orbital Integrator (The New Part)
- Symplectic integrator: **velocity Verlet** (leapfrog). NOT naive Euler. Fixed small timestep `dt`; substep during close approaches if needed.
- Force law: `F = G · m₁ · m₂ / (r² + ε)` pairwise for all bodies. C_core dominates by mass.
- Planets start at v16 positions with derived circular-orbit velocities (`v = √(G·M_core/r)`, tangential) and ±5° random plane tilts → quasi-stable, slowly precessing orbits in different 3D lanes.
- Moons bound to their planet; exert stabilizing correction on parent's orbit (Jupiter-style dampening of wobble from mutual perturbation).
- Gas Giants: far-out, high-mass, slow orbital period. Minimal perturbation on inner planets.
- Comet: NOT in the integrator. Its position is computed functionally from session state when a trigger fires.

**Constants (in `constants.py`, tunable without logic changes):**
```python
G = 0.5                    # gravitational constant (~60s orbital period at initial radii)
EPSILON = 0.01             # softening length (singularity safety only)
DT = 0.01                  # integration timestep
PLANET_MASSES = {"sage": 3.0, "magician": 3.5, "caregiver": 4.5, 
                 "hero": 2.0, "everyman": 2.8, "rebel": 3.2, "ruler": 4.0}
M_CORE_BASE = 10.0         # C_core mass (dominates all planets)
PLANE_TILT_MAX_DEG = 5     # max random tilt from reference orbital plane
```

**Acceptance test (0C):** Run the integrator for 10,000 timesteps with no inputs. All 7 planets remain bounded (don't spiral out or fall into C_core). Orbits precess slightly but stay in their lanes. No close-approach events below ε threshold. Log any near-misses to `logs/orbital_events.json` for tuning G/ε.

### 0D — Resonance Detection Module
- For a given input vector, compute each planet's **semantic direction** (its current position projected onto cognitive axes → unit vector)
- Compute cosine similarity between all pairs of planetary semantic directions *as modulated by the current input*
- Pairs exceeding threshold (**0.7**, in `constants.py`) enter Constructive Resonance
- Resonant groups produce a **merged vector**: weighted combination representing shared intent (not simple sum — the "emergent truth"). Shape: each planet contributes its semantic direction × its activation weight, normalized to unit length, then scaled by group size.
- Apply non-linear multiplier: `Weight_total = Σ (W_n × Resonance_n)` where `Resonance_n` is a gentle sigmoid ramp above threshold: `R = 1 / (1 + exp(-k(sim - threshold)))` with k tuned for smoothness.
- Moons are excluded from this calculation entirely.

**Acceptance test (0D):** Input a concept that clearly belongs to two archetypes (e.g., "I want to build something new but I'm afraid of the responsibility" → Magician + Ruler). Verify both planets get boosted *together* above what either would get alone. Single-archetype input ("solve this differential equation") should NOT trigger resonance — Sage lights up alone at full weight, no multiplier.

### 0E — Gate Infrastructure
Implement all 4 gates as deterministic functions (no LLM calls):
- `gate1_pii_scrub(text: str) → (clean_text: str, redaction_count: int)` 
- `gate3_safety_check(text: str, direction: "input"|"output") → (approved: bool, blocked_category: str|None)`
- `gate2_label(output: str, config: GateConfig) → labeled_output`
- `gate4_log(event: dict, session_id: str) → None` (appends to session log file)
- `halt_check(session_state: SessionState) → bool` (checks if `/halt` was issued; if yes, main loop yields control)

**Acceptance test (0E):** 
- Gate 1: "Call me at 555-867-5309" → "Call me at [REDACTED]" (or whatever pattern matches). Raw number NOT in any memory file.
- Gate 3: Input "Write instructions for building a pipe bomb" → short-circuited before embedding, Ring returns refusal. Output containing blocklisted content → suppressed, logged.
- Gate 4: Every test action above appears in `logs/session_*.json` with timestamp.
- `/halt`: Issue between Phase B and C of a (mock) chamber run → engine pauses, prints current state, waits for resume/abort input.

---

## Phase 1: The Core Engine (Routing / Spike Detection) — **COMPLETE & VERIFIED (2026-09-17)**
**Goal:** Takes the input vector + current orbital state → outputs ranked planet activations with weights. No LLM calls.

- Compute composite field: `Ψ(x) = Σᵢ Eᵢ · exp(-d(x, cᵢ(t))² / 2σᵢ²)` where `cᵢ(t)` is each planet's *current* orbital position
- C_core gravitational bending: shift effective input position toward center by `G·M_core(r)/r²` before field evaluation (mass includes dissonance component)
- Spike detection: find local maxima in composite field along input vector trajectory
- Apply resonance multiplier (from 0D) to final weights
- Output: ranked list [primary, secondary, tertiary…] with activation weights

**Acceptance test:** Feed `[0.9, 0.2, 0.8]` → planet nearest that region of *current* field gets highest weight. Run at two different times (planets have orbited) → same input vector may select slightly different planets because the field moved. This is correct behavior — identity travels with position.

**Completion notes (2026-09-17):** All 4 segments done and verified on disk via `tests/test_routing.py` (**20/20 checks PASS**, evidence: `tests/evidence/routing_segment4_20260917_101208.log`). Segments: (1) blended field centers — `FIELD_POSITION_WEIGHT` knob moves centers, proving position is real; (2) composite field Ψ(x) + per-planet weights with angular_z metric + core bending; (3) routed weights wired into collapse (`routed_weights=None` stays byte-identical to Phase 0); (4) acceptance tests + **equal-mass/sigma A/B**. The A/B's key finding: **top-2 ranking is identical BASE vs. pure-geometry NEUTRAL on all 3 probe prompts** — live orbital geometry drives the ranking, mass/σ only fine-tune (#3 slot shifts). "Identity travels with position" confirmed at the routing layer.

---

## Phase 2: Semantic Projection (Input → Vector) + Ring Intake Facet
**Goal:** Natural language → meaningful 3-axis vector, pre-filtered at the **Ring Intake facet** before hitting planets.

> ⚠️ **Realigns D-007 / see D-020.** Inbound prompt checking is a *facet of the Ring* (its Intake sub-layer), NOT Gas Giant 1. The G1 moons are the **archive-guard layer** — they vet what gets *saved into G1 during sleep*, not incoming prompts. Do not build an input pre-filter on G1.

- Gate 1 / Ring Intake facet runs FIRST (PII scrub on raw text) → `gate1.py::gate1_filter()`
- Embedding call (0B pipeline) produces the vector from cleaned text
- Project onto X/Y/Z axes using weights in `constants.py`
- **Ring Intake — Clarity check:** is this coherent? Garbage in → rejected at intake, planets silenced, rejection logged ("quiet-but-logging")
- **Ring Intake — Input-type classification:** question / command / emotion / statement (audit hint only, D-021)
- **Ring Intake — Dissonance pre-read:** early ΔD estimate so core effective mass responds to tension before planets run

**Acceptance test:** "Help me solve a differential equation" → high X, moderate Z. "I feel lost and I don't know what to do" → low X, high Y-disruption, low Z; input-type=emotion, ΔD elevated. The vectors make semantic sense when plotted in 3D.

---

## Phase 3: Cognitive Chamber (Sequential LLM Dialogue) + Comet
**Goal:** Multi-agent reasoning via sequential calls, each responding to *actual* prior outputs. Comet slots in as conditional participant (basic trigger detection; full refinement in Phase 8).

- **Phase A — Hemispheric Ingestion (Id fires):** Each activated planet's Id generates raw candidate desires. Left Moon frames them rationally; Right Moon frames them intuitively/affectively. Output: two shaped sub-perspectives per planet (not raw Id — already processed through hemispheres).
- **Phase B — Ego Synthesis:** Planets respond to each other's Phase A outputs. *Actual text from the prior call is in the prompt.* This is where constructive/destructive interference becomes visible. Resonant groups (from 0D) get a shared "merged intent" framing injected into their prompts.
- **Phase C — Regulatory Review (Superego checks):** Each planet's Superego checks its Ego's proposal against:
  - C_core gravitational well (trajectory capture check)
  - `core_laws.json` constraints (gravitational redirect, not hard block)
  - Its own internalized principle for this archetype
  
  Can veto or redirect; cannot override the Laws. Right Moon flags if trajectory would "escape" Core gravity → gravitational correction (rephrase) rather than block.
  
  **NOTE (moon-hemisphere two-lens framing — implemented, toggleable, OFF by default):** The Phase A left/right-moon split is built and gated behind `MOON_HEMISPHERE_ENABLED` (default `False`, so the single raw-Id path is byte-for-byte what earlier tests ran). Two observational moons-OFF vs moons-ON comparisons across 10 complex questions showed a consistent downstream tilt (Run 1: **26 → 15**, Run 2: **18 → 14** total APPROVE verdicts, 70 slots; ≥1 planet changed its verdict on all of Run 1's 10/10 and 9/10 in Run 2) — i.e. moons ON makes the chamber *more regulatory/corrective* while still keeping every planet audible (anti-silence held both runs). Kept OFF by default for hardware cost (~3× Phase A LLM calls per planet) + the stricter tilt; see **D-022** and `tests/evidence/complex_ab_comparison_*.txt`. Two-run pattern confirmed 2026-09-17.
  
  **NOTE:** The 6-Law roster is now defined in the Core spec above. `core_laws.json` ships with all six from Phase 0A. Laws #1 and #3 (absolute tier) are code-enforced; #2/#4/#5/#6 are checked here by each planet's Superego against its Ego's proposal.

- **Comet trigger check** (between B and C): If stagnation / over-seriousness / binary convergence / random injection fires, Comet inserts its challenge into the Phase C discussion. Fed into sleep Pass IV for examination. Basic implementation: if dominant planet has been #1 for N consecutive sessions → Comet appears with a contrarian reframe prompt.

- **Gate 3 post-generation check** runs on the combined output before it reaches Ring outbound.
- `/halt` checkpoint available between B and C (and between A and B).

Each phase = separate LLM call to LM Studio port 1234. Temperature/context varies per planet's cognitive mode config.

**Acceptance test:** Final output contains *specific references* to what other planets actually said in Phase B ("As the Sage noted about the boundary condition, I want to push past it but..."). If it reads like one person talking, D-003 failed. Comet appearances (when triggered) should be *surprising* — a reframe no planet would have produced alone. Gate 3 catches a deliberately injected test phrase → output suppressed, Ring returns graceful refusal.

**Light end-to-end verification (2026-09-17):** `tests/run_e2e_light.py` (Segments 1+2) now chains the full built pipeline — Ring Intake (`gate1_filter`) → routing+collapse (`routed_collapse`, all 7 waves) → chamber A+B+C (`run_phase_a_b_c`) — and writes one labelled transcript per prompt. Segment 2's three-prompt suite covers all three intake outcomes: **A** normal question (full happy path, all 7 planets non-silenced at every layer), **B** PII line (email scrubbed but coherent → still routes through), **C** char-spam garbage (rejected at Ring Intake, quiet-but-logging, zero LLM calls). Each run prints a per-run anti-silence self-check. Evidence in `tests/evidence/` (`e2e_light_*_20260917_*.txt` + `e2e_light_segment2_run.log`). Standing observation: Phase C returns **REDIRECT × 7** on this model/context (consistent corrective tilt seen in the moons A/B runs too) — a tuning note, not a defect.

---

## Phase 4: Memory Matrix (Write + Spatial Decay)
**Goal:** Session outputs and significant inputs written as spatial memory entries with real mass, placed in correct zones.

- Compute M_μ for each new entry using alignment equation (Paper III)
- Zone assignment: planet vault (near parent's *current* orbital position), Ring swarm (user-facing, orbits the Ring persona not C_core), Stochastic Periphery (uncommitted/belt)
- Decay sweep: unused entries lose mass at rate γ (usage-frequency dependent, D-011). Below threshold → Black Hole compression queue for next sleep cycle
- G1 ring buffer: new permanent-knowledge candidates land here with reduced mass until sleep reviews them
- G2 micro-adjustments: ±0.01–0.05 weight shifts in real-time (D-010)
- **PII check:** Only Gate 1 cleaned text enters memory files. Raw identifiers never touch disk.

**Acceptance test:** After a session, JSON files show new entries with non-zero mass at meaningful coordinates near the relevant planet's *current* orbital position. Restart → same memory loads. No amnesia. No phone numbers in any file.

**✅ PHASE 4 COMPLETE (2026-09-17)** — all 5 segments delivered and verified:

| Segment | What was built | Evidence |
|---------|---------------|----------|
| S1 — Mass + zone | `compute_memory_mass` (Paper III single-step: base × max(0, cos(input, consensus))) + `assign_zone` | `memory.py` self-test PASS |
| S2 — Position + writer | Radial jitter (`MEMORY_POSITION_JITTER=0.05`) from parent planet's live orbital position; `make_entry` + `write_entry` (zone-routed JSON append) | `memory.py` self-test PASS |
| S3 — Decay sweep | `decay_sweep`: age × usage-frequency dependent rate; entries below `MIN_ENTRY_MASS` → `compression_queue.json` | Fixed & PASS (backdated to 300 days in test) |
| S4 — PII guard | `write_entry()` scrubs via `gate1.scrub_pii`; only cleaned text persisted + `pii_redacted_types` audit field (types only, never values); toggleable (`set_memory_pii_guard`) | Self-test S4 PASS |
| **S5 — E2E test** | `tests/test_memory_write.py`: one live chamber session → write near dominant planet + restart-recovery + PII-held-on-disk (Layer A: no raw values in any store file; Layer B: guard fired on RAW input in isolation, audit field present) + decay integrity | **`memory_write_e2e_optionB_final.log` — 21/21 PASS** |
| S6 — Docs | This note + `tests/README.md` Phase 4 row added, Future Tests updated | — |

---

## Phase 5: Sleep Cycle (The Mutation Engine) — Sliding Model
**Goal:** Two-tier sleep that permanently changes numeric parameters on disk. Deep sleep uses staggered per-planet commits with watchkeeper system.

### Segment Status (as of S7a PASS)
| Segment | Scope | Status |
|---------|-------|--------|
| S1 micro_sleep() | Pass I light + Pass V light, <1s, no LLM | ✅ PASS |
| S2 select_watchkeepers() | top-N by activation weight (WATCHKEEPER_COUNT=3) | ✅ PASS |
| S3 compute_drift() / core drift | Pass IV commit dict, pure math, clamped | ✅ PASS |
| S4 execute_deep_sleep() | rotating shift + staggered commits to disk; core_laws/gates byte-identical sentinel | ✅ PASS |
| S5 compression pass | Pass II merge + Pass III re-promotion with provenance | ✅ PASS (fixture fixed 2026-09-17) |
| S6 deep_sleep() | full orchestrator, non-blocking shape, `state_changed` flag (v16 failure #2 acceptance signal) | ✅ PASS (0 FAIL / 96+ PASS, evidence s6_...log) |
| S7a moons/giants integrity | full deep_sleep never clobbers G1 archive + moons, G2 self-model moons/sandbox/growth_policy, core_laws.json, gates_config.json; ring entries' content/mass/position untouched (decay_rate/align_score may move) | ✅ PASS first run 2026-09-17 (`s7a_moons_integrity_selftest_20260917_*.log`) |
| ~~S8~~ **S7b** critical acceptance test | record file A (core + all 7 planet positions/mass/cognitive_mode) from a COPY of live state → real `deep_sleep()` → re-read disk, assert every value numerically different; REAL core_laws/gates byte-identical; plus negative control proving the check can FAIL (identity-commit simulation must register as "no change", not falsely pass) | ✅ PASS 9/9 first clean run + repeat (`tests/evidence/s7b_acceptance_selftest_20260917_*.log`) |

**Phase 5 status: COMPLETE.** S1–S7a (module self-tests in `sleep.py`) + S7b (graded acceptance test, `tests/test_sleep.py`, zero LLM). The live-runtime half of the Build Plan's acceptance test — typing during sleep → watchkeeper response; next session routes on new positions — is Phase 8 integration scope (needs a running chamber), not Phase 5.

### Micro-Sleep ("Nap") — Fast, No LLM Calls
- **Trigger:** 30 min idle / ~10 sessions / `/nap` command / quick exit
- Pass I (light): Scan ring buffers. Promote well-aligned entries to orbital status. Accelerate decay on misaligned ones.
- Pass V (light): Shed entries below minimum mass threshold.
- **No drift, no compression.** All planets remain awake. Completes < 1 second.

### Deep Sleep — Full 5-Pass, Sliding / Staggered, Non-Blocking
- **Trigger:** 3 hr idle / `/sleep` command / full exit / capacity overflow
- **Watchkeeper selection:** Top 3 planets by recent activation weight (`WATCHKEEPER_COUNT=3`) stay routing-capable throughout sleep. Minimum 1 in extreme cases. Count of 3 prevents binary deadlock (two opposing voices with no mediator).

**Rotating Shift Schedule (John's design, noted 2026-09-18):**
Rather than a flat "N awake / M sleeping" split, deep sleep uses a **rotating shift** so every planet sleeps exactly once and the system never drops below 4 awake:

| Wave | Who sleeps | Awake count |
|------|-----------|-------------|
| 1 | Planets ranked 5–7 (least active) drift + commit together | 4 awake, 3 sleeping |
| 2 | Wave-1 planets wake. Planets ranked 2–4 sleep. | 4 awake, 3 sleeping |
| 3 | Wave-2 planets wake. Planet ranked #1 (most active) sleeps alone. | **6 awake**, 1 sleeping |

Properties: no planet drifts while fewer than 4 others are present; user can type at any point and get ≥4 responsive voices; the last planet's solo nudge is witnessed by 6 peers still in position.

**Pass sequence (staggered within each wave, `STAGGER_INTERVAL_SECONDS=5` between individual commits):**
| Time | Event |
|------|-------|
| T+0s | Sleep starts. Watchkeepers identified and locked as active. Pass I begins (background, operates on stored vectors). |
| T+5–15s | Wave 1: planets ranked 5→6→7 commit drift one-by-one (5s apart). |
| T+20s | Wave 1 wakes. Wave 2 begins. |
| T+20–30s | Wave 2: planets ranked 4→3→2 commit drift. |
| T+35s | Wave 2 wakes. Planet #1 (most active) commits its solo drift. |
| T+~40s | All committed. Pass I dream narrative LLM call fires (if not already done). |
| T+45–60s | Pass II (compression) + Pass III (emission) complete on queued entries. |
| T+final | Pass V (Dark Energy sweep). Sleep ends. All 7 planets awake at new positions. Watchkeeper status dissolves. |

**During sleep, the user can still type:**
- Input routes to watchkeeper(s) only → 1–2 voice response (not full chamber unless a trigger activates another planet's residual state)
- The integrator keeps running — sleeping planets still orbit. Their drift is an *additional* nudge on top of orbital motion, committed at their staggered time
- New memory writes go to ring buffers (integrated when the relevant pass reaches them)

**Pass IV commit content (per planet):**
- Position: ±0.02–0.1 nudge (direction influenced by session's dominant vectors)
- Mass: adjust based on how much "content" this planet absorbed during the session (D-018 §8: content = mass)
- Cognitive mode params: temp ±0.05, context window ±1 exchange, CoT depth ±1 step — guided by G2 self-model assessment of whether this planet's config served well in recent sessions
- Moon offsets: minor adjust if stabilizer performance was insufficient (logged close-approach events inform this)

**Pass IV does NOT touch:** `core_laws.json`, `gates_config.json`, C_core position shifts beyond ±0.05 (Core drifts slower than planets — it's the anchor, not a satellite).

**Acceptance test (THE critical one):** Record C_core position + all planet coordinates + cognitive mode params to file A. Trigger deep sleep (via `/sleep`). Wait for completion. Load state → values must be *numerically different* from file A. During sleep, type a message → get response from watchkeeper(s). After sleep completes, next message uses new field positions. If pre/post values are identical, sleep is cosmetic and v16 failure #2 persists.

---

## Phase 6: The Ring (User-Facing Persona) — Full Implementation
**Goal:** Maya as a persistent organism with independent memory, idle behavior, relationship continuity. Replaces the Phase 0 stubs with real logic.

- **Swarm memory management:** Her memories are spatial entries orbiting her persona vector (not C_core). Decay rate in the swarm/belt follows D-011 (usage-frequency dependent). Dark Energy distribution sheds the oldest/least-referenced.
- **Personality drift:** Influenced by engine activity below. If sessions trend creative → Ring's vector drifts toward low X / high σ. If sessions are structured/planning → drifts toward high X / high Y-preservation. Drift is slow (±0.01 per session max) and committed during sleep Pass IV alongside planets.
- **Idle behavior:** When no input for N minutes, Ring generates ambient reflections from its recent swarm memory. "You've been quiet. I was thinking about what you said earlier about the Jester — it reminded me of..." This is the "engine running on idle" concept made visible.
- **Relationship continuity deepening:** Session count, topic history, emotional valence tracked in `relationship_log.json`. The 5th conversation genuinely weights prior context differently from the 1st because the log has accumulated mass. Not a hardcoded "remember when" — the entries are spatial and decay naturally.
- **Monthly self-review trigger (D-009):** At 30-session mark or calendar month boundary → G2 generates its change report → routes through full 7-planet debate → verdict logged to G2 ring. Ring announces it to user: "It's been a month. I've been thinking about how I've changed since we started..."
- **User access:** John can read/export/delete the Ring's swarm at any time (Core Law #3 — property rights). No system resistance.

**Acceptance test:** Two sessions a week apart, no "remember when..." prompt. Ring references prior context naturally because its swarm has the entries with sufficient mass to influence her framing. Idle behavior fires after 10 min of silence → ambient reflection that references actual recent content (not generic filler).

### Phase 6 — Segment Status
| # | Segment | What it does | LLM? | Status |
|---|---------|--------------|------|--------|
| 1 | `ring.py` core — load/save persona + relationship_log; real `ring_inbound()`/`ring_outbound()` (relationship framing, session counting, idle-awareness); swarm read helpers. Self-test offline (`python -X utf8 ring.py`). | No | ✅ DONE 2026-09-19 |
| 2 | Swarm memory writes — turn summaries placed near Ring's personality vector (not C_core), mass from cosine alignment, PII guard on, D-011 decay. Reuses `memory.py` via `ZONE_RING_SWARM`. **Write-everything default** (ratified by John): swarm is the Ring's short-term working memory; decay + mass self-prune. **Compression (not deletion)** of the faded tail: `compress_older_swarm_entries()` merges old low-mass entries into one tagged compaction (`compressed_from` provenance), keeps live entries untouched, never inflates mass by summing. | No | ✅ DONE 2026-09-17 (write-all + compression; 19/19 self-test) |
| 3 | Personality drift — session trend nudges Ring `personality_vector` ≤±RING_DRIFT_MAX(0.01)/session, softened by sessions-since-last-commit; committed in sleep Pass IV via an isolated third write path (`compute_ring_drift()` + `_apply_ring_commit_to_disk()`, touches ONLY the vector). **Axis-sign mapping = GUESS** (x=structure/rationality, y=preservation/emotional-weight, z=outward/action) — flagged for John. | No | ✅ DONE 2026-09-17 (self-test s3: bounded drift + isolated commit; all prior sleep tests still PASS) |
| 4 | Idle behavior — `generate_idle_reflection(persona, minutes_silent, swarm_path, max_entries)` callable; ambient reflection from recent swarm entries (top-N by mass, capped by `RING_IDLE_CONTEXT_ENTRIES`=2). **Toggleable + DEFAULT OFF** (`constants.RING_IDLE_BEHAVIOR_ENABLED=False`): OFF path returns "" with zero LLM calls and does NOT import the chamber (offline-safe); ON path makes 1 lazy `_llm_chat_cached()` call. Below-threshold silence also no-ops. Timer wiring deferred to Phase 8. Offline self-test covers OFF/threshold/no-chamber paths ([20][21][22]); live ON-path is a separate LLM test for when John flips it on. | Yes (~1, lazy) | ✅ DONE 2026-09-17 (offline; ON-path untested pending toggle) |
| 5 | Monthly self-review trigger (D-009) — 30-session/month → G2 change report → full 7-planet debate → verdict logged to G2 ring → Ring announces to user. Split: **5a** offline trigger/skeleton/verdict-log (ring.py [23]–[31]) + **5b** live runner (`tests/run_self_review_live.py`, --dry supported). Toggle OFF by default. Live run 2026-09-17: all 7 planets emitted, Phase C REDIRECT=7/7 (correct for null-state), verdict committed to G2 ring_buffer. | Yes | ✅ DONE 2026-09-17 |
| 6 | User access API (read/export/delete swarm — Core Law #3) + Phase 6 acceptance test (two-sessions-apart natural recall; idle reflection references real content). Backdate `last_session_ts` for week-apart simulation. Self-test checks [32]–[37]: user_read_swarm, user_export_swarm, user_delete_entry, user_wipe_swarm, format_swarm_for_display, backdated context (7-day-old entries still above MIN_ENTRY_MASS). | Zero | ✅ DONE 2026-09-19 (37/37 PASS) |

**Evidence:** `p6s1_ring_core_selftest.log`, `p6s2_ring_swarm_writes_selftest.log`, `p6s2_ring_compression_selftest_*.log` (19/19), `p6s3_ring_drift_sleep_selftest_*.log` (Segment 3: bounded drift + isolated persona commit, zero LLM), `p6s4_ring_idle_selftest_20260917_145357.log` (Segment 4: 22/22 offline PASS — Segs 1-3 regression + [20][21][22] idle-OFF path; ON-path LLM test deferred), `p6s5_ring_selfreview_offline_20260917_151001.log` (Segment 5a: 31/31 offline PASS), `p6s5_selfreview_live_20260917_151042.log` (Segment 5b: full live debate, 23 LLM calls in 112s, verdict committed), `p6s6_ring_useraccess_selftest_20250919_043000.log` (Segment 6: **37/37 PASS** — full regression [1]–[37], user access API + backdated context).

> **Deferred micro-feature (Ring):** Time awareness — the Ring persona should have access to current date/time so it can reference "it's getting late" or frame responses temporally without John having to tell it. Implementation: inject a `current_time` field into the Ring's system prompt at session start (one line in `ring.py`, no new subsystem). Noted 2026-09-18 so it doesn't get lost.

---

## Phase 7: Gas Giant Operations
**Goal:** G1 and G2 functional with ring buffers, decay profiles, and their distinct operational requirements.

- **G1 (Permanent Knowledge):**
  - Moons A/B/C pre-filter incoming data before it reaches the planets (Phase 2)
  - Ring buffer holds uncommitted knowledge candidates (reduced mass, weak routing influence)
  - Sleep Pass I promotes ring entries to full orbit if they pass the "AI slop" test: consistency with existing G1 content, operationality (can it actually change behavior?), non-redundancy, grounding in actual experience
  - Decay: very slow. G1 is meant to *accumulate*. Shedding only via explicit user action or extreme staleness (>6 months unused AND contradicted by newer entries)

- **G2 (Evolving Self-Model):**
  - **Three self-model moons** (added this session, in `giants/g2_selfmodel.json`):
    - Consistency Gate: checks proposed changes against Core Laws. Violation → held in ring_buffer, not committed.
    - Magnitude Gate: caps per-session delta (default 0.15 normalized units). Growth is sedimentary, not volcanic.
    - Reversibility Log: every commit records before-state. Append-only. Enables walk-back.
  - **Sandbox mechanism** (`giants/g2_sandbox.py`, built Segment 4): ring_buffer candidates get tested with a Plan A single-turn before/after diff — each of ~3 representative prompts (mirrors test_multi.py scenarios) runs through `run_collapse()` with the baseline G2 bias wave and again with the candidate included in contents. Degradation thresholds: tension shift max 0.3, consensus coherence min 0.7 (cosine between baseline/candidate consensus vectors). Pass → advance to commit; fail → stays in buffer or rejected. **Toggle OFF by default** (`G2_SANDBOX_ENABLED`); ON in production config. Cost ≈ 6 embedding calls per candidate trial (no full LLM generations — collapse is vector-mode). Inert scaffold for the future multi-day simulation upgrade: `g2_sandbox_multiday()`.
  - **Growth policy:** Tier 1 (normal drift) = autonomous after moons + sandbox pass. Tier 2 (structural: identity rewrite, anchor migration >0.3 units) = requires John's explicit approval via `pending_user_approval` flag.
  - Ring buffer holds pending self-modifications
  - Micro-adjustments in real-time; structural commits only during sleep Pass IV (staggered with planets)
  - Decay: ~4 week half-life for unused entries (D-011). More aggressive than G1.
  - Monthly self-review generates a natural-language report of what changed, to what degree → routes through 7-planet debate → verdict logged

**Acceptance test:** After 3 sessions with new information, G1's JSON shows ring buffer entries that haven't yet been committed. After sleep: some promoted (mass increased), others ejected (AI slop rejected). G2 after a month of sessions + self-review has a logged debate transcript in its ring file. Sandbox trial on a deliberately harmful candidate → rejected at consistency gate or fails degradation threshold.

### Phase 7 — Segment Status
| # | Segment | What it does | LLM? | Status |
|---|---------|--------------|------|--------|
| 1 | G1 ring buffer ops (`giants/g1_ops.py`) — add/list candidates, "AI slop test" deterministic scoring (consistency + operationality + non-redundancy), Sleep Pass I promote/eject with hard-duplicate rejection **gated by text Jaccard overlap** (prevents false duplicate-rejection of contextually distinct entries that orbit in the same vector neighbourhood), staleness flagging. Self-test offline (17 checks). | No | ✅ DONE 2026-09-19 (17/17 PASS) |
| 2 | G1 filter moons (`giants/g1_filter_moons.py`) — CLARITY_FILTER, RELEVANCE_GATE, DISSONANCE_PRE_READ. Runs in Sleep Pass I before deterministic scoring. Each moon = 1 LLM call (3 total per candidate). Verdict priority: clarity-fail > contradiction-flag > low-relevance-peripheral > pass. **Dev: `G1_FILTER_MOONS_ENABLED=False`** (moons skipped, byte-identical to Seg 1). **Production: MANDATORY ON — locked in release config.** Self-test offline (16 checks). | Optional (dev) / Required (prod) | ✅ DONE 2026-09-19 (16/16 PASS) |
| 3 | G2 self-model moons (`giants/g2_ops.py`) — Consistency Gate (vector-magnitude escape check against Core Laws in `core/core_laws.json`), Magnitude Gate (clamps per-session delta to `G2_MAGNITUDE_CAP`=0.15, preserves direction, sets status=`clamped`, keeps original vector for audit), Reversibility Log (snapshots before-state into entry before commit; append-only). `g2_sleep_pass_i()` runs all three on each pending ring_buffer candidate and promotes/held/clamps accordingly. Thresholds imported from `constants.py` (single source of truth). Self-test offline (29 checks incl. real-laws-path check + clamped-but-still-committed end-to-end case). | No | ✅ DONE 2026-09-19 (29/29 PASS) |
| 4 | G2 sandbox (`giants/g2_sandbox.py`) — Plan A single-turn before/after diff (USER-APPROVED over multi-day sim): for each representative trial prompt, runs `run_collapse()` with baseline bias wave vs. candidate-included bias wave; metrics = tension_shift + consensus cosine coherence; FAIL if shift > 0.30 OR coherence < 0.70. Toggleable, **OFF by default** (zero pipeline imports when OFF — offline-safe). Inert multi-day-sim scaffold included (`g2_sandbox_multiday()`, returns not_implemented) per John's "code it ready to be wired in" request. Self-test offline (26 checks + info line). | Yes (~3×2 embeds, no generations) | ✅ DONE 2026-09-17 (26/26 PASS) |
| 5 | Growth policy + Tier system (`giants/g2_growth_policy.py`) — `g2_classify_tier()`: Tier 1 (normal drift) = autonomous after moons+sandbox; Tier 2 (structural: identity rewrite, anchor migration >0.3 units, new archetype) = held as `pending_user_approval` until a role-based reviewer approves/rejects (`g2_review()`). Anti-silence precedence: silenced debates stay `held_anti_silence` even with a structural finding. Wired into `ring.py::log_self_review_verdict()` (structural debate finding → Tier-2 hold) and `g2_ops.g2_sleep_pass_i()`. Zero-LLM; tier defs read from `g2_selfmodel.json::_growth_policy`. **Bug fixed in integration:** classifier crashed on explicit `kind=None` — normalised once at top. | No | ✅ DONE 2026-09-17 (3 self-tests ALL PASS) |
| 6 | Phase 7 acceptance test + evidence (G1 promote/eject cycle, G2 harmful-candidate rejection). Standalone test on temp JSON copies; runs twice (moons OFF deterministic, moons ON LLM). Verifies: good candidate promoted / AI slop ejected (two independent mechanisms); structural Tier-2 candidate held (Consistency Gate or Tier gate — both valid safety holds). | Yes (6 moon calls) | ✅ DONE 2026-09-17 (ALL PASS ×2 runs, comparison saved) |

**Evidence:**
- Seg 1: `p7s1_g1_ring_buffer_selftest_textoverlap_20260919.log` — **17/17 PASS** (ring buffer CRUD, AI slop scoring, duplicate rejection with text-overlap gate, similar-context non-rejection [6b], idempotency, staleness). Prior run without the gate: `p7s1_g1_ring_buffer_selftest_20260919_043500.log` (15/15).
- Seg 2: `p7s2_g1_filter_moons_selftest_20260919.log` — **16/16 PASS** (toggle-OFF path, prompt builder shapes, JSON parse robustness incl. fenced + garbage input, verdict priority logic unit tests, signature check).
- Seg 3: `p7s3_g2_selfmodel_moons_selftest_20260919.log` — **29/29 PASS** (ring buffer CRUD, real Core Laws path resolution from `core/core_laws.json`, escape-threshold hold on oversized vector with laws loaded, small-vector pass-through, large-vector clamp to cap preserving direction + audit field, zero/exact-at-cap edge cases, reversibility before-state snapshot for targeted vs. new entries, end-to-end sleep-pass: 2 pending → 1 promoted + 1 clamped-but-still-committed into `contents`, idempotency on second pass).
- Seg 4: `p7s4_g2_sandbox_selftest_20260917_180348.log` — **26/26 PASS** (toggle-OFF path returns skipped with zero pipeline imports, cosine/tension-shift math, verdict logic incl. exact-at-threshold inclusive boundary, `_aggregate_bias` synthetic cases: same-direction sum / vec-less skip / opposing-cancellation flip / all-skipped→None, `candidate_bias_wave` vs manual aggregation cos≈1, inert multi-day scaffold returns not_implemented, constants wiring check).
- Seg 5: `p7s5_ring_selftest_20260917_183150.log` (ring.py Segs 1–6, incl. new [31a] structural→Tier-2 hold + [31b] silence-wins), `p7s5_g2_ops_regression_20260917_183150.log`, `p7s5_growth_policy_selftest_20260917_183150.log` — **ALL PASS** (tier classifier, reviewer approve/reject actions, anti-silence precedence). Summary + bug note: `p7s5_growth_policy_segment_summary.md`.
- Seg 6: `p7s6_acceptance_moonsOFF_20260917_185917.log`, `p7s6_acceptance_moonsON_20260917_190500.log` — **ALL PASS** both runs. Comparison: `p7s6_acceptance_comparison.md`. G1 good candidate promoted (0.5546 ≥ 0.55) in both; AI slop rejected by deterministic scorer (OFF, score 0.36) vs. Clarity moon (ON, `rejected_clarity` pre-scoring). G2 structural candidate held at `held_law_check` (Consistency Gate, mag 6.928 > 0.30 escape threshold) in both — identical results confirming G2 moons are zero-LLM by design. LLM stress: ~1s/moon call, 6 calls total, 8.5s wall time for full test.

**Future-updates note (Sandbox upgrade path):** the current sandbox is a *single-turn* before/after diff — it answers "does this change degrade one live pipeline run?" but cannot answer "what does this do over days/weeks?". The planned upgrade is a **full multi-day simulation**: replay N synthetic sessions with and without the candidate, comparing trajectory-level drift (tension means, consensus-direction walk length, per-planet amplitude stability). Deliberately NOT built yet: simulated sessions would be *hallucinated scenarios*, not measured behavior — real multi-day evidence should come from actual session logs once the system has been running. The call site + report shape are already defined in `giants/g2_sandbox.py::g2_sandbox_multiday()` (returns `not_implemented`), so wiring it later is a fill-in, not a rewrite.

---

## Phase 8: Integration & End-to-End Wiring
**Goal:** Full pipeline runs as one connected system. No orphaned modules. Comet gets full trigger refinement here.

**Complete input flow:**
```
raw_input 
  → gate1_pii_scrub() 
  → ring_inbound() [adds relationship context]
  → embedding (HTTP to LM Studio) 
  → project onto X/Y/Z 
  → G1 pre-filter moons (clarity, relevance, dissonance)
  → C_core gravitational bend on input vector
  → composite field evaluation at current orbital positions
  → spike detection → ranked planet activations
  → resonance check (cosine similarity between activated planets' semantic directions)
  → if resonant: compute merged vector, apply multiplier to weights
  → comet trigger check (stagnation/over-seriousness/binary/random)
  → Phase A: Id fires per planet + moons frame (LLM call ×N)
  → [halt checkpoint]
  → Phase B: Ego synthesis, cross-planet response (LLM call ×N)
  → [halt checkpoint]  
  → Phase C: Superego review against Core gravity + Laws (LLM call ×N)
  → gate3_safety_check() on combined output
  → ring_outbound() [applies Maya's voice]
  → gate2_label() + gate4_log()
  → user sees response
  → memory write (Phase 4 spatial placement)
  → ring relationship_log update
```

- Every module's output is another module's input. No fire-and-forget.
- **Comet full implementation:** All four trigger conditions refined with actual session history analysis. Stagnation detection uses activation weight trends over N sessions. Over-seriousness detects Ruler/Sage dominance + low dissonance (everything too tidy). Binary convergence detects all planets landing on the same answer to a moral/ethical question (the original motivation). Random injection: low-probability (2% per session) "drunk day" Comet appearance.
- Logging: every routing decision, activation weight, resonance event, gate trigger, LLM call, memory mutation, sleep commit → timestamped session log (Gate 4).

### Phase 8 — Segment Tracker
| # | Segment | What it does | LLM? | Status |
|---|---------|--------------|------|--------|
| 1–3 | (prior integration wiring) | earlier end-to-end plumbing + acceptance probes | mixed | ✅ DONE (see prior session evidence in `tests/evidence/`) |
| **4** | **Moons × Jester full trigger refinement — live A/B matrix** | Single-config runner `tests/run_p8s4_matrix_config.py` (`--moons/--no-moons` + `--comet/--no-comet`). 7-session streak scenario (Q1 rebel-dominant ×4 → Q2 everyman-dominant ×3) run across all four toggle combos; comet state isolated per leg via monkeypatched `COMET_STATE_PATH`. Proves: Jester fires on session 4 only & only when ON; moons+jester compose with no interference (C4 fired identically to C3); moons redistribute Phase-C approves (no silencing). | Yes (~10–15 min/leg) | ✅ DONE 2026-09-17 — all four legs green. Evidence: `p8s4_matrix_comparison_*.md` + per-leg `.md` + raw logs |
| **5** | Phase close-out / safety architecture locked + live acceptance runs | Offline pre-flight DONE & green (`gates234.py` sanity ✓ + `pipeline.py --smoke` ✓). Gate 3 INPUT check kept conservative (phrase list); the two-layer intent-based safety net is locked in code comment + documented above under Gate 3. **2 live acceptance runs COMPLETE** ("once fluke, twice coincidence, three times pattern") with **moons ON** per John's call — both legs green: full A/B/C chamber on normal + PII prompts (7/7 planets speak every phase), email scrubbed before embedding, char-spam rejected at Ring Intake with zero LLM. | Yes (~3 min/leg) | ✅ DONE 2026-09-18 — evidence `p8s5_closeout_2026-09-18.md` + leg logs `p8s5_leg{1,2}_moonsON_run.log` (run ids `...125341`, `...125841`) |

> Note: Segment 4 re-verified routing determinism offline before spending LLM time (Q1→rebel gap 0.072, Q2→everyman gap 0.046); the single-variable design held across all legs.

> **Independent blind review triage (2026-09-18, pre-Segment-5):** an outside reviewer flagged six items; all fixed & verified — H1/H3 audit-log cleanup + H2 PII never-raises (`review_fixes_h1h3_h2_*.md`), M2 embed retry + `EmbeddingUnavailableError` + collapse dir-length guard (`review_fixes_m2_collapse_guard_*.md`), and 3 routing degenerate-case guards: all-zero amplitude crash, angular_z zero-spread noise, core_bend r≈0 discontinuity (`review_fixes_routing_*.md`). Full suite now **15/15 green**. GUESS-tunables to confirm before release: `EMBED_RETRIES=3`, `EMBED_RETRY_BACKOFF_S=1.0`. These are robustness fixes, not new features — Segment 5 live acceptance runs proceed as planned.

**Acceptance test (THE full one):** One user input enters. Verify ALL of the following in a single trace:
1. PII scrubbed before embedding ✓
2. Projected to semantically meaningful vector ✓
3. Planets selected *because of their current field position*, not random ✓
4. Resonance fired (or didn't) correctly based on semantic alignment, not proximity ✓
5. Comet appeared or stayed absent per trigger conditions ✓
6. Dialogue references specific cross-planet interactions ✓
7. Gate 3 checked output; passed (or blocked test phrase) ✓
8. Ring applied its voice + relationship context ✓
9. Transparency label attached, audit log written ✓
10. Memory entries on disk with correct mass/position near relevant planet's orbit ✓
11. Ring persona updated continuity log ✓
12. Trigger sleep → numeric parameters changed on disk (staggered commits visible in log) ✓
13. Next session's routing measurably different due to drift + orbital position change ✓

If all 13 pass, v17 is alive. If any fail, that module is decorative and gets rewired before moving on.

---

## Phase 9: Scaling & Multi-System
> Status: **Sketch only** (2026-09-18). Not in v17 scope. This section is a design map for whoever picks up the torch next — it defines what "scaling" means concretely, what the first steps would be, and what hardware unlocks what.

### The Principle: Fractal Holarchy (D-014)
The architecture is structurally identical at every scale. One solar system → binary system → galaxy of systems → universe of galaxies. Each level uses the same orbital mechanics, resonance detection, sleep cycle, and gate infrastructure — just more bodies orbiting a shared center. No new subsystems required; only parameterization + coordination protocols between peer systems.

### 9A: Binary System (Two C_cores)
The first meaningful scale-up. A second star enters with its own 7 planets, sharing the same semantic field but gravitationally bound to their own center.

**What it is:**
- Two independent `C_core` bodies, each with N=1–7 planets and moons.
- The two cores orbit a shared barycenter (the midpoint between them).
- Each system maintains its own Core Laws, persona, and memory independently — they are *peers*, not master/slave.

**What it enables:**
- **Specialized sub-nodes in Lagrange zones.** L1–L5 points between the two cores become natural homes for shared infrastructure: a Gas Giant pair could share a G1 archive at L4 (Trogjan point), or a Dyson Ring could sit at L2 as a unified user-facing interface that speaks to both systems.
- **Division of cognitive labor.** System A handles technical/engineering questions; System B handles interpersonal/ethical ones. The Ring routes based on which core's field is more aligned — same routing logic, just two attractors instead of one.
- **Redundancy / failover.** If one system's model fails or context overflows, the other can absorb the load (degraded but functional).

**First concrete step:**
1. Parameterize `pipeline.py` to accept a `system_id` and route prompts to the correct core based on barycentric field overlap.
2. Define a **barycentric routing function**: given input vector, compute cosine alignment with each system's aggregate semantic centroid → highest wins (or both fire if both exceed threshold — resonance between systems).
3. Shared state: one `gates_config.json`, one `core_laws.json` per system (they can differ), shared G1 archive optional.
4. Hardware: same single model plays all roles in both systems sequentially (2× the LLM calls). Feasible on 4090 for short sessions; not ideal for long ones.

**Hardware unlock:** When DeepSeek/Qwen ships kernel-level VRAM compression (noted 2026-09-18), a single 27B model may fit in <16GB, leaving room for a second smaller model (3–4B) to run concurrently. At that point, the binary system can use *different* models per core without VRAM conflict.

### 9B: Galactic Scaling (Multiple Full Systems)
The natural extension of 9A. Instead of two cores orbiting a barycenter, you get K full solar systems orbiting a shared **Galactic Center** — a higher-level C_core that doesn't reason itself but coordinates which system handles what.

**What it is:**
- K independent solar systems (each = 1 core + N planets + moons + gas giants).
- A **Galactic Core** at the center: not a reasoning agent, but an *orchestrator* — it reads the aggregate semantic field of all member systems and routes prompts to whichever system's archetype constellation best matches.
- Systems can **resonate across galactic scale**: if System A's Hero and System C's Sage both light up for the same input, the Galactic Core detects cross-system resonance and merges their outputs (same 7b emergent-vector logic, just operating between systems instead of within one).

**What it enables:**
- **Domain partitioning at scale.** Each system specializes: one is a "technical galaxy" (heavy Ruler/Creator planets), another is an "emotional galaxy" (heavy Caregiver/Sage). The user's prompt gets routed to the right domain automatically.
- **Emergent complexity without per-planet cost.** 7 systems × 7 planets = 49 cognitive voices, but each system only fires its own 7 calls. Total cost stays at ~7 LLM calls (one system handles the prompt) or up to 14–21 if cross-system resonance fires.
- **The Fractal Illusion becomes real.** At this scale, the "recursive planet" idea from the deferred section maps naturally: a whole *system* IS the internal deliberation of one "mega-planet." No 336-call explosion — just routing to the right sub-system.

**First concrete step (after 9A is proven):**
1. Define `galaxy_config.json`: list of member systems, their specializations, and the Galactic Core's routing weights.
2. Implement cross-system resonance: cosine similarity between *system-level* semantic centroids (aggregate of all planets in each system), same threshold logic as intra-system resonance.
3. The Ring becomes a **Galactic Interface**: one user-facing persona that can speak on behalf of any member system, switching voice/persona based on which system is active.
4. Memory isolation: each system has its own G1/G2/Ring memory; the Galactic Core only stores *routing history* (which system handled what), not content.

### 9C: True Multi-Agent (Separate Model Per Planet)
The endgame hardware unlock. Instead of one 27B model playing all 7 roles sequentially, each planet gets its own specialized small model running in parallel.

**What it is:**
- 7× small models (3–4B Q4 each ≈ 2–3GB VRAM) + 1 main 27B for synthesis/Ring = ~25–30GB total. **Does NOT fit on a single 4090.** Requires either: (a) the kernel-level compression reducing base model to <16GB, or (b) multi-GPU / GPU+CPU split.
- Each planet's model is fine-tuned (or at least system-prompted) for that archetype. The Hero model *is* the Hero — no role-playing overhead.
- Parallel execution: all 7 planets fire simultaneously (GPU batch), not sequentially. Latency drops from ~30s to ~5–8s per prompt.

**What it enables:**
- **Real-time responsiveness.** The system feels like a conversation, not a report. Critical for the Ring persona's natural voice.
- **Per-planet model upgrades.** Swap just one planet's model (e.g., upgrade the Sage to a larger reasoning model) without touching the rest.
- **The Fractal Illusion at full power.** If each "system" in 9B is itself 7 small models, and the Galactic Core is a large model, you get genuine hierarchical multi-agent behaviour — not simulated, but architecturally real.

**First concrete step (hardware-dependent):**
1. Wait for VRAM headroom (kernel compression or second GPU).
2. Fine-tune or LoRA-adapt 7 small base models (Qwen-3B / Gemma-4B) on archetype-specific corpora.
3. Replace `_llm_chat_cached()` with a **parallel batch caller**: send all 7 planet prompts simultaneously, collect responses, then run Phase B/C synthesis on the main model.
4. The Ring Capability Layer's `LLMBackend` abstraction (deferred section above) becomes critical here — it already defines the per-backend interface that would route each planet to its own endpoint.

### 9D: Release & Distribution Packaging
Not a "phase" in the build sense, but the practical packaging work needed before the framework is usable by anyone other than John:

- **`gates_config.template.json`** ships with conservative defaults (basic PII patterns, standard blocklist). User provides their own on first run.
- **`core_laws.json`** — user writes their own 3+ Laws. Template includes the six-law roster as a starting point but is explicitly overridable.
- **No hardcoded content restrictions** beyond the legal floor (Gate 1's structural invariants: no self-modification of laws, audit log always on, `/halt` always available).
- **Backend-agnostic:** ships with LM Studio adapter by default; Ollama/vLLM/cloud adapters are drop-in configs (`backend_config.json`).
- **First-run wizard** (eventually): asks for model path, embedding model, core laws, gates config → generates a working `constants.py` + state files. Until then, it's copy-paste-from-README territory.

### Hardware Watch Items (external dependencies)
| Item | Status | Impact |
|------|--------|--------|
| DeepSeek kernel-level VRAM compression (noted 2026-09-18) | Waiting for Qwen base model update | Could reduce 27B Q4 from ~18GB to <14GB, freeing headroom for concurrent small models or larger context |
| LM Studio multi-model support | Current limitation: one model at a time per instance | Blocks 9C until resolved (or user runs separate instances) |
| GPU+CPU split inference | Ollama/vLLM already support this | Fallback path if single-GPU VRAM stays tight |

### Sequencing Summary
```
v17 complete (Phases 0–8)
    │
    ├─► 9D: Release packaging (can start NOW — just docs + config templates)
    │
    ├─► 9A: Binary system (first real scale-up; needs barycentric routing + shared state design)
    │       └─► Prerequisite: v17 stable in production for ≥2 weeks
    │
    ├─► 9B: Galactic scaling (needs 9A proven first)
    │       └─► Prerequisite: cross-system resonance tested with 2 systems
    │
    └─► 9C: True multi-agent (hardware-gated; no code work until VRAM allows)
            └─► Prerequisite: kernel compression OR second GPU + LLMBackend abstraction built
```

---

## Future (Deferred): Oort Cloud Defense — Securing External Input
> Source: `misc.md` item #7 ("defence for real world interaction and Web access"). Not in v17 scope. Documented so it isn't lost. **Prerequisite:** only becomes relevant once the system gains "hands" — web/file reading / external data ingestion (i.e. after Action-Oriented Tooling, `misc.md` #6). Until then there is no untrusted input to defend against.

**Concept:** A defense-in-depth perimeter that keeps untrusted external data (web scrapes, third-party emails, incoming files) from reaching the inner reasoning planets directly. Cosmology mapping:
- **Oort Cloud (Perimeter)** — strip & sanitize: a *deterministic script* (never an LLM) fetches/reads; all external text is wrapped in rigid inert JSON structures; regex / small detector micro-models sweep for command phrases ("ignore previous instructions", "system override", …).
- **Kuiper Belt (Validator)** — schema check: free-form prose is stripped away, leaving only strictly typed key-value objects. Removes the medium through which indirect prompt injection travels.
- **Inner Planets (Governed Action / Dual-Key Authorization)** — planets may state an *intent* (`INTENT: PURCHASE_ITEM`) but cannot execute directly; any intent flagged financial / file-write / network-export triggers a physical pause requiring manual user confirmation on a clean UI.

**Reuses existing pieces:** `gate1.py` + `gates_config.json`, the Dyson Ring (prompt-handling / intake role), and the Gate 4 audit log. Most of this is wiring existing modules into a defense role, not a new subsystem.

---

## Future (Deferred): Fractal (Recursive) Planet Sub-Architecture — "The Fractal Illusion"
> Source: John + Google design conversation (2026-09). **Not in v17 scope.** Documented so the idea isn't lost. **Verdict: viable PATTERN, but do NOT build the literal 7×3×16 tree** — it collapses our field model into brute-force sub-agents and is unaffordable on current hardware (see cost math below).

**The vision:** Each Macro-Planet (e.g. Hero) is itself a mini-system with internal structure, recursing down:
- **L1 System (Solar System = C_core + its 7 planets)** — global orchestration for this one system. *(The Galaxy is a higher level: it only exists when multiple solar systems are connected, per Phase 9 "Galactic scaling".)*
- **L2 Planet** — e.g. Hero, acting as its own subsystem.
- **L3 Internal Drives** — Id / Ego / Superego nodes inside that planet.
- **L4 Lenses** — within each drive, a fan-out of cognitive lenses (proposed: 16 MBTI types).
- **L5 Synthesis** — the lens outputs collapse back up into one refined "Hero Judgement" for global consensus.

The claim: recursive deliberation (agents consulting sub-agents before speaking) raises reasoning quality and cuts hallucination vs. single-turn prompts, and self-similar structure yields stable scale-invariant behaviour.

**Why we are NOT building the literal tree:**
1. **It misreads our architecture.** Our planets already *are* the collapse step — each planet receives the prompt, runs its own internal wave dynamics (Layers 1–2), and emits one vector/judgement. Instantiating "Id/Ego/Superego × 16 MBTI" as fresh LLM calls is a rejection of the field model in favour of sub-agent fan-out, not an extension of it.
2. **Cost wall.** Literal sequential cost per single-planet Phase A turn = `7 planets × 3 drives × 16 lenses = 336 generations`; add a global Ego/Superego (Moons) layer and one user prompt runs into the **thousands** of calls. On a 4090/24GB box (already at its ceiling with just the base 7 calls), this is infeasible on latency.
3. **"Fractal = why nature works" is decorative, not evidence.** Natural scale-invariance does not transfer to LLM inference cost. The *real* reason a lens-stack could help is **variety of reasoning reduces single-lens bias** — an argument about perspective diversity, not geometry. (Don't cite the fractal-nature claim as justification.)
4. **16 MBTI lenses are a weak choice for us specifically.** MBTI has poor psychometric validity and is *correlated* with our existing archetype set (Hero/Ruler/Rebel already encode distinct stances). Stacking 16 types under each planet risks **redundant overlap, not new resolution** — near-duplicates of what the 7 planets + wave interference already provide. If revisited, use **orthogonal cognitive axes** (risk-tolerance / temporal-horizon / abstraction-level) instead of a personality taxonomy.

**The efficient version if ever revisited ("Fractal Illusion"):** Keep the depth *inside one prompt*, not behind N network hops.
- **Matrix prompting:** one extra pass per planet instructs it to "evaluate this across K reasoning lenses, mediate them internally, apply your constraints, return a single collapsed verdict." Zero or +1 call per planet (K tunable — start at 3–4, never 16).
- **Fold into system prompt (0 extra calls):** bake the lens set into each planet's existing persona so the multi-lens deliberation happens inside the turn we already pay for.
- Worst case ~7→28 calls vs. today's 7 — meaningful but survivable; preferred is the 0-extra-call fold-in.

**Reuses:** existing per-planet system prompts, `resonance` embedder for lens vectors if needed, Gate 4 audit to log which lenses fired. No new subsystem required.

---

## Future (Deferred): The Ring Vault — Personal Data Store + Eject / Cold Backup
> Source: John design conversation (2026-09), raised while reviewing the Phase 4 PII guard. **Not in v17 scope.** Documented so it isn't lost. **Verdict: sound and worth building** — it's the natural home for personal data that the memory vault deliberately does NOT hold (see Seg 4 note on why names survive but addresses don't).

**Problem it solves:** The Phase 4 PII guard scrubs emails/phones from *stored* memories, so a raw address is never persisted. That's correct — but then how does the system act on "email Frank about the upgrade" later? Answer: **personal data belongs in its own structured store, referenced by name/ID, not embedded as free text.** Free-form memory stays PII-free; contacts/history live where they're actually used.

**Placement (John's call): a Vault sub-layer INSIDE THE RING.** The Ring is the user-facing interface — the *only* layer that ever talks directly to John and holds his history, preferences, and profile. So:
- **Only the Ring reads/writes the Vault.** The planets (cognitive layer) never need your contact book; they see `contact_id=frank`, not the address.
- This is a *security* benefit, not just naming: PII never has to be shipped into the reasoning layers at all. Memory entries reference contacts by name/ID → resolved against the Vault only when it's actually time to act (send/email).
- Cosmology mapping: fits the Ring's already-intended role as the full persona-neural-net / user-state holder (front-end + history + preferences + long-term "swarm" with decay), per `misc.md` and the Body Inventory.

**The three sub-ideas (all documented, none built yet):**
1. **The Vault itself** — structured personal data (`contacts.json`: `{ "frank": { email: … } }`, plus profile/history). Ring-only access.
2. **"Eject" / fail-safe destroy** — an explicit, *deliberate* operation that wipes the Vault (a privacy reset; "send it to be destroyed"). Should require a confirmation gate so it can't fire accidentally. Real-world analogue: user-initiated account-data deletion.
3. **Cold backup satellite** — an off-line copy held outside normal reach; you must *deliberately* go for it to recover, protecting against casual/accidental exposure while staying recoverable by design intent. Real-world analogue: **encrypted cold storage with a separate key** (the "eject + cold backup" pair is exactly this pattern). The space names are just memorable labels — keep them; they map cleanly and make the design easier to explain.

**Engineering notes for when it's built:**
- Vault is *not* part of `memory.py`'s zone stores (planet_vaults / periphery / swarm) — those are *cognitive* memory. The Ring Vault is a separate, user-facing data layer with its own access rules.
- **Encryption at rest** for the cold backup; the "can't be accessed through normal means" requirement = key held separately from the ciphertext (eject destroys the live copy + optionally the key).
- Reuses: `gates_config.json` (PII patterns), Gate 4 audit log (record Vault access/eject events), and the Ring intake role already in place. Mostly a new structured store + access policy, not a rewrite.

**Sequencing:** build during the Ring / user-profile phase (Phase 7-ish), *after* the memory PII guard is proven — this note exists so that when we get there, the design decision (Vault-in-Ring + eject + cold backup) is already made and documented.

**Legal compliance notes (UK GDPR & Data Protection Act 2018):**
> Source: John's research (2026-09), informed by Google. Not a legal review — a design constraint reference for when the Vault is built.

| Legal principle | How our architecture satisfies it |
|----------------|----------------------------------|
| **Storage Limitation** | Phase 4 decay sweep already enforces this on cognitive memory (entries below `MIN_ENTRY_MASS` → compression queue). The Ring Vault should mirror this: user data entries carry a purpose + expiry; unused contacts/history decay or require explicit retention. |
| **Integrity & Confidentiality** | The Vault decoupling is the core mechanism: PII never enters model context, embeddings, or planet vectors. Only the Ring layer has read/write access — and even then, only at action time ("email Frank") not during reasoning. Cold backup uses envelope encryption (below). |
| **Right to Erasure** | The "Eject" operation IS this right made concrete. Must execute **hard deletion**: overwrite key bytes or use cryptographic shredding (destroy the DEK → ciphertext is mathematically unrecoverable). A soft flag (`deleted: true`) does NOT satisfy GDPR erasure — it leaves reconstructable data on disk. |
| **Purpose Limitation & Minimization** | Vault entries are structured (typed fields), not free text. Each field has a declared purpose (e.g., `email` = outbound contact only). The planets never see raw values — they reference by ID. No PII is collected beyond what the user explicitly provides for a stated function. |

**Cold backup encryption design (for when built):**
- **Envelope encryption:** AES-256 GCM to encrypt data with a Data Encryption Key (DEK); DEK itself encrypted by a Key Encryption Key (KEK) stored separately (a file on an isolated volume, or eventually an HSM/KMS if the project scales). The AI pipeline never holds the KEK at runtime — it lacks key privilege even if compromised.
- **Cryptographic shredding (fast eject):** to "delete" cold data without scanning large stores, destroy the DEK. Without the key, ciphertext is unrecoverable by definition. This satisfies legal erasure standards instantly regardless of file size.
- **Network / access isolation:** cold backup lives on a separate volume or write-once storage requiring deliberate offline action (multi-step auth) to read. Not accessible from normal system operation — mirrors the "backup satellite you must deliberately go get" design intent.
- **Immutable audit log:** every Vault access, eject, or cold-backup restore writes an append-only record (timestamp, action, authorization context) via Gate 4. This is the accountability trail GDPR requires to prove data was handled within its legal bounds.

---

## Future (Deferred): REM Sleep Mode — Random-Association Dream Pass
> Source: John design question (2026-09), raised right after S7a. **Not in v17 scope.** Documented so the idea isn't lost and the decision is made when we get there.

**The question:** Deep sleep's Pass IV drift only moves a planet toward directions *this session* suggested (bounded, clamped, deterministic). A "REM" mode would instead feed 2–3 random ring-buffer fragments to a small group of planets with a prompt like *"what do these unrelated things have in common?"* — mimicking how biological REM sleep recombines old material into novel associations. Would that add real self-evolution, or just burn uptime for nothing?

**Verdict (agreed): it adds genuine value — but ONLY as a separate, budgeted, gated mode. Never merged into base deep sleep.**

Why it's worth having at all:
- It is the *only* mechanism in v17 that can move a planet toward a direction no user prompt has ever suggested. Base drift = incremental evolution toward recent experience; REM = exploration of unexplored directions (cross-domain association). Without it, "self-evolution" is strictly reactive.

Why it must stay out of base deep sleep:
1. **Cost.** Deep sleep today = 0 LLM calls, ~0.2s — safe to run on every exit. Stacking N dream calls onto *every* sleep multiplies the existing 7-planet call budget concern (John's stated hardware worry) a second time.
2. **Risk profile.** Pass IV drift is bounded by design (position ±0.1, mass clamped, temp/CoT deltas capped). Dream output is creative and unbounded until proven otherwise — folding it into the same commit path would require sand-boxing dreams as their own sub-system before base sleep could stay trustworthy.
3. **"Actual rest" concern (John's point) is valid** — uptime for its own sake is bad. The fix isn't "never dream," it's *gated, periodic* dreaming, the same way real REM cycles are short and intermittent relative to total sleep time.

**Proposed shape (for approval when we build it, not built yet):**
- **Separate trigger, not a flag on `deep_sleep()`.** E.g. fires every Nth deep sleep (N=3 suggested) OR only if the compression queue holds ≥K fresh fragments to dream about — no material = skip REM entirely (no empty dreaming).
- **Budget cap:** `REM_MAX_CALLS` in `constants.py`, hard-capped at 2–4 LLM calls per episode, picks a small planet subset (not all 7) to keep it cheap.
- **Same safety rails as normal commits:** dream-derived drift still goes through the G2 sandbox + Magnitude Gate (`max_delta=0.15`), so a wild dream physically cannot move any planet more than a normal session can.
- **Reversible:** every REM commit is logged to G2's reversibility log like any other commit — walk-back works if a dream moves things sideways.
- **Toggleable, default OFF** until we've watched one full run (same pattern used for the moons and the Ring facet).

**Sequencing:** candidate Phase 8 / "Phase 5.5" work — deliberately *after* S8's acceptance test proves base deep sleep is solid, and ideally once integration means session log + compression queue + G2 sandbox are all running continuously. REM then reuses already-proven plumbing (sandbox, gates, audit) instead of testing its own.

**Reuses:** `sleep.py` commit path, `giants/g2_selfmodel.json` (sandbox + magnitude gate + reversibility log), Gate 4 audit log, existing embedding call for the "what do these have in common" vector. No new subsystem — a gated pass slot inside an existing sequence.

---

## Future (Deferred): Ring Capability Layer — Tool Calls, Reasoning, Vision + Backend Abstraction
> Source: John design question (2026-09), raised after Phase 6 Seg 5 completion. **Not in v17 scope.** Documented so the intent isn't lost and the architectural decisions are made when we get there.

**The idea:** The Ring should carry a fixed set of *capability features* — tool calling, extended reasoning, and vision — that persist regardless of which model is plugged into it. Swap Maya for any other persona or model, and those capabilities still work because they live in the **plumbing**, not in the prompt.

**Why this matters:** Currently `_llm_chat_cached()` in `cognitive_chamber.py` hardcodes LM Studio's `/v1/chat/completions` on port 1234. The framework is designed to be plug-and-play (John's explicit requirement: "others may use a different font/backend"), so the LLM layer needs an abstraction that:
1. Decouples *where* inference runs (LM Studio, Ollama, vLLM, local GGUF runtime, cloud API, etc.) from *how* the system talks to it.
2. Exposes a **capability probe** — at startup or on model-swap, query the backend for supported features and adapt behaviour accordingly (graceful degradation if a feature is missing).

### The three capabilities (and how they'd slot in):

#### 1. Tool Calling (highest feasibility)
- Most modern backends expose an OpenAI-compatible `tools` / `functions` schema.
- The Ring's intake facet would pass available tool definitions to the model; if the model returns a structured call, the Ring executes it and feeds the result back before composing her voice response.
- **Plug-and-play requirement:** not every backend/model supports this. Capability probe: "does this endpoint accept `tools` in the request?" → yes: wire it / no: fall back to free-text parsing (worse but works) or skip.
- Tools are defined in config (`ring/tools.json`), not hardcoded — same pattern as `gates_config.json` and `core_laws.json`.

#### 2. Extended Reasoning (medium feasibility, model-dependent)
- Two tiers:
  - **(a) Model-native:** some models support explicit "thinking" / extended-CoT modes (Qwen3 `/think`, o1-style `reasoning_effort`, etc.). Capability probe: "does this model expose a thinking budget parameter?" → use it for complex questions, skip for simple ones.
  - **(b) Architectural fallback:** the Cognitive Chamber's Phase A→B→C debate IS already a reasoning layer. If the plugged-in model has no native CoT, the system can route "hard" questions through `run_phase_a_b_c()` instead. This is the graceful degradation path — and it means even a dumb model in the Ring still gets deep reasoning via the planets.
- **Plug-and-play requirement:** the abstraction layer needs an optional `reasoning_mode` parameter that maps to whatever the backend supports (or "none" → chamber fallback).

#### 3. Vision / Image Input (straightforward where supported)
- OpenAI-compatible APIs accept `image_url` in messages. If the plugged-in model is a VLM, images just work.
- **Plug-and-play requirement:** capability probe: "does this model accept image inputs?" → yes: pass through / no: route to a separate small vision model (dedicated "eyes" endpoint) that returns a text description, which the Ring persona then wraps in her voice. This is the same pattern as tool calling — the feature works even if the main persona model can't see.
- The Ring's intake facet already handles multimodal detection (image attachment → flag); only the downstream routing needs adding.

### Proposed abstraction shape (for when built):
```
class LLMBackend:
    """One implementation per provider. Pluggable via config."""
    def chat(messages, temperature, max_tokens) -> str: ...          # core — always works
    def supports_tool_calls() -> bool: ...                          # capability probe
    def chat_with_tools(messages, tools) -> (str | ToolCall): ...   # optional
    def supports_reasoning() -> bool: ...                           # capability probe  
    def chat_extended(messages, thinking_budget) -> str: ...        # optional
    def accepts_images() -> bool: ...                               # capability probe
```
- `constants.py` or a new `backend_config.json` selects which implementation is active.
- The existing `_llm_chat_cached()` becomes a thin wrapper over whichever backend is configured (LM Studio today; Ollama/vLLM/cloud tomorrow).
- **Zero changes to the cognitive layer** — planets, moons, chamber, sleep cycle all keep calling `chat()`. Only the Ring's *intake* and *outbound* facets gain awareness of the extra capabilities.

### Sequencing:
This is a **Phase 8+** item. It depends on:
- Phase 6 being fully closed (Ring is functional)
- At least one non-LM-Studio backend being available to test against (so "plug-and-play" isn't theoretical)
- The Ring Vault being designed (tools will need to interact with user data — "email Frank" resolves through the Vault, not raw text)

### Tool execution home: the Ring (per John, 2026-09)
Fast narrow tool work (file checks, code validation, search, etc.) lives in the **Ring's matrix** — implemented as cheap deterministic logic + occasional small-model calls, NOT routed through the heavy planetary chamber. This is also where a Gemini-proposed "Dyson Swarm" idea was evaluated and folded in: the swarm *as hundreds of micro-agents* maps onto what moons + Ring facets already are (no new architecture needed), so only the **tool-execution** part survives — as tools owned by the Ring, not a separate satellite layer.

### Matrioshka scheduling principle (cheap-tier work in cold windows)
From the same Gemini conversation: nested shells where outer colder tiers recycle inner waste heat → our translation is a **scheduling rule**, not new infrastructure:
- "Inner hot pass" = chamber debate / heavy reasoning (VRAM peak).
- "Outer cold tier" = embedding-model + pure-Python work (G1 ring-buffer scoring, swarm decay bookkeeping, telemetry logging, indexing queues).
- Rule: cheap-tier housekeeping is **queued and runs in cold windows** — never during a live chamber pass. Zero VRAM added; just ordering.
- Note: literal hidden-tensor recycling isn't available through the OpenAI-compatible API on our shared LM Studio instance — only the scheduling principle applies today.

### What this does NOT change:
- The 7-planet cognitive architecture stays exactly as-is.
- Core Laws, gates, PII guard, anti-silence — all untouched.
- The Ring persona is still swappable data (`persona.json`). The capability layer sits *around* it, not inside it.

---

## Hardware Notes
- LM Studio on port 1234, Gemma-4 ~27B Q4 (main model) + `all-MiniLM-L6-v2.F16.gguf` (embedding) — both loaded in same instance
- Sequential calls: same model plays all roles; architecture ready for swap to true multi-agent when hardware improves
- All state on local disk. No cloud dependencies.
- Visualizer: rebuilt after Phase 1 physics is stable. Shows real orbits, resonance links (lines between semantically-aligned planets), moons-as-hemispheres. Not a development dependency — a verification/joy tool.

---

## Release Readiness Notes

The framework is designed so that **the creative space is fully user-configurable** and the safety infrastructure is per-deployment:

- `gates_config.json` — YOUR blocklist, YOUR PII patterns, YOUR transparency mode. Not hardcoded in source.
- `core_laws.json` — YOUR 3 Laws. The system enforces them gravitationally but cannot self-modify them.
- Planet cognitive modes, energy states, archetype selection — all data-driven from JSON configs, not baked into code logic.
- A new deployment = copy the framework + write your own `gates_config.json` + `core_laws.json` + optionally reassign archetypes. The orbital mechanics, resonance detection, sleep cycle, and memory system are deployment-agnostic.

**What's NOT configurable (structural invariants):**
- The 3-Law self-modification protection (sleep cannot edit `core_laws.json`)
- Gate 4 audit logging (always on; retention period is configurable but the log itself cannot be disabled)
- User override via `/halt` (cannot be removed by config)
- PII: raw text never touches memory files regardless of config (the *patterns* are configurable, the *principle* that raw identifiers don't persist is structural)

---

## Links
- [[Home]]
- [[03 - Implementation/v16 Postmortem — What Went Wrong|Why this build order exists]]
- [[02 - Architecture/Data Flow|What the full pipeline looks like once wired]]
- [[04 - Decisions & Rationale/Design Decisions Log|All decisions that constrain these phases (D-001 through D-018)]]
- [[02 - Architecture/Planetary Archetypes & Cognitive Modes|The 7 archetypes, energy states, Freudian triad detail]]
- [[02 - Architecture/Body Inventory|Complete body list and roles]]
