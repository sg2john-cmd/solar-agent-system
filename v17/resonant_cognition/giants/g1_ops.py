"""
Resonant Cognition v17 — Phase 7, Segment 1: G1 Knowledge Archive Operations
============================================================================

G1 is the permanent knowledge store. It ACCUMULATES (very slow decay; entries are
compressed but not shed unless >6 months unused AND contradicted by newer content).

This module provides:
    - Ring buffer read/write (add candidate, list, check status)
    - The "AI slop test" as a deterministic scoring function:
        * consistency  — cosine alignment with existing G1 content vectors
        * operationality — does the entry reference actionable knowledge?
          (heuristic: contains verb+object structure markers; scored 0..1)
        * non-redundancy — minimum distance to any existing committed entry
    - Sleep Pass I hook: score ring entries → promote or eject
    - Offline self-test (zero LLM calls)

Design notes:
- G1 ring_buffer lives in giants/g1_knowledge.json under "ring_buffer" (list of dicts).
- Committed knowledge lives in the same file under "contents".
- Each entry has: id, text, vector_position (384-dim or null), mass, created_ts,
  last_used_ts, status ("pending" | "promoted" | "ejected"), score_breakdown.
- The scoring is PURE MATH (cosine + heuristics). No LLM calls in this segment.
  Phase 7 Seg 2 (filter moons) may add an optional LLM pass later.

RUN: python -X utf8 giants/g1_ops.py   (self-test, no LM Studio needed)
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
# Make the package root importable so `constants` resolves whether this module is
# run as a script (giants/g1_ops.py) or imported as giants.g1_ops.
_PKG_ROOT = os.path.dirname(_HERE)
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)
try:
    import constants
except ImportError:  # pragma: no cover — direct-script fallback when root not found
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    try:
        import constants
    except ImportError:
        class _NoConsts:
            def __getattr__(self, name):
                return False
        constants = _NoConsts()
_G1_PATH = os.path.join(_HERE, "g1_knowledge.json")


# ─── TUNABLES (local until calibration proves them; then promote to constants.py) ──

# Minimum composite score for promotion. Below this → ejected as "AI slop".
G1_PROMOTE_THRESHOLD = 0.55

# An entry is considered "contradicted by newer" if a NEWER entry has cosine > 
# CONTRADICT_COSINE in the OPPOSITE direction (i.e., dot < -CONTRADICT_COSINE).
G1_CONTRADICT_COSINE = 0.7

# Staleness: unused for more than this many days AND contradicted → eligible for shed.
G1_STALENESS_DAYS = 180  # ~6 months per Build Plan

# Peripheral verdict mass factor (C1 wiring): when the Relevance moon flags a candidate
# as peripheral, it is still promoted but its gravitational mass is scaled down by this
# factor so it exerts less pull than a full-strength match. GUESS — tune after live runs.
G1_PERIPHERAL_MASS_FACTOR = 0.5

# Non-redundancy floor: if cosine to any committed entry exceeds this, the candidate
# is "too similar" (redundant) and scores low on the non-redundancy axis.
G1_REDUNDANCY_CEILING = 0.95

# Text overlap threshold for confirming a vector-level duplicate is truly redundant.
# If vectors are near-identical BUT text Jaccard < this, they "sound similar" but
# carry different context → NOT a true duplicate; score normally.
G1_TEXT_OVERLAP_CONFIRM = 0.70


# ─── VECTOR MATH HELPERS ──────────────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0 for zero/near-zero vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a < 1e-9 or mag_b < 1e-9:
        return 0.0
    return dot / (mag_a * mag_b)


def _text_jaccard(text_a: str, text_b: str) -> float:
    """Jaccard overlap on content words (lowercased, stopwords removed).
    Returns 0..1. Used to confirm whether two vector-similar entries actually
    say the same thing or just orbit in the same neighbourhood for different reasons."""
    import re
    # NOTE: this is a MINIMAL stopword list (zero external deps). It covers the
    # most common English function words. If a future test shows a short word
    # leaking through as a content token, add it here — do NOT lower the Jaccard
    # threshold to compensate.
    _STOP = frozenset(
        "a an and are as at be been but by can could did do does done for from had has have he her his i if in into is it its just me my no not of off on or our out over own she so than that the their them then there these they this those to under up upon us was we were what when where which while who whom why will with would you your"
    )

    def _tokens(text: str) -> set[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        return {w for w in words if w not in _STOP and len(w) > 1}

    ta, tb = _tokens(text_a or ""), _tokens(text_b or "")
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    return len(intersection) / len(union) if union else 0.0


# ─── FILE I/O ─────────────────────────────────────────────────────────────────

def _load_g1(path: str | None = None) -> dict:
    """Load G1 JSON from disk."""
    p = path or _G1_PATH
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save_g1(data: dict, path: str | None = None) -> None:
    """Write G1 JSON back to disk (atomic-ish: write to temp then replace)."""
    p = path or _G1_PATH
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


# ─── RING BUFFER OPERATIONS ──────────────────────────────────────────────────

def g1_add_candidate(
    text: str,
    vector_position: list[float] | None = None,
    mass: float = 0.3,
    path: str | None = None,
) -> dict:
    """Add a knowledge candidate to G1's ring buffer (uncommitted).

    Returns the entry dict as written. The candidate sits in "pending" status
    until Sleep Pass I scores it and promotes or ejects it.
    """
    g1 = _load_g1(path)
    entry: dict = {
        "id": f"g1_rb_{uuid.uuid4().hex[:8]}",
        "text": text,
        "vector_position": vector_position,
        "mass": max(0.01, min(mass, 1.0)),
        "created_ts": time.time(),
        "last_used_ts": time.time(),
        "status": "pending",
        "score_breakdown": None,
    }
    g1.setdefault("ring_buffer", []).append(entry)
    _save_g1(g1, path)
    return entry


def g1_list_candidates(path: str | None = None, status: str | None = None) -> list[dict]:
    """List ring buffer entries, optionally filtered by status."""
    g1 = _load_g1(path)
    entries = g1.get("ring_buffer", []) or []
    if status is not None:
        entries = [e for e in entries if e.get("status") == status]
    return entries


def g1_get_committed(path: str | None = None) -> list[dict]:
    """List committed (promoted) knowledge entries."""
    g1 = _load_g1(path)
    return g1.get("contents", []) or []


# ─── THE "AI SLOP TEST" — DETERMINISTIC SCORING ──────────────────────────────

def g1_score_candidate(
    candidate: dict,
    committed_entries: list[dict],
) -> dict:
    """Score a ring-buffer candidate against existing G1 content.

    Three axes (each 0..1):
        consistency   — average cosine alignment with committed entries that have vectors.
                        Higher = more consistent with the archive's knowledge space.
                        If no committed entries have vectors, defaults to 0.5 (neutral).
        operationality— heuristic: does the text contain actionable structure?
                        Scored by presence of action verbs / imperative markers.
                        Simple keyword-based; will be refined if LLM moons are added later.
        non_redundancy— 1 - max(cosine to any committed entry with a vector).
                        Higher = more novel. If cosine > G1_REDUNDANCY_CEILING → ~0.

    Composite = weighted average: 0.4 * consistency + 0.3 * operationality + 0.3 * non_redundancy

    Returns: {"composite": float, "consistency": float, "operationality": float,
              "non_redundancy": float}
    """
    # --- Consistency ---
    cand_vec = candidate.get("vector_position") or []
    committed_vecs = [e.get("vector_position") for e in committed_entries if e.get("vector_position")]

    if cand_vec and committed_vecs:
        aligns = [_cosine(cand_vec, cv) for cv in committed_vecs]
        consistency = max(0.0, sum(aligns) / len(aligns))  # clamp to [0,1]
    elif not committed_vecs:
        consistency = 0.5  # neutral when archive is empty
    else:
        consistency = 0.3  # candidate has no vector; can't measure alignment

    # --- Operationality (simple heuristic) ---
    text_lower = (candidate.get("text") or "").lower()
    action_markers = [
        "use", "apply", "set", "configure", "implement", "run", "execute",
        "check", "verify", "ensure", "validate", "test", "deploy", "build",
        "calculate", "compute", "derive", "solve", "optimize", "reduce",
        "increase", "decrease", "limit", "cap", "threshold", "tolerance",
    ]
    hits = sum(1 for m in action_markers if m in text_lower)
    # Scale: 0 hits → 0.2 (baseline), 5+ hits → 1.0
    operationality = min(1.0, 0.2 + 0.16 * hits)

    # --- Non-redundancy ---
    if cand_vec and committed_vecs:
        max_sim = max(_cosine(cand_vec, cv) for cv in committed_vecs)
        non_redundancy = max(0.0, 1.0 - max(max_sim, 0.0))
        # Penalize hard if above redundancy ceiling
        if max_sim > G1_REDUNDANCY_CEILING:
            non_redundancy *= 0.3  # heavy penalty for near-duplicates
    else:
        non_redundancy = 0.5  # neutral when can't measure

    composite = 0.4 * consistency + 0.3 * operationality + 0.3 * non_redundancy
    return {
        "composite": round(composite, 4),
        "consistency": round(consistency, 4),
        "operationality": round(operationality, 4),
        "non_redundancy": round(non_redundancy, 4),
    }


# ─── SLEEP PASS I HOOK: PROMOTE / EJECT ──────────────────────────────────────

def g1_sleep_pass_i(path: str | None = None) -> dict:
    """Score all pending ring-buffer candidates and promote or eject.

    Called during deep sleep (or can be invoked standalone for testing).
    
    For each pending entry:
        1. Score it against current committed contents.
        2. If composite >= G1_PROMOTE_THRESHOLD → PROMOTE:
           Move from ring_buffer to contents, status="promoted".
        3. Else → EJECT:
           Mark status="ejected" with score_breakdown (stays in ring_buffer for audit).
    
    Also checks staleness: if a committed entry is >G1_STALENESS_DAYS unused AND
    contradicted by a newer entry, mark it "contradicted_stale" (flagged but NOT
    deleted — G1 accumulates; only explicit user action removes entries permanently).

    Returns report: {"promoted": [...], "ejected": [...], "stale_flagged": [...],
                     "total_pending": int}
    """
    g1 = _load_g1(path)
    ring = g1.get("ring_buffer", []) or []
    committed = g1.get("contents", []) or []

    promoted: list[dict] = []
    ejected: list[dict] = []
    held_for_review: list[dict] = []
    remaining_ring: list[dict] = []

    # C1 FIX — G1 filter moons (production safety rail). When the toggle is on,
    # each pending candidate runs through the 3-moon LLM pre-pass BEFORE scoring.
    # Dev mode (toggle OFF) leaves this off → byte-identical to Segment 1, zero
    # extra LLM calls. Gated by constants.G1_FILTER_MOONS_ENABLED (mandatory ON at release).
    _moons_on = bool(getattr(constants, "G1_FILTER_MOONS_ENABLED", False))
    if _moons_on:
        from giants.g1_filter_moons import apply_filter_moons_to_sleep_pass as _apply_moons
    else:
        _apply_moons = None

    for entry in ring:
        if entry.get("status") != "pending":
            # Already processed (ejected/flagged from a prior pass); keep for audit trail.
            remaining_ring.append(entry)
            continue

        moon_verdict: str | None = None
        if _apply_moons is not None:
            entry, moon_verdict = _apply_moons(entry, g1, recent_topics=None)

        # Moon verdicts take precedence over the deterministic scoring below.
        if moon_verdict == "rejected_clarity":
            # Clarity moon: content too incoherent to store — eject with reason.
            entry["status"] = "ejected"
            entry["ejected_ts"] = time.time()
            entry["reject_reason"] = "moon_rejected_clarity"
            entry["_moon_verdict"] = moon_verdict
            ejected.append(entry)
            remaining_ring.append(entry)
            continue
        if moon_verdict == "flagged_contradiction":
            # Dissonance moon: conflicts with committed knowledge — hold for review,
            # do NOT promote or eject this pass. Stays pending-ish but flagged so a
            # human can reconcile it (mirrors Tier-2 hold semantics).
            entry["status"] = "flagged_contradiction"
            entry["_moon_verdict"] = moon_verdict
            remaining_ring.append(entry)
            held_for_review.append({"id": entry.get("id")})
            continue

        score = g1_score_candidate(entry, committed)
        entry["score_breakdown"] = score

        # Hard-reject near-duplicates: vector says "same neighbourhood" AND text
        # actually overlaps enough to confirm it's the same knowledge restated.
        # If vectors are close but texts diverge (different context, similar topic),
        # treat as distinct — the orbital proximity is coincidental, not redundancy.
        is_duplicate = False
        if entry.get("vector_position") and committed and score["non_redundancy"] < 0.05:
            cand_vec = entry.get("vector_position")
            best_sim, best_text = -2.0, ""
            for ce in committed:
                cv = ce.get("vector_position") or []
                if not cv:
                    continue
                s = _cosine(cand_vec, cv)
                if s > best_sim:
                    best_sim, best_text = s, (ce.get("text") or "")
            overlap = _text_jaccard(entry.get("text") or "", best_text)
            is_duplicate = overlap >= G1_TEXT_OVERLAP_CONFIRM
            entry["_debug_text_overlap"] = round(overlap, 3)

        if not is_duplicate and score["composite"] >= G1_PROMOTE_THRESHOLD:
            # PROMOTE: move to contents
            entry["status"] = "promoted"
            entry["promoted_ts"] = time.time()
            # Peripheral verdict (Relevance moon): promote at reduced mass so it is
            # stored but carries less gravitational weight than a full-strength match.
            if moon_verdict == "peripheral":
                base_mass = float(entry.get("mass") or 0.5)
                entry["original_mass"] = base_mass
                entry["mass"] = round(base_mass * G1_PERIPHERAL_MASS_FACTOR, 4)
                entry["peripheral"] = True
            if moon_verdict:
                entry["_moon_verdict"] = moon_verdict
            promoted.append(entry)
            committed.append(entry)  # add to committed list for subsequent scoring
        else:
            # EJECT: stay in ring buffer with status="ejected" (audit trail)
            entry["status"] = "ejected"
            entry["ejected_ts"] = time.time()
            if is_duplicate:
                entry["reject_reason"] = "near_duplicate_of_committed_entry"
            ejected.append(entry)
            remaining_ring.append(entry)

    # Staleness check on committed entries
    stale_flagged: list[dict] = []
    now = time.time()
    for i, c in enumerate(committed):
        last_used = c.get("last_used_ts", c.get("created_ts", 0))
        days_unused = (now - last_used) / 86400.0
        if days_unused > G1_STALENESS_DAYS:
            # Check for contradiction by newer entries
            c_vec = c.get("vector_position") or []
            contradicted = False
            if c_vec:
                for other in committed:
                    if other is c:
                        continue
                    o_vec = other.get("vector_position") or []
                    if o_vec and other.get("created_ts", 0) > c.get("created_ts", 0):
                        if _cosine(c_vec, o_vec) < -G1_CONTRADICT_COSINE:
                            contradicted = True
                            break
            if contradicted:
                c["contradicted_stale"] = True
                stale_flagged.append({"id": c["id"], "days_unused": round(days_unused, 1)})

    # Write back
    g1["ring_buffer"] = remaining_ring
    g1["contents"] = committed
    _save_g1(g1, path)

    def _entry_summary(e: dict) -> dict:
        return {
            "id": e["id"],
            "text": e.get("text", "")[:200],
            "composite": (e.get("score_breakdown") or {}).get("composite"),
            "reject_reason": e.get("reject_reason", ""),
            "moon_verdict": e.get("_moon_verdict", ""),
        }

    return {
        "promoted": [_entry_summary(e) for e in promoted],
        "ejected": [_entry_summary(e) for e in ejected],
        "held_for_review": held_for_review,
        "stale_flagged": stale_flagged,
        "total_pending": len(promoted) + len(ejected),
    }


# ─── SELF-TEST (offline, zero LLM) ──────────────────────────────────────────

def _self_test() -> None:
    import tempfile, shutil

    print("=" * 64)
    print("g1_ops.py — Phase 7 Segment 1 self-test (G1 ring buffer + AI slop test)")
    print("=" * 64)

    tmp = tempfile.mkdtemp(prefix="g1_s1_")
    # Copy the real G1 JSON as our working file (empty ring_buffer + contents).
    g1_path = os.path.join(tmp, "g1_knowledge.json")
    shutil.copy2(_G1_PATH, g1_path)

    failures: list[str] = []

    def check(label: str, cond: bool) -> None:
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {label}")
        if not cond:
            failures.append(label)

    try:
        # ── [1] Add candidate to empty ring buffer.
        e1 = g1_add_candidate(
            text="Set the orbital integrator timestep to 0.01 for stability.",
            vector_position=[1.0, 0.5, 0.0, 0.0],  # short vec for test simplicity
            mass=0.4,
            path=g1_path,
        )
        check("[1] Candidate added with status=pending", e1["status"] == "pending")

        cands = g1_list_candidates(g1_path)
        check("[1] Ring buffer has 1 entry after add", len(cands) == 1)

        # ── [2] Add a second candidate (different vector).
        e2 = g1_add_candidate(
            text="Verify that the PII guard strips email addresses before storage.",
            vector_position=[0.0, 1.0, 0.5, 0.0],
            mass=0.35,
            path=g1_path,
        )
        check("[2] Second candidate added", len(g1_list_candidates(g1_path)) == 2)

        # ── [3] Score against empty committed set (neutral consistency).
        score_empty = g1_score_candidate(e1, [])
        check("[3] Score vs empty archive: consistency=0.5 (neutral)",
              score_empty["consistency"] == 0.5)
        check("[3] Operationality > 0 for action-text",
              score_empty["operationality"] > 0.2)

        # ── [4] Promote first candidate manually to seed committed set.
        g1_data = _load_g1(g1_path)
        # Move e1 from ring_buffer to contents (simulate prior promotion).
        ring = g1_data["ring_buffer"]
        contents = g1_data["contents"]
        for r in list(ring):
            if r["id"] == e1["id"]:
                r["status"] = "promoted"
                ring.remove(r)
                contents.append(r)
        _save_g1(g1_data, g1_path)

        committed_now = g1_get_committed(g1_path)
        check("[4] Committed set has 1 entry", len(committed_now) == 1)

        # ── [5] Score e2 against the now-non-empty archive.
        score_e2 = g1_score_candidate(e2, committed_now)
        check("[5] Consistency measured (not neutral)",
              score_e2["consistency"] != 0.5 or len(committed_now) == 0)
        # e2's vector [0,1,0.5,0] vs e1's [1,0.5,0,0]: cosine should be moderate.
        expected_cos = _cosine([0.0, 1.0, 0.5, 0.0], [1.0, 0.5, 0.0, 0.0])
        check("[5] Consistency matches manual cosine",
              abs(score_e2["consistency"] - expected_cos) < 0.01)

        # ── [6] Redundancy: add a TRUE near-duplicate (same vector AND same meaning).
        dup_vec = [1.0, 0.5, 0.0, 0.0]  # identical to e1
        g1_add_candidate(
            # Tighter paraphrase of e1: shares nearly every content word, only
            # reorders/rewrites one verb. Jaccard should be well above 0.70.
            text="The orbital integrator timestep is set to 0.01 for stability.",
            vector_position=dup_vec,
            mass=0.3,
            path=g1_path,
        )
        dup_entry = g1_list_candidates(g1_path, status="pending")[-1]
        score_dup = g1_score_candidate(dup_entry, committed_now)
        check("[6] True duplicate has low non_redundancy (< 0.3)",
              score_dup["non_redundancy"] < 0.3)

        # ── [6b] "Sounds similar but different context": same vector neighbourhood,
        #         but text is about a completely different operational concern.
        g1_add_candidate(
            text="Verify the sleep stagger interval prevents overlapping planet commits during deep pass four rotation cycle.",
            vector_position=[0.95, 0.55, 0.0, 0.0],  # very close to e1's [1.0, 0.5, 0.0, 0.0]
            mass=0.3,
            path=g1_path,
        )
        similar_ctx = g1_list_candidates(g1_path, status="pending")[-1]
        score_similar = g1_score_candidate(similar_ctx, committed_now)
        check("[6b] Similar-context entry also has low vector non_redundancy",
              score_similar["non_redundancy"] < 0.05)

        # ── [7] Run Sleep Pass I: should promote good entries, eject true duplicates.
        report = g1_sleep_pass_i(g1_path)
        check("[7] Report has total_pending == number processed",
              report["total_pending"] >= 3)  # e2 + the dup + similar_ctx (e1 already committed)

        # The TRUE duplicate should be ejected (vector AND text both match).
        dup_id = dup_entry["id"]
        check("[7] True duplicate was ejected",
              any(ej["id"] == dup_id for ej in report["ejected"]))

        # The "sounds similar but different context" entry must NOT be rejected as a
        # duplicate — it may be promoted or ejected on composite score, but the reason
        # must not be near_duplicate_of_committed_entry.
        sim_id = similar_ctx["id"]
        g1_check = _load_g1(g1_path)
        sim_on_disk = next(
            (e for e in g1_check.get("ring_buffer", []) + g1_check.get("contents", [])
             if e["id"] == sim_id), None
        )
        check("[7] Similar-context entry NOT rejected as duplicate",
              sim_on_disk is not None
              and sim_on_disk.get("reject_reason") != "near_duplicate_of_committed_entry")

        # ── [8] Verify disk state after Pass I.
        g1_after = _load_g1(g1_path)
        promoted_ids = {c["id"] for c in g1_after["contents"]}
        check("[8] Promoted entries are in contents",
              any(c["status"] == "promoted" for c in g1_after["contents"]))

        # Ejected entry stays in ring_buffer with status="ejected".
        ejected_entries = [r for r in g1_after["ring_buffer"] if r.get("status") == "ejected"]
        check("[8] Ejected entries remain in ring buffer (audit trail)",
              len(ejected_entries) >= 1)

        # ── [9] Idempotency: run Pass I again, nothing new to process.
        report2 = g1_sleep_pass_i(g1_path)
        check("[9] Second pass processes 0 pending (idempotent)",
              report2["total_pending"] == 0)

        # ── [10] Staleness: backdate a committed entry to >6 months, add contradicting.
        g1_data = _load_g1(g1_path)
        if g1_data["contents"]:
            old_entry = g1_data["contents"][0]
            old_entry["last_used_ts"] = time.time() - (200 * 86400)  # 200 days ago
            old_vec = old_entry.get("vector_position") or [0.0, 0.0, 0.0]
            # Add a NEW committed entry with OPPOSITE vector (contradiction).
            contradicting = {
                "id": "g1_test_contra",
                "text": "Contradicting knowledge for staleness test.",
                "vector_position": [-v for v in old_vec] if any(old_vec) else [0.0, 0.0, 0.0],
                "mass": 0.5,
                "created_ts": time.time(),
                "last_used_ts": time.time(),
                "status": "promoted",
            }
            g1_data["contents"].append(contradicting)
            _save_g1(g1_data, g1_path)

        report3 = g1_sleep_pass_i(g1_path)
        # The old entry should be flagged as contradicted_stale (if vectors are opposite).
        check("[10] Staleness flag logic ran without error", isinstance(report3, dict))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"g1_ops.py Segment 1 self-test: {len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  ✗ {f}")
        raise SystemExit(1)
    else:
        print("g1_ops.py Segment 1 self-test: ALL PASS (G1 ring buffer + AI slop test)")


if __name__ == "__main__":
    _self_test()
