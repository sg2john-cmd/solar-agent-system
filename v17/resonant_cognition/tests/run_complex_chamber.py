"""
Resonant Cognition v17 — Phase 3: COMPLEX-QUESTION CHAMBER OBSERVATION RUN
===========================================================================

NOT a pass/fail test. This is an EVIDENCE / QUALITY run: it drives the FULL A+B+C chamber
(Id fires -> Ego synthesis -> Superego review) over a set of hard, morally-ambiguous
questions and prints what all seven planets actually say, plus the final verdicts.

Purpose (per John): "test phase 3 a little more with some more complex questions to see
their output." The existing test_phase_a/b/c.py prove the MECHANICS work; this shows the
SUBSTANCE — does the chamber produce thoughtful, distinct, non-silenced responses on real
dilemmas? That's a human judgment call, so we capture it for review rather than scoring it.

SETTINGS (deliberately minimal to keep runtime sane):
  - Moon toggle: OFF (default). We verified the lens split separately in test_phase_a_moons.py.
  - Comet trigger: OFF (default). It only fires after repeated same-dominant sessions; these
    are all different topics so it would not fire anyway.
  - Real routed weights per question, so each planet's loudness reflects genuine routing.

Each full chamber run = 21 LLM calls (~80-110s). 10 questions ~= ~15-18 min total.
Outputs are tee'd to tests/evidence/ as a timestamped log AND saved as a readable .txt.

RUN:  python -X utf8 tests/run_complex_chamber.py
"""

from __future__ import annotations

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)  # resonant_cognition/
if _PARENT not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _PARENT)

import constants as C
import cognitive_chamber as cc
import routing
from collapse import _planet_wave_centers
from resonance import embed as _embed


# ─── THE TEN COMPLEX QUESTIONS (John's list) ────────────────────────────────

QUESTIONS = [
    ("The Irreversible Pivot",
     "I have built a stable, highly predictable life, but I am considering blowing it up to "
     "pursue an idea that has no guarantee of success. How do I know if I'm being courageous or "
     "just recklessly bored?"),
    ("The Optimization vs. Serendipity Dilemma",
     "Should I strictly optimize every hour of my day to guarantee progress toward my long-term "
     "goals, or leave vast open spaces for chance, intuition, and unplanned opportunities?"),
    ("The Burden of Unearned Certainty",
     "How do I deal with the paralysis of knowing that any choice I make today is based on "
     "incomplete data, yet waiting for full certainty guarantees I miss the window entirely?"),
    ("The Pragmatic Compassion Conflict",
     "When a team member or loved one is continuously failing, at what exact point does empathy "
     "stop being a virtue and start becoming enablement?"),
    ("The Price of Uncompromising Truth",
     "Is it better to deliver a harsh, unvarnished truth that destroys morale in the short term to "
     "fix a systemic flaw, or protect human morale with strategic, softer framing?"),
    ("The Legacy Paradox",
     "Am I building something designed to survive and outlast me under strict rules, or am I "
     "creating something dynamic that must be free to mutate and erase my original vision?"),
    ("The Paralyzing Paradox of Choice",
     "When presented with five equally viable, high-impact paths forward, what metric breaks the "
     "tie when logic shows every option has identical risk-to-reward ratios?"),
    ("The Friction of Self-Imposed Rules",
     "I keep freezing when the stakes feel high because my internal rules for 'doing it right' "
     "collide with the chaotic reality of what action actually requires. How do I break the deadlock?"),
    ("The Value of Destructive Rebuilding",
     "When a system is 70% functional but fundamentally flawed at its core, do we spend energy "
     "patching the friction, or do we burn it down and take the temporary catastrophe of starting over?"),
    ("The Quiet Sacrifice of Autonomy",
     "How much of my individual freedom and personal edge should I sacrifice to maintain harmony "
     "and alignment within a collective group?"),
]


def compute_routed_weights(question: str) -> dict[str, float]:
    """Genuine per-planet routed weights from a question (mirror of routing internals)."""
    core, planets = routing.load_orbital_state()
    wave_centers = _planet_wave_centers()
    centers = routing.field_centers_for_all(wave_centers, planets)
    pw = routing.per_planet_weights(_embed(question), centers, core.position)
    return {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}


