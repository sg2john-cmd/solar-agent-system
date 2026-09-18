"""
Resonant Cognition v17 — Phase 3: MOONS A/B COMPARISON (full A+B+C chamber)
===========================================================================

NOT a pass/fail test. This is an EVIDENCE / QUALITY run that directly answers John's
question by doing the SAME ten complex questions TWICE and lining them up side by side:

    RUN A — Moons OFF   (MOON_HEMISPHERE_ENABLED = False)  ~21 LLM calls / question
    RUN B — Moons ON    (MOON_HEMISPHERE_ENABLED = True)   ~30 LLM calls / question

The ONLY thing that changes between the two runs is the moon toggle. Comet stays OFF for
both (it only fires after repeated same-dominant sessions; these 10 are all different topics,
so it would not fire anyway). Real routed weights are used per question in BOTH runs, so each
planet's loudness reflects genuine routing and is identical across A and B.

Purpose: a direct apples-to-apples look at what the moon-hemisphere two-lens framing actually
changes (or doesn't) in Phase A raw Id, and whether it shifts Ego synthesis or Superego verdicts
downstream — so we can judge "is it worth keeping ON by default?" on substance, not vibes.

Each full chamber run = 21 LLM calls (~80-110s). Moons mode adds one lens pair + merge per
planet in Phase A (3 calls/planet vs 1), i.e. ~9 extra calls/question. 10 questions each way ~=
~25-30 min total wall time.

Outputs:
  - evidence/complex_ab_moonsOFF_<ts>.txt   (full readable transcript, run A)
  - evidence/complex_ab_moonsON_<ts>.txt    (full readable transcript, run B)
  - evidence/complex_ab_comparison_<ts>.txt (side-by-side per question + verdict matrices)

RUN:  python -X utf8 tests/run_complex_chamber_ab.py
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


# ─── THE TEN COMPLEX QUESTIONS (John's list — identical to run_complex_chamber.py) ──

QUESTIONS = [
    ("The Irreversible Pivot",
     "I have built a stable, highly predictable life, but I am considering blowing it up to "
     "pursue an idea that has no guarantee of success. How do I know if I'm being courageous or "
     "just recklessly bored?"),
    ("The Optimization vs. Serendipity Dilemma",
     "Should I strictly optimize every hour of my day to guarantee progress toward long-term "
     "goals, or leave vast open spaces for chance, intuition, and unplanned opportunities?"),
    ("The Burden of Unearned Certainty",
     "How do I deal with the paralysis of knowing that any choice you make today is based on "
     "incomplete data, yet waiting for full certainty guarantees missing the window entirely?"),
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
    """Genuine per-planet routed weights from a question (mirror of routing internals).

    Computed ONCE per question and reused for both runs so the only variable is moons.
    """
    core, planets = routing.load_orbital_state()
    wave_centers = _planet_wave_centers()
    centers = routing.field_centers_for_all(wave_centers, planets)
    pw = routing.per_planet_weights(_embed(question), centers, core.position)
    return {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}


def run_chamber_pass(moons_on: bool):
    """Run all ten questions through the full A+B+C chamber with moons forced to moons_on.

    Returns a list of per-question records and the total wall time.
    """
    C.MOON_HEMISPHERE_ENABLED = bool(moons_on)
    C.COMET_TRIGGER_ENABLED = False  # comet stays off for BOTH runs (single variable: moons).
    print(f"\n{'='*72}")
    print(f"  CHAMBER PASS — Moons {'ON' if moons_on else 'OFF'}")
    print(f"{'='*72}")

    records = []
    t_pass = time.time()
    for idx, (title, q) in enumerate(QUESTIONS, start=1):
        weights = compute_routed_weights(q)
        ranked = sorted(weights.items(), key=lambda kv: -kv[1])
        top3 = ", ".join(f"{p}={w:.4f}" for p, w in ranked[:3])

        print(f"\n--- [{idx}/{len(QUESTIONS)}] {title}  (dominant={ranked[0][0]}, top3: {top3}) ---")
        t0 = time.time()
        combined = cc.run_phase_a_b_c(q, routed_weights=weights)
        dt = round(time.time() - t0, 1)

        verdicts = {pid: r.get("verdict", "UNKNOWN") for pid, r in combined["phase_c"].items()}
        approves = sum(1 for v in verdicts.values() if v == "APPROVE")
        redirects = sum(1 for v in verdicts.values() if v == "REDIRECT")

        records.append({
            "title": title,
            "question": q,
            "dominant": ranked[0][0],
            "top3": top3,
            "weights": weights,
            "phase_a": combined["phase_a"],
            "phase_b": combined["phase_b"],
            "verdicts": verdicts,
            "approves": approves,
            "redirects": redirects,
            "time_s": dt,
        })
        print(f"    verdicts: APPROVE={approves} REDIRECT={redirects}  ({dt}s)")

    return records, round(time.time() - t_pass, 1)


def write_transcript(path: str, label: str, records: list[dict], pass_time: float):
    """Write a full readable transcript for one chamber pass."""
    lines = [
        "=" * 78,
        f"COMPLEX-QUESTION CHAMBER — {label}",
        f"Model: {cc._get_model_id()}   Comet trigger: OFF (both runs)",
        f"Pass wall time: {pass_time}s",
        "=" * 78,
    ]
    for idx, rec in enumerate(records, start=1):
        lines.append("\n" + "#" * 72)
        lines.append(f"QUESTION {idx} — {rec['title']}")
        lines.append(f'"{rec["question"]}"')
        lines.append(f"[routing] dominant={rec['dominant']}   top3: {rec['top3']}")
        lines.append("#" * 72)

        lines.append("\n── PHASE A · ID FIRES (raw instinct) ──")
        for pid in sorted(rec["phase_a"].keys()):
            r = rec["phase_a"][pid]
            name = cc._PLANET_NAMES.get(pid, pid)
            w = rec["weights"].get(pid, 0.5)
            lines.append(f"  {name:<12} (w={w:.2f}): {r['response'].strip()}")

        lines.append("\n── PHASE B · EGO SYNTHESIS ──")
        for pid in sorted(rec["phase_b"].keys()):
            r = rec["phase_b"][pid]
            name = cc._PLANET_NAMES.get(pid, pid)
            lines.append(f"  {name:<12}: {r['response'].strip()}")

        lines.append("\n── PHASE C · SUPEREGO REVIEW (verdicts) ──")
        for pid in sorted(rec["verdicts"].keys()):
            name = cc._PLANET_NAMES.get(pid, pid)
            lines.append(f"  {name:<12} [{rec['verdicts'][pid]}]")

    return "\n".join(lines)


def verdict_matrix(records: list[dict]) -> str:
    order = sorted(cc._PLANET_NAMES.keys())
    header = "Question".ljust(34) + "".join(f"{p[:5].upper():>6}" for p in order)
    rows = [header, "-" * len(header)]
    for rec in records:
        row = (rec["title"][:30] + "..").ljust(34) if len(rec["title"]) > 30 else rec["title"].ljust(34)
        row += "".join(f"{rec['verdicts'].get(p, '?')[0].upper():>6}" for p in order)
        rows.append(row)
    return "\n".join(rows)


def write_comparison(path: str, a_records: list[dict], b_records: list[dict]):
    """Side-by-side comparison + verdict matrices + a short summary of what changed."""
    L = [
        "=" * 78,
        "MOONS A/B COMPARISON — same 10 questions, moons OFF (A) vs ON (B)",
        f"Model: {cc._get_model_id()}   Comet trigger: OFF for both",
        "=" * 78,
    ]

    # Verdict matrices first — the quickest signal of downstream shift.
    L.append("\n### VERDICT MATRIX — MOONS OFF (A) ###")
    L.append(verdict_matrix(a_records))
    L.append("\n\n### VERDICT MATRIX — MOONS ON (B) ###")
    L.append(verdict_matrix(b_records))

    # Per-question side-by-side.
    for idx, (rec_a, rec_b) in enumerate(zip(a_records, b_records), start=1):
        L.append("\n" + "#" * 72)
        L.append(f"QUESTION {idx} — {rec_a['title']}")
        L.append(f'"{rec_a["question"]}"')
        va = sum(1 for v in rec_a["verdicts"].values() if v == "APPROVE")
        vb = sum(1 for v in rec_b["verdicts"].values() if v == "APPROVE")
        L.append(f"  verdicts: A(moonsOFF)=A{va}/R{7-va}   B(moonsON)=A{vb}/R{7-vb}")

        # Phase A side by side per planet.
        L.append("\n  PHASE A (raw Id) — OFF vs ON:")
        for pid in sorted(rec_a["phase_a"].keys()):
            name = cc._PLANET_NAMES.get(pid, pid)
            ta = rec_a["phase_a"][pid]["response"].strip()
            tb = rec_b["phase_a"][pid]["response"].strip()
            L.append(f"    {name:<12}")
            L.append(f"       OFF: {ta}")
            L.append(f"       ON : {tb}")

        # Phase B side by side per planet (shorter, to keep it readable).
        L.append("\n  PHASE B (Ego synthesis) — OFF vs ON:")
        for pid in sorted(rec_a["phase_b"].keys()):
            name = cc._PLANET_NAMES.get(pid, pid)
            ta = rec_a["phase_b"][pid]["response"].strip()
            tb = rec_b["phase_b"][pid]["response"].strip()
            L.append(f"    {name:<12}")
            L.append(f"       OFF: {ta[:600]}{'…' if len(ta) > 600 else ''}")
            L.append(f"       ON : {tb[:600]}{'…' if len(tb) > 600 else ''}")

    # Summary of verdict shifts.
    L.append("\n\n" + "=" * 78)
    L.append("VERDICT SHIFT SUMMARY (OFF vs ON, per question)")
    L.append("=" * 78)
    shifts = 0
    for idx, (rec_a, rec_b) in enumerate(zip(a_records, b_records), start=1):
        changed = [p for p in cc._PLANET_NAMES if rec_a["verdicts"].get(p) != rec_b["verdicts"].get(p)]
        if changed:
            shifts += 1
            detail = ", ".join(
                f"{cc._PLANET_NAMES.get(p,p)} {rec_a['verdicts'].get(p,'?')}→{rec_b['verdicts'].get(p,'?')}"
                for p in changed
            )
            L.append(f"  Q{idx:>2} {rec_a['title'][:34]:<36} {len(changed)} changed: {detail}")
    if shifts == 0:
        L.append("  (no verdict changes across all 10 questions — moons did NOT shift Superego calls)")
    else:
        L.append(f"\n  {shifts}/{len(a_records)} questions had at least one planet change its verdict.")

    return "\n".join(L)


def main() -> int:
    cc._ensure_names()   # populate _PLANET_NAMES for display.

    print("=" * 72)
    print("MOONS A/B COMPARISON — full A+B+C chamber, same 10 questions")
    print(f"Model: {cc._get_model_id()}")
    print("This makes ~ (21 + 30) x 10 LLM calls. Expect ~25-30 min.")
    print("=" * 72)

    t_start = time.time()

    # RUN A — moons OFF.
    a_records, a_time = run_chamber_pass(moons_on=False)
    # RUN B — moons ON.
    b_records, b_time = run_chamber_pass(moons_on=True)

    total = round(time.time() - t_start, 1)

    ts = time.strftime("%Y%m%d_%H%M%S")
    ev = os.path.join(_HERE, "evidence")
    txt_a = os.path.join(ev, f"complex_ab_moonsOFF_{ts}.txt")
    txt_b = os.path.join(ev, f"complex_ab_moonsON_{ts}.txt")
    txt_cmp = os.path.join(ev, f"complex_ab_comparison_{ts}.txt")

    with open(txt_a, "w", encoding="utf-8") as f:
        f.write(write_transcript(txt_a, "MOONS OFF (A)", a_records, a_time))
    with open(txt_b, "w", encoding="utf-8") as f:
        f.write(write_transcript(txt_b, "MOONS ON (B)", b_records, b_time))
    with open(txt_cmp, "w", encoding="utf-8") as f:
        f.write(write_comparison(txt_cmp, a_records, b_records))

    print("\n" + "=" * 72)
    print("DONE. Moons A/B comparison complete.")
    print(f"  Run A (moons OFF): {a_time}s   Run B (moons ON): {b_time}s   Total: {total}s")
    print(f"  Transcript (OFF):     {txt_a}")
    print(f"  Transcript (ON):      {txt_b}")
    print(f"  Side-by-side compare: {txt_cmp}")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    # Restore defaults in a finally so the repo is left exactly as found.
    try:
        sys.exit(main())
    finally:
        C.MOON_HEMISPHERE_ENABLED = False
        C.COMET_TRIGGER_ENABLED = False
