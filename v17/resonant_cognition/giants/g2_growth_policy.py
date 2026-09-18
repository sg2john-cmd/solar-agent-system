"""
Resonant Cognition v17 — Phase 7, Segment 5: G2 Growth Policy + Tier System
============================================================================

Answers ONE question for any proposed self-model change: is this a small DRIFT the
system may commit on its own (Tier 1), or a STRUCTURAL change to the design itself
that must wait for an explicit approval decision (Tier 2)?

The tier definitions are NOT invented here — they already live in g2_selfmodel.json
under "_growth_policy":
    Tier 1 (autonomous): normal drift (tension averages shift, planet weights adjust
                         within bounds). Commits automatically after passing the moons.
    Tier 2 (notify/approval): structural changes — planet identity text rewritten,
                         semantic anchor direction migrated >0.3 units, new archetype
                         added. Flagged status="pending_user_approval"; NOT committed
                         until a reviewer says yes/no.

This module is PURE / DETERMINISTIC — zero LLM calls. It reads the *actual shape of
the proposed change* (its fields and vector magnitude) and classifies it. The moons in
g2_ops.py judge legality + magnitude; the sandbox judges behavioral effect; THIS module
judges "how big a deal is this, does it need a human?" — the growth-policy layer.

Why deterministic: tiering must be stable and auditable. A random LLM call deciding
"does my own change need approval?" would be exactly the kind of self-justification we
do NOT want in the safety rail. The rules are explicit, logged, and reversible.

APPROVER IS ROLE-BASED (not hardcoded to one person): during dev John is admin; after
release a different user reviews. So Tier 2 = "queue for whoever holds approval," not
"wait for John." g2_review() records WHO decided via the caller-supplied reviewer tag.

RUN: python -X utf8 giants/g2_growth_policy.py   (self-test, no LM Studio needed)
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_GIANTS_DIR = _HERE
_PKG_ROOT = os.path.dirname(_HERE)
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)
_G2_PATH = os.path.join(_GIANTS_DIR, "g2_selfmodel.json")

# ─── TUNABLES (single source of truth: constants.py) ──────────────────────────
try:
    from constants import G2_TIER2_ANCHOR_MIGRATION as _CONST_T2_MIGRATE
except ImportError:  # pragma: no cover — isolated-context fallback matches JSON policy
    _CONST_T2_MIGRATE = 0.30

# A semantic-anchor / self-vector migration beyond this many normalized units is a
# STRUCTURAL (Tier 2) change. Matches g2_selfmodel.json "_growth_policy.tier_2_notify"
# ("semantic anchor direction migrated >0.3 units"). GUESS — tune after live runs.
TIER2_ANCHOR_MIGRATION = _CONST_T2_MIGRATE


def _vector_magnitude(v) -> float:
    """Euclidean norm; 0.0 for anything that isn't a numeric sequence."""
    if not isinstance(v, (list, tuple)) or len(v) == 0:
        return 0.0
    try:
        return math.sqrt(sum(float(x) * float(x) for x in v))
    except (TypeError, ValueError):
        return 0.0


# ─── TIER CLASSIFIER ─────────────────────────────────────────────────────────

def g2_classify_tier(entry: dict) -> dict:
    """Classify a proposed G2 self-change as Tier 1 or Tier 2.

    Deterministic rules, in priority order (first match wins):
      TIER 2 (structural — needs approval):
        - "kind" == "anchor_migration" with vector magnitude > TIER2_ANCHOR_MIGRATION
          (semantic-anchor direction migrated beyond the structural bound)
        - "rewrites_identity_text" is True   (planet/persona identity text rewritten)
        - "adds_archetype" is True            (a new archetype/planet added)
      TIER 1 (autonomous — commits after moons pass):
        - anything else: normal drift within bounds.

    A self-review VERDICT record (role == "SELF_REVIEW_VERDICT") carries no vector and
    does not rewrite identity, so it classifies as Tier 1 by default; but if the debate
    reports a structural finding (debate.structural_findings > 0) or all planets REDIRECT
    with an explicit escalation flag, callers may still promote it to Tier 2. We keep
    this module's job narrow: classify from fields present on the entry.

    Returns {"tier": int, "reason": str, "signals": [str,...]}.
      signals lists every structural trigger that fired (empty for clean Tier 1).
    """
    if not isinstance(entry, dict):
        return {"tier": 2, "reason": "Unparseable entry — held conservatively.",
                "signals": ["unparseable"]}

    vec = entry.get("vector_position") or entry.get("delta_vector")
    mag = _vector_magnitude(vec)

    signals: list[str] = []

    # Rule 1: anchor / identity migration. A re-anchoring of a semantic anchor is a
    # STRUCTURAL (design) change in itself — it holds even with no numeric nudge.
    # If a vector IS present and exceeds the bound, that magnitude is noted too.
    # `kind` may be absent OR explicitly None (callers pass {"kind": None} to mean
    # "no structural kind"). Normalise once so every rule below can use it safely.
    kind = str(entry.get("kind") or "").lower()
    if kind == "anchor_migration" or entry.get("is_anchor_migration"):
        if mag > TIER2_ANCHOR_MIGRATION:
            signals.append(f"anchor_migration magnitude {mag:.3f} > {TIER2_ANCHOR_MIGRATION}")
        else:
            signals.append("semantic anchor re-anchored (structural)")

    # Rule 2: identity text rewritten.
    if bool(entry.get("rewrites_identity_text")):
        signals.append("identity_text_rewrite")

    # Rule 3: new archetype / planet added.
    if bool(entry.get("adds_archetype")) or kind in ("add_archetype", "new_planet"):
        signals.append("archetype_added")

    tier = 2 if signals else 1
    reason = (
        "Structural change — requires reviewer approval." + " Triggers: " + "; ".join(signals)
        if signals else
        f"Normal drift within bounds (magnitude {mag:.3f}) — autonomous."
    )
    return {"tier": tier, "reason": reason, "signals": signals}


