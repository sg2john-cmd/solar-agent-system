# Phase 0H — Multi-Pass Recursive Feedback (The Echo)

**Status: IMPLEMENTED + verified.** Date: this session. One small, togglable addition to the
collapse pipeline in `collapse.py`. No new files required at runtime; constants live in
`constants.py` (mirrored in `calibrate_axes.py` template).

## The idea (John, from Google's "Missing Catalyst" audit)

A thought is not one splash. In a real psyche: the Id fires a ripple → it hits the Superego
(counter-ripple) → that reshapes how the Ego perceives the original impulse → the next wave
is different. It's a recursive echo chamber. v17 before 0H dropped 7 stones and froze the water
after one microsecond. 0H lets the ripples bounce back **before** the waveform is observed.

## What was built (vector mode — no LLM calls)

`run_collapse()` now runs a pass loop:

- **Pass 1 (initial splash):** identical to pre-0H behavior — embed question, each planet emits
  `amplitude = mass × relevance`, context/G2 synthetic waves added, Dark Matter pull applied,
  then `collapse()`.
- **Passes 2..N:** `_apply_echo(waves, prev_result)` reads the previous pass's collapse output and
  adjusts only *planetary* wave directions (never `_ctx_*` / `_g2_bias`, so memory is untouched):
  1. **Repulsion from opposition** — a planet moves its direction *away* from any voice it cancelled
     against (`align < 0`). The debate response: you feel the pushback and pull back. Strength scales
     with how opposed they were, your own amplitude, and `ECHO_ALIGN_REPEL`.
  2. **Consensus echo-chamber pull** — every wave leans slightly toward the group consensus vector
     (`ECHO_CONSENSUS_PULL`). Kept LOW to preserve individuality.
  Then re-`collapse()`. Directions bend; energy/amplitude is preserved (same discipline as the DM pull),
  except a small global amplitude *retraction* under high tension (`ECHO_TENSION_GAIN`).

## Toggle / debug handles (constants.py)

| Constant | Default | Meaning |
|---|---|---|
| `ECHO_ENABLED` | `True` | Master switch. `False` → single pass, byte-identical to pre-0H. Use for A/B debugging. |
| `ECHO_PASSES` | `2` | Total passes incl. the initial splash (2 = one echo). Bump to 3 later if wanted. |
| `ECHO_TENSION_GAIN` | `0.5` *(GUESS)* | Global amplitude retraction when the field is tense. |
| `ECHO_ALIGN_REPEL` | `0.35` *(GUESS)* | Hardness of contrarian pullback from opponents. |
| `ECHO_CONSENSUS_PULL` | `0.12` *(GUESS)* | Echo-chamber convergence toward consensus (keep low). |

All three gains are GUESSES tuned by feel — no real session data yet. They're the debug knobs:
if the system feels too agreeable, drop `ECHO_CONSENSUS_PULL`; if it fights itself forever, drop
`ECHO_TENSION_GAIN`/`ECHO_ALIGN_REPEL`.

## Verification (this session)

Double-split test still passes with echo ON (opposition > agreement in tension). A/B on the
opposition prompt "tear down the rules and break everything":

| | Echo OFF | Echo ON |
|---|---|---|
| Rebel / Ruler amp | 0.848 / 0.844 | **0.636 / 0.633** (both retracted) |
| tension_raw | 1.356 | **0.902** (debate cooled) |
| surviving consensus | 2.435 | 1.942 |

Consensus vector moved ~0.49 Euclidean — a real behavioral change, not cosmetic. The two opponents
felt the collision and pulled back before speaking: exactly the Id→Superego counter-ripple John wanted.

## LLM-mode echo (future — ports almost unchanged)

When `WAVE_SPEECH_MODE = "llm"` lands (Phase B), the *same* pass loop applies. The only difference is
what each planet emits per pass: instead of a static identity vector, it generates short text via the
chamber model → embeds it. To make the echo genuinely richer in LLM mode, feed the previous pass's
consensus vector + tension description back into the generation prompt ("here's how the group reacted;
adjust your take") before re-embedding. The `_apply_echo` geometric adjustment can then be reduced or
dropped for planets that already "thought about it." Not built yet — see `emit_waves_llm()` stub.

## Open questions (for John)

1. **Pass count:** 2 is the default (initial + one echo). Want a 3-pass option exposed, or leave at 2?
2. **Gains are GUESSES.** After a few real conversations, review whether the echo makes responses too
   soft (over-retracted) or still too spiky. Tune via constants — no code change needed.
