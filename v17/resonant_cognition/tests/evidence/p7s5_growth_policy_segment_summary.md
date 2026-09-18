# Phase 7 — Segment 5: G2 Growth Policy + Tier System (evidence summary)

**Date:** 2026-09-17 (run timestamp `20260917_183150`)
**Status:** ✅ DONE — all offline self-tests green.

## What this segment adds
Tier-based growth policy for G2's evolving self-model:
- **Tier 1 (normal drift):** autonomous after moons + sandbox pass; auto-committed to `contents`.
- **Tier 2 (structural change):** identity rewrite, anchor migration >0.3 units, or new archetype → held as `pending_user_approval` until a role-based reviewer approves/rejects.
- **Anti-silence precedence:** a silenced debate (`all_emitted=False`) is always `held_anti_silence`, even if it carries a structural finding — nothing is treated as "decided" when voices are missing.

## Key integration point
`ring.py::log_self_review_verdict()` now routes each self-review verdict through the tier gate: a debate that surfaces a **structural finding** (`debate.structural_findings > 0`) becomes `pending_user_approval` (Tier 2) instead of auto-committing. Plain clean debates stay Tier 1 and commit. This is deterministic / zero-LLM; it reads only fields already on the record and pulls tier definitions from `g2_selfmodel.json::_growth_policy` via `g2_classify_tier()` (single source of truth).

## Bug found & fixed during integration
The first run crashed at ring.py check [29] with:
```
AttributeError: 'NoneType' object has no attribute 'lower'   # g2_growth_policy.py line 118, Rule 3
```
Root cause: `ring.py` passes `"kind": None` (meaning "no structural kind") for non-structural verdicts. `g2_classify_tier()` normalised `kind` with a `.get("kind", "")` default, but an **explicit** `None` bypasses that default and crashed Rule 3's raw `.lower()`. Fix: normalise once at the top of the classifier (`str(entry.get("kind") or "").lower()`) so every rule is safe against both missing and explicit-`None` kinds. (Note: this was a real runtime bug, not the "stale guard references" described in the prior handoff — ring.py's `if not okXX:` guards were already consistent.)

## Test results (all offline / zero LLM)
| Module | Checks | Result | Raw log |
|--------|--------|--------|---------|
| `ring.py` (Segs 1–6, incl. new [31a]/[31b]) | all pass | ✅ ALL PASS | `p7s5_ring_selftest_20260917_183150.log` |
| `giants/g2_ops.py` (regression, G2 moons + tier gate [11a]–[11e]) | all pass | ✅ ALL PASS | `p7s5_g2_ops_regression_20260917_183150.log` |
| `giants/g2_growth_policy.py` (tier classifier + reviewer actions) | 24 checks | ✅ ALL PASS | `p7s5_growth_policy_selftest_20260917_183150.log` |

New ring.py checks added this segment:
- **[31a]** structural finding in debate → Tier-2 hold (`pending_user_approval`).
- **[31b]** silenced debate with a structural finding → `held_anti_silence` (silence wins over tier).

## Notes for production
G2 moons are **mandatory ON** for final release (locked decision, same as G1). The reviewer role is not hardcoded to one person — it's the current system admin now and any designated reviewer post-release.
