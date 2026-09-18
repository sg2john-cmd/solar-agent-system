"""
Resonant Cognition v17 — Phase 6 Segment 5b: LIVE monthly self-review runner (D-009)
====================================================================================

RUNNER (observational, `run_*`), NOT a graded regression test. This is the ~21+ LLM
call burst that John approved running as one deliberate live shot while he napped.

WHAT IT DOES, end to end:
  1. Trigger check via ring.check_self_review_trigger() on the REAL relationship log
     and G2 state (toggle forced ON for this run — it is a dedicated live runner).
  2. G2 change report: ONE lazy _llm_chat_cached() call over the skeleton raw material
     (session stats + recent topics), voiced from G2's self-model perspective.
  3. FULL 7-planet debate via cognitive_chamber.run_phase_a_b_c(): Phase A Id fires ×7,
     Phase B Ego synthesis ×7, Phase C Superego review ×7 — all real LLM calls.
  4. ANTI-SILENCE CHECK (anti-majority-vote rule): every planet must have emitted
     non-empty, non-error content in ALL THREE phases before any verdict is logged.
     If any planet failed/silenced → nothing is treated as decided; the record is held
     with status="held_anti_silence" and NO committed verdict is written to G2's ring.
  5. Verdict logged via ring.log_self_review_verdict() — append-only, carries BEFORE-
     state snapshot (reversibility moon), tier-1 behavioral only (consistency moon),
     no numeric self-model mutation (magnitude moon).
  6. Maya's announcement line: ONE more lazy LLM call in the persona's voice_notes,
     so the Ring announces it naturally ("It's been a month...").
  7. Evidence saved to tests/evidence/p6s5_selfreview_live_<timestamp>.log — the full
     transcript (report, per-planet Phase A/B/C text, verdict tally) is in that file.

COST WARNING: ~23 LLM calls total (1 report + 7×A + 7×B + 7×C + 1 announcement).
Near the 4090's ceiling with the base model loaded — this runner assumes LM Studio is
up and idle. Moons/Comet stay at their constants defaults for this run (OFF by default),
so the debate shape is exactly the standard chamber A/B/C.

USAGE:
    python -X utf8 tests/run_self_review_live.py            # full live run
    python -X utf8 tests/run_self_review_live.py --dry     # ZERO LLM: trigger + skeleton
                                                           # only, prints what WOULD run

EXIT CODES: 0 = completed (verdict logged OR intentionally held), 1 = hard failure.
"""

from __future__ import annotations

import json
import os
import sys
import time
import datetime as _dt

_HERE = os.path.dirname(os.path.abspath(__file__))            # .../tests
_ROOT = os.path.dirname(_HERE)                                # .../resonant_cognition
sys.path.insert(0, _ROOT)

import ring                                                   # noqa: E402  (offline-safe import)


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _evidence_path(name: str) -> str:
    d = os.path.join(_HERE, "evidence")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)