def g2_is_structural(entry: dict) -> bool:
    """Convenience predicate: True if the entry is a Tier-2 structural change."""
    return g2_classify_tier(entry)["tier"] == 2


# ─── REVIEWER ACTIONS (role-based, not hardcoded to one person) ──────────────

def g2_review(entry_id: str | None, decision: str, reviewer: str = "unspecified",
              path: str | None = None) -> dict:
    """Record a reviewer's yes/no on a Tier-2 pending change.

    decision  : "approve" → commit the entry (move ring_buffer → contents).
                "reject"  → mark status="rejected_tier2"; leave it in buffer for audit,
                            do NOT commit.
    reviewer  : tag of who decided (role-based; dev=admin/John, post-release=user).

    Returns {"status": str, "entry_id": ...} or an error dict if the entry / decision is bad.
    """
    data = _load_g2(path)
    target = None
    for e in data.get("ring_buffer", []):
        if e.get("id") == entry_id:
            target = e
            break
    if target is None:
        return {"status": "error", "reason": f"No ring_buffer entry with id={entry_id!r}"}

    decision = str(decision).lower().strip()
    if decision not in ("approve", "reject"):
        return {"status": "error", "reason": f"decision must be 'approve' or 'reject', got {decision!r}"}

    target["reviewer"] = reviewer
    target["review_ts"] = time.time()
    target["review_decision"] = decision

    if decision == "approve":
        # Commit: snapshot before-state (reversibility), move to contents.
        current_contents = list(data.get("contents", []))
        target.setdefault("before", [dict(c) for c in current_contents] if not target.get("before") else target["before"])
        target["committed_ts"] = time.time()
        target["status"] = "committed"
        data["ring_buffer"] = [e for e in data["ring_buffer"] if e.get("id") != entry_id]
        data.setdefault("contents", []).append(target)
    else:
        # Reject: do NOT commit. Keep in buffer, flagged for audit (never silently dropped).
        target["status"] = "rejected_tier2"

    _save_g2(data, path)
    return {"status": decision, "entry_id": entry_id}


# ─── FILE I/O (local copy; mirrors g2_ops.py so this module stays importable standalone) ──
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


# ─── SELF-TEST (offline — zero LLM calls) ─────────────────────────────────────

