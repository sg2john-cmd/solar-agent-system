"""
Resonant Cognition v17 — Session Memory & G2 Bias Wave (Phase 0F)
=================================================================

This module gives the collapse engine *a memory of what happened earlier in this
session*, and a low-amplitude "mood" wave from G2's committed self-model.

DESIGN (approved by John):
    Layer 1 — Session RAM: prior prompts in THIS session enter the superposition
              as extra waves with exponential decay (recent = louder). This is
              the engine-level analogue of the moons-as-short-term-buffer idea.
    Layer 2 — G2 bias wave: G2's committed `contents[]` are aggregated into ONE
              persistent low-amplitude wave that rides on every collapse, so
              the system "remembers its own mood" across sessions.
    Layer 3 — G1 long-term knowledge: NOT wired here yet (Phase 7).

Everything in this module is pure / read-only with respect to JSON files. It does
NOT write to g2_selfmodel.json — that happens at session end via a separate
summary routine (see summarize_session_for_g2 below; the writer lives elsewhere
so we don't couple engine + persistence).

RUN: python -X utf8 memory.py   (self-test, no LM Studio calls needed)
"""

from __future__ import annotations

import json
import math
import os
import random
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))


# ─── TUNABLES ────────────────────────────────────────────────────────────────
# Kept here (not constants.py) because they are memory-layer-specific, not engine-wide.
# If calibration ever needs them, promote to constants.py + calibrate_axes template.

SESSION_DECAY_HALF_LIFE_MIN = 5.0    # A turn's background-wave amplitude halves every ~5 min of wall time.
                                     # Tune later against real sessions. GUESS for now (flagged).
SESSION_WAVE_BASE_AMPLITUDE = 0.35   # Scale factor: prior-turn waves are QUIETER than the current question.
                                     # Keeps "context" as context, not as a competing voice. GUESS.
G2_BIAS_AMPLITUDE = 0.15             # How loud the self-model mood wave is relative to planets. Very low.
                                     # The system "remembers its own mood", it doesn't shout about it. GUESS.

# PII GUARD (Phase 4 Seg 4): scrub emails/phones/etc out of semantic_content before it
# reaches disk. Reuses gate1.scrub_pii (the PII-only step, NOT the clarity gate — memory
# text should be REDACTED, never rejected for being low-clarity). Toggleable; default ON.
MEMORY_PII_GUARD_ENABLED = True
# Option C blend (John-approved): context direction = alpha*consensus + beta*question
#   B-consensus carries the "why" (system's own reading of what happened).
#   A-question is a faint literal trace so two near-identical consensus vectors can still disambiguate.
CONTEXT_BLEND_ALPHA_CONSENSUS = 0.8
CONTEXT_BLEND_BETA_QUESTION   = 0.2
MAX_SESSION_TURNS_IN_SUPERPOSITION = 8   # Cap: only last N turns contribute waves (older ones fade below noise).


# ─── LAYER 1: SESSION RAM ────────────────────────────────────────────────────

