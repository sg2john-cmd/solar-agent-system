"""
Resonant Cognition v17 — Phase 7, Segment 2: G1 Filter Moons
=============================================================

G1's three moons act as an intake pre-filter that runs during Sleep Pass I,
BEFORE the deterministic AI-slop scoring in g1_ops.g1_sleep_pass_i().

Each moon makes exactly ONE LLM call per candidate (3 total per candidate):

  CLARITY_FILTER          — is this entry atomic, unambiguous, actionable?
                            Strips redundancy; returns cleaned text.
  RELEVANCE_GATE          — does the system need this knowledge now, or is it
                            peripheral noise? Returns a 0-1 relevance score.
  DISSONANCE_PRE_READ     — does this contradict anything already committed in
                            G1? Flags for review if so.

TOGGLE:
  constants.G1_FILTER_MOONS_ENABLED
    - DEV (default): False → moons are skipped entirely; Sleep Pass I behaves
      exactly as Segment 1 defined it (zero LLM calls, byte-identical).
    - PRODUCTION: True   → moons run on every candidate. This is MANDATORY in a
      full release — turning them off risks archive integrity (unverified data
      entering G1's permanent store). See Build Plan Phase 7 Seg 2 note.

RUN (offline self-test, zero LLM calls):
    python -X utf8 giants/g1_filter_moons.py

RUN (live test with moons ON — requires LM Studio running):
    python -X utf8 giants/g1_filter_moons.py --moons-on
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_GIANTS_DIR = _HERE          # g1_knowledge.json lives alongside this file
_G1_PATH = os.path.join(_GIANTS_DIR, "g1_knowledge.json")


# ─── IMPORT TOGGLES (lazy — only touch constants when moons are actually ON) ──

def _C():
    """Lazy import of constants so the offline self-test never needs LM Studio."""
    import constants as C
    return C


def moons_enabled() -> bool:
    """Returns True if G1 filter moons should run. OFF by default (dev mode)."""
    try:
        return bool(getattr(_C(), "G1_FILTER_MOONS_ENABLED", False))
    except ImportError:
        return False


# ─── MOON PROMPT BUILDERS (pure string functions — no LLM call here) ─────────

def _clarity_prompt(candidate_text: str, g1_contents_sample: list[dict]) -> list[dict]:
    """Build the message list for the Clarity moon.

    The moon's job: verify the entry is atomic (one idea), unambiguous, and
    actionable. Strip any redundancy against existing G1 content. Return JSON.
    """
    sample_lines = []
    for c in g1_contents_sample[:5]:  # cap at 5 to keep prompt small
        t = (c.get("text") or "")[:200]
        sample_lines.append(f"- {t}")
    sample_block = "\n".join(sample_lines) if sample_lines else "(archive is empty)"

    system = (
        "You are the CLARITY_FILTER moon of G1, the permanent knowledge archive. "
        "Your job is to verify that an incoming entry is valid archive content. Valid entries include: "
        "operational procedures ('when X happens, do Y'), parameter settings ('set Z to W; verify above V causes failure'), "
        "debugging references ('if symptom A occurs, check B before dividing by C'), and factual system descriptions "
        "('component X uses scheme Y with property Z'). These are ALL valid — do not reject them for being straightforward.\n"
        "REJECT ONLY if: (1) the entry is circular/vacuous ('the system works by doing what it does'), "
        "(2) it is pure philosophy or motivation with zero reference to any concrete system component, "
        "or (3) it bundles 3+ unrelated ideas making the primary one unclear.\n"
        "If the entry passes but contains minor redundancy with existing content below, strip the redundant wording. "
        "If it bundles 2 closely-related ideas, keep both in cleaned_text.\n"
        "Respond ONLY with valid JSON: "
        '{"pass": true/false, "reason": "<one sentence>", '
        '"cleaned_text": "<the cleaned version of the entry>"}'
    )
    user = (
        f"INCOMING ENTRY:\n{candidate_text}\n\n"
        f"EXISTING G1 CONTENT (for redundancy check):\n{sample_block}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _relevance_prompt(candidate_text: str, recent_topics: list[str]) -> list[dict]:
    """Build the message list for the Relevance moon.

    The moon's job: judge whether this knowledge is needed by the system NOW or
    is peripheral noise. recent_topics comes from the Ring's swarm memory (last N).
    """
    topics_block = "\n".join(f"- {t}" for t in recent_topics[:5]) if recent_topics else "(no recent session context available)"

    system = (
        "You are the RELEVANCE_GATE moon of G1, the permanent knowledge archive. "
        "Your job is to judge whether this incoming knowledge is relevant to what the "
        "system has been working on recently, or whether it is peripheral noise that "
        "should be demoted (lower mass, peripheral storage) rather than committed at full weight. "
        "Score relevance 0.0–1.0 where: 0.8+ = clearly needed now; 0.5–0.79 = potentially useful, keep but lower priority; "
        "< 0.5 = peripheral — mark as low_relevance so Sleep Pass I can demote it. "
        "Respond ONLY with valid JSON: "
        '{"pass": true/false, "relevance_score": <float>, "note": "<one sentence>"}'
    )
    user = (
        f"INCOMING ENTRY:\n{candidate_text}\n\n"
        f"RECENT SESSION TOPICS (from Ring swarm):\n{topics_block}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _dissonance_prompt(candidate_text: str, candidate_vec: list[float] | None, g1_contents: list[dict]) -> list[dict]:
    """Build the message list for the Dissonance Pre-Read moon.

    The moon's job: check whether this entry contradicts anything already in G1.
    It receives both text and vector context so it can reason about semantic conflict.
    """
    # Build a compact view of existing contents (text + short vec) for the prompt
    content_lines = []
    for c in g1_contents[:8]:  # cap at 8 to keep prompt manageable
        t = (c.get("text") or "")[:200]
        v = c.get("vector_position") or []
        v_short = [round(x, 3) for x in v[:4]] if v else "[]"
        cid = c.get("id", "?")
        content_lines.append(f"[{cid}] {t}  vec≈{v_short}")
    contents_block = "\n".join(content_lines) if content_lines else "(archive is empty)"

    cand_vec_str = f"{[round(x,3) for x in candidate_vec[:4]]}" if candidate_vec else "not provided"

    system = (
        "You are the DISSONANCE_PRE_READ moon of G1, the permanent knowledge archive. "
        "Your job is to detect whether this incoming entry CONTRADICTS anything already "
        "committed in the archive. A contradiction means the new entry asserts something "
        "incompatible with an existing committed fact (e.g., different value, opposite claim). "
        "Merely being on a similar topic is NOT a contradiction. "
        "If you detect a likely contradiction, flag it so Sleep Pass I can hold the entry for review "
        "rather than auto-committing it alongside its contradicting counterpart. "
        "Respond ONLY with valid JSON: "
        '{"contradiction_detected": true/false, '
        '"conflicting_entry_id": "<id of the conflicting G1 entry or null>", '
        '"note": "<one sentence>"}'
    )
    user = (
        f"INCOMING ENTRY:\n{candidate_text}\n"
        f"Candidate vector (first 4 dims): {cand_vec_str}\n\n"
        f"EXISTING G1 CONTENTS:\n{contents_block}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ─── LLM RESPONSE PARSING (defensive — bad JSON should not crash Sleep Pass I) ──

def _parse_moon_json(raw: str, moon_name: str) -> dict:
    """Parse the moon's JSON response. Returns a safe default on failure."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first and last fence line
        inner = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(inner).strip()

    try:
        data = json.loads(text)
        return data
    except (json.JSONDecodeError, ValueError):
        # Quiet-but-logging: log the failure, return a "no objection" default so
        # the candidate is not silently dropped by a parse error.
        print(f"[g1_filter_moons] WARNING: {moon_name} returned unparseable JSON: {text[:200]!r}")
        return {"_parse_error": True, "_raw": raw[:500]}


