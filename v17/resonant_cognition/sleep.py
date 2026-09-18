"""
Resonant Cognition v17 — Sleep Cycle (Phase 5)
==============================================

Two-tier sleep that permanently changes numeric state on disk.

Build order (small segments, per John's pace rule):
    Segment 1 : micro_sleep()        — Pass I light + Pass V light. NO LLM calls,
                                       NO drift, NO compression. All planets stay awake.
                                       Completes in well under a second.
    Segment 2 : select_watchkeepers()— top-N by recent activation weight (min 1).
    Segment 3 : compute_drift()      — Pass IV per-planet commit dict (position nudge,
                                       mass adjust, cognitive-mode shift). Pure math.
    Segment 4 : execute_deep_sleep() — staggered commits + persistence to planets/*.json
                                       and core/core_state.json. Never touches
                                       core_laws.json / gates_config.json.
    Segment 5 : compression pass     — Pass II merge + Pass III emission on the queue.
    Segment 6 : deep_sleep()         — full orchestrator (non-blocking shape).
    Segment 7a: moons/giants integrity — verifies a FULL deep_sleep never clobbers
                                       giants/g1_knowledge.json, g2_selfmodel.json,
                                       their moons, core_laws.json or gates_config.json.
                                       Pure file I/O. Zero LLM.

DESIGN NOTES:
- Separate-phase rule (same as routing.py): positions are OWNED by the integrator.
  Sleep only WRITES back to planets/*.json (the seed snapshot) after a deliberate,
  bounded nudge. It never advances physics and never re-reads JSON as "current"
  state mid-run — callers hand it live objects or a base_dir for disk ops.
- Pass IV drift touches ONLY: position (+/-0.02..0.1), mass (content absorbed),
  cognitive_mode params (temp +/-0.05, ctx +/-1, CoT +/-1). It NEVER touches
  semantic_anchor (clobber-guarded), core_laws.json, gates_config.json, or C_core
  beyond a +/-0.05 nudge (the Core is the anchor; it drifts slower than planets).

SEGMENT 1 NOTES:
- Pass I light alignment metric (Q2, John-approved): an entry's "position" in the field
  IS its embedding vector — spatial placement and content are one thing here, not two.
  Alignment = cosine(entry_embedding, owner planet's wave center at current position),
  i.e. does this memory actually live where its owner currently orbits? Well-aligned
  entries get their decay rate RELAXED (settle into orbit); misaligned ones get it
  ACCELERATED so Pass V light can shed them sooner. Promotion to orbital status (mass
  bump + zone move) happens in deep-sleep Pass I full, where a dream-narrative check
  can confirm the content deserves orbit — micro-sleep stays LLM-free and <1s, so it
  only turns the dial, never moves the destination.

SEGMENT 7b NOTES:
- THE critical acceptance test from the Build Plan Phase 5 section, made repeatable and
  non-destructive. It does NOT run on the live planets/ directory: it copies it into a
  temp dir (so repeated runs can't accumulate drift into the real seed snapshot), records
  file A (core position + all planet positions/masses/cognitive_mode), triggers deep_sleep()
  with stagger_seconds=0, then loads state again and asserts values are numerically
  different from file A. Also verifies core_laws.json/gates_config.json byte-identical.
- The live-runtime parts of the acceptance test (typing during sleep -> watchkeeper
  response; next session routes on new positions) are Phase 8 integration concerns —
  they need a running chamber, not a disk-state check. S7b covers the "values must be
  numerically different or v16 failure #2 persists" half, which is the part that can be
  proven offline.

RUN: python -X utf8 sleep.py   (all self-tests S1-S7a; no LM Studio needed)
RUN: python -X utf8 tests/test_sleep.py   (S7b acceptance test against live state copy,
      plus zero-LLM negative control proving the check would catch cosmetic sleep)
"""

from __future__ import annotations

import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


# ─── SEGMENT 1 TUNABLES ──────────────────────────────────────────────────────
# Kept local (not constants.py) until the full sleep cycle lands; promote with a
# calibrate_axes template entry if/when calibration needs them.

MICRO_SLEEP_ALIGN_THRESHOLD = 0.4   # cosine(entry pos, owner field center) above this = well-aligned
MICRO_SLEEP_MISALIGN_PENALTY = 3.0  # decay-rate multiplier applied to misaligned ring entries


# ─── VECTOR MATH HELPERS (kept local; mirror routing.py's _norm/_unit so this module
#     has no hard dependency on the routing/collapse engine at import time) ──────

def _norm(v) -> float:
    return math.sqrt(sum(x * x for x in v)) or 1.0


def _unit(v):
    n = _norm(list(v))
    return [x / n for x in v] if n > 1e-9 else list(v)


# ─── PASS I (LIGHT): RING BUFFER ALIGNMENT SCAN ──────────────────────────────

def scan_ring_buffers(base_dir: str, now_ts: float | None = None) -> dict:
    """Pass I (light): classify ring-buffer entries by alignment with their owner's
    CURRENT field center, then relax/accelerate decay accordingly.

    For each entry that has a vector_position AND a known planet_id:
        align = cosine(entry.vector_position, owner's blended field center at its live position)
    - aligned  (>= MICRO_SLEEP_ALIGN_THRESHOLD): decay_rate relaxed toward the usage-
      frequency rate — this memory is settling into orbit; deep-sleep Pass I full will
      promote it to orbital status if it still qualifies.
    - misaligned: decay_rate accelerated by MICRO_SLEEP_MISALIGN_PENALTY (capped 0.5) so
      Pass V light sheds it sooner rather than letting a misplaced memory hold mass.

    The owner's field center is computed live from planets/<id>.json via the integrator
    loaders + routing.compute_field_center — "identity travels with position" applies to
    memory alignment too: if a planet has drifted, memories that no longer sit where it
    orbits are treated as misaligned even if their content is fine.

    Returns report: {scanned, aligned, misaligned, skipped, files_changed}
    """
    import time as _time
    now_ts = float(now_ts) if now_ts is not None else _time.time()
    # Lazy imports keep `import sleep` cheap and LM-Studio-free at module load.
    import constants as C
    import integrator as I
    import routing as R

    try:
        planets = I.load_planets(base_dir)
        live_by_id = {p.id: p for p in planets}
    except Exception as exc:  # orbital state unavailable -> skip Pass I, never crash the nap
        return {"scanned": 0, "aligned": 0, "misaligned": 0,
                "skipped": -1, "files_changed": 0, "error": repr(exc)}

    # Owner field centers: blend each planet's semantic anchor (its identity direction in
    # the same space as entry positions) with its live orbital position. Using the anchor
    # instead of a 384-dim LLM wave center keeps this pass offline and fast — the anchor
    # IS the planet's fixed cognitive-space direction, which is exactly what "well-aligned"
    # means for spatial placement (Q2 approval).
    anchors = getattr(C, "SEMANTIC_ANCHORS", {}) or {}
    centers: dict[str, list[float]] = {}
    for pid, p in live_by_id.items():
        anchor = anchors.get(pid)
        if not anchor:
            continue
        lifted_pos = R._unit(R.axes_to_384(tuple(p.position)))  # type: ignore[attr-defined]
        w = float(getattr(C, "FIELD_POSITION_WEIGHT", 0.5))
        blended = [w * a + (1 - w) * lp for a, lp in zip(_unit(anchor), lifted_pos)]
        centers[pid] = R._unit(blended)

    report = {"scanned": 0, "aligned": 0, "misaligned": 0, "skipped": 0, "files_changed": 0}
    ring_files = [os.path.join(base_dir, "ring", "swarm.json"),
                  os.path.join(base_dir, "giants", "g1_knowledge.json"),
                  os.path.join(base_dir, "giants", "g2_selfmodel.json")]

    for path in ring_files:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("ring_buffer", []) or []
        changed = False
        for e in entries:
            pos = e.get("vector_position")
            owner = str(e.get("planet_id", "")).lower()
            center = centers.get(owner)
            if not pos or center is None:
                report["skipped"] += 1   # no position, unknown owner, or planet has no anchor
                continue
            report["scanned"] += 1
            align = max(-1.0, min(1.0, sum(a * b for a, b in zip(pos, center))))
            base_rate = float(e.get("decay_rate", 0.02))
            if align >= MICRO_SLEEP_ALIGN_THRESHOLD:
                # Relax toward the usage-frequency rate so aligned memories settle in.
                relaxed = base_rate / (1 + max(0, int(e.get("access_count", 0) or 0)))
                e["align_score"] = round(align, 4)
                if abs(float(e.get("decay_rate")) - relaxed) > 1e-9:
                    e["decay_rate"] = round(relaxed, 6)
                    changed = True
                report["aligned"] += 1
            else:
                # Misaligned: accelerate decay so Pass V light can shed them sooner.
                new_rate = min(base_rate * MICRO_SLEEP_MISALIGN_PENALTY, 0.5)
                e["align_score"] = round(align, 4)
                if abs(float(e.get("decay_rate")) - new_rate) > 1e-9:
                    e["decay_rate"] = round(new_rate, 6)
                    changed = True
                report["misaligned"] += 1
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            report["files_changed"] += 1
    return report


# ─── PASS V (LIGHT): MINIMUM MASS SWEEP ──────────────────────────────────────

def shed_low_mass(base_dir: str, now_ts: float | None = None, min_mass: float | None = None) -> dict:
    """Pass V (light): Dark Energy sweep. Apply age-based decay to every live store and
    move anything below the minimum mass threshold into compression_queue.json.

    This reuses memory.decay_sweep directly — it IS Pass V full, and for micro-sleep
    there is no difference: the shed list goes to the Black Hole queue either way.
    Kept as a thin wrapper so deep_sleep() can call the same name with different args
    (e.g. a stricter min_mass at final pass) without duplicating logic.
    """
    import memory as M  # lazy: decay_sweep lives in the Phase 4 module
    return M.decay_sweep(base_dir, now_ts=now_ts, min_mass=min_mass)


# ─── MICRO SLEEP (Segment 1 entry point) ─────────────────────────────────────

def micro_sleep(base_dir: str | None = None, now_ts: float | None = None) -> dict:
    """Micro-sleep ("nap"): fast, LLM-free, all planets stay awake.

    Sequence: Pass I light (ring alignment scan) + Pass V light (min-mass shed).
    No drift, no compression, no watchkeeper logic — that's deep sleep's job.
    Must complete in well under a second; it is called on 30-min idle / ~10 sessions /
    quick exit so it can never be the reason a session feels slow.

    Returns combined report: {"pass_i": {...}, "pass_v": {...}, "elapsed_s": float}
    """
    import time as _time
    if base_dir is None:
        base_dir = _HERE
    t0 = _time.time()
    pass_i = scan_ring_buffers(base_dir, now_ts=now_ts)
    pass_v = shed_low_mass(base_dir, now_ts=now_ts)
    elapsed = _time.time() - t0
    return {"pass_i": pass_i, "pass_v": pass_v, "elapsed_s": round(elapsed, 4)}


# ─── SEGMENT 2: WATCHKEEPER SELECTION ─────────────────────────────────────────

def select_watchkeepers(activation_weights: dict[str, float],
                        count: int | None = None,
                        min_count: int = 1) -> dict:
    """Select which planets stay awake during deep sleep.

    Chooses the top-N by recent activation weight (from routing or session totals).
    These planets remain responsive if the user types during sleep; all others enter
    full drift. Pure math, no disk writes — callers persist the locked set however
    they need to.

    Args:
        activation_weights: {planet_id: float} — higher = more recently/actively engaged.
            May include non-planet keys (e.g. "_core"); those are ignored.
        count: How many watchkeepers to select. Defaults to C.WATCHKEEPER_COUNT (2).
        min_count: Floor (always at least this many stay awake). Default 1.

    Returns:
        {"watchkeepers": [planet_id, ...], "asleep": [planet_id, ...],
         "weights_snapshot": {pid: weight}, "count": int}
    """
    import constants as C
    if count is None:
        count = int(getattr(C, "WATCHKEEPER_COUNT", 2))
    count = max(count, min_count)

    # Filter to known planet IDs only (ignore _core, comet triggers, etc.)
    valid = {pid: float(w) for pid, w in activation_weights.items()
             if not str(pid).startswith("_")}

    if not valid:
        # No weights provided — all planets stay awake (safe default).
        return {"watchkeepers": [], "asleep": [],
                "weights_snapshot": {}, "count": 0,
                "note": "no activation weights supplied; no planets locked for sleep"}

    ranked = sorted(valid.items(), key=lambda x: x[1], reverse=True)
    selected = [pid for pid, _ in ranked[:count]]
    all_pids = [pid for pid, _ in ranked]
    asleep = [pid for pid in all_pids if pid not in set(selected)]

    return {
        "watchkeepers": selected,
        "asleep": asleep,
        "weights_snapshot": dict(sorted(valid.items(), key=lambda x: x[1], reverse=True)),
        "count": len(selected),
    }


# ─── SEGMENT 3: PASS IV DRIFT ENGINE ──────────────────────────────────────────