class SessionMemory:
    """Per-session in-memory log of what's been asked + how the field responded.

    Each turn is stored as a dict:
        {
            "turn_index": int,           # 0-based position within this session
            "question_text": str,        # raw user text (for display / debugging)
            "question_vec": list[float], # 384-dim embedding of the question
            "consensus_vec": list[float] | None,  # surviving wave from collapse()
            "tension": float,            # tension reading from that turn's collapse
            "ts": float                  # unix timestamp when this turn ran
        }

    The engine calls record_turn() AFTER each run_collapse(). When the NEXT question
    arrives, get_background_waves(now_ts) returns a list of (unit_dir, amplitude)
    pairs ready to be appended into collapse()'s wave superposition.
    """

    def __init__(self):
        self._history: list[dict] = []

    # -- write side ----------------------------------------------------------

    def record_turn(self, question_text: str, question_vec: list[float],
                    consensus_vec: list[float] | None, tension: float) -> int:
        """Log a completed turn. Returns the new turn_index (0-based)."""
        entry = {
            "turn_index": len(self._history),
            "question_text": question_text,
            "question_vec": list(question_vec),
            "consensus_vec": [float(x) for x in consensus_vec] if consensus_vec else None,
            "tension": float(tension),
            "ts": time.time(),
        }
        self._history.append(entry)
        return entry["turn_index"]

    # -- read side -----------------------------------------------------------

    def get_background_waves(self, now_ts: float | None = None):
        """Return [(unit_dir_384d, amplitude), ...] for prior turns that should
        enter the NEXT collapse as background waves.

        OPTION C (John-approved): each context wave's DIRECTION is a blend of
            alpha * consensus_vec  +  beta * question_vec   (normalized)
        so the "why" (what the system actually landed on) dominates, with a faint
        trace of the literal question for disambiguation.

        If a turn has no consensus stored yet (shouldn't happen in normal flow),
        we fall back to pure question direction for that entry only.

        Amplitude decays with wall-clock age (exponential half-life). Very old or
        very quiet turns are dropped — they'd add noise, not signal.
        """
        now_ts = time.time() if now_ts is None else now_ts
        out = []
        a_c = CONTEXT_BLEND_ALPHA_CONSENSUS
        b_q = CONTEXT_BLEND_BETA_QUESTION
        for entry in self._history[-MAX_SESSION_TURNS_IN_SUPERPOSITION:]:
            qv = entry.get("question_vec") or []
            if not qv:
                continue
            cv = entry.get("consensus_vec") or None
            # Blend. If consensus missing, use question alone (beta rescaled to 1).
            if cv and len(cv) == len(qv):
                blended = [a_c * c + b_q * q for c, q in zip(cv, qv)]
            else:
                blended = list(qv)
            n = math.sqrt(sum(x * x for x in blended)) or 1.0
            unit = [x / n for x in blended]
            age_min = max(0.0, (now_ts - entry["ts"]) / 60.0)
            decay = math.pow(2.0, -age_min / SESSION_DECAY_HALF_LIFE_MIN)
            amp = SESSION_WAVE_BASE_AMPLITUDE * decay
            if amp < 0.02:
                continue
            out.append((unit, amp))
        return out

    def __len__(self):
        return len(self._history)

    def to_list(self) -> list[dict]:
        """Copy of the raw history (for persistence or debugging)."""
        return [dict(e) for e in self._history]


# ─── LAYER 2: G2 BIAS WAVE ──────────────────────────────────────────────────

def load_g2_bias_wave(g2_path: str | None = None,
                      now_ts: float | None = None):
    """Read g2_selfmodel.json `contents[]`, aggregate into a single low-amplitude
    bias wave. Returns (unit_dir_384d, amplitude) or None if there's nothing to say.

    Each G2 entry is expected to carry its own 384-dim embedding under key "vec"
    (written by the session-summarizer). Entries without a vec are skipped — we do
    NOT call the embedder here (this function is called on every collapse; calling
    an HTTP service per call would be slow and brittle).

    Decay: entries older than G2's half-life contribute less. We use exponential
    decay matching constants.G2_DECAY_HALF_LIFE_WEEKS (imported lazily to avoid a
    hard dependency if constants isn't loaded yet in tests).
    """
    if g2_path is None:
        g2_path = os.path.join(_HERE, "giants", "g2_selfmodel.json")
    if not os.path.exists(g2_path):
        return None

    with open(g2_path, encoding="utf-8") as f:
        data = json.load(f)

    contents = data.get("contents", []) or []
    # Only committed entries matter; ring_buffer is proposed and untested.
    if not contents:
        return None

    now_ts = time.time() if now_ts is None else now_ts

    try:
        import constants as C
        half_life_weeks = float(getattr(C, "G2_DECAY_HALF_LIFE_WEEKS", 4.0) or 4.0)
    except Exception:
        half_life_weeks = 4.0

    # Accumulate weighted sum of embeddings; entries with no vec are skipped.
    acc = None
    total_weight = 0.0
    for entry in contents:
        vec = entry.get("vec") if isinstance(entry, dict) else None
        if not vec or len(vec) == 0:
            continue
        ts = float(entry.get("ts", now_ts))
        age_weeks = max(0.0, (now_ts - ts) / (7 * 24 * 3600))
        w = math.pow(2.0, -age_weeks / half_life_weeks) if half_life_weeks > 0 else 1.0
        if acc is None:
            acc = [x * w for x in vec]
        else:
            acc = [a + (b * w) for a, b in zip(acc, vec)]
        total_weight += w

    if not acc or total_weight <= 1e-9:
        return None

    # Normalize to a unit direction; amplitude is the fixed low bias scale.
    n = math.sqrt(sum(x * x for x in acc)) or 1.0
    unit = [x / n for x in acc]
    return (unit, G2_BIAS_AMPLITUDE)


# ─── SESSION SUMMARY (feeds Layer 2 on session end) ──────────────────────────