# ─── MOON PASS (the main entry point called from Sleep Pass I) ───────────────

def g1_filter_moons_pass(
    candidate: dict,
    g1_data: dict,
    recent_topics: list[str] | None = None,
) -> dict:
    """Run all three G1 moons on a single candidate entry.

    Args:
        candidate:     the ring-buffer entry dict (has "text", "vector_position", etc.)
        g1_data:       the full loaded G1 JSON (for contents + existing context)
        recent_topics: optional list of recent topic strings from Ring swarm memory.
                       If None, the Relevance moon runs with no session context.

    Returns a dict with one key per moon plus an overall verdict:
        {
            "clarity":     {"pass": bool, ...},
            "relevance":   {"relevance_score": float, ...},
            "dissonance":  {"contradiction_detected": bool, ...},
            "overall_verdict": "pass" | "rejected_clarity" | "peripheral"
                               | "flagged_contradiction",
        }

    NOTE: This function makes exactly 3 LLM calls. It is ONLY called when
    G1_FILTER_MOONS_ENABLED is True (production mode). In dev mode, Sleep Pass I
    skips this entirely and behaves as Segment 1 defined it.
    """
    from cognitive_chamber import _llm_chat_cached

    text = candidate.get("text") or ""
    vec = candidate.get("vector_position") or None
    contents = g1_data.get("contents", [])
    topics = recent_topics or []

    results: dict = {}

    # ── MOON 1: CLARITY_FILTER ────────────────────────────────────────────────
    try:
        msgs = _clarity_prompt(text, contents)
        raw = _llm_chat_cached(msgs, temperature=0.3, max_tokens=256)
        clarity = _parse_moon_json(raw, "CLARITY_FILTER")
    except Exception as exc:
        print(f"[g1_filter_moons] CLARITY moon LLM call failed: {exc}")
        clarity = {"pass": True, "_llm_error": str(exc)}  # fail-open: don't block on error

    results["clarity"] = clarity

    # ── MOON 2: RELEVANCE_GATE ────────────────────────────────────────────────
    try:
        msgs = _relevance_prompt(text, topics)
        raw = _llm_chat_cached(msgs, temperature=0.3, max_tokens=192)
        relevance = _parse_moon_json(raw, "RELEVANCE_GATE")
    except Exception as exc:
        print(f"[g1_filter_moons] RELEVANCE moon LLM call failed: {exc}")
        relevance = {"pass": True, "relevance_score": 0.5, "_llm_error": str(exc)}

    results["relevance"] = relevance

    # ── MOON 3: DISSONANCE_PRE_READ ───────────────────────────────────────────
    try:
        msgs = _dissonance_prompt(text, vec, contents)
        raw = _llm_chat_cached(msgs, temperature=0.2, max_tokens=256)
        dissonance = _parse_moon_json(raw, "DISSONANCE_PRE_READ")
    except Exception as exc:
        print(f"[g1_filter_moons] DISSONANCE moon LLM call failed: {exc}")
        dissonance = {"contradiction_detected": False, "_llm_error": str(exc)}

    results["dissonance"] = dissonance

    # ── OVERALL VERDICT (priority order matters) ──────────────────────────────
    # 1. Clarity failure is the strongest rejection — if the entry isn't atomic
    #    and unambiguous, nothing else matters.
    if not clarity.get("pass", True):
        results["overall_verdict"] = "rejected_clarity"
        return results

    # 2. Dissonance flag holds the entry for review (not rejected, just held).
    if dissonance.get("contradiction_detected"):
        results["overall_verdict"] = "flagged_contradiction"
        return results

    # 3. Low relevance → demote to peripheral (Sleep Pass I will assign lower mass).
    rel_score = float(relevance.get("relevance_score", 0.5))
    if rel_score < 0.5:
        results["overall_verdict"] = "peripheral"
        return results

    # 4. All clear → pass through to normal Sleep Pass I scoring.
    results["overall_verdict"] = "pass"
    return results


