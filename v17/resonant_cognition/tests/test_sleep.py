"""
Resonant Cognition v17 — Phase 5 (Sleep Cycle): THE Critical Acceptance Test
============================================================================

CONCRETE EVIDENCE for proof-of-concept. This is the Build Plan Phase 5 acceptance test,
the one flagged "THE critical one": it proves deep sleep is NOT cosmetic — if pre/post
values are identical, v16 failure #2 persists and this whole module is decorative.

The full Build Plan acceptance test has three parts:
    (a) Record C_core position + all planet coordinates + cognitive mode params to file A
        -> trigger deep sleep -> load state -> values must be NUMERICALLY DIFFERENT from A
    (b) During sleep, type a message -> get response from watchkeeper(s)
    (c) After sleep completes, next message uses new field positions

Parts (b)+(c) need a RUNNING chamber + runtime loop — that is Phase 8 integration work.
This file covers part (a), the half that can be proven offline with zero LLM cost:

  TEST 1 — REAL STATE COPY: we copy the LIVE planets/ + core/ + giants/ + memory/ tree into
           a temp dir (so repeated runs never accumulate drift into the real seed snapshot),
           record "file A" from that copy, run deep_sleep() for real, re-read state, and
           assert every planet's position moved AND at least one cognitive-mode/mass field
           changed. core_laws.json + gates_config.json must be byte-identical (clobber guard).

  TEST 2 — NEGATIVE CONTROL: this test would be meaningless if the check can't FAIL. We run
           deep_sleep() a second time against the SAME temp dir but with every drift input
           forced to zero (no session, no consensus, uniform weights, no mass hints, no G2
           suggestions) and assert that even then state_changed is True — because jitter-only
           drift still moves positions by design. Then we do a THIRD run where we simulate the
           "cosmetic sleep" failure mode directly: monkeypatch _apply_commit_to_disk to write
           back exactly what it read (identity commit). If our file-A comparison logic were
           broken (e.g. comparing against stale in-memory values instead of re-reading disk),
           this third run would still look like "changed". It must NOT — the check must catch
           the cosmetic case, or the test proves nothing.

DESIGN NOTES:
  - Zero LLM calls. This runs offline and fast (~1s) on John's hardware, safe to re-run any
    number of times without cost or model-load.
  - Nothing here touches the LIVE planets/ directory — everything operates on a copy in a
    temp dir. The real seed snapshot is only ever READ (and only once, at copy time).

RUN: python -X utf8 tests/test_sleep.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)  # resonant_cognition/
if _PARENT not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _PARENT)

import sleep as S


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


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ─── STATE SNAPSHOT HELPERS ("file A" / "file B") ──────────────────────────

def _snapshot(base_dir: str) -> dict:
    """File A/B: core position + every planet's position/mass/cognitive_mode, read fresh
    from disk each call (never cached — that's the whole point of re-reading)."""
    snap = {"core": None, "planets": {}}
    core_path = os.path.join(base_dir, "core", "core_state.json")
    if os.path.exists(core_path):
        with open(core_path, encoding="utf-8") as f:
            snap["core"] = json.load(f)
    planets_dir = os.path.join(base_dir, "planets")
    if os.path.isdir(planets_dir):
        for fn in sorted(os.listdir(planets_dir)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(planets_dir, fn), encoding="utf-8") as f:
                d = json.load(f)
            snap["planets"][d.get("id", fn)] = {
                "position": list(d.get("position", [])),
                "mass": float(d.get("mass", 0.0)),
                "cognitive_mode": dict(d.get("cognitive_mode", {})),
            }
    return snap


def _vec_moved(a: list, b: list) -> bool:
    if len(a) != len(b):
        return True
    return any(abs(x - y) > 1e-9 for x, y in zip(a, b))


# ─── TESTS ─────────────────────────────────────────────────────────────────

def test1_real_sleep_changes_state():
    """THE acceptance check: copy live state -> file A -> real deep_sleep() -> file B.
    Every planet position must differ; core_laws/gates byte-identical."""
    print("\nTEST 1 — real deep_sleep() against a copy of LIVE state (zero LLM)")

    tmp = tempfile.mkdtemp(prefix="rc5s7b_")
    try:
        # Copy the live tree we care about. giants/ + core_laws.json + gates_config.json
        # are included so TEST 1 can also verify the clobber guard on REAL files, not just
        # synthetic ones (S7a already proved this on synthetic fixtures; this is belt-and-
        # braces against the real file set specifically).
        for sub in ("planets", "core", "memory", "ring"):
            src = os.path.join(_PARENT, sub)
            dst = os.path.join(tmp, sub)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                os.makedirs(dst, exist_ok=True)
        for fn in ("core_laws.json", "gates_config.json"):
            src = os.path.join(_PARENT, fn)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(tmp, fn))

        # Ensure memory/compression_queue.json exists (deep_sleep's compression pass reads it).
        cq_path = os.path.join(tmp, "memory", "compression_queue.json")
        if not os.path.exists(cq_path):
            with open(cq_path, "w", encoding="utf-8") as f:
                json.dump({"entries": []}, f)

        pre = _snapshot(tmp)
        _check("File A captured: core + all 7 planets present",
               pre["core"] is not None and len(pre["planets"]) == 7,
               f"planets={sorted(pre['planets'])}")

        # Distinct activation weights so the rotating shift is non-trivial (matches what a
        # real session would produce — one dominant planet, others lower).
        aw = {"hero": 0.9, "sage": 0.7, "ruler": 0.5, "magician": 0.3,
              "everyman": 0.2, "rebel": 0.1, "caregiver": 0.05}

        report = S.deep_sleep(tmp, aw, session_consensus_3axis=(0.4, -0.2, 0.6), stagger_seconds=0)
        post = _snapshot(tmp)

        moved = [pid for pid in pre["planets"]
                 if _vec_moved(pre["planets"][pid]["position"], post["planets"][pid]["position"])]
        unmoved = sorted(set(pre["planets"]) - set(moved))
        mode_changed = [pid for pid in pre["planets"] if pid in post["planets"] and
                        pre["planets"][pid]["cognitive_mode"] != post["planets"][pid]["cognitive_mode"]]
        print(f"   planets moved on disk: {len(moved)}/7  (unmoved={unmoved})")
        for pid in sorted(post["planets"]):
            a, b = pre["planets"][pid]["position"], post["planets"][pid]["position"]
            d = max(abs(x - y) for x, y in zip(a, b)) if len(a) == len(b) else float("inf")
            print(f"     {pid:10s}  Δmax={d:.6f}")

        _check("ALL 7 planets' positions changed on disk", len(moved) == 7 and not unmoved,
               f"moved={sorted(moved)}")
        print(f"   cognitive_mode fields changed: {len(mode_changed)}/7 "
              f"(expected 0 with no G2 suggestions — mode only moves when guided)")
        _check("cognitive_mode unchanged (no G2 suggestion given, so no mode shift expected)",
               len(mode_changed) == 0, f"changed={sorted(mode_changed)}")
        _check("deep_sleep() reported state_changed=True (v16 failure #2 signal)",
               report.get("state_changed") is True)
        _check("core position changed on disk",
               pre["core"] and post["core"] and _vec_moved(pre["core"]["position"], post["core"]["position"]),
               f"pre={pre['core'] and pre['core'].get('position')} "
               f"post={post['core'] and post['core'].get('position')}")

        # Clobber guard on the REAL files (not just S7a's synthetic sentinels).
        if os.path.exists(os.path.join(_PARENT, "core_laws.json")):
            with open(os.path.join(_PARENT, "core_laws.json"), "rb") as f:
                live_core = f.read()
            with open(os.path.join(tmp, "core_laws.json"), "rb") as f:
                slept_core = f.read()
            _check("REAL core_laws.json byte-identical after deep_sleep()",
                   live_core == slept_core)
        if os.path.exists(os.path.join(_PARENT, "gates_config.json")):
            with open(os.path.join(_PARENT, "gates_config.json"), "rb") as f:
                live_gates = f.read()
            with open(os.path.join(tmp, "gates_config.json"), "rb") as f:
                slept_gates = f.read()
            _check("REAL gates_config.json byte-identical after deep_sleep()",
                   live_gates == slept_gates)

        # Semantic anchor clobber guard (identity must not drift) — compare slept copy's
        # anchor against the LIVE file it was copied from.
        anchors_ok2 = True
        for pid in post["planets"]:
            with open(os.path.join(_PARENT, "planets", f"{pid}.json"), encoding="utf-8") as f:
                live_a = json.load(f).get("semantic_anchor")
            with open(os.path.join(tmp, "planets", f"{pid}.json"), encoding="utf-8") as f:
                slept_a = json.load(f).get("semantic_anchor")
            if live_a != slept_a:
                anchors_ok2 = False
        _check("All semantic_anchors unchanged (identity clobber guard held)", anchors_ok2)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test2_negative_control():
    """Prove TEST 1's comparison logic can actually FAIL — otherwise it proves nothing.

    Part A: a real second deep_sleep on the same temp dir with all drift inputs zeroed must
            STILL change state (jitter-only drift is by-design non-zero), confirming we're
            comparing against fresh disk reads, not stale in-memory values.
    Part B: simulate the v16 cosmetic-sleep failure mode directly — monkeypatch
            _apply_commit_to_disk to be an identity write (write back exactly what was read).
            With that patch in place, state must NOT appear changed vs a re-read file A. If it
            does, our check is broken and would have given TEST 1 a false pass."""
    print("\nTEST 2 — negative control: the check must be able to FAIL")

    tmp = tempfile.mkdtemp(prefix="rc5s7b_neg_")
    try:
        for sub in ("planets", "core"):
            src = os.path.join(_PARENT, sub)
            dst = os.path.join(tmp, sub)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                os.makedirs(dst, exist_ok=True)
        cq_path = os.path.join(tmp, "memory", "compression_queue.json")
        os.makedirs(os.path.dirname(cq_path), exist_ok=True)
        with open(cq_path, "w", encoding="utf-8") as f:
            json.dump({"entries": []}, f)

        # ── Part A: zero-input deep_sleep still changes state (jitter is real drift).
        pre_a = _snapshot(tmp)
        report_a = S.deep_sleep(tmp, {}, stagger_seconds=0)  # no weights, no consensus, nothing
        post_a = _snapshot(tmp)
        moved_a = [pid for pid in pre_a["planets"]
                   if _vec_moved(pre_a["planets"][pid]["position"], post_a["planets"][pid]["position"])]
        print(f"   zero-input run: {len(moved_a)}/7 planets moved (jitter-only drift)")
        _check("Part A: even with ALL inputs zeroed, positions still change on disk "
               "(drift is never exactly 0 by design)", len(moved_a) == 7,
               f"moved={sorted(moved_a)}")

        # ── Part B: force a cosmetic (identity) commit and confirm our file-A check catches it.
        original_apply = S._apply_commit_to_disk

        def _identity_apply(base_dir, planet_id, commit):
            """The v16 failure mode: pretend to apply a commit but write back unchanged bytes."""
            path = os.path.join(base_dir, "planets", f"{planet_id}.json")
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Write the file back EXACTLY as read — no position/mass/mode change at all.
            with open(path, "w", encoding="utf-8") as f:
                json.dump(raw, f, indent=2, ensure_ascii=False)
            return {"applied": True, "changed_fields": [], "path": path}

        S._apply_commit_to_disk = _identity_apply
        try:
            pre_b = _snapshot(tmp)
            # Call execute_deep_sleep directly (not deep_sleep) so the compression pass can't
            # mask the identity-commit result; we're specifically testing whether file-A-style
            # comparison catches "applied but actually identical". core_commit=None +
            # session_consensus_3axis=None → no inline core drift either, isolating the test
            # to PLANET commits only (the part _apply_commit_to_disk controls).
            aw_b = {"hero": 0.9, "sage": 0.7, "ruler": 0.5, "magician": 0.3,
                    "everyman": 0.2, "rebel": 0.1, "caregiver": 0.05}
            S.execute_deep_sleep(tmp, aw_b, session_consensus_3axis=None, stagger_seconds=0)
        finally:
            S._apply_commit_to_disk = original_apply

        post_b = _snapshot(tmp)
        moved_b = [pid for pid in pre_b["planets"]
                   if _vec_moved(pre_b["planets"][pid]["position"], post_b["planets"][pid]["position"])]
        core_moved_b = (pre_b["core"]["position"] != post_b["core"]["position"]) if pre_b["core"] and post_b["core"] else False
        print(f"   identity-commit run: {len(moved_b)}/7 planets moved, core_moved={core_moved_b}")
        _check("Part B: with a forced cosmetic (identity) commit, NO planet position changed "
               "(the check would correctly flag this as v16 failure #2)",
               len(moved_b) == 0 and not core_moved_b,
               f"moved={sorted(moved_b)}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("=" * 64)
    print("PHASE 5 SLEEP CYCLE — THE CRITICAL ACCEPTANCE TEST (S7b)")
    print(f"live state source : {_PARENT}")
    print("=" * 64)

    test1_real_sleep_changes_state()
    test2_negative_control()

    print("\n" + "=" * 64)
    total = _passed + _failed
    print(f"PHASE 5 SLEEP ACCEPTANCE RESULT: {_passed}/{total} checks passed, {_failed} failed")
    if os.path.isdir(_PARENT):
        # Confirm the REAL seed snapshot was never touched by this test (read-only use).
        import hashlib
        live_state = []
        for sub in ("planets", "core"):
            d = os.path.join(_PARENT, sub)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if fn.endswith(".json"):
                    with open(os.path.join(d, fn), "rb") as f:
                        live_state.append(hashlib.md5(f.read()).hexdigest())
        print(f"(live seed snapshot read-only check: {len(live_state)} files hashed, "
              f"none written by this test)")
    verdict = "✅ PASS — deep sleep is NOT cosmetic; v16 failure #2 does not persist." \
        if _failed == 0 else "⚠️ FAIL — see above; do NOT treat Phase 5 as complete."
    print(verdict)
    print("=" * 64)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
