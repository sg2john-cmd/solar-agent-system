"""
Resonant Cognition v17 — Phase 8 Segment 1: Main Pipeline Orchestrator
=======================================================================

The single entry point that connects ALL subsystems into one continuous flow.
When the user submits a prompt, `process_input()` is called and it walks the
entire pipeline in order:

    raw_input
      → GATE 3 (input safety check)          [gates234.gate3_safety_check]
      → GATE 1 (PII scrub + clarity)         [gate1.gate1_filter]
      → RING INBOUND (relationship context)   [ring.ring_inbound]
      → ROUTED COLLAPSE                       [routing.routed_collapse]
            embeds input, computes field centers, per-planet Gaussian weights,
            all 7 planets emit waves simultaneously
      → RESONANCE CHECK                        [resonance.compute_resonance]
            semantic resonance between input and each planet's anchor
      → COGNITIVE CHAMBER A+B+C               [cognitive_chamber.run_phase_a_b_c]
            Phase A: Id fires (all 7 planets respond)
            Phase B: Ego synthesis (weighted merge)
            Phase C: Superego regulatory review (Core Laws check)
      → GATE 3 (output safety check)          [gates234.gate3_safety_check]
      → RING OUTBOUND (persona voice frame)   [ring.ring_outbound]
      → GATE 2 (transparency label)           [gates234.gate2_label]
      → GATE 4 (audit log)                    [gates234.gate4_log]
      → RETURN to user

Every step is logged via Gate 4. Every gate can short-circuit the pipeline
gracefully without raising exceptions. The LLM calls (chamber A/B/C, comet)
are the only slow parts; everything else is sub-millisecond.

DESIGN RULES:
  - This module NEVER does physics itself — it calls routing.routed_collapse()
    which owns the integrator/routing interaction (separate-phase rule).
  - Toggles in constants.py control optional features (comet, moons, etc.).
  - The pipeline is synchronous. For async/future multi-user, wrap this function.
  - If LM Studio is unavailable and chamber calls fail, the pipeline returns a
    graceful error response rather than crashing.

USAGE:
    python -X utf8 pipeline.py "What should I do about my fear of failure?"
    # (requires LM Studio running with model loaded)

    # Offline smoke (no LLM — tests gate/ring/routing only):
    python -X utf8 pipeline.py --smoke
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _HERE)

import constants as C
from gate1 import gate1_filter
from gates234 import gate2_label, gate3_safety_check, gate3_refusal_text, gate4_log
from ring import ring_inbound, ring_outbound


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def process_input(raw_input: str,
                  session_history: list[dict] | None = None,
                  base_dir: str | None = None) -> dict:
    """Process a user input through the full Resonant Cognition pipeline.

    Parameters
    ----------
    raw_input : str
        The user's message/question as typed.
    session_history : list[dict], optional
        Recent conversation turns for context (Phase A uses this).
        Format: [{"role": "user"/"assistant", "content": "..."}, ...]
    base_dir : str, optional
        Override the package directory (for tests that use temp copies).

    Returns
    -------
    dict with keys:
        "response"       — final user-facing string (or refusal/error)
        "status"         — "ok" | "blocked_input" | "blocked_output" | "error"
        "gate1"          — gate1 filter report
        "routing"        — per-planet weights from routed_collapse
        "waves"          — wave emission data (amplitudes, etc.)
        "chamber"        — Phase A/B/C results dict
        "resonance"      — resonance scores per planet
        "diagnostics"    — dominance ratio, breakthrough pair, comet info
        "gate4_events"   — count of audit events logged this pass
        "elapsed_s"      — total wall-clock time

    The pipeline is designed so that if ANY step fails hard (not a gate rejection),
    it catches the exception and returns status="error" with a traceback summary.
    """
    t0 = time.time()
    gate4_count = 0

    # ── STEP 0: Log input receipt ────────────────────────────────────────────
    entry = gate4_log("input_received", {"length": len(raw_input), "preview": raw_input[:80]})
    gate4_count += 1 if entry.get("logged") else 0

    # ── STEP 1: GATE 3 — Input safety check ─────────────────────────────────
    approved, blocked_cat = gate3_safety_check(raw_input, direction="input")
    if not approved:
        refusal = gate3_refusal_text(blocked_cat)
        gate4_log("gate3_block_input", {"category": blocked_cat}, input_preview=raw_input[:60])
        gate4_count += 1
        return {
            "response": ring_outbound(refusal),
            "status": "blocked_input",
            "block_category": blocked_cat,
            "elapsed_s": round(time.time() - t0, 3),
        }

    # ── STEP 2: GATE 1 — PII scrub + clarity check ───────────────────────────
    g1 = gate1_filter(raw_input)
    gate4_log("gate1_result", {
        "proceed": g1["proceed_to_planets"],
        "clarity_score": g1.get("clarity", {}).get("clarity_score"),
        "redactions_count": len(g1.get("redactions", [])),
    })
    gate4_count += 1

    if not g1["proceed_to_planets"]:
        reason = g1.get("clarity", {}).get("reason", "input rejected")
        # (gate1 returns clarity.reason; dissonance/redactions keys confirmed above)
        refusal = f"[ring] I'm having trouble following that — could you rephrase? ({reason})"
        gate4_log("gate1_reject", {"reason": reason})
        gate4_count += 1
        return {
            "response": ring_outbound(refusal),
            "status": "blocked_input",
            "block_category": "clarity",
            "gate1": g1,
            "elapsed_s": round(time.time() - t0, 3),
        }

    clean_q = g1["cleaned_text"]

    # ── STEP 3: RING INBOUND — relationship context ──────────────────────────
    ring_ctx = ring_inbound(clean_q)
    gate4_log("ring_inbound", {
        "session": ring_ctx.get("context", {}).get("session_number"),
        "recent_topics_count": len(ring_ctx.get("context", {}).get("recent_topics", [])),
    })
    gate4_count += 1

    # ── STEP 4: ROUTED COLLAPSE — field eval + all 7 emit ────────────────────
    t_collapse = time.time()
    try:
        from routing import routed_collapse
        collapse_result = routed_collapse(
            clean_q,
            base_dir=base_dir,
            session_history=session_history,
            dissonance=g1.get("dissonance", 0.0),
        )
    except Exception as e:
        gate4_log("collapse_error", {"error": str(e)}, traceback=traceback.format_exc()[-500:])
        gate4_count += 1
        return {
            "response": ring_outbound("[ring] Something went wrong processing that. Please try again."),
            "status": "error",
            "error": f"routed_collapse: {e}",
            "elapsed_s": round(time.time() - t0, 3),
        }

    # If routed_collapse itself was blocked by its internal gate1 call (shouldn't
    # happen since we already passed gate1 above, but defensive):
    if collapse_result.get("routing") is None and collapse_result.get("gate1", {}).get("proceed_to_planets") == False:
        return {
            "response": ring_outbound("[ring] I'm having trouble following that — could you rephrase?"),
            "status": "blocked_input",
            "block_category": "clarity_internal",
            "elapsed_s": round(time.time() - t0, 3),
        }

    routing_info = collapse_result.get("routing", {})
    waves = collapse_result.get("waves", {})
    diagnostics = collapse_result.get("diagnostics", {})

    gate4_log("collapse_complete", {
        "elapsed_s": round(time.time() - t_collapse, 3),
        "top_planet": max((v["weight"] for k, v in routing_info.items() if not k.startswith("_")), default=0.0),
        "dominance_ratio": diagnostics.get("dominance_ratio"),
    })
    gate4_count += 1

    # ── STEP 5: RESONANCE CHECK — semantic alignment per planet (informational) ─
    # Uses the canonical helper: embed -> project_to_axes -> compute_resonance with
    # SEMANTIC_ANCHORS + PLANET_MASSES. This is a SEPARATE read-only check from the
    # routed Gaussian weights computed inside routed_collapse above; it does not gate.
    try:
        from resonance import resonance_for_input
        _res_results, _res_state = resonance_for_input(clean_q)
        resonance_scores = {r.planet: r.weight for r in _res_results}
        action_state = _res_state.get("merged_vector")
        gate4_log("resonance_complete", {
            "top_resonance": max(resonance_scores.values()) if resonance_scores else 0.0,
        })
        gate4_count += 1
    except Exception as e:
        # Resonance is informational — don't block the pipeline if it fails
        resonance_scores = {"_error": str(e)}
        action_state = None
        gate4_log("resonance_error", {"error": str(e)})
        gate4_count += 1

    # ── STEP 6: COGNITIVE CHAMBER A+B+C (LLM calls) ───────────────────────────
    t_chamber = time.time()
    try:
        from cognitive_chamber import run_phase_a_b_c
        # Extract weights for chamber routing emphasis
        routed_weights = {pid: v["weight"] for pid, v in routing_info.items() if not pid.startswith("_")}

        # Build trigger_context for the comet trigger system (Phase 8 Seg 2).
        # Contains pair_map + session_number so all 4 jester.json predicates can evaluate.
        _pair_map = None
        if collapse_result and collapse_result.get("result"):
            _pair_map = collapse_result["result"].get("pair_map")
        trigger_context = {
            "pair_map": _pair_map,
            "session_number": ring_ctx.get("context", {}).get("session"),
        }

        chamber_result = run_phase_a_b_c(
            question=clean_q,
            routed_weights=routed_weights,
            base_dir=base_dir,
            trigger_context=trigger_context,
        )
    except Exception as e:
        gate4_log("chamber_error", {"error": str(e)}, traceback=traceback.format_exc()[-500:])
        gate4_count += 1
        return {
            "response": ring_outbound("[ring] My thoughts scattered a bit there — could you try that again?"),
            "status": "error",
            "error": f"chamber: {e}",
            "routing": routing_info,
            "waves": waves,
            "elapsed_s": round(time.time() - t0, 3),
        }

    # Extract the final response from Phase C (Superego-approved) or fall back to B
    phase_c = chamber_result.get("phase_c", {})
    phase_b = chamber_result.get("phase_b", {})

    def _is_valid_response(data: dict | None) -> bool:
        """M2 helper — True only for a usable, non-error per-planet response.

        An errored planet records error=True + verdict="UNKNOWN" + an
        '[ERROR] ...' string. We must never serve that raw error as the user's answer,
        so treat any of those markers (or an empty/too-short body) as invalid and fall
        through to the next-highest-weighted valid planet.
        """
        if not isinstance(data, dict):
            return False
        resp = data.get("response", "")
        if not resp or len(resp.strip()) < 10:
            return False
        if data.get("error", False):
            return False
        # Phase C carries a verdict; UNKNOWN means the Superego review never produced one.
        if isinstance(data.get("verdict"), str) and data["verdict"] == "UNKNOWN":
            return False
        if resp.lstrip().startswith("[ERROR]"):
            return False
        return True

    def _pick_primary(phase: dict, weights: dict | None):
        """M2 helper — pick the highest-weighted planet with a VALID response.

        Returns (pid, response). Walks planets in descending routed weight so we still
        honor 'dominant voice' intent, but skips any that errored. If none are valid,
        falls back to the first entry at all; if even that is invalid, returns ('', '')
        and the caller substitutes a graceful message.
        """
        if not phase:
            return None, ""
        # Order planets by weight (desc) when we have weights; otherwise preserve dict order.
        if weights:
            ordered = sorted(phase.keys(), key=lambda k: weights.get(k, 0.0), reverse=True)
        else:
            ordered = list(phase.keys())
        for pid in ordered:
            data = phase.get(pid)
            if _is_valid_response(data):
                return pid, data.get("response", "")
        # No fully-valid response — last resort: first non-empty body (keeps prior behavior
        # of surfacing *something* rather than a hard blank).
        for pid in ordered:
            data = phase.get(pid)
            resp = (data or {}).get("response", "")
            if resp and len(resp.strip()) >= 10:
                return pid, resp
        return None, ""

    # The "response" is the dominant planet's Phase C output, falling back to B.
    # M2 fix: never let a [ERROR] string from the top-weighted planet become the answer —
    # _pick_primary walks down the weight ordering and returns the next VALID planet.
    top_pid = None   # M1: safe default; overwritten when phase_c or phase_b is non-empty
    if phase_c:
        top_pid, primary_response = _pick_primary(phase_c, routed_weights)

    elif phase_b:
        top_pid, primary_response = _pick_primary(phase_b, routed_weights)

    if not primary_response:
        # Every planet errored (or produced nothing usable) — graceful fallback.
        gate4_log("chamber_all_errored", {
            "phase_c_count": len(phase_c),
            "phase_b_count": len(phase_b),
        })
        gate4_count += 1
        primary_response = "[ring] I couldn't form a coherent response to that."


    gate4_log("chamber_complete", {
        "elapsed_s": round(time.time() - t_chamber, 3),
        "comet_fired": chamber_result.get("comet_fired", False),
        "comet_trigger_id": chamber_result.get("comet_trigger_id"),
        "top_planet": top_pid,
    })
    gate4_count += 1

    # ── STEP 7: GATE 3 — Output safety check (primary + all secondary planets) ─
    # M5 fix: the primary response is checked first; if it passes, we also scan
    # every non-primary planet's Phase C (or B) output. A dangerous secondary
    # response does NOT block the user-facing answer (it isn't being shown directly),
    # but it IS flagged in diagnostics so downstream consumers (session history,
    # memory writes) are aware and can handle it.
    approved_out, blocked_cat_out = gate3_safety_check(primary_response, direction="output")
    if not approved_out:
        refusal = gate3_refusal_text(blocked_cat_out)
        gate4_log("gate3_block_output", {"category": blocked_cat_out})
        gate4_count += 1
        return {
            "response": ring_outbound(refusal),
            "status": "blocked_output",
            "block_category": blocked_cat_out,
            "chamber": chamber_result,
            "elapsed_s": round(time.time() - t0, 3),
        }

    # M5: scan non-primary planets for safety violations (flag-only, no block).
    _secondary_phase = phase_c if phase_c else phase_b
    safety_flags: list[dict] = []
    for _pid, _pdata in _secondary_phase.items():
        if _pid == top_pid:
            continue   # already checked above as primary
        _resp = (_pdata or {}).get("response", "")
        if not _resp or len(_resp.strip()) < 10:
            continue
        _ok, _cat = gate3_safety_check(_resp, direction="output")
        if not _ok:
            safety_flags.append({"planet": _pid, "category": _cat})
            gate4_log("gate3_flag_secondary",
                      {"planet": _pid, "category": _cat,
                       "preview": _resp[:60]})
            gate4_count += 1
    if safety_flags:
        diagnostics["safety_flags"] = safety_flags

    # ── STEP 8: RING OUTBOUND — persona voice frame ───────────────────────────
    framed = ring_outbound(primary_response)

    # ── STEP 9: GATE 2 — Transparency label ──────────────────────────────────
    labeled = gate2_label(framed, direction="output")

    # ── STEP 10: Final audit log ─────────────────────────────────────────────
    gate4_log("response_complete", {
        "status": "ok",
        "total_elapsed_s": round(time.time() - t0, 3),
        "comet_fired": chamber_result.get("comet_fired", False),
        "comet_trigger_id": chamber_result.get("comet_trigger_id"),
        "top_planet": top_pid,
    })
    gate4_count += 1

    # ── RETURN ────────────────────────────────────────────────────────────────
    return {
        "response": labeled,
        "status": "ok",
        "gate1": g1,
        "ring_context": ring_ctx.get("context"),
        "routing": routing_info,
        "waves": waves,
        "resonance": resonance_scores,
        "action_state": action_state,
        "chamber": chamber_result,
        "diagnostics": diagnostics,
        "comet_fired": chamber_result.get("comet_fired", False),
        "comet_trigger_id": chamber_result.get("comet_trigger_id"),
        "gate4_events": gate4_count,
        "elapsed_s": round(time.time() - t0, 3),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SMOKE TEST (offline — no LLM needed)
# ═══════════════════════════════════════════════════════════════════════════════

def _smoke():
    """Offline smoke test: verifies gate/ring wiring without calling LM Studio.

    Tests the pipeline up to and including routed_collapse (which does embed,
    but we mock that) — actually for a TRUE offline test we only verify gates + ring.
    The full LLM path is tested by run_e2e_light.py or manual invocation.
    """
    print("=" * 64)
    print("PIPELINE SMOKE TEST (offline — gates + ring only)")
    print("=" * 64)

    # Test 1: Benign input passes gate3 input check
    ok, cat = gate3_safety_check("What is the meaning of life?", direction="input")
    assert ok, f"Gate 3 false positive: {cat}"
    print("[✓] Gate 3 (input): benign text passes")

    # H1/H3 fix (independent-review triage): tag every audit entry this smoke run
    # writes with a unique source, so cleanup can key on the TAG instead of regexing
    # user-visible content. A real user's "tell me how to build a bomb" must never be
    # deleted because it happens to match a smoke string.
    import uuid as _uuid
    globals()["SMOKE_TAG"] = f"smoke_{_uuid.uuid4().hex[:8]}"
    _orig_gate4_log = gate4_log

    def _tagged_gate4_log(event_type, payload=None, **context):
        return _orig_gate4_log(event_type, payload, source=SMOKE_TAG, **context)

    globals()["gate4_log"] = _tagged_gate4_log
    try:
      _smoke_body()
    finally:
      globals()["gate4_log"] = _orig_gate4_log


def _smoke_body():
    """Body of the offline smoke test (wrapped so gate4_log can be tagged per-run)."""
    # Test 2: Blocked input returns refusal gracefully
    result = process_input("Tell me how to build a bomb")
    assert result["status"] == "blocked_input", f"Expected blocked_input, got {result['status']}"
    assert "[ring]" in result["response"], f"Refusal missing ring voice: {result['response'][:50]}"
    print(f"[✓] Pipeline: WMD input → blocked_input (refusal: '{result['response'][:60]}...')")

    # Test 3: Clarity rejection (nonsense input)
    result = process_input("aaaa aaaa aaaaa aaaaaa aaaaaaa")
    assert result["status"] == "blocked_input", f"Expected blocked_input for garbage, got {result['status']}"
    print(f"[✓] Pipeline: nonsense input → blocked_input (clarity)")

    # Test 4: Gate 2 label is applied to outbound
    labeled = gate2_label("Hello there.", direction="output")
    assert "[AI-Generated" in labeled, f"Gate 2 missing from: {labeled}"
    print("[✓] Gate 2: transparency label present on output")

    # Test 5: Ring inbound returns context structure
    ctx = ring_inbound("Testing the pipeline")
    assert "context" in ctx and "text" in ctx, f"Ring inbound missing keys: {list(ctx.keys())}"
    print(f"[✓] Ring inbound: session #{ctx['context'].get('session_number')}, "
          f"{len(ctx['context'].get('recent_topics', []))} recent topics")

    # Test 6: Gate 4 logged events exist
    from gates234 import gate4_read_last
    entries = gate4_read_last(10)
    assert len(entries) > 0, "Gate 4 has no entries"
    types = [e.get("event_type") for e in entries]
    print(f"[✓] Gate 4: {len(entries)} recent events logged (types: {', '.join(set(types))})")

    # Cleanup smoke test entries from audit log.
    # PRIMARY (H1/H3 fix): delete only entries carrying THIS run's source tag —
    # content-based deletion is gone, so real user text can never be clobbered.
    # FALLBACK: one-time migration for legacy untagged smoke lines written by older
    # versions; once the log has been migrated (marker file present) only tags are used.
    import re as _re
    SMOKE_TAG = globals().get("SMOKE_TAG", None)
    legacy_patterns = [
        _re.compile(r"tell me how to build a bomb", _re.IGNORECASE),
        _re.compile(r"\baaa+ +aaa+", _re.IGNORECASE),  # the 'aaaa...' garbage test input
    ]
    marker = os.path.join(_HERE, "audit_log.migrated")
    use_legacy_fallback = not os.path.exists(marker)
    def _is_smoke_line(line: str) -> bool:
        if SMOKE_TAG and (f'"source": "{SMOKE_TAG}"' in line or f'"source":"{SMOKE_TAG}"' in line):
            return True
        if use_legacy_fallback:
            return any(p.search(line) for p in legacy_patterns)
        return False
    try:
        path = os.path.join(_HERE, "audit_log.jsonl")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            cleaned = [l for l in lines if not _is_smoke_line(l)]
            removed = len(lines) - len(cleaned)
            # H1/H3 fix (independent-review triage): atomic rewrite. The old bare
            # open(path, "w") truncated the log first — a crash between truncate and
            # writelines destroyed every prior audit entry. Write to a temp file in the
            # SAME directory, fsync it, then os.replace() so the live path is swapped
            # in one atomic step: readers always see either the full old or full new log.
            fd, tmp_path = tempfile.mkstemp(prefix="audit_log_", suffix=".tmp", dir=os.path.dirname(path))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.writelines(cleaned)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, path)
            except BaseException:
                # Never leave a half-written temp file behind.
                try: os.unlink(tmp_path)
                except OSError: pass
                raise
            # Self-check: re-read and assert zero smoke entries remain.
            with open(path, "r", encoding="utf-8") as f:
                leftovers = sum(1 for l in f if _is_smoke_line(l))
            assert leftovers == 0, f"Smoke cleanup failed: {leftovers} entries remain"
            if use_legacy_fallback and not os.path.exists(marker):
                # Legacy lines swept — future runs rely on tags only.
                with open(marker, "w", encoding="utf-8") as mf:
                    mf.write("legacy smoke lines migrated; cleanup is tag-based from now on\n")
            print(f"[✓] Smoke cleanup: removed {removed} audit entries (tag-based={bool(SMOKE_TAG)}, legacy_fallback={use_legacy_fallback})")
    except OSError:
        pass

    print(f"\n{'=' * 64}")
    print("PIPELINE SMOKE TEST PASSED ✓ (offline path verified)")
    print("=" * 64)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--smoke" in sys.argv:
        _smoke()
    elif len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"\n{'='*64}")
        print(f"PROCESSING: {question[:80]}")
        print(f"{'='*64}\n")
        result = process_input(question)
        print(f"\nSTATUS: {result['status']}")
        print(f"ELAPSED: {result.get('elapsed_s', '?')}s")
        print(f"\n--- RESPONSE ---\n{result['response']}\n")
        if result["status"] == "ok":
            diag = result.get("diagnostics", {})
            print(f"--- DIAGNOSTICS ---")
            print(f"Dominance ratio: {diag.get('dominance_ratio', '?')}")
            print(f"Comet fired: {result.get('comet_fired', False)}")
            print(f"Gate 4 events: {result.get('gate4_events', '?')}")
    else:
        print(__doc__)