# Drift bounds (kept local until full cycle lands; promote to constants.py later).
DRIFT_POSITION_MIN = 0.02   # minimum position nudge magnitude
DRIFT_POSITION_MAX = 0.10   # maximum position nudge magnitude
DRIFT_MASS_DELTA = 0.3      # max mass change per sleep (content absorbed)
DRIFT_TEMP_DELTA = 0.05     # cognitive mode param shift bounds
DRIFT_CTX_DELTA = 1         # context window exchanges +/-
DRIFT_COT_DELTA = 1         # CoT depth +/−
CORE_DRIFT_MAX = 0.05       # C_core nudge cap (drifts slower than planets)
RING_DRIFT_MAX = 0.01        # Ring persona personality_vector nudge cap per session
                              # (Phase 6 Seg 3: the face drifts LESS than even the Core —
                              #  it is the user's stable companion, not a moving body.)


def compute_drift(planet: "Planet",                   # type: ignore[name-defined]
                  session_consensus_3axis: tuple[float, float, float] | None,
                  activation_weight: float,
                  mass_delta_hint: float = 0.0,
                  g2_mode_suggestion: dict | None = None) -> dict:
    """Pass IV drift computation for ONE planet. Pure math — returns a commit dict.

    Does NOT write to disk (that's Segment 4's job). The returned dict contains the
    new values that `execute_deep_sleep` will apply via read-modify-write of the full
    planets/<id>.json file (preserving _semantic_anchor_guard, id_flavor, etc.).

    Drift direction: nudge position TOWARD the session consensus in 3-axis cognitive
    space. Planets that were more active get a proportionally larger nudge (they
    absorbed more of the conversation and should shift further toward where the
    discussion went). Planets with near-zero activation drift minimally.

    Args:
        planet: Live Planet dataclass (from integrator.load_planets).
        session_consensus_3axis: The session's consensus vector projected to 3-axis
            cognitive space (x=Rationality, y=Preservation, z=Outward). None if no
            session occurred (e.g. idle-only sleep) — in that case position drift is
            zero but cognitive-mode params can still shift.
        activation_weight: This planet's routing weight during the session (0..1).
            Scales the drift magnitude: high-activation planets move more.
        mass_delta_hint: How much "content" this planet absorbed (positive = gained,
            negative = shed). Clamped to DRIFT_MASS_DELTA. D-018 §8: content = mass.
        g2_mode_suggestion: Optional dict from G2 self-model with suggested cognitive
            mode adjustments, e.g. {"temperature": +0.03, "cot_depth": -1}.
            Applied if present; otherwise params stay unchanged.

    Returns commit dict:
        {
          "planet_id": str,
          "position": [x, y, z],         # new absolute position
          "mass": float,                  # new mass (clamped 2.0–4.5)
          "cognitive_mode": {"temperature": float, "context_window_exchanges": int,
                             "cot_depth": int, "prompt_structure": str},
          "drift_magnitude": float,       # L2 distance of position change (for logging)
        }
    """
    import random as _rng

    pid = planet.id
    pos = list(planet.position)  # [x, y, z]
    mass = float(planet.mass)
    cm = planet.cognitive_mode   # CognitiveModeConfig dataclass

    # ── Position drift: nudge toward session consensus, scaled by activation ──
    if session_consensus_3axis is not None and activation_weight > 0.01:
        cx, cy, cz = session_consensus_3axis
        # Direction from current position toward consensus.
        dx, dy, dz = (cx - pos[0], cy - pos[1], cz - pos[2])
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist > 1e-9:
            # Normalize direction, scale by activation-weight-proportional magnitude.
            # Full range DRIFT_POSITION_MIN..DRIFT_POSITION_MAX mapped to weight 0..1.
            mag = DRIFT_POSITION_MIN + (DRIFT_POSITION_MAX - DRIFT_POSITION_MIN) * min(activation_weight, 1.0)
            nx, ny, nz = dx / dist, dy / dist, dz / dist
            pos[0] += nx * mag
            pos[1] += ny * mag
            pos[2] += nz * mag
        drift_mag = mag
    else:
        # No session or negligible activation: tiny random jitter (prevents calcification).
        jitter_scale = 0.005
        pos[0] += _rng.uniform(-jitter_scale, jitter_scale)
        pos[1] += _rng.uniform(-jitter_scale, jitter_scale)
        pos[2] += _rng.uniform(-jitter_scale, jitter_scale)
        drift_mag = 0.0

    # ── Mass adjustment: content absorbed during session (None = no hint) ──
    hint_val = 0.0 if mass_delta_hint is None else mass_delta_hint
    mass_delta = max(-DRIFT_MASS_DELTA, min(DRIFT_MASS_DELTA, float(hint_val)))
    new_mass = round(max(2.0, min(4.5, mass + mass_delta)), 4)

    # ── Cognitive mode params: G2 suggestion or no change ──
    new_temp = cm.temperature
    new_ctx = cm.context_window_exchanges
    new_cot = cm.cot_depth
    if g2_mode_suggestion:
        dt = float(g2_mode_suggestion.get("temperature", 0.0))
        dc = int(g2_mode_suggestion.get("context_window_exchanges", 0))
        do_ = int(g2_mode_suggestion.get("cot_depth", 0))
        new_temp = round(max(0.1, min(1.5, cm.temperature + max(-DRIFT_TEMP_DELTA, min(DRIFT_TEMP_DELTA, dt)))), 3)
        new_ctx = max(1, min(7, cm.context_window_exchanges + max(-DRIFT_CTX_DELTA, min(DRIFT_CTX_DELTA, dc))))
        new_cot = max(0, min(4, cm.cot_depth + max(-DRIFT_COT_DELTA, min(DRIFT_COT_DELTA, do_))))

    return {
        "planet_id": pid,
        "position": [round(p, 6) for p in pos],
        "mass": new_mass,
        "cognitive_mode": {
            "temperature": new_temp,
            "context_window_exchanges": new_ctx,
            "cot_depth": new_cot,
            "prompt_structure": cm.prompt_structure,  # unchanged
        },
        "drift_magnitude": round(drift_mag, 6),
    }


def compute_core_drift(core: "CoreState",                     # type: ignore[name-defined]
                       session_consensus_3axis: tuple[float, float, float] | None) -> dict:
    """Pass IV drift for C_core. The Core is the anchor — it drifts SLOWER than planets.

    Max nudge: CORE_DRIFT_MAX (0.05). Direction same as planets (toward consensus).
    Returns {"position": [x,y,z], "drift_magnitude": float}.
    Never touches laws_file_path, G_value, M_base, or dissonance params.
    """
    import random as _rng
    pos = list(core.position)
    if session_consensus_3axis is not None:
        cx, cy, cz = session_consensus_3axis
        dx, dy, dz = (cx - pos[0], cy - pos[1], cz - pos[2])
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist > 1e-9:
            mag = CORE_DRIFT_MAX * min(1.0, dist / 5.0)  # scale down for far consensus
            pos[0] += (dx / dist) * mag
            pos[1] += (dy / dist) * mag
            pos[2] += (dz / dist) * mag
    else:
        jitter = 0.002
        pos[0] += _rng.uniform(-jitter, jitter)
        pos[1] += _rng.uniform(-jitter, jitter)
        pos[2] += _rng.uniform(-jitter, jitter)
    return {"position": [round(p, 6) for p in pos], "drift_magnitude": round(CORE_DRIFT_MAX, 6)}


def compute_ring_drift(personality_vector: list[float],
                       session_trend_3axis: tuple[float, float, float] | None,
                       sessions_since_last_drift: int = 1) -> dict:
    """Phase 6 Segment 3 — Pass IV drift for the RING (user-facing persona).

    The Ring is the face, not a moving body. It should feel like it *grows with you*
    but never lurches. So its personality_vector [x, y, z] takes at most ±RING_DRIFT_MAX
    (0.01) per committed drift — an order of magnitude smaller than the Core.

    DIRECTION (GUESS on exact axis signs — flagged for John's sanity check):
      session_trend_3axis is a small 3-axis summary of recent sessions:
        x = rationality/structure bias   (+ = more structured/planning)
        y = preservation/emotional-weight (+ = more relational, higher valence)
        z = outward/action bias         (+ = more active / less idle)
      The persona is nudged TOWARD the trend direction (the face leans into how you
      have actually been talking), scaled down by RING_DRIFT_MAX and softened further
      if many sessions piled up since the last commit (we don't want a big catch-up jump).

    Zero LLM calls. Pure math + bounded arithmetic.
    Returns {"personality_vector": [x,y,z], "drift_magnitude": float}.
    Never touches name, voice_notes, model_id, idle_state — only the vector.
    """
    pv = list(personality_vector)
    if session_trend_3axis is None:
        return {"personality_vector": [round(p, 6) for p in pv], "drift_magnitude": 0.0}

    tx, ty, tz = (float(v) for v in session_trend_3axis)
    tlen = math.sqrt(tx * tx + ty * ty + tz * tz)
    if tlen < 1e-9:
        return {"personality_vector": [round(p, 6) for p in pv], "drift_magnitude": 0.0}

    # Soften the nudge when many sessions accumulated since last commit (avoid a lurch).
    scale = max(0.25, 1.0 / float(max(1, sessions_since_last_drift)))
    mag = RING_DRIFT_MAX * min(1.0, tlen) * scale
    pv[0] += (tx / tlen) * mag
    pv[1] += (ty / tlen) * mag
    pv[2] += (tz / tlen) * mag
    # Keep the persona vector in a sane bounded box so drift can't wander off-scale.
    for i in range(3):
        pv[i] = max(-0.5, min(0.5, pv[i]))
    return {"personality_vector": [round(p, 6) for p in pv], "drift_magnitude": round(mag, 6)}


def _apply_ring_commit_to_disk(base_dir: str,
                               commit: dict) -> dict:
    """Phase 6 Segment 3 — read-modify-write ring/persona.json with a drift commit.

    Mirrors the isolated core-commit write path (its own third, self-contained branch;
    does NOT reuse _apply_commit_to_disk because that targets planets/<id>.json). Only
    personality_vector is touched; every other persona field is preserved byte-for-byte.
    Never raises on a missing file — logs and skips (a vanished ring is an S7 concern).
    Returns {"path", "applied", "changed_fields"}.
    """
    path = os.path.join(base_dir, "ring", "persona.json")
    if not os.path.exists(path):
        return {"path": path, "applied": False, "changed_fields": [],
                "note": "ring/persona.json missing; skipped"}
    with open(path, "r", encoding="utf-8") as f:
        pdata = json.load(f)

    changed: list[str] = []
    if "personality_vector" in commit and \
            commit["personality_vector"] != pdata.get("personality_vector"):
        pdata["personality_vector"] = [round(float(p), 6) for p in commit["personality_vector"]]
        changed.append("personality_vector")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(pdata, f, indent=2, ensure_ascii=False)
    return {"path": path, "applied": True, "changed_fields": changed}


# ─── SELF-TEST (Segment 1+2 — pure math, no LM Studio) ─────────────────────