def _load_g2() -> dict:
    with open(os.path.join(_ROOT, "giants", "g2_selfmodel.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def _dry_run() -> int:
    """--dry: zero LLM. Show trigger decision + the report skeleton that 5b would feed."""
    import constants as C
    rel_log = ring.load_relationship_log()
    g2 = _load_g2()
    saved = getattr(C, "RING_SELF_REVIEW_ENABLED", False)
    C.RING_SELF_REVIEW_ENABLED = True          # force ON purely to evaluate the trigger
    try:
        trig = ring.check_self_review_trigger(rel_log, g2_state=g2)
    finally:
        C.RING_SELF_REVIEW_ENABLED = saved

    persona = ring.load_persona()
    print("=" * 64)
    print("DRY RUN — Segment 5b self-review (ZERO LLM calls)")
    print("=" * 64)
    print(f"session_count            : {trig['session_count']}")
    print(f"sessions since last rev. : {trig['sessions_since_last_review']}")
    print(f"months since last review : "
          f"{trig['months_since_last_review'] if trig['months_since_last_review'] != float('inf') else 'no anchor yet'}")
    print(f"trigger fire?            : {trig['fire']}  reason={trig['reason']}")
    print("-" * 64)
    print("Report skeleton (raw material G2 would expand):")
    print(ring.build_g2_change_report_skeleton(rel_log, persona=persona))
    print("-" * 64)
    if trig["fire"]:
        print("A full run WOULD now make ~23 LLM calls and log a verdict to G2's ring_buffer.")
    else:
        print("Trigger not due yet — a full run would no-op at the trigger gate (zero LLM).")
    return 0


def main() -> int:
    import constants as C

    if "--dry" in sys.argv[1:]:
        return _dry_run()

    t_start = time.time()
    log_lines: list[str] = []

    def log(line: str = "") -> None:
        print(line)
        log_lines.append(line)

    ev_path = _evidence_path(f"p6s5_selfreview_live_{_ts()}.log")

    log("=" * 64)
    log("PHASE 6 SEGMENT 5b — LIVE MONTHLY SELF-REVIEW (D-009)")
    log(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 64)

    # ── 1. Trigger check on REAL state (force toggle ON — dedicated live runner) ──
    rel_log = ring.load_relationship_log()
    g2 = _load_g2()
    saved_toggle = bool(getattr(C, "RING_SELF_REVIEW_ENABLED", False))
    C.RING_SELF_REVIEW_ENABLED = True
    try:
        trig = ring.check_self_review_trigger(rel_log, g2_state=g2)
    finally:
        # Keep it ON for this process so the rest of the flow sees an enabled system.
        pass
    log(f"[1] Trigger check: fire={trig['fire']} reason={trig['reason']} "
        f"sessions={trig['session_count']} since_last={trig['sessions_since_last_review']}")

    # ── 2. G2 change report (ONE LLM call over the skeleton) ──────────────────────
    persona = ring.load_persona()
    skeleton = ring.build_g2_change_report_skeleton(rel_log, persona=persona)
    log("\n[2] Building G2 change report...")
    log("-" * 64)
    log(skeleton)
    log("-" * 64)

    from cognitive_chamber import _llm_chat_cached   # real LLM — LM Studio must be up

    g2_name = "G2 Self-Model"
    report_system = (
        f"You are {g2_name}, the evolving self-model of a seven-planet AI solar system. "
        f"The user-facing persona is '{persona.get('name','')}'. "
        "A periodic self-review has been triggered. Using ONLY the raw material provided, "
        "write your natural-language change report: what you have noticed changing in how "
        "the system thinks and speaks over this period (tone, recurring themes, which "
        "planets carry more weight), and what that means for future sessions. Be concrete "
        "about the topics listed; if material is thin, say honestly that the record is young. "
        "120-250 words. No markdown, no preamble."
    )
    report_text = _llm_chat_cached(
        [{"role": "system", "content": report_system},
         {"role": "user", "content": skeleton}],
        temperature=0.7,
        max_tokens=int(getattr(C, "RING_SELF_REVIEW_MAX_TOKENS", 384)),
    )
    log("\n[2] G2 change report:\n")
    log(report_text)

    # ── 3. FULL 7-planet debate via run_phase_a_b_c() ─────────────────────────────
    debate_question = (
        "The system's self-model has just submitted this periodic self-review report: "
        f'"{report_text}" — Review it as a group. Does the reported drift sound true to '
        "what you each experienced in recent sessions? Where does it overstate, understate, "
        "or miss something? APPROVE if the report is faithful and safe to commit; REDIRECT "
        "if it needs correction before it becomes part of the self-model."
    )
    log("\n[3] Running FULL 7-planet debate (Phase A → B → C, ~21 LLM calls)...")
    combined = run_phase_a_b_c(debate_question)

    # ── 4. ANTI-SILENCE CHECK — every planet must emit in ALL three phases ─────────
    def _clean(r: dict | None) -> str:
        if not r:
            return ""
        t = str(r.get("response", "") or "").strip()
        if t.startswith("[ERROR]"):
            return ""
        return t

    errors: list[str] = []
    for phase_key in ("phase_a", "phase_b", "phase_c"):
        results = combined.get(phase_key, {}) or {}
        if len(results) < 7:
            errors.append(f"{phase_key}: only {len(results)}/7 planets returned")
        for pid, r in sorted(results.items()):
            if not _clean(r):
                errors.append(f"{phase_key}:{pid} empty or errored")

    phase_c = combined.get("phase_c", {}) or {}
    approves = sum(1 for r in phase_c.values() if str(r.get("verdict", "")).upper() == "APPROVE")
    redirects = sum(1 for r in phase_c.values() if str(r.get("verdict", "")).upper() == "REDIRECT")
    all_emitted = not errors and len(phase_c) == 7

    log("\n" + "-" * 64)
    log(f"[4] ANTI-SILENCE CHECK: {'ALL 7 EMITTED IN ALL 3 PHASES' if all_emitted else 'VIOLATION — see below'}")
    for e in errors:
        log(f"     ✗ {e}")
    log(f"    Phase C tally: APPROVE={approves} REDIRECT={redirects} (of {len(phase_c)} planets)")

    # ── 5. Verdict logged to G2's ring_buffer (append-only, reversible) ───────────
    summary = {
        "all_emitted": all_emitted,
        "approve": approves,
        "redirect": redirects,
        "error": errors,
        "session_count": trig["session_count"],
    }
    record = ring.log_self_review_verdict(report_text, debate_summary=summary)
    log(f"\n[5] Verdict logged to G2 ring_buffer: status={record['status']} ts={record['ts']:.0f}")

    # ── 6. Maya's announcement (ONE LLM call, persona voice) ──────────────────────
    if all_emitted:
        ann_system = (
            f"You are '{persona.get('name','')}', the user-facing persona of this system. "
            f"Voice: {persona.get('voice_notes','warm, natural')}. A monthly self-review "
            "just completed and its verdict was logged. Announce it to the user in ONE short, "
            "natural paragraph (2-4 sentences): that some time has passed, that you've been "
            f"thinking about how the system has changed, and one concrete thing from the report "
            f'that matters to them. Do NOT paste the full report; reference it. No markdown.\n'
            f'The change report (for your reference): "{report_text[:800]}"'
        )
        try:
            announcement = _llm_chat_cached(
                [{"role": "system", "content": ann_system},
                 {"role": "user", "content": "Announce the completed self-review to the user now."}],
                temperature=float(getattr(C, "RING_IDLE_TEMPERATURE", 0.8)),
                max_tokens=224,
            )
        except Exception as exc:
            announcement = f"[{persona.get('name','Ring')} was going to say something about the self-review (unavailable: {type(exc).__name__})]"
    else:
        announcement = (f"{persona.get('name','Ring')}: the monthly review ran, but not every "
                        "voice came through clearly this time — I'm holding it rather than "
                        "pretending we reached a clean verdict. It's logged for another pass.")
    log(f"\n[6] Ring announcement:\n{announcement}")

    # ── 7. Per-planet transcript (full evidence) ──────────────────────────────────
    log("\n" + "=" * 64)
    log("FULL DEBATE TRANSCRIPT")
    log("=" * 64)
    for phase_key, label in (("phase_a", "PHASE A — Id fires"),
                             ("phase_b", "PHASE B — Ego synthesis"),
                             ("phase_c", "PHASE C — Superego review")):
        results = combined.get(phase_key, {}) or {}
        log(f"\n── {label} ({len(results)}/7 planets)")
        for pid in sorted(results.keys()):
            r = results[pid]
            verdict = f" [{r.get('verdict','')}]" if "verdict" in r else ""
            txt = (str(r.get("response", "") or "").strip() or "(empty)")[:1200]
            log(f"\n  ▸ {pid} ({r.get('elapsed_s','?')}s){verdict}")
            for line in txt.splitlines():
                log(f"    {line}")

    total = time.time() - t_start
    log("\n" + "=" * 64)
    log(f"SEGMENT 5b COMPLETE in {total:.1f}s — "
        f"{'verdict COMMITTED' if all_emitted else 'verdict HELD (anti-silence)'}; "
        f"Phase C APPROVE={approves} REDIRECT={redirects}")
    log(f"Evidence file: {ev_path}")

    with open(ev_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    # Restore the toggle to its default (OFF) for any subsequent live flow.
    C.RING_SELF_REVIEW_ENABLED = saved_toggle
    return 0 if all_emitted else 1


if __name__ == "__main__":
    from cognitive_chamber import run_phase_a_b_c   # noqa: E402  (only imported at run time)
    sys.exit(main())
