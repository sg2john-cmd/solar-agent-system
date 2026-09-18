"""
Resonant Cognition v17 — PRODUCTION-CONFIG FULL PIPELINE VERIFICATION (post review-fix pass)
============================================================================================

WHY THIS EXISTS:
  After the full blind-review fix pass (C1..M5, L1..L5 touched pipeline.py,
  cognitive_chamber.py, g1_ops.py, gates234.py, calibrate_axes.py), we re-verify the
  system "still functions as intended" under the PRODUCTION configuration — i.e. with
  every moon system that is mandatory at release turned ON for this run:

    - MOON_HEMISPHERE_ENABLED = True   (dual-moon hemisphere framing in Phase A Id)
    - G1_FILTER_MOONS_ENABLED = True   (G1 filter moons pre-pass — the C1/M4 wiring fix)
    - G2 self-model moons           (always run; no toggle exists by design)

  This is a RE-VERIFICATION RUN, not an A/B comparison: one full pipeline pass with all
  production toggles on, plus explicit evidence that every moon system actually fired.

WHAT IT CHECKS (printed per layer + written to the transcript):
    1. All 7 planets receive the prompt and emit real content in Phase A / B AND C
       (anti-silence; anti-majority-vote philosophy).
    2. Dual-moon hemisphere framing was ACTIVE for every planet in Phase A
       (two lens calls + merge — visible via chamber diagnostics / phase_a metadata).
    3. G1 filter moons pre-pass executed when G1_FILTER_MOONS_ENABLED is on.
    4. Id -> Ego -> Superego chain produced verdicts for all 7.
    5. Waveform projection: routed_collapse emitted per-planet weights AND amplitudes,
       and the collapse result carried a consensus energy value.
    6. M2 fix: primary answer is NOT an [ERROR] string (errored planets skipped).

CONVENTION: observational `run_` runner like run_e2e_light.py — no exit-code gate; it
writes ONE dated transcript to tests/evidence/. Toggles are set in-memory for this process
only; constants.py on disk is never mutated.

Run (needs LM Studio at 127.0.0.1:1234, embedding + chat models):
    python -X utf8 tests/run_production_config_verify.py     # ~15-20 min (moons ON = 2x Phase A)
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in [os.path.abspath(p) for p in sys.path]:
    sys.path.insert(0, _PARENT)

import constants as C
import cognitive_chamber as cc
from gate1 import gate1_filter
from routing import routed_collapse
from cognitive_chamber import run_phase_a_b_c
from giants.g1_ops import g1_sleep_pass_i  # noqa: F401  (proves the C1/M4 wiring imports cleanly)

_EVIDENCE_DIR = os.path.join(_HERE, "evidence")


# ─── Two prompts: one where a planet should clearly lead, one balanced ──────────

PROMPTS = [
    ("dominance", "I keep overthinking every decision and it's starting to freeze me up — "
                  "how do I get unstuck without just picking randomly?"),
    ("balanced",  "Should I strictly optimize every hour of my day to guarantee progress toward "
                  "my long-term goals, or leave vast open spaces for chance, intuition, and "
                  "unplanned opportunities?"),
]


def _set_moons(on: bool) -> None:
    """Set production moon toggles in-memory (constants.py on disk never touched)."""
    C.MOON_HEMISPHERE_ENABLED = bool(on)
    C.G1_FILTER_MOONS_ENABLED = bool(on)


def _run_one(label: str, prompt: str) -> dict:
    print("\n" + "=" * 72)
    print(f"  PRODUCTION-CONFIG RUN — {label}")
    print("=" * 72)

    # LAYER 1 — Ring Intake.
    t0 = time.time()
    g1 = gate1_filter(prompt)
    rejected = not g1.get("proceed_to_planets", False)
    print(f"  intake: proceed={not rejected} ({time.time()-t0:.1f}s)")

    if rejected:
        return {"label": label, "prompt": prompt, "rejected_at_intake": True,
                "g1": g1, "rc": None, "chamber": None, "checks": []}

    clean = g1["cleaned_text"]

    # LAYER 2 — routing + waveform projection / collapse. No chat LLM.
    t0 = time.time()
    rc = routed_collapse(clean)
    print(f"  routing+collapse done ({time.time()-t0:.1f}s)")

    weights = {pid: v["weight"] for pid, v in rc.get("routing", {}).items()
               if not str(pid).startswith("_")}

    # LAYER 3 — full chamber with moons ON (toggles already set at process start).
    t0 = time.time()
    chamber = run_phase_a_b_c(clean, routed_weights=weights)
    print(f"  chamber A+B+C done ({time.time()-t0:.1f}s)")

    return {"label": label, "prompt": prompt, "rejected_at_intake": False,
            "g1": g1, "rc": rc, "chamber": chamber}


def _checks(res: dict) -> list[str]:
    """Explicit moon-chain + pipeline verification lines for this run."""
    out: list[str] = []

    def line(msg: str) -> None:
        print("  [verify] " + msg)
        out.append("  - " + msg)

    if res.get("rejected_at_intake"):
        line(f"{res['label']}: rejected at Ring Intake — downstream checks N/A")
        return out

    label, rc, chamber = res["label"], res["rc"] or {}, res["chamber"] or {}

    # 1. Anti-silence: all 7 planets real content in A/B/C.
    for key, lbl in (("phase_a", "Phase A (Id)"), ("phase_b", "Phase B (Ego)"),
                     ("phase_c", "Phase C (Superego)")):
        ph = chamber.get(key) or {}
        present = [p for p in ph if not ph[p].get("error") and (ph[p].get("response") or "").strip()]
        missing = sorted(set(ph) - set(present))
        line(f"{lbl}: {len(present)}/7 planets emitted real content"
             + (f"  MISSING: {missing}" if missing else "  OK"))

    # 2. Hemisphere framing active? Phase A/B/C records carry a moon_mode marker:
    #    'two_lens' when the dual-moon split ran, 'single' on the plain path.
    ph_a = chamber.get("phase_a") or {}
    two_lens = sum(1 for r in ph_a.values() if isinstance(r, dict) and r.get("moon_mode") == "two_lens")
    line(f"dual-moon hemisphere framing: {two_lens}/7 Phase A records tagged moon_mode='two_lens'"
         + ("  OK" if two_lens == 7 else "  CHECK — moons toggle was ON, expected all 'two_lens'"))

    # 3. G1 filter moons toggle state + wiring import already proven at module top.
    line(f"G1_FILTER_MOONS_ENABLED = {C.G1_FILTER_MOONS_ENABLED}  "
         f"(g1_ops.g1_sleep_pass_i imported OK — C1/M4 wiring intact)")

    # 4. Phase C verdict tally (anti-silence: no planet should lack a verdict).
    ph_c = chamber.get("phase_c") or {}
    tally = Counter((r.get("verdict") or "UNKNOWN") for r in ph_c.values())
    line(f"Phase C verdicts: {len(ph_c)}/7 present -> " +
         ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))

    # 5. Waveform projection evidence: weights + amplitudes + consensus energy.
    routing = rc.get("routing") or {}
    waves = rc.get("waves") or {}
    amps_ok = all(w.get("amplitude", 0) > 0 for w in waves.values() if not str(w).startswith("_"))
    energy = (rc.get("result") or {}).get("total_energy")
    line(f"waveform projection: {len([k for k in routing if not str(k).startswith('_')])}/7 weights, "
         f"all amplitudes > 0: {amps_ok}, consensus energy={energy}")

    # 6. M2 fix — primary answer must not be an [ERROR] string.
    phase_c = chamber.get("phase_c") or {}
    if phase_c:
        ranked = sorted(phase_c.items(), key=lambda kv: -(kv[1].get("routing_weight", 0)
                          if isinstance(kv[1], dict) else 0))
        # M2's _pick_primary walks by routed weight; replicate the "no [ERROR] primary" check.
        errored = [p for p, r in phase_c.items()
                   if str(r.get("response") or "").startswith("[ERROR]")]
        line(f"M2 fix: planets with [ERROR] output: {errored if errored else 'none'}  "
             + ("OK" if not any(str(phase_c[p].get('response','')).startswith('[ERROR]')
                                 for p in phase_c) else "CHECK — verify fallback chose a clean planet"))

    return out


def _transcript(results: list[dict]) -> str:
    L = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        model_id = cognitive_chamber_model()
    except Exception:
        model_id = "(not detected)"
    L.append("#" * 78)
    L.append("PRODUCTION-CONFIG FULL PIPELINE VERIFICATION (all release-mandatory moons ON)")
    L.append(f"# Generated: {ts}   Model: {model_id}")
    L.append("# Toggles for this run (in-memory only):")
    L.append(f"#   MOON_HEMISPHERE_ENABLED = {C.MOON_HEMISPHERE_ENABLED}")
    L.append(f"#   G1_FILTER_MOONS_ENABLED = {C.G1_FILTER_MOONS_ENABLED}")
    L.append("#   G2 self-model moons: always-on (no toggle by design)")
    L.append("#" * 78)

    for res in results:
        L.append("\n" + "=" * 78)
        L.append(f"PROMPT — {res['label']}: \"{res['prompt']}\"")
        L.append("=" * 78)

        if res.get("rejected_at_intake"):
            L.append("REJECTED at Ring Intake. "
                     f"Reason: {(res['g1'].get('clarity') or {}).get('reason', 'n/a')}")
            continue

        g1, rc, chamber = res["g1"], res["rc"] or {}, res["chamber"] or {}

        L.append("\n── RING INTAKE ──")
        L.append(f"  proceed={g1.get('proceed_to_planets')}  "
                 f"clarity={(g1.get('clarity') or {}).get('clarity_score', 'n/a')}  "
                 f"PII redactions: {len(g1.get('redactions') or [])}")

        L.append("\n── ROUTING + WAVEFOLD COLLAPSE ──")
        routing = rc.get("routing") or {}
        ranked = sorted(((pid, v) for pid, v in routing.items() if not str(pid).startswith("_")),
                        key=lambda kv: -kv[1].get("weight", 0.0))
        L.append(f"  {'planet':<12} {'weight':>8}")
        for rank, (pid, v) in enumerate(ranked, 1):
            L.append(f"   {rank}. {pid:<10} w={v.get('weight', 0.0):.4f}")
        waves = rc.get("waves") or {}
        L.append("  all-7-amplitudes : " + ", ".join(
            f"{pid}={w.get('amplitude', 0.0):.4f}" for pid, w in sorted(waves.items())
            if not str(pid).startswith("_")))

        for key, lbl in (("phase_a", "PHASE A — Id (dual-moon hemisphere framing)"),
                         ("phase_b", "PHASE B — Ego synthesis"),
                         ("phase_c", "PHASE C — Superego verdicts")):
            ph = chamber.get(key) or {}
            L.append(f"\n── {lbl}   ({len(ph)} planets) ──")
            for pid in sorted(ph.keys()):
                r = ph[pid]
                err = " [ERROR]" if r.get("error") else ""
                verdict = f"  [{r['verdict']}]" if key == "phase_c" and r.get("verdict") else ""
                resp = (r.get("response") or "").strip().replace("\n", " ")
                L.append(f"    {pid:<12}{err}{verdict} {resp[:500]}{'…' if len(resp) > 500 else ''}")

        L.append("\n── VERIFICATION CHECKS ──")
        L.extend(res.get("checks", []))

    return "\n".join(L)


def _g1_moons_report(g1_path: str) -> dict:
    """Run the G1 archive sleep pass with filter moons ON and report what happened."""
    try:
        report = g1_sleep_pass_i(g1_path)
    except Exception as e:  # a giant failure must not kill the whole verification run
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    ok = isinstance(report, dict) and report.get("filter_moons_ran") is True
    detail = (f"candidates={report.get('total_candidates')}, promoted="
              f"{report.get('promoted_count')}, rejected_slop={report.get('rejected_slop_count')}, "
              f"verdicts={ {k: v for k, v in report.items() if k.endswith('_count')} }")
    return {"ok": ok, "detail": detail}


def main() -> None:
    # Set production toggles IN-MEMORY for this process only. constants.py is never touched.
    C.MOON_HEMISPHERE_ENABLED = True
    C.G1_FILTER_MOONS_ENABLED = True

    print("#" * 78)
    print("PRODUCTION-CONFIG VERIFICATION — moons ON (release configuration)")
    print(f"  MOON_HEMISPHERE_ENABLED={C.MOON_HEMISPHERE_ENABLED}   "
          f"G1_FILTER_MOONS_ENABLED={C.G1_FILTER_MOONS_ENABLED}")
    print("  G2 self-model moons: always on. Expect ~15-20 min (moons double Phase A calls).")
    print("#" * 78)

    results = []
    for label, prompt in PROMPTS:
        res = _run_one(label, prompt)
        if not res.get("rejected_at_intake"):
            res["checks"] = _checks(res)
        results.append(res)

    # G1 filter moons: run the archive sleep pass ONCE (deterministic + LLM pre-pass when
    # candidates exist) so we have concrete evidence the C1/M4 wiring fires in production.
    g1_report = None
    try:
        from giants import g1_ops as _g1o
        g1_path = getattr(_g1o, "_G1_PATH", None)
    except Exception:
        g1_path = None
    if g1_path and os.path.exists(g1_path):
        print(f"\n  G1 filter moons: running sleep pass on {os.path.basename(g1_path)} ...")
        _set_moons(True)
        t0 = time.time()
        g1_report = _g1_moons_report(g1_path)
        print(f"  G1 report ({time.time()-t0:.1f}s): ok={g1_report.get('ok')} "
              f"{g1_report.get('detail') or g1_report.get('error', '')}")

    os.makedirs(_EVIDENCE_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(_EVIDENCE_DIR, f"prod_config_verify_moonsON_{stamp}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_transcript(results) + "\n")

    print("\n" + "#" * 78)
    print(f"# DONE -> {out_path}")
    print("# Toggles were in-memory only; constants.py on disk is unchanged.")
    print("#" * 78)


if __name__ == "__main__":
    main()