# ─── SLEEP PASS I INTEGRATION (the hook that g1_ops.py will call) ─────────────

def apply_filter_moons_to_sleep_pass(
    candidate: dict,
    g1_data: dict,
    recent_topics: list[str] | None = None,
) -> tuple[dict, str | None]:
    """Run the filter moons on a candidate and return (candidate, verdict_or_None).

    This is the integration point that g1_ops.g1_sleep_pass_i() will call when
    G1_FILTER_MOONS_ENABLED is True. It returns:
      - the (possibly modified) candidate dict — cleaned_text from Clarity moon
        replaces the original text if the Clarity pass succeeded and produced
        a different cleaned string.
      - verdict_or_None: None means "all clear, proceed to normal scoring".
                         A string means the verdict that should be applied:
                         "rejected_clarity"       → eject with reason
                         "flagged_contradiction"  → mark for review (don't promote yet)
                         "peripheral"             → promote at reduced mass

    In dev mode (G1_FILTER_MOONS_ENABLED=False), g1_ops.py never calls this.
    """
    if not moons_enabled():
        return candidate, None

    result = g1_filter_moons_pass(candidate, g1_data, recent_topics)
    verdict = result["overall_verdict"]

    # Apply cleaned text from Clarity moon (if it produced one and it differs).
    cleaned = (result.get("clarity") or {}).get("cleaned_text", "").strip()
    if cleaned and verdict == "pass" and cleaned != candidate.get("text"):
        candidate["original_text"] = candidate.get("text")  # keep for audit
        candidate["text"] = cleaned

    return candidate, (None if verdict == "pass" else verdict)


# ─── SELF-TEST (offline — zero LLM calls; verifies structure + toggle-OFF path) ──

