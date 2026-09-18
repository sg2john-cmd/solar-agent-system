"""
Resonant Cognition v17 — Phase 3 Comet B→C BASIC TRIGGER CHECK (Segment)
=========================================================================

Standalone, self-contained test for the MINIMAL comet trigger logic. This segment is
deliberately PURE-LOGIC (no LLM calls) so it runs in <1s and is fully deterministic:
the "does the comet fire?" decision, cross-session state persistence, dominant-planet
selection, prompt well-formedness, and the OFF-by-default toggle contract are all
verifiable without a model. The actual contrarian-reframe LLM call + its fold into
Phase C is exercised separately against LM Studio (see note at bottom).

CONVENTION: one focused test per segment; own runner; PASS/FAIL summary; exit 0/1.
Run:  python -X utf8 tests/test_comet_trigger.py   (from the resonant_cognition dir)

Design rule honoured throughout: the trigger is a DIAL, not a rewrite. When
COMET_TRIGGER_ENABLED is False (default), run_phase_a_b_c() must take the exact same
path as before — this test asserts the default is False so existing A/B/C results stay
byte-identical until we deliberately flip it on for its own LLM segment.
"""

from __future__ import annotations

import os
import sys
import json
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)          # .../resonant_cognition
if _ROOT not in [os.path.abspath(p) for p in sys.path]:
    sys.path.insert(0, _ROOT)

import constants as C  # noqa: E402
from cognitive_chamber import (  # noqa: E402
    check_comet_trigger,
    _load_comet_state,
    _save_comet_state,
    _dominant_planet,
    build_comet_prompt,
)


# ─── tiny test harness ────────────────────────────────────────────────────────

_PASSED = 0
_FAILED = 0
_FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASSED, _FAILED
    if cond:
        _PASSED += 1
        print(f"   \u2713 {name}")
    else:
        _FAILED += 1
        _FAILURES.append(name)
        print(f"   \u2717 {name}" + (f"  [{detail}]" if detail else ""))


