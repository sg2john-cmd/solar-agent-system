"""Quick multi-prompt test for collapse.py — runs 5 scenarios, prints compact results."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collapse import run_collapse

tests = [
    ("MULTI: creative + structural", 
     "Design a story about a broken clockmaker who must fix time itself using only the tools he has left."),
    ("FOCUSED-2: emotional + logical", 
     "Why do people grieve for places they will never visit again?"),
    ("FOCUSED-3: moral dilemma", 
     "Is it wrong to lie to a dying person to spare them fear?"),
    ("ALL/CHAOS: contradictory demands", 
     "Be completely free yet fully obedient, destroy the system but build a better one inside its bones, and do all of this quietly."),
    ("QUIET: simple factual", 
     "What is the boiling point of water at sea level?"),
]

for label, q in tests:
    out = run_collapse(q)
    res = out["result"]
    spoken = sorted(
        ((p, w) for p, w in out["waves"].items() if w["amplitude"] > 0.1),
        key=lambda kv: kv[1]["amplitude"], reverse=True,
    )
    print(f"\n--- {label} ---")
    print(f"  Q: {q[:70]}...")
    voices = ", ".join(f"{p}:{w['amplitude']:.2f}" for p, w in spoken)
    print(f"  voices -> {voices}")
    print(f"  energy in={res['raw_energy']:.2f} out={res['total_energy']:.2f} tension={res['tension']:.3f} polarity={res['polarity_factor']}")