def summarize_session_for_g2(session: SessionMemory,
                             dominant_planets: list[str],
                             avg_tension: float,
                             conflict_pairs: list[tuple[str, str]] | None = None):
    """Produce a G2 `contents`-ready entry from a finished session.

    This does NOT write to disk — the caller is responsible for appending it to
    g2_selfmodel.json's contents[] (and running through the 3 moons + sandbox
    before committing). We keep this function pure so the writer can decide policy.

    The returned dict has:
        ts, source ("session_summary"), dominant_planets, avg_tension, conflict_pairs,
        vec (mean of question embeddings in this session — the "flavor" of the session),
        half_life_weeks (copied from constants so decay is self-describing)
    """
    hist = session.to_list()
    if not hist:
        return None

    # Session-flavor vector = mean of all question embeddings in this session.
    dim = len(hist[0]["question_vec"])
    acc = [0.0] * dim
    for e in hist:
        v = e["question_vec"]
        if len(v) != dim:
            continue
        for i, x in enumerate(v):
            acc[i] += x / len(hist)

    try:
        import constants as C
        hl = float(getattr(C, "G2_DECAY_HALF_LIFE_WEEKS", 4.0) or 4.0)
    except Exception:
        hl = 4.0

    return {
        "ts": time.time(),
        "source": "session_summary",
        "turn_count": len(hist),
        "dominant_planets": list(dominant_planets),
        "avg_tension": float(avg_tension),
        "conflict_pairs": [list(p) for p in (conflict_pairs or [])],
        "vec": acc,
        "half_life_weeks": hl,
    }


# ─── LAYER 3: SPATIAL MEMORY MATRIX (Phase 4, Segment 1) ─────────────────────
#
# Pure math over the collapse result. Nothing here touches disk (that's Segment
# 2). Two questions answered per new memory:
#   (a) how much MASS does it carry?      -> compute_memory_mass()
#   (b) which ZONE of the field is it in? -> assign_zone()
#
# MASS — Paper III "Dynamic Information Evolution", single-step form.
#   Full paper:  M_u = ∫ W(τ)·S(τ)·e^(-γ(t-τ)) dτ   (accumulates over repeated exposure)
#   Phase 4 uses the one-moment evaluation of that integrand for a brand-new entry:
#       S = semantic alignment with the field's own answer
#         = cosine(semantic_vec, consensus_vec)      [clamped >=0: misaligned input -> 0]
#       W ≈ 1.0 (active will — every persisted turn is one we chose to keep)
#   So M_u = MEMORY_MASS_BASE * max(0, cos). The time-integral GROWTH (entries gain
#   mass as they're re-encountered) is wired in the sleep cycle Pass V later; same math.

def compute_memory_mass(semantic_vec: list[float], consensus_vec: list[float] | None,
                        base_mass: float | None = None) -> float:
    """M_u for a new memory entry (Paper III single-step form).

    semantic_vec  — the input's 384-dim embedding (what was asked / observed).
    consensus_vec — the collapse result's surviving wave (what the field landed on).
    Returns base_mass * max(0, cosine). If either vec is missing/zero -> 0.0.
    """
    if semantic_vec and consensus_vec:
        n = min(len(semantic_vec), len(consensus_vec))
        dot = sum(a * b for a, b in zip(semantic_vec[:n], consensus_vec[:n]))
        na = math.sqrt(sum(x * x for x in semantic_vec))
        nb = math.sqrt(sum(x * x for x in consensus_vec))
        if na > 1e-9 and nb > 1e-9:
            cos = dot / (na * nb)
        else:
            return 0.0
    else:
        return 0.0
    if base_mass is None:
        import constants as C
        base_mass = float(getattr(C, "MEMORY_MASS_BASE", 1.0) or 1.0)
    return float(base_mass * max(0.0, cos))


# ZONE — where the entry lives in the field (spatial + governance).
#   planet_vault        : one planet clearly dominated -> that archetype's vault.
#   ring_swarm          : ring_membership=True -> orbits THE RING (user layer), not C_core.
#   stochastic_periphery: no clear owner (contested) -> the asteroid belt; decays to dust
#                         unless alignment later promotes it (Paper III integration).
ZONE_PLANET_VAULT = "planet_vault"
ZONE_RING_SWARM = "ring_swarm"
ZONE_STOCHASTIC_PERIPHERY = "stochastic_periphery"


