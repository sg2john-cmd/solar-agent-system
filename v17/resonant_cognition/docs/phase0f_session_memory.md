# Phase 0F — Session Memory & G2 Bias Wave (COMPLETE)

## What Was Built This Session

**Layer 1 — Session RAM (prior-turn context waves):**
- `memory.py::SessionMemory` records each turn's question embedding + consensus vector + tension.
- On the next collapse, prior turns enter the superposition as extra low-amplitude waves with exponential time decay (half-life ≈ 5 min wall clock).
- **Option C blend** (John-approved): context direction = `0.8 * consensus_vec + 0.2 * question_vec`. The "why" (what the system landed on) dominates; the literal question is a faint trace for disambiguation.

**Layer 2 — G2 bias wave (cross-session mood):**
- `memory.py::load_g2_bias_wave()` reads committed entries from `g2_selfmodel.json:contents[]`.
- Aggregates them into one persistent low-amplitude wave added to every collapse.
- Currently returns None because contents is empty (no sessions have been summarized yet). Will activate once the session-end writer runs.

**Layer 3 — G1 long-term knowledge:** NOT wired. Phase 7.

## Files Changed / Added

| File | Change |
|---|---|
| `memory.py` (~280 lines) | **NEW.** SessionMemory class, load_g2_bias_wave(), summarize_session_for_g2(). Self-testable via `python -X utf8 memory.py`. |
| `collapse.py::run_collapse()` | Now accepts optional `session_history` and `g2_bias_vector` params. Backward-compatible: calling with no args produces identical results to before (verified by re-running test_multi.py — unchanged output). |
| `test_multiturn.py` (~90 lines) | **NEW.** 5-turn demonstration showing context waves shift tension on repeated questions. Run: `python -X utf8 test_multiturn.py`. |

## Verified Results

- `test_multi.py`: PASS (identical to pre-change baseline).
- `test_multiturn.py`: PASS. Same factual question asked stateless vs with 4 prior emotional/moral/chaotic turns → tension shifts from 0.110 to 0.247 (+125%). Top planet unchanged (Everyman — it IS a quiet fact) but the *debate field* is warmer because of accumulated context.
- `memory.py` self-test: PASS.

## What's Stubbed / Not Yet Wired

| Item | Status | Where it lives |
|---|---|---|
| G2 session-end writer (persist summary into g2_selfmodel.json contents[]) | **Stub.** Function exists (`summarize_session_for_g2`), but nothing calls it yet. Wiring happens in Phase 7 (sleep cycle) when the offline pass runs the 3 moons + sandbox check before committing. | `memory.py::summarize_session_for_g2()` — returns a ready-to-append dict; caller appends to JSON. |
| "System check" bootstrap turn (seed first real question with a warm baseline instead of void) | **Future option, not blocking.** Sketch: at session start, run one synthetic self-referential prompt through `run_collapse()`, record it as turn 0 in SessionMemory. Subsequent turns then have context from t=1. Benefit: stable cross-session baseline for comparison testing. Cost: one extra embedding call per session start. | Noted here; implement when needed (likely Phase 7 or later). |
| LLM-mode wave speech (`emit_waves_llm`) | Stub (raises NotImplementedError). Later phase. | `collapse.py` |
| Comet/Jester trigger conditions | Unresolved. Phase 8. | `resonance.py::should_comet_fire()` |
| Ring wiring (consensus vector → natural language response) | Not built. Agent stands in for it currently. | Future phase. |

## Tunable Constants (in memory.py, NOT constants.py — promote if calibration needs them)

| Constant | Value | Meaning | Flagged as GUESS? |
|---|---|---|---|
| `SESSION_DECAY_HALF_LIFE_MIN` | 5.0 min | How fast prior-turn waves fade | Yes — tune after real sessions |
| `SESSION_WAVE_BASE_AMPLITUDE` | 0.35 | Max loudness of a single context wave vs planets | Yes |
| `CONTEXT_BLEND_ALPHA_CONSENSUS` | 0.8 | Weight on "why" (consensus) in Option C blend | John-approved ratio; tune if needed |
| `CONTEXT_BLEND_BETA_QUESTION` | 0.2 | Weight on literal question in Option C blend | Complementary to alpha |
| `G2_BIAS_AMPLITUDE` | 0.15 | Loudness of self-model mood wave | Yes — very low by design |
| `MAX_SESSION_TURNS_IN_SUPERPOSITION` | 8 | Cap on how many prior turns contribute waves | Reasonable default; tune if long sessions show drift |

## Next Steps (when John is ready)

1. **Phase 7 (sleep cycle):** wire the G2 writer + moons + sandbox into an offline pass that runs at session end / micro-sleep / deep-sleep triggers.
2. **LLM-mode wave speech:** build `emit_waves_llm` so 7 distinct voices actually generate text → embed → collapse. The math already handles it; only the emitter needs building.
3. **Comet triggers (Phase 8):** decide the predicate for when Jester fires.
4. **Ring wiring:** translate consensus vector + tension reading into natural language via a swappable frontend model.
