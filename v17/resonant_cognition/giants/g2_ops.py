"""
Resonant Cognition v17 — Phase 7, Segment 3: G2 Self-Model Operations + Moons
==============================================================================

G2 is the evolving self-model. It tracks how the system thinks and speaks over
time. Unlike G1 (permanent knowledge), G2 entries decay (~4 week half-life) and
consolidated truths are re-emitted via White Hole pass during sleep.

This module provides:
    - Ring buffer read/write for proposed self-changes
    - The THREE G2 moons, all DETERMINISTIC (zero LLM calls):
        1. CONSISTENCY_GATE   — check against core_laws.json; hold on violation
        2. MAGNITUDE_GATE     — cap per-session delta to self-vector at G2_MAGNITUDE_CAP
        3. REVERSIBILITY_LOG  — snapshot before-state before any commit (append-only)
    - g2_sleep_pass_i()      — the deep-sleep hook that runs all three moons on
                               each ring_buffer candidate, then promotes or holds
    - Offline self-test (zero LLM calls): python -X utf8 giants/g2_ops.py

Design notes:
- G2's ring_buffer lives in giants/g2_selfmodel.json under "ring_buffer".
  Committed entries move to "contents" after passing all three moons.
- Each entry has: id, text (or report_text), vector_position (optional), mass,
  created_ts, status ("pending"|"committed"|"held_law_check"|"clamped"), 
  before (snapshot dict or []), tier, debate (if from self-review).
- The moons are STRUCTURAL SAFETY RAILS — they don't judge semantic quality
  (that's G1's job via LLM moons). They enforce:
    * the system cannot violate its own Core Laws (absolute constraint)
    * no single session can rewrite who the system "is" (magnitude cap)
    * every change is reversible (before-state logged, append-only)

RUN: python -X utf8 giants/g2_ops.py   (self-test, no LM Studio needed)
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_GIANTS_DIR = _HERE
# Make sure the package root is on sys.path so we can import constants.py.
_PKG_ROOT = os.path.dirname(_HERE)
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)
_G2_PATH = os.path.join(_GIANTS_DIR, "g2_selfmodel.json")

# Segment 5: deterministic growth-policy tiering (same package dir as this module).
try:
    from giants.g2_growth_policy import g2_classify_tier as _g2_classify_tier
except ImportError:  # pragma: no cover — direct-script fallback when not a package
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    from g2_growth_policy import g2_classify_tier as _g2_classify_tier

# Also need core_laws.json for the Consistency Gate. It lives at the project root
# (one level up from giants/). If not found there, try the current dir.
_CORE_LAWS_CANDIDATES = [
    os.path.join(_HERE, "..", "core", "core_laws.json"),  # giants/../core/core_laws.json (actual location)
    os.path.join(_HERE, "..", "core_laws.json"),          # legacy: project root
    os.path.join(os.getcwd(), "core", "core_laws.json"),   # fallback: cwd/core/
    os.path.join(os.getcwd(), "core_laws.json"),           # fallback: cwd (legacy)
]


# ─── TUNABLES ─────────────────────────────────────────────────────────────────
# Source of truth for G2 thresholds lives in constants.py. We import from there
# (single source) and re-export local names for backward-compat with any code
# that does `from g2_ops import G2_MAGNITUDE_CAP`.
try:
    from constants import G2_MAGNITUDE_CAP as _CONST_G2_CAP, G2_ESCAPE_THRESHOLD as _CONST_G2_ESC
except ImportError:  # pragma: no cover — fallback if run in an isolated context
    _CONST_G2_CAP = 0.15
    _CONST_G2_ESC = 0.30

G2_MAGNITUDE_CAP = _CONST_G2_CAP          # max per-session delta to self-vector
ESCAPE_THRESHOLD = _CONST_G2_ESC          # Consistency Gate hold threshold (2× cap)


# ─── VECTOR MATH (local copy to keep g2_ops self-contained) ──────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a < 1e-9 or mag_b < 1e-9:
        return 0.0
    return dot / (mag_a * mag_b)


def _vector_magnitude(v: list[float]) -> float:
    """Euclidean norm of a vector."""
    return math.sqrt(sum(x * x for x in v)) if v else 0.0


def _clamp_vector_to_cap(vec: list[float], cap: float) -> tuple[list[float], bool]:
    """Clamp a delta vector to `cap` magnitude, preserving direction.

    Returns (clamped_vec, was_clamped). If the vector is already within cap,
    returns it unchanged with was_clamped=False.
    """
    mag = _vector_magnitude(vec)
    if mag <= cap or mag < 1e-9:
        return vec, False
    scale = cap / mag
    clamped = [x * scale for x in vec]
    return clamped, True


# ─── FILE I/O ─────────────────────────────────────────────────────────────────

def _load_g2(path: str | None = None) -> dict:
    p = path or _G2_PATH
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save_g2(data: dict, path: str | None = None) -> None:
    p = path or _G2_PATH
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _load_core_laws() -> list[dict]:
    """Load core_laws.json. Returns [] if not found (Consistency Gate degrades gracefully)."""
    for candidate in _CORE_LAWS_CANDIDATES:
        try:
            with open(candidate, encoding="utf-8") as f:
                data = json.load(f)
                # The file may be a list or a dict with "laws" key
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "laws" in data:
                    return data["laws"]
                return []
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return []


# ─── RING BUFFER OPERATIONS ──────────────────────────────────────────────────

def g2_add_candidate(
    text: str,
    vector_position: list[float] | None = None,
    mass: float = 0.3,
    tier: int = 1,
    kind: str | None = None,
    path: str | None = None,
) -> dict:
    """Add a proposed self-change to G2's ring_buffer (status=pending).

    Args:
        text:            The description of the proposed change or observation.
        vector_position: Optional 384-dim (or shorter for tests) delta vector.
                         If None, the Magnitude Gate skips (no vector to cap).
        mass:            Initial mass (0..1). G2 entries decay at ~4-week half-life.
        tier:            Growth policy tier. 1=autonomous, 2=pending_user_approval.
                         NOTE: this is a HINT / initial label only. The authoritative
                         Tier decision is made deterministically by g2_growth_policy.
                         g2_classify_tier() inside the sleep pass — so passing tier=1
                         does NOT let a structural change slip past approval.
        kind:            Optional structural tag for the growth-policy classifier, e.g.
                         "anchor_migration". Combined with vector magnitude it decides
                         Tier 1 vs Tier 2 (see g2_growth_policy.py).
    """
    data = _load_g2(path)
    entry = {
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "vector_position": vector_position,
        "mass": mass,
        "tier": tier,
        "status": "pending",
        "created_ts": time.time(),
        "before": [],  # REVERSIBILITY_LOG will fill this before commit
    }
    if kind is not None:
        entry["kind"] = kind
    data.setdefault("ring_buffer", []).append(entry)
    _save_g2(data, path)
    return entry


def g2_list_candidates(path: str | None = None, status: str | None = None) -> list[dict]:
    """List ring_buffer entries, optionally filtered by status."""
    data = _load_g2(path)
    entries = data.get("ring_buffer", [])
    if status is not None:
        return [e for e in entries if e.get("status") == status]
    return list(entries)


def g2_get_committed(path: str | None = None) -> list[dict]:
    """Return committed G2 contents (the current self-model state)."""
    data = _load_g2(path)
    return list(data.get("contents", []))


# ─── MOON 1: CONSISTENCY_GATE ────────────────────────────────────────────────

def g2_moon_consistency(
    entry: dict,
    core_laws: list[dict] | None = None,
) -> tuple[bool, str]:
    """Check a proposed self-change against the Core Laws.

    Returns (passed: bool, reason: str).
      - passed=True  → no law violation detected; entry may proceed.
      - passed=False → entry should be HELD in ring_buffer with status="held_law_check".

    The check is DETERMINISTIC and STRUCTURAL — it does NOT use an LLM to judge
    whether the change is "good." It checks whether the proposed vector delta or
    text would conflict with any ABSOLUTE-tier law (tier=1 in core_laws.json).

    How it works:
      1. Load absolute laws (those marked as absolute/primary tier).
      2. If the entry has a vector_position, check its MAGNITUDE against an
         escape threshold (G2_MAGNITUDE_CAP * 2). A large-magnitude delta in ANY
         direction — inward or outward — is held for review, because both
         "escaping gravitational containment" (outward) and a violent collapse
         toward the core (inward) are structural risks Law #1/#3 guard against.
         Directionality is intentionally NOT checked: magnitude-only is the more
         conservative bound and avoids false-passing a large inward vector that
         would compress the system's internal spacing.
      3. If no vector is present, pass (text-only entries are checked by the
         sandbox in Segment 4, not here).

    This is intentionally CONSERVATIVE: when in doubt, HOLD rather than commit.
    The entry stays in ring_buffer with status="held_law_check" and a note
    explaining which law triggered the hold. It can be reviewed manually or
    re-evaluated on the next sleep pass.
    """
    if core_laws is None:
        core_laws = _load_core_laws()

    # No laws loaded → nothing to check against; pass with a note.
    if not core_laws:
        return True, "No core laws loaded — Consistency Gate skipped (degraded mode)."

    vec = entry.get("vector_position")
    if not vec:
        # Text-only entries: the sandbox (Segment 4) handles semantic checks.
        # The Consistency Gate only applies to vector-bearing changes here.
        return True, "No vector — Consistency Gate defers to sandbox (Seg 4)."

    # Magnitude check (directionality intentionally NOT checked — see docstring).
    # A large-magnitude delta in any direction is a structural risk: outward
    # vectors threaten gravitational containment; inward vectors compress the
    # system's internal spacing. Both are held for review under Law #1/#3.
    mag = _vector_magnitude(vec)
    if mag < 1e-9:
        return True, "Zero-magnitude delta — no gravitational effect."

    # Escape threshold: G2_MAGNITUDE_CAP * 2 (GUESS value — tune after live runs).
    ESCAPE_THRESHOLD = G2_MAGNITUDE_CAP * 2

    if mag > ESCAPE_THRESHOLD:
        reason = (
            f"Vector magnitude {mag:.4f} exceeds escape threshold {ESCAPE_THRESHOLD:.4f}. "
            f"Held for review — potential gravitational containment violation."
        )
        return False, reason

    return True, "Within safe bounds — no law violation detected."


# ─── MOON 2: MAGNITUDE_GATE ──────────────────────────────────────────────────

def g2_moon_magnitude(
    entry: dict,
) -> tuple[dict, bool]:
    """Cap the proposed vector delta to G2_MAGNITUDE_CAP.

    Returns (modified_entry, was_clamped).
      - If the entry's vector_position magnitude exceeds the cap, it is clamped
        to exactly CAP magnitude in the same direction, and status is set to
        "clamped" so the user can audit what was limited.
      - If within cap, the entry passes through unchanged (was_clamped=False).

    This moon MUTATES the entry dict in-place AND returns it for convenience.
    The caller is responsible for saving back to disk.
    """
    vec = entry.get("vector_position")
    if not vec:
        return entry, False  # no vector to cap

    clamped_vec, was_clamped = _clamp_vector_to_cap(vec, G2_MAGNITUDE_CAP)
    if was_clamped:
        original_mag = _vector_magnitude(vec)
        entry["original_vector_position"] = vec          # audit trail
        entry["original_magnitude"] = round(original_mag, 6)
        entry["clamped_to_magnitude"] = G2_MAGNITUDE_CAP
        entry["vector_position"] = clamped_vec
        if entry.get("status") == "pending":
            entry["status"] = "clamped"
    return entry, was_clamped


# ─── MOON 3: REVERSIBILITY_LOG ──────────────────────────────────────────────

def g2_moon_reversibility(
    entry: dict,
    current_contents: list[dict],
) -> dict:
    """Snapshot the BEFORE-state into the entry before commit.

    This is called IMMEDIATELY before an entry moves from ring_buffer to contents.
    It records:
      - "before": a copy of the relevant existing content that this change modifies
        (if the entry targets an existing committed entry by id) or [] if it's a
        new addition.
      - "committed_ts": timestamp of the commit.

    The log is APPEND-ONLY — entries in contents are never overwritten, only
    appended to. If a walk-back is needed later, the "before" field tells you
    exactly what state to restore.

    Returns the modified entry (with before-state filled in).
    """
    # Find if this entry targets an existing committed entry for modification.
    target_id = entry.get("targets_entry_id")  # optional: which existing entry it modifies
    before_snapshot = []
    if target_id:
        for c in current_contents:
            if c.get("id") == target_id:
                before_snapshot.append(dict(c))  # deep-ish copy (shallow is fine for JSON)
                break

    entry["before"] = before_snapshot
    entry["committed_ts"] = time.time()
    return entry


# ─── SLEEP PASS I FOR G2 (the main hook) ─────────────────────────────────────

def g2_sleep_pass_i(path: str | None = None, recent_topics: list[str] | None = None) -> dict:
    """Run all three G2 moons on each pending ring_buffer candidate.

    For each pending entry:
      1. CONSISTENCY_GATE  → if failed, set status="held_law_check" and stop.
      2. MAGNITUDE_GATE    → clamp vector if needed (mutates entry in-place).
      3. REVERSIBILITY_LOG → snapshot before-state.
      4. If all pass: move to contents (status="committed"), append to contents list.

    Returns a report dict:
        {
            "total_pending": int,
            "promoted":     [entry_id, ...],
            "held_law":     [{"id": ..., "reason": ...}, ...],
            "clamped":      [{"id": ..., "original_mag": ..., "capped_to": ...}, ...],
            "errors":       [{"id": ..., "error": str}, ...],
        }

    NOTE: This function is PURE MATH — zero LLM calls. It runs offline in the
    self-test and during deep sleep without needing LM Studio.
    """
    data = _load_g2(path)
    pending = [e for e in data.get("ring_buffer", []) if e.get("status") == "pending"]
    contents = list(data.get("contents", []))
    core_laws = _load_core_laws()

    report: dict = {
        "total_pending": len(pending),
        "promoted": [],
        "held_law": [],
        "clamped": [],
        "pending_approval": [],  # Segment 5: Tier-2 structural changes awaiting reviewer
        "errors": [],
    }

    for entry in pending:
        try:
            # ── MOON 1: CONSISTENCY_GATE ──────────────────────────────────────
            consistency_ok, reason = g2_moon_consistency(entry, core_laws)
            if not consistency_ok:
                entry["status"] = "held_law_check"
                entry["hold_reason"] = reason
                report["held_law"].append({"id": entry["id"], "reason": reason})
                continue  # do NOT proceed to other moons

            # ── MOON 2: MAGNITUDE_GATE ────────────────────────────────────────
            entry, was_clamped = g2_moon_magnitude(entry)
            if was_clamped:
                report["clamped"].append({
                    "id": entry["id"],
                    "original_mag": entry.get("original_magnitude"),
                    "capped_to": G2_MAGNITUDE_CAP,
                })

            # ── MOON 3: REVERSIBILITY_LOG ─────────────────────────────────────
            g2_moon_reversibility(entry, contents)

            # ── SEGMENT 5 GROWTH-POLICY TIER GATE ────────────────────────────
            # Deterministic tier classification from the ACTUAL shape of the change
            # (not the caller's hint). Tier-2 structural changes do NOT auto-commit:
            # they are held with status="pending_user_approval" so a reviewer can
            # approve/reject via g2_growth_policy.g2_review(). Tier-1 commits as before.
            _tier = _g2_classify_tier(entry)
            entry["growth_policy"] = {"tier": _tier["tier"], "reason": _tier["reason"],
                                      "signals": _tier["signals"], "classified_ts": time.time()}
            if _tier["tier"] == 2:
                entry["status"] = "pending_user_approval"
                report.setdefault("pending_approval", []).append(
                    {"id": entry.get("id"), "reason": _tier["reason"], "signals": _tier["signals"]})
                continue  # stays in ring_buffer, NOT committed — awaiting reviewer

            # ── COMMIT (Tier 1 autonomous): move to contents ──────────────────
            entry["status"] = "committed"
            # Remove from ring_buffer (use .get() — some legacy entries may lack id)
            _eid = entry.get("id")
            if _eid is not None:
                data["ring_buffer"] = [e for e in data.get("ring_buffer", []) if e.get("id") != _eid]
            # Append to contents (append-only — never overwrite)
            data.setdefault("contents", []).append(entry)
            if _eid is not None:
                report["promoted"].append(_eid)

        except Exception as exc:
            report["errors"].append({"id": entry.get("id", "<no-id>"), "error": f"{type(exc).__name__}: {exc}"})
            # Leave the entry in ring_buffer with status unchanged so it can be retried.

    _save_g2(data, path)
    return report


# ─── SELF-TEST (offline — zero LLM calls) ─────────────────────────────────────

def reason_lower(s: str) -> str:
    """Helper for case-insensitive checks in tests."""
    return s.lower() if s else ""


def _self_test() -> None:
    import tempfile, shutil

    print("=" * 60)
    print("g2_ops.py — Phase 7 Segment 3 self-test (G2 Self-Model Moons)")
    print("=" * 60)

    failures = []

    def check(label: str, cond: bool):
        tag = "PASS" if cond else "FAIL"
        print(f"  [{tag}] {label}")
        if not cond:
            failures.append(label)

    # Use a temp copy of the real g2_selfmodel.json so we don't pollute live state.
    tmpdir = tempfile.mkdtemp(prefix="g2_ops_test_")
    test_path = os.path.join(tmpdir, "g2_selfmodel.json")
    try:
        shutil.copy(_G2_PATH, test_path)
    except FileNotFoundError:
        # If the live file doesn't exist (fresh checkout), create a minimal fixture.
        fixture = {
            "id": "g2", "name": "G2 Self-Model", "role": "evolving_self_knowledge",
            "position": [-18.0, 2.0, 8.0], "velocity": [0.657, -0.0, 1.433],
            "mass": 60.0, "ring_buffer": [], "contents": [],
            "moons": [], "sandbox": {}, "_growth_policy": {},
        }
        with open(test_path, "w") as f:
            json.dump(fixture, f)

    try:
        # ── [1] g2_add_candidate creates a pending entry ─────────────────────
        e1 = g2_add_candidate(
            text="Tone has shifted toward more analytical framing in recent sessions.",
            vector_position=[0.05, 0.03, -0.02],  # small delta, within cap
            mass=0.4, tier=1, path=test_path,
        )
        check("[1a] Entry added with status=pending", e1["status"] == "pending")
        check("[1b] before field is empty list initially", e1["before"] == [])

        # ── [2] g2_list_candidates returns the entry ─────────────────────────
        pending = g2_list_candidates(test_path, status="pending")
        check("[2a] One pending candidate after add", len(pending) == 1)
        check("[2b] Candidate has correct id", pending[0]["id"] == e1["id"])

        # ── [3] CONSISTENCY_GATE: small vector passes ────────────────────────
        ok, reason = g2_moon_consistency(e1, core_laws=[])  # no laws → pass (degraded)
        check("[3a] No-laws mode: consistency gate passes", ok is True)

        # With a large vector that would "escape" — should fail if laws loaded.
        e_large = dict(e1)
        e_large["vector_position"] = [0.5, 0.4, -0.3]  # mag ≈ 0.70 > 0.30 threshold
        # Use the real laws file for a realistic test (also verifies path resolution).
        _real_laws = _load_core_laws()
        check("[3x] Real core_laws.json loaded from disk", len(_real_laws) > 0)
        ok_large, reason_large = g2_moon_consistency(e_large, core_laws=_real_laws)
        check("[3b] Large vector with laws present: held for review", ok_large is False)
        check("[3c] Hold reason mentions escape threshold", "escape" in reason_lower(reason_large))

        # ── [4] MAGNITUDE_GATE: small vector passes through unchanged ────────
        e_small = {"id": "t1", "vector_position": [0.05, 0.03, -0.02], "status": "pending"}
        out, clamped = g2_moon_magnitude(e_small)
        check("[4a] Small vector: not clamped", clamped is False)
        check("[4b] Small vector: unchanged", out["vector_position"] == [0.05, 0.03, -0.02])

        # ── [5] MAGNITUDE_GATE: large vector gets clamped to cap ─────────────
        e_big = {"id": "t2", "vector_position": [1.0, 0.8, -0.6], "status": "pending"}
        out_big, clamped_big = g2_moon_magnitude(e_big)
        check("[5a] Large vector: was_clamped=True", clamped_big is True)
        new_mag = _vector_magnitude(out_big["vector_position"])
        check("[5b] Clamped magnitude ≈ G2_MAGNITUDE_CAP (0.15)", abs(new_mag - G2_MAGNITUDE_CAP) < 0.01)
        check("[5c] Original vector preserved in audit field", out_big.get("original_vector_position") == [1.0, 0.8, -0.6])
        check("[5d] Status set to 'clamped'", out_big["status"] == "clamped")

        # ── [6] REVERSIBILITY_LOG: new entry gets empty before-state ─────────
        e_new = {"id": "t3", "text": "new observation"}
        g2_moon_reversibility(e_new, current_contents=[])
        check("[6a] New entry (no target): before=[]", e_new["before"] == [])
        check("[6b] committed_ts is set", "committed_ts" in e_new and e_new["committed_ts"] > 0)

        # ── [7] REVERSIBILITY_LOG: modifying existing entry snapshots it ─────
        existing = [{"id": "orig_1", "text": "original state", "mass": 0.5}]
        e_mod = {"id": "t4", "text": "modified observation", "targets_entry_id": "orig_1"}
        g2_moon_reversibility(e_mod, current_contents=existing)
        check("[7a] Targeted entry: before has 1 snapshot", len(e_mod["before"]) == 1)
        check("[7b] Snapshot preserves original text", e_mod["before"][0]["text"] == "original state")

        # ── [8] g2_sleep_pass_i: end-to-end on temp file ─────────────────────
        # Add a second candidate that will be clamped.
        # NOTE: mag ≈ 0.458 — above the Magnitude Cap (0.15) so it gets CLAMPED,
        # but below the Escape Threshold (0.30*2=0.60... wait, 0.60 > 0.458)
        # Re-check: escape threshold = G2_MAGNITUDE_CAP * 2 = 0.15 * 2 = 0.30
        # 0.458 > 0.30 → this WOULD trip the Consistency Gate and be HELD,
        # not clamped+committed.
        #
        # To test the "clamped but still committed" path, we need a vector that is:
        #   above Magnitude Cap (0.15)  → gets clamped
        #   below Escape Threshold (0.30) → passes Consistency Gate
        # So use something like [0.2, 0.1, -0.05] → mag ≈ 0.229 ✓ both conditions.
        g2_add_candidate(
            text="Moderate tone shift detected in last 5 sessions (clamped case).",
            vector_position=[0.20, 0.10, -0.05],  # mag ≈ 0.229: clamps to cap, passes law gate
            mass=0.6, tier=1, path=test_path,
        )
        report = g2_sleep_pass_i(test_path)

        check("[8a] Report total_pending == 2", report["total_pending"] == 2)
        check("[8b] At least one promoted (the small-vector entry)", len(report["promoted"]) >= 1)
        check("[8c] The large-vector entry was clamped", any(c["id"] != e1["id"] for c in report["clamped"]))

        # Verify disk state after pass.
        data_after = _load_g2(test_path)
        promoted_ids = {e["id"] for e in data_after.get("contents", [])}
        check("[8d] Promoted entries are now in contents", any(p in promoted_ids for p in report["promoted"]))
        # The clamped entry should also be committed (clamping doesn't reject, just limits).
        all_committed = [e for e in data_after.get("contents", []) if e.get("status") == "committed"]
        check("[8e] Clamped entry was still committed (not rejected)", len(all_committed) >= 2)

        # ── [9] Idempotency: second pass processes 0 pending ────────────────
        report2 = g2_sleep_pass_i(test_path)
        check("[9a] Second pass: total_pending == 0", report2["total_pending"] == 0)
        check("[9b] Second pass: nothing promoted", len(report2["promoted"]) == 0)

        # ── [10] _clamp_vector_to_cap edge cases ─────────────────────────────
        v_zero, clz = _clamp_vector_to_cap([0.0, 0.0, 0.0], G2_MAGNITUDE_CAP)
        check("[10a] Zero vector: not clamped", clz is False)

        v_exact, cle = _clamp_vector_to_cap([G2_MAGNITUDE_CAP, 0.0, 0.0], G2_MAGNITUDE_CAP)
        check("[10b] Vector exactly at cap: not clamped", cle is False)

        v_over, clo = _clamp_vector_to_cap([1.0, 1.0, 1.0], G2_MAGNITUDE_CAP)
        over_mag_after = _vector_magnitude(v_over)
        check("[10c] Vector well above cap: clamped to ~cap", abs(over_mag_after - G2_MAGNITUDE_CAP) < 0.01)

        # ── [11] SEGMENT 5 integration: structural change held for approval,    ─
        # then committed by reviewer. Uses kind="anchor_migration" with a small     ─
        # vector (below escape threshold so the Consistency Gate passes) but tagged  ─
        # as an anchor migration — Tier 2 must still hold it via the growth policy. ─
        from giants.g2_growth_policy import g2_review
        e_struct = g2_add_candidate(
            text="Re-anchor Sage's identity framing toward more authoritative tone (no numeric nudge).",
            kind="anchor_migration",
            vector_position=None,  # pure semantic/identity re-anchoring: no vector to cap or escape-check
            mass=0.7, tier=1, path=test_path,   # NOTE: caller says tier=1, but classifier must override
        )
        rep = g2_sleep_pass_i(test_path)
        pending_appr = {p["id"] for p in rep.get("pending_approval", [])}
        promoted_now = set(rep.get("promoted", []))
        check("[11a] Structural change flagged pending_approval", e_struct["id"] in pending_appr)
        check("[11b] Structural change NOT auto-promoted (tier gate overrode tier=1 hint)",
              e_struct["id"] not in promoted_now)
        st = _load_g2(test_path)
        held_entry = next((x for x in st["ring_buffer"] if x.get("id") == e_struct["id"]), None)
        check("[11c] Held entry status=pending_user_approval on disk",
              held_entry is not None and held_entry.get("status") == "pending_user_approval")
        check("[11d] growth_policy block records Tier 2 + signal",
              bool(held_entry) and held_entry.get("growth_policy", {}).get("tier") == 2)
        # Reviewer approves → commits.
        res = g2_review(e_struct["id"], "approve", reviewer="admin(dev)", path=test_path)
        st2 = _load_g2(test_path)
        committed_ids = {x.get("id") for x in st2.get("contents", [])}
        check("[11e] After approve: structural entry is in contents", e_struct["id"] in committed_ids)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if failures:
        print(f"g2_ops.py Segment 3 self-test: {len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  ✗ {f}")
        import sys as _sys
        _sys.exit(1)
    else:
        print("g2_ops.py Segment 3 self-test: ALL PASS (G2 Self-Model Moons)")


if __name__ == "__main__":
    _self_test()