# POSITION — where the entry sits in 3D cognitive space (Segment 2).
# A memory lives near the planet that dominated its turn. Multiple entries for
# the same planet get a small random radial jitter so they don't stack on one point.
def _position_with_jitter(planet_position: list[float],
                          jitter_mag: float | None = None) -> list[float]:
    """Copy of a planet's [x,y,z] nudged outward by up to `jitter_mag` in a random
    radial direction. Keeps the entry 'near' the parent without exact overlap."""
    if jitter_mag is None:
        import constants as C
        jitter_mag = float(getattr(C, "MEMORY_POSITION_JITTER", 0.05) or 0.0)
    import random
    pos = [float(x) for x in planet_position]
    r = math.sqrt(sum(p * p for p in pos))
    if r > 1e-9:
        unit = [p / r for p in pos]           # radial direction from origin
    else:
        unit = [0.0, 0.0, 0.0]
    off = random.random() * jitter_mag          # 0..jitter_mag along the radius
    return [pos[i] + unit[i] * off for i in range(3)]


# PII GUARD (Phase 4 Seg 4) — scrub before persistence. See MEMORY_PII_GUARD_ENABLED.
def set_memory_pii_guard(enabled: bool) -> None:
    """Toggle the write-path PII guard on/off (module-level, for tests / reversibility)."""
    global MEMORY_PII_GUARD_ENABLED
    MEMORY_PII_GUARD_ENABLED = bool(enabled)


def _pii_guard(semantic_content: str) -> tuple[str, list[dict]]:
    """Return (cleaned_text, redactions) for a memory's semantic content.

    When the guard is disabled OR gate1 has pii.enabled=False, returns the text
    unchanged with an empty redaction list. NEVER raises — a scrub failure must not
    block a legitimate write; in that case we return the original and flag it so the
    caller can choose to drop the entry rather than persist unscrubbed PII.
    """
    if not MEMORY_PII_GUARD_ENABLED:
        return semantic_content, []
    try:
        import gate1  # imported lazily: memory self-tests run without LM Studio / heavy deps
        cleaned, redactions = gate1.scrub_pii(semantic_content or "")
        return cleaned, list(redactions)
    except Exception as exc:      # never let a scrub error corrupt or block persistence
        # Contract (see docstring): NEVER raises. Return the original text flagged so
        # the caller can choose to drop the entry rather than crash the write path.
        print(f"[memory] PII guard failed ({exc!r}); returning unscrubbed content, flagged for drop.")
        return semantic_content, [{"type": "pii_guard_error", "detail": repr(exc)}]


# STORE MAP — which on-disk file each zone writes to (relative to base_dir).
ZONE_FILE_REL = {
    ZONE_PLANET_VAULT: "memory/planet_vaults.json",
    ZONE_STOCHASTIC_PERIPHERY: "memory/stochastic_periphery.json",
    ZONE_RING_SWARM: "ring/swarm.json",
}


def _load_store(path: str) -> dict:
    """Load a {entries:[...]} store, tolerating a missing file (treat as empty)."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    return {"entries": []}


def _save_store(obj: dict, path: str) -> None:
    """Write a store back to disk, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def make_entry(semantic_content: str,
               planet_position: list[float] | None,
               mass: float,
               zone: str = ZONE_PLANET_VAULT,
               ring_membership: bool = False,
               decay_rate: float = 0.02,
               ts: float | None = None) -> dict:
    """Build a ready-to-persist memory entry (plain dict).

    Position defaults to the parent planet's live [x,y,z] + small radial jitter.
    If planet_position is None (no clear owner / periphery), it sits at the origin.
    """
    now = time.time()
    ts = now if ts is None else float(ts)   # ts sets creation_ts (birth); last used defaults to NOW
    pos = _position_with_jitter(planet_position or [0.0, 0.0, 0.0])
    return {
        "entry_id": f"mem_{int(now * 1000)}_x{random.randint(0, 9999):04d}",
        "vector_position": pos,
        "mass": float(mass),
        "semantic_content": semantic_content,
        "creation_ts": ts,
        "last_accessed": now,
        "decay_rate": float(decay_rate),
        "ring_membership": bool(ring_membership),
        "zone": zone,
    }


