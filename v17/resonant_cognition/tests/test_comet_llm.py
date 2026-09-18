"""
Resonant Cognition v17 — Phase 3 Segment (FINAL): Comet B→C LLM-Half Test
=========================================================================

CONCRETE EVIDENCE for proof-of-concept. This is the LAST piece of Phase 3: it proves
the COMET's contrarian reframe actually appears END-TO-END with REAL routing and REAL
chamber runs — not just in a pure-logic unit test (that was test_comet_trigger.py).

WHAT WE ARE PROVING (from John): "once is fluke, twice coincidence, three times pattern."
So we drive the SAME dominant planet for THREE consecutive real sessions and check that
the comet fires exactly on the 3rd one — then proves a DIFFERENT-dominant question does
NOT fire. Every scenario runs against the live LM Studio model (real LLM calls).

THE COMET, in plain terms: it is NOT an 8th planet. It is one injected voice. When a
single planet has been the loudest ("dominant") for N straight sessions, the comet adds
ONE short contrarian reframe, which gets folded into EVERY planet's Phase C (Superego)
review context so each voice judges its Ego proposal with that poke present.

SCENARIOS (all use REAL routed weights computed from the question):
  - SAGE RUN   x3 : "solve this differential equation..." -> routing makes SAGE dominant.
                    Sessions 1,2: no fire. Session 3: FIRES exactly here.
  - EVERYMAN x1   : "how do I save money each month...?" -> routing makes EVERYMAN dominant.
                    A DIFFERENT planet than sage -> streak resets -> must NOT fire.

Both candidates were verified empirically (see scratch probe) to be deterministic and
stable across repeated embed calls, so the streak can build reliably for repeatable logs.

REQUIRES: LM Studio running with both the embedding model AND a main chat model loaded.

RUN:  python -X utf8 tests/test_comet_llm.py
"""

from __future__ import annotations

import os
import sys
import time
import tempfile

# Tests live in tests/ — parent dir has the modules.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)  # resonant_cognition/
if _PARENT not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _PARENT)

import constants as C
import cognitive_chamber as cc
import routing
from collapse import _planet_wave_centers
from resonance import embed as _embed

# ─── TEST COUNTERS ──────────────────────────────────────────────────────────

_passed = 0
_failed = 0