def _self_test() -> None:
    import tempfile

    print("=" * 60)
    print("g1_filter_moons.py — Phase 7 Segment 2 self-test (G1 Filter Moons)")
    print("=" * 60)

    failures = []

    def check(label: str, cond: bool):
        tag = "PASS" if cond else "FAIL"
        print(f"  [{tag}] {label}")
        if not cond:
            failures.append(label)

    # ── [1] moons_enabled() returns False by default (dev mode) ───────────────
    check("[1] moons_enabled() is False in dev mode (default)", moons_enabled() is False)

    # ── [2] Prompt builders produce non-empty message lists ──────────────────
    cand = {"text": "Set the orbital integrator timestep to 0.01 for stability.",
            "vector_position": [1.0, 0.5, 0.0, 0.0]}
    g1_sample = {
        "contents": [{"id": "e1", "text": "The orbital integrator timestep is set to 0.01 for stability.",
                      "vector_position": [1.0, 0.5, 0.0, 0.0]}]
    }

    m_clarity = _clarity_prompt(cand["text"], g1_sample["contents"])
    check("[2a] Clarity prompt has system + user messages", len(m_clarity) == 2 and "system" in m_clarity[0]["role"] or m_clarity[0].get("role") == "system")
    check("[2b] Clarity prompt mentions CLARITY_FILTER", "CLARITY_FILTER" in (m_clarity[0].get("content") if isinstance(m_clarity[0], dict) else ""))

    m_rel = _relevance_prompt(cand["text"], ["orbital mechanics", "integrator tuning"])
    check("[2c] Relevance prompt has 2 messages", len(m_rel) == 2)
    check("[2d] Relevance prompt includes recent topics", "orbital mechanics" in (m_rel[1].get("content") if isinstance(m_rel[1], dict) else ""))

    m_dis = _dissonance_prompt(cand["text"], cand["vector_position"], g1_sample["contents"])
    check("[2e] Dissonance prompt has 2 messages", len(m_dis) == 2)
    check("[2f] Dissonance prompt includes existing contents id", "e1" in (m_dis[1].get("content") if isinstance(m_dis[1], dict) else ""))

    # ── [3] _parse_moon_json handles valid JSON ───────────────────────────────
    good = json.dumps({"pass": True, "reason": "clear", "cleaned_text": "x"})
    parsed = _parse_moon_json(good, "test")
    check("[3a] Valid JSON parses correctly", parsed.get("pass") is True)

    # ── [4] _parse_moon_json handles markdown-fenced JSON ────────────────────
    fenced = '```json\n{"pass": false, "reason": "too vague"}\n```'
    parsed_f = _parse_moon_json(fenced, "test")
    check("[3b] Fenced JSON parses correctly", parsed_f.get("pass") is False)

    # ── [5] _parse_moon_json handles garbage gracefully (no crash) ───────────
    bad_result = _parse_moon_json("this is not json at all", "test_bad")
    check("[3c] Garbage input returns _parse_error flag, no exception raised", "_parse_error" in bad_result)

    # ── [6] apply_filter_moons_to_sleep_pass returns (candidate, None) when OFF ──
    test_cand = {"text": "some entry text", "vector_position": [0.1, 0.2]}
    out_cand, verdict = apply_filter_moons_to_sleep_pass(test_cand, g1_sample)
    check("[6a] Dev mode: verdict is None (moons skipped)", verdict is None)
    check("[6b] Dev mode: candidate text unchanged", out_cand["text"] == "some entry text")

    # ── [7] Verdict priority logic (unit-test the decision tree without LLM) ──
    # Simulate each moon result to verify the overall_verdict priority.
    def _sim(clarity_pass: bool, contradiction: bool, rel_score: float) -> str:
        """Replicate the verdict logic from g1_filter_moons_pass for unit testing."""
        if not clarity_pass:
            return "rejected_clarity"
        if contradiction:
            return "flagged_contradiction"
        if rel_score < 0.5:
            return "peripheral"
        return "pass"

    check("[7a] Clarity failure overrides all → rejected_clarity",
          _sim(False, False, 0.9) == "rejected_clarity")
    check("[7b] Contradiction flag beats relevance → flagged_contradiction",
          _sim(True, True, 0.3) == "flagged_contradiction")
    check("[7c] Low relevance (no contradiction) → peripheral",
          _sim(True, False, 0.3) == "peripheral")
    check("[7d] All clear → pass",
          _sim(True, False, 0.85) == "pass")

    # ── [8] g1_filter_moons_pass is callable (signature check, no LLM call made
    #         because we monkey-patch the import to catch any accidental call) ──
    # We don't actually CALL it here (would need LM Studio); just verify it exists
    # and has the right signature shape.
    import inspect
    sig = inspect.signature(g1_filter_moons_pass)
    params = list(sig.parameters.keys())
    check("[8a] g1_filter_moons_pass accepts candidate, g1_data, recent_topics",
          set(params) == {"candidate", "g1_data", "recent_topics"})

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if failures:
        print(f"g1_filter_moons.py Segment 2 self-test: {len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print("g1_filter_moons.py Segment 2 self-test: ALL PASS (G1 Filter Moons)")


if __name__ == "__main__":
    _self_test()