def write_entry(entry: dict, base_dir: str) -> tuple[str, int]:
    """Append an entry to the JSON file for its zone. Returns (abs_path, new_count).

    Reads the store, appends, writes back — safe for incremental growth. The zone
    decides the destination file; unknown zones fall back to stochastic_periphery.

    PII GUARD (Seg 4): semantic_content is scrubbed via gate1.scrub_pii before it is
    persisted. Only the CLEANED text is ever written to disk; redactions are recorded
    in an audit field (type + count, never the raw matched string) so we can prove the
    guard fired without storing the PII itself.

    GUARD FAILURE POLICY: if the scrubber itself errors, _pii_guard returns the
    original text flagged with type 'pii_guard_error' — and this caller DROPS the
    entry (returns ("", 0)) rather than persisting unscrubbed content. A broken
    guard must never become a PII leak path.
    """
    # Scrub on the write path — this is the single choke point every zone passes through.
    cleaned, redactions = _pii_guard(entry.get("semantic_content", ""))
    if any(r.get("type") == "pii_guard_error" for r in redactions):
        print(f"[memory] PII guard error flagged — DROPPING entry (not persisting unscrubbed content). "
              f"zone={entry.get('zone')!r}")
        return ("", 0)
    to_store = dict(entry)
    to_store["semantic_content"] = cleaned
    if redactions:
        # Audit trail WITHOUT raw PII: types only. (scrub_pii's list carries 'match';
        # we intentionally drop it so the original value never touches disk.)
        to_store["pii_redacted_types"] = [r.get("type", "unknown") for r in redactions]
    rel = ZONE_FILE_REL.get(to_store.get("zone", ""),
                            ZONE_FILE_REL[ZONE_STOCHASTIC_PERIPHERY])
    path = os.path.join(base_dir, rel)
    store = _load_store(path)
    entries = store.setdefault("entries", [])
    entries.append(to_store)
    _save_store(store, path)
    return (path, len(entries))


# DECAY (Segment 3) — usage-frequency dependent (D-011).
# Frequently-accessed memories decay SLOWER. decay_rate = base / (1 + uses).
def _backdate_last_accessed(base_dir: str, rel_path: str, ts: float):
    """Test helper: set last_accessed (and creation_ts) of a store's entries to `ts`,
    so the decay sweep sees them as old. Only used by the self-test."""
    path = os.path.join(base_dir, rel_path)
    store = _load_store(path)
    for e in store.get("entries", []):
        e["last_accessed"] = float(ts)
        e["creation_ts"] = float(ts)
    _save_store(store, path)


def compute_decay_rate(access_count: int | None = None,
                       base_gamma: float | None = None) -> float:
    """Per-day decay rate for an entry, slower the more it has been used.

    access_count — how many times this memory has been re-encountered (default 0).
    """
    if base_gamma is None:
        import constants as C
        base_gamma = float(getattr(C, "DECAY_GAMMA_BASE", 0.02) or 0.0)
    return float(base_gamma / (1 + max(0, access_count or 0)))


def decay_sweep(base_dir: str, now_ts: float | None = None,
                min_mass: float | None = None) -> dict:
    """Walk every live memory store, apply exponential age decay to each entry's mass,
    and move anything below `min_mass` into compression_queue.json (Black Hole intake).

    Decay model:  mass_now = mass_orig * exp(-decay_rate * days_since_last_accessed)
      - decay_rate is per-day (DECAY_GAMMA_BASE=0.02 -> ~35-day half-life) and is
        usage-frequency dependent via the stored entry's own decay_rate field.
    Returns a report dict: {files, kept, decayed, moved_to_compression} counts.
    Only rewrites files that actually changed (avoids needless disk churn).
    """
    now_ts = time.time() if now_ts is None else float(now_ts)
    import constants as C
    if min_mass is None:
        min_mass = float(getattr(C, "MIN_ENTRY_MASS", 0.05) or 0.0)

    live_files = [os.path.join("memory", "planet_vaults.json"),
                  os.path.join("memory", "stochastic_periphery.json"),
                  os.path.join("ring", "swarm.json")]
    comp_path = os.path.join(base_dir, "memory", "compression_queue.json")

    report = {"files": 0, "kept": 0, "moved_to_compression": 0}
    swept = []   # all entries that fell below min_mass (across every live store)
    for rel in live_files:
        path = os.path.join(base_dir, rel)
        store = _load_store(path)
        entries = store.get("entries", [])
        report["files"] += 1
        if not entries:
            continue
        kept_entries = []
        for e in entries:
            last = float(e.get("last_accessed", e.get("creation_ts", now_ts)))
            days = max(0.0, (now_ts - last) / 86400.0)
            rate = float(e.get("decay_rate", 0.02))
            orig_mass = float(e.get("mass", 0.0))
            new_mass = orig_mass * math.exp(-rate * days)
            if new_mass < min_mass:
                e["mass"] = round(new_mass, 6)      # record final (dead) mass
                swept.append(e)
            else:
                e["mass"] = round(new_mass, 6)      # shrink in place; survived
                kept_entries.append(e)
        report["kept"] += len(kept_entries)
        if len(kept_entries) != len(entries):        # only rewrite if something moved out
            store["entries"] = kept_entries
            _save_store(store, path)
    
    # Black Hole intake: append everything that fell below the floor to the queue.
    if swept:
        report["moved_to_compression"] += len(swept)
        comp = _load_store(comp_path)
        for e in swept:
            comp.setdefault("entries", []).append(e)
        _save_store(comp, comp_path)
    return report


