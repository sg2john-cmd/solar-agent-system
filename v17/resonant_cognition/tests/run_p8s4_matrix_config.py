"""
Resonant Cognition v17 — Phase 8 Segment 4: MOONS × JESTER MATRIX (single config)
==================================================================================

One leg of the 2×2 comparison matrix. Run ONE config at a time so John can keep up and the
context window never blows out. The same 7-session streak scenario is used for ALL four configs,
so the ONLY thing that varies between legs is the moons toggle and/or the jester (comet) toggle —
a clean apples-to-apples, single-variable comparison.

THE 2×2 MATRIX (run each with its own flag set):
    C1  --no-moons --no-comet   baseline (both off)
    C2     --moons --no-comet   isolates the moons effect
    C3  --no-moons    --comet   isolates the jester effect (fires on session 4)
    C4     --moons    --comet   both active at once

THE SCENARIO (identical across all four configs):
    Sessions 1–4 : Q1 repeated ×4  → builds a stagnation streak, so the Jester fires EXACTLY on
                               session 4 (streak > 3 in comet/triggers.py). Same dominant planet.
    Sessions 5–7 : Q2 repeated ×3  → DIFFERENT dominant planet, so the streak must RESET and the
                               Jester must NOT fire again here (it also sits inside its cooldown).

Q1 routes to REBEL #1; Q2 routes to EVERYMAN #1 — a real dominant switch. Both gaps are large
enough (≥0.04) that an identical repeated string's #1 won't flip on embedding wobble, so the
stagnation streak is genuine and stable across sessions 1–4.

WHAT THIS RECORDS PER CONFIG:
    - per-session routing dominant + top-3 weights
    - per-session Phase C verdicts (the downstream signal moons/jester could shift)
    - comet_fired / trigger_id / detail for every session
    - a small verdict matrix + a comet-fire line-up, so the four configs can be diffed side by side

ISOLATION (the non-obvious part — see handoff Observations #1):
    The live chamber calls comet.triggers.evaluate_triggers(), which persists state to its OWN
    module-level constant COMET_STATE_PATH. It does NOT use C.COMET_STATE_FILE. So we monkeypatch
    comet.triggers.COMET_STATE_PATH to a fresh per-config temp file so C1–C4 never leak state into
    each other, and restore it in finally. We also save/restore the two toggles (MOON_HEMISPHERE_ENABLED,
    COMET_TRIGGER_ENABLED) the same way run_complex_chamber_ab.py does — repo left exactly as found.

    Note: with jester ON but no session_number passed to evaluate_triggers from a direct test call,
    random_injection uses true RNG at p=0.02 (non-deterministic). The STAGNATION trigger is what we
    actually expect on session 4; if any other session fires via the ~2% random path, the evidence
    records it explicitly so it isn't mistaken for a stagnation failure.

Outputs (one timestamped file per config into tests/evidence/):
    p8s4_<label>_<ts>.md   — summary + verdict matrix + comet line-up + per-session detail
    (raw stdout is expected to be captured by the caller's redirect if desired)

RUN ONE LEG, e.g.:
    python -X utf8 tests/run_p8s4_matrix_config.py --no-moons --no-comet      # C1 baseline
    python -X utf8 tests/run_p8s4_matrix_config.py     --moons --no-comet     # C2 moons only
    python -X utf8 tests/run_p8s4_matrix_config.py --no-moons    --comet      # C3 jester only
    python -X utf8 tests/run_p8s4_matrix_config.py     --moons    --comet     # C4 both on

Each leg ≈ 7 full A+B+C chambers. Moons OFF ≈ 80–110 s/chamber; moons ON roughly doubles Phase A
cost (one extra lens pair + merge per planet). Expect ~9–25 min per leg depending on the moons flag.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
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


# ─── THE TWO QUESTIONS (verified via embed-only routing probe — different dominants) ──

Q1 = ("I have built a stable, highly predictable life, but I am considering blowing it up to "
      "pursue an idea that has no guarantee of success. How do I know if I'm being courageous or "
      "just recklessly bored?")          # → REBEL dominant (gap ≈ 0.073)

Q2 = ("How do I save money each month without feeling deprived or giving up the things I love most?")
                                        # → EVERYMAN dominant (gap ≈ 0.046)

# 7-session scenario: Q1 ×4 (build streak, jester fires on session 4) then Q2 ×3 (reset).
SESSIONS = [
    (1, Q1), (2, Q1), (3, Q1), (4, Q1),   # same dominant → stagnation accumulates
    (5, Q2), (6, Q2), (7, Q2),            # different dominant → streak resets
]


def compute_routed_weights(question: str) -> dict[str, float]:
    """Genuine per-planet routed weights from a question.

    Computed FRESH each session (not cached across sessions) so the stagnation fingerprint and
    dominant see exactly what the live routing produces on that turn. Routing is deterministic for
    an identical string + fixed orbital seed, so Q1's dominant stays REBEL across sessions 1–4.
    """
    core, planets = routing.load_orbital_state()
    wave_centers = _planet_wave_centers()
    centers = routing.field_centers_for_all(wave_centers, planets)
    pw = routing.per_planet_weights(_embed(question), centers, core.position)
    return {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}


def run_scenario(moons_on: bool, comet_on: bool) -> list[dict]:
    """Run the 7-session scenario with the two toggles forced. Returns per-session records."""
    cc._ensure_names()  # populate _PLANET_NAMES for display.

    C.MOON_HEMISPHERE_ENABLED = bool(moons_on)
    C.COMET_TRIGGER_ENABLED = bool(comet_on)

    print(f"\n{'='*72}")
    print(f"  P8S4 MATRIX CONFIG — Moons {'ON' if moons_on else 'OFF'} | "
          f"Jester (Comet) {'ON' if comet_on else 'OFF'}")
    print(f"  Scenario: Q1 ×4 → Q2 ×3   Model: {cc._get_model_id()}")
    print(f"{'='*72}")

    records = []
    for session_no, q in SESSIONS:
        weights = compute_routed_weights(q)
        ranked = sorted(weights.items(), key=lambda kv: -kv[1])
        top3 = ", ".join(f"{p}={w:.4f}" for p, w in ranked[:3])

        print(f"\n--- [session {session_no}/7] dominant={ranked[0][0]}  (top3: {top3}) ---")
        t0 = time.time()
        combined = cc.run_phase_a_b_c(q, routed_weights=weights)
        dt = round(time.time() - t0, 1)

        verdicts = {pid: r.get("verdict", "UNKNOWN") for pid, r in combined["phase_c"].items()}
        approves = sum(1 for v in verdicts.values() if v == "APPROVE")
        redirects = sum(1 for v in verdicts.values() if v == "REDIRECT")

        records.append({
            "session": session_no,
            "question": q,
            "dominant": ranked[0][0],
            "top3": top3,
            "weights": weights,
            "verdicts": verdicts,
            "approves": approves,
            "redirects": redirects,
            "comet_fired": bool(combined.get("comet_fired", False)),
            "comet_trigger_id": combined.get("comet_trigger_id"),
            "comet_reframe": combined.get("comet_reframe"),
            "time_s": dt,
        })

        cf = "FIRE" if records[-1]["comet_fired"] else "-"
        print(f"    verdicts: APPROVE={approves} REDIRECT={redirects}  comet={cf}  ({dt}s)")

    return records


def comet_lineup(records: list[dict]) -> str:
    """One row per session showing whether the jester fired and on which trigger."""
    rows = ["session  dominant        comet   trigger"]
    for r in records:
        fire = "FIRED" if r["comet_fired"] else "-"
        trig = (r["comet_trigger_id"] or "")[:20]
        rows.append(f"   {r['session']}     {r['dominant']:<14} {fire:<7} {trig}")
    return "\n".join(rows)


def verdict_matrix(records: list[dict]) -> str:
    order = sorted(cc._PLANET_NAMES.keys())
    header = "sess  dominant".ljust(18) + "".join(f"{p[:5].upper():>6}" for p in order)
    rows = [header, "-" * len(header)]
    for r in records:
        row = f"  {r['session']}    {r['dominant']}".ljust(18)
        row += "".join(f"{r['verdicts'].get(p, '?')[0].upper():>6}" for p in order)
        rows.append(row)
    return "\n".join(rows)


def write_markdown(path: str, label: str, records: list[dict], pass_time: float,
                   moons_on: bool, comet_on: bool):
    """Write the per-config evidence summary (markdown, self-contained)."""
    fired_sessions = [r["session"] for r in records if r["comet_fired"]]

    L = [
        "# Phase 8 Segment 4 — Moons × Jester Matrix: " + label,
        "",
        f"**Config:** Moons {'ON' if moons_on else 'OFF'} | "
        f"Jester (Comet) {'ON' if comet_on else 'OFF'}  ",
        f"**Model:** `{cc._get_model_id()}` + `text-embedding-allmini`, LM Studio @ 127.0.0.1:1234  ",
        f"**Scenario:** Q1 (rebel-dominant) ×4 → Q2 (everyman-dominant) ×3 = 7 sessions  ",
        f"**Pass wall time:** {pass_time}s   **Comet fired on:** "
        + (", ".join(str(s) for s in fired_sessions) if fired_sessions else "(no session)"),
        "",
        "## Comet fire line-up",
        "```",
        comet_lineup(records),
        "```",
        "",
        "**Expected:** with jester ON, the Jester fires on **session 4** (stagnation, streak > 3) and "
        "**does NOT fire again on sessions 5–7** after the dominant switches to everyman (streak resets + "
        "cooldown). With jester OFF, no session fires. Any other-session fire is almost certainly the ~2% "
        "`random_injection` path (no session_number passed) and is flagged in the table above.",
        "",
        "## Phase C verdict matrix (downstream signal)",
        "```",
        verdict_matrix(records),
        "```",
        "",
    ]

    # Verdict shift across the dominant switch (Q1 block vs Q2 block) — cheap, meaningful.
    q1_approves = [r["approves"] for r in records if r["session"] <= 4]
    q2_approve = sum(r["approves"] for r in records if r["session"] >= 5) // max(1, len([r for r in records if r["session"] >= 5]))
    L += [
        f"**Approve totals:** Q1 block (sess 1–4): {q1_approves} per session | "
        f"Q2 block (sess 5–7): avg {q2_approve}",
        "",
        "## Per-session detail",
    ]

    for r in records:
        L.append("")
        L.append(f"### Session {r['session']} — dominant `{r['dominant']}` ({r['time_s']}s)")
        L.append(f"- top3: {r['top3']}")
        L.append(f"- verdicts: APPROVE={r['approves']} REDIRECT={r['redirects']}")
        if r["comet_fired"]:
            L.append(f"- **COMET FIRED** — trigger `{r['comet_trigger_id']}`")
            ref = (r["comet_reframe"] or "").strip().replace("\n", " ")
            L.append(f"  - reframe: {ref[:240]}{'…' if len(ref) > 240 else ''}")

    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="P8S4 Moons × Jester matrix — single config leg.")
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument("--moons", action="store_true", help="Moons (MOON_HEMISPHERE_ENABLED) ON")
    m.add_argument("--no-moons", dest="moons", action="store_false")
    cm = ap.add_mutually_exclusive_group(required=True)
    cm.add_argument("--comet", action="store_true", help="Jester/Comet (COMET_TRIGGER_ENABLED) ON")
    cm.add_argument("--no-comet", dest="comet", action="store_false")
    args = ap.parse_args()

    moons_on, comet_on = bool(args.moons), bool(args.comet)
    label = f"moons{'ON' if moons_on else 'OFF'}_jester{'ON' if comet_on else 'OFF'}"

    # ── Isolate comet state to a fresh per-config temp file (the non-obvious part). ──
    import comet.triggers as ct
    real_state_path = ct.COMET_STATE_PATH
    tmp_state = os.path.join(tempfile.gettempdir(), f"comet_p8s4_{label}_{int(time.time())}.json")
    if os.path.exists(tmp_state):
        try:
            os.remove(tmp_state)
        except OSError:
            pass

    # Save original toggles so we can restore the repo exactly as found.
    orig_moons = C.MOON_HEMISPHERE_ENABLED
    orig_comet = C.COMET_TRIGGER_ENABLED

    t_start = time.time()
    try:
        ct.COMET_STATE_PATH = tmp_state  # monkeypatch — evaluate_triggers reads this at call time
        records = run_scenario(moons_on, comet_on)
        pass_time = round(time.time() - t_start, 1)
    finally:
        ct.COMET_STATE_PATH = real_state_path      # restore state path
        C.MOON_HEMISPHERE_ENABLED = orig_moons     # restore toggles (repo as found)
        C.COMET_TRIGGER_ENABLED = orig_comet

    ts = time.strftime("%Y%m%d_%H%M%S")
    ev = os.path.join(_HERE, "evidence")
    md_path = os.path.join(ev, f"p8s4_{label}_{ts}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(write_markdown(md_path, label, records, pass_time, moons_on, comet_on))

    n_fire = sum(1 for r in records if r["comet_fired"])
    print("\n" + "=" * 72)
    print(f"DONE. {label} — {pass_time}s | comet fired on "
          f"{[r['session'] for r in records if r['comet_fired']] or 'no session'}")
    print(f"  Evidence: {md_path}")
    print("=" * 72)

    # Restore temp state file cleanup (best effort).
    try:
        if os.path.exists(tmp_state):
            os.remove(tmp_state)
    except OSError:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
