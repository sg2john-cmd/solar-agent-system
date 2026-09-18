"""
Resonant Cognition v17 — Phase 3 Segment: Moon-Hemisphere Two-Lens Framing (LLM)
=================================================================================

CONCRETE EVIDENCE for proof-of-concept of the MOON toggle. When MOON_HEMISPHERE_ENABLED
is ON, each planet's Phase A "Id fires" runs THREE live LLM calls instead of one:
  - LEFT lens   -> raw Id framed RATIONALLY (the analytic/structural side)
  - RIGHT lens  -> raw Id framed INTUITIVELY (the felt/affective side)
  - MERGE       -> weaves the two lenses into ONE coherent raw-Id response.

We are proving, with REAL routed weights + the live model:
  (1) The pipeline stays STABLE in moons mode — all 7 planets produce a non-empty merged
      Id response every run (no crashes, no blank outputs). This is the safety net that
      matters most before we ever leave this toggle off-by-default.
  (2) The two lenses are actually DIFFERENT from each other for at least some planets —
      i.e. the split is producing genuinely distinct sub-perspectives, not just echoing one
      line twice. (Soft check: a meaningful fraction of the 7 planets have LEFT != RIGHT.)
  (3) The MERGE is not an echo of either single lens — for at least some planets it differs
      from BOTH raw lenses (proof the weave step did real work, not just copied input).
  (4) Anti-silence invariant still holds in moons mode: every one of the 7 has a voice.

"Once is fluke, twice coincidence, three times pattern." -> each scenario runs THREE times;
we average lens-divergence across the 3x7=21 planet-instances and require a stable majority.

REQUIRES: LM Studio running with both the embedding model AND a main chat model loaded.

RUN:  python -X utf8 tests/test_phase_a_moons.py
"""

from __future__ import annotations

import os
import sys

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

QUESTION = ("I'm trying to decide whether to take a risk on a new project, "
            "but I keep freezing when the stakes feel high.")

RUNS = 3   # three full moons-mode Phase A runs.


def compute_routed_weights(question: str) -> dict[str, float]:
    """Genuine per-planet routed weights from a question (mirror of routing internals)."""
    core, planets = routing.load_orbital_state()
    wave_centers = _planet_wave_centers()
    centers = routing.field_centers_for_all(wave_centers, planets)
    pw = routing.per_planet_weights(_embed(question), centers, core.position)
    return {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}


# ─── LENS DIVERGENCE (soft, temperature-tolerant) ──────────────────────────

def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def run_moons_phase_a(question: str, weights: dict[str, float]) -> tuple[dict, dict]:
    """Run ONE moons-mode Phase A. We need the two RAW lenses per planet too (to compare
    them), but cc.phase_a_id_fires only returns the merged response. So we reproduce the
    exact 3-call sequence it uses — same prompts, same model — and keep all three outputs."""
    cfgs = cc._load_all_planet_configs()
    out_merged: dict[str, str] = {}
    out_lens: dict[str, tuple[str, str]] = {}
    for pid in sorted(cfgs.keys()):
        cfg = cfgs[pid]
        w = weights.get(pid, 0.5)
        temp = cfg.get("cognitive_mode", {}).get("temperature", 0.7)
        left_messages = cc._build_lens_prompt(cfg, question, w, "LEFT")
        right_messages = cc._build_lens_prompt(cfg, question, w, "RIGHT")
        left_text = cc._llm_chat_cached(left_messages, temperature=temp,
                                        max_tokens=getattr(C, "MOON_LENS_MAX_TOKENS", 192))
        right_text = cc._llm_chat_cached(right_messages, temperature=temp,
                                         max_tokens=getattr(C, "MOON_LENS_MAX_TOKENS", 192))
        merge_messages = cc._build_merge_prompt(cfg, question, left_text, right_text)
        merged_text = cc._llm_chat_cached(merge_messages, temperature=temp,
                                          max_tokens=getattr(C, "MOON_MERGE_MAX_TOKENS", 512))
        out_merged[pid] = merged_text
        out_lens[pid] = (left_text, right_text)
    return out_merged, out_lens


