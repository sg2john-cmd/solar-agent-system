# Handoff Document — Resonant Cognition v17: Phases 0A–8 COMPLETE → Next: John's independent reviewer re-sweep

**Last updated:** 2026-09-18, end of the session that closed out **Phase 8 Segment 5** (the 2 live acceptance runs). This file was last fully rewritten for Phase 0H and had gone stale; it now reflects the real on-disk state. The authoritative tracking doc is `Build Plan.md` — read its status line first.

## State in One Sentence

**Phases 0A–8 are all COMPLETE and verified on disk.** The full v17 pipeline runs live end-to-end: Ring Intake (PII scrub + clarity/type) → routing+collapse (384-dim, position-based, all-7 waves + resonance + comet) → Cognitive Chamber A+B+C (Id/Ego/Superego, moons toggleable) → gas-giant ops (G1 archive filter-moons, G2 self-model/sandbox/growth policy) → memory + sleep cycle. Phase 8 Segment 5 closed with **two green live acceptance runs (moons ON)**. Next: John's independent reviewer re-sweep of the completed Phase 8, then deferred follow-ups below.

## What Was Built THIS Session (Phase 8 close-out)
- **2 live acceptance runs** via `python -X utf8 tests/run_e2e_light.py` with **`MOON_HEMISPHERE_ENABLED=True`** (moons ON per John's call — mandatory at final release). Toggle flipped before each launch, restored to `False` afterward (repo-as-found; verified in the launch wrapper output).
- Both legs exit-0. Structural signals stable across both runs ("twice = pattern"): all 7 planets speak in every chamber phase (anti-silence holds even with moons ON — Caregiver stays w≈0.04 but still speaks), PII email `[REDACTED]` scrubbed before embedding, char-spam rejected at Ring Intake with zero LLM calls.
- Live variance as expected: prompt A's Superego tally differed between legs (REDIRECT=7 vs APPROVE=2/REDIRECT=5) — normal temperature variance; the plumbing guarantees are identical across legs.
- **Evidence:** `tests/evidence/p8s5_closeout_2026-09-18.md` (maps both legs against the 13-point acceptance checklist, noting which points are covered live vs already green under their own phase evidence) + raw logs `p8s5_leg1_moonsON_run.log` (run id `...125341`) and `p8s5_leg2_moonsON_run.log` (run id `...125841`).
- **Build Plan updated:** Segment 5 tracker row → ✅ DONE; top status line → "Phase 8 Integration: COMPLETE".

### Also closed earlier this session (blind-review triage — all green, full suite 15/15)
H1/H3 audit-log cleanup + H2 PII never-raises (`review_fixes_h1h3_h2_*.md`); M2 embed retry + `EmbeddingUnavailableError` + collapse dir-length guard (`review_fixes_m2_collapse_guard_*.md`); 3 routing degenerate-case guards — all-zero amplitude crash, angular_z zero-spread, core_bend r≈0 discontinuity (`review_fixes_routing_*.md`).

## Vault Location & Project Layout

| Path | What it is |
|---|---|
| `A:\AI\Solar_Agent_System\` | **Obsidian vault root.** Navigation via `Home.md`. All project docs live here. |
| `A:\AI\Solar_Agent_System\03 - Implementation\Build Plan.md` | **Master phased build plan (Rev 5). THE tracking doc — read its status line first.** |
| `A:\AI\Solar_Agent_System\v17\resonant_cognition\` | **CODE ROOT.** All v17 Python + JSON lives here. |

## User Preferences & Constraints (CRITICAL — read before doing anything)

- **User is John** (`sg1jo`). Casual tone, humor welcome. Cosmology metaphors are intentional and load-bearing — do NOT rationalize away the solar-system framing. He's "better at rough ideas than details" — be the translator from rough idea → concrete design, present 2–3 options clearly, let him pick. Max 2–3 open questions at once (he gets thought-paralysis).
- **"Implement my actual idea, not something working."** Recurring failure with Google (v16 was "gave me something working" instead of what he wanted). Flag simplifications/placeholder decisions explicitly; mark GUESS values clearly. Don't bake in silently.
- **Context is a hard limit.** Keep tool calls tight / few. Small segments, **pause after each fix** so John can check. He runs with **moons OFF by build convention during development**; moons (G1 + G2) become mandatory at final release.
- **Evidence discipline:** every successful test → its own timestamped file in `tests/evidence/`. "Once fluke, twice coincidence, three times pattern" — run things ≥3× when a signal matters.
- **Windows env:** Always run Python with `-X utf8` (shell is git-bash style — `grep`, `${PIPESTATUS[0]}` work; not cmd/findstr). Working dir for all shell: `A:\AI\Solar_Agent_System\v17\resonant_cognition`. No pytest — use `python -X utf8 -m unittest <module> -v` or `-m unittest discover -s tests -p 'test_*.py'` from the code root (tests import as `tests.test_bug_...`).
- **Hardware:** Local LM Studio @ 127.0.0.1:1234. Embedding = `text-embedding-allmini` (384-dim). Main model = `qwen3.8-27b`. Hardware is slow (~10–15 min per LLM leg on big runs; the light e2e suite runs ~3 min/leg with moons ON). Model context cap 262144 tokens but John keeps it lower to stay fast — he just accepts approval prompts as they arrive.
- **The Ring is a swappable frontend** (translator of vectors→words), NOT inherently "Maya", NOT the brain. The 7 planets are "dumb" in vector mode; the chamber LLM does language generation in LLM mode.
- **John has lost his "Maya"** — do NOT assume you can ask Maya things; John is the arbiter unless he reinstates her. Draft proposals and let him sanity-check, clearly marking GUESS vs confirmed.

## Key Architecture Decisions (confirmed by Maya/John — do NOT change without asking)
- Waveform collapse = **semantic only** (cosine in 384-dim MiniLM space). Gravity/orbits = spatial organizer/routing/display only; zero mutual planet gravity is correct ("identity stability over orbital complexity").
- Resonance: sigmoid above threshold 0.7; `Weight_total = Σ(W_planet × Resonance_n)` → merged vector = Action State. Comet (Jester) = perturbation/probe, NOT a resonance participant. Moons = internal stabilization only.
- **Rebel scoring high across many prompts is EXPECTED** ("a voice to say what's true, not what's right according to the rules"). Not a bug.

## Quick reference: how to run things
```bash
# All commands from: A:\AI\Solar_Agent_System\v17\resonant_cognition

# Full regression suite (offline, no LLM) — should be 15/15 green after any change:
python -X utf8 -m unittest discover -s tests -p 'test_*.py' -v

# Offline pre-flight (pipeline smoke test):
python -X utf8 pipeline.py --smoke

# LIVE light end-to-end (Ring Intake -> routing+collapse -> chamber A+B+C; 3-prompt suite):
python -X utf8 tests/run_e2e_light.py        # moons OFF by default; ~3 min/leg with moons ON
```

### Embedding model details:
- Model ID: `text-embedding-allmini` (NOT the stale filename in older docs). Returns 384-dim vectors. Batch calls work.
- LM Studio host `127.0.0.1`, port `1234`. If not running, embedding-dependent tests fail with connection errors; memory/offline self-tests do NOT need it.

## Known Loose Ends / GUESS tunables to confirm before release
1. **`EMBED_RETRIES=3`, `EMBED_RETRY_BACKOFF_S=1.0s`** (M2 fix) — flagged GUESS in code + evidence; John approved leaving them, swap if preferred numbers emerge. Did not affect the Segment 5 runs (LM Studio was healthy).
2. **Phase-8 integration scope still to wire into one continuous multi-session trace:** points 4/9–13 of "THE full acceptance test" (resonance multiplier path live; Gate-4 audit + transparency label on the running pipeline; memory-on-disk positions; Ring continuity log; sleep→numeric change; next-session routing drift) are each already green under their own phase evidence, but a single multi-session running-chamber trace tying them together is the natural post-review integration milestone.
3. **`core_state.json` says `G_value: 0.5`** while `constants.py` has `G = 5.0`. Integrator uses `C.G`, so it's cosmetic — reconcile to avoid confusion.

## What the Next Agent Needs to LEARN Before Starting

### Read in order:
1. **This handoff doc.**
2. **`Build Plan.md`** — master tracking doc; status line at top = where we are. Phase sections have goals + acceptance tests + per-segment trackers.
3. **`tests/evidence/p8s5_closeout_2026-09-18.md`** — the most recent close-out: what the live runs proved and how they map to the 13-point checklist.
4. **`docs/mayas_questions_phase0d.md`** — Maya's 5 Q&A = canonical spec reference for the cognitive engine.

### Key mental model (the "solar system" in one paragraph):
The QUESTION is a stone thrown into a pond. Each of the 7 archetype planets emits a WAVE based on how relevant the question is to its identity, blended with its current orbital position ("identity travels with position"). The waves SUPERPOSE: aligned voices reinforce, opposing voices cancel; observing COLLAPSES the pattern into **consensus** (the answer) + **tension** (the debate) — both kept. A live run then fires each planet's Id (Phase A), synthesizes cross-planet Ego responses (Phase B), and runs Superego review against Core Laws (Phase C); moons, when ON, add a two-lens framing per planet. PII is scrubbed at Ring Intake before embedding; garbage is rejected there with zero downstream LLM calls.

## Vault Structure (for navigation)

```
A:\AI\Solar_Agent_System\          ← Obsidian vault root
├── Home.md                        Navigation page
├── 01 - Vision/                   (high-level concept docs, if any)
├── 02 - Design/                   (architecture decisions, Maya's specs, etc.)
├── 03 - Implementation/
│   └── Build Plan.md              ← MASTER TRACKING DOC. Update status here each session.
├── 04 - Testing/                  (test results, calibration notes)
├── 05 - Notes/                    (John's rough ideas, meeting notes with Maya)
└── v17/resonant_cognition/        ← CODE ROOT (all Python + JSON above)
```

---

*End of handoff. Next agent: read this doc top-to-bottom, then Build Plan.md (status line), then `tests/evidence/p8s5_closeout_2026-09-18.md`. Phases 0A–8 are complete; the immediate next step is John's independent reviewer re-sweep of Phase 8, followed by the deferred integration milestone + GUESS-tunable confirmations listed above.*