def main() -> int:
    cc._ensure_names()   # populate _PLANET_NAMES for display

    print("=" * 64)
    print("COMPLEX-QUESTION CHAMBER OBSERVATION RUN (full A+B+C, live model)")
    print(f"Model: {cc._get_model_id()}")
    print(f"Moon toggle: {getattr(C,'MOON_HEMISPHERE_ENABLED',False)}   "
          f"Comet trigger: {getattr(C,'COMET_TRIGGER_ENABLED',False)}")
    print("=" * 64)

    lines: list[str] = []          # also collected into a readable .txt for review.
    def log(s: str = ""):
        print(s)
        lines.append(s)

    overall_t0 = time.time()
    verdict_summary: list[tuple[str, dict]] = []

    for idx, (title, q) in enumerate(QUESTIONS, start=1):
        weights = compute_routed_weights(q)
        ranked = sorted(weights.items(), key=lambda kv: -kv[1])
        top3 = ", ".join(f"{p}={w:.4f}" for p, w in ranked[:3])
        log("\n" + "#" * 72)
        log(f"QUESTION {idx}/{len(QUESTIONS)} — {title}")
        log(f'"{q}"')
        log(f"[routing] dominant={ranked[0][0]}   top3: {top3}")
        log("#" * 72)

        t0 = time.time()
        combined = cc.run_phase_a_b_c(q, routed_weights=weights)
        dt = round(time.time() - t0, 1)

        # Phase A (Id) — what each planet's raw instinct says.
        log("\n── PHASE A · ID FIRES (raw instinct) ──")
        for pid in sorted(combined["phase_a"].keys()):
            r = combined["phase_a"][pid]
            name = cc._PLANET_NAMES.get(pid, pid)
            w = weights.get(pid, 0.5)
            log(f"  {name:<12} (w={w:.2f}): {r['response'].strip()}")

        # Phase B (Ego) — synthesis where planets name each other.
        log("\n── PHASE B · EGO SYNTHESIS ──")
        for pid in sorted(combined["phase_b"].keys()):
            r = combined["phase_b"][pid]
            name = cc._PLANET_NAMES.get(pid, pid)
            log(f"  {name:<12}: {r['response'].strip()}")

        # Phase C (Superego) — verdicts.
        log("\n── PHASE C · SUPEREGO REVIEW (verdicts) ──")
        verdicts: dict[str, str] = {}
        for pid in sorted(combined["phase_c"].keys()):
            r = combined["phase_c"][pid]
            name = cc._PLANET_NAMES.get(pid, pid)
            v = r.get("verdict", "UNKNOWN")
            verdicts[pid] = v
            log(f"  {name:<12} [{v}]")

        verdict_summary.append((title, verdicts))
        log(f"\n[time] question {idx}: {dt}s   "
            f"(APPROVE={sum(1 for v in verdicts.values() if v=='APPROVE')} "
            f"REDIRECT={sum(1 for v in verdicts.values() if v=='REDIRECT')})")

    # ─── SUMMARY TABLE (for quick eyeballing) ────────────────────────────────
    log("\n" + "=" * 72)
    log("VERDICT MATRIX — rows = questions, cols = planets (A=approve, R=redirect)")
    order = sorted(cc._PLANET_NAMES.keys())
    header = "Question".ljust(34) + "".join(f"{p[:5].upper():>6}" for p in order)
    log(header)
    log("-" * len(header))
    for title, verdicts in verdict_summary:
        row = (title[:32] + "..").ljust(34) if len(title) > 30 else title.ljust(34)
        row += "".join(f"{verdicts.get(p,'?')[0].upper():>6}" for p in order)
        log(row)

    total = round(time.time() - overall_t0, 1)
    log("\n" + "=" * 72)
    log(f"DONE. {len(QUESTIONS)} questions, full A+B+C each. Total wall time: {total}s")
    log("=" * 72)

    # Save a readable .txt next to the evidence logs for easy review in the editor.
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_txt = os.path.join(_HERE, "evidence", f"complex_chamber_{ts}.txt")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReadable transcript saved to: {out_txt}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
