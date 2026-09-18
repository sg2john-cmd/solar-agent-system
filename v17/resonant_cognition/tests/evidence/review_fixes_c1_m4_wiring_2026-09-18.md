# Review Fixes — Segment 1: C1 (G1 moons wiring) + M4 (Tier-2 approval resolver)

**Date:** 2026-09-18
**Source review:** Independent blind code review of v17 (attached as text file). Verdict: "not production-ready... no fundamental design flaws." Priority #1 = C1 + safety-filter wiring; M4 is its sibling.
**Scope this segment:** make the two *unwired* self-model safety features actually reachable in production, gated by existing toggles / a new deterministic CLI. **No LLM calls were made — everything below ran offline.**

---

## C1 — G1 filter moons now wired into deep-sleep (was: silently absent)

**Finding (verified against code):** `g1_filter_moons.apply_filter_moons_to_sleep_pass()` had NO production caller. Only test scripts (`run_p7s6_acceptance.py`, `run_p7s6b_battery.py`) invoked it as a manual pre-pass. So flipping the mandatory-at-release flag `G1_FILTER_MOONS_ENABLED` ON would change nothing: candidates promoted/ejected unfiltered. The project's own evidence note (`p7s6_acceptance_moonsOFF_summary.md:57-59`) stated this verbatim.

**Fix (`giants/g1_ops.py::g1_sleep_pass_i()`):**
- Added a guarded `import constants` (package-root path insert + direct-script fallback, mirroring g2_ops.py).
- At the top of the pass, `_moons_on = bool(getattr(constants, "G1_FILTER_MOONS_ENABLED", False))`; when ON, each pending candidate runs `apply_filter_moons_to_sleep_pass(entry, g1)` **before** deterministic scoring.
- Moon verdicts take precedence:
  - `rejected_clarity` → EJECT with `reject_reason="moon_rejected_clarity"`.
  - `flagged_contradiction` → HOLD (`status="flagged_contradiction"`), neither promoted nor ejected; surfaced in report as `held_for_review`. Mirrors Tier-2 hold semantics (human reconciles).
  - `peripheral` → PROMOTE at reduced mass: new tunable `G1_PERIPHERAL_MASS_FACTOR = 0.5` (**flagged GUESS** — tune after live runs); original mass preserved in `original_mass`, entry tagged `peripheral=True`.
  - `pass`/`None` → normal deterministic scoring path (unchanged).
- Return dict now includes `"held_for_review": [...]`; promoted/ejected composite reads use `.get("score_breakdown", {})` so moon-short-circuited entries don't KeyError.

**Why this is the right shape:** it matches the exact contract documented in `g1_filter_moons.py:283-296` ("This is the integration point that g1_ops.g1_sleep_pass_i() will call"). Dev mode (toggle OFF) leaves `_apply_moons=None`, so zero extra LLM calls — byte-identical to Segment 1.

**Verification (offline):**
- `python -X utf8 giants/g1_ops.py` → **ALL PASS** (17 checks). Confirms dev-mode path is unchanged and no regression in scoring/promotion/duplicate/staleness logic.

---

## M4 — Tier-2 structural changes now resolvable (was: accumulate forever)

**Finding (verified):** Structural self-changes are held at `status="pending_user_approval"` (`ring.py:791` self-review path, and g2 sleep-pass), but the only callers of the resolver `g2_review()` were self-tests. Nothing in production could approve/reject a held change → they pile up indefinitely. Same class as C1 (a named safety feature with no live path).

**Fix:** new standalone tool **`review_tier2.py`** at repo root — deterministic, zero LLM:
- `--list` → every ring_buffer entry with `status="pending_user_approval"` (id, kind, mass, ts, text preview) + usage hints.
- `--approve <ENTRY_ID> [--reviewer NAME]` → calls `g2_review(...,"approve")`: snapshots before-state (reversibility), moves ring_buffer→contents, status=`committed`.
- `--reject  <ENTRY_ID> [--reviewer NAME]` → calls `g2_review(...,"reject")`: NOT committed; stays in buffer as `status="rejected_tier2"` for audit.
- Default reviewer tag `admin` (role-based: dev=John, post-release the user who runs it). `--path` override for testing only.
- Bad/unknown id → clear error + re-lists still-pending entries so a typo doesn't dead-end.

**Verification (offline round-trip on temp copies of g2_selfmodel.json):**
1. Injected two structural candidates, set to production state `pending_user_approval`.
2. `--list` → showed exactly 2 with correct ids/kinds/text. ✓
3. `--approve <a> --reviewer john-test` → a committed (`in contents: True`, moved out of buffer). ✓
4. `--reject <b>` → b kept in buffer, `status=rejected_tier2`. ✓
5. Post-decision `--list` → "No Tier-2 changes currently awaiting review." ✓

Disk state after run confirmed by direct JSON read (not just stdout): a present in `contents`, b status=`rejected_tier2`.

---

## Release implications
- **C1:** with `G1_FILTER_MOONS_ENABLED=True` at release, G1's 3-moon LLM filter now genuinely runs on every deep-sleep candidate. This is the safety rail that was silently off. (Adds ~3 short LLM calls per pending candidate — expected cost of a mandatory-on feature; dev stays free.)
- **M4:** Tier-2 holds are no longer terminal dead-ends. The reviewer workflow is now: `review_tier2.py --list` → decide → `--approve/--reject`. No change to how entries get *held* (that logic was already correct and tested).

## Not touched this segment
H1–H5, M1–M3, M5, L1–L5 remain open for subsequent segments. Constants toggles left at dev defaults (`G1_FILTER_MOONS_ENABLED=False`, etc.) — flipping to release values is a deliberate separate step so dev testing stays cheap/offline.
