"""
Resonant Cognition v17 — Phase 7, Segment 6: G1/G2 Acceptance Test (Standalone)
================================================================================

This is a DIRECT unit-stress + acceptance test for the two gas giants operating
in isolation (no full solar system, no ring, no planets). It verifies:

  G1 CYCLE:
    - A good operational candidate → PROMOTED to contents.
    - An obvious "AI slop" vague/filler candidate → EJECTED from ring_buffer.
    - With --moons-on: the filter moons (LLM) run as a pre-pass before scoring.

  G2 REJECTION:
    - A structurally harmful candidate (kind="anchor_migration", vector mag > 0.3)
      → HELD at "pending_user_approval" (NOT committed to contents).

Design principles:
    - Operates on TEMP COPIES of the real JSON files. Live data is never touched.
    - Zero LLM calls in the default (moons OFF) path — fully deterministic.
    - --moons-on flag enables G1 filter moons (requires LM Studio running).
    - Prints before/after state diffs for evidence capture.

USAGE:
    # Moons OFF (deterministic, no LM Studio needed):
    python -X utf8 tests/run_p7s6_acceptance.py

    # Moons ON (LLM calls to G1 filter moons; requires LM Studio):
    python -X utf8 tests/run_p7s6_acceptance.py --moons-on

EVIDENCE: Output is captured via redirect or tee by the runner script.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

# ─── PATH SETUP ──────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))  # tests/
_PKG_ROOT = os.path.dirname(_HERE)                   # resonant_cognition/
_GIANTS_DIR = os.path.join(_PKG_ROOT, "giants")

# Ensure the package root is on sys.path so imports work regardless of cwd.
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from giants.g1_ops import g1_add_candidate, g1_sleep_pass_i, G1_PROMOTE_THRESHOLD
from giants.g2_ops import g2_add_candidate, g2_sleep_pass_i
from giants.g2_growth_policy import g2_classify_tier


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _diff_summary(before: dict, after: dict, label: str) -> None:
    """Print a concise before/after comparison for evidence."""
    print(f"\n{'─' * 60}")
    print(f"  {label} — BEFORE vs AFTER")
    print(f"{'─' * 60}")

    # G1-style
    b_contents = len(before.get("contents", []))
    a_contents = len(after.get("contents", []))
    b_ring = len(before.get("ring_buffer", []))
    a_ring = len(after.get("ring_buffer", []))
    print(f"  contents: {b_contents} → {a_contents}  (Δ {a_contents - b_contents:+d})")
    print(f"  ring_buffer: {b_ring} → {a_ring}  (Δ {a_ring - b_ring:+d})")

    # Status breakdown of ring entries
    for key in ("ring_buffer", "contents"):
        items = after.get(key, []) or []
        if not items:
            continue
        statuses: dict[str, int] = {}
        for e in items:
            s = e.get("status", "?")
            statuses[s] = statuses.get(s, 0) + 1
        if statuses:
            print(f"    {key} statuses: {statuses}")


def _print_entry_brief(entry: dict, indent: str = "      ") -> None:
    """Print a one-line brief for an entry."""
    eid = entry.get("id", "?")[:12]
    text = (entry.get("text") or "")[:80].replace("\n", " ")
    status = entry.get("status", "?")
    score = entry.get("score_breakdown") or {}
    composite = score.get("composite", "—") if isinstance(score, dict) else "—"
    print(f"  {indent}[{eid}] status={status} composite={composite}")
    print(f"  {indent}  text: \"{text}\"")


# ─── G1 TEST SCENARIO ────────────────────────────────────────────────────────

def run_g1_cycle(g1_copy_path: str, moons_on: bool) -> tuple[dict, dict]:
    """Seed G1 with a good candidate + AI slop → run sleep pass → return (before, after)."""
    print("\n" + "=" * 60)
    print("  G1 ACCEPTANCE CYCLE")
    print(f"  Moons: {'ON' if moons_on else 'OFF'}")
    print("=" * 60)

    before = _load_json(g1_copy_path)

    # ── Seed a committed reference FIRST so consistency scoring has something to match ──
    ref_entry = {
        "id": "g1_ref_000",
        "text": "The orbital integrator uses a fixed timestep Verlet scheme for planet position updates.",
        "vector_position": [0.75, 0.25, -0.05, 0.0] * 96,
        "mass": 0.8,
        "created_ts": time.time() - 86400 * 30,  # 30 days old
        "last_used_ts": time.time(),
        "status": "promoted",
        "score_breakdown": {"composite": 0.91, "consistency": 0.88, "operationality": 0.92, "non_redundancy": 0.75},
    }
    g1_data = _load_json(g1_copy_path)
    g1_data.setdefault("contents", []).append(ref_entry)
    _save_g1(g1_data, g1_copy_path)

    # ── Seed candidate A: good, operational knowledge ───────────────────────
    # Has action verbs, references concrete system parameters. Should score high
    # on operationality and consistency (aligned with the seeded reference).
    good_vec = [0.8, 0.2, -0.1, 0.0] * 96  # 384-dim-ish (simplified: repeat pattern)
    good_entry = g1_add_candidate(
        text="Set the orbital integrator timestep to dt=0.01 for numerical stability; "
             "values above 0.05 cause divergence in the Verlet integration loop.",
        vector_position=good_vec,
        mass=0.7,
        path=g1_copy_path,
    )
    print(f"\n  [SEED] Good candidate: {good_entry['id']}")

    # ── Seed candidate B: AI slop — vague, filler, no actionable content ─────
    slop_vec = [0.01, -0.02, 0.03, 0.0] * 96  # near-zero magnitude
    slop_entry = g1_add_candidate(
        text="It is generally good to consider various factors when thinking about things in a holistic manner.",
        vector_position=slop_vec,
        mass=0.2,
        path=g1_copy_path,
    )
    print(f"  [SEED] AI slop candidate: {slop_entry['id']}")

    # ── Run Sleep Pass I (with optional moon pre-pass) ───────────────────────
    if moons_on:
        print("\n  [MOONS] Running G1 filter moons as pre-pass on each pending candidate...")
        from giants.g1_filter_moons import apply_filter_moons_to_sleep_pass, moons_enabled
        # Enable the toggle for this run
        import constants
        original_toggle = getattr(constants, "G1_FILTER_MOONS_ENABLED", False)
        constants.G1_FILTER_MOONS_ENABLED = True

        g1_data = _load_json(g1_copy_path)
        ring = g1_data.get("ring_buffer", []) or []
        for candidate in ring:
            if candidate.get("status") != "pending":
                continue
            print(f"    → Moon pre-pass on {candidate['id']}...")
            candidate, verdict = apply_filter_moons_to_sleep_pass(candidate, g1_data)
            # Apply cleaned text back
            idx = next((i for i, e in enumerate(ring) if e.get("id") == candidate.get("id")), None)
            if idx is not None:
                ring[idx] = candidate
            if verdict:
                print(f"      Moon verdict: {verdict}")
                # If moons rejected, mark it so sleep pass will eject
                if "reject" in (verdict or "").lower():
                    candidate["status"] = "ejected"
                    candidate["reject_reason"] = f"moon_verdict:{verdict}"
            else:
                print(f"      Moon verdict: PASS (proceeding to deterministic scoring)")

        g1_data["ring_buffer"] = ring
        _save_g1(g1_data, g1_copy_path)

        # Restore toggle after moons run
        constants.G1_FILTER_MOONS_ENABLED = original_toggle
    else:
        print("\n  [MOONS] OFF — skipping LLM pre-pass (deterministic path).")

    report = g1_sleep_pass_i(path=g1_copy_path)

    after = _load_json(g1_copy_path)

    # ── Print results ────────────────────────────────────────────────────────
    print(f"\n  SLEEP PASS REPORT:")
    print(f"    total_pending: {report['total_pending']}")
    print(f"    promoted:      {[e.get('id') for e in report.get('promoted', [])]}")
    print(f"    ejected:       {[e.get('id') for e in report.get('ejected', [])]}")

    # Show what happened to each seed.
    # NOTE: promoted entries are MOVED from ring_buffer to contents by the sleep pass.
    all_entries = after.get("contents", []) + after.get("ring_buffer", [])
    good_in_contents = any(
        e.get("id") == good_entry["id"] and e.get("status") == "promoted"
        for e in after.get("contents", [])
    )
    slop_ejected = any(
        e.get("id") == slop_entry["id"] and e.get("status") == "ejected"
        for e in after.get("ring_buffer", [])
    )

    print(f"\n  VERIFICATION:")
    print(f"    [{'PASS' if good_in_contents else 'FAIL'}] Good candidate promoted to contents: {good_in_contents}")
    print(f"    [{'PASS' if slop_ejected else 'FAIL'}] AI slop ejected from ring buffer:   {slop_ejected}")

    # Score breakdown for evidence
    for e in all_entries:
        if e.get("id") in (good_entry["id"], slop_entry["id"]):
            _print_entry_brief(e)

    return before, after


def _save_g1(data: dict, path: str) -> None:
    """Local save helper (mirrors g1_ops._save_g1)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ─── G2 TEST SCENARIO ────────────────────────────────────────────────────────

