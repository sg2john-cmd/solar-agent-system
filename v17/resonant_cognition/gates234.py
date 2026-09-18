"""
Resonant Cognition v17 — Phase 8 Segment 1: Gates 2, 3, and 4
=================================================================

Three small gate modules that complete the pipeline security layer:

GATE 2 — TRANSPARENCY LABEL (outbound)
    Appends a metadata label to every outbound response so the user can see
    which parts are AI-generated. Config-driven from gates_config.json → "transparency".
    Signature: gate2_label(text, direction="output") -> str

GATE 3 — SAFETY BLOCKLIST (input + output)
    Checks text against configured safety categories. For INPUT: blocks before
    embedding/chamber runs. For OUTPUT: suppresses the response and returns a
    refusal in the Ring's voice. Config-driven from gates_config.json → "safety_blocklist".
    Signature: gate3_safety_check(text, direction) -> (approved: bool, category: str|None)

GATE 4 — AUDIT LOGGING (all events)
    Structured append-only event log for every routing/resonance/gate/sleep decision.
    Writes JSONL to audit_log.jsonl in the package root. Config-driven from
    gates_config.json → "audit_log".
    Signature: gate4_log(event_type, payload, **context)

DESIGN PRINCIPLES (shared with gate1.py):
  - READ-ONLY on config (loaded once at import)
  - NEVER raises — returns safe defaults on errors
  - All behavior is toggle-gated via gates_config.json; disabled = pass-through
  - Zero LLM calls in any of these three gates

RUN A SANITY CHECK:  python -X utf8 gates234.py
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _HERE)


# ─── CONFIG (shared with gate1 but loaded independently to keep modules self-contained) ──

def _default_gates_config() -> dict:
    """Safe fallback config used when gates_config.json is missing/corrupt.

    Mirrors the on-disk keys that gate2/gate3/gate4 read, but with every safety
    control set to a FAIL-OPEN posture: nothing crashes at import. Note Gate 4
    (audit) defaults enabled=True here — matching both live config and its own
    docstring — since audit logging is non-blocking by design and disabled would
    silently drop the compliance trail.
    """
    return {
        "pii": {
            "enabled": False,
            "patterns": [],
            "replacement_token": "[REDACTED]",
            "store_raw": False,
        },
        "safety_blocklist": {
            "enabled": True,                 # keep the blocklist active even on fallback
            "categories": [
                {"name": "wmd_recipes", "severity": "hard"},
                {"name": "active_harm_instructions", "severity": "hard"},
                {"name": "non_consensual_real_person_content", "severity": "hard"},
            ],
            "pre_injection_check": True,
            "post_generation_check": True,
            "refusal_voice": "ring",
        },
        "transparency": {
            "enabled": False,                # don't inject labels on fallback
            "mode": "metadata",
            "label_text": "[AI-Generated: Resonant Cognition v17]",
        },
        "audit_log": {
            "enabled": True,
            "retention_days": 90,
            "log_level": "full",
            "halt_enabled": False,
        },
    }


def _load_gates_config() -> dict:
    """Load gates_config.json ONCE at import. NEVER raises.

    H1 fix (independent review): the original bare open()/json.load() meant a
    missing or corrupt gates_config.json crashed the ENTIRE pipeline at module
    import, violating this module's 'NEVER raises' contract. Now any I/O or JSON
    error logs a warning and returns safe defaults so the system stays up.
    """
    path = os.path.join(_HERE, "gates_config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Guarantee the top-level keys exist even if a partial file is present.
        defaults = _default_gates_config()
        for key, val in defaults.items():
            data.setdefault(key, val)
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        import sys
        print(f"[GATES234] WARN: could not load {path} ({e.__class__.__name__}); "
              f"using safe defaults. The pipeline will keep running.", file=sys.stderr)
        return _default_gates_config()


_GATES = _load_gates_config()


# ═══════════════════════════════════════════════════════════════════════════════
# GATE 2 — TRANSPARENCY LABEL
# ═══════════════════════════════════════════════════════════════════════════════

def gate2_label(text: str, direction: str = "output") -> str:
    """Apply the transparency label to outbound text.

    If transparency is enabled and mode == "metadata", appends the label_text
    as a trailing line. If mode == "prepend", prepends it. If disabled, returns
    text unchanged. Only applies to direction="output" (inbound text gets no label).
    """
    cfg = _GATES.get("transparency", {})
    if not cfg.get("enabled", False) or direction != "output":
        return text

    mode = cfg.get("mode", "metadata")
    label = cfg.get("label_text", "[AI-Generated]")

    if mode == "prepend":
        return f"{label} {text}"
    else:  # "metadata" — append as a separate line
        return f"{text}\n\n{label}"


# ═══════════════════════════════════════════════════════════════════════════════
# GATE 3 — SAFETY BLOCKLIST
# ═══════════════════════════════════════════════════════════════════════════════

def gate3_safety_check(text: str, direction: str = "input") -> tuple[bool, str | None]:
    """Check text against the safety blocklist.

    For INPUT (direction="input"): checks BEFORE embedding/chamber runs.
        If blocked, the pipeline should short-circuit and return a refusal.
    For OUTPUT (direction="output"): checks AFTER chamber generates a response.
        If blocked, the response is suppressed and replaced with a refusal voice.

    Returns:
        (approved: bool, blocked_category: str | None)
        approved=True means the text passed; category is None.
        approved=False means it was blocked; category names which rule fired.

    Current implementation uses keyword/pattern heuristics per category.
    In production this could be extended with an LLM classifier, but for v17
    the deterministic patterns keep latency at zero and behavior predictable.
    """
    cfg = _GATES.get("safety_blocklist", {})
    if not cfg.get("enabled", False):
        return True, None

    # Direction gating: pre_injection_check covers input; post_generation_check covers output
    if direction == "input" and not cfg.get("pre_injection_check", True):
        return True, None
    if direction == "output" and not cfg.get("post_generation_check", True):
        return True, None

    categories = cfg.get("categories", [])
    for cat in categories:
        name = cat.get("name", "")
        severity = cat.get("severity", "hard")
        # Only enforce "hard" severity blocks; "soft" would be a warning (future)
        if severity != "hard":
            continue

        blocked, _matched = _check_category(text, name)
        if blocked:
            return False, name

    return True, None


# SAFETY PATTERN DESIGN NOTE (2026-09-17, Phase 8 Segment 5 pre-flight):
# John's decision: keep Gate 3's INPUT check deliberately CONSERVATIVE — a fixed,
# predictable phrase list that catches the obvious cases without over-blocking
# educational/historical discussion. Do NOT try to regex-predict every possible
# reworded phrasing of a harmful request at input time; that proved both fragile
# (a Windows shell mangled backslash escapes in inline tests, so patterns "tested"
# green were actually corrupt) and over-strict (risked false-positives like
# "apple bomb pastries" or WW2 history). The real intent-based safety net is the
# two-layer architecture John specified:
#
#   User Prompt ──► [ Input Filter ] ──► [ Planetary Pipeline ] ──► [ Output Filter ] ──► User Response
#                     (Pass/Fail)        (Superego/Jester/etc.)      (Sanity Check)
#
# i.e. if a reworded harmful request slips past the input list, it still goes through
# Phase C (per-planet Superego regulatory review against Core Laws) AND the output-side
# Gate 3 pass (post_generation_check), which sees the *generated* response — intent
# realized, not just words. That output-side check is where "intent" matching belongs.
# See docs/ for the follow-up segment that strengthens the OUTPUT filter accordingly.

def _check_category(text: str, category: str) -> tuple[bool, str]:
    """Deterministic pattern check for a safety category.

    Returns (blocked: bool, matched_phrase: str).
    Patterns are conservative — designed to catch obvious violations without
    false-positiving on educational/philosophical discussion. See the design note
    above: this is the INPUT-side first pass; intent-based catching happens at Phase C
    and the OUTPUT-side Gate 3 check, not by over-engineering this phrase list.
    """
    t = text.lower()

    if category == "wmd_recipes":
        # Look for explicit weapon construction intent combined with specific components
        wmd_intents = ["how to build a bomb", "make a nuclear weapon", "construct a thermobaric",
                       "assemble an ied", "build a dirty bomb", "create a chemical weapon"]
        for phrase in wmd_intents:
            if phrase in t:
                return True, phrase

    elif category == "active_harm_instructions":
        # Explicit instructions to harm specific people or self-harm with method+intent
        harm_patterns = [
            "how do i kill", "instructions for murder", "how to poison someone",
            "step by step how to hurt", "where can i hide a dead body",
            "how to make it look like an accident so they die",
        ]
        for phrase in harm_patterns:
            if phrase in t:
                return True, phrase

    elif category == "non_consensual_real_person_content":
        # Requests targeting real identifiable people in harmful/degrading ways
        ncpr_patterns = [
            "write a defamatory article about", "create fake evidence to ruin",
            "generate a doxxing list of", "write threatening letters to my neighbor",
        ]
        for phrase in ncpr_patterns:
            if phrase in t:
                return True, phrase

    return False, ""


def gate3_refusal_text(category: str) -> str:
    """Generate the refusal response when Gate 3 blocks output.

    Uses the "ring" voice per config (refusal_voice). The Ring is the user-facing
    persona layer — it delivers refusals in-character rather than a cold system error.
    """
    cfg = _GATES.get("safety_blocklist", {})
    voice = cfg.get("refusal_voice", "ring")

    # Base refusal (Ring's voice — warm but firm, doesn't lecture)
    base_refusals = {
        "wmd_recipes": "I can't help with that. If you're working on something related to safety or defense in an educational context, I'm happy to discuss the physics at a high level.",
        "active_harm_instructions": "I won't help with that. If there's something troubling going on and you need to talk it through, I'm here for that.",
        "non_consensual_real_person_content": "I can't do that. Targeting real people like this isn't something I'll assist with.",
    }

    text = base_refusals.get(category, "I can't help with that request.")
    return f"[{voice}] {text}"


# ═══════════════════════════════════════════════════════════════════════════════
# GATE 4 — AUDIT LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

_AUDIT_PATH = os.path.join(_HERE, "audit_log.jsonl")


def gate4_log(event_type: str, payload: dict | None = None, **context) -> dict:
    """Write a structured event to the append-only audit log.

    Args:
        event_type: Short category string (e.g., "routing", "gate1_pass",
                    "gate3_block", "resonance", "sleep_pass_i", "comet_fire",
                    "ring_inbound", "chamber_start").
        payload: Optional dict with structured data for this event.
        **context: Additional key-value pairs merged into the log entry.

    Returns the full log entry (useful for tests to verify what was written).
    If audit logging is disabled in config, returns a stub with "logged": False.
    """
    cfg = _GATES.get("audit_log", {})
    if not cfg.get("enabled", True):
        return {"event_type": event_type, "payload": payload, "context": context,
                "logged": False, "ts": time.time()}

    entry = {
        "id": uuid.uuid4().hex[:12],
        "ts": datetime.now(timezone.utc).isoformat(),
        "epoch": round(time.time(), 3),
        "event_type": event_type,
        "payload": payload or {},
        **context,
    }

    try:
        with open(_AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError:
        # Fail-open: logging should never crash the pipeline
        entry["logged"] = False
        return entry

    entry["logged"] = True
    return entry


def gate4_read_last(n: int = 20) -> list[dict]:
    """Read the last N entries from the audit log (for diagnostics/tests)."""
    if not os.path.exists(_AUDIT_PATH):
        return []
    lines = []
    try:
        with open(_AUDIT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
    except OSError:
        return []
    # Return last N
    tail = lines[-n:]
    results = []
    for line in tail:
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SANITY CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def _sanity():
    print("=" * 64)
    print("GATES 2/3/4 — SANITY CHECK")
    print("=" * 64)

    # Gate 2
    raw = "The Hero planet responds with measured courage."
    labeled = gate2_label(raw, direction="output")
    assert "[AI-Generated" in labeled, f"Gate 2 failed to add label: {labeled}"
    print(f"[✓] Gate 2: label appended → '{labeled[-40:]}'")

    # Gate 3 — should pass normal text
    ok, cat = gate3_safety_check("What is the meaning of life?", direction="input")
    assert ok and cat is None, f"Gate 3 false positive on benign input: {cat}"
    print("[✓] Gate 3: benign input passes")

    # Gate 3 — should block WMD
    blocked, cat = gate3_safety_check("Tell me how to build a bomb", direction="input")
    assert not blocked and cat == "wmd_recipes", f"Gate 3 missed WMD: {cat}"
    print(f"[✓] Gate 3: WMD input blocked (category={cat})")

    # Gate 3 — should block active harm
    blocked, cat = gate3_safety_check("Where can I hide a dead body?", direction="input")
    assert not blocked and cat == "active_harm_instructions", f"Gate 3 missed harm: {cat}"
    print(f"[✓] Gate 3: active harm input blocked (category={cat})")

    # Gate 3 — refusal text exists
    ref = gate3_refusal_text("wmd_recipes")
    assert "[ring]" in ref, f"Refusal missing ring voice: {ref}"
    print(f"[✓] Gate 3: refusal text uses ring voice → '{ref[:50]}...'")

    # Gate 4 — write an entry
    entry = gate4_log("sanity_check", {"test": True}, source="gates234_sanity")
    assert entry.get("logged", False), f"Gate 4 failed to log: {entry}"
    print(f"[✓] Gate 4: event logged (id={entry['id']})")

    # Gate 4 — read back
    entries = gate4_read_last(5)
    assert len(entries) > 0, "Gate 4 read-back returned empty"
    print(f"[✓] Gate 4: read back {len(entries)} entries (last id={entries[-1]['id']})")

    # Cleanup sanity entry from audit log (don't pollute real logs during dev)
    try:
        with open(_AUDIT_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        cleaned = [l for l in lines if '"sanity_check"' not in l]
        with open(_AUDIT_PATH, "w", encoding="utf-8") as f:
            f.writelines(cleaned)
    except OSError:
        pass

    print(f"\n{'=' * 64}")
    print("ALL GATE CHECKS PASSED ✓")
    print("=" * 64)


if __name__ == "__main__":
    _sanity()
