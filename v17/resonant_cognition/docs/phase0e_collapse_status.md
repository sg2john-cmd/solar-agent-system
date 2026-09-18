# Phase 0E — Waveform Collapse: Status & Design Notes

## What's Working (verified by running)

`collapse.py` runs the full pipeline in **vector/dumb mode**:

```
question → MiniLM embed (384-dim)
         → each planet emits a wave (amplitude = mass × cosine(input, planet_identity_embedding))
         → superpose all 7 waves
         → read: consensus vector (what remains) + tension (what was cancelled/debated)
```

### Double-split test results (2025-06, this session)

| Test | Leading voices | Tension | Polarity |
|---|---|---|---|
| Agreement ("clear step-by-step analysis") | Sage 1.07, Ruler 0.62, Rebel 0.50 … all 7 speak | 1.171 | 0.578 |
| Opposition ("tear down rules, break everything") | **Rebel 0.85**, Ruler 0.84, Sage 0.63 … Hero/Caregiver quiet (0.19) | 1.447 | **0.996** |

Opposition correctly produces more tension + near-perfect polarity factor (two loud voices genuinely opposed). Agreement stays lower-tension with broad participation.

### Key fix this session
- Wave centers moved from coarse 3-axis semantic anchors → **full 384-dim MiniLM embeddings of each planet's identity text** (`id_flavor` + `ego_descriptor` from `planets/*.json`). This fixed the RULER-COLLAPSE defect (Ruler won everything) and gave genuine per-planet discrimination.
- Bug fix: scalar×list multiplication in vector superposition.

### Cancellation nodes: distributed, not single-point
In full 384-dim space no two planet identity texts are directly opposite (cosine ≈ −1). Cancellation is spread across many small anti-alignments — **this matches John's pond intuition**: "7 stones in water produce a web of intersections, not one clean node." The tension scalar captures total cancelled energy; the pair_map records per-pair contributions.

## Architecture Decisions (confirmed)

| Decision | Status |
|---|---|
| Vector mode = dumb planets (geometry only), LLM mode = 7 voices actually speaking | Both toggleable via `C.WAVE_SPEECH_MODE` |
| Opposition semantics first; fall back to "not-aligned" if it misbehaves | Working as intended in vector mode |
| Polarity-aware tension (solves "two negatives cancel → do we keep wrong answer?") | Implemented: small-voice cancellation down-weighted as noise |
| Gravity/position plays NO role in cognition (Maya spec) | Respected — collapse is purely semantic |
| 3D propagating wave-field simulation | Shelved (`docs/future_3d_wavefield.md`) |

## Memory: NOW WIRED (Phase 0F)

**What exists and is working:**

- `memory.py::SessionMemory` — per-turn log with exponential decay context waves (Option C blend).
- `collapse.py::run_collapse()` accepts optional `session_history` + `g2_bias_vector`; backward-compatible.
- `memory.py::load_g2_bias_wave()` — reads G2 committed contents into a low-amplitude mood wave (returns None until first session summary is persisted).
- `memory.py::summarize_session_for_g2()` — produces the dict to append to g2_selfmodel.json at session end. **Stub: not yet called by anything.** Wiring happens in Phase 7.

**What's still scaffold-only:**
- `bodies.py::MemoryEntry` (spatial zone-based entries for G1 swarm) — not wired, Phase 7.
- `SessionState.input_history` — superseded by SessionMemory for the collapse engine; kept for other subsystems.

See `docs/phase0f_session_memory.md` for full details, test results, and tunable constants.

## Next Steps (when John is ready)

1. **Phase 7 (sleep cycle):** wire G2 writer + moons + sandbox into offline pass. Activate the bias wave across sessions.
2. **LLM-mode wave speech** (`emit_waves_llm` stub): each planet generates a short response via Ring/chamber model → embed → use as wave vector.
3. **Comet/Jester trigger conditions**: still open (Phase 8).
4. **Ring wiring**: translate surviving consensus vector + tension reading into natural language response.
