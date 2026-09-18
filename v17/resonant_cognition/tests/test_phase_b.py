"""
Resonant Cognition v17 — Phase 3 Segment 2: Test Suite (Phase B "Ego Synthesis")
================================================================================

CONCRETE EVIDENCE for proof-of-concept. The whole POINT of Phase B is that each
planet now READS the other six planets' raw Id responses and responds TO THEM by
name — this is where constructive/destructive interference becomes visible in text,
rather than being abstracted into a single "winning" answer.

Every check here exists to prove one thing: the group actually talked to each other.

REQUIRES: LM Studio running with both the embedding model AND a main chat model loaded.

RUN:  python -X utf8 tests/test_phase_b.py
"""

from __future__ import annotations

import os
import sys
import time

# Tests live in tests/ — parent dir has the modules.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)  # resonant_cognition/
if _PARENT not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _PARENT)

import cognitive_chamber as cc

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


# ─── SHARED: one A+B run, reused across tests to keep LLM cost down ─────────

def _run_once(question: str) -> dict:
    return cc.run_phase_a_b(question)


def _name_of(pid: str) -> str:
    """Lowercased archetype display name for a planet id (e.g. 'Caregiver')."""
    cfgs = cc._load_all_planet_configs()
    return cfgs.get(pid, {}).get("archetype_name", pid.title()).lower()


def _mentions_other(own_pid: str, text: str) -> list[str]:
    """Return the OTHER planet names that appear in `text` (case-insensitive).

    We deliberately do NOT require exact display-name spelling — planets are told to
    name people by name but may use their archetype noun. We match on the id stem as
    a fallback too, so 'hero' counts even if rendered 'Hero'.
    """
    text_lower = text.lower()
    others: list[str] = []
    for pid in cc._load_all_planet_configs().keys():
        if pid == own_pid:
            continue
        display = _name_of(pid)
        # Match either the display name or the raw id stem.
        if (display and display.split()[0] in text_lower) or (pid in text_lower):
            others.append(display)
    return others


# ─── TEST A: ALL-7-EMIT INVARIANT HOLDS IN PHASE B TOO ─────────────────────

def test_all_seven_emit_in_b(combined: dict):
    """INVARIANT carried from Phase A: no planet goes silent in the synthesis round.
    Even a 'peripheral' voice must still speak once it has heard the group."""
    print("\nTEST A — All-Seven-Emit Invariant (Phase B)")
    phase_b = combined["phase_b"]

    expected_ids = {"caregiver", "everyman", "hero", "magician", "rebel", "ruler", "sage"}
    got_ids = set(phase_b.keys())
    _check("Exactly 7 planets returned in Phase B", len(phase_b) == 7, f"got {len(phase_b)}")
    _check("All expected planet IDs present in Phase B", got_ids == expected_ids,
           f"missing={expected_ids - got_ids}")

    for pid in sorted(expected_ids):
        r = phase_b.get(pid)
        if r is None:
            _check(f"{pid} present in B", False, "MISSING")
            continue
        ok = not r.get("error", False) and len(r["response"].strip()) >= 20
        _check(f"B/{pid}: responded without error and ≥20 chars", ok,
               f"{len(r['response'])} chars")


# ─── TEST B: PLANETS ACTUALLY READ EACH OTHER (the core claim) ─────────────

def test_planets_reference_each_other(combined: dict):
    """THE acceptance criterion for Ego Synthesis. At least 5 of 7 Phase B responses
    must name at least ONE other planet by name. If this is low, the planets are
    just re-stating their Id and ignoring the transcript — which defeats the whole point."""
    print("\nTEST B — Planets Reference Each Other By Name (core claim)")

    refs_found = 0
    for pid in sorted(combined["phase_b"].keys()):
        text = combined["phase_b"][pid]["response"]
        others = _mentions_other(pid, text)
        if len(others) >= 1:
            refs_found += 1
        print(f"      {pid:<10} mentions {len(others)} other(s): {', '.join(sorted(set(others))) or '—'}")

    _check("At least 5/7 planets named another planet", refs_found >= 5, f"{refs_found}/7 did")
    # Stronger signal: the group is a real dialogue if at least one planet names TWO+ others.
    multi_refs = sum(1 for pid in combined["phase_b"]
                     if len(_mentions_other(pid, combined["phase_b"][pid]["response"])) >= 2)
    _check("At least 1 planet engaged with 2+ others (multi-voice dialogue)", multi_refs >= 1,
           f"{multi_refs} planets named ≥2 others")