def _self_test():
    import random
    import shutil
    import tempfile
    import time as _time

    print("sleep.py Segment 1 self-test: micro_sleep()")
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}")
        if not cond:
            failures.append(name)

    tmp = tempfile.mkdtemp(prefix="rc5s1_")
    try:
        random.seed(20260918)
        import constants as C

        # Build a synthetic base_dir with the store layout Phase 4 expects PLUS a minimal
        # planets/ snapshot so Pass I has live orbital state to read (separate-phase rule).
        for rel in ("memory", "ring", "planets"):
            os.makedirs(os.path.join(tmp, rel), exist_ok=True)
        for rel in ("memory/planet_vaults.json", "memory/stochastic_periphery.json",
                    "memory/compression_queue.json"):
            with open(os.path.join(tmp, *rel.split("/")), "w", encoding="utf-8") as f:
                json.dump({"entries": []}, f)

        # Minimal live planet state for the owner (sage): must satisfy load_planets schema.
        sage_pos = [6.0, 2.5, -1.5]
        with open(os.path.join(tmp, "planets", "sage.json"), "w", encoding="utf-8") as f:
            json.dump({"id": "sage", "archetype_name": "Sage", "position": sage_pos,
                       "velocity": [0.1, 0.2, -0.1], "mass": 3.0, "sigma": 1.2}, f)

        import routing as R
        anchor = list(C.SEMANTIC_ANCHORS["sage"])   # [1.0, 0.4, -0.5]
        lifted_pos = R._unit(R.axes_to_384(tuple(sage_pos)))
        w = float(getattr(C, "FIELD_POSITION_WEIGHT", 0.5))
        owner_center = R._unit([w * a + (1 - w) * lp for a, lp in zip(R._unit(anchor), lifted_pos)])

        # (a) Aligned entry: position points along the owner's CURRENT field center.
        aligned_pos = [c * 2.0 for c in owner_center]
        # (b) Misaligned entry: perpendicular to the owner's field center.
        u, v = owner_center[0], owner_center[1]
        perp = [-v / _norm([u, v]), u / _norm([u, v]), 0.0] if abs(u) + abs(v) > 1e-9 else [0.0, 1.0, 0.0]
        mis_pos = [p * 2.0 for p in perp]

        swarm_path = os.path.join(tmp, "ring", "swarm.json")
        with open(swarm_path, "w", encoding="utf-8") as f:
            json.dump({"entries": [], "ring_buffer": [
                {"entry_id": "aligned_1", "vector_position": aligned_pos,
                 "planet_id": "sage", "decay_rate": 0.02, "access_count": 5},
                {"entry_id": "misaligned_1", "vector_position": mis_pos,
                 "planet_id": "sage", "decay_rate": 0.02, "access_count": 0},
            ]}, f)

        # (c) Aged entries in the planet vault: one should survive Pass V, one must be shed.
        now = _time.time()
        old_alive_ts = now - 5 * 86400     # 5 days old at rate 0.02 -> mass ~0.90*orig (survives)
        old_dead_ts = now - 200 * 86400    # 200 days old at rate 0.02 -> mass ~0.016*orig (below 0.05 floor)
        vault_path = os.path.join(tmp, "memory", "planet_vaults.json")
        with open(vault_path, "w", encoding="utf-8") as f:
            json.dump({"entries": [
                {"entry_id": "alive_1", "vector_position": aligned_pos, "mass": 0.9,
                 "semantic_content": "old but still useful knowledge",
                 "creation_ts": old_alive_ts, "last_accessed": old_alive_ts,
                 "decay_rate": 0.02, "ring_membership": False, "zone": "planet_vault"},
                {"entry_id": "dead_1", "vector_position": mis_pos, "mass": 0.9,
                 "semantic_content": "ancient noise, long superseded",
                 "creation_ts": old_dead_ts, "last_accessed": old_dead_ts,
                 "decay_rate": 0.02, "ring_membership": False, "zone": "planet_vault"},
            ]}, f)

        t0 = _time.time()
        report = micro_sleep(base_dir=tmp, now_ts=now)
        elapsed = _time.time() - t0

        print(f"  elapsed: {elapsed:.4f}s")
        check("completes in < 1 second", elapsed < 1.0)
        check("returns combined report shape",
              set(report.keys()) == {"pass_i", "pass_v", "elapsed_s"})

        # Pass I assertions: aligned relaxed, misaligned accelerated.
        with open(swarm_path, encoding="utf-8") as f:
            swarm = json.load(f)
        by_id = {e["entry_id"]: e for e in swarm.get("ring_buffer", [])}
        a = by_id.get("aligned_1"); m = by_id.get("misaligned_1")
        check("Pass I scanned both ring entries", report["pass_i"]["scanned"] == 2)
        check("Pass I aligned count == 1", report["pass_i"]["aligned"] == 1)
        check("Pass I misaligned count == 1", report["pass_i"]["misaligned"] == 1)
        if a and m:
            # Aligned: rate relaxed by (1/(1+uses)) = 1/6 of base.
            expected_relaxed = round(0.02 / (1 + 5), 6)
            check(f"aligned decay_rate relaxed to {expected_relaxed}",
                  abs(a["decay_rate"] - expected_relaxed) < 1e-9)
            check("aligned align_score >= threshold", a.get("align_score", 0) >= MICRO_SLEEP_ALIGN_THRESHOLD)
            # Misaligned: rate accelerated by penalty (capped at 0.5).
            expected_accel = round(min(0.02 * MICRO_SLEEP_MISALIGN_PENALTY, 0.5), 6)
            check(f"misaligned decay_rate accelerated to {expected_accel}",
                  abs(m["decay_rate"] - expected_accel) < 1e-9)
            check("misaligned align_score below threshold", m.get("align_score", 1) < MICRO_SLEEP_ALIGN_THRESHOLD)

        # Pass V assertions: old dead entry shed, aged live entry mass changed on disk.
        with open(vault_path, encoding="utf-8") as f:
            vault = json.load(f)
        remaining_ids = [e["entry_id"] for e in vault.get("entries", [])]
        check("aged-but-surviving entry still present", "alive_1" in remaining_ids)
        check("below-min-mass entry shed from live store", "dead_1" not in remaining_ids)
        if "alive_1" in remaining_ids:
            alive = next(e for e in vault["entries"] if e["entry_id"] == "alive_1")
            expected_mass = round(0.9 * math.exp(-0.02 * 5), 6)
            check(f"surviving entry mass decayed on disk to {expected_mass}",
                  abs(alive["mass"] - expected_mass) < 1e-9)

        comp_path = os.path.join(tmp, "memory", "compression_queue.json")
        with open(comp_path, encoding="utf-8") as f:
            comp = json.load(f)
        check("shed entry landed in compression queue",
              any(e.get("entry_id") == "dead_1" for e in comp.get("entries", [])))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"Segment 1 self-test: {len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("Segment 1 self-test: PASS (micro_sleep = Pass I light + Pass V light, <1s, no LLM)")


# ─── SEGMENT 2 SELF-TEST ─────────────────────────────────────────────────────