def main() -> int:
    global _passed, _failed

    print("=" * 64)
    print("MOON-HEMISPHERE TWO-LENS FRAMING — LLM TEST (live LM Studio)")
    print(f"Model under test: {cc._get_model_id()}")
    print("=" * 64)

    cc._ensure_names()   # populate _PLANET_NAMES for display
    weights = compute_routed_weights(QUESTION)
    dom = max(weights, key=weights.get)
    top3 = sorted(((p, round(w, 4)) for p, w in weights.items()), key=lambda kv: -kv[1])[:3]
    print(f"\nQuestion: \"{QUESTION}\"")
    print(f"Routing dominant: {dom}   top3: {top3}")

    # Force the moon toggle ON for this whole test; restore afterwards.
    original = getattr(C, "MOON_HEMISPHERE_ENABLED", False)
    C.MOON_HEMISPHERE_ENABLED = True
    try:
        merged_runs: list[dict[str, str]] = []
        distinct_lens_total = 0   # how many of the (3 runs x 7 planets) have LEFT != RIGHT
        non_echo_merge_total = 0  # how many merges differ from BOTH raw lenses
        total_instances = 0

        for i in range(1, RUNS + 1):
            print(f"\n── MOONS Phase A run {i}/{RUNS} ──")
            merged, lens = run_moons_phase_a(QUESTION, weights)
            merged_runs.append(merged)
            total_instances += len(merged)

            for pid in sorted(lens.keys()):
                left_t, right_t = lens[pid]
                if _norm(left_t) != _norm(right_t):
                    distinct_lens_total += 1
                m = _norm(merged.get(pid, ""))
                if m and m != _norm(left_t) and m != _norm(right_t):
                    non_echo_merge_total += 1

            for pid in sorted(merged.keys()):
                preview = merged[pid][:80].replace("\n", " ")
                print(f"   {cc._PLANET_NAMES.get(pid, pid):<12} [moons] | {preview}...")
    finally:
        C.MOON_HEMISPHERE_ENABLED = original

    # TEST 1 — pipeline stability in moons mode (all-7 non-empty every run).
    print("\nTEST 1 — Pipeline Stability in Moons Mode (all-7 merged, non-empty)")
    bad = 0
    for mr in merged_runs:
        if len(mr) != 7:
            bad += 1
        for pid, txt in mr.items():
            if not _norm(txt):
                bad += 1
    _check(f"All {total_instances} moons-mode Id responses across {RUNS} runs were non-empty",
           bad == 0, f"{bad} blank/missing")

    # TEST 2 — lenses are distinct (soft: majority of instances LEFT != RIGHT).
    print("\nTEST 2 — The Two Lenses Are Distinct (split is not just echoing one line)")
    frac_lens = distinct_lens_total / max(total_instances, 1)
    _check("Majority of lens pairs differ (LEFT != RIGHT)",
           frac_lens >= 0.5, f"{distinct_lens_total}/{total_instances} distinct ({frac_lens:.0%})")

    # TEST 3 — merge is not an echo of either raw lens (soft: majority).
    print("\nTEST 3 — Merge Is Not An Echo Of Either Single Lens (weave did real work)")
    frac_merge = non_echo_merge_total / max(total_instances, 1)
    _check("Majority of merges differ from BOTH raw lenses",
           frac_merge >= 0.5, f"{non_echo_merge_total}/{total_instances} non-echo ({frac_merge:.0%})")

    # TEST 4 — anti-silence: every run has all 7 voices present (no planet dropped).
    print("\nTEST 4 — Anti-Silence Invariant Holds in Moons Mode (all 7 have a voice each run)")
    all_seven = all(len(mr) == 7 for mr in merged_runs)
    _check("Every moons-mode run produced exactly 7 planet responses",
           all_seven, f"runs with 7 = {sum(1 for mr in merged_runs if len(mr)==7)}/{RUNS}")

    # ─── SUMMARY ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 64)
    total = _passed + _failed
    print(f"MOONS LLM RESULT: {_passed}/{total} checks passed, {_failed} failed")
    print("=" * 64)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