# ─── TEST C: PHASE B IS NOT JUST A COPY OF PHASE A ─────────────────────────

def test_b_is_not_a_copy_of_a(combined: dict):
    """A lazy model might just re-emit its Id response in Phase B. If a planet's
    Phase B text is nearly identical to its Phase A text, it did NOT engage the group."""
    print("\nTEST C — Phase B Differs From Phase A (engagement, not parrot)")

    near_identical = 0
    for pid in combined["phase_a"]:
        a = combined["phase_a"][pid]["response"].strip().lower()
        b = combined["phase_b"][pid]["response"].strip().lower()
        if not a or not b:
            continue
        # Jaccard over word sets — robust to ordering, catches "same words re-shuffled".
        set_a, set_b = set(a.split()), set(b.split())
        union = len(set_a | set_b) or 1
        overlap = len(set_a & set_b) / union
        if overlap > 0.7:
            near_identical += 1
    _check("No planet simply re-emitted its Phase A text (>70% word overlap)",
           near_identical == 0, f"{near_identical} planets were near-identical")


# ─── TEST D: AGREE / PUSH-BACK LANGUAGE IS PRESENT (interference in prose) ──

def test_agreement_and_pushback_language(combined: dict):
    """Constructive vs destructive interference should show up as AGREEMENT or
    PUSHBACK verbs. We expect the group to contain BOTH — some alignment, some tension."""
    print("\nTEST D — Agreement AND Push-Back Language Present")

    agree_markers = ["agree", "align", "echo", "resonate", "validat", "right that",
                     "stand by", "stand harder", "back you up", "you're right"]
    push_markers  = ["push back", "disagree", "counterweight", "harden", "hardening",
                     "but i", "however", "refine", "qualify", "resist", "against"]

    agree_hits = 0
    push_hits = 0
    for r in combined["phase_b"].values():
        t = r["response"].lower()
        if any(m in t for m in agree_markers):
            agree_hits += 1
        if any(m in t for m in push_markers):
            push_hits += 1

    _check("Agreement language present (constructive resonance)", agree_hits >= 2, f"{agree_hits}/7")
    _check("Push-back / tension language present (destructive interference)", push_hits >= 2,
           f"{push_hits}/7")


# ─── TEST E: TIMING BUDGET FOR FULL A+B ON THE 4090 ────────────────────────

def test_timing_budget_a_b(combined: dict):
    """Full A+B = 14 sequential LLM calls. Budget is generous (300s) — this exists to
    catch a pathological slowdown, not to be tight. We already observed ~44s."""
    print("\nTEST E — Full A+B Timing (<300s budget)")
    total = combined.get("total_time_s", 0)
    _check(f"Full A+B completed in {total:.1f}s (<300s)", total < 300, f"{total:.1f}s")


# ─── RUNNER ────────────────────────────────────────────────────────────────

def main():
    print("=" * 64)
    print("PHASE 3 SEGMENT 2 — TEST SUITE (Phase B: Ego Synthesis)")
    print(f"Model endpoint: {cc.C.LM_STUDIO_HOST}:{cc.C.LM_STUDIO_PORT}")
    print("=" * 64)

    t_start = time.time()

    # One A+B run feeds every test — keeps LLM cost to a single cycle.
    combined = _run_once("What should I do when I feel stuck and can't see the way forward?")

    test_all_seven_emit_in_b(combined)
    test_planets_reference_each_other(combined)
    test_b_is_not_a_copy_of_a(combined)
    test_agreement_and_pushback_language(combined)
    test_timing_budget_a_b(combined)

    total_time = time.time() - t_start

    print(f"\n{'='*64}")
    print(f"RESULTS: {_passed} passed, {_failed} failed  ({total_time:.1f}s wall)")
    print(f"{'='*64}")

    if _failed == 0:
        print("✅ ALL TESTS PASS — Phase B (Ego Synthesis) is solid. The group talked to each other.")
    else:
        print(f"⚠️ {_failed} test(s) FAILED — review output above.")

    return _failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
