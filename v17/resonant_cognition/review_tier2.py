"""
Resonant Cognition v17 — M4 fix: Tier-2 structural-change review tool.

WHY THIS EXISTS (M4)
====================
Structural self-changes (planet identity rewrites, semantic-anchor migrations >0.3
units, new archetypes) are held in G2's ring_buffer with status="pending_user_approval"
by the growth-policy tier gate (g2_growth_policy.g2_classify_tier). The resolver
function g2_review() existed but had NO production caller — so pending changes could
accumulate indefinitely with no way to approve or reject them. This script is that
missing, deterministic reviewer entry point. It makes ZERO LLM calls.

USAGE
=====
  # List every Tier-2 change currently waiting for a decision:
  python -X utf8 review_tier2.py --list

  # Approve one (commits it: snapshot before-state → move ring_buffer → contents):
  python -X utf8 review_tier2.py --approve <entry_id> [--reviewer NAME]

  # Reject one (NOT committed; kept in buffer with status="rejected_tier2" for audit):
  python -X utf8 review_tier2.py --reject <entry_id> [--reviewer NAME]

Notes:
  - Deterministic / offline. No LM Studio required.
  - Default reviewer tag is "admin". In dev that's John; post-release the user/admin
    who runs it passes their own name via --reviewer (role-based, not hardcoded).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _load_g2(path: str | None = None) -> dict:
    from giants.g2_growth_policy import _G2_PATH as _DEFAULT
    p = path or _DEFAULT
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def pending_entries(path: str | None = None) -> list[dict]:
    """Return ring_buffer entries currently awaiting a Tier-2 decision."""
    from giants.g2_ops import g2_list_candidates
    return g2_list_candidates(path=path, status="pending_user_approval") or []


def _fmt(e: dict, idx: int) -> str:
    kind = e.get("kind", "?")
    text = (e.get("text") or "").strip().replace("\n", " ")
    if len(text) > 90:
        text = text[:87] + "..."
    created = e.get("created_ts")
    return f"  [{idx}] {e.get('id')}\n      kind={kind}   mass={e.get('mass', '?')}   ts={created}\n      text: {text}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="M4 fix — resolve Tier-2 structural self-changes (deterministic, no LLM)."
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="List pending Tier-2 changes.")
    mode.add_argument("--approve", metavar="ENTRY_ID", help="Approve + commit a pending change.")
    mode.add_argument("--reject", metavar="ENTRY_ID", help="Reject a pending change (kept for audit).")
    ap.add_argument("--reviewer", default="admin", help="Reviewer tag recorded on the decision (default: admin).")
    ap.add_argument("--path", default=None, help="Override g2_selfmodel.json path (testing only).")
    args = ap.parse_args()

    if args.list:
        items = pending_entries(args.path)
        if not items:
            print("No Tier-2 changes are currently awaiting review. ✓")
            return 0
        print(f"{len(items)} Tier-2 structural change(s) awaiting your decision:\n")
        for i, e in enumerate(items, 1):
            print(_fmt(e, i))
        print("\nApprove: python -X utf8 review_tier2.py --approve <entry_id> [--reviewer NAME]")
        print("Reject : python -X utf8 review_tier2.py --reject  <entry_id> [--reviewer NAME]")
        return 0

    decision = "approve" if args.approve else "reject"
    entry_id = args.approve or args.reject

    from giants.g2_growth_policy import g2_review
    result = g2_review(entry_id, decision, reviewer=args.reviewer, path=args.path)

    status = result.get("status")
    if status == "error":
        # Helpful hint: maybe the id is wrong / already resolved.
        print(f"✗ {result.get('reason')}")
        items = pending_entries(args.path)
        if not items:
            print("  (No Tier-2 changes are currently pending — run --list to confirm.)")
        else:
            print("\nStill-pending entries:")
            for i, e in enumerate(items, 1):
                print(_fmt(e, i))
        return 1

    verb = "APPROVED + committed" if decision == "approve" else "REJECTED (kept for audit)"
    print(f"[OK] Tier-2 change {entry_id} → {verb}.")
    print(f"     reviewer={args.reviewer}")
    remaining = len(pending_entries(args.path))
    print(f"     Remaining pending: {remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