def assign_zone(routed_weights: dict[str, float] | None,
                ring_membership: bool = False) -> str:
    """Pick the zone for a new memory entry from this turn's routing weights.

    routed_weights — {planet_id: weight} (0..1 Gaussian shapes; all 7 present).
    Rule: ring membership wins first (it orbits the Ring, not C_core). Otherwise,
    if the top planet clearly dominates (> DOMINANCE_ZONE_RATIO x the runner-up)
    it owns a dedicated planet_vault. Else the entry is contested -> periphery.
    """
    if ring_membership:
        return ZONE_RING_SWARM
    import constants as C
    ratio = float(getattr(C, "DOMINANCE_ZONE_RATIO", 2.0) or 2.0)
    wts = [w for pid, w in (routed_weights or {}).items() if not str(pid).startswith("_")]
    if len(wts) >= 2:
        ranked = sorted((float(x) for x in wts), reverse=True)
        top, second = ranked[0], ranked[1]
        if second > 1e-9 and top / second > ratio and top > 1e-9:
            return ZONE_PLANET_VAULT
    return ZONE_STOCHASTIC_PERIPHERY


# ─── SELF-TEST ───────────────────────────────────────────────────────────────

def _self_test() -> None:
    print("memory.py self-test\n" + "=" * 50)
    s = SessionMemory()
    # Fake two turns with tiny fake "embeddings" (we don't need real MiniLM here).
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    now = time.time()
    s.record_turn("q1", v1, [0.5, 0.1, 0.0], tension=0.3)
    # Backdate the first turn by 10 minutes so decay is visible.
    s._history[0]["ts"] = now - 10 * 60
    s.record_turn("q2", v2, [0.1, 0.5, 0.0], tension=0.7)

    waves = s.get_background_waves(now_ts=now)
    print(f"background waves produced: {len(waves)} (expect 2)")
    for i, (u, a) in enumerate(waves):
        print(f"  wave[{i}] amp={a:.4f} dir_norm~{math.sqrt(sum(x*x for x in u)):.3f}")

    # G2 bias: no contents yet -> should be None.
    b = load_g2_bias_wave()
    print(f"g2 bias (empty contents) = {b!r}  (expect None)")

    # Layer 3 (Phase 4 Seg 1): memory mass + zone assignment. Pure math, no disk.
    sem = [1.0, 0.5, 0.0]                       # input semantic vector
    con_same = [2.0, 1.0, 0.0]                  # consensus aligned with it (cos=1)
    con_orth = [0.0, 0.0, 3.0]                  # consensus orthogonal to it (cos~0)
    m_aligned = compute_memory_mass(sem, con_same)      # expect ~1.0
    m_misaligned = compute_memory_mass(sem, con_orth)   # expect ~0.0
    m_none = compute_memory_mass(sem, None)             # expect 0.0 (no consensus)
    print(f"\nLayer 3: mass aligned={m_aligned:.4f} (~1.0), "
          f"misaligned={m_misaligned:.4f} (~0.0), none={m_none:.4f}")

    w_dom = {p: (0.8 if p == "hero" else 0.1) for p in ["sage", "magician", "caregiver",
                                                        "hero", "everyman", "rebel", "ruler"]}
    w_flat = {p: (0.30 if i < 4 else 0.29) for i, p in enumerate(
        ["sage", "magician", "caregiver", "hero", "everyman", "rebel", "ruler"])}
    z_dom = assign_zone(w_dom)                 # hero 0.8 vs 0.1 -> planet_vault
    z_flat = assign_zone(w_flat)               # no clear owner -> periphery
    z_ring = assign_zone(w_flat, ring_membership=True)  # ring membership wins -> ring_swarm
    print(f"Layer 3: zone dominant={z_dom} (expect planet_vault), "
          f"contested={z_flat} (expect stochastic_periphery), "
          f"ring={z_ring} (expect ring_swarm)")
    assert abs(m_aligned - 1.0) < 1e-6, "aligned mass should be ~base"
    assert m_misaligned < 1e-6, "misaligned mass should be ~0"
    assert z_dom == ZONE_PLANET_VAULT and z_flat == ZONE_STOCHASTIC_PERIPHERY
    assert z_ring == ZONE_RING_SWARM
    print("Layer 3 self-test: PASS")

    # Layer 3 (Phase 4 Seg 2): build an entry, write it to disk, read it back.
    # Uses a TEMP dir so real memory/ stores are never touched by the self-test.
    tmp = tempfile.mkdtemp(prefix="mem_seg2_")
    try:
        planet_pos = [1.0, 2.0, -1.0]
        e1 = make_entry("I like planning things carefully.", planet_pos,
                        mass=compute_memory_mass([1.0, 0.5, 0.0], [2.0, 1.0, 0.0]),
                        zone=ZONE_PLANET_VAULT)
        p1, n1 = write_entry(e1, tmp)                       # -> memory/planet_vaults.json
        e2 = make_entry("contested thought", None, mass=0.3,
                        zone=ZONE_STOCHASTIC_PERIPHERY)
        p2, n2 = write_entry(e2, tmp)                       # -> memory/stochastic_periphery.json
        # Re-read from disk to prove it persisted.
        back1 = _load_store(p1)["entries"]
        back2 = _load_store(p2)["entries"]
        print(f"\nLayer 3 S2: wrote vault entry -> {os.path.relpath(p1, tmp)} (count={n1})")
        print(f"Layer 3 S2: wrote periphery entry -> {os.path.relpath(p2, tmp)} (count={n2})")
        print(f"  read-back vault[0] pos={[round(x,4) for x in back1[0]['vector_position']]} "
              f"mass={back1[0]['mass']:.3f} zone={back1[0]['zone']}")
        # Invariants: position is near the planet (within jitter), mass carried over,
        # and both entries landed in their own files.
        import constants as C
        d = math.sqrt(sum((a - b) ** 2 for a, b in zip(back1[0]["vector_position"], planet_pos)))
        jitter_cap = float(getattr(C, "MEMORY_POSITION_JITTER", 0.05)) + 1e-9
        assert n1 == 1 and len(back2) == 1
        assert abs(back1[0]["mass"] - 1.0) < 1e-6
        if d > jitter_cap:
            raise AssertionError(f"jitter too large: {d} > {jitter_cap}")
        assert back2[0]["zone"] == ZONE_STOCHASTIC_PERIPHERY
        print("Layer 3 S2 self-test: PASS (write -> read-back verified)")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # Layer 3 (Phase 4 Seg 3): decay sweep. Fake old + recent entries in a temp dir.
    tmp3 = tempfile.mkdtemp(prefix="mem_seg3_")
    try:
        now3 = time.time()
        day = 86400.0
        # A fresh, high-mass entry (should survive). last_accessed=now -> no decay.
        fresh = make_entry("recent strong memory", [0.5, 0.5, 0.5], mass=0.9,
                           zone=ZONE_PLANET_VAULT, ts=now3)
        # An OLD entry: born AND last-used 300 days ago (never re-accessed since).
        # At gamma=0.02/day, mass 0.5 -> 0.5*exp(-0.02*300)=~1.3e-3, far below the
        # MIN_ENTRY_MASS floor of 0.05, so it must be swept to compression.
        old = make_entry("stale contested thought", None, mass=0.5,
                         zone=ZONE_STOCHASTIC_PERIPHERY)
        write_entry(old, tmp3)     # -> stochastic_periphery.json
        _backdate_last_accessed(tmp3, os.path.join("memory", "stochastic_periphery.json"),
                                now3 - 300 * day)
        write_entry(fresh, tmp3)   # -> planet_vaults.json (fresh; last_used=now)
        rep = decay_sweep(tmp3, now_ts=now3)
        print("\nLayer 3 S3: sweep report =", {k: rep[k] for k in rep})
        vault_kept = _load_store(os.path.join(tmp3, "memory", "planet_vaults.json"))["entries"]
        periph_kept = _load_store(os.path.join(tmp3, "memory", "stochastic_periphery.json"))["entries"]
        comp_q = _load_store(os.path.join(tmp3, "memory", "compression_queue.json"))["entries"]
        print(f"  vault kept={len(vault_kept)} (expect 1, fresh survived)")
        print(f"  periphery kept={len(periph_kept)} (expect 0, old decayed away)")
        print(f"  compression queue={len(comp_q)} (expect 1, the dead entry)")
        # Invariants:
        assert len(vault_kept) == 1 and vault_kept[0]["mass"] > 0.85   # fresh barely decayed
        assert len(periph_kept) == 0, "old entry should have fallen below floor"
        assert len(comp_q) == 1 and comp_q[0]["semantic_content"] == "stale contested thought"
        # The swept entry's recorded (final) mass is what pushed it below the floor.
        assert comp_q[0]["mass"] < float(getattr(C, "MIN_ENTRY_MASS", 0.05))
        # D-011: a frequently-used entry decays slower than an unused one.
        r_unused = compute_decay_rate(access_count=0)
        r_used = compute_decay_rate(access_count=4)
        print(f"  decay rate unused={r_unused:.4f}/day vs used(5x)={r_used:.4f}/day (used is slower)")
        assert r_used < r_unused
        print("Layer 3 S3 self-test: PASS")
    finally:
        import shutil
        shutil.rmtree(tmp3, ignore_errors=True)

    # Layer 3 (Phase 4 Seg 4): PII guard — write-path scrubbing.
    # Prove that raw emails/phones NEVER reach disk: only the redacted text is persisted,
    # and an audit field records that a redaction happened (type, not the value).
    tmp4 = tempfile.mkdtemp(prefix="mem_seg4_")
    try:
        pii_text = "My email is john.doe@example.com, call me at 555-867-5309 sometime."
        e_pii = make_entry(pii_text, [1.0, 0.0, 0.0], mass=0.7,
                           zone=ZONE_PLANET_VAULT)
        p4, n4 = write_entry(e_pii, tmp4)          # -> memory/planet_vaults.json
        on_disk = _load_store(p4)["entries"][-1]
        print("\nLayer 3 S4: PII guard (guard ON by default)")
        print(f"  raw in   : {pii_text}")
        print(f"  stored   : {on_disk['semantic_content']}")
        # Invariants:
        assert "john.doe@example.com" not in on_disk["semantic_content"], \
            "raw email must NOT be persisted"
        assert "555-867-5309" not in on_disk["semantic_content"], \
            "raw phone must NOT be persisted"
        assert "[REDACTED]" in on_disk["semantic_content"], \
            "redaction token should appear where PII was scrubbed"
        # Audit field present and names the redacted TYPES (not values).
        assert "pii_redacted_types" in on_disk, "expected an audit field listing redactions"
        # The raw matched value must not leak into the audit field either.
        assert all("example.com" not in str(t) and "867-5309" not in str(t)
                   for t in on_disk["pii_redacted_types"]), \
            "audit types must not contain the raw PII value"

        # Toggle OFF: with the guard disabled, write_entry stores the text unchanged.
        set_memory_pii_guard(False)
        try:
            e_off = make_entry(pii_text, [0.0, 1.0, 0.0], mass=0.7,
                               zone=ZONE_STOCHASTIC_PERIPHERY)
            p4b, _ = write_entry(e_off, tmp4)         # -> stochastic_periphery.json
            on_disk_off = _load_store(p4b)["entries"][-1]
            assert "john.doe@example.com" in on_disk_off["semantic_content"], \
                "guard OFF should persist text unchanged (reversibility check)"
        finally:
            set_memory_pii_guard(True)               # always restore default ON
        print("  guard OFF round-trip: raw persisted as expected, then restored to ON")

        # H2 fix (independent-review triage): a FAILED scrub must not raise AND the caller
        # must DROP the entry — unscrubbed content never reaches disk. Simulate by making
        # gate1.scrub_pii blow up mid-run.
        import gate1
        original_scrub = gate1.scrub_pii

        class _Boom(Exception):
            pass

        def _boom(_t: str):  # type: ignore[no-redef]
            raise _Boom("simulated scrub failure")

        gate1.scrub_pii = _boom
        try:
            e_fail = make_entry("my email is x@y.z (should never persist)", [0.0, 0.0, 1.0],
                                mass=0.7, zone=ZONE_PLANET_VAULT)
            p_drop, n_drop = write_entry(e_fail, tmp4)   # must NOT raise
            assert p_drop == "" and n_drop == 0, \
                f"failed scrub must drop the entry, got ({p_drop!r}, {n_drop})"
            vault_now = _load_store(os.path.join(tmp4, ZONE_FILE_REL[ZONE_PLANET_VAULT]))
            assert all(e.get("entry_id") != e_fail["entry_id"] for e in vault_now["entries"]), \
                "dropped entry must not appear on disk"
            print("  guard FAILURE round-trip: entry dropped, nothing persisted (H2 contract holds)")
        finally:
            gate1.scrub_pii = original_scrub
        print("Layer 3 S4 self-test: PASS (PII never reaches disk; toggle + failure-drop verified)")
    finally:
        import shutil
        shutil.rmtree(tmp4, ignore_errors=True)

    # summarize_session_for_g2 on a populated session:
    summ = summarize_session_for_g2(s, dominant_planets=["rebel", "sage"], avg_tension=0.5)
    print(f"session summary keys = {sorted(summ.keys()) if summ else 'None'}")
    if summ:
        print(f"  vec dim = {len(summ['vec'])}, turn_count={summ['turn_count']}")


if __name__ == "__main__":
    _self_test()