def _check(name: str, condition: bool, detail: str = ""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  ✓ {name}" + (f"  ({detail})" if detail else ""))
    else:
        _failed += 1
        print(f"  ✗ FAIL: {name}" + (f"  ({detail})" if detail else ""))


# ─── SCENARIO CONSTANTS ─────────────────────────────────────────────────────

SAGE_QUESTION = "solve this differential equation: dy/dx = 3y + x, with y(0) = 1."
EVERYMAN_QUESTION = (
    "how do I save money each month without feeling deprived or cutting out things I love?"
)

SAGE_RUNS = 3          # must build a streak to 3 so the comet fires on run 3.


# ─── REAL ROUTED WEIGHTS (mirror routing.routed_collapse's internal snippet) ──

def compute_routed_weights(question: str) -> dict[str, float]:
    """Compute genuine per-planet routed weights from a question — exactly what
    routing.routed_collapse() does internally before it runs collapse. We only need the
    weights (for the dominant planet + loudness), NOT the full collapse output, so this
    is lighter and avoids re-running wave math twice."""
    core, planets = routing.load_orbital_state()
    wave_centers = _planet_wave_centers()
    centers = routing.field_centers_for_all(wave_centers, planets)
    pw = routing.per_planet_weights(_embed(question), centers, core.position)
    return {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}


def dominant_of(weights: dict[str, float]) -> str | None:
    """Highest-weight planet (the comet's notion of 'dominant')."""
    if not weights:
        return None
    return max(weights, key=lambda k: weights[k])


# ─── STATE ISOLATION ────────────────────────────────────────────────────────

def _isolated_comet_state_path() -> str:
    """Point the comet state at a throwaway file so we NEVER clobber any real state.
    run_phase_a_b_c() calls check_comet_trigger with no path arg, which falls back to the
    global C.COMET_STATE_FILE — so we temporarily swap that global for a temp path."""
    fd, tmp = tempfile.mkstemp(prefix="comet_state_llmtest_", suffix=".json")
    os.close(fd)
    try:
        os.remove(tmp)   # start clean; the chamber will create it on first save.
    except OSError:
        pass
    return tmp


# ─── RUN ONE REAL SESSION (full A+B+C, comet toggle ON) ─────────────────────

def run_session(question: str) -> dict:
    """One full live chamber run with REAL routed weights and the comet toggle forced on."""
    weights = compute_routed_weights(question)
    print(f"   dominant planet this session: {dominant_of(weights)}  "
          f"(top3: {sorted(((p, round(w,4)) for p,w in weights.items()), key=lambda kv:-kv[1])[:3]})")
    combined = cc.run_phase_a_b_c(question, routed_weights=weights)
    return combined


# ─── MAIN ───────────────────────────────────────────────────────────────────

def main() -> int:
    global _passed, _failed

    print("=" * 64)
    print("COMET B→C — LLM-HALF TEST (end-to-end, live LM Studio)")
    print(f"Model under test: {cc._get_model_id()}")
    print("=" * 64)

    # Pre-flight sanity: confirm the two scenarios really route to DIFFERENT dominants.
    sage_w = compute_routed_weights(SAGE_QUESTION)
    evm_w = compute_routed_weights(EVERYMAN_QUESTION)
    print(f"\n[PRE-FLIGHT] SAGE question dominant  -> {dominant_of(sage_w)}")
    print(f"[PRE-FLIGHT] EVERYMAN question dom.   -> {dominant_of(evm_w)}")

    _check("Pre-flight: the two scenario questions route to DIFFERENT dominants",
           dominant_of(sage_w) != dominant_of(evm_w),
           f"sage_q={dominant_of(sage_w)}, everyman_q={dominant_of(evm_w)}")

    # Isolate comet state + force the toggle ON for this whole test.
    tmp_state = _isolated_comet_state_path()
    original_state_file = C.COMET_STATE_FILE
    original_enabled = getattr(C, "COMET_TRIGGER_ENABLED", False)
    C.COMET_STATE_FILE = tmp_state
    C.COMET_TRIGGER_ENABLED = True
    try:
        # ── SAGE x3 : build a streak so the comet fires EXACTLY on run 3 ──────────
        print("\n" + "=" * 64)
        print(f"SAGE RUNS ({SAGE_RUNS} consecutive same-dominant sessions)")
        print("=" * 64)

        fired_flags: list[bool] = []
        refrares: list[str | None] = []
        phase_c_runs: list[dict[str, dict]] = []
        for i in range(1, SAGE_RUNS + 1):
            print(f"\n── SAGE run {i}/{SAGE_RUNS} ──")
            combined = run_session(SAGE_QUESTION)
            fired_flags.append(bool(combined["comet_fired"]))
            refrares.append(combined["comet_reframe"])
            phase_c_runs.append(combined["phase_c"])

        # TEST 1: fires exactly on the 3rd session (not on 1 or 2).
        print("\nTEST 1 — Comet fires EXACTLY on the 3rd consecutive same-dominant session")
        _check("Session 1 did NOT fire", fired_flags[0] is False, f"fired={fired_flags[0]}")
        _check("Session 2 did NOT fire", fired_flags[1] is False, f"fired={fired_flags[1]}")
        _check("Session 3 DID fire", fired_flags[2] is True, f"fired={fired_flags[2]}")

        # TEST 2: when it fires, the contrarian reframe is a non-empty string.
        print("\nTEST 2 — Fired session produced a non-empty contrarian reframe")
        _check("comet_reframe on run 3 is a non-empty string",
               isinstance(refrares[2], str) and len(refrares[2].strip()) > 0,
               f"len={len((refrares[2] or '').strip())}")

        # TEST 3: the injected voice did NOT break Superego parsing on any run.
        print("\nTEST 3 — Injected comet voice does not break Phase C verdicts (all runs)")
        bad = 0
        for i, pc in enumerate(phase_c_runs, start=1):
            if len(pc) != 7:
                bad += 1
            for pid, r in pc.items():
                if r.get("verdict") not in ("APPROVE", "REDIRECT"):
                    bad += 1
        total_verdicts = sum(len(pc) for pc in phase_c_runs)
        _check(f"All {total_verdicts} Phase C verdicts across 3 runs stayed valid (no UNKNOWN)",
               bad == 0, f"{bad} malformed")

        # TEST 4: a DIFFERENT-dominant question does NOT fire (streak reset works live).
        print("\nTEST 4 — Different-dominant session does NOT fire (live streak reset)")
        combined_evm = run_session(EVERYMAN_QUESTION)
        _check("EVERYMAN-dominant session did NOT fire",
               bool(combined_evm["comet_fired"]) is False,
               f"fired={combined_evm['comet_fired']}")

    finally:
        # Restore globals + clean up the temp state file.
        C.COMET_STATE_FILE = original_state_file
        C.COMET_TRIGGER_ENABLED = original_enabled
        try:
            os.remove(tmp_state)
        except OSError:
            pass

    # ─── SUMMARY ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 64)
    total = _passed + _failed
    print(f"COMET LLM-HALF RESULT: {_passed}/{total} checks passed, {_failed} failed")
    print("=" * 64)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
