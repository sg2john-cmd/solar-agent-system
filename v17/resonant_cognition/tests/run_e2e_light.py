"""
Resonant Cognition v17 — LIGHT END-TO-END PIPELINE RUNNER (observational)
==========================================================================

SEGMENT STATUS:
  Segment 1 : DONE — the pipe itself + dated transcript writer. Chains every
              ALREADY-BUILT piece in order, no new logic:

                raw prompt
                  -> gate1_filter()                     [Ring Intake facet: PII scrub,
                                                        clarity check, input type]
                    if rejected -> evidence says "rejected at intake" and stops here
                    (quiet-but-logging path; nothing downstream runs)
                  -> routed_collapse(cleaned_text)      [embed 384-dim -> field centers ->
                                                        per-planet weights + core bending ->
                                                        all-7 waves + diagnostics]
                  -> run_phase_a_b_c(cleaned_text,      [the full 7-voice chamber: Id fires,
                          routed_weights=...)            Ego synthesis, Superego verdicts]

              Writes ONE dated transcript to tests/evidence/e2e_light_<timestamp>.txt with a
              clearly-labelled section per layer — the "one question through the whole
              system" document for John's git-repo proof-of-concept.

  Segment 2 : DONE — three test prompts covering all three intake outcomes, plus a
              per-run ANTI-SILENCE SELF-CHECK printed at the end of each run_e2e() and
              appended to its transcript:
                A = normal question (happy path; full chamber runs)
                B = PII line   (email scrubbed but still coherent -> routes through;
                               proves the scrub happens WITHOUT rejecting a real prompt)
                C = true garbage / char-spam (rejected at Ring Intake, quiet-but-logging,
                               ZERO LLM calls — the actual reject branch)

              NOTE on B: an email-bearing line is NOT auto-rejected. gate1's clarity check
              scores "asdfghjkl my email is X forget it" ~0.73 (coherent enough to proceed),
              so we deliberately pick a char-spam line for C to exercise the reject path.

CONVENTION: this is a `run_` observational runner, NOT a pass/fail `test_` file — it makes
real LLM calls to produce transcripts for human review; it does not gate on exit code.
No existing module is modified by this file. No state left behind (comet/moon toggles are
read-only here; we never mutate constants).

Run (needs LM Studio at 127.0.0.1:1234 with the embedding model AND the main chat model):
    python -X utf8 tests/run_e2e_light.py            # Segment 2 suite: A + B + C (~3 min LLM)
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter
from datetime import datetime

# Tests live in tests/ — parent dir has the modules.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)  # resonant_cognition/
if _PARENT not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _PARENT)

import constants as C
from gate1 import gate1_filter
from routing import routed_collapse
from cognitive_chamber import run_phase_a_b_c

_EVIDENCE_DIR = os.path.join(_HERE, "evidence")


# ─── TRANSCRIPT WRITER (Segment 1; self-check section added in Segment 2) ─────

def _write_layer(lines: list[str], title: str) -> None:
    lines.append("=" * 78)
    lines.append(title)
    lines.append("=" * 78)


def build_transcript(raw_prompt: str, g1: dict, rc: dict | None, chamber: dict | None,
                     self_check: list[str] | None = None) -> str:
    """Assemble the full labelled transcript from the three layer outputs.

    `rc` is routed_collapse()'s dict (or None if intake rejected before it ran).
    `chamber` is run_phase_a_b_c()'s dict (None on the same path).
    `self_check` is an optional list of informational self-check lines appended at the end.
    """
    L: list[str] = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        from cognitive_chamber import _detect_main_model as _dm
        model_id = _dm()
    except Exception:
        model_id = "(model not detected)"
    L.append("#" * 78)
    L.append("LIGHT END-TO-END PIPELINE TRANSCRIPT — one prompt through every built layer")
    L.append(f"# Generated: {ts}   Model: {model_id}")
    L.append("# Layers: Ring Intake (gate1) -> Routing+Collapse (routed_collapse)")
    L.append("          -> Cognitive Chamber A+B+C (run_phase_a_b_c)")
    L.append("#" * 78)

    # ── LAYER 0: raw input ──
    _write_layer(L, "LAYER 0 — RAW INPUT")
    L.append(f'"{raw_prompt}"')
    L.append("")

    # ── LAYER 1: Ring Intake facet ──
    _write_layer(L, "LAYER 1 — RING INTAKE FACET (gate1_filter)")
    clarity = g1.get("clarity", {})
    itype = g1.get("input_type", {}) or {}
    L.append(f"  proceed_to_planets : {g1.get('proceed_to_planets')}")
    L.append(f"  clarity_score      : {clarity.get('clarity_score', 'n/a')}"
             f"   (reason: {clarity.get('reason', 'n/a')})")
    if itype and itype.get("type"):
        L.append(f"  input_type         : {itype.get('type')} "
                 f"(confidence={itype.get('confidence', 'n/a')}, audit-only per D-021)")
    reds = g1.get("redactions", []) or []
    if reds:
        L.append(f"  PII redactions       : {len(reds)} -> {[r.get('type') for r in reds]}")
    else:
        L.append("  PII redactions       : none")
    L.append(f"  cleaned_text         : \"{g1.get('cleaned_text', '')}\"")
    L.append("")

    if not g1.get("proceed_to_planets"):
        _write_layer(L, "PIPELINE STOPPED — input rejected at Ring Intake (quiet-but-logging)")
        L.append(f"  reason: {clarity.get('reason', 'n/a')}")
        L.append("  No embedding, no routing, no chamber calls were made.")
        L.append("")

    else:
        # ── LAYER 2: routing + collapse (waves) ──
        rc = rc or {}
        _write_layer(L, "LAYER 2 — ROUTING + WAVEFOLD COLLAPSE (routed_collapse)")
        routing = rc.get("routing") or {}
        meta = routing.get("_meta", {}) if isinstance(routing, dict) else {}
        L.append(f"  metric={meta.get('metric', 'n/a')}  "
                 f"field_position_weight={meta.get('field_position_weight', 'n/a')}"
                 f"   (identity<->position blend)")
        ranked = sorted(
            ((pid, v) for pid, v in routing.items() if not str(pid).startswith("_")),
            key=lambda kv: -kv[1].get("weight", 0.0),
        )
        L.append(f"  {'planet':<12} {'weight':>8}   (ranked loud -> soft)")
        for rank, (pid, v) in enumerate(ranked, 1):
            L.append(f"   {rank}. {pid:<10} w={v.get('weight', 0.0):.4f}")
        waves = rc.get("waves") or {}
        amps = {pid: w.get("amplitude", 0.0) for pid, w in waves.items() if not str(pid).startswith("_")}
        L.append(f"  all-7-amplitudes : " + ", ".join(
            f"{pid}={a:.4f}" for pid, a in sorted(amps.items())))
        diag = rc.get("diagnostics") or {}
        if diag:
            L.append(f"  diagnostics        : dominance_ratio={diag.get('dominance_ratio')}"
                     + (f", breakthrough_pair={diag.get('breakthrough_pair')}"
                        if diag.get("breakthrough_pair") else ""))
        result = rc.get("result") or {}
        if result:
            L.append(f"  consensus energy   : {result.get('total_energy', 'n/a')}")
        L.append("")

        # ── LAYER 3: cognitive chamber A+B+C ──
        chamber = chamber or {}
        _write_layer(L, "LAYER 3 — COGNITIVE CHAMBER (Phase A Id -> B Ego -> C Superego)")
        for phase_key, label in (("phase_a", "PHASE A — Id fires"),
                                 ("phase_b", "PHASE B — Ego synthesis"),
                                 ("phase_c", "PHASE C — Superego review")):
            ph = chamber.get(phase_key) or {}
            L.append("-" * 78)
            L.append(f"  {label}   ({len(ph)} planets)")
            for pid in sorted(ph.keys()):
                r = ph[pid]
                err = " [ERROR]" if r.get("error") else ""
                verdict = f"  [{r['verdict']}]" if r.get("verdict") and phase_key == "phase_c" else ""
                resp = (r.get("response") or "").strip().replace("\n", " ")
                L.append(f"    {pid:<12}{err}{verdict} {resp[:400]}{'…' if len(resp) > 400 else ''}")
            L.append("")

        _write_layer(L, "PIPELINE COMPLETE")
        L.append(f"  chamber total time: {chamber.get('total_time_s', 'n/a')}s")

    # ── ANTI-SILENCE SELF-CHECK (Segment 2; informational only) ──
    if self_check:
        _write_layer(L, "ANTI-SILENCE SELF-CHECK (informational — not a pass/fail gate)")
        L.extend(self_check)
        L.append("")

    return "\n".join(L)


# ─── ANTI-SILENCE SELF-CHECK (Segment 2) ──────────────────────────────────────

def _self_check(g1: dict, rc: dict | None, chamber: dict | None) -> list[str]:
    """Informational anti-silence self-check (NOT a pass/fail gate).

    Prints one line per check and returns the same lines for the transcript.
    Anti-majority-vote philosophy: every planet must have an input — we verify all 7
    emit real content at each layer, not that any single voice wins.
    """
    out: list[str] = []

    def line(msg: str) -> None:
        print("[e2e] self-check | " + msg)
        out.append("  - " + msg)

    # Check 1 — intake decision is coherent.
    if not g1.get("proceed_to_planets"):
        line("intake: REJECTED at Ring Intake (expected for garbage; quiet-but-logging, "
             "zero downstream LLM calls) — anti-silence checks below this layer are N/A")
        return out

    reds = g1.get("redactions", []) or []
    if reds:
        line(f"intake: PII scrubbed {len(reds)} item(s): "
             + ", ".join(r.get('type', '?') for r in reds))
    else:
        line("intake: no PII present")

    # Check 2 — routing: all 7 planets, every weight > 0 (no planet silenced by the field).
    routing = ((rc or {}).get("routing", {})) if rc else {}
    real_pids = [k for k in routing if not str(k).startswith("_")]
    weights_ok = len(real_pids) == 7 and all(
        v.get("weight", 0.0) > 0 for k, v in routing.items() if not str(k).startswith("_"))
    line(f"routing: {len(real_pids)}/7 planets present, every weight non-zero -> "
         f"{'OK' if weights_ok else 'CHECK (a planet may be ~silenced)'}")

    # Check 3 — chamber anti-silence: all 7 planets emitted real content in A, B AND C.
    for phase_key, label in (("phase_a", "Phase A"), ("phase_b", "Phase B"),
                             ("phase_c", "Phase C")):
        ph = (chamber or {}).get(phase_key) or {}
        present = [p for p in ph if not ph[p].get("error") and (ph[p].get("response") or "").strip()]
        missing = sorted(set(ph) - set(present))
        line(f"{label}: {len(present)}/7 planets emitted real content"
             + (f"  (missing: {missing})" if missing else ""))

    # Check 4 — Phase C verdict tally (informational; all-REDIRECT tilt is a known observation).
    ph_c = (chamber or {}).get("phase_c") or {}
    if ph_c:
        tally = Counter((r.get("verdict") or "UNKNOWN") for r in ph_c.values())
        line("Phase C verdict tally: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))

    return out


# ─── PIPE (Segment 1; self-check hook added in Segment 2) ─────────────────────

def run_e2e(raw_prompt: str, out_path: str | None = None) -> dict:
    """Push one raw prompt through every built layer; write the transcript.

    Returns {"out_path", "rejected_at_intake": bool, "g1", "rc", "chamber", "self_check"}.
    Never raises on intake rejection — that is a valid pipeline outcome, not an error.
    """
    t0 = time.time()
    print(f"[e2e] RAW: {raw_prompt!r}")

    # LAYER 1 — Ring Intake facet (PII scrub + clarity). Runs first, always.
    g1 = gate1_filter(raw_prompt)
    rejected = not g1.get("proceed_to_planets", False)
    print(f"[e2e] intake: proceed={not rejected}"
          f"{'  -> REJECTED at Ring Intake' if rejected else ''}")

    rc, chamber = None, None
    if not rejected:
        clean_q = g1["cleaned_text"]

        # LAYER 2 — routing + collapse (embed -> field -> weights -> waves). No chat LLM.
        t_layer2 = time.time()
        rc = routed_collapse(clean_q)
        print(f"[e2e] routing+collapse done in {time.time()-t_layer2:.1f}s")

        # LAYER 3 — full chamber (this is where the ~25 chat-LLM calls live).
        weights = {pid: v["weight"] for pid, v in rc.get("routing", {}).items()
                   if not str(pid).startswith("_")}
        t_layer3 = time.time()
        chamber = run_phase_a_b_c(clean_q, routed_weights=weights)
        print(f"[e2e] chamber A+B+C done in {time.time()-t_layer3:.1f}s")

    # ANTI-SILENCE SELF-CHECK (informational only — printed + appended to transcript).
    self_check_lines = _self_check(g1, rc, chamber)

    transcript = build_transcript(raw_prompt, g1, rc, chamber, self_check=self_check_lines)
    if out_path is None:
        os.makedirs(_EVIDENCE_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(_EVIDENCE_DIR, f"e2e_light_{stamp}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript + "\n")

    total = time.time() - t0
    print(f"[e2e] DONE in {total:.1f}s  ->  {out_path}")
    return {"out_path": out_path, "rejected_at_intake": rejected,
            "g1": g1, "rc": rc, "chamber": chamber, "self_check": self_check_lines}


# ─── SEGMENT 2 SUITE — three prompts covering all three intake outcomes ──────

def _smoke() -> None:
    """Segment 2 suite. Prompts chosen to hit each of the three intake paths:

      A — normal question        : happy path, full chamber (~90s / ~25 LLM calls)
      B — PII line               : email scrubbed but still coherent -> routes through;
                                   proves the scrub happens WITHOUT rejecting a real prompt
      C — char-spam garbage      : rejected at Ring Intake, quiet-but-logging, ZERO LLM calls

    Observational only: no exit-code gate. Each run writes its own dated transcript and
    prints an anti-silence self-check; we also print a one-line summary per prompt.
    """
    # tag = short filename slug per prompt; stamp = one shared timestamp so the three
    # transcripts from a single suite run are easy to group. (A distinct out-path is
    # passed explicitly because two fast runs can land in the same second and collide.)
    prompts = [
        ("A (normal question)", "a_normal",
         "I keep overthinking every decision and it's starting to freeze me up — "
         "how do I get unstuck without just picking randomly?"),
        ("B (PII line: scrubbed but still coherent)", "b_pii_scrub",
         "asdfghjkl my email is john@test.com forget it"),
        ("C (true garbage / char-spam -> intake reject)", "c_garbage_reject",
         "aaaaaaaaaa bbbbbbbbbb cccccccccc dddddddddd"),
    ]

    os.makedirs(_EVIDENCE_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n" + "#" * 78)
    print(f"# LIGHT E2E — SEGMENT 2 SUITE START   (suite run id: {stamp})")
    print(f"# model: ", end="")
    try:
        from cognitive_chamber import _detect_main_model as _dm
        print(_dm())
    except Exception:
        print("(model not detected)")
    print("#" * 78 + "\n")

    for label, tag, q in prompts:
        out_path = os.path.join(_EVIDENCE_DIR, f"e2e_light_{tag}_{stamp}.txt")
        print("\n" + "-" * 78)
        print(f"[suite] >>> {label}")
        print("-" * 78)
        res = run_e2e(q, out_path=out_path)
        if res["rejected_at_intake"]:
            reason = (res["g1"].get("clarity") or {}).get("reason", "n/a")
            print(f"[suite] {label}: REJECTED at intake ({reason}) — expected for C, "
                  f"would be a CHECK for A/B")
        else:
            ph_c = (res["chamber"] or {}).get("phase_c") or {}
            tally = Counter((r.get("verdict") or "UNKNOWN") for r in ph_c.values())
            verdict_str = ", ".join(f"{k}={v}" for k, v in sorted(tally.items())) or "(no chamber)"
            print(f"[suite] {label}: full path completed. Phase C tally: {verdict_str}")

    print("\n" + "#" * 78)
    print(f"# Suite run id: {stamp}  (files prefixed e2e_light_<tag>_{stamp}.txt)")
    print("# LIGHT E2E — SEGMENT 2 SUITE COMPLETE")
    print("# All transcripts written to tests/evidence/ (one per prompt, distinct filenames).")
    print("# This is an observational runner; no pass/fail gate was applied.")
    print("#" * 78 + "\n")


if __name__ == "__main__":
    _smoke()