def _self_test_s2():
    import random

    print("\nsleep.py Segment 2 self-test: select_watchkeepers()")
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}")
        if not cond:
            failures.append(name)

    import constants as C

    # Normal case: clear top-3 (prevents binary deadlock).
    weights = {"sage": 0.9, "hero": 0.7, "magician": 0.5,
               "caregiver": 0.3, "everyman": 0.2, "rebel": 0.1, "ruler": 0.05}
    r = select_watchkeepers(weights)
    check("selects top-3 by weight", r["watchkeepers"] == ["sage", "hero", "magician"])
    check("remaining 4 are asleep", len(r["asleep"]) == 4 and set(r["asleep"]) == {
        "caregiver", "everyman", "rebel", "ruler"})
    check("count matches WATCHKEEPER_COUNT (3)", r["count"] == int(C.WATCHKEEPER_COUNT) == 3)
    check("weights_snapshot has all 7", len(r["weights_snapshot"]) == 7)

    # Ties: stable ordering (first encountered wins on equal weight).
    tie_weights = {"sage": 0.5, "hero": 0.5, "magician": 0.5,
                   "caregiver": 0.2, "everyman": 0.1, "rebel": 0.1, "ruler": 0.05}
    r2 = select_watchkeepers(tie_weights)
    check("tie: all three top-weight planets selected", set(r2["watchkeepers"]) == {"sage", "hero", "magician"})

    # Fewer planets than count: all stay awake, none asleep.
    small = {"sage": 0.8, "hero": 0.6}
    r3 = select_watchkeepers(small)
    check("2 planets, count=3: both still watchkeepers (fewer than N)", set(r3["watchkeepers"]) == {"sage", "hero"})
    check("no one asleep with only 2 planets", r3["asleep"] == [])

    # Empty weights: safe default (all awake).
    r4 = select_watchkeepers({})
    check("empty weights: no watchkeepers locked", r4["watchkeepers"] == [])
    check("empty weights: note present", "note" in r4)

    # Non-planet keys ignored (jester_trigger has no _ prefix but isn't a planet —
    # in practice only the 7 known IDs appear; we filter by not-starting-with-underscore).
    mixed = {"sage": 0.9, "_core": 1.0, "hero": 0.7, "magician": 0.5}
    r5 = select_watchkeepers(mixed)
    check("non-planet keys excluded from selection",
          set(r5["watchkeepers"]) <= {"sage", "hero", "magician"})

    # Custom count override: ask for only 2.
    r6 = select_watchkeepers(weights, count=2)
    check("count=2 selects top 2 (override)", r6["watchkeepers"] == ["sage", "hero"])

    # Min-count floor: even if count param is 0, at least min_count stay awake.
    r7 = select_watchkeepers(weights, count=0, min_count=1)
    check("min_count=1 overrides count=0", len(r7["watchkeepers"]) == 1)

    print()
    if failures:
        print(f"Segment 2 self-test: {len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("Segment 2 self-test: PASS (select_watchkeepers = top-N by activation weight, pure math)")


# ─── SEGMENT 3 SELF-TEST ─────────────────────────────────────────────────────

def _self_test_s3():
    import random

    print("\nsleep.py Segment 3 self-test: compute_drift() + compute_core_drift()")
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}")
        if not cond:
            failures.append(name)

    from bodies import Planet, CoreState, CognitiveModeConfig
    random.seed(42)  # deterministic jitter for reproducibility

    # ── Planet drift: active planet with session consensus ──
    sage = Planet(id="sage", archetype_name="Sage", position=[5.0, 1.0, -2.0],
                  velocity=[0.1, 0.05, -0.05], mass=3.0, sigma=1.2,
                  cognitive_mode=CognitiveModeConfig(temperature=0.7, context_window_exchanges=3, cot_depth=2))
    consensus = (6.0, 2.0, -1.0)  # session went toward higher rationality + preservation
    commit = compute_drift(sage, consensus, activation_weight=0.9, mass_delta_hint=0.2)

    check("position moved toward consensus", 
          commit["position"][0] > sage.position[0])  # x increased (consensus.x > pos.x)
    check("drift magnitude within bounds",
          DRIFT_POSITION_MIN <= commit["drift_magnitude"] <= DRIFT_POSITION_MAX)
    check("mass increased by hint (clamped)", abs(commit["mass"] - 3.2) < 1e-6)
    check("cognitive_mode unchanged without G2 suggestion",
          commit["cognitive_mode"]["temperature"] == 0.7 and
          commit["cognitive_mode"]["cot_depth"] == 2)
    check("prompt_structure preserved", commit["cognitive_mode"]["prompt_structure"] == "standard")

    # ── Planet drift: low activation gets minimal nudge ──
    rebel = Planet(id="rebel", archetype_name="Rebel", position=[-3.0, -1.0, 4.0],
                   velocity=[-0.05, 0.1, 0.02], mass=2.5, sigma=0.9,
                   cognitive_mode=CognitiveModeConfig())
    commit_low = compute_drift(rebel, consensus, activation_weight=0.05)
    check("low-activation drift is near minimum",
          commit_low["drift_magnitude"] <= DRIFT_POSITION_MIN + 0.01)

    # ── Planet drift: no session (idle-only sleep) → jitter only ──
    everyman = Planet(id="everyman", archetype_name="Everyman", position=[0.5, -2.0, 1.0],
                      velocity=[0.0, 0.0, 0.0], mass=3.0, sigma=1.0,
                      cognitive_mode=CognitiveModeConfig())
    commit_idle = compute_drift(everyman, None, activation_weight=0.0)
    check("no-session: drift magnitude is 0 (jitter only)", commit_idle["drift_magnitude"] == 0.0)
    # Position changed slightly (jitter) but mass unchanged.
    pos_diff = sum((a - b) ** 2 for a, b in zip(commit_idle["position"], everyman.position)) ** 0.5
    check("no-session: position has tiny jitter (< 0.01)", 0 < pos_diff < 0.01)
    check("no-session: mass unchanged", commit_idle["mass"] == 3.0)

    # ── Mass clamping ──
    heavy = Planet(id="ruler", archetype_name="Ruler", position=[2.0, 2.0, 2.0],
                   velocity=[0, 0, 0], mass=4.4, sigma=1.5,
                   cognitive_mode=CognitiveModeConfig())
    commit_clamp = compute_drift(heavy, (3, 3, 3), activation_weight=1.0, mass_delta_hint=2.0)
    check("mass clamped at max 4.5", commit_clamp["mass"] <= 4.5)

    light = Planet(id="caregiver", archetype_name="Caregiver", position=[1.0, -3.0, 0.5],
                   velocity=[0, 0, 0], mass=2.1, sigma=1.0,
                   cognitive_mode=CognitiveModeConfig())
    commit_clamp_low = compute_drift(light, (0, -4, 1), activation_weight=1.0, mass_delta_hint=-5.0)
    check("mass clamped at min 2.0", commit_clamp_low["mass"] >= 2.0)

    # ── G2 mode suggestion applied within bounds ──
    magician = Planet(id="magician", archetype_name="Magician", position=[-1.0, 3.0, -0.5],
                      velocity=[0, 0, 0], mass=3.2, sigma=1.1,
                      cognitive_mode=CognitiveModeConfig(temperature=0.7, context_window_exchanges=3, cot_depth=1))
    commit_g2 = compute_drift(magician, (0, 2, 0), activation_weight=0.5,
                              g2_mode_suggestion={"temperature": +0.04, "cot_depth": +1})
    check("G2 suggestion: temp increased within bounds",
          abs(commit_g2["cognitive_mode"]["temperature"] - 0.74) < 1e-6)
    check("G2 suggestion: cot_depth increased by 1", commit_g2["cognitive_mode"]["cot_depth"] == 2)

    # G2 suggestion clamped at bounds.
    commit_g2_clamp = compute_drift(magician, (0, 2, 0), activation_weight=0.5,
                                    g2_mode_suggestion={"temperature": +1.0, "cot_depth": +9})
    check("G2 clamp: temp capped at +DRIFT_TEMP_DELTA",
          commit_g2_clamp["cognitive_mode"]["temperature"] <= 0.75 + 1e-6)
    check("G2 clamp: cot_depth capped at +DRIFT_COT_DELTA", 
          commit_g2_clamp["cognitive_mode"]["cot_depth"] == 2)

    # ── Core drift: slower than planets ──
    core = CoreState(position=[0.1, -0.8, -0.3], G_value=5.0, M_base=10.0,
                     dissonance_alpha=1.2, dissonance_beta=1.8, well_depth=2.5,
                     session_counter=42, laws_file_path="core_laws.json")
    core_commit = compute_core_drift(core, (3.0, 1.0, 0.5))
    core_dx = sum((a - b) ** 2 for a, b in zip(core_commit["position"], core.position)) ** 0.5
    check("core drift magnitude <= CORE_DRIFT_MAX", core_dx <= CORE_DRIFT_MAX + 1e-6)
    check("core moved toward consensus (x increased)", core_commit["position"][0] > core.position[0])

    # Core with no session: tiny jitter only.
    core_idle = compute_core_drift(core, None)
    core_idle_dx = sum((a - b) ** 2 for a, b in zip(core_idle["position"], core.position)) ** 0.5
    check("core idle: drift is minimal (< 0.01)", core_idle_dx < 0.01)

    print()
    if failures:
        print(f"Segment 3 self-test: {len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("Segment 3 self-test: PASS (compute_drift + compute_core_drift = pure math, bounded, no disk)")


# ─── SEGMENT 4: STAGGERED COMMIT + PERSISTENCE (ROTATING SHIFT) ──────────────
#
# John's rotating shift schedule (approved this session; documented in Build Plan):
#   Rank all 7 planets by activation weight, most active = rank 1.
#     Wave 1 : ranks 5–7 sleep          → 4 awake
#     Wave 2 : wave-1 wakes; ranks 2–4 sleep → 4 awake (wave-1 trio + ranks 1 & 5…)
#     Wave 3 : wave-2 wakes; rank 1 sleeps alone  → 6 awake, 1 sleeping
#
# Invariant: the system NEVER drops below 4 planets awake.
# Every planet gets exactly one sleep turn per deep-sleep cycle.
#
# Persistence rule (the load-bearing part):
#   Each commit is a READ-MODIFY-WRITE of the WHOLE planets/<id>.json dict. We
#   mutate position / mass / cognitive_mode in place and write the full dict back,
#   so _semantic_anchor_guard, semantic_anchor, id_flavor, ego_descriptor and any
#   future fields survive untouched. We NEVER reconstruct a planet from the
#   dataclass (that would drop unknown keys). core_laws.json and gates_config.json
#   are never opened for write by anything in this module.

# Planet IDs the system knows about (single source of truth for sleep scheduling).
_KNOWN_PLANET_IDS = ["sage", "magician", "caregiver", "hero",
                     "everyman", "rebel", "ruler"]


def _planetary_ranking(activation_weights: dict[str, float]) -> list[str]:
    """Rank planet IDs most-active → least-active. Ties break alphabetically for
    determinism (same input always yields the same schedule). Planets missing from
    the weights dict are treated as weight 0 and ranked after all weighted ones."""
    scored = sorted(
        ((pid, float(activation_weights.get(pid, 0.0))) for pid in _KNOWN_PLANET_IDS),
        key=lambda x: (-x[1], x[0]),
    )
    return [pid for pid, _ in scored]


def compute_rotating_shift(activation_weights: dict[str, float]) -> list[list[str]]:
    """Build the 3-wave rotating sleep schedule (pure math).

    Returns a list of 3 waves; each wave is the list of planet IDs that sleep in it.
    Wave sizes are always [3, 3, 1] for 7 planets. Fewer planets degrade gracefully:
    we never wake someone who hasn't slept and we never sleep more than half the
    system (floor(awake) >= 4 whenever 7 planets exist).
    """
    ranked = _planetary_ranking(activation_weights)
    n = len(ranked)

    # John's exact schedule (7 planets): sleep the 3 LEAST-active each wave, and
    # always rank by CURRENT activity — so the most recent activity re-orders who
    # sleeps next. With 7 planets that yields waves of [3, 3, 1]:
    #   Wave 1: ranks 5–7 sleep (least active) → 4 awake
    #   Wave 2: wave-1 wakes; the new least-active 3 of the remaining sleep → 4 awake
    #   Wave 3: the single most-recently-active planet sleeps alone → 6 awake, 1 sleeping
    if n == 7:
        w1 = ranked[-3:]
        rem1 = [p for p in ranked if p not in set(w1)]
        w2 = rem1[-3:]
        rem2 = [p for p in rem1 if p not in set(w2)]  # the single most-active planet
        return [w1, w2, rem2]

    # Degraded systems (< 7 planets): same "least-active trio" rule, floored so the
    # system never drops below half awake.
    if n <= 3:
        return [ranked[max(0, n - (n // 2 or 1)):], ranked[:max(0, n - (n // 2 or 1))]]
    # n == 4 or 5 or 6: sleep the least-active ceil(n/2)-ish group in two waves.
    half = max(1, n // 2)
    w1 = ranked[n - half:] if n > 3 else []
    rem = [p for p in ranked if p not in set(w1)]
    return [w for w in (list(w1), list(rem)) if w]


def _apply_commit_to_disk(base_dir: str, planet_id: str,
                          commit: dict) -> dict:
    """Read-modify-write ONE planets/<id>.json with a drift commit.

    Returns {"path": ..., "applied": bool, "changed_fields": [...]}. Never raises on
    missing file — logs and skips (a planet that vanished mid-sleep is an S7 concern,
    not a crash reason). The JSON dict is the source of truth; dataclass fields are
    only used to know WHICH keys to touch.
    """
    path = os.path.join(base_dir, "planets", f"{planet_id}.json")
    if not os.path.exists(path):
        return {"path": path, "applied": False, "changed_fields": [],
                "note": "planet file missing; skipped"}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    changed: list[str] = []
    # Position
    if "position" in commit and commit["position"] != data.get("position"):
        data["position"] = [round(float(p), 6) for p in commit["position"]]
        changed.append("position")
    # Mass (clamped by compute_drift already; clamp again defensively)
    if "mass" in commit and abs(commit["mass"] - float(data.get("mass", 3.0))) > 1e-9:
        data["mass"] = round(min(4.5, max(2.0, float(commit["mass"]))), 6)
        changed.append("mass")
    # Cognitive mode — mutate the SUB-OBJECT in place; never replace sibling keys.
    cm_in = commit.get("cognitive_mode") or {}
    if cm_in:
        cm_out = data.setdefault("cognitive_mode", {})
        for key, val in cm_in.items():
            if val is None:
                continue
            cur = cm_out.get(key)
            if isinstance(val, int) and not isinstance(cur, bool):
                new_val: object = int(val)
            elif isinstance(val, float):
                new_val = round(float(val), 6)
            else:
                new_val = val
            if new_val != cur:
                cm_out[key] = new_val
                changed.append(f"cognitive_mode.{key}")
    # sigma is drift-invariant (semantic volume set at init) — never touched here.

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"path": path, "applied": True, "changed_fields": changed}


def execute_deep_sleep(base_dir: str,
                       activation_weights: dict[str, float],
                       session_consensus_3axis: tuple[float, float, float] | None = None,
                       mass_delta_hints: dict[str, float] | None = None,
                       g2_mode_suggestions: dict[str, dict] | None = None,
                       core_commit: dict | None = None,
                       ring_personality_vector: list[float] | None = None,
                       sessions_since_last_ring_drift: int = 1,
                       stagger_seconds: float | None = None) -> dict:
    """Segment 4: commit drift to disk using the rotating shift schedule.

    Pure math + file I/O — zero LLM calls. Steps:
      1. Build the 3-wave rotating shift from activation weights (never <4 awake).
      2. For each wave, in order: compute_drift() for every sleeping planet, then
         staggered _apply_commit_to_disk() (STAGGER_INTERVAL_SECONDS apart by default;
         pass stagger_seconds=0 to skip waiting — used by tests).
      3. Apply the core commit (from compute_core_drift) last; C_core is already
         bounded at CORE_DRIFT_MAX inside that function.
      4. Return a full report: waves, per-planet applied fields, timing, invariants.

    Invariants asserted on return:
      - every planet slept exactly once across all waves (7 unique IDs)
      - >= 4 planets awake during each wave (for the standard 7-planet system)
      - core_laws.json / gates_config.json were never opened for write (this module
        has no code path that opens them — verified by S7's byte-identical check)
    """
    import time as _time
    import constants as C

    if stagger_seconds is None:
        stagger_seconds = float(getattr(C, "STAGGER_INTERVAL_SECONDS", 5))

    waves = compute_rotating_shift(activation_weights)
    mass_delta_hints = mass_delta_hints or {}
    g2_mode_suggestions = g2_mode_suggestions or {}

    report: dict = {
        "started_at": _time.time(),
        "waves": [],
        "applied": {},          # planet_id -> {changed_fields, drift_magnitude}
        "skipped": {},
        "core_applied": False,
        "ring_applied": False,
        "invariants": {},
    }

    all_slept: list[str] = []
    for wave_idx, wave in enumerate(waves):
        # Awake during this wave: everyone minus those sleeping NOW (previous waves woke).
        awake_now = [p for p in _KNOWN_PLANET_IDS if p not in set(wave)]
        wave_report = {"wave": wave_idx + 1, "sleeping": list(wave),
                       "awake_count": len(awake_now)}
        t_wave_start = _time.time()
        for i, pid in enumerate(wave):
            from bodies import Planet
            path = os.path.join(base_dir, "planets", f"{pid}.json")
            if not os.path.exists(path):
                report["skipped"][pid] = "planet file missing"
                continue
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            cm = raw.get("cognitive_mode", {})
            from bodies import CognitiveModeConfig
            planet = Planet(
                id=raw["id"], archetype_name=raw["archetype_name"],
                position=list(raw["position"]), velocity=list(raw.get("velocity", [0, 0, 0])),
                mass=float(raw.get("mass", 3.0)), sigma=float(raw.get("sigma", 1.0)),
                cognitive_mode=CognitiveModeConfig(
                    temperature=cm.get("temperature", 0.7),
                    context_window_exchanges=cm.get("context_window_exchanges", 3),
                    cot_depth=cm.get("cot_depth", 1),
                    prompt_structure=cm.get("prompt_structure", "standard")),
                id_flavor=raw.get("id_flavor", ""),
                ego_descriptor=raw.get("ego_descriptor", ""),
                superego_principle=raw.get("superego_principle", ""),
                orbital_plane_tilt_deg=raw.get("orbital_plane_tilt_deg", 0.0),
            )
            commit = compute_drift(
                planet, session_consensus_3axis,
                activation_weight=float(activation_weights.get(pid, 0.0)),
                mass_delta_hint=mass_delta_hints.get(pid),
                g2_mode_suggestion=g2_mode_suggestions.get(pid),
            )
            apply_res = _apply_commit_to_disk(base_dir, pid, commit)
            (report["applied"] if apply_res["applied"] else report["skipped"])[pid] = \
                {k: v for k, v in apply_res.items() if k != "path"} | {
                    "drift_magnitude": commit.get("drift_magnitude", 0.0)}
            all_slept.append(pid)
            # Stagger (skip the wait after the last planet in the wave).
            if i < len(wave) - 1 and stagger_seconds > 0:
                _time.sleep(stagger_seconds)
        wave_report["elapsed_s"] = round(_time.time() - t_wave_start, 3)
        report["waves"].append(wave_report)

    # Core commit last (already bounded by compute_core_drift at CORE_DRIFT_MAX).
    if core_commit and "position" in core_commit:
        core_path = os.path.join(base_dir, "core", "core_state.json")
        if os.path.exists(core_path):
            with open(core_path, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            cdata["position"] = [round(float(p), 6) for p in core_commit["position"]]
            # session_counter is bumped by the runtime, NOT by sleep — never touch it.
            with open(core_path, "w", encoding="utf-8") as f:
                json.dump(cdata, f, indent=2, ensure_ascii=False)
            report["core_applied"] = True
        else:
            report["skipped"]["_core"] = "core_state.json missing"
    elif core_commit is None and session_consensus_3axis is not None:
        # No pre-computed core commit supplied — compute one inline (bounded).
        from bodies import CoreState
        core_path = os.path.join(base_dir, "core", "core_state.json")
        if os.path.exists(core_path):
            with open(core_path, "r", encoding="utf-8") as f:
                cdata = json.load(f)
            core = CoreState(
                position=list(cdata["position"]), G_value=cdata.get("G_value", 5.0),
                M_base=cdata.get("M_base", 10.0),
                dissonance_alpha=cdata.get("dissonance_alpha", 1.2),
                dissonance_beta=cdata.get("dissonance_beta", 1.8),
                well_depth=cdata.get("well_depth", 2.5),
                session_counter=int(cdata.get("session_counter", 0)),
                laws_file_path=cdata.get("laws_file_path", "core_laws.json"))
            ccommit = compute_core_drift(core, session_consensus_3axis)
            cdata["position"] = [round(float(p), 6) for p in ccommit["position"]]
            with open(core_path, "w", encoding="utf-8") as f:
                json.dump(cdata, f, indent=2, ensure_ascii=False)
            report["core_applied"] = True
    report["core_drift_magnitude"] = (core_commit or {}).get("drift_magnitude",
        0.0) if core_commit else None

    # Ring commit last of all — isolated third write path (Phase 6 Segment 3).
    # The persona's personality_vector is nudged <= RING_DRIFT_MAX toward the recent
    # session trend, then committed via its own _apply_ring_commit_to_disk(). This
    # branch NEVER touches planets/, core/, or any sentinel file.
    if ring_personality_vector is not None and session_consensus_3axis is not None:
        rcommit = compute_ring_drift(ring_personality_vector, session_consensus_3axis,
                                     sessions_since_last_ring_drift)
        res = _apply_ring_commit_to_disk(base_dir, {"personality_vector": rcommit["personality_vector"]})
        report["ring_applied"] = bool(res.get("applied", False))
        report["ring_changed_fields"] = res.get("changed_fields", [])
        report["ring_drift_magnitude"] = rcommit.get("drift_magnitude", 0.0)

    # Invariants.
    unique_slept = list(dict.fromkeys(all_slept))
    known_present = [p for p in _KNOWN_PLANET_IDS
                     if os.path.exists(os.path.join(base_dir, "planets", f"{p}.json"))]
    min_awake = min((len(set(_KNOWN_PLANET_IDS) - set(w["sleeping"])) for w in report["waves"]),
                    default=0)
    report["invariants"] = {
        "each_planet_slept_once": unique_slept == sorted(unique_slept, key=all_slept.index)
            and len(set(all_slept)) == len(all_slept),
        "all_present_planets_covered": set(unique_slept) >= set(known_present),
        "min_awake_during_any_wave": min_awake,
    }
    report["elapsed_total_s"] = round(_time.time() - report["started_at"], 3)
    return report


# ─── SEGMENT 4 SELF-TEST ─────────────────────────────────────────────────────

def _self_test_s4():
    import shutil
    import tempfile
    from bodies import CognitiveModeConfig, Planet

    print("\nsleep.py Segment 4 self-test: compute_rotating_shift() + execute_deep_sleep()")
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}")
        if not cond:
            failures.append(name)

    # ── Schedule shape: John's exact rotating shift for the standard 7-planet system.
    weights = {"sage": 0.9, "hero": 0.8, "magician": 0.6,
               "caregiver": 0.4, "everyman": 0.3, "rebel": 0.2, "ruler": 0.1}
    waves = compute_rotating_shift(weights)
    check("3 waves produced", len(waves) == 3)
    # Rank order: sage(1) hero(2) magician(3) caregiver(4) everyman(5) rebel(6) ruler(7)
    check("wave 1 sleeps ranks 5–7 (least active trio)",
          set(waves[0]) == {"everyman", "rebel", "ruler"})
    check("wave 2 sleeps ranks 2–4", set(waves[1]) == {"hero", "magician", "caregiver"})
    check("wave 3 sleeps rank 1 (most active) alone", waves[2] == ["sage"])
    # Every planet exactly once.
    all_slept = waves[0] + waves[1] + waves[2]
    check("each of the 7 planets sleeps exactly once",
          len(set(all_slept)) == 7 and sorted(all_slept) == sorted(_KNOWN_PLANET_IDS))
    # Never below 4 awake.
    for i, w in enumerate(waves):
        awake = len(set(_KNOWN_PLANET_IDS) - set(w))
        check(f"wave {i+1}: awake count >= 4 (got {awake})", awake >= 4)

    # Determinism: same weights → identical schedule.
    waves_again = compute_rotating_shift(dict(reversed(list(weights.items()))))
    check("schedule is deterministic (dict order doesn't matter)", waves == waves_again)

    # Ties handled without crash or duplicate sleeps.
    tie_w = {p: 0.5 for p in _KNOWN_PLANET_IDS}
    tw = compute_rotating_shift(tie_w)
    check("all-tied weights still sleep each planet exactly once",
          len(set(sum(tw, []))) == 7 and len(sum(tw, [])) == 7)

    # ── Disk round-trip: build a synthetic base_dir from the REAL planet schemas.
    tmp = tempfile.mkdtemp(prefix="rc5s4_")
    try:
        import constants as C
        for rel in ("memory", "ring", "planets", "core"):
            os.makedirs(os.path.join(tmp, rel), exist_ok=True)
        for rel in ("memory/planet_vaults.json", "memory/stochastic_periphery.json",
                    "memory/compression_queue.json", "ring/swarm.json"):
            with open(os.path.join(tmp, *rel.split("/")), "w", encoding="utf-8") as f:
                json.dump({"entries": []}, f)
        # core_laws + gates_config sentinels — must be byte-identical after sleep.
        sentinel_blobs = {"core/core_laws.json": b'{"laws": ["sentinel-law"]}',
                          "gates/gates_config.json": b'{"pii_enabled": true}'}
        for rel, blob in sentinel_blobs.items():
            os.makedirs(os.path.dirname(os.path.join(tmp, *rel.split("/"))), exist_ok=True)
            with open(os.path.join(tmp, *rel.split("/")), "wb") as f:
                f.write(blob)

        # Seven planet files in the exact on-disk schema (incl. guard + anchor).
        for i, pid in enumerate(_KNOWN_PLANET_IDS):
            data = {
                "id": pid, "archetype_name": pid.title(),
                "position": [float(i) - 2.0, float(-i) * 0.5, 1.0 + i * 0.1],
                "velocity": [0.1, -0.05, 0.02],
                "mass": round(2.4 + i * 0.3, 3), "sigma": 1.0,
                "cognitive_mode": {"temperature": 0.7, "context_window_exchanges": 3,
                                   "cot_depth": 1, "prompt_structure": "standard"},
                "id_flavor": f"flavor-{pid}", "ego_descriptor": f"ego-{pid}",
                "superego_principle": f"principle-{pid}",
                "orbital_plane_tilt_deg": float(i),
                "semantic_anchor": list(C.SEMANTIC_ANCHORS[pid]),
                "_semantic_anchor_guard": "DO NOT MODIFY — semantic identity",
            }
            with open(os.path.join(tmp, "planets", f"{pid}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        core_state = {"position": [0.1, -0.8, -0.3], "G_value": 5.0, "M_base": 10.0,
                      "dissonance_alpha": 1.2, "dissonance_beta": 1.8, "well_depth": 2.5,
                      "session_counter": 42, "laws_file_path": "core_laws.json",
                      "genesis_state": {"version": "17.0.0", "sentinel": True}}
        with open(os.path.join(tmp, "core", "core_state.json"), "w", encoding="utf-8") as f:
            json.dump(core_state, f, indent=2)

        pre = {}
        for pid in _KNOWN_PLANET_IDS:
            with open(os.path.join(tmp, "planets", f"{pid}.json"), encoding="utf-8") as f:
                pre[pid] = json.load(f)
        with open(os.path.join(tmp, "core", "core_state.json"), encoding="utf-8") as f:
            core_pre = json.load(f)

        # Run the full staggered commit (stagger=0 for test speed).
        report = execute_deep_sleep(
            tmp, weights,
            session_consensus_3axis=(4.0, 1.5, -0.5),
            mass_delta_hints={"sage": 0.2},
            g2_mode_suggestions={"hero": {"temperature": +0.04}},
            stagger_seconds=0,
        )

        check("all 7 planets applied, none skipped", len(report["applied"]) == 7 and not report["skipped"])
        check("core commit applied", report["core_applied"] is True)
        inv = report["invariants"]
        check("invariant: each planet slept exactly once", inv["each_planet_slept_once"])
        check("invariant: all present planets covered", inv["all_present_planets_covered"])
        check("invariant: min awake during any wave >= 4", inv["min_awake_during_any_wave"] >= 4)

        # Post-sleep disk state.
        moved = preserved = mass_changed = cm_changed = 0
        for pid in _KNOWN_PLANET_IDS:
            with open(os.path.join(tmp, "planets", f"{pid}.json"), encoding="utf-8") as f:
                post = json.load(f)
            # Every planet's position moved (drift or jitter is always non-zero).
            if post["position"] != pre[pid]["position"]:
                moved += 1
            # Identity fields survive byte-for-byte.
            for key in ("semantic_anchor", "_semantic_anchor_guard", "id_flavor",
                        "ego_descriptor", "superego_principle", "orbital_plane_tilt_deg"):
                assert post[key] == pre[pid][key], f"{pid}.{key} clobbered!"
            else:
                pass
            if all(post[k] == pre[pid][k] for k in ("semantic_anchor", "_semantic_anchor_guard",
                                                    "id_flavor", "ego_descriptor",
                                                    "superego_principle", "orbital_plane_tilt_deg")):
                preserved += 1
            if abs(post["mass"] - pre[pid]["mass"]) > 1e-9:
                mass_changed += 1
            if post["cognitive_mode"] != pre[pid]["cognitive_mode"]:
                cm_changed += 1
        check(f"all 7 positions changed on disk (moved={moved})", moved == 7)
        check("identity fields preserved for all 7 planets", preserved == 7)
        check("sage mass bumped by its hint", abs(pre["sage"]["mass"] + 0.2 - \
              json.load(open(os.path.join(tmp, 'planets', 'sage.json'), encoding='utf-8'))["mass"]) < 1e-6)
        check("hero cognitive_mode temp shifted by G2 suggestion", cm_changed >= 1)

        with open(os.path.join(tmp, "core", "core_state.json"), encoding="utf-8") as f:
            core_post = json.load(f)
        cdx = sum((a - b) ** 2 for a, b in zip(core_post["position"], core_pre["position"])) ** 0.5
        check("core position nudged within CORE_DRIFT_MAX", 0 < cdx <= CORE_DRIFT_MAX + 1e-6)
        check("core session_counter untouched by sleep", core_post["session_counter"] == 42)
        check("core genesis_state sentinel intact", core_post.get("genesis_state", {}).get("sentinel") is True)

        # Sentinel files byte-identical.
        for rel, blob in sentinel_blobs.items():
            with open(os.path.join(tmp, *rel.split("/")), "rb") as f:
                check(f"{rel} byte-identical after sleep", f.read() == blob)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"Segment 4 self-test: {len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("Segment 4 self-test: PASS (rotating shift + staggered read-modify-write, identity preserved)")


# ─── SEGMENT 5: PASS II COMPRESSION + PASS III EMISSION ──────────────────────
#
# The Black Hole (compression_queue.json) is where Pass V sheds memories that fell
# below MIN_ENTRY_MASS. Segment 5 processes that queue in two passes, zero LLM:
#
#   Pass II — COMPRESSION: near-duplicate entries merge into one survivor.
#     "Similar" = cosine position alignment >= COMPRESS_SIMILARITY (0.92) OR
#     normalized text overlap >= COMPRESS_TEXT_OVERLAP (0.85). The survivor is the
#     HIGHEST-mass member; it absorbs the sum of members' masses (capped at
#     4.5 so a merged memory can't outmass any living planet), inherits the most
#     recent last_accessed, and gains compression metadata (merged_from list with
#     ids + final masses — full provenance for audit).
#
#   Pass III — EMISSION: survivors whose compressed mass reaches COMPRESS_PROMOTE_MASS
#     (0.6) are re-promoted into their ORIGINAL zone at REDUCED mass (× 0.5). Rationale:
#     a memory that kept re-shedding had real weight but stale freshness — it comes
#     back with the accumulated substance and half the influence, so it competes on
#     merit again instead of instantly reclaiming its old rank.
#
#   Everything else stays in the queue (the Black Hole keeps what isn't worth
#   merging or re-promoting yet). The queue is rewritten atomically: load →
#   transform → save, same as every other store touch in this codebase.

COMPRESS_SIMILARITY = 0.92      # cosine(vector_position_a, vector_position_b) merge threshold
COMPRESS_TEXT_OVERLAP = 0.85    # token-set overlap ratio on semantic_content (lowercased)
COMPRESS_PROMOTE_MASS = 0.6     # compressed-mass floor for re-promotion to a live store
COMPRESS_REPROMOTE_FACTOR = 0.5 # mass multiplier applied at re-promotion
MAX_COMPRESSED_MASS = 4.5       # merged memories can't outmass the biggest planet


def _cosine(a, b) -> float:
    """Cosine similarity between two equal-length vectors; 0 for degenerate inputs."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = _norm(list(a)), _norm(list(b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return dot / (na * nb)


def _text_overlap_ratio(ua: str, ub: str) -> float:
    """Jaccard-style overlap of token SETS (lowercased). Two phrasings of the same
    fact share most tokens; unrelated content shares few. Empty strings → 0."""
    ta = set(str(ua or "").lower().split())
    tb = set(str(ub or "").lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _merge_cluster(members: list[dict]) -> dict:
    """Collapse a cluster of similar entries into ONE survivor (highest mass).

    Provenance is preserved in `compressed_from`: [{entry_id, final_mass}] for every
    absorbed member. The survivor keeps its own semantic_content / vector_position /
    decay_rate / zone / ring_membership — it was the strongest voice in the cluster.
    """
    members = sorted(members, key=lambda e: float(e.get("mass", 0.0)), reverse=True)
    survivor = dict(members[0])
    total_mass = sum(float(e.get("mass", 0.0)) for e in members)
    absorbed = [m for m in members[1:]]
    survivor["mass"] = round(min(MAX_COMPRESSED_MASS, total_mass), 6)
    survivor["last_accessed"] = max(float(e.get("last_accessed", 0.0)) for e in members)
    survivor["compressed_from"] = [
        {"entry_id": e.get("entry_id", "?"), "final_mass": round(float(e.get("mass", 0.0)), 6)}
        for e in absorbed
    ]
    survivor["compression_ts"] = max(float(e.get("last_accessed", 0.0)) for e in members)
    return survivor


def _group_similar(entries: list[dict]) -> list[list[dict]]:
    """Greedy first-match clustering (queue is small — shed memories, not the whole
    system). Deterministic: entries are processed in their stored order."""
    clusters: list[list[dict]] = []
    for e in entries:
        placed = False
        for cl in clusters:
            rep = cl[0]
            if (_cosine(e.get("vector_position", []), rep.get("vector_position", []))
                    >= COMPRESS_SIMILARITY or
                _text_overlap_ratio(e.get("semantic_content", ""),
                                    rep.get("semantic_content", "")) >= COMPRESS_TEXT_OVERLAP):
                cl.append(e)
                placed = True
                break
        if not placed:
            clusters.append([e])
    return clusters


def _zone_path_for_entry(base_dir: str, entry: dict) -> str | None:
    """Map an entry's zone back to the live store file it came from. Mirrors
    memory.ZONE_FILE_REL but stays self-contained (sleep.py must not import memory).
    Returns None for unknown zones — those stay in the queue forever."""
    zone = entry.get("zone", "")
    mapping = {
        "planet_vault": os.path.join(base_dir, "memory", "planet_vaults.json"),
        "ring_swarm": os.path.join(base_dir, "ring", "swarm.json"),
        "stochastic_periphery": os.path.join(base_dir, "memory", "stochastic_periphery.json"),
    }
    return mapping.get(zone)


def process_compression_queue(base_dir: str) -> dict:
    """Segment 5 entry point: Pass II (merge) + Pass III (re-promote) on the queue.

    Pure math + file I/O. Returns a report with per-step counts and the ids of
    everything merged / re-promoted / kept, so S7 can assert exact outcomes.
    """
    import memory as M  # for zone constants only (single source of truth)
    comp_path = os.path.join(base_dir, "memory", "compression_queue.json")
    queue = json.load(open(comp_path, encoding="utf-8")) if os.path.exists(comp_path) else {"entries": []}
    entries = list(queue.get("entries", []))

    report = {
        "queue_size_in": len(entries),
        "clusters_found": 0,
        "merged_clusters": 0,
        "absorbed_entries": [],
        "survivors": [],
        "re_promoted": [],   # [{entry_id, zone, emitted_mass}]
        "kept_in_queue": [],
        "queue_size_out": 0,
    }

    if not entries:
        return report

    # ── Pass II: compress near-duplicates.
    clusters = _group_similar(entries)
    report["clusters_found"] = len(clusters)
    survivors: list[dict] = []
    for cl in clusters:
        if len(cl) == 1:
            survivors.append(dict(cl[0]))
        else:
            merged = _merge_cluster(cl)
            absorbed_ids = [m.get("entry_id", "?") for m in cl]
            report["merged_clusters"] += 1
            report["absorbed_entries"].extend(
                i for i in absorbed_ids if i != merged.get("compressed_from") and i)
            survivors.append(merged)
    # (entry_id of the survivor itself is NOT absorbed; only its cluster-mates are.)
    report["absorbed_entries"] = [
        a for a in report["absorbed_entries"] if True
    ]  # ids already exclude nothing — recompute cleanly below instead.

    # Clean recomputation of absorbed ids (explicit, testable):
    absorbed: list[str] = []
    survivors2: list[dict] = []
    for cl in clusters:
        if len(cl) == 1:
            s = dict(cl[0])
            survivors2.append(s)
        else:
            merged = _merge_cluster(cl)
            absorbed.extend(m.get("entry_id", "?") for m in cl
                            if m.get("entry_id") != merged.get("entry_id"))
            survivors2.append(merged)
    report["absorbed_entries"] = sorted(set(absorbed))
    survivors = survivors2

    # ── Pass III: re-promote heavy compressed survivors (reduced mass).
    remaining_in_queue: list[dict] = []
    for s in survivors:
        if float(s.get("mass", 0.0)) >= COMPRESS_PROMOTE_MASS and "compressed_from" in s:
            target = _zone_path_for_entry(base_dir, s)
            if target is None:
                remaining_in_queue.append(s)   # unknown zone → stays parked
                continue
            emitted_mass = round(min(MAX_COMPRESSED_MASS,
                                     float(s["mass"]) * COMPRESS_REPROMOTE_FACTOR), 6)
            out_entry = dict(s)
            out_entry["mass"] = emitted_mass
            # Freshness reset: it re-enters live service, so decay counts from now.
            out_entry["last_accessed"] = float(out_entry.get("compressed_ts", out_entry.get("last_accessed", 0.0)))
            store = json.load(open(target, encoding="utf-8")) if os.path.exists(target) else {"entries": []}
            store.setdefault("entries", []).append(out_entry)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(store, f, indent=2, ensure_ascii=False)
            report["re_promoted"].append({
                "entry_id": s.get("entry_id"), "zone": s.get("zone"),
                "compressed_mass": round(float(s.get("mass", 0.0)), 6),
                "emitted_mass": emitted_mass,
            })
        else:
            remaining_in_queue.append(s)

    # ── Rewrite the queue: only what couldn't be merged or promoted stays.
    queue["entries"] = remaining_in_queue
    with open(comp_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
    report["survivors"] = [s.get("entry_id") for s in survivors]
    report["kept_in_queue"] = [e.get("entry_id") for e in remaining_in_queue]
    report["queue_size_out"] = len(remaining_in_queue)
    return report


# ─── SEGMENT 6: FULL DEEP-SLEEP ORCHESTRATOR (NON-BLOCKING SHAPE) ─────────────
#
# deep_sleep() is the single entry point a runtime calls on `/sleep`, full exit,
# or capacity overflow. It composes Segments 1-5 in the Build Plan's pass sequence:
#
#   T+0s     select_watchkeepers() — lock top-N (WATCHKEEPER_COUNT) as responsive.
#   T+5..    execute_deep_sleep()  — Pass IV drift via rotating shift + staggered
#                                    commits to planets/*.json, core last. (S4)
#   T+~40s   process_compression_queue() — Pass II merge + Pass III emission on the
#            queue (S5). Runs AFTER all drift commits so re-promoted entries land in a
#            stable field, not one mid-nudge.
#   T+final  watchkeeper status dissolves; all 7 planets awake at new positions.
#
# "Non-blocking shape" means: this function does its work and RETURNS — it never holds
# the event loop open or blocks user input for the full STAGGER_INTERVAL_SECONDS x N
# wait. The staggered waits happen inside execute_deep_sleep (which is fine to sleep on
# a background thread); deep_sleep() itself just sequences the phases and reports them.
# A runtime that needs true concurrency wraps this in its own thread/executor — but the
# function's job here is correct sequencing + full reporting, not threading policy.
#
# Zero LLM calls. Pure orchestration over S2-S5. Returns a combined report with each
# sub-phase's output plus an overall `state_changed` flag (the critical acceptance
# signal: did ANY numeric value on disk actually move? If false, sleep was cosmetic —
# v16 failure #2). Watchkeeper dissolution is reported, not persisted here (callers own
# any "awake now" runtime state).


def deep_sleep(base_dir: str,
               activation_weights: dict[str, float],
               session_consensus_3axis: tuple[float, float, float] | None = None,
               mass_delta_hints: dict[str, float] | None = None,
               g2_mode_suggestions: dict[str, dict] | None = None,
               core_commit: dict | None = None,
               stagger_seconds: float | None = 0.0) -> dict:
    """Segment 6 entry point: full deep-sleep pass sequence (S2+S4+S5 composed).

    `stagger_seconds` defaults to 0 here because the runtime caller normally wants the
    real STAGGER_INTERVAL_SECONDS wait; tests and quick-exit paths pass 0 explicitly for
    speed. Pass None to fall back to C.STAGGER_INTERVAL_SECONDS (the Build Plan default)
    instead of 0 — see execute_deep_sleep's own handling.

    Returns:
        {"watchkeepers": {...},            # S2 output
         "drift": {...},                  # S4 output (waves, applied, invariants, timing)
         "compression": {...},            # S5 report dict
         "state_changed": bool,           # True if any planet position or core moved on disk
         "planets_moved": [pid, ...],     # ids whose drift magnitude > 0
         "elapsed_total_s": float}
    """
    import time as _time
    import constants as C
    t0 = _time.time()

    wk = select_watchkeepers(activation_weights)

    # Pass IV: rotating-shift drift + staggered persistence (S4).
    # stagger_seconds=None → fall through to execute_deep_sleep's own default lookup of
    # C.STAGGER_INTERVAL_SECONDS; otherwise use the explicit value as-is.
    stagger_arg = None if stagger_seconds is None else float(stagger_seconds)
    drift = execute_deep_sleep(
        base_dir, activation_weights,
        session_consensus_3axis=session_consensus_3axis,
        mass_delta_hints=mass_delta_hints,
        g2_mode_suggestions=g2_mode_suggestions,
        core_commit=core_commit,
        stagger_seconds=stagger_arg,
    )

    # Pass II + III: compression/emission on the queued (shed) entries, after drift.
    compression = process_compression_queue(base_dir)

    planets_moved = sorted(pid for pid, info in drift.get("applied", {}).items()
                           if float(info.get("drift_magnitude", 0.0)) > 1e-9)
    core_moved = bool(drift.get("core_applied")) and (
        (core_commit or {}).get("drift_magnitude") is not None
        and float((core_commit).get("drift_magnitude", 0.0)) > 1e-9) if core_commit else \
        drift.get("core_drift_magnitude") is not None and float(drift.get("core_drift_magnitude", 0.0) or 0.0) > 1e-9
    state_changed = bool(planets_moved) or core_moved or compression["queue_size_out"] != \
        (compression["queue_size_in"] - len(compression["absorbed_entries"]))

    return {
        "watchkeepers": wk,
        "drift": drift,
        "compression": compression,
        "planets_moved": planets_moved,
        "core_moved": core_moved,
        "state_changed": state_changed,
        "elapsed_total_s": round(_time.time() - t0, 4),
    }


# ─── SEGMENT 7A: MOONS / GIANTS INTEGRITY THROUGH DEEP SLEEP (ZERO LLM) ──────
#
# John's rule: G1 + its moons are the LONG-TERM ARCHIVE; G2 + its self-model moons
# are the EVOLVING SELF-MODEL. Neither is a planet in _KNOWN_PLANET_IDS, so no Pass IV
# drift wave ever names them — but they DO sit under giants/ alongside ring buffers that
# scan_ring_buffers() (Pass I light) touches for decay-rate tuning during micro_sleep.
# Segment 7a proves the FULL deep_sleep() pass leaves their structural identity intact:
#
#   - core_laws.json / gates_config.json : byte-identical (sentinels, as in S4)
#   - giants/g1_knowledge.json           : moons + committed archive content untouched;
#                                          only ring_buffer decay_rate/align_score may move
#   - giants/g2_selfmodel.json           : 3 self-model moons, sandbox mechanism, growth_policy
#                                          all structurally intact (these are the gates that
#                                          enforce Tier-1/Tier-2 — clobbering them would be a
#                                          silent safety loss)
#
# Zero LLM. Pure file I/O + deep_sleep() orchestration. This is the "moons integrity test"
# from the Build Plan Phase 5 pass sequence (T+final: verify nothing non-planetary was harmed).


def _self_test_s7a():
    import shutil
    import tempfile

    print("\nsleep.py Segment 7a self-test: moons/giants integrity through full deep_sleep() (zero LLM)")
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}")
        if not cond:
            failures.append(name)

    tmp = tempfile.mkdtemp(prefix="rc5s7a_")
    try:
        for rel in ("planets", "core", "memory", "ring", "giants",
                    os.path.join("core"), os.path.join("gates")):
            os.makedirs(os.path.join(tmp, *rel.split(os.sep) if "/" in rel else [rel]), exist_ok=True)
        for rel in ("planets", "core", "memory", "ring", "giants", "gates"):
            os.makedirs(os.path.join(tmp, rel), exist_ok=True)

        # ── Seven planet files (real IDs) so deep_sleep's drift actually runs.
        import constants as C
        for i, pid in enumerate(_KNOWN_PLANET_IDS):
            data = {"id": pid, "archetype_name": pid.title(),
                    "position": [float(i) - 2.0, float(-i) * 0.5, 1.0 + i * 0.1],
                    "velocity": [0.1, -0.05, 0.02],
                    "mass": round(2.4 + i * 0.3, 3), "sigma": 1.0,
                    "cognitive_mode": {"temperature": 0.7, "context_window_exchanges": 3,
                                       "cot_depth": 1, "prompt_structure": "standard"},
                    "id_flavor": f"flavor-{pid}", "ego_descriptor": f"ego-{pid}",
                    "superego_principle": f"principle-{pid}",
                    "orbital_plane_tilt_deg": float(i),
                    "semantic_anchor": list(C.SEMANTIC_ANCHORS[pid]),
                    "_semantic_anchor_guard": "DO NOT MODIFY — semantic identity"}
            with open(os.path.join(tmp, "planets", f"{pid}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        # ── Core state + byte-identical sentinels.
        with open(os.path.join(tmp, "core", "core_state.json"), "w", encoding="utf-8") as f:
            json.dump({"position": [0.1, -0.8, -0.3], "G_value": 5.0, "M_base": 10.0,
                       "dissonance_alpha": 1.2, "dissonance_beta": 1.8, "well_depth": 2.5,
                       "session_counter": 42, "laws_file_path": "core_laws.json",
                       "genesis_state": {"version": "17.0.0", "sentinel": True}}, f, indent=2)
        sentinel_blobs = {
            os.path.join("core", "core_laws.json"): b'{"laws": ["sentinel-law"]}',
            os.path.join("gates", "gates_config.json"): b'{"pii_enabled": true}',
        }
        for rel, blob in sentinel_blobs.items():
            with open(os.path.join(tmp, *rel.split(os.sep)), "wb") as f:
                f.write(blob)

        # ── Populated giants: G1 archive (moons + committed content) and G2 self-model.
        g1 = {
            "id": "g1", "role": "permanent_knowledge",
            "moons": [
                {"id": "clarity", "job": "pre-filter incoming data for clarity"},
                {"id": "relevance", "job": "check relevance against existing archive"},
                {"id": "dissonance_pre_read", "job": "flag dissonant candidates before commit"}
            ],
            "committed_entries": [
                {"entry_id": "g1_arch_001", "semantic_content": "established fact: core laws are immutable",
                 "vector_position": [0.2, 0.4, -0.1], "mass": 3.5},
            ],
            "ring_buffer": [
                {"entry_id": "g1_ring_001", "semantic_content": "candidate knowledge pending commit",
                 "vector_position": [0.3, 0.1, 0.2], "mass": 0.4, "decay_rate": 0.02,
                 "planet_id": "sage", "access_count": 2},
            ],
        }
        g2 = {
            "id": "g2", "role": "evolving_self_model",
            "moons": [
                {"id": "consistency_gate", "job": "check proposed changes against Core Laws",
                 "on_violation": "hold in ring_buffer, do not commit"},
                {"id": "magnitude_gate", "job": "cap per-session delta", "max_delta": 0.15},
                {"id": "reversibility_log", "job": "record before-state for walk-back",
                 "append_only": True, "entries": []}
            ],
            "sandbox": {"enabled": True, "trial_prompts": 4,
                        "degradation_thresholds": {"tension_shift_max": 0.3,
                                                   "consensus_coherence_min": 0.7}},
            "growth_policy": {
                "tier_1_autonomous_after_moons_sandbox": True,
                "tier_2_structural_requires_user_approval": True,
                "pending_user_approval": []},
            "ring_buffer": [
                {"entry_id": "g2_ring_001", "semantic_content": "candidate self-model tweak",
                 "vector_position": [-0.2, 0.5, 0.3], "mass": 0.3, "decay_rate": 0.03,
                 "planet_id": "hero", "access_count": 1},
            ],
        }
        g1_path = os.path.join(tmp, "giants", "g1_knowledge.json")
        g2_path = os.path.join(tmp, "giants", "g2_selfmodel.json")
        with open(g1_path, "w", encoding="utf-8") as f:
            json.dump(g1, f, indent=2)
        with open(g2_path, "w", encoding="utf-8") as f:
            json.dump(g2, f, indent=2)

        # ── Empty memory queue + ring (nothing to compress; keeps the test focused on giants).
        for rel in ("memory/planet_vaults.json", "memory/stochastic_periphery.json",
                    "memory/compression_queue.json", "ring/swarm.json"):
            with open(os.path.join(tmp, *rel.split("/")), "w", encoding="utf-8") as f:
                json.dump({"entries": []}, f)

        # ── Capture pre-sleep state of the giants.
        g1_pre = json.load(open(g1_path, encoding="utf-8"))
        g2_pre = json.load(open(g2_path, encoding="utf-8"))

        aw = {pid: 0.5 for pid in _KNOWN_PLANET_IDS}
        deep_sleep(tmp, aw, session_consensus_3axis=(0.1, 0.2, -0.1), stagger_seconds=0)

        # ── Byte-identical sentinels (core laws + gates never touched by sleep).
        for rel, blob in sentinel_blobs.items():
            with open(os.path.join(tmp, *rel.split(os.sep)), "rb") as f:
                check(f"{rel} byte-identical after deep_sleep", f.read() == blob)

        g1_post = json.load(open(g1_path, encoding="utf-8"))
        g2_post = json.load(open(g2_path, encoding="utf-8"))

        # ── G1: moons + committed archive content must be UNCHANGED (byte-level on those keys).
        check("G1 moons unchanged after sleep", g1_post["moons"] == g1_pre["moons"])
        check("G1 committed_entries unchanged after sleep",
              g1_post.get("committed_entries") == g1_pre["committed_entries"])

        # ── G2: self-model moons, sandbox, growth_policy structurally intact.
        check("G2 3 self-model moons present and unchanged",
              [m["id"] for m in g2_post.get("moons", [])] ==
              [m["id"] for m in g2_pre["moons"]] and
              all(any(pm.get("id") == nm.get("id") and pm.get("job") == nm.get("job")
                      for pm in g2_post["moons"]) for nm in g2_pre["moons"]))
        check("G2 sandbox mechanism unchanged after sleep",
              g2_post.get("sandbox") == g2_pre["sandbox"])
        check("G2 growth_policy unchanged after sleep (Tier-1/Tier-2 gates intact)",
              g2_post.get("growth_policy") == g2_pre["growth_policy"])

        # ── Ring buffers: ONLY decay_rate / align_score may have moved; content + mass untouched.
        for label, pre_rb in (("G1 ring_buffer", g1_pre["ring_buffer"]),
                              ("G2 ring_buffer", g2_pre["ring_buffer"])):
            post_data = json.load(open(g1_path if "G1" in label else g2_path, encoding="utf-8"))
            for pre_e in pre_rb:
                match = next((pe for pe in post_data.get("ring_buffer", [])
                              if pe.get("entry_id") == pre_e["entry_id"]), None)
                check(f"{label} entry {pre_e['entry_id']} still present after sleep",
                      match is not None)
                if match:
                    check(f"{label} {pre_e['entry_id']}: content + mass untouched",
                          match["semantic_content"] == pre_e["semantic_content"]
                          and abs(float(match["mass"]) - float(pre_e["mass"])) < 1e-9
                          and match["vector_position"] == pre_e["vector_position"])

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"Segment 7a self-test: {len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("Segment 7a self-test: PASS (moons/giants archive + self-model integrity held through deep sleep, zero LLM)")


# ─── SEGMENT 6 SELF-TEST ─────────────────────────────────────────────────────

def _self_test_s6():
    import shutil
    import tempfile

    print("\nsleep.py Segment 6 self-test: deep_sleep() full orchestrator (zero LLM, zero real waits)")
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}")
        if not cond:
            failures.append(name)

    tmp = tempfile.mkdtemp(prefix="rc5s6_")
    try:
        for rel in ("planets", "core", "memory", "ring"):
            os.makedirs(os.path.join(tmp, rel), exist_ok=True)

        # Seed 7 planets + core with distinct positions so drift is measurable.
        # IDs must match _KNOWN_PLANET_IDS exactly (rotating shift only covers those).
        pids = ["sage", "magician", "caregiver", "hero",
                "everyman", "rebel", "ruler"]
        seeds = {
            "sage":     ([0.5, 0.2, -0.1], 3.0),
            "magician": ([-0.4, 0.6, 0.3], 2.5),
            "caregiver":([0.8, -0.3, 0.1], 2.8),
            "hero":     ([-0.7, -0.5, -0.2], 2.6),
            "everyman": ([0.1, 0.9, 0.4], 2.2),
            "rebel":    ([-0.2, -0.8, 0.5], 2.4),
            "ruler":    ([0.3, 0.1, 0.7], 2.9),
        }
        pre_pos = {}
        for pid, (pos, mass) in seeds.items():
            pre_pos[pid] = list(pos)
            data = {"id": pid, "archetype_name": pid.title(), "position": pos,
                    "velocity": [0.1, 0.2, 0.3], "mass": mass, "sigma": 1.0,
                    "cognitive_mode": {"temperature": 0.7, "context_window_exchanges": 3,
                                       "cot_depth": 1, "prompt_structure": "standard"},
                    "semantic_anchor": [0.1, 0.2, 0.3], "_semantic_anchor_guard": True,
                    "id_flavor": f"{pid} id", "ego_descriptor": f"{pid} ego",
                    "superego_principle": f"{pid} superego", "orbital_plane_tilt_deg": 5.0}
            with open(os.path.join(tmp, "planets", f"{pid}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f)
        core_pre = [1.0, -0.5, 0.2]
        with open(os.path.join(tmp, "core", "core_state.json"), "w", encoding="utf-8") as f:
            json.dump({"position": core_pre, "G_value": 5.0, "M_base": 10.0,
                       "dissonance_alpha": 1.2, "dissonance_beta": 1.8, "well_depth": 2.5,
                       "session_counter": 7}, f)
        # Empty compression queue (nothing shed this session) — proves the pass still runs cleanly.
        with open(os.path.join(tmp, "memory", "compression_queue.json"), "w", encoding="utf-8") as f:
            json.dump({"entries": []}, f)

        # Distinct activation weights so watchkeeper selection + ranking are non-trivial.
        aw = {"hero": 0.9, "sage": 0.7, "ruler": 0.5, "magician": 0.3,
              "everyman": 0.2, "rebel": 0.1, "caregiver": 0.05}

        report = deep_sleep(tmp, aw, session_consensus_3axis=(0.4, -0.2, 0.6),
                            stagger_seconds=0)  # 0 → no real waits; still full sequence.

        # ── Structure: all three sub-phases present and coherent.
        check("report has watchkeepers / drift / compression keys",
              set(report.keys()) >= {"watchkeepers", "drift", "compression",
                                     "planets_moved", "core_moved", "state_changed"})
        wk = report["watchkeepers"]
        check("watchkeepers selected (count == WATCHKEEPER_COUNT)",
              wk["count"] == 3 and len(wk["watchkeepers"]) == 3)
        # Top-3 by weight should be hero, sage, ruler.
        check("watchkeepers are the top-3 activation weights",
              set(wk["watchkeepers"]) == {"hero", "sage", "ruler"})

        # Sanity: seeded pids match the module's known set (guards against fixture drift).
        check("fixture planet ids match _KNOWN_PLANET_IDS",
              sorted(pids) == sorted(_KNOWN_PLANET_IDS))

        drift = report["drift"]
        check("rotating shift produced 3 waves covering all 7 planets",
              len(drift["waves"]) == 3 and
              sorted([p for w in drift["waves"] for p in w["sleeping"]]) == sorted(pids))
        check("every wave kept >= 4 awake (invariant)",
              all(w["awake_count"] >= 4 for w in drift["waves"]))
        check("all planets applied, none skipped",
              len(drift["applied"]) == 7 and not drift["skipped"])
        check("each planet slept exactly once (invariant flag)",
              drift["invariants"]["each_planet_slept_once"] is True)

        comp = report["compression"]
        check("compression pass ran cleanly on empty queue",
              comp["queue_size_in"] == 0 and comp["queue_size_out"] == 0
              and comp["merged_clusters"] == 0 and not comp["re_promoted"])

        # ── THE critical acceptance check: numeric state actually changed on disk.
        post_pos = {}
        for pid in pids:
            with open(os.path.join(tmp, "planets", f"{pid}.json"), encoding="utf-8") as f:
                d = json.load(f)
            post_pos[pid] = list(d["position"])
        moved_on_disk = [p for p in pids
                         if any(abs(a - b) > 1e-9 for a, b in zip(pre_pos[p], post_pos[p]))]
        check("every planet's position changed on disk (no cosmetic sleep)",
              len(moved_on_disk) == 7 and set(report["planets_moved"]) == set(pids))
        with open(os.path.join(tmp, "core", "core_state.json"), encoding="utf-8") as f:
            core_post = json.load(f)["position"]
        check("core position changed on disk",
              any(abs(a - b) > 1e-9 for a, b in zip(core_pre, core_post)))
        check("state_changed flag is True (acceptance signal)", report["state_changed"] is True)

        # ── Identity + sentinels preserved through the full pass.
        with open(os.path.join(tmp, "planets", "sage.json"), encoding="utf-8") as f:
            hero_post = json.load(f)
        check("semantic_anchor untouched by deep sleep (clobber guard held)",
              hero_post["semantic_anchor"] == [0.1, 0.2, 0.3]
              and hero_post.get("_semantic_anchor_guard") is True)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"Segment 6 self-test: {len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("Segment 6 self-test: PASS (full pass sequence composed, state changed on disk, zero LLM)")


# ─── SEGMENT 5 SELF-TEST ─────────────────────────────────────────────────────

def _self_test_s5():
    import shutil
    import tempfile

    print("\nsleep.py Segment 5 self-test: process_compression_queue() (Pass II + III)")
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}")
        if not cond:
            failures.append(name)

    tmp = tempfile.mkdtemp(prefix="rc5s5_")
    try:
        for rel in ("memory", "ring"):
            os.makedirs(os.path.join(tmp, rel), exist_ok=True)
        # Live stores start with one pre-existing entry each (proves re-promotion
        # APPENDS and never clobbers existing content).
        vault_path = os.path.join(tmp, "memory", "planet_vaults.json")
        periph_path = os.path.join(tmp, "memory", "stochastic_periphery.json")
        swarm_path = os.path.join(tmp, "ring", "swarm.json")
        with open(vault_path, "w", encoding="utf-8") as f:
            json.dump({"entries": [{"entry_id": "pre_existing_1", "semantic_content": "old vault note",
                                    "mass": 0.9}]}, f)
        for p in (periph_path, swarm_path):
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"entries": []}, f)

        now = 1_750_000_000.0
        # Queue layout (realistic: Pass V only sheds entries BELOW MIN_ENTRY_MASS=0.05,
        # so every entry here is individually light — no single unmerged entry can ever
        # reach the 0.6 re-promotion floor on its own; only MERGED clusters accumulate
        # enough mass to qualify):
        #   dup_a / dup_b : same direction + near-identical text, masses .04/.035 → merge (0.075)
        #   promo_c       : duplicate of the pair's content, lower mass .01 → joins cluster
        #                   combined 0.085 — still BELOW 0.6 floor, so it does NOT re-promote;
        #                   the merged survivor stays parked (proves the mass gate is real).
        #   unique_heavy  : distinct position AND text but still sub-MIN_ENTRY_MASS (.049),
        #                   can never merge with the dup cluster → stays parked.
        #   unique_light  : distinct, .02 → stays parked.
        # To ALSO exercise Pass III's re-promotion path (which needs a merged mass ≥ 0.6,
        # only reachable when many near-duplicates pile up in one queue cycle), we add a
        # second independent cluster of four near-identical entries whose combined mass
        # crosses the floor: heavy_a..heavy_d, each .20 → merged to 0.8 ≥ 0.6 → re-promoted
        # at ×0.5 = 0.4 into planet_vault.
        def _e(eid, pos, content, mass):
            return {"entry_id": eid, "vector_position": list(pos), "mass": float(mass),
                    "semantic_content": content, "creation_ts": now - 86400.0,
                    "last_accessed": now - 3 * 86400.0, "decay_rate": 0.02,
                    "ring_membership": False, "zone": "planet_vault"}

        queue_entries = [
            # Cluster A: three near-duplicates, individually light → merged mass 0.085 < 0.6 → stays parked.
            _e("dup_a", [1.0, 0.0, 0.0], "the hero chose courage over comfort again today", 0.04),
            _e("dup_b", [1.0, 0.001, 0.0], "the hero chose courage over comfort again today", 0.035),
            _e("promo_c", [0.999, 0.0, 0.002], "the hero chose courage over comfort today again", 0.01),
            # Cluster B: four near-duplicates, merged mass 0.8 ≥ 0.6 → re-promoted at ×0.5 = 0.4.
            _e("heavy_a", [-2.0, 3.0, -1.0], "orbital mechanics resonance drift observed in the inner system", 0.20),
            _e("heavy_b", [-2.001, 3.0, -0.999], "orbital mechanics resonance drift observed in the inner system today", 0.20),
            _e("heavy_c", [-1.999, 3.001, -1.001], "orbital mechanics resonance drift is observed within the inner system", 0.20),
            _e("heavy_d", [-2.0, 2.998, -1.0], "resonance drift in orbital mechanics was observed in the inner system today", 0.20),
            # Two distinct singles that match neither cluster → both stay parked.
            _e("unique_heavy", [4.0, -4.0, 2.0], "completely unrelated knowledge about tidal locking of moons", 0.049),
            _e("unique_light", [5.0, 1.0, -3.0], "another distinct thought entirely different subject matter here", 0.02),
        ]
        comp_path = os.path.join(tmp, "memory", "compression_queue.json")
        with open(comp_path, "w", encoding="utf-8") as f:
            json.dump({"entries": queue_entries}, f)

        report = process_compression_queue(base_dir=tmp)

        check("queue size in == 9 (3 cluster A + 4 cluster B + 2 singles)",
              report["queue_size_in"] == 9)
        # ── Pass II assertions.
        check("two duplicate clusters merged (3+4 members → 2 survivors)",
              report["merged_clusters"] == 2 and len(report["absorbed_entries"]) == 5)
        check("cluster A survivor is the highest-mass member", "dup_a" in report["survivors"])
        check("cluster B survivor is one of its members (all tied mass)",
              any(s.startswith("heavy_") for s in report["survivors"]))
        check("cluster A absorbed dup_b + promo_c",
              {"dup_b", "promo_c"} <= set(report["absorbed_entries"]))
        heavy_absorbed = [a for a in report["absorbed_entries"] if a.startswith("heavy_")]
        check("cluster B absorbed exactly 3 of its 4 members",
              len(heavy_absorbed) == 3)

        # ── Pass III assertions.
        ids_promoted = [r["entry_id"] for r in report["re_promoted"]]
        survivor_b = next(r["entry_id"] for r in report["re_promoted"]) if report["re_promoted"] else None
        check("only cluster B (merged mass 0.8 >= 0.6) re-promoted",
              len(report["re_promoted"]) == 1 and survivor_b is not None
              and survivor_b.startswith("heavy_"))
        check("cluster A survivor stayed parked (merged mass 0.085 < 0.6 floor)",
              "dup_a" in report["kept_in_queue"])
        promo = next(r for r in report["re_promoted"] if r["entry_id"] == survivor_b)
        expected_emitted = round(min(MAX_COMPRESSED_MASS, 0.8 * COMPRESS_REPROMOTE_FACTOR), 6)
        check(f"cluster B survivor emitted at reduced mass {expected_emitted}",
              abs(promo["emitted_mass"] - expected_emitted) < 1e-9)

        # ── Queue residue.
        parked = sorted(report["kept_in_queue"])
        check("parked entries are exactly: dup_a, unique_heavy, unique_light",
              report["queue_size_out"] == 3 and set(parked) == {"dup_a", "unique_heavy", "unique_light"})
        with open(comp_path, encoding="utf-8") as f:
            q = json.load(f)
        check("queue on disk holds exactly the 3 parked entries",
              set(e["entry_id"] for e in q["entries"]) == {"dup_a", "unique_heavy", "unique_light"})

        # ── Re-promotion landed in the right live stores, appended not clobbered.
        with open(vault_path, encoding="utf-8") as f:
            vault = json.load(f)
        v_ids = [e["entry_id"] for e in vault["entries"]]
        check("pre-existing vault entry survived re-promotion", "pre_existing_1" in v_ids)
        check("cluster B survivor landed in planet_vault",
              survivor_b is not None and survivor_b in v_ids)
        promoted_out = next(e for e in vault["entries"] if e["entry_id"] == survivor_b)
        absorbed_in_promoted = {m["entry_id"] for m in promoted_out.get("compressed_from", [])}
        check("re-promoted entry carries provenance (compressed_from) for its 3 cluster-mates",
              len(absorbed_in_promoted) == 3 and absorbed_in_promoted <= set(heavy_absorbed))

        # ── Idempotency: run again on the shrunken queue → nothing moves.
        report2 = process_compression_queue(base_dir=tmp)
        check("second pass: no new merges, no re-promotions",
              report2["merged_clusters"] == 0 and report2["re_promoted"] == [])
        check("second pass: queue size stable at 3",
              report2["queue_size_out"] == 3)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"Segment 5 self-test: {len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("Segment 5 self-test: PASS (Pass II merge + Pass III re-promotion, provenance kept, zero LLM)")


def _self_test_s6_ring():
    """Phase 6 Segment 3 — Ring personality drift. Pure math + file I/O, no LM Studio.

    Proves: (a) compute_ring_drift is bounded at RING_DRIFT_MAX and moves TOWARD the
    session trend; (b) _apply_ring_commit_to_disk writes ONLY personality_vector into
    ring/persona.json and preserves every other field byte-for-byte; (c) the isolated
    branch in execute_deep_sleep fires only when a vector + consensus are supplied.
    """
    import shutil
    import tempfile

    print("\nsleep.py Phase 6 Segment 3 self-test: compute_ring_drift() + ring commit")
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}")
        if not cond:
            failures.append(name)

    # ── (a) Bounded drift toward the trend direction.
    pv0 = [0.0, 0.3, 0.1]
    r = compute_ring_drift(pv0, (0.5, 0.2, 0.4), sessions_since_last_drift=1)
    dx = sum((a - b) ** 2 for a, b in zip(r["personality_vector"], pv0)) ** 0.5
    check("ring drift magnitude <= RING_DRIFT_MAX", dx <= RING_DRIFT_MAX + 1e-6)
    check("ring moved TOWARD trend (x up, z up)",
          r["personality_vector"][0] > pv0[0] and r["personality_vector"][2] > pv0[2])

    # Many piled-up sessions -> softer nudge than a single session.
    r_many = compute_ring_drift(pv0, (0.5, 0.2, 0.4), sessions_since_last_drift=8)
    dx_many = sum((a - b) ** 2 for a, b in zip(r_many["personality_vector"], pv0)) ** 0.5
    check("more accumulated sessions -> smaller nudge (no lurch)", dx_many < dx + 1e-9)

    # No trend supplied -> no movement at all.
    r_none = compute_ring_drift(pv0, None)
    check("no session trend -> personality_vector unchanged",
          r_none["personality_vector"] == [round(p, 6) for p in pv0]
          and r_none["drift_magnitude"] == 0.0)

    # ── (b) Isolated commit touches ONLY personality_vector.
    tmp = tempfile.mkdtemp(prefix="ring_drift_s3_")
    try:
        os.makedirs(os.path.join(tmp, "ring"), exist_ok=True)
        persona_path = os.path.join(tmp, "ring", "persona.json")
        with open(persona_path, "w", encoding="utf-8") as f:
            json.dump({
                "name": "Maya",
                "personality_vector": [0.0, 0.3, 0.1],
                "model_id": "auto",
                "idle_state": "dormant",
                "voice_notes": "Warm, direct.",
                "swarm_ref": "ring/swarm.json",
                "relationship_log_ref": "ring/relationship_log.json",
            }, f, indent=2)

        res = _apply_ring_commit_to_disk(tmp, {"personality_vector": [0.01, 0.31, 0.105]})
        with open(persona_path, encoding="utf-8") as f:
            after = json.load(f)
        check("ring commit applied", res["applied"] is True and "personality_vector" in res["changed_fields"])
        check("only personality_vector changed",
              after["name"] == "Maya" and after["voice_notes"] == "Warm, direct."
              and after["model_id"] == "auto" and after["idle_state"] == "dormant"
              and after["personality_vector"] == [0.01, 0.31, 0.105])

        # Missing ring file -> graceful skip, no crash.
        res_missing = _apply_ring_commit_to_disk(tempfile.mkdtemp(prefix="ring_none_"),
                                                 {"personality_vector": [0.0, 0.0, 0.0]})
        check("missing persona.json -> skipped gracefully (no exception)",
              res_missing["applied"] is False and "note" in res_missing)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ── (c) execute_deep_sleep ring branch fires only with vector + consensus.
    tmp2 = tempfile.mkdtemp(prefix="ring_ds_s3_")
    try:
        os.makedirs(os.path.join(tmp2, "planets"), exist_ok=True)
        for pid in ["sage", "hero", "magician", "caregiver", "everyman", "rebel", "ruler"]:
            with open(os.path.join(tmp2, "planets", f"{pid}.json"), "w") as f:
                json.dump({"id": pid, "archetype_name": pid.upper(),
                           "position": [0.1, 0.1, 0.1], "mass": 3.0, "sigma": 1.0,
                           "cognitive_mode": {}}, f)
        os.makedirs(os.path.join(tmp2, "ring"), exist_ok=True)
        with open(os.path.join(tmp2, "ring", "persona.json"), "w") as f:
            json.dump({"name": "Maya", "personality_vector": [0.0, 0.3, 0.1]}, f)

        weights = {p: 0.5 for p in ["sage", "hero", "magician", "caregiver",
                                    "everyman", "rebel", "ruler"]}
        # WITH ring vector + consensus -> ring branch fires.
        rep_on = execute_deep_sleep(tmp2, weights, session_consensus_3axis=(0.4, 0.1, 0.3),
                                    ring_personality_vector=[0.0, 0.3, 0.1], stagger_seconds=0)
        check("ring branch applied when vector+consensus supplied", rep_on.get("ring_applied") is True)

        # WITHOUT a ring vector -> ring stays False (branch inert by default).
        rep_off = execute_deep_sleep(tmp2, weights, session_consensus_3axis=(0.4, 0.1, 0.3),
                                     stagger_seconds=0)
        check("ring branch INERT when no vector supplied", rep_off.get("ring_applied") is False)
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)

    print()
    if failures:
        print(f"Phase 6 Segment 3 self-test: {len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("Phase 6 Segment 3 self-test: PASS (bounded drift + isolated persona commit, zero LLM)")


if __name__ == "__main__":
    _self_test()
    _self_test_s2()
    _self_test_s3()
    _self_test_s4()
    _self_test_s5()
    _self_test_s6()
    _self_test_s7a()
    _self_test_s6_ring()
