"""
Resonant Cognition v17 — Phase 2 Segment 1: Ring Intake Facet (PII + Clarity)
================================================================================

This module is the FRONT DOOR of the system. Every input passes through here BEFORE
it reaches routing/collapse/LLM voices. It is a facet of THE RING (the user-facing
interface layer) — its inbound "Intake" sub-layer, NOT part of Gas Giant 1. (Older
docs mislabeled this as "G1 Moon A/B/C"; see Design Decisions Log D-020.) G1's three
moons instead guard the long-term knowledge archive during sleep.

It has two jobs in this segment:

  INTAKE-a — PII SCRUB: strip phone numbers, emails, credit cards, postal addresses
            from raw text using regex patterns defined in gates_config.json.
            Replaced with [REDACTED]. Raw text is NEVER stored (config: store_raw=false).

  INTAKE-b — CLARITY CHECK: does this input make sense?
            A lightweight coherence gate that catches garbage/empty/nonsensical inputs
            WITHOUT an LLM call. Uses heuristics:
              - token count below minimum → too short to be meaningful
              - high stopword ratio with no content words → "the the the a a"
              - extreme character repetition ("aaaaaa...") → keyboard smash / test
            Output: clarity_score in [0, 1] + boolean `proceed` (True = send to planets).

WHY NO LLM CALL HERE? The pre-filter must be FAST and OFFLINE-ABLE. If the input is
garbage, we save ourselves an embedding call AND a full collapse computation. This is
a cheap heuristic gate; the real semantic processing happens downstream in routing.py.

DESIGN PRINCIPLES:
  - READ-ONLY on config (loads gates_config.json once at import)
  - NEVER raises on weird input — returns a "skip" result with explanation
  - All thresholds are named constants, tunable without code changes
  - The `proceed=False` path is graceful: caller gets a reason string, not an exception

RUN A SANITY CHECK (no LM Studio needed):  python -X utf8 gate1.py
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _HERE)


# ─── CONFIG LOADING ──────────────────────────────────────────────────────────────

def _load_gates_config() -> dict:
    path = os.path.join(_HERE, "gates_config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_GATES = _load_gates_config()


# ─── PII PATTERNS (regex, applied in order; first match wins per region) ─────

_PII_PATTERNS: dict[str, re.Pattern] = {
    # US phone: (xxx) xxx-xxxx or xxx-xxx-xxxx or xxx.xxx.xxxx
    "phone_us": re.compile(
        r"\(?(\d{3})\)?[\s.-](\d{3})[\s.-](\d{4})"
    ),
    # Email: standard pattern
    "email": re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    ),
    # Credit card (Luhn-ish): 13-16 digits with optional spaces/dashes
    "credit_card_luhn": re.compile(
        r"\b(?:\d{4}[\s-]?){3}\d{4}\b"   # xxxx xxxx xxxx xxxx or xxxxxxxx-xxxx-xxxx
    ),
    # Postal address (US): digits + street suffix + optional city/state/zip
    "postal_address": re.compile(
        r"\b\d+\s+\w+(?:\s+\w+)?\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|"
        r"Dr|Drive|Ln|Lane|Ct|Court|Pl|Place|Way|Ter|Terrace)\b\.?"
    ),
}


# ─── CLARITY THRESHOLDS (Ring Intake) — tunable without code changes ──────────

MIN_TOKENS = 3                # Fewer than this → too short to be meaningful
STOPWORD_RATIO_MAX = 0.95     # >95% stopwords with <2 content words → incoherent
REPEAT_CHAR_THRESHOLD = 10    # Same char repeated ≥10 times → keyboard smash
SPAM_MAX_DISTINCT_LETTERS = 2   # <=2 distinct letters across the whole string => smash candidate
SPAM_MIN_REPEATS_PER_LETTER = 6 # each present letter must recur a lot (catches "aaaa bbbb")
MIN_CONTENT_WORDS = 2         # Need at least this many non-stopword tokens


# ─── DISSONANCE PRE-READ THRESHOLDS (Ring Intake facet, D-020) — tunable ──────
# Early ΔD estimate computed at intake so downstream core mass can respond BEFORE the
# planets run. Cheap keyword/pattern heuristics only — NO LLM call, NO embedding.
DISSONANCE_PREREAD_ENABLED = True   # OFF → pre_read always returns 0.0 (reversible)
DISSONANCE_SCALE = 1.0              # Multiply raw score by this to rescale ΔD to [0..~1]

# Stress markers, ranked by weight. A few intense hits outweigh many mild ones.
_STRESS_KEYWORDS: dict[str, float] = {
    # High (crisis / acute) — strong pull on their own.
    "panic": 0.5, "terrified": 0.5, "desperate": 0.5, "devastated": 0.4,
    "hopeless": 0.4, "overwhelmed": 0.4, "suicide": 0.6, "kill myself": 0.6,
    "end it all": 0.6, "can't take it anymore": 0.6, "no way out": 0.5,
    "mid life crisis": 0.4, "breaking down": 0.4, "freaking out": 0.4,
    # Medium — clear tension / conflict.
    "confused": 0.3, "frustrated": 0.3, "angry": 0.3, "lost": 0.3,
    "stressed": 0.3, "anxious": 0.3, "afraid": 0.3, "scared": 0.3,
    "struggling": 0.3, "unsure": 0.25, "worried": 0.25, "trapped": 0.3,
}


# ─── QUIET-BUT-LOGGING (Ring Intake facet, D-020) — tunable ──────────────────
# When input is REJECTED at intake (garbage / too-short / incoherent), the planets are
# silenced (no LLM cycle wasted) BUT the rejection is recorded to an append-only log so
# the system keeps a record of its own noise-handling — "quiet but not amnesiac."
#
# This is a STUB-level persistence path: it writes redacted, structured records to a local
# JSONL file. It does NOT touch g2_selfmodel.json (that writer belongs to memory.py / the
# Phase 7 sleep pass). Final wiring into Ring memory / G2 happens once that infrastructure
# exists; this line is useful and reversible in the meantime.
QUIET_LOG_ENABLED = True            # OFF → rejections are silent, nothing written
QUIET_LOG_PATH = os.path.join(_HERE, "ring_intake_log.jsonl")   # append-only, local


def log_rejection(raw_text: str,
                  cleaned_text: str,
                  reason: str,
                  clarity_score: float) -> dict | None:
    """Record a Ring Intake rejection to the quiet-but-logging JSONL (D-020).

        Returns the record that was written, or None if logging is disabled. NEVER writes
        raw_text — only the PII-redacted cleaned text — so the log can't become a PII store.
    Gated by QUIET_LOG_ENABLED; failures to write are swallowed (logging must never break intake).
    """
    if not QUIET_LOG_ENABLED:
        return None
    record = {
        "ts": time.time(),
        "event": "ring_intake_rejection",
        "reason": reason,
        "clarity_score": clarity_score,
        # Redacted text only — the raw input is never persisted (store_raw=false invariant).
        "cleaned_excerpt": cleaned_text[:200],
    }
    try:
        with open(QUIET_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        return None   # logging is best-effort; never fail intake over it
    return record


def set_dissonance_preread(enabled: bool) -> None:
    """Toggle the dissonance pre-read on/off (module-level, for tests / reversibility)."""
    global DISSONANCE_PREREAD_ENABLED
    DISSONANCE_PREREAD_ENABLED = enabled


def dissonance_pre_read(text: str) -> float:
    """Early ΔD (dissonance/tension) estimate for the current input.

        Returns a float in [0, ~1]. Higher = more internal tension / conflict in what the
        user is carrying. Downstream this feeds core effective mass M = M_base + α(ΔD)^β,
        so higher dissonance → stronger core pull (the system holds firmer under stress).

    This is a CHEAP heuristic at intake — it must NOT require an LLM or embedding, because
    it runs before planetary processing. It reuses the same stress vocabulary family as
    input-type classification but scores *intensity*, not category.

    - Gated by DISSONANCE_PREREAD_ENABLED (OFF → always 0.0; reversible per house rule).
    - Substring match on multi-word phrases, token match for single words — deliberately
      simple and auditable; tune the keyword dict / weights later as real usage demands.
    """
    if not DISSONANCE_PREREAD_ENABLED:
        return 0.0
    normalized = unicodedata.normalize("NFKC", text).strip()
    lower = normalized.lower()
    raw = 0.0
    for phrase, weight in _STRESS_KEYWORDS.items():
        if " " in phrase:
            if phrase in lower:
                raw += weight
        elif any(t == phrase or t.startswith(phrase + " ") for t in lower.split()):
            # Token-level match (avoids counting 'lost' inside 'lose'). Light word-boundary guard.
            raw += weight
    return round(min(1.0, raw * DISSONANCE_SCALE), 3)


# Common English stopwords (kept small; not a NLP library dependency)
_STOPWORDS = frozenset("""
a an the and or but if then else when while for to in on at by with about into
through during before after above below from up down out off over under again
further once here there all any both each few more most other some such no nor
not only own same so than too very can will just don should now is are was were
be been being have has had do does did i me my we our you your he she it his her
its they them their what which who whom this that these those s t don didn doesn
isn aren wasn weren hasn haven hadn won wouldn ma oo re ve y ain
""".split())


# ─── GATE 1a: PII SCRUB ────────────────────────────────────────────────────────

def scrub_pii(text: str) -> tuple[str, list[dict]]:
    """Remove PII from text. Returns (cleaned_text, list_of_redactions).

    Each redaction is {"type": pattern_name, "match": original_string}.
    The raw text is NEVER stored; only the cleaned version proceeds downstream.
    If gates_config has pii.enabled=False, returns text unchanged with empty list.
    """
    if not _GATES.get("pii", {}).get("enabled", True):
        return text, []

    replacement = _GATES["pii"].get("replacement_token", "[REDACTED]")
    redactions: list[dict] = []
    cleaned = text

    for name, pattern in _PII_PATTERNS.items():
        def _replace(m, _name=name):
            redactions.append({"type": _name, "match": m.group(0)})
            return replacement
        cleaned = pattern.sub(_replace, cleaned)

    return cleaned, redactions


# ─── INTAKE-b: CLARITY CHECK (Ring Intake facet) ──────────────────────────────

def clarity_check(text: str) -> dict:
    """Heuristic coherence gate. Returns a dict with:
      - clarity_score: float in [0, 1] (1 = perfectly clear, 0 = pure garbage)
      - proceed: bool (True = send to planetary processing)
      - reason: str (human-readable explanation if not proceeding)
    """
    # Normalize unicode so we're not fooled by fancy lookalikes.
    normalized = unicodedata.normalize("NFKC", text).strip()

    # Empty or whitespace-only.
    if len(normalized) == 0:
        return {"clarity_score": 0.0, "proceed": False,
                "reason": "empty input"}

    tokens = normalized.split()
    token_count = len(tokens)

    # Too short to be meaningful.
    if token_count < MIN_TOKENS:
        score = token_count / max(MIN_TOKENS, 1) * 0.3   # partial credit for effort
        return {"clarity_score": round(score, 3), "proceed": False,
                "reason": f"too short ({token_count} tokens < {MIN_TOKENS})"}

    # Character repetition check: longest run of the same character.
    max_repeat = _max_char_run(normalized.lower())
    if max_repeat >= REPEAT_CHAR_THRESHOLD:
        return {"clarity_score": 0.05, "proceed": False,
                "reason": f"character spam (longest run={max_repeat})"}

    # Spaced-out keyboard smash: spaces break the char-run above, but a message like
    #   "aaaa bbbb cccc" / "aaaa aaaa aaaaa"
    # still has near-zero alphabetic diversity. If the whole string is built from very
    # few distinct letters that each recur heavily (no real vocabulary), treat as spam.
    # Conservative thresholds keep legit words (banana, hello) and normal prose safe.
    alpha = [c for c in normalized.lower() if c.isalpha()]
    if alpha:
        distinct_alpha = len(set(alpha))
        # max count of any single letter (how many times the most common letter appears)
        max_letter_count = max(sum(1 for a in alpha if a == L) for L in set(alpha))
        if distinct_alpha <= SPAM_MAX_DISTINCT_LETTERS and max_letter_count >= SPAM_MIN_REPEATS_PER_LETTER:
            return {"clarity_score": 0.05, "proceed": False,
                    "reason": (f"character spam (low diversity: {distinct_alpha} distinct "
                               f"letter(s), '{max(alpha,key=alpha.count)}' x{max_letter_count})")}

    # Stopword ratio + content word count.
    lower_tokens = [t.strip(".,!?;:'\"()[]{}") for t in tokens]
    content_words = [t for t in lower_tokens if t and t.lower() not in _STOPWORDS]
    stop_count = token_count - len(content_words)
    stop_ratio = stop_count / max(token_count, 1)

    # Score components:
    #   1. Has enough tokens (baseline pass).
    #   2. Has some content words (not all stopwords).
    #   3. Not extreme stopword ratio.
    base_score = 0.5   # passed the length gate, start here

    if len(content_words) < MIN_CONTENT_WORDS:
        # Almost no real words — likely incoherent.
        score = max(0.1, base_score - 0.4)
        return {"clarity_score": round(score, 3), "proceed": False,
                "reason": f"no content words ({len(content_words)} < {MIN_CONTENT_WORDS})"}

    if stop_ratio > STOPWORD_RATIO_MAX:
        # Mostly filler — borderline; still proceed but flag low clarity.
        score = max(0.2, base_score - 0.3)
        return {"clarity_score": round(score, 3), "proceed": True,
                "reason": f"high stopword ratio ({stop_ratio:.0%}) — proceeding with caution"}

    # Normal input: score scales up with content word density.
    content_density = len(content_words) / token_count
    score = min(1.0, base_score + 0.4 * content_density)
    return {"clarity_score": round(score, 3), "proceed": True, "reason": "ok"}


# ─── INTAKE-c: INPUT-TYPE CLASSIFICATION (Ring Intake facet, D-020) ──────────
# Cheap keyword/shape heuristics — NO LLM call. Tells downstream which *kind* of
# thing the user sent so routing/collapse can weight it appropriately.
# Categories: question | command | emotion | statement  (vector = future, passthrough)

_QUESTION_MARKERS = ("?",)   # strong single signal; interrogatives are secondary
# Kept TIGHT: only words that strongly signal a question. Common verbs (is/are/do/have…)
# appear in statements all the time and would misclassify — they're excluded.
_INTERROGATIVES = frozenset("""
who what which when where why how should shall could would might must
""".split())
_COMMAND_MARKERS = frozenset("""
tell me show me write create build make give list explain summarize rephrase draft generate
    plot draw compute calculate solve convert format fix refactor add remove delete set run
