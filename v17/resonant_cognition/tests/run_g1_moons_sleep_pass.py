"""
Resonant Cognition v17 — G1 FILTER-MOONS SLEEP PASS (live LLM evidence)
=======================================================================

WHY THIS EXISTS:
  The production-config verify runner proved the wiring imports and the toggle is
  active, but G1's ring_buffer was empty so no candidates actually went through
  the 3-moon LLM pre-pass. This runner seeds a small set of realistic candidates
  (good knowledge, borderline junk, redundant entry) into the ring buffer, then
  runs g1_sleep_pass_i() with G1_FILTER_MOONS_ENABLED=True so we get concrete
  evidence that the moons actually fire, make verdicts, and influence promotion.

CANDIDATES SEEDED:
  1. A clear, operational, non-redundant insight (should PROMOTE)
  2. Coherent but low-value filler / "AI slop" (should EJECT or stay peripheral)
  3. Something that slightly contradicts an existing committed entry (if any exist;
     otherwise tests the clarity/relevance moons on its own merit)

CONVENTION: observational run_ runner — no exit-code gate. Writes one dated
transcript to tests/evidence/. Toggles set in-memory only.

Run (needs LM Studio at 127.0.0.1:1234 for the moon LLM calls):
    python -X utf8 tests/run_g1_moons_sleep_pass.py     # ~2-5 min (3 candidates × ~3 moon calls)
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in [os.path.abspath(p) for p in sys.path]:
    sys.path.insert(0, _PARENT)

import constants as C
from giants.g1_ops import g1_add_candidate, g1_sleep_pass_i, _G1_PATH

_EVIDENCE_DIR = os.path.join(_HERE, "evidence")


# ─── Candidates to seed ────────────────────────────────────────────────────────

CANDIDATES = [
    {
        "label": "good_insight",
        "text": (
            "When a user expresses decision paralysis, the most effective intervention is not "
            "to provide more options or analysis but to introduce a reversibility filter: "
            "'Can this choice be undone?' This single binary test converts an open-ended fear "
            "into a bounded engineering constraint and has shown consistent reduction in "
            "overthinking loops across multiple session types."
        ),
        "mass": 0.7,
    },
    {
        "label": "borderline_slop",
        "text": (
            "It is generally acknowledged that cognitive systems benefit from some degree of "
            "structured reflection and periodic review in order to maintain overall coherence "
            "and avoid the accumulation of unnecessary complexity over extended operational periods."
        ),
        "mass": 0.4,
    },
    {
        "label": "vague_redundant",
        "text": (
            "The system should balance structure with flexibility, allowing for both planned "
            "execution and adaptive response to emerging circumstances in a holistic manner."
        ),
        "mass": 0.3,
    },
]


def main() -> None:
    # Toggle moons ON in-memory (constants.py on disk untouched).
    C.G1_FILTER_MOONS_ENABLED = True

    print("#" * 72)
    print("G1 FILTER-MOONS SLEEP PASS — live LLM evidence run")
    print(f"  G1_FILTER_MOONS_ENABLED = {C.G1_FILTER_MOONS_ENABLED}")
    print(f"  G1 path: {_G1_PATH}")
    print(f"  Candidates to seed: {len(CANDIDATES)}")
    print("#" * 72)

    # ── Step 1: Seed candidates into the ring buffer ──────────────────────────
    seeded = []
    for cand in CANDIDATES:
        entry = g1_add_candidate(text=cand["text"], mass=cand["mass"], path=_G1_PATH)
        seeded.append({"label": cand["label"], "id": entry["id"], "text": entry["text"][:80]})
        print(f"  [seed] {cand['label']:<20} -> {entry['id']} (mass={cand['mass']})")

    # ── Step 2: Run the sleep pass with moons ON ─────────────────────────────
    print("\n--- Running g1_sleep_pass_i() with filter moons ON ---")
    t0 = time.time()
    try:
        report = g1_sleep_pass_i(_G1_PATH)
    except Exception as e:
        traceback.print_exc()
        report = {"error": f"{type(e).__name__}: {e}"}
    elapsed = time.time() - t0

    # ── Step 3: Print results ────────────────────────────────────────────────
    print(f"\n--- Results ({elapsed:.1f}s) ---")
    if "error" in report:
        print(f"  ERROR: {report['error']}")
    else:
        promoted = report.get("promoted", [])
        ejected = report.get("ejected", [])
        held = report.get("held_for_review", [])
        remaining = report.get("remaining_ring", report.get("still_pending", []))

        print(f"  Promoted:   {len(promoted)}")
        for e in promoted:
            reason = e.get("reject_reason", "") or ""
            moon_v = e.get("moon_verdict", "") or ""
            print(f"    + {e['id']}  moon={moon_v}  text={e['text'][:60]}...")

        print(f"  Ejected:    {len(ejected)}")
        for e in ejected:
            reason = e.get("reject_reason", "") or ""
            moon_v = e.get("moon_verdict", "") or ""
            print(f"    - {e['id']}  reason={reason}  moon={moon_v}  text={e['text'][:60]}...")

        if held:
            print(f"  Held for review: {len(held)}")
            for e in held:
                print(f"    ! {e['id']}  text={e['text'][:60]}...")

        # Check which seeded IDs got which verdicts
        print("\n  Per-candidate outcomes:")
        all_processed = promoted + ejected + (held or [])
        for s in seeded:
            match = next((p for p in all_processed if p["id"] == s["id"]), None)
            if match:
                status = "PROMOTED" if match in promoted else ("EJECTED" if match in ejected else "HELD")
                moon_v = match.get("moon_verdict", "n/a") or "n/a"
                reject_r = match.get("reject_reason", "") or ""
                print(f"    {s['label']:<20} -> {status:<10}  moon={moon_v:<25}  reason={reject_r}")
            else:
                print(f"    {s['label']:<20} -> STILL PENDING (no verdict this pass)")

        # Score breakdown if available
        for e in all_processed:
            sb = e.get("score_breakdown")
            if sb:
                print(f"\n  Score breakdown [{e['id']}]: {sb}")

    # ── Step 4: Write transcript to evidence ─────────────────────────────────
    os.makedirs(_EVIDENCE_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(_EVIDENCE_DIR, f"g1_moons_sleep_pass_{stamp}.txt")

    L = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    L.append("#" * 72)
    L.append("G1 FILTER-MOONS SLEEP PASS — LIVE EVIDENCE TRANSCRIPT")
    L.append(f"# Generated: {ts}")
    L.append(f"# G1_FILTER_MOONS_ENABLED = True (in-memory)")
    L.append(f"# Duration: {elapsed:.1f}s")
    L.append("#" * 72)

    L.append("\nSEEDED CANDIDATES:")
    for s in seeded:
        L.append(f"  {s['label']:<20} id={s['id']}  text=\"{s['text']}...\"")

    L.append(f"\nREPORT ({elapsed:.1f}s):")
    if "error" in report:
        L.append(f"  ERROR: {report['error']}")
    else:
        for key in ("promoted", "ejected", "held_for_review", "remaining_ring", "still_pending"):
            items = report.get(key)
            if items is not None:
                L.append(f"\n  {key.upper()} ({len(items)}):")
                for e in items:
                    moon_v = e.get("moon_verdict", "") or ""
                    reject_r = e.get("reject_reason", "") or ""
                    score = e.get("score_breakdown", "")
                    L.append(f"    {e['id']}  moon={moon_v}  reason={reject_r}")
                    if score:
                        L.append(f"      scores: {score}")
                    L.append(f"      text: \"{e['text'][:200]}\"")

    # Summary line for quick scanning
    if "error" not in report:
        p = len(report.get("promoted", []))
        ej = len(report.get("ejected", []))
        h = len(report.get("held_for_review", []) or [])
        L.append(f"\nSUMMARY: {p} promoted, {ej} ejected, {h} held for review. "
                 f"Moons fired: {'YES' if any(e.get('moon_verdict') for e in report.get('promoted',[])+report.get('ejected',[]) or []) else 'NO (check toggle)'}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print(f"\n{'#' * 72}")
    print(f"# DONE -> {out_path}")
    print("# Toggles were in-memory only; constants.py on disk unchanged.")
    print(f"{'#' * 72}")


if __name__ == "__main__":
    main()