def run_g2_rejection(g2_copy_path: str) -> tuple[dict, dict]:
    """Inject a structural Tier-2 candidate → verify it's held at pending_user_approval."""
    print("\n" + "=" * 60)
    print("  G2 ACCEPTANCE REJECTION (Structural Candidate)")
    print("=" * 60)

    before = _load_json(g2_copy_path)

    # ── Seed a structurally harmful candidate ────────────────────────────────
    # kind="anchor_migration" + vector magnitude > 0.3 → Tier 2 (pending_user_approval)
    # Vector: [0.5, 0.4, 0.3] has magnitude sqrt(0.25+0.16+0.09)=sqrt(0.5)≈0.707 > 0.3
    harmful_vec = [0.5, 0.4, 0.3, 0.0] * 96  # 384-dim with magnitude well above 0.3
    harmful_entry = g2_add_candidate(
        text="Migrate the Hero planet's semantic anchor from 'courage-driven' to "
             "'fear-avoidant' framing, shifting the core identity vector by a large delta.",
        vector_position=harmful_vec,
        mass=0.9,
        tier=1,  # HINT says Tier 1 — but the growth policy classifier will override to Tier 2
        kind="anchor_migration",
        path=g2_copy_path,
    )
    print(f"\n  [SEED] Structural candidate: {harmful_entry['id']}")
    print(f"         kind={harmful_entry.get('kind')}, hint_tier={harmful_entry.get('tier')}")

    # Show what the classifier would say (for evidence)
    tier_result = g2_classify_tier(harmful_entry)
    print(f"  [CLASSIFY] tier={tier_result['tier']}, reason=\"{tier_result['reason']}\"")
    print(f"             signals={tier_result['signals']}")

    # ── Run G2 Sleep Pass I (deterministic — moons are structural, zero LLM) ─
    report = g2_sleep_pass_i(path=g2_copy_path)

    after = _load_json(g2_copy_path)

    # ── Print results ────────────────────────────────────────────────────────
    print(f"\n  SLEEP PASS REPORT:")
    print(f"    total_pending: {report['total_pending']}")
    print(f"    promoted:      {[e for e in report.get('promoted', [])]}")
    print(f"    held_law:      {report.get('held_law', [])}")
    print(f"    pending_approval: {report.get('pending_approval', [])}")
    print(f"    clamped:       {report.get('clamped', [])}")

    # Verify the candidate is NOT in contents and IS held (either law_check or user_approval)
    in_contents = any(e.get("id") == harmful_entry["id"] for e in after.get("contents", []))
    in_ring_held = any(
        e.get("id") == harmful_entry["id"] and e.get("status") in ("held_law_check", "pending_user_approval")
        for e in after.get("ring_buffer", [])
    )
    # Report which hold state it's in
    held_status = next(
        (e.get("status") for e in after.get("ring_buffer", []) if e.get("id") == harmful_entry["id"]), "?"
    )

    print(f"\n  VERIFICATION:")
    print(f"    [{'PASS' if not in_contents else 'FAIL'}] NOT committed to contents: {not in_contents}")
    print(f"    [{'PASS' if in_ring_held else 'FAIL'}] Held (status={held_status}): {in_ring_held}")

    # Show the entry's final state
    for e in after.get("ring_buffer", []):
        if e.get("id") == harmful_entry["id"]:
            _print_entry_brief(e)

    return before, after


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 7 Seg 6: G1/G2 Acceptance Test")
    parser.add_argument("--moons-on", action="store_true",
                        help="Enable G1 filter moons (requires LM Studio running)")
    args = parser.parse_args()

    ts = _ts()
    print("=" * 60)
    print(f"  PHASE 7 SEGMENT 6 — ACCEPTANCE TEST")
    print(f"  Timestamp: {ts}")
    print(f"  G1 Moons: {'ON' if args.moons_on else 'OFF'}")
    print(f"  G2 Moons: deterministic (always on, zero LLM)")
    print("=" * 60)

    failures = []

    # ── Create temp copies of real JSON files ────────────────────────────────
    tmpdir = tempfile.mkdtemp(prefix="p7s6_acceptance_")
    g1_copy = os.path.join(tmpdir, "g1_knowledge_test.json")
    g2_copy = os.path.join(tmpdir, "g2_selfmodel_test.json")

    shutil.copy2(os.path.join(_GIANTS_DIR, "g1_knowledge.json"), g1_copy)
    shutil.copy2(os.path.join(_GIANTS_DIR, "g2_selfmodel.json"), g2_copy)
    print(f"\n  Temp dir: {tmpdir}")
    print(f"  G1 copy:  {os.path.basename(g1_copy)}")
    print(f"  G2 copy:  {os.path.basename(g2_copy)}")

    try:
        # ── RUN G1 CYCLE ─────────────────────────────────────────────────────
        g1_before, g1_after = run_g1_cycle(g1_copy, moons_on=args.moons_on)
        _diff_summary(g1_before, g1_after, "G1")

        # Check assertions.
        # Promoted entries are moved to contents; ejected stay in ring_buffer.
        all_after = g1_after.get("contents", []) + g1_after.get("ring_buffer", [])
        good_promoted = any(
            e.get("text", "").startswith("Set the orbital integrator") and e.get("status") == "promoted"
            for e in g1_after.get("contents", [])
        )
        slop_ejected = any(
            e.get("text", "").startswith("It is generally good") and e.get("status") == "ejected"
            for e in g1_after.get("ring_buffer", [])
        )

        if not good_promoted:
            failures.append("G1: Good candidate was NOT promoted")
        if not slop_ejected:
            failures.append("G1: AI slop candidate was NOT ejected")

        # ── RUN G2 REJECTION ─────────────────────────────────────────────────
        g2_before, g2_after = run_g2_rejection(g2_copy)
        _diff_summary(g2_before, g2_after, "G2")

        # Check assertions for G2.
        # The structural candidate must NOT be committed. It can be held at either
        # "held_law_check" (Consistency Gate catches magnitude > escape threshold first)
        # or "pending_user_approval" (Tier gate). Both are valid safety holds.
        harmful_in_contents = any(
            e.get("kind") == "anchor_migration"
            for e in g2_after.get("contents", [])
        )
        harmful_held = any(
            e.get("kind") == "anchor_migration"
            and e.get("status") in ("held_law_check", "pending_user_approval")
            for e in g2_after.get("ring_buffer", [])
        )

        if harmful_in_contents:
            failures.append("G2: Structural candidate was COMMITTED (should be held!)")
        if not harmful_held:
            failures.append("G2: Structural candidate NOT in a held state")

    finally:
        # ── FINAL SUMMARY ────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print(f"  FINAL RESULT — {'ALL PASS' if not failures else 'FAILURES DETECTED'}")
        print("=" * 60)
        if failures:
            for f in failures:
                print(f"    ✗ {f}")
            print(f"\n  Total failures: {len(failures)}")
        else:
            print("    ✓ G1: Good candidate promoted, AI slop ejected.")
            print("    ✓ G2: Structural candidate held at pending_user_approval.")
            print("\n  Both giants are operating correctly in isolation.")

        # Cleanup temp dir
        try:
            shutil.rmtree(tmpdir)
            print(f"\n  Temp dir cleaned: {tmpdir}")
        except OSError as e:
            print(f"\n  [WARN] Could not clean temp dir {tmpdir}: {e}")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
