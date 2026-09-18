"""
Resonant Cognition v17 — Phase 8 Segment 2: Full Comet Trigger System
=======================================================================

Implements the authoritative 4-trigger spec from comet/jester.json. The Jester (Comet)
is a perturbation event / system probe, NOT a resonance participant. It appears only
when one of its trigger conditions is met, delivers ONE contrarian reframe, and fades.

TRIGGERS (per jester.json):
  1. stagnation         (weight 0.8) — same dominant planet + similar topic >3 exchanges
  2. over_seriousness   (weight 0.7) — sustained Ruler+Caregiver dominance, no creative input >5
  3. binary_convergence (weight 0.9) — two planets in direct opposition (align < -0.6), unresolved >2
  4. random_injection   (weight 0.4) — p=0.02 per session, anti-calcification

ARCHITECTURE:
  - This module is PURE LOGIC + TINY STATE I/O. No LLM calls here.
  - The cognitive_chamber calls evaluate_triggers() between Phase B and Phase C.
  - If it fires, the chamber makes ONE LLM call (build_comet_prompt) and folds the result in.
  - Toggle: constants.COMET_TRIGGER_ENABLED gates whether this module is invoked at all.

STATE FILE: comet/comet_state.json — small JSON tracking cross-turn counters.
            Deliberately minimal; NOT the Phase 4/8 memory machinery.

DESIGN RULES (John's constraints):
  - "Implement my actual idea, not something that works."
  - GUESS values are flagged with # GUESS comments for later tuning.
  - The comet does NOT change what the user submitted; it adds a contrarian voice.
  - When COMET_TRIGGER_ENABLED is False (default), this module is NEVER imported by
    the chamber — byte-identical path preserved.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)  # .../resonant_cognition
if _ROOT not in [os.path.abspath(p) for p in __import__("sys").path]:
    __import__("sys").path.insert(0, _ROOT)

import constants as C


# ─── STATE FILE LOCATION (separate from the old minimal comet_state.json at root) ──
COMET_STATE_PATH = os.path.join(_HERE, "comet_state.json")


def _load_jester_spec(base_dir: str | None = None) -> dict:
    """Load the authoritative jester.json spec. Falls back to sane defaults if missing."""
    path = os.path.join(_HERE, "jester.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback defaults matching jester.json values
        return {
            "trigger_conditions": [
                {"id": "stagnation", "activation_weight": 0.8},
                {"id": "over_seriousness", "activation_weight": 0.7},
                {"id": "binary_convergence", "activation_weight": 0.9},
                {"id": "random_injection", "probability_per_session": 0.02, "activation_weight": 0.4},
            ],
        }


# ─── STATE MANAGEMENT (tiny cross-turn JSON) ─────────────────────────────────────

_DEFAULT_STATE: dict[str, Any] = {
    # Stagnation tracking
    "dominant_planet": None,       # last session's dominant planet ID
    "topic_hash": None,            # hash of last session's topic fingerprint
    "same_pattern_streak": 0,      # consecutive sessions with same dominant+topic

    # Over-seriousness tracking
    "serious_dominance_streak": 0, # consecutive sessions where ruler+caregiver dominated

    # Binary convergence tracking
    "binary_opp_pair": None,       # "planetA|planetB" key of the opposing pair
    "binary_opp_exchanges": 0,     # how many consecutive sessions this opposition persisted

    # Cooldown (GUESS: 3 sessions min gap between any comet fires)
    "last_fired_session": None,    # session_number at last fire (for cooldown check)

    # H2 fix — per-turn counter. The ring's session number only increments when a
    # session ENDS, so it is constant across every turn of a live conversation.
    # Seeding the random trigger on that sticky value made it fire EVERY turn or
    # NEVER. This counter ticks once per evaluate_triggers() call and is reset in
    # _update_counters() when the session number changes, giving each turn within a
    # session its own independent draw while staying deterministic for tests.
    "turn_counter": 0,
}


def load_comet_state(path: str | None = None) -> dict:
    """Load comet trigger state. Missing/corrupt file returns defaults."""
    p = path or COMET_STATE_PATH
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults so new keys are always present
        merged = dict(_DEFAULT_STATE)
        merged.update(data)
        return merged
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(_DEFAULT_STATE)


def save_comet_state(state: dict, path: str | None = None) -> None:
    """Persist comet trigger state. Best-effort; never raises."""
    p = path or COMET_STATE_PATH
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        print(f"   [COMET] WARN: could not persist state to {p}: {e}")


# ─── TOPIC FINGERPRINT (GUESS-level approximation for stagnation detection) ─────

def _topic_fingerprint(question: str, dominant_pid: str | None) -> str:
    """Cheap hash of (dominant planet + first 8 content words). Not semantic — just
    catches 'same question to same planet' patterns. Upgradable to embeddings later."""
    if not question or not dominant_pid:
        return "none"
    # First 8 non-empty words, lowercased — crude but deterministic
    words = [w.strip(".,!?;:'\"()[]{}") for w in question.split()]
    words = [w.lower() for w in words if w]
    fingerprint_input = f"{dominant_pid}:{' '.join(words[:8])}"
    return hashlib.md5(fingerprint_input.encode("utf-8")).hexdigest()[:12]


# ─── INDIVIDUAL PREDICATES ──────────────────────────────────────────────────────

def _check_stagnation(state: dict, dominant_pid: str | None, question: str) -> tuple[bool, int]:
    """TRIGGER 1 (weight 0.8): same dominant planet + similar topic >3 exchanges without new info.

    GUESS approximation: we track consecutive sessions where BOTH the dominant planet AND
    the topic fingerprint match. At streak >= 4 (i.e., ">3"), it fires. A genuinely new
    topic (different fingerprint) or different dominant planet resets to 1.
    """
    if dominant_pid is None:
        return False, 0

    fp = _topic_fingerprint(question, dominant_pid)
    same_as_last = (state.get("dominant_planet") == dominant_pid and state.get("topic_hash") == fp)

    if same_as_last:
        streak = int(state.get("same_pattern_streak", 0)) + 1
    else:
        streak = 1

    # Fire when streak exceeds 3 (i.e., on the 4th consecutive same-pattern session)
    fired = streak > 3
    return fired, streak


def _check_over_seriousness(state: dict, routed_weights: dict[str, float] | None) -> tuple[bool, int]:
    """TRIGGER 2 (weight 0.7): sustained high-Ruler/Caregiver dominance with no creative/exploratory
    input for >5 exchanges.

    'Creative/exploratory' = magician or rebel having the highest routed weight.
    If neither is #1, AND ruler+caregiver combined weight exceeds all others individually,
    we count it as a 'serious' session. At streak >= 6 (i.e., ">5"), it fires.
    """
    if not routed_weights:
        return False, 0

    real = {k: v for k, v in routed_weights.items() if not k.startswith("_")}
    if not real:
        return False, 0

    top_pid = max(real, key=lambda k: real[k])

    # Creative/exploratory planets break the streak immediately
    creative_planets = {"magician", "rebel"}
    if top_pid in creative_planets:
        return False, 0  # resets (caller will set streak to 0)

    # Check ruler+caregiver dominance: their combined weight should be notable
    # AND at least one of them should be in the top-2
    serious_pids = {"ruler", "caregiver"}
    ruler_w = real.get("ruler", 0.0)
    caregiver_w = real.get("caregiver", 0.0)
    combined_serious = ruler_w + caregiver_w

    # At least one serious planet in top-2, and combined > any single non-serious planet
    sorted_pids = sorted(real.keys(), key=lambda k: real[k], reverse=True)
    top2 = set(sorted_pids[:2])
    has_serious_in_top2 = bool(serious_pids & top2)

    if has_serious_in_top2 and combined_serious > 0:
        max_non_serious = max((real[p] for p in real if p not in serious_pids), default=0.0)
        if combined_serious >= max_non_serious:
            streak = int(state.get("serious_dominance_streak", 0)) + 1
        else:
            streak = 1
    else:
        return False, 0  # not a serious session; caller resets

    fired = streak > 5  # ">5 exchanges" per jester.json
    return fired, streak


def _check_binary_convergence(
    state: dict,
    pair_map: dict[str, dict] | None,
) -> tuple[bool, str | None, int]:
    """TRIGGER 3 (weight 0.9): two planets in direct opposition (cosine < -0.6), unresolved after 2 exchanges.

    'Unresolved' = the same pair has had align < -0.6 for >2 consecutive sessions without
    the opposition improving (align rising above threshold).
    """
    if not pair_map:
        return False, None, 0

    # Find the most opposed pair this session (lowest align value)
    min_align = 1.0
    min_pair_key = None
    for key, val in pair_map.items():
        align = val.get("align", 0.0)
        if align < min_align:
            min_align = align
            min_pair_key = key

    # Threshold from jester.json: cosine similarity < -0.6
    threshold = -0.6
    if min_align >= threshold or min_pair_key is None:
        return False, state.get("binary_opp_pair"), 0  # no opposition this session

    # Same pair as last session? Increment; new pair resets to 1
    prev_pair = state.get("binary_opp_pair")
    if prev_pair == min_pair_key:
        exchanges = int(state.get("binary_opp_exchanges", 0)) + 1
    else:
        exchanges = 1

    # Fire after >2 consecutive sessions of the same opposition (i.e., on the 3rd)
    fired = exchanges > 2
    return fired, min_pair_key, exchanges


def _check_random_injection(session_number: int | None, turn_counter: int = 0) -> bool:
    """TRIGGER 4 (weight 0.4): random anti-calcification trigger, p=0.02 per TURN.

    H2 fix (independent review): the seed now includes a per-turn counter, not just the
    (sticky) session number. Within one live conversation the session number is constant,
    so seeding on it alone made this draw identical every turn — firing EVERY turn or
    NEVER instead of an independent ~2% chance each turn. Adding the counter gives each
    turn its own deterministic draw while keeping tests reproducible when given a fixed
    (session_number, turn_counter) pair.
    """
    p = 0.02
    if session_number is not None:
        # Deterministic per-TURN seed: (session, counter) advances one step each call.
        rng = random.Random(f"comet_random_injection:{session_number}:{turn_counter}")
        return rng.random() < p
    else:
        # Live mode with no session number: true randomness per call
        return random.random() < p


# ─── COOLDOWN CHECK (GUESS: 3 sessions min gap) ────────────────────────────────

COOLDOWN_SESSIONS = 3  # GUESS — tunable; jester.json implies a cooldown via last_appearance_session


def _in_cooldown(state: dict, session_number: int | None) -> bool:
    """Return True if the comet fired within the last COOLDOWN_SESSIONS sessions.

    H3 fix (independent review): the original short-circuited to False whenever EITHER
    value was None/falsy, which silently BYPASSED cooldown — a fire that recorded no
    session number could immediately re-fire. Now: if we know it fired recently but can't
    measure the gap (missing/unparseable numbers), we FAIL CLOSED and enforce cooldown.
    Cooldown only lifts once the session number is usable AND shows a clear gap.
    """
    last = state.get("last_fired_session")

    # Never fired before → no cooldown.
    if last is None:
        return False

    try:
        last_i = int(last)
    except (TypeError, ValueError):
        # We know it fired but can't read the recorded session — fail closed.
        return True

    if session_number is None:
        # It fired recently and we have no usable current session number to measure the
        # gap against → fail closed (don't allow an immediate consecutive fire).
        return True

    try:
        cur_i = int(session_number)
    except (TypeError, ValueError):
        return True  # unparseable current session — fail closed

    gap = cur_i - last_i
    return gap < COOLDOWN_SESSIONS


# ─── MAIN EVALUATION ENTRY POINT ───────────────────────────────────────────────

def evaluate_triggers(
    routed_weights: dict[str, float] | None = None,
    pair_map: dict[str, dict] | None = None,
    question: str = "",
    session_number: int | None = None,
    state: dict | None = None,
    state_path: str | None = None,
) -> tuple[bool, str, float, str]:
    """Evaluate ALL 4 comet triggers. Returns (fired, trigger_id, weight, detail).

    If multiple triggers qualify simultaneously, the HIGHEST activation_weight wins
    (binary_convergence at 0.9 > stagnation at 0.8 > over_seriousness at 0.7 > random at 0.4).

    Side effect: updates and persists comet_state.json with new counters.

    Parameters:
        routed_weights : per-planet Gaussian weights from routing (dict pid -> float)
        pair_map       : collapse result's pair_map { "a|b": {"align": float, "cancelled": float} }
        question       : the user's input text (for topic fingerprinting)
        session_number : current session count from ring context (for cooldown + random seed)
        state          : pre-loaded state dict (if None, loads from disk)
        state_path     : override path for state file (testing)

    Returns:
        (fired, trigger_id, weight, detail_string)
        fired=True means the comet should fire this turn.
        trigger_id is one of: "stagnation", "over_seriousness", "binary_convergence", "random_injection"
        weight is the activation_weight from jester.json for the winning trigger.
        detail is a human-readable explanation (for logs / Gate 4).
    """
    if state is None:
        state = load_comet_state(state_path)

    spec = _load_jester_spec()
    # Build weight lookup from spec
    weights_map: dict[str, float] = {}
    for tc in spec.get("trigger_conditions", []):
        tid = tc.get("id", "")
        w = tc.get("activation_weight", 0.5)
        weights_map[tid] = w

    dominant_pid = _dominant(routed_weights)

    # Cooldown check: if recently fired, skip ALL triggers this turn
    if _in_cooldown(state, session_number):
        # Still update state counters (they keep running), just don't fire
        new_state = _update_counters(
            state, dominant_pid, question, routed_weights, pair_map,
            session_number=session_number,
        )
        save_comet_state(new_state, state_path)
        return False, "", 0.0, "cooldown"

    # Evaluate each trigger, collect candidates
    candidates: list[tuple[float, str, str]] = []  # (weight, trigger_id, detail)

    # --- Trigger 1: Stagnation ---
    stag_fired, stag_streak = _check_stagnation(state, dominant_pid, question)
    if stag_fired:
        # L2 fix: counters keep advancing through cooldown turns, so the streak
        # count includes suppressed (cooldown) sessions — say that honestly.
        candidates.append((
            weights_map.get("stagnation", 0.8),
            "stagnation",
            f"Same pattern ({dominant_pid}) for {stag_streak} sessions without new info "
            f"(count includes suppressed/cooldown turns)."
        ))

    # --- Trigger 2: Over-seriousness ---
    os_fired, os_streak = _check_over_seriousness(state, routed_weights)
    if os_fired:
        candidates.append((
            weights_map.get("over_seriousness", 0.7),
            "over_seriousness",
            f"Ruler/Caregiver dominance sustained for {os_streak} sessions with no creative input."
        ))

    # --- Trigger 3: Binary convergence ---
    bc_fired, bc_pair, bc_exchanges = _check_binary_convergence(state, pair_map)
    if bc_fired and bc_pair:
        candidates.append((
            weights_map.get("binary_convergence", 0.9),
            "binary_convergence",
            f"Planets {bc_pair.replace('|', ' vs ')} in direct opposition (align < -0.6) for {bc_exchanges} sessions unresolved."
        ))

    # --- Trigger 4: Random injection (H2: per-turn counter, not sticky session number) ---
    _turn_counter = int(state.get("turn_counter", 0))
    if _check_random_injection(session_number, turn_counter=_turn_counter):
        candidates.append((
            weights_map.get("random_injection", 0.4),
            "random_injection",
            f"Random anti-calcification trigger (p=0.02) fired at session {session_number}, turn {_turn_counter}."
        ))

    # --- Select winner: highest weight; tie-break by order in jester.json ---
    if not candidates:
        new_state = _update_counters(
            state, dominant_pid, question, routed_weights, pair_map,
            session_number=session_number,
        )
        save_comet_state(new_state, state_path)
        return False, "", 0.0, "no trigger met"

    # Sort by weight descending (stable sort preserves jester.json order for ties)
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_weight, best_id, best_detail = candidates[0]

    # --- Update state with fire + all counters ---
    new_state = _update_counters(
        state, dominant_pid, question, routed_weights, pair_map,
        session_number=session_number,
    )
    new_state["last_fired_session"] = session_number  # start cooldown clock
    save_comet_state(new_state, state_path)

    return True, best_id, best_weight, best_detail


def _dominant(routed_weights: dict[str, float] | None) -> str | None:
    """Planet with the highest routed weight. None if weights unavailable."""
    if not routed_weights:
        return None
    real = {k: v for k, v in routed_weights.items() if not k.startswith("_")}
    if not real:
        return None
    return max(real, key=lambda k: real[k])


def _update_counters(
    state: dict,
    dominant_pid: str | None,
    question: str,
    routed_weights: dict[str, float] | None,
    pair_map: dict[str, dict] | None,
    session_number: int | None = None,
) -> dict:
    """Compute the NEXT state after this turn (regardless of whether comet fired)."""
    new = dict(state)  # shallow copy

    # H2 fix — advance the per-turn counter every call, but RESET it to 0 when we are on a
    # NEW session (session number changed since last turn). This keeps each turn's random
    # draw independent within a conversation while making the very first turn of any new
    # session deterministic again. The CURRENT call already used state["turn_counter"]; this
    # stored value is what the NEXT call reads.
    if "_last_session_seen" not in new:
        new["_last_session_seen"] = None
    prev_seen = new.get("_last_session_seen")
    new["turn_counter"] = int(state.get("turn_counter", 0)) + 1
    if session_number is not None and session_number != prev_seen:
        # First turn of a fresh (or first) session — reset so its draw is stable/reproducible.
        new["turn_counter"] = 0
    new["_last_session_seen"] = session_number

    # Stagnation counters
    if dominant_pid is not None and question:
        fp = _topic_fingerprint(question, dominant_pid)
        same = (state.get("dominant_planet") == dominant_pid and state.get("topic_hash") == fp)
        new["same_pattern_streak"] = int(state.get("same_pattern_streak", 0)) + 1 if same else 1
    else:
        new["same_pattern_streak"] = 0
    new["dominant_planet"] = dominant_pid
    new["topic_hash"] = _topic_fingerprint(question, dominant_pid) if (question and dominant_pid) else None

    # Over-seriousness counter
    os_fired, os_streak = _check_over_seriousness(state, routed_weights)
    # If creative planet was top, reset to 0; otherwise use the computed streak
    if routed_weights:
        real = {k: v for k, v in routed_weights.items() if not k.startswith("_")}
        if real:
            top_pid = max(real, key=lambda k: real[k])
            if top_pid in ("magician", "rebel"):
                new["serious_dominance_streak"] = 0
            else:
                new["serious_dominance_streak"] = os_streak
        else:
            new["serious_dominance_streak"] = 0
    else:
        new["serious_dominance_streak"] = 0

    # Binary convergence counter
    bc_fired, bc_pair, bc_exchanges = _check_binary_convergence(state, pair_map)
    if bc_pair is not None and bc_exchanges > 0:
        new["binary_opp_pair"] = bc_pair
        new["binary_opp_exchanges"] = bc_exchanges
    else:
        # No opposition this session — reset
        new["binary_opp_pair"] = None
        new["binary_opp_exchanges"] = 0

    return new


# ─── STANDALONE SMOKE TEST (run directly) ──────────────────────────────────────

if __name__ == "__main__":
    print("Comet Triggers Module — Quick Smoke Test")
    print("=" * 60)

    # Test with synthetic data (no LLM, no file I/O beyond temp state)
    import tempfile

    tmp_state = os.path.join(tempfile.gettempdir(), "comet_smoke_test.json")
    if os.path.exists(tmp_state):
        os.remove(tmp_state)

    print("\n[1] No weights -> no fire:")
    result = evaluate_triggers(routed_weights=None, state_path=tmp_state)
    print(f"    fired={result[0]}, reason='{result[3]}'")
    assert not result[0], "Should not fire with no data"

    print("\n[2] Normal weights (sage dominant), first session -> no fire:")
    w = {"sage": 0.9, "hero": 0.7, "ruler": 0.3, "caregiver": 0.4,
         "everyman": 0.5, "magician": 0.6, "rebel": 0.2}
    pm = {"sage|rebel": {"align": -0.1, "cancelled": 0.05},
          "hero|ruler": {"align": 0.3, "cancelled": 0.0}}
    result = evaluate_triggers(routed_weights=w, pair_map=pm,
                               question="How do I handle conflict at work?",
                               session_number=1, state_path=tmp_state)
    print(f"    fired={result[0]}, reason='{result[3]}'")

    print("\n[3] Same input x4 (stagnation should fire on 4th):")
    for i in range(2, 5):
        result = evaluate_triggers(routed_weights=w, pair_map=pm,
                                   question="How do I handle conflict at work?",
                                   session_number=i, state_path=tmp_state)
        print(f"    session {i}: fired={result[0]}, trigger='{result[1]}', detail='{result[3]}'")

    print("\n[4] Binary convergence (opposing pair x3):")
    # Reset state for clean test
    if os.path.exists(tmp_state):
        os.remove(tmp_state)
    pm_opp = {"ruler|rebel": {"align": -0.8, "cancelled": 0.5},
              "sage|hero": {"align": 0.9, "cancelled": 0.0}}
    for i in range(1, 4):
        result = evaluate_triggers(routed_weights=w, pair_map=pm_opp,
                                   question=f"different question {i} about something else",
                                   session_number=i, state_path=tmp_state)
        print(f"    session {i}: fired={result[0]}, trigger='{result[1]}', detail='{result[3]}'")

    # Cleanup
    if os.path.exists(tmp_state):
        os.remove(tmp_state)

    print("\n" + "=" * 60)
    print("Smoke test complete. All assertions passed.")
