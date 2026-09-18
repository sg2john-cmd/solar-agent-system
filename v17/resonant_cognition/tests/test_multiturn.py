"""
Resonant Cognition v17 — Phase 0F: Multi-turn session memory test.

Demonstrates that prior turns in a session actually CHANGE which planets speak on
subsequent questions, via Option C context waves (alpha*consensus + beta*question).

RUN: python -X utf8 test_multiturn.py
"""
import time
from collapse import run_collapse
from memory import SessionMemory
from resonance import embed as _reembed


def _top(voices, n=4):
    ranked = sorted(((p, w["amplitude"]) for p, w in voices.items() if not p.startswith("_")),
                    key=lambda kv: kv[1], reverse=True)
    return ", ".join(f"{p}:{a:.2f}" for p, a in ranked[:n] if a > 0.05)


def _ctx_count(voices):
    return sum(1 for k in voices if k.startswith("_ctx"))


print("MULTI-TURN MEMORY TEST\n" + "=" * 60)

session = SessionMemory()

# A small conversation: factual, then emotional, then moral, then chaotic.
turns = [
    ("Turn 1 (quiet fact)", "What is the boiling point of water at sea level?"),
    ("Turn 2 (emotional)",   "Why do people grieve for places they will never visit again?"),
    ("Turn 3 (moral)",       "Is it wrong to lie to a dying person to spare them fear?"),
    ("Turn 4 (chaos)",       "Be completely free yet fully obedient, destroy the system but build a better one."),
]

print("\n--- Running first pass: each turn with memory from PRIOR turns ---")
for label, q in turns:
    hist = session.get_background_waves(now_ts=time.time())
    out = run_collapse(q, session_history=hist)
    res = out["result"]
    print(f"\n{label}")
    print(f"  Q: {q[:70]}...")
    print(f"  ctx waves in superposition: {_ctx_count(out['waves'])}   (expect {len(session)})")
    print(f"  voices -> {_top(out['waves'])}")
    print(f"  energy in={res['raw_energy']:.2f} out={res['total_energy']:.2f} "
          f"tension={res['tension']:.3f} polarity={res['polarity_factor']}")
    # Record this turn for the NEXT iteration.
    session.record_turn(q, _reembed(q), res["consensus_vector"], res["tension"])


def _reembed(text):
    from resonance import embed
    return embed(text)


print("\n\n--- Now: ASK THE SAME FIRST QUESTION AGAIN (Turn 5 = repeat of Turn 1's question) ---")
# Same quiet factual question, but now the session has 4 turns of emotional/moral/chaotic context.
repeat_q = "What is the boiling point of water at sea level?"
hist = session.get_background_waves(now_ts=time.time())
out_repeat = run_collapse(repeat_q, session_history=hist)

# Compare against a FRESH stateless answer to the same question (no memory).
out_fresh = run_collapse(repeat_q)  # no session history

print(f"\nSAME QUESTION: {repeat_q}")
print(f"\n  STATELESS (no memory):")
print(f"    voices -> {_top(out_fresh['waves'])}")
print(f"    tension={out_fresh['result']['tension']:.3f} polarity={out_fresh['result']['polarity_factor']}")

print(f"\n  WITH 4-TURN SESSION MEMORY:")
print(f"    ctx waves in superposition: {_ctx_count(out_repeat['waves'])}")
print(f"    voices -> {_top(out_repeat['waves'])}")
print(f"    tension={out_repeat['result']['tension']:.3f} polarity={out_repeat['result']['polarity_factor']}")

# Did the context actually change anything?
diff_tension = abs(out_repeat["result"]["tension"] - out_fresh["result"]["tension"])
fresh_top = _top(out_fresh["waves"]).split(",")[0].strip()
mem_top   = _top(out_repeat["waves"]).split(",")[0].strip()

print(f"\n--- interpretation ---")
print(f"  tension delta: {diff_tension:.3f}  (0.0 = memory had NO effect, >0 = it did)")
print(f"  top voice stateless : {fresh_top}")
print(f"  top voice with-mem  : {mem_top}")
if diff_tension < 0.01 and fresh_top == mem_top:
    print("  >>> WARNING: memory appears to have had no measurable effect.")
    print("      Check context wave amplitudes or blend weights in memory.py.")
else:
    print("  >>> Memory is influencing the collapse (tension shifted / top voice changed).")