def fresh_state_path() -> str:
    """A throwaway state file in a temp dir so we never touch the real comet_state.json."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="comet_test_")
    os.close(fd)
    return path


# ─── TEST 1: default toggle is OFF (byte-identical A/B/C contract) ───────────

def test_default_off():
    print("\n[TEST 1] Default toggle is OFF (existing A/B/C path untouched)")
    # Re-import a FRESH view of constants to confirm the shipped default, independent
    # of any runtime flag parsing in this process.
    import importlib
    fresh = importlib.reload(C)
    check("COMET_TRIGGER_ENABLED defaults to False", getattr(fresh, "COMET_TRIGGER_ENABLED", None) is False)
    check("COMET_CONSECUTIVE_SESSIONS default == 3 (three-times-pattern)",
          int(getattr(fresh, "COMET_CONSECUTIVE_SESSIONS", -1)) == 3)
    check("COMET_STATE_FILE resolves to an absolute path inside the module dir",
          os.path.isabs(C.COMET_STATE_FILE) and C.COMET_STATE_FILE.endswith("comet_state.json"))


# ─── TEST 2: streak logic — N=3 means fire on the 3rd straight session ──────

def test_streak_fires_on_third():
    print("\n[TEST 2] Streak fires exactly on the N-th (3rd) consecutive same-planet session")
    p = fresh_state_path()
    try:
        # Session 1: hero leads, cold start.
        fired1, s1 = check_comet_trigger("hero", state={"streak_planet": None, "streak_count": 0}, state_path=p)
        # Session 2: hero again.
        st = _load_state(p)
        fired2, s2 = check_comet_trigger("hero", state=st, state_path=p)
        # Session 3: hero again -> should FIRE now (3 straight).
        st = _load_state(p)
        fired3, s3 = check_comet_trigger("hero", state=st, state_path=p)

        check("session1 not fired", fired1 is False and s1 == 1, f"got ({fired1},{s1})")
        check("session2 not fired", fired2 is False and s2 == 2, f"got ({fired2},{s2})")
        check("session3 FIRED at streak==3", fired3 is True and s3 == 3, f"got ({fired3},{s3})")
    finally:
        os.remove(p)


def _load_state(p):
    return _load_comet_state(p)


def drive_sessions(planet_seq, p):
    """Feed a sequence of per-session dominant planets through the trigger.
    Returns list of (fired, streak) in order. Uses real state file persistence."""
    out = []
    for pid in planet_seq:
        st = _load_state(p)
        out.append(check_comet_trigger(pid, state=st, state_path=p))
    return out


# ─── TEST 3b: re-fire cadence — fires at 3, then every REFIRE_STEP more (5,7..) ──

def test_refire_cadence():
    print(f"\n[TEST 3b] Re-fire cadence: fire at N=3, then every COMET_REFIRE_STEP={C.COMET_REFIRE_STEP} more")
    p = fresh_state_path()
    try:
        results = drive_sessions(["hero"] * 8, p)   # hero leads 8 straight sessions
        fired_at = [i + 1 for i, (f, s) in enumerate(results) if f]  # 1-based session numbers
        expected = [3, 5, 7]                          # N=3 then every 2 more up to session 8
        check("fires exactly at sessions {0}, not the others".format(expected),
              fired_at == expected, f"got fired_at={fired_at}")
        check("streak counts climb 1..8", [s for _, s in results] == list(range(1, 9)),
              f"got {[s for _, s in results]}")
    finally:
        os.remove(p)


# ─── TEST 3c: subject change mid-streak resets (no false re-fire) ──────────────

def test_subject_change_resets_mid_streak():
    print("\n[TEST 3c] A subject change (new dominant planet) mid-run RESETS the cadence")
    p = fresh_state_path()
    try:
        # hero,hero,hero(s3 fires),sage(subject change -> reset),sage,sage(...)
        seq = ["hero", "hero", "hero", "sage", "sage", "sage"]
        results = drive_sessions(seq, p)
        fired_at = [(i + 1, pid) for i, (pid) in enumerate(seq) if results[i][0]]
        # Only the hero streak should have fired: session 3. sage only reaches streak 3
        # at overall session 6 -> that is sage's OWN 3rd straight, so it fires too.
        check("hero fired on its 3rd (session 3)", any(n == 3 and pl == "hero" for n, pl in fired_at),
              f"got {fired_at}")
        check("sage, after the reset, builds a FRESH streak and fires on ITS 3rd (session 6)",
              any(n == 6 and pl == "sage" for n, pl in fired_at), f"got {fired_at}")
        # Crucially: sessions 4 & 5 (sage's 1st & 2nd) must NOT have fired.
        check("no premature fire on sage's 1st/2nd session", all(n not in (4, 5) for n, _ in fired_at),
              f"got {fired_at}")
    finally:
        os.remove(p)


# ─── TEST 3: a different planet breaks the streak (no false fire) ────────────

def test_streak_break():
    print("\n[TEST 3] A different dominant planet RESETS the streak to 1")
    p = fresh_state_path()
    try:
        _save_comet_state({"streak_planet": "hero", "streak_count": 2}, p)   # hero, 2 in a row...
        fired, s = check_comet_trigger("sage", state=_load_state(p), state_path=p)  # ...but sage leads now
        st = _load_state(p)
        check("switching planet does NOT fire (streak resets to 1)",
              fired is False and s == 1, f"got ({fired},{s})")
        check("state now tracks the NEW dominant planet",
              st["streak_planet"] == "sage" and st["streak_count"] == 1, f"got {st}")

        # And if hero comes back it must NOT instantly fire (fresh streak of 1).
        fired2, s2 = check_comet_trigger("hero", state=_load_state(p), state_path=p)
        check("returning planet starts a FRESH streak (no instant fire)",
              fired2 is False and s2 == 1, f"got ({fired2},{s2})")
    finally:
        os.remove(p)


# ─── TEST 4: no dominant planet -> reset + never fire (graceful, no crash) ──

def test_no_dominant():
    print("\n[TEST 4] Missing routed weights -> no fire, state resets, no crash")
    p = fresh_state_path()
    try:
        _save_comet_state({"streak_planet": "hero", "streak_count": 5}, p)   # even a long streak...
        fired, s = check_comet_trigger(None, state=_load_state(p), state_path=p)  # ...can't fire w/o weights
        st = _load_state(p)
        check("no dominant -> not fired", fired is False and s == 0, f"got ({fired},{s})")
        check("state reset to empty (streak_planet=None, count=0)",
              st["streak_planet"] is None and st["streak_count"] == 0, f"got {st}")
    finally:
        os.remove(p)


# ─── TEST 5: corrupt / missing state file -> fresh state, never crash ────────

def test_corrupt_state():
    print("\n[TEST 5] Missing or corrupt state file is treated as a clean start")
    p = fresh_state_path()
    try:
        os.remove(p)  # missing entirely
        st = _load_comet_state(p)
        check("missing file -> empty state", st == {"streak_planet": None, "streak_count": 0}, f"got {st}")

        with open(p, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json ]]")   # corrupt content
        st2 = _load_comet_state(p)
        check("corrupt JSON -> empty state (no exception)",
              st2 == {"streak_planet": None, "streak_count": 0}, f"got {st2}")

        with open(p, "w", encoding="utf-8") as f:   # right shape but wrong types
            json.dump({"streak_count": "three"}, f)
        st3 = _load_comet_state(p)
        check("non-int count coerced to 0 (no crash)", st3["streak_count"] == 0, f"got {st3}")
    finally:
        if os.path.exists(p):
            os.remove(p)


# ─── TEST 6: dominant-planet selection from routed weights ──────────────────

def test_dominant_selection():
    print("\n[TEST 6] _dominant_planet picks the highest weight, ignores internal keys")
    w = {"hero": 0.20, "sage": 0.55, "_dark_matter": 0.99, "caregiver": 0.10}
    check("picks real max (sage), ignores underscore-prefixed internal keys",
          _dominant_planet(w) == "sage", f"got {_dominant_planet(w)}")
    check("empty weights -> None", _dominant_planet({}) is None)
    check("None weights -> None", _dominant_planet(None) is None)


# ─── TEST 7: comet prompt is well-formed (structure, not LLM content) ────────

def test_prompt_wellformed():
    print("\n[TEST 7] build_comet_prompt returns a valid chat message pair")
    msgs = build_comet_prompt("Should I switch careers?", "The Ruler")
    check("returns a list of 2 messages", isinstance(msgs, list) and len(msgs) == 2, f"got {len(msgs)}")
    roles = [m.get("role") for m in msgs]
    check("roles are system then user", roles == ["system", "user"], f"got {roles}")
    sys_txt = msgs[0].get("content", "")
    usr_txt = msgs[1].get("content", "")
    check("system prompt names the comet/jester identity", ("COMET" in sys_txt or "Jester" in sys_txt))
    check("prompt carries the dominant planet name", "The Ruler" in (sys_txt + usr_txt))
    check("prompt carries the original question", "switch careers" in usr_txt)
    check("all message contents are non-empty strings",
          all(isinstance(m.get("content"), str) and m["content"].strip() for m in msgs))


def main():
    t0 = time.time()
    print("=" * 64)
    print("COMET B→C BASIC TRIGGER — LOGIC TEST (pure, no LLM)")
    print("=" * 64)

    test_default_off()
    test_streak_fires_on_third()
    test_refire_cadence()
    test_subject_change_resets_mid_streak()
    test_streak_break()
    test_no_dominant()
    test_corrupt_state()
    test_dominant_selection()
    test_prompt_wellformed()

    dt = time.time() - t0
    print("\n" + "=" * 64)
    total = _PASSED + _FAILED
    print(f"RESULT: {_PASSED}/{total} passed, {_FAILED} failed   ({dt:.2f}s)")
    if _FAILED:
        print("FAILURES:")
        for f in _FAILURES:
            print(f"  - {f}")
        print("=" * 64)
        return 1
    print("ALL COMET-TRIGGER LOGIC CHECKS PASSED")
    print("=" * 64)
    # NOTE: the LLM half (the contrarian reframe call + its fold into Phase C) is a
    # separate segment run against LM Studio with --smoke-c --comet; it needs routed
    # weights and real sessions, so it is intentionally NOT covered by this pure-logic suite.
    return 0


if __name__ == "__main__":
    sys.exit(main())