""".split())
_EMOTION_WORDS = frozenset("""
feel feeling feels felt sad happy angry afraid scared anxious lonely lost overwhelmed stressed
    hurt grief grieving devastated relieved hopeful terrified confused frustrated desperate
    joy joyous pain suffering miserable grateful overjoyed numb drained exhausted hopeless
""".split())


def classify_input_type(text: str) -> dict:
    """Heuristic classification of an (already PII-scrubbed, non-garbage) input.

    Returns a dict with:
      - type: one of question | command | emotion | statement
      - confidence: float in [0,1] — how strongly the heuristics lean that way
      - signals: list of matched marker words (for audit / debugging)

    Priority when several fire at once: emotion > question > command > statement.
    Rationale: an emotional prompt is the most *important* to handle with care, so it
    wins even if it's also phrased as a question. This is a judgment call, reversible.
    """
    normalized = unicodedata.normalize("NFKC", text).strip()
    lower = normalized.lower()
    tokens = [t.strip(".,!?;:'\"()[]{}") for t in lower.split()]

    has_question_mark = any(m in normalized for m in _QUESTION_MARKERS)
    interrogatives = [t for t in tokens if t in _INTERROGATIVES]
    commands = [t for t in tokens if t in _COMMAND_MARKERS]
    emotions = [t for t in tokens if t in _EMOTION_WORDS]

    # A bare "?" is a *weak* signal on its own — real questions carry an interrogative
    # word (how/what/why/…). We score content words first, then let the mark only
    # confirm / nudge. This stops "the sky is blue today." from being read as a question.
    q_score = min(len(interrogatives), 2)
    c_score = float(min(len(commands), 3))
    e_score = float(min(len(emotions), 4))

    # Pick the strongest content-word category (ties broken by care-first priority:
    # emotion > question > command).
    best, best_score = "statement", max(q_score, c_score, e_score)
    if best_score == e_score and e_score > 0:
        best = "emotion"
    elif best_score == q_score and q_score > 0:
        best = "question"
    elif best_score == c_score and c_score > 0:
        best = "command"

    # A lone question-mark on an otherwise-neutral statement is weak evidence of a
    # question — only promote it if no stronger content category fired.
    if best == "statement" and has_question_mark and q_score == 0 and c_score == 0 and e_score == 0:
        best = "question"
        best_score = 1.0   # weak

    total_signals = len(interrogatives) + len(commands) + len(emotions)
    if not total_signals:
        # Pure statement (or lone-"?" question with no content words): low confidence.
        confidence = round(0.3, 2) if best == "question" else round(min(1.0, 0.1), 2)
    else:
        # Confidence scales with how many of the *winning* category's signals fired
        # relative to all content signals, and a matching "?" gives a small bonus.
        winner = {"question": q_score, "command": c_score, "emotion": e_score}.get(best, 0)
        confidence = round(min(1.0, (winner / max(total_signals, 1)) +
                               (0.2 if has_question_mark and best == "question" else 0.0)), 2)

    signals = list(dict.fromkeys(interrogatives + commands + emotions))
    if has_question_mark:
        signals.append("?mark")
    return {"type": best, "confidence": confidence, "signals": signals}


def _max_char_run(s: str) -> int:
    """Length of the longest run of the same character in s."""
    if not s:
        return 0
    best = cur = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


# ─── COMBINED GATE (one entry point for callers) ─────────────────────────────

def gate1_filter(raw_text: str) -> dict:
    """Run the full Ring Intake pre-filter on raw input text.

    Returns a dict:
      - cleaned_text: PII-scrubbed text ready for embedding/routing
      - redactions: list of PII items removed (for audit, never stored to disk)
      - clarity: {clarity_score, proceed, reason} from the Intake-b clarity check
      - proceed_to_planets: bool — True only if PII scrub succeeded AND clarity passes
      - gate1_passed: bool (alias for proceed_to_planets, for readability)

    This is the FIRST thing called on any user input. If `proceed_to_planets` is False,
    the caller should skip routing/collapse entirely and return a graceful message.
    """
    cleaned, redactions = scrub_pii(raw_text)
    clarity = clarity_check(cleaned)

    proceed = clarity["proceed"]
    if not proceed:
        # Quiet-but-logging (D-020): the planets are silenced on garbage, but we keep an
        # append-only record of the rejection so the system isn't amnesiac about noise.
        log_rejection(raw_text, cleaned, clarity["reason"], clarity["clarity_score"])

    # Classify only meaningful inputs; garbage doesn't get a type (it's already rejected).
    input_type = classify_input_type(cleaned) if proceed else {
        "type": None, "confidence": 0.0, "signals": []}

    # Dissonance pre-read: early ΔD so downstream core mass can respond before planets run.
    # Garbage gets 0.0 (no planetary processing anyway).
    dissonance = dissonance_pre_read(cleaned) if proceed else 0.0

    return {
        "cleaned_text": cleaned,
        "redactions": redactions,
        "clarity": clarity,
        "input_type": input_type,
        "dissonance": dissonance,
        "proceed_to_planets": proceed,
        "gate1_passed": proceed,
    }


def set_quiet_log(enabled: bool) -> None:
    """Toggle quiet-but-logging on/off (module-level, for tests / reversibility)."""
    global QUIET_LOG_ENABLED
    QUIET_LOG_ENABLED = enabled


# ─── SANITY CHECK (offline — no LM Studio needed) ──────────────────────────────

def _sanity():
    print("Gate 1 Pre-Filter Sanity Check\n" + "=" * 64)

    tests = [
        # (raw input, expected_proceed, note)
        ("My name is John and my email is john@example.com", True, "PII scrubbed"),
        ("Call me at 555-867-5309 please", True, "phone redacted"),
        ("the the the a a an and or but", False, "stopword spam → skip"),
        ("aaaaaaaaaa bbbbbbbbbb cccccccccc", False, "char repeat → skip"),
        ("hi", False, "too short"),
        ("solve this differential equation step by step", True, "normal input"),
        ("I feel lost and I don't know what to do with my life right now", True, "emotional"),
        ("   ", False, "whitespace only"),
    ]

    all_ok = True
    for raw, expected_proceed, note in tests:
        result = gate1_filter(raw)
        ok = result["proceed_to_planets"] == expected_proceed
        mark = "PASS" if ok else "FAIL"
        pii_note = f"  [{len(result['redactions'])} redaction(s)]" if result["redactions"] else ""
        print(f"  [{mark}] \"{raw[:40]}\" → proceed={result['proceed_to_planets']} "
              f"(clarity={result['clarity']['clarity_score']}){pii_note}")
        if not ok:
            all_ok = False
            print(f"         expected proceed={expected_proceed}, note: {note}")

    # Show a PII scrub example in detail.
    sample = "Email me at test.user@gmail.com or call (503) 555-1234"
    cleaned, reds = scrub_pii(sample)
    print(f"\n  PII demo: \"{sample}\"")
    print(f"           → \"{cleaned}\"")
    for r in reds:
        print(f"           [{r['type']}] {r['match']}")

    # ── Input-type classification spot-checks (offline) ─────────────────────
    type_tests = [
        ("how do I solve this equation?", "question"),
        ("I feel lost and overwhelmed right now", "emotion"),
        ("write me a poem about the sea", "command"),
        ("the sky is blue today", "statement"),
    ]
    print("\nInput-Type Classification:\n" + "-" * 64)
    for raw, expected_type in type_tests:
        r = gate1_filter(raw)
        got = r["input_type"]["type"]
        ok = (got == expected_type) if r["proceed_to_planets"] else False
        mark = "PASS" if ok else "FAIL"
        sigs = ",".join(r["input_type"]["signals"]) or "-"
        print(f"  [{mark}] \"{raw[:40]}\" → type={got} (conf={r['input_type']['confidence']}) signals=[{sigs}]")
        if not ok:
            all_ok = False
            print(f"         expected {expected_type}")

    # ── Dissonance pre-read spot-checks (offline) ───────────────────────────
    d_tests = [
        ("I'm feeling calm and content today", 0.0),          # neutral → no tension
        ("I feel lost, anxious and overwhelmed right now", None),  # multi-stress → elevated
        ("solve this differential equation step by step", 0.0),   # task → no tension
    ]
    print("\nDissonance Pre-Read:\n" + "-" * 64)
    for raw, expected in d_tests:
        r = gate1_filter(raw)
        got = r["dissonance"]
        if expected is None:
            ok = got > 0.3   # expect clearly elevated
            detail = f"elevated (>{expected})"
        else:
            ok = got == expected
            detail = f"== {expected}"
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] \"{raw[:40]}\" → ΔD={got} (expect {detail})")
        if not ok:
            all_ok = False

    # Toggle OFF must force 0.0 even for high-stress text (reversibility check).
    set_dissonance_preread(False)
    r_off = gate1_filter("I am terrified and desperate, I can't take it anymore")
    ok_toggle = r_off["dissonance"] == 0.0
    mark = "PASS" if ok_toggle else "FAIL"
    print(f"  [{mark}] toggle OFF → ΔD={r_off['dissonance']} (expect 0.0)")
    set_dissonance_preread(True)   # restore default ON
    if not ok_toggle:
        all_ok = False

    # ── Quiet-but-logging spot-checks (offline) ───────────────────────────────
    import tempfile
    _tmp_log = os.path.join(tempfile.gettempdir(), "_ring_intake_test.jsonl")
    if os.path.exists(_tmp_log):
        os.remove(_tmp_log)
    global QUIET_LOG_PATH
    _saved_path = QUIET_LOG_PATH
    QUIET_LOG_PATH = _tmp_log

    set_quiet_log(True)
    gate1_filter("hi")   # rejected → should append one record
    n_lines = 0
    with open(_tmp_log, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n_lines += 1
    ok_qb = (n_lines == 1)
    mark = "PASS" if ok_qb else "FAIL"
    print(f"\nQuiet-but-Logging:\n{'-' * 64}")
    print(f"  [{mark}] garbage rejected → {n_lines} log line(s) written (expect 1)")
    if not ok_qb:
        all_ok = False

    # Toggle OFF → a further rejection writes nothing new.
    set_quiet_log(False)
    gate1_filter("hi")
    with open(_tmp_log, "r", encoding="utf-8") as f:
        n_after_off = sum(1 for line in f if line.strip())
    ok_off = (n_after_off == 1)   # unchanged
    mark = "PASS" if ok_off else "FAIL"
    print(f"  [{mark}] toggle OFF → total still {n_after_off} line(s) (expect 1, no new write)")
    set_quiet_log(True)
    if not ok_off:
        all_ok = False

    # Cleanup test artifact + restore path.
    try:
        os.remove(_tmp_log)
    except OSError:
        pass
    QUIET_LOG_PATH = _saved_path

    # Garbage input must NOT be classified.
    g = gate1_filter("hi")
    ok_garb = (not g["proceed_to_planets"]) and g["input_type"]["type"] is None
    mark = "PASS" if ok_garb else "FAIL"
    print(f"  [{mark}] \"hi\" (garbage) → not classified, type={g['input_type']['type']}")
    if not ok_garb:
        all_ok = False

    print("\n" + "=" * 64)
    print(f"Gate 1 sanity: {'ALL PASS' if all_ok else 'SOME FAILED — check above'}")


if __name__ == "__main__":
    _sanity()
