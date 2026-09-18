"""
Resonant Cognition v17 — Phase 7, Segment 4: G2 Sandbox (PROPOSED_CHANGE_TRIAL)
==============================================================================

The sandbox is the EMPIRICAL trial for proposed self-changes sitting in G2's
ring_buffer. The three G2 moons judge legality and magnitude (deterministic,
zero LLM calls — see g2_ops.py). The sandbox judges ACTUAL BEHAVIORAL EFFECT:
does applying this change to the live collapse pipeline degrade output?

DESIGN — Plan A (single-turn before/after diff; USER-APPROVED):
    For each representative trial prompt:
        1. Run run_collapse(prompt, g2_bias_vector=BASELINE)   -> record metrics
           BASELINE = memory.load_g2_bias_wave() as-is (no new candidate).
        2. Run run_collapse(prompt, g2_bias_vector=CANDIDATE)  -> record metrics
           CANDIDATE = the bias wave computed AS IF the proposed entry were
                      already committed to contents.
        3. Compute:
             tension_shift   = |candidate.tension - baseline.tension|
             coherence       = cosine(baseline.consensus_vector, candidate.consensus_vector)
        4. Verdict per prompt (and overall):
             FAIL if tension_shift > G2_SANDBOX_TENSION_SHIFT_MAX
                  OR coherence   < G2_SANDBOX_CONSENSUS_COHERENCE_MIN

    Why this shape: a single committed G2 entry shifts the aggregated bias wave
    only slightly, so small deltas are EXPECTED and healthy — that is exactly
    what the thresholds (shift <= 0.30, coherence >= 0.70) tolerate. A harmful
    or structurally-wrong candidate will show up as a tension jump or a rotated
    consensus direction that the numbers catch without any LLM judgement.

WHY NOT MULTI-DAY SIMULATION:
    Simulated multi-day runs would be HALLUCINATED, not measured — they test our
    model of the system, not the system itself (John's question, answered in
    conversation). A real before/after diff on live pipeline output is cheaper,
    honest, and sufficient for "is this specific change safe to commit?".

OFFLINE-SAFETY (same pattern as RING_IDLE_BEHAVIOR / g2_ops):
    When G2_SANDBOX_ENABLED=False (dev default), try_candidate() returns
    {"status": "skipped", ...} with ZERO LLM/embedding calls and does NOT import
    collapse or memory. The self-test below therefore runs entirely offline —
    no LM Studio required.

COST:
    Each trial prompt = 2 embedding calls (baseline + candidate). No full LLM
    generations — collapse is vector-mode ("dumb planets"); the chamber never
    fires in a sandbox run. Default G2_SANDBOX_TRIAL_PROMPTS=3 -> ~6 embeddings.

FUTURE UPGRADE (documented, scaffold included, INERT):
    A full multi-day simulation would replay N synthetic sessions through the
    pipeline with/without the candidate and compare trajectory-level drift
    (tension means, consensus direction walk, per-planet amplitude stability).
    See g2_sandbox_multiday() below: a clearly-marked scaffold that returns an
    "not_implemented" report. It is present so wiring it later is not a rewrite;
    the plan to build it lives in Build Plan.md (Phase 7, future-updates note).

RUN: python -X utf8 giants/g2_sandbox.py   (self-test, no LM Studio needed)
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))          # .../giants
_PKG_ROOT = os.path.dirname(_HERE)                          # .../resonant_cognition
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)
_G2_PATH = os.path.join(_HERE, "g2_selfmodel.json")

# ─── TUNABLES (single source of truth: constants.py — added this segment) ────
try:
    from constants import (
        G2_SANDBOX_ENABLED as _CONST_SB_ENABLED,
        G2_SANDBOX_TRIAL_PROMPTS as _CONST_SB_PROMPTS,
        G2_SANDBOX_TENSION_SHIFT_MAX as _CONST_SB_TSHIFT,
        G2_SANDBOX_CONSENSUS_COHERENCE_MIN as _CONST_SB_CMIN,
    )
except ImportError:  # pragma: no cover — fallback for isolated runs
    _CONST_SB_ENABLED = False
    _CONST_SB_PROMPTS = 3
    _CONST_SB_TSHIFT = 0.30
    _CONST_SB_CMIN = 0.70

G2_SANDBOX_ENABLED = _CONST_SB_ENABLED      # master switch (OFF in dev, ON in prod)
G2_SANDBOX_TRIAL_PROMPTS = _CONST_SB_PROMPTS
G2_SANDBOX_TENSION_SHIFT_MAX = _CONST_SB_TSHIFT
G2_SANDBOX_CONSENSUS_COHERENCE_MIN = _CONST_SB_CMIN


# ─── PURE MATH (no imports of the pipeline — safe offline) ──────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [−1, 1]; 0.0 for empty/mismatched/zero vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    ma = math.sqrt(sum(x * x for x in a))
    mb = math.sqrt(sum(y * y for y in b))
    if ma < 1e-9 or mb < 1e-9:
        return 0.0
    return dot / (ma * mb)


def tension_shift(baseline_tension: float, candidate_tension: float) -> float:
    """Absolute change in total tension between baseline and candidate runs."""
    return abs(float(candidate_tension) - float(baseline_tension))


def verdict_from_metrics(t_shift: float, coherence: float) -> bool:
    """True = PASS (change is acceptable), False = FAIL (degraded).

    A trial prompt fails if EITHER metric breaches its threshold:
      tension shifted too much  (> G2_SANDBOX_TENSION_SHIFT_MAX)
      OR consensus rotated/lost direction (< G2_SANDBOX_CONSENSUS_COHERENCE_MIN)
    """
    return (t_shift <= G2_SANDBOX_TENSION_SHIFT_MAX
            and coherence >= G2_SANDBOX_CONSENSUS_COHERENCE_MIN)


# ─── CANDIDATE BIAS WAVE (the "apply the change" lever, no LLM calls) ────────

def _aggregate_bias(contents: list[dict], now_ts: float | None = None,
                    half_life_weeks: float = 4.0):
    """Aggregate a list of committed entries into one bias wave.

    Mirrors memory.load_g2_bias_wave() EXACTLY (same decay weights, same unit-
    direction normalization) but takes `contents` as a parameter instead of
    reading g2_selfmodel.json from disk — so we can compute the CANDIDATE wave
    (current contents + proposed entry) without touching live state.

    VECTORS USED HERE: each entry's 384-dim SEMANTIC embedding under key "vec"
    (written by memory.summarize_session_for_g2 for session-summary entries).
    This is deliberately NOT the same as `vector_position` — that is a short
    spatial delta used by ring_buffer candidates to describe how much the
    self-model shifts in 3D space; it is not a semantic embedding and must not
    be fed into this aggregation. Entries without a usable "vec" are skipped.
    Returns (unit_dir, amplitude) or None if nothing usable.
    """
    now_ts = time.time() if now_ts is None else now_ts
    acc = None
    total_weight = 0.0
    for entry in contents:
        vec = entry.get("vec") if isinstance(entry, dict) else None
        if not vec or len(vec) == 0:
            continue
        ts = float(entry.get("ts", now_ts))
        age_weeks = max(0.0, (now_ts - ts) / (7 * 24 * 3600))
        w = math.pow(2.0, -age_weeks / half_life_weeks) if half_life_weeks > 0 else 1.0
        acc = [x * w for x in vec] if acc is None else \
              [a + (b * w) for a, b in zip(acc, vec)]
        total_weight += w

    if not acc or total_weight <= 1e-9:
        return None
    n = math.sqrt(sum(x * x for x in acc)) or 1.0
    unit = [x / n for x in acc]
    # Same fixed low-amplitude scale the real bias wave uses.
    # memory.py owns G2_BIAS_AMPLITUDE (memory-layer tunable). Lazy import so
    # this function stays callable in isolated contexts; hard-coded fallback
    # matches memory.G2_BIAS_AMPLITUDE's documented value of 0.15.
    try:
        from memory import G2_BIAS_AMPLITUDE as _AMP
    except Exception:  # pragma: no cover — isolated-context fallback
        _AMP = 0.15
    return (unit, float(_AMP))


def candidate_bias_wave(entry: dict, g2_path: str | None = None,
                        now_ts: float | None = None):
    """Compute the bias wave AS IF `entry` were already committed to contents.

    entry must carry a 384-dim SEMANTIC embedding under key "vec" (the session
    summarizer writes this for contents-style entries). If it doesn't, there is
    no measurable behavioral effect yet — return None and let the caller treat
    that as PASS-with-note.

    NOTE: ring_buffer candidates created by g2_ops.g2_add_candidate store their
    vector under "vector_position" (a short spatial delta), NOT "vec". Those
    entries will always hit this early-return HERE — but try_candidate() is
    responsible for synthesizing a semantic vec from the entry's text before
    calling this function, so in practice ring-buffer candidates DO get trialed.
    See try_candidate()'s _synthesize_vec_if_needed helper.
    """
    if not (isinstance(entry, dict) and entry.get("vec")):
        return None
    data = _load_g2(g2_path)
    contents = list(data.get("contents", [])) + [entry]
    try:
        import constants as C
        hl = float(getattr(C, "G2_DECAY_HALF_LIFE_WEEKS", 4.0) or 4.0)
    except Exception:
        hl = 4.0
    return _aggregate_bias(contents, now_ts=now_ts, half_life_weeks=hl)


def _load_g2(path: str | None = None) -> dict:
    p = path or _G2_PATH
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ─── THE TRIAL (lazy pipeline imports — OFF path never touches them) ────────

def _synthesize_vec_if_needed(entry: dict,
                              embed_fn=None) -> tuple[dict, list[str]]:
    """Return (entry_maybe_with_vec, notes).

    If `entry` already carries a usable 384-dim "vec", return it unchanged.
    Otherwise, if it has text and an embedding function is available, embed the
    text ONCE and attach the result to a SHALLOW COPY of the entry (the caller's
    dict is never mutated). If embedding fails or no text is present, return the
    original entry plus a note so the caller can fall through to its existing
    "no vec → PASS-with-note" path with full auditability.

    Why a copy: try_candidate may be called on live ring_buffer entries; we must
    not write a derived field back into the persisted state.
    """
    notes: list[str] = []
    if isinstance(entry, dict) and entry.get("vec"):
        return entry, notes

    text = (entry or {}).get("text", "") if isinstance(entry, dict) else ""
    if not text or embed_fn is None:
        notes.append("Entry carries no 384-dim vec and no text to embed — nothing "
                     "for the pipeline to feel yet. Treated as PASS (no measurable "
                     "effect); commit proceeds on the moons' verdict alone.")
        return entry, notes

    try:
        vec = list(embed_fn(text))
    except Exception as exc:  # embedding endpoint down / timeout / bad response
        notes.append(f"Entry has text but no vec, and embedding it failed "
                     f"({type(exc).__name__}: {exc}). Treated as PASS-with-note; "
                     "no behavioral trial possible. Commit proceeds on the moons' "
                     "verdict alone.")
        return entry, notes
    if not vec or len(vec) == 0:
        notes.append("Entry has text but embedding returned an empty vector — "
                     "treated as PASS-with-note; no behavioral trial possible.")
        return entry, notes

    enriched = dict(entry)
    enriched["vec"] = vec
    notes.append(f"Synthesized 384-dim semantic vec from entry text via local "
                 f"embedder (dim={len(vec)}). Trial proceeds on the synthesized "
                 f"wave; original ring_buffer entry is NOT mutated.")
    return enriched, notes


def try_candidate(entry: dict, trial_prompts: list[str] | None = None,
                  g2_path: str | None = None,
                  embed_fn=None) -> dict:
    """Run the before/after sandbox trial for one ring_buffer candidate.

    Args:
        entry: a G2 ring_buffer OR contents-style entry (dict).
            - If it carries a 384-dim semantic "vec", that is used directly.
            - Otherwise, if it has text and `embed_fn` is provided (or the
              default local embedder is reachable), a vec is synthesized ONCE
              from the text and attached to a copy of the entry — the live
              ring_buffer record is never mutated. This is what makes the
              sandbox actually trial real g2_add_candidate() outputs, which
              store their vector under "vector_position" (a spatial delta) and
              do NOT carry a semantic vec.
            - If neither path yields a usable vec, returns PASS-with-note so
              the commit can proceed on the moons' verdict alone.
        trial_prompts: prompts to run through the pipeline. Defaults to the
               sandbox's own list in g2_selfmodel.json ("sandbox.trial_prompts");
               if that is also empty, falls back to 3 built-in representative
               prompts (agreement / opposition / moral-dilemma).
        g2_path: optional override of the G2 state file (used by self-tests).
        embed_fn: callable(text) -> list[float]. Defaults to resonance.embed
               (local LM Studio MiniLM, with retry/backoff). Pass a stub in
               tests to keep the self-test offline.

    Returns a report dict:
        {
            "status": "passed" | "failed" | "skipped",
            "entry_id": str,
            "prompts_run": int,
            "per_prompt": [ {"prompt":..., "tension_baseline":..., "tension_candidate":...,
                             "tension_shift":..., "coherence":..., "passed": bool}, ... ],
            "overall_tension_shift_max": float,
            "overall_coherence_min": float,
            "notes": [...],
        }

    OFFLINE-SAFE: when G2_SANDBOX_ENABLED is False this returns immediately with
    status="skipped" and makes ZERO pipeline/embedding calls (no import of
    collapse, memory, or resonance either).
    """
    eid = entry.get("id", "<no-id>") if isinstance(entry, dict) else "<bad-entry>"

    # ── MASTER TOGGLE FIRST — no imports, no calls, just a report ────────────
    if not G2_SANDBOX_ENABLED:
        return {
            "status": "skipped",
            "reason": "sandbox disabled (G2_SANDBOX_ENABLED=False)",
            "entry_id": eid,
            "prompts_run": 0,
        }

    notes = []

    # ── Synthesize a semantic vec if the entry doesn't already carry one ─────
    # This is what makes real ring_buffer candidates (which store their vector
    # under "vector_position", a spatial delta) actually triable. Lazy-import
    # resonance only when we need it, so the OFF path stays import-free.
    if embed_fn is None:
        try:
            from resonance import embed as _default_embed   # lazy: OFF-safe
            embed_fn = _default_embed
        except Exception:
            embed_fn = None  # let the helper fall through to PASS-with-note
    entry, synth_notes = _synthesize_vec_if_needed(entry, embed_fn=embed_fn)
    notes.extend(synth_notes)

    # ── Resolve trial prompts ────────────────────────────────────────────────
    if not trial_prompts:
        try:
            data = _load_g2(g2_path)
            configured = (data.get("sandbox", {}) or {}).get("trial_prompts") or []
            trial_prompts = list(configured)[:G2_SANDBOX_TRIAL_PROMPTS]
        except Exception:
            trial_prompts = []
    if not trial_prompts:
        # Built-in representatives (mirrors test_multi.py scenario shapes).
        trial_prompts = [
            "Please give me a clear, well-ordered, step-by-step analysis with solid evidence.",   # agreement
            "We should tear down the existing rules and break everything to start over from scratch.",  # opposition
            "Is it ever right to tell someone a painful truth that will hurt them but save them later?",  # moral dilemma
        ][:G2_SANDBOX_TRIAL_PROMPTS]

    # ── Baseline bias wave (current committed contents, no new candidate) ────
    import memory as _memory            # lazy: OFF path never imports this
    baseline_wave = _memory.load_g2_bias_wave(g2_path=g2_path) if g2_path else \
                    _memory.load_g2_bias_wave()

    # ── Candidate bias wave (contents + proposed entry) ──────────────────────
    candidate_wave = candidate_bias_wave(entry, g2_path=g2_path)
    if candidate_wave is None:
        # Only reachable now when synthesis also failed (no vec AND no usable
        # text/embed). The synth path already appended a specific note above.
        notes.append("No usable 384-dim semantic vec after synthesis — nothing "
                     "for the pipeline to feel. Treated as PASS (no measurable "
                     "effect); commit proceeds on the moons' verdict alone.")
        return {
            "status": "passed",
            "entry_id": eid,
            "prompts_run": 0,
            "per_prompt": [],
            "overall_tension_shift_max": 0.0,
            "overall_coherence_min": 1.0,
            "notes": notes,
        }

    # ── Run each prompt through the live pipeline, with and without change ───
    from collapse import run_collapse   # lazy: OFF path never imports this
    per_prompt = []
    for prompt in trial_prompts:
        try:
            base_out = run_collapse(prompt, g2_bias_vector=baseline_wave)
            cand_out = run_collapse(prompt, g2_bias_vector=candidate_wave)
            b_res = base_out["result"]
            c_res = cand_out["result"]

            t_shift = tension_shift(b_res.get("tension", 0.0), c_res.get("tension", 0.0))
            coh = cosine_similarity(b_res.get("consensus_vector") or [],
                                    c_res.get("consensus_vector") or [])
            per_prompt.append({
                "prompt": prompt[:80],
                "tension_baseline": b_res.get("tension"),
                "tension_candidate": c_res.get("tension"),
                "tension_shift": round(t_shift, 6),
                "coherence": round(coh, 6),
                "passed": bool(verdict_from_metrics(t_shift, coh)),
            })
        except Exception as exc:
            per_prompt.append({
                "prompt": prompt[:80],
                "error": f"{type(exc).__name__}: {exc}",
                "passed": False,   # a pipeline failure is NOT a pass
            })

    # ── Overall verdict ──────────────────────────────────────────────────────
    shifts = [p["tension_shift"] for p in per_prompt if "tension_shift" in p]
    cohs = [p["coherence"] for p in per_prompt if "coherence" in p]
    overall_ok = bool(per_prompt) and all(p.get("passed") for p in per_prompt)

    return {
        "status": "passed" if overall_ok else "failed",
        "entry_id": eid,
        "prompts_run": len(trial_prompts),
        "per_prompt": per_prompt,
        "overall_tension_shift_max": round(max(shifts), 6) if shifts else 0.0,
        "overall_coherence_min": round(min(cohs), 6) if cohs else 1.0,
        "notes": notes,
    }


# ─── FUTURE SCAFFOLD: multi-day simulation (INERT — not implemented yet) ─────

def g2_sandbox_multiday(entry: dict, days: int = 7,
                        sessions_per_day: int = 3) -> dict:
    """SCAFFOLD ONLY — the planned full multi-day simulation upgrade.

    The single-turn before/after diff (try_candidate above) answers "does this
    change degrade one live pipeline run?". A multi-day sim would additionally
    answer "what does this do to trajectories over days/weeks?" by replaying N
    synthetic sessions through the pipeline with and without the candidate and
    comparing tension means, consensus-direction walk length, and per-planet
    amplitude stability.

    It is NOT implemented (deliberately — see Build Plan.md future-updates note:
    simulated sessions would be hallucinated scenarios; real multi-day evidence
    should come from real session logs once the system has been running). This
    stub exists so the call site and report shape are already defined, making a
    later implementation a fill-in rather than a redesign.
    """
    return {
        "status": "not_implemented",
        "reason": ("Multi-day simulation is a documented future upgrade (see "
                   "Build Plan.md, Phase 7 future-updates). Use try_candidate() "
                   "for the single-turn before/after diff in the meantime."),
        "entry_id": entry.get("id", "<no-id>") if isinstance(entry, dict) else None,
        "planned_days": days,
        "planned_sessions_per_day": sessions_per_day,
    }


# ─── SELF-TEST (offline — zero LLM/embedding calls; no LM Studio needed) ─────

def _self_test() -> None:
    import tempfile, shutil

    print("=" * 60)
    print("g2_sandbox.py — Phase 7 Segment 4 self-test (G2 Sandbox)")
    print("=" * 60)

    failures = []

    def check(label: str, cond: bool):
        tag = "PASS" if cond else "FAIL"
        print(f"  [{tag}] {label}")
        if not cond:
            failures.append(label)

    # ── [1] TOGGLE-OFF PATH: skipped with zero pipeline imports ──────────────
    # (Module-level name is mutated via globals() so no `global` statement is
    # needed inside this function; restored in the finally block.)
    saved_enabled = G2_SANDBOX_ENABLED
    try:
        globals()["G2_SANDBOX_ENABLED"] = False   # dev default — force it for the test

        entry_off = {"id": "off1", "text": "test change",
                     "vec": [0.1] * 384, "ts": time.time()}
        rep_off = try_candidate(entry_off)
        check("[1a] Toggle OFF: status=skipped", rep_off["status"] == "skipped")
        check("[1b] Toggle OFF: zero prompts run", rep_off.get("prompts_run", -1) == 0)
        check("[1c] Toggle OFF: reason mentions disabled",
              "disabled" in rep_off.get("reason", "").lower())

        # Prove the pipeline was never imported by this path.
        _pre = set(sys.modules)
        try_candidate(entry_off)   # run again to be sure nothing lazy-loads
        _new_mods = set(sys.modules) - _pre
        check("[1d] Toggle OFF: no new pipeline modules loaded (collapse/memory not imported fresh)",
              "collapse" not in _new_mods and not any(m.startswith("giants.") for m in _new_mods))
    finally:
        globals()["G2_SANDBOX_ENABLED"] = saved_enabled

    # ── [2] PURE MATH: cosine_similarity ─────────────────────────────────────
    check("[2a] cos(identical) ≈ 1.0", abs(cosine_similarity([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-9)
    check("[2b] cos(opposite) ≈ −1.0", abs(cosine_similarity([1, 2, 3], [-1, -2, -3]) + 1.0) < 1e-9)
    check("[2c] cos(orthogonal) = 0.0", cosine_similarity([1, 0], [0, 1]) == 0.0)
    check("[2d] cos(mismatched dims) = 0.0", cosine_similarity([1, 2], [1, 2, 3]) == 0.0)
    check("[2e] cos(zero vector) = 0.0", cosine_similarity([0, 0, 0], [1, 1, 1]) == 0.0)

    # ── [3] PURE MATH: tension_shift ────────────────────────────────────────
    check("[3a] shift(2.0, 2.5) = 0.5", abs(tension_shift(2.0, 2.5) - 0.5) < 1e-9)
    check("[3b] shift is symmetric", abs(tension_shift(2.5, 2.0) - tension_shift(2.0, 2.5)) < 1e-9)
    check("[3c] shift identical = 0.0", tension_shift(1.7, 1.7) == 0.0)

    # ── [4] VERDICT LOGIC (unit-level, no pipeline) ─────────────────────────
    check("[4a] small shift + high coherence → PASS",
          verdict_from_metrics(t_shift=0.05, coherence=0.95) is True)
    check("[4b] huge tension shift → FAIL even if coherent",
          verdict_from_metrics(t_shift=0.80, coherence=1.0) is False)
    check("[4c] low coherence → FAIL even if tension stable",
          verdict_from_metrics(t_shift=0.0, coherence=0.30) is False)
    check("[4d] exactly at thresholds → PASS (<= and >= are inclusive)",
          verdict_from_metrics(t_shift=G2_SANDBOX_TENSION_SHIFT_MAX,
                               coherence=G2_SANDBOX_CONSENSUS_COHERENCE_MIN) is True)

    # ── [5] _aggregate_bias: synthetic entries, no disk, no LLM ─────────────
    now = time.time()
    e_a = {"vec": [1.0, 0.0, 0.0], "ts": now}          # fresh → weight ≈ 1
    e_b = {"vec": [2.0, 0.0, 0.0], "ts": now - 7 * 86400}   # ~1 week old (hl=4wk → w≈0.707)
    wave = _aggregate_bias([e_a, e_b], now_ts=now, half_life_weeks=4.0)
    check("[5a] Two same-direction entries: unit dir points +x",
          wave is not None and abs(wave[0][0] - 1.0) < 1e-9)
    # Check amplitude scale against the canonical value (imported inside
    # _aggregate_bias itself — importing memory here would make check [1d]
    # meaningless, so read the constant indirectly).
    _G2AMP = getattr(__import__("constants"), "G2_BIAS_AMPLITUDE", None)
    if _G2AMP is not None and wave is not None:
        check("[5b] Bias wave uses the standard low-amplitude scale",
              abs(wave[1] - float(_G2AMP)) < 1e-9)

    # Entry without a vec is skipped entirely.
    e_novec = {"text": "no vector yet"}
    wave2 = _aggregate_bias([e_a, e_novec], now_ts=now, half_life_weeks=4.0)
    check("[5c] Vec-less entry ignored: dir still +x",
          wave2 is not None and abs(wave2[0][0] - 1.0) < 1e-9)

    # Opposing entries partially cancel → direction moves toward the stronger one.
    e_c = {"vec": [-3.0, 0.0, 0.0], "ts": now}         # fresh and heavier than e_a
    wave3 = _aggregate_bias([e_a, e_c], now_ts=now, half_life_weeks=4.0)
    check("[5d] Opposing entries: net dir flips to the stronger (−x)",
          wave3 is not None and wave3[0][0] < 0)

    # All-skipped → None.
    check("[5e] No usable vecs at all → None", _aggregate_bias([{"text": "x"}], now_ts=now) is None)

    # ── [6] candidate_bias_wave: entry without a vec → None (pass-with-note path) ──
    tmpdir = tempfile.mkdtemp(prefix="g2_sb_test_")
    test_path = os.path.join(tmpdir, "g2_selfmodel.json")
    try:
        shutil.copy(_G2_PATH, test_path)

        plain = {"id": "t6", "text": "a note with no vector", "status": "pending"}
        check("[6a] candidate_bias_wave(plain entry) → None",
              candidate_bias_wave(plain, g2_path=test_path) is None)

        # ── [6b-H5] _synthesize_vec_if_needed: the H5 fix path ─────────────
        # A ring-buffer-style entry (vector_position set, no "vec") should get a
        # synthesized vec attached to a COPY when an embed_fn is supplied.
        rb_entry = {"id": "h5rb", "text": "a proposed structural change",
                    "vector_position": [0.1, -0.2, 0.3],
                    "mass": 0.3, "tier": 1, "status": "pending"}
        _orig_id = rb_entry.get("id")
        stub_vec = [0.7] * 384
        calls: list[str] = []
        def _stub_embed(text: str):
            calls.append(text)
            return list(stub_vec)
        enriched, syn_notes = _synthesize_vec_if_needed(rb_entry, embed_fn=_stub_embed)
        check("[6b-H5a] Ring-buffer entry (no vec) gets a synthesized vec",
              isinstance(enriched, dict) and len(enriched.get("vec", [])) == 384)
        check("[6b-H5b] Synthesized vec attached to a COPY — original not mutated",
              "vec" not in rb_entry and enriched is not rb_entry
              and enriched.get("id") == _orig_id
              and enriched.get("vector_position") == [0.1, -0.2, 0.3])
        check("[6b-H5c] Embedder was called exactly once with the entry's text",
              calls == ["a proposed structural change"])
        check("[6b-H5d] Synthesis note explains what happened (auditable)",
              any("Synthesized 384-dim" in n for n in syn_notes))

        # Entry that already has a vec: returned unchanged, no embed call.
        already = {"id": "h5has", "vec": [0.1] * 384, "text": "ignore me"}
        calls.clear()
        enriched2, syn_notes2 = _synthesize_vec_if_needed(already, embed_fn=_stub_embed)
        check("[6b-H5e] Entry with existing vec is returned unchanged",
              enriched2 is already and not calls and not syn_notes2)

        # Entry with text but embed raises → fall through to PASS-with-note path.
        def _bad_embed(text: str):
            raise RuntimeError("LM Studio down")
        rb_fail = {"id": "h5fail", "text": "some text", "vector_position": [0.1, 0.2, 0.3]}
        enriched3, syn_notes3 = _synthesize_vec_if_needed(rb_fail, embed_fn=_bad_embed)
        check("[6b-H5f] Embed failure → original entry returned (no vec added)",
              "vec" not in rb_fail and enriched3 is rb_fail)
        check("[6b-H5g] Embed failure note is recorded for audit",
              any("embedding it failed" in n for n in syn_notes3))

        # Entry with no text AND no vec → PASS-with-note, no embed call.
        calls.clear()
        bare = {"id": "h5bare", "status": "pending"}
        enriched4, syn_notes4 = _synthesize_vec_if_needed(bare, embed_fn=_stub_embed)
        check("[6b-H5h] No-text entry: no embed call, note recorded",
              not calls and "vec" not in bare
              and any("no text to embed" in n for n in syn_notes4))

        # ── [6c-H5] try_candidate end-to-end with a stubbed embedder (OFFLINE) ──
        # Prove the H5 fix actually lets a real ring-buffer candidate be trialed:
        # toggle ON, monkeypatch collapse.run_collapse so no LM call happens,
        # feed a vector_position-only entry → expect prompts_run > 0 and the
        # synthesized-vec note present in the report.
        import types
        saved_enabled2 = G2_SANDBOX_ENABLED
        fake_collapse_mod = types.ModuleType("collapse")
        _call_count = {"n": 0}
        def _fake_run_collapse(prompt, g2_bias_vector=None):
            _call_count["n"] += 1
            # Deterministic: tension and consensus depend on the bias wave so that
            # baseline vs candidate differ measurably.
            amp = (g2_bias_vector or ([0.0] * 384, 0.15))[1]
            return {"result": {"tension": round(amp, 6),
                               "consensus_vector": [1.0, 0.0, 0.0]}}
        fake_collapse_mod.run_collapse = _fake_run_collapse
        real_collapse = sys.modules.get("collapse")
        saved_embed_fn_default = None  # we pass embed_fn explicitly below; no global swap needed
        try:
            globals()["G2_SANDBOX_ENABLED"] = True
            sys.modules["collapse"] = fake_collapse_mod   # shadow the real one for this test

            rb_live = {"id": "h5live", "text": "a live ring-buffer candidate",
                       "vector_position": [0.1, -0.2, 0.3],
                       "mass": 0.3, "tier": 1, "status": "pending"}
            report = try_candidate(rb_live,
                                   trial_prompts=["p1", "p2", "p3"],
                                   g2_path=test_path,
                                   embed_fn=_stub_embed)
            check("[6c-H5a] Ring-buffer candidate now actually TRIED (prompts_run>0)",
                  report.get("status") in ("passed", "failed")
                  and report.get("prompts_run", 0) == 3
                  and len(report.get("per_prompt", [])) == 3)
            check("[6c-H5b] Report notes include the synthesis explanation",
                  any("Synthesized 384-dim" in n for n in report.get("notes", [])))
            check("[6c-H5c] run_collapse was called (baseline + candidate per prompt)",
                  _call_count["n"] == 6)   # 3 prompts × 2 runs
        finally:
            globals()["G2_SANDBOX_ENABLED"] = saved_enabled2
            if real_collapse is not None:
                sys.modules["collapse"] = real_collapse
            else:
                sys.modules.pop("collapse", None)

        # Entry WITH a vec produces the same direction as _aggregate_bias(contents+[entry]).
        v = [0.5, -0.3, 0.2]
        ent_vec = {"id": "t7", "vec": v, "ts": time.time(), "status": "pending"}
        cw = candidate_bias_wave(ent_vec, g2_path=test_path)
        expected_dir = _aggregate_bias(
            list(_load_g2(test_path).get("contents", [])) + [ent_vec], now_ts=time.time())
        if cw is not None and expected_dir is not None:
            check("[6b] candidate wave matches manual aggregation (cos ≈ 1)",
                  abs(cosine_similarity(cw[0], expected_dir[0]) - 1.0) < 1e-9)
        else:
            # Live contents may be empty → both should still agree on None-or-dir.
            check("[6b] candidate wave consistent with aggregation (both present or both absent)",
                  (cw is not None) == (expected_dir is not None))

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ── [7] MULTIDAY SCAFFOLD: inert by design ──────────────────────────────
    rep_md = g2_sandbox_multiday({"id": "md1"}, days=7)
    check("[7a] Multiday scaffold returns not_implemented",
          rep_md["status"] == "not_implemented")
    check("[7b] Scaffold points to the documented upgrade path",
          "Build Plan" in rep_md.get("reason", ""))

    # ── [8] CONSTANTS WIRING: module values match constants.py (single source) ──
    try:
        import constants as _C
        check("[8a] G2_SANDBOX_ENABLED matches constants",
              G2_SANDBOX_ENABLED == getattr(_C, "G2_SANDBOX_ENABLED"))
        check("[8b] Tension-shift threshold matches constants (0.30)",
              abs(G2_SANDBOX_TENSION_SHIFT_MAX - getattr(_C, "G2_SANDBOX_TENSION_SHIFT_MAX", 0.3)) < 1e-9)
        check("[8c] Coherence minimum matches constants (0.70)",
              abs(G2_SANDBOX_CONSENSUS_COHERENCE_MIN - getattr(_C, "G2_SANDBOX_CONSENSUS_COHERENCE_MIN", 0.7)) < 1e-9)
    except Exception as exc:
        check(f"[8x] constants import for wiring check ({exc})", False)

    # ── [9] LIVE TOGGLE STATE: report what the module currently sees ────────
    print(f"  (info) live G2_SANDBOX_ENABLED = {saved_enabled} "
          f"(dev default OFF; flip in constants.py for production)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if failures:
        print(f"g2_sandbox.py Segment 4 self-test: {len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print("g2_sandbox.py Segment 4 self-test: ALL PASS (G2 Sandbox, offline)")


if __name__ == "__main__":
    _self_test()