def _self_test() -> None:
    import tempfile, shutil

    print("=" * 60)
    print("g2_growth_policy.py — Phase 7 Segment 5 self-test (Growth Policy / Tiers)")
    print("=" * 60)
    failures = []

    def check(label: str, cond: bool):
        tag = "PASS" if cond else "FAIL"
        print(f"  [{tag}] {label}")
        if not cond:
            failures.append(label)

    tmpdir = tempfile.mkdtemp(prefix="g2_gp_test_")
    test_path = os.path.join(tmpdir, "g2_selfmodel.json")
    try:
        shutil.copy(_G2_PATH, test_path)
    except FileNotFoundError:
        fixture = {"id": "g2", "ring_buffer": [], "contents": [], "_growth_policy": {}}
        with open(test_path, "w") as f:
            json.dump(fixture, f)

    try:
        # ── [1] Clean drift → Tier 1 ─────────────────────────────────────────
        c = g2_classify_tier({"text": "tone slightly more analytical",
                              "vector_position": [0.05, 0.03, -0.02], "tier": 1})
        check("[1a] Small drift classifies Tier 1", c["tier"] == 1)
        check("[1b] No structural signals", c["signals"] == [])

        # ── [2] Anchor migration beyond bound → Tier 2 ───────────────────────
        big = g2_classify_tier({"kind": "anchor_migration", "vector_position": [0.5, 0.4, -0.3]})
        check("[2a] Large anchor migration classifies Tier 2", big["tier"] == 2)
        check("[2b] Signal names the magnitude trigger", any("anchor_migration" in s for s in big["signals"]))

        # ── [3] Anchor re-anchoring is structural EVEN with a small vector ───
        within = g2_classify_tier({"kind": "anchor_migration",
                                   "vector_position": [0.1, 0.05, -0.02]})  # mag ≈ 0.115 < 0.3
        check("[3a] Anchor re-anchoring is Tier 2 even with small vector", within["tier"] == 2)
        check("[3b] Small-magnitude anchor migration notes structural signal",
              any("re-anchored" in s for s in within["signals"]))

        # ── [4] Identity text rewrite → Tier 2 (no vector needed) ────────────
        ident = g2_classify_tier({"text": "rewrite Sage persona identity", "rewrites_identity_text": True})
        check("[4a] Identity rewrite classifies Tier 2", ident["tier"] == 2)
        check("[4b] Signal present", any("identity" in s for s in ident["signals"]))

        # ── [5] Archetype added → Tier 2 ─────────────────────────────────────
        arch = g2_classify_tier({"kind": "add_archetype", "adds_archetype": True})
        check("[5a] New archetype classifies Tier 2", arch["tier"] == 2)

        # ── [6] Self-review verdict (no vector, no identity) → Tier 1 default ─
        vr = g2_classify_tier({"role": "SELF_REVIEW_VERDICT", "report_text": "...",
                               "debate": {"approve": 4, "redirect": 3, "all_emitted": True}})
        check("[6a] Plain self-review verdict classifies Tier 1", vr["tier"] == 1)

        # ── [7] g2_is_structural predicate ───────────────────────────────────
        check("[7a] is_structural(big anchor)", g2_is_structural({"kind": "anchor_migration", "vector_position": [0.9, 0, 0]}) is True)
        check("[7b] is_structural(clean drift)", g2_is_structural({"text": "x"}) is False)

        # ── [8] Non-anchor vector exactly at TIER2_ANCHOR_MIGRATION → Tier 1    ─
        # (the magnitude-only rule uses strict >; a plain drift with no anchor/identity
        # flag is autonomous regardless of size, so the bound is not a hard wall for
        # non-structural entries — only re-anchoring / identity / archetype are.)
        exact = g2_classify_tier({"vector_position": [TIER2_ANCHOR_MIGRATION, 0.0, 0.0]})
        check("[8a] Non-anchor drift at bound stays Tier 1", exact["tier"] == 1)

        # ── [9] g2_review: approve commits a pending Tier-2 entry ────────────
        from giants.g2_ops import g2_add_candidate
        e = g2_add_candidate(text="structural test change", kind="anchor_migration",
                             vector_position=[0.5, 0.4, -0.3], tier=2, path=test_path)
        check("[9a] Pending entry created in buffer", any(x.get("id") == e["id"] for x in _load_g2(test_path)["ring_buffer"]))
        res = g2_review(e["id"], "approve", reviewer="admin(dev)", path=test_path)
        data_after = _load_g2(test_path)
        committed_ids = {x.get("id") for x in data_after.get("contents", [])}
        buffer_ids = {x.get("id") for x in data_after["ring_buffer"]}
        check("[9b] Approve result status=approve", res["status"] == "approve")
        check("[9c] Approved entry moved to contents", e["id"] in committed_ids)
        check("[9d] Approved entry removed from ring_buffer", e["id"] not in buffer_ids)
        committed_entry = next(x for x in data_after["contents"] if x.get("id") == e["id"])
        check("[9e] Reviewer tag recorded (role-based)", committed_entry.get("reviewer") == "admin(dev)")
        check("[9f] Status=committed", committed_entry.get("status") == "committed")

        # ── [10] g2_review: reject keeps entry in buffer, NOT committed ──────
        e2 = g2_add_candidate(text="structural test change 2", kind="anchor_migration",
                              vector_position=[0.5, 0.4, -0.3], tier=2, path=test_path)
        res2 = g2_review(e2["id"], "reject", reviewer="admin(dev)", path=test_path)
        data_after2 = _load_g2(test_path)
        rejected_entry = next((x for x in data_after2["ring_buffer"] if x.get("id") == e2["id"]), None)
        committed_ids2 = {x.get("id") for x in data_after2.get("contents", [])}
        check("[10a] Reject result status=reject", res2["status"] == "reject")
        check("[10b] Rejected entry stays in ring_buffer (audit)", rejected_entry is not None)
        check("[10c] Rejected entry NOT in contents", e2["id"] not in committed_ids2)
        check("[10d] Rejected status flag set", rejected_entry and rejected_entry.get("status") == "rejected_tier2")

        # ── [11] g2_review error paths ───────────────────────────────────────
        bad_id = g2_review("does_not_exist", "approve", path=test_path)
        check("[11a] Unknown id → error status", bad_id.get("status") == "error")
        e3 = g2_add_candidate(text="bad decision test", tier=2, path=test_path)
        bad_dec = g2_review(e3["id"], "maybe", path=test_path)
        check("[11b] Invalid decision → error status", bad_dec.get("status") == "error")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    if failures:
        print(f"g2_growth_policy.py Segment 5 self-test: {len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print("g2_growth_policy.py Segment 5 self-test: ALL PASS (Growth Policy / Tiers)")


if __name__ == "__main__":
    _self_test()
