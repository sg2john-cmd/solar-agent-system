"""
Resonant Cognition v17 — Phase 6 Segment 1: The Ring (User-Facing Persona) Core
================================================================================

The Ring is the ONLY thing the user talks to. It is a swappable frontend, NOT
inherently "Maya" and NOT the brain behind the system — it's the face; the seven
planets are the minds. This module implements that contract for real (replacing
the Phase 0 stubs described in Build Plan.md §"The Ring — Interface Contract").

WHAT THIS SEGMENT DOES (zero LLM calls, fully offline):
  - Loads / saves persona.json and relationship_log.json from disk.
  - ring_inbound(): adds RELATIONSHIP FRAMING on top of already-hygienised input.
    This COMPLEMENTS gate1 (PII scrub + clarity) — it does NOT duplicate it. In the
    Phase 8 pipeline, gate1 runs first; by the time text reaches ring_inbound it is
    clean. Here we layer "this is conversation #N, last time we were talking about X"
    style context onto it.
  - ring_outbound(): applies the persona's voice (from voice_notes in persona.json)
    + idle-awareness phrasing to an engine-approved output string.
  - Swarm read helpers: read-only access to the Ring's spatial memory swarm for now.
    Writing into the swarm arrives in Segment 2 (reuses memory.py machinery).

DESIGN PRINCIPLES:
  - persona.json and relationship_log.json are USER-EDITABLE DATA. No field value is
    hardcoded as behaviour. The name "Maya" is a deployment choice, not identity — if
    John edits the JSON, the next run picks up the new voice automatically.
  - Pure read/write on JSON. No LM Studio calls in this segment.
  - Self-test at bottom: python -X utf8 ring.py

PIPELINE POSITION (Phase 8 full flow):
  raw_input → gate1_pii_scrub() → ring_inbound() [THIS MODULE — relationship context]
             → embedding → ... → chamber A/B/C → gate3_safety_check()
             → ring_outbound() [THIS MODULE — persona voice applied]
             → gate2_label + gate4_log → user sees response

RUN: python -X utf8 ring.py   (self-test, no LM Studio needed)
"""

from __future__ import annotations

import json
import os
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_RING_DIR = os.path.join(_HERE, "ring")
_PERSONA_PATH = os.path.join(_RING_DIR, "persona.json")
_REL_LOG_PATH = os.path.join(_RING_DIR, "relationship_log.json")
_SWARM_PATH = os.path.join(_RING_DIR, "swarm.json")


# ─── TUNABLES ────────────────────────────────────────────────────────────────
# How many recent topics to surface in ring_inbound context. GUESS: 3 (flagged).
INBOUND_RECENT_TOPICS = 3

# Idle-state thresholds (minutes of silence before the Ring is considered "quiet").
# These inform the idle_state label returned by ring_outbound; actual timer wiring
# happens in Phase 8. Default "active" until a caller tells us otherwise.
IDLE_THRESHOLD_MINUTES = 10.0


# ─── LOAD / SAVE ─────────────────────────────────────────────────────────────

def load_persona(path: str | None = None) -> dict:
    """Load persona.json from disk. Returns the raw dict (all fields user-editable).

    Raises FileNotFoundError if the file is missing — this is a hard dependency, not
    an optional feature; the Ring cannot function without its persona definition.
    """
    p = path or _PERSONA_PATH
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_persona(persona: dict, path: str | None = None) -> None:
    """Write persona.json back to disk. Used by Segment 3 (drift commit)."""
    p = path or _PERSONA_PATH
    with open(p, "w", encoding="utf-8") as f:
        json.dump(persona, f, indent=2, ensure_ascii=False)


def load_relationship_log(path: str | None = None) -> dict:
    """Load relationship_log.json. Returns a dict with guaranteed key structure."""
    p = path or _REL_LOG_PATH
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Ensure all expected keys exist (forward/backward compat).
    for k, default in [
        ("session_count", 0),
        ("topic_history", []),
        ("emotional_valence_history", []),
        ("last_session_ts", None),
        ("first_contact_ts", None),
        ("notes", ""),
    ]:
        data.setdefault(k, default)
    return data


def save_relationship_log(log: dict, path: str | None = None) -> None:
    """Write relationship_log.json back to disk."""
    p = path or _REL_LOG_PATH
    with open(p, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def load_swarm(path: str | None = None) -> dict:
    """Load the Ring's spatial memory swarm (read-only in this segment).

    Returns {"entries": [...]} — same shape as bodies.MemoryEntry serialised.
    Empty list is valid and expected for a fresh system.
    """
    p = path or _SWARM_PATH
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "entries" not in data:
        data["entries"] = []
    return data


# ─── RING INBOUND (relationship framing — complements gate1) ────────────────

def ring_inbound(raw_input: str, persona: dict | None = None,
                 rel_log: dict | None = None) -> dict:
    """Add relationship context to an already-cleaned input string.

    This is NOT a replacement for gate1 — in the live pipeline, text arriving here
    has already been PII-scrubbed and clarity-checked by gate1_pii_scrub(). The Ring
    adds what ONLY it knows: "this is conversation #47", "last time we were on the
    Jester idea", "you've talked about X a lot recently".

    Parameters
    ----------
    raw_input : str
        Cleaned text (post-gate1). Treated as already safe to store in context.
    persona   : dict, optional
        Loaded persona.json content. If None, loaded from disk.
    rel_log   : dict, optional
        Loaded relationship_log.json content. If None, loaded from disk.

    Returns
    -------
    dict with keys:
      text       — the input string unchanged (Ring does NOT modify user words)
      context    — {"session": int, "recent_topics": [str,...], "is_first_session": bool}
      persona_name — str, for downstream display use

    Side effects: NONE. Session counting / log updates happen at session END
    (see update_relationship_log below), not here, so inbound is idempotent and
    safe to call multiple times on the same input during a turn.
    """
    if persona is None:
        persona = load_persona()
    if rel_log is None:
        rel_log = load_relationship_log()

    session_count = int(rel_log.get("session_count", 0))
    topics: list[str] = rel_log.get("topic_history", []) or []
    recent_topics = topics[-INBOUND_RECENT_TOPICS:] if len(topics) > INBOUND_RECENT_TOPICS else topics[:]

    context = {
        "session": session_count,
        "recent_topics": recent_topics,
        "is_first_session": (session_count == 0),
    }

    return {
        "text": raw_input,
        "context": context,
        "persona_name": persona.get("name", ""),
    }


# ─── RING OUTBOUND (persona voice application) ──────────────────────────────

def ring_outbound(engine_output: str, persona: dict | None = None,
                  idle_minutes: float = 0.0) -> str:
    """Apply the persona's voice to an engine-approved output string.

    In Phase 6 Segment 1 this is a LIGHTWEIGHT text transformation — no LLM call.
    It prepends the persona name and, if the Ring has been idle recently, adds a
    brief ambient-awareness line BEFORE the main content (not after, so the user's
    question isn't buried under preamble).

    The actual "Maya speaks in her own words" full-voice pass will be an LLM call
    added in a later segment or at Phase 8 integration; this stub keeps the contract
    live and testable now.

    Parameters
    ----------
    engine_output : str
        The approved response from gate3 (post-safety-check). Not modified in content,
        only framed by persona voice markers.
    persona       : dict, optional — loaded from disk if None.
    idle_minutes  : float — how many minutes of silence preceded this output. If
                    >= IDLE_THRESHOLD_MINUTES, an ambient line is prepended.

    Returns
    -------
    str: the framed response ready for display to the user.
    """
    if persona is None:
        persona = load_persona()

    name = persona.get("name", "")
    prefix = f"{name}: " if name else ""

    idle_line = ""
    if idle_minutes >= IDLE_THRESHOLD_MINUTES:
        # Ambient awareness — references the Ring's own quiet, not a generic filler.
        # Full swarm-referencing version arrives in Segment 4 (idle reflections).
        idle_line = f"[{name} has been thinking while you were away...] "

    return idle_line + prefix + engine_output


# ─── RELATIONSHIP LOG UPDATES (called at session end, not per-inbound) ──────

def update_relationship_log(topic: str | None = None,
                            valence: float | None = None,
                            log: dict | None = None,
                            persist: bool = True,
                            path: str | None = None) -> dict:
    """Increment session count and optionally record a topic / valence sample.

    Called ONCE per session (not once per inbound call). This is what makes the 5th
    conversation genuinely different from the 1st — the log accumulates real mass.

    Parameters
    ----------
    topic   : str, optional — short label for this session's main subject. Appended to
              topic_history (capped at _MAX_TOPIC_HISTORY entries to keep file small).
    valence : float in [-1.0, 1.0], optional — rough emotional tone of the session.
              Positive = warm/positive; negative = tense/negative; 0 = neutral.
    log     : dict, optional — pre-loaded relationship_log. Loaded from disk if None.
    persist : bool — write back to disk (True by default). Set False in tests.
    path    : str, optional — override file path (used by self-test).

    Returns the updated log dict.
    """
    if log is None:
        log = load_relationship_log()

    now = time.time()
    first_contact_ts = log.get("first_contact_ts")
    if first_contact_ts is None:
        log["first_contact_ts"] = now
    log["last_session_ts"] = now
    log["session_count"] = int(log.get("session_count", 0)) + 1

    _MAX_TOPIC_HISTORY = 20   # keeps file small; old topics age out naturally
    if topic:
        history: list[str] = log.setdefault("topic_history", [])
        history.append(topic)
        if len(history) > _MAX_TOPIC_HISTORY:
            log["topic_history"] = history[-_MAX_TOPIC_HISTORY:]

    if valence is not None:
        v = max(-1.0, min(1.0, float(valence)))   # clamp to [-1, 1]
        vh: list[float] = log.setdefault("emotional_valence_history", [])
        vh.append(v)
        _MAX_VALENCE_HISTORY = 50
        if len(vh) > _MAX_VALENCE_HISTORY:
            log["emotional_valence_history"] = vh[-_MAX_VALENCE_HISTORY:]

    if persist:
        save_relationship_log(log, path)

    return log


# ─── SEGMENT 2: SWARM MEMORY WRITES ─────────────────────────────────────────
#
# The Ring's long-term memories are spatial entries that orbit her personality
# vector (NOT C_core). They live in ring/swarm.json via memory.ZONE_RING_SWARM.
#
# WHEN a turn becomes a swarm entry is a design decision. Proposal for John to
# ratify at the pause: user-facing / relational content goes to swarm, not everything.
# The function below makes that decision explicit and testable; the actual call-site
# wiring happens in Phase 8 when the full pipeline runs.
#
# HOW IT WORKS:
#   - Position: near persona.personality_vector [x,y,z] + small radial jitter
#     (reuses memory._position_with_jitter for consistency with other zones).
#   - Mass:    cosine alignment between semantic_vec and consensus_vec, scaled by
#     MEMORY_MASS_BASE. Same formula as planet vaults.
#   - PII guard: ON (reuses memory._pii_guard -> gate1.scrub_pii). Raw text is never
#     written to disk; only cleaned content + redaction-type audit trail.
#   - Decay:   D-011 usage-frequency rate via memory.compute_decay_rate(0) = base_gamma.
#     Grows over time as the entry is re-encountered in sleep Pass V (same path
#     as planet vaults; no special handling needed here).
#
# Zero LLM calls. Pure JSON write.

import math  # noqa: F401


def should_write_to_ring_swarm(session_topic: str | None,
                               valence: float | None,
                               has_relational_content: bool = False) -> bool:
    """Decide whether a completed session's summary becomes a Ring swarm entry.

    DEFAULT: write everything. The swarm is the Ring's short-term working memory —
    if you ask a Python question today and reference it two sessions later, the Ring
    needs a spatial trace of that conversation to respond coherently. D-011 decay +
    mass handle priority naturally:
      - Relational / high-emotional-weight entries get more mass (higher alignment)
        and survive longer.
      - Purely informational entries get less mass and fade faster under decay.
    This means the swarm self-prunes toward what matters without us having to make
    a hard cut at write time.

    The only reason to skip is if there was NO meaningful content at all (empty
    session, pure garbage that gate1 should have already rejected). In practice this
    function will return True for essentially every real session.

    Parameters are kept for future tuning (e.g. a "max swarm size" cap that might
    start dropping the lowest-mass entries when the swarm gets very large), but as of
    Segment 2 the logic is: always write unless explicitly told not to.
    """
    # If there's any content worth remembering, write it.
    if session_topic or has_relational_content:
        return True
    # No topic AND no relational flag → likely an empty/noise session. Still write
    # by default (the swarm is cheap; decay handles cleanup) unless a future cap says otherwise.
    return True


def make_ring_swarm_entry(semantic_content: str,
                          persona: dict | None = None,
                          semantic_vec: list[float] | None = None,
                          consensus_vec: list[float] | None = None,
                          ts: float | None = None) -> dict:
    """Build a memory entry positioned near the Ring's personality vector.

    Reuses memory.make_entry with zone=ZONE_RING_SWARM and ring_membership=True.
    Position is persona.personality_vector + jitter (NOT C_core, NOT a planet).
    Mass uses the same cosine-alignment formula as planet vaults.

    Parameters
    ----------
    semantic_content : str -- short summary of what happened this session.
                         Will be PII-scrubbed before persistence by write_entry.
    persona          : dict, optional -- loaded from disk if None.
    semantic_vec     : 384-dim embedding of the content (for mass calculation).
                       If None, mass defaults to MEMORY_MASS_BASE * 0.5 (neutral).
    consensus_vec    : 384-dim collapse result vector. Same fallback as above.
    ts               : creation timestamp override (used by tests/backdating).

    Returns a plain dict ready for memory.write_entry().
    """
    import memory  # lazy: avoids import cycle; ring.py can be loaded standalone
    if persona is None:
        persona = load_persona()

    pv = list(persona.get("personality_vector", [0.0, 0.3, 0.1]))
    pos = memory._position_with_jitter(pv)   # same jitter mechanism as other zones

    if semantic_vec is not None and consensus_vec is not None:
        mass = memory.compute_memory_mass(semantic_vec, consensus_vec)
    else:
        import constants as C
        base = float(getattr(C, "MEMORY_MASS_BASE", 1.0) or 1.0)
        mass = base * 0.5   # neutral fallback when no vectors available

    decay_rate = memory.compute_decay_rate(access_count=0)

    now = time.time()
    ts_val = float(ts) if ts is not None else now
    import random as _rng
    entry_id = f"ring_{int(ts_val * 1000)}_x{_rng.randint(0, 9999):04d}"

    return {
        "entry_id": entry_id,
        "vector_position": pos,
        "mass": float(mass),
        "semantic_content": semantic_content,
        "creation_ts": ts_val,
        "last_accessed": now,
        "decay_rate": float(decay_rate),
        "ring_membership": True,
        "zone": memory.ZONE_RING_SWARM,
    }


def write_ring_swarm_entry(entry: dict, base_dir: str | None = None) -> tuple[str, int]:
    """Persist a ring swarm entry to disk via memory.write_entry.

    The PII guard inside memory.write_entry scrubs semantic_content before it touches
    the file. Returns (abs_path, new_entry_count).

    base_dir defaults to _HERE (the code root), matching how memory.py resolves paths.
    """
    import memory
    if base_dir is None:
        base_dir = _HERE
    return memory.write_entry(entry, base_dir)


def read_ring_swarm_entries(path: str | None = None) -> list[dict]:
    """Return all live swarm entries (mass >= MIN_ENTRY_MASS), sorted by mass desc.

    Used by ring_outbound / idle reflections to know what the Ring 'remembers'.
    Entries below min_mass are considered shed by decay and excluded from active recall.

    path : optional explicit swarm file path override (used by tests).
           Defaults to the live ring/swarm.json.
    """
    import constants as C
    swarm = load_swarm(path)
    min_mass = float(getattr(C, "MIN_ENTRY_MASS", 0.05) or 0.0)
    entries = [e for e in swarm.get("entries", []) if float(e.get("mass", 0)) >= min_mass]
    entries.sort(key=lambda e: float(e.get("mass", 0)), reverse=True)
    return entries


def get_ring_memory_context(persona: dict | None = None,
                            max_entries: int = 5,
                            swarm_path: str | None = None) -> list[dict]:
    """Return the top-N swarm entries by mass for use in ring_inbound/outbound context.

    This is what makes the 5th conversation genuinely different from the 1st:
    the Ring has accumulated spatial memories with sufficient mass to influence
    her framing. Called by Phase 8's pipeline; in Segment 2 it's available but
    not yet wired into the live flow.
    """
    entries = read_ring_swarm_entries(swarm_path)
    return entries[:max_entries]


# ─── SEGMENT 4: IDLE BEHAVIOR (ambient reflection during silence) ──────────
#
# When the user has been quiet for a while, the Ring can offer a SHORT ambient
# aside — "You've been quiet. I was thinking about what you said earlier about X…"
# — sourced from her own recent swarm memory, voiced in persona voice_notes.
#
# DESIGN PRINCIPLES (Segment 4):
#   - TOGGLEABLE + DEFAULT OFF: constants.RING_IDLE_BEHAVIOR_ENABLED gates it. When
#     OFF, generate_idle_reflection() returns "" with ZERO LLM calls and does not
#     even import cognitive_chamber — so ring.py stays fully offline and the live
#     flow is byte-identical to pre-Segment-4 until John flips the toggle on.
#   - LAZY IMPORT: the LLM primitive (cognitive_chamber._llm_chat_cached) is imported
#     INSIDE the ON branch only, so `python -X utf8 ring.py` never needs LM Studio.
#   - ONE call max. It reuses the existing chamber HTTP primitive — no reinvented
#     urllib. Context is capped by RING_IDLE_CONTEXT_ENTRIES (default 2) so a fast-
#     growing swarm can't balloon the single prompt against the hardware ceiling.
#   - NO SIDE EFFECTS: reads swarm + persona, does not write anything to disk.
#   - GRACEFUL on empty memory: if there are no live entries yet (fresh system), it
#     still speaks — just a softer "I've been thinking…" that doesn't pretend to
#     remember specifics it doesn't have.
#
# TIMER WIRING IS DEFERRED TO PHASE 8. This segment only builds the callable; Phase 8's
# pipeline decides WHEN minutes_silent crosses IDLE_THRESHOLD_MINUTES and calls this.

def generate_idle_reflection(persona: dict | None = None,
                             minutes_silent: float = 0.0,
                             swarm_path: str | None = None,
                             max_entries: int | None = None) -> str:
    """Return a short ambient reflection from the Ring during user silence.

    Parameters
    ----------
    persona        : dict, optional — loaded from disk if None (uses name + voice_notes).
    minutes_silent : float — how long the user has been quiet. Below IDLE_THRESHOLD_MINUTES,
                     returns "" immediately (no LLM call) so callers can gate cheaply.
    swarm_path     : str, optional — explicit ring/swarm.json override (used by tests).
    max_entries    : int, optional — cap on how many recent entries feed the prompt.
                     Defaults to constants.RING_IDLE_CONTEXT_ENTRIES.

    Returns
    -------
    str: "" when disabled OR below the idle threshold (no-op). Otherwise a short,
         persona-voiced ambient line that references actual recent swarm content where
         available. Never raises on empty memory — falls back to a generic aside.
    """
    import constants as C

    # Hard gate FIRST: toggle OFF => pure no-op, zero LLM, zero imports of the chamber.
    if not bool(getattr(C, "RING_IDLE_BEHAVIOR_ENABLED", False)):
        return ""

    # Cheap threshold gate: only reflect once we've actually been quiet long enough.
    if minutes_silent < IDLE_THRESHOLD_MINUTES:
        return ""

    if persona is None:
        persona = load_persona()

    name = persona.get("name", "")
    voice_notes = str(persona.get("voice_notes", "")) or "warm, natural"

    # Source real recent content (top-N by mass). Capped so the prompt stays small.
    if max_entries is None:
        max_entries = int(getattr(C, "RING_IDLE_CONTEXT_ENTRIES", 2) or 1)
    entries = get_ring_memory_context(persona, max_entries=max_entries,
                                      swarm_path=swarm_path)

    # Build the prompt. If there's real memory, quote a snippet; if not, be honest that
    # we're just thinking (don't fabricate specifics).
    if entries:
        snippets = "\n".join(
            f"- {str(e.get('semantic_content', '')).strip()[:120]}"
            for e in entries
        )
        memory_block = (
            "Recent things you remember from your conversations with the user:\n"
            + snippets
        )
    else:
        memory_block = (
            "You don't have specific recent memories to point to yet — just keep it soft "
            "and honest (you've been thinking, but there's no particular topic to name)."
        )

    system_prompt = (
        f"You are '{name}', the user-facing persona of an AI system. Your voice: {voice_notes}.\n"
        "The user has been quiet for a while. Offer ONE short, natural ambient aside — at most "
        "1-2 sentences. Reference what you were genuinely thinking about (draw ONLY from the "
        "recent memories provided). Do NOT ask a direct question unless it flows naturally; this "
        "is you thinking out loud, not an interrogation. No preamble like 'I am an AI'. "
        "No markdown. Just the aside itself."
    )
    user_prompt = (
        f"The user has been silent for about {minutes_silent:.0f} minutes.\n\n"
        + memory_block
    )

    # Lazy import — only reached when toggle is ON, so offline self-test never touches this.
    from cognitive_chamber import _llm_chat_cached
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        text = _llm_chat_cached(
            messages,
            temperature=float(getattr(C, "RING_IDLE_TEMPERATURE", 0.8)),
            max_tokens=int(getattr(C, "RING_IDLE_MAX_TOKENS", 160)),
        )
    except Exception as exc:  # never crash the ring because a reflection failed
        return f"[{name} was thinking out loud… (reflection unavailable: {type(exc).__name__})]"

    text = (text or "").strip()
    if not name:
        return text
    return f"{name}: {text}" if text else ""


# ─── SEGMENT 5A: MONTHLY SELF-REVIEW TRIGGER (D-009) — zero LLM, offline ──────
#
# WHAT THIS SUB-SEGMENT DOES (no LM Studio calls, fully offline):
#   - check_self_review_trigger(): pure decision logic. Fires at the 30-session
#     mark OR a calendar-month boundary since the last review; never fires twice
#     for the same session / same month.
#   - build_g2_change_report_skeleton(): assembles the text that G2's report will be
#     built from (session stats + recent topics). Zero LLM — this is the raw material;
#     5b turns it into a natural-language report with ONE lazy LLM call.
#   - log_self_review_verdict(): appends the debate verdict to G2's ring_buffer in
#     g2_selfmodel.json, respecting the three self-model moons' existing contract:
#       * consistency gate  — tier-1 (behavioral) entry; never touches core_laws /
#                             gates_config / contents structure.
#       * magnitude gate    — it records a REPORT + VERDICT, not a vector nudge;
#                             no numeric self-model field is modified here.
#       * reversibility log — append-only: the new entry carries the BEFORE-state
#                             (what was in ring_buffer just before) so any drift can
#                             be walked back without rebuilding from scratch.
#
# DESIGN PRINCIPLES (Segment 5a):
#   - TOGGLEABLE + DEFAULT OFF via constants.RING_SELF_REVIEW_ENABLED. The trigger
#     returns {"fire": False} with zero side effects when off — the live flow is
#     byte-identical to pre-Segment-5 until John flips it on.
#   - SESSION COUNT = relationship_log.session_count (GUESS, flagged): that counter
#     already increments once per session via update_relationship_log(), so "30
#     sessions" means 30 real conversations with the user.
#   - G2 state lives in giants/g2_selfmodel.json; all paths are overridable for tests
#     (g2_path / rel_log kwargs) so nothing here ever writes live files during
#     `python -X utf8 ring.py`.

def check_self_review_trigger(rel_log: dict,
                              g2_state: dict | None = None,
                              g2_path: str | None = None,
                              now: float | None = None) -> dict:
    """Decide whether the D-009 monthly self-review should fire, and why.

    Pure function — reads only; writes nothing. Returns a dict:
      {"fire": bool,          # True ONLY when constants.RING_SELF_REVIEW_ENABLED is set
       "reason": str|None,    # "session_threshold" | "month_boundary" | None
       "session_count": int,
       "sessions_since_last_review": int,
       "months_since_last_review": float}

    Trigger rules (per D-009):
      1. Session threshold: session_count has crossed the next multiple of
         RING_SELF_REVIEW_SESSION_THRESHOLD since the last logged review.
      2. Month boundary: >= 1 calendar month elapsed since the last review's
         timestamp (or first-contact, if no review yet).
    Anti-double-fire: both rules compare AGAINST the last review recorded in G2's
    ring_buffer, so a single session can never log two reviews.

    Parameters
    ----------
    rel_log   : relationship_log dict (session_count + timestamps must be present;
                load_relationship_log() guarantees the keys).
    g2_state  : pre-loaded g2_selfmodel.json. If None and g2_path is given, loads it;
                if both are None, reads live file ONLY to inspect last review (read-only).
    g2_path   : explicit path override for tests.
    now       : timestamp override (tests / backdating). Defaults to time.time().
    """
    import constants as C

    result = {
        "fire": False,
        "reason": None,
        "session_count": int(rel_log.get("session_count", 0) or 0),
        "sessions_since_last_review": 0,
        "months_since_last_review": float("inf"),
    }

    # Hard gate first: toggle OFF => pure no-op, zero side effects.
    if not bool(getattr(C, "RING_SELF_REVIEW_ENABLED", False)):
        return result

    ts = float(now) if now is not None else time.time()

    # Locate the last self-review entry in G2's ring_buffer (append-only log).
    g2 = g2_state
    if g2 is None:
        p = g2_path or os.path.join(_HERE, "giants", "g2_selfmodel.json")
        try:
            with open(p, "r", encoding="utf-8") as f:
                g2 = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            g2 = {"ring_buffer": []}
    last_review_ts: float | None = None
    for entry in reversed(g2.get("ring_buffer", []) or []):
        if isinstance(entry, dict) and str(entry.get("role", "")).upper().startswith("SELF_REVIEW"):
            t = entry.get("ts")
            if t is not None:
                last_review_ts = float(t)
            break

    # Rule 1 — session threshold (GUESS: relationship_log.session_count, flagged).
    threshold = int(getattr(C, "RING_SELF_REVIEW_SESSION_THRESHOLD", 30) or 30)
    # If a review already fired AT the current count (same session), don't re-fire:
    # we approximate "since last review" via the recorded session_count in that entry.
    sessions_at_last = 0
    if last_review_ts is not None:
        for entry in reversed(g2.get("ring_buffer", []) or []):
            if isinstance(entry, dict) and str(entry.get("role", "")).upper().startswith("SELF_REVIEW"):
                sessions_at_last = int(entry.get("session_count", 0) or 0)
                break
    sessions_since_last_review = max(0, result["session_count"] - sessions_at_last)
    result["sessions_since_last_review"] = sessions_since_last_review
    session_due = (
        threshold > 0
        and result["session_count"] >= threshold          # haven't even reached it yet?
        and (last_review_ts is None or result["session_count"] > sessions_at_last)
        and (result["session_count"] // threshold) > (sessions_at_last // threshold)
    )

    # Rule 2 — calendar-month boundary.
    anchor = last_review_ts if last_review_ts is not None else rel_log.get("first_contact_ts")
    months_since = float("inf")
    if anchor is not None:
        try:
            months_since = max(0.0, (ts - float(anchor)) / (30.44 * 86400.0))
        except (TypeError, ValueError):
            months_since = float("inf")
    result["months_since_last_review"] = months_since
    month_due = (anchor is not None) and (months_since >= 1.0)

    if session_due:
        result["fire"] = True
        result["reason"] = "session_threshold"
    elif month_due:
        result["fire"] = True
        result["reason"] = "month_boundary"
    return result


def build_g2_change_report_skeleton(rel_log: dict, persona: dict | None = None,
                                    max_topics: int | None = None) -> str:
    """Assemble the raw-material text G2 uses to write its change report. ZERO LLM.

    Returns a compact block with session stats + the most recent topic labels (capped
    by constants.RING_SELF_REVIEW_REPORT_TOPICS). 5b wraps this in one lazy
    _llm_chat_cached() call to produce the natural-language report; offline tests use
    the skeleton directly so no LM Studio is ever needed.
    """
    import constants as C
    if persona is None:
        persona = load_persona()
    cap = int(max_topics) if max_topics else int(getattr(C, "RING_SELF_REVIEW_REPORT_TOPICS", 5))
    topics: list[str] = rel_log.get("topic_history", []) or []
    recent = [str(t).strip() for t in topics[-cap:] if str(t).strip()] if cap > 0 else []

    lines = [
        "SELF-MODEL CHANGE REPORT — RAW MATERIAL (G2)",
        f"Persona: {persona.get('name', '')}",
        f"Sessions completed: {int(rel_log.get('session_count', 0) or 0)}",
    ]
    fc = rel_log.get("first_contact_ts")
    ls = rel_log.get("last_session_ts")
    if fc is not None and ls is not None:
        try:
            span_days = (float(ls) - float(fc)) / 86400.0
            lines.append(f"Span: ~{span_days:.1f} days since first contact")
        except (TypeError, ValueError):
            pass
    if recent:
        lines.append("Recent topics: " + "; ".join(recent))
    else:
        lines.append("Recent topics: none recorded yet.")
    return "\n".join(lines)


def log_self_review_verdict(report_text: str, debate_summary: dict,
                            g2_state: dict | None = None,
                            g2_path: str | None = None,
                            persist: bool = True,
                            now: float | None = None) -> dict:
    """Append the self-review verdict to G2's ring_buffer (append-only, reversible).

    Honors the three self-model moons' existing contract (see g2_selfmodel.json):
      * CONSISTENCY  — behavioral tier-1 entry only; this function never writes to
                       contents, core_laws, or gates_config.
      * MAGNITUDE    — records a report + verdict; NO numeric self-model field is
                       modified here (no vector nudge, no mass change).
      * REVERSIBILITY— the new record carries "before" = snapshot of ring_buffer as it
                       was just before this append, enabling exact walk-back.

    Parameters
    ----------
    report_text    : G2's natural-language change report (from 5b) or the skeleton text.
    debate_summary : dict — at minimum {"all_emitted": bool, "approve": int,
                       "redirect": int, "error": list[str]}. The anti-silence flag
                       all_emitted must be True for this to be logged as a VERDICT;
                       otherwise it is held with status="held_anti_silence" (nothing is
                       treated as decided — no majority-vote collapse).
    g2_state       : pre-loaded G2 dict; loaded from g2_path if None.
    g2_path        : path override for tests. Defaults to giants/g2_selfmodel.json.
    persist        : write back to disk (True by default). Set False in offline tests.

    Returns the appended record dict.
    """
    ts = float(now) if now is not None else time.time()
    p = g2_path or os.path.join(_HERE, "giants", "g2_selfmodel.json")
    state = g2_state
    if state is None:
        with open(p, "r", encoding="utf-8") as f:
            state = json.load(f)

    buffer: list = state.setdefault("ring_buffer", [])
    before_snapshot = [dict(e) for e in buffer]   # reversibility log: BEFORE-state

    all_emitted = bool(debate_summary.get("all_emitted", False))

    # ── SEGMENT 5 WIRING: route the verdict through the growth-policy tier gate. ──
    # A self-review that surfaces a STRUCTURAL finding (debate.structural_findings > 0)
    # is NOT auto-committed as Tier-1 — it is flagged for reviewer approval, consistent
    # with how g2_sleep_pass_i() holds structural candidates. This is deterministic and
    # zero-LLM; the classifier reads only fields present on the record.
    tier = 1
    structural = False
    try:
        from giants.g2_growth_policy import g2_classify_tier as _classify
    except ImportError:  # pragma: no cover — direct-script fallback when not a package
        import sys as _sys
        if os.path.join(_HERE, "giants") not in _sys.path and _HERE not in _sys.path:
            _sys.path.insert(0, _HERE)
        try:
            from g2_growth_policy import g2_classify_tier as _classify  # type: ignore
        except ImportError:
            _classify = None
    if _classify is not None:
        structural_findings = int(debate_summary.get("structural_findings", 0) or 0)
        provisional = {
            "role": "SELF_REVIEW_VERDICT",
            # Promote to Tier-2 signal iff the debate flagged a structural finding.
            "rewrites_identity_text": False,
            "adds_archetype": False,
            "kind": "anchor_migration" if structural_findings > 0 else None,
        }
        _c = _classify(provisional)
        tier = int(_c["tier"])
        structural = (tier == 2 and structural_findings > 0)

    if not all_emitted:
        status = "held_anti_silence"
    elif structural:
        # Structural self-review finding: log it, but do NOT auto-commit — await reviewer.
        status = "pending_user_approval"
    else:
        status = "committed"

    record = {
        "role": "SELF_REVIEW_VERDICT",
        "tier": tier,
        "status": status,
        "ts": ts,
        "session_count": int(debate_summary.get("session_count", 0) or 0),
        "report_text": str(report_text or ""),
        "debate": {
            "approve": int(debate_summary.get("approve", 0)),
            "redirect": int(debate_summary.get("redirect", 0)),
            "error_planets": list(debate_summary.get("error", []) or []),
            "all_emitted": all_emitted,
        },
        "before": before_snapshot,   # reversibility log — exact walk-back possible
    }
    if structural:
        record["growth_policy"] = {
            "tier": 2,
            "reason": f"Self-review flagged {structural_findings} structural finding(s) — reviewer approval required.",
            "signals": [f"self_review_structural_findings={structural_findings}"],
        }
    buffer.append(record)
    if persist:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    return record


def save_swarm(swarm: dict, path: str | None = None) -> None:
    """Write the Ring's swarm store back to disk. Used by compression / pruning."""
    p = path or _SWARM_PATH
    with open(p, "w", encoding="utf-8") as f:
        json.dump(swarm, f, indent=2, ensure_ascii=False)


def compress_older_swarm_entries(swarm: dict,
                                 keep_count: int | None = None,
                                 min_mass: float | None = None) -> tuple[list[dict], list[dict]]:
    """Compress the Ring's OLDER swarm entries rather than hard-deleting them.

    WHY COMPRESSION AND NOT DELETION (John's call, Segment 2):
      The real question is never "which single memory dies?" — it's how old-but-still-
      relevant material condenses into less. Decay already sheds what's truly gone
      (mass < MIN_ENTRY_MASS). What remains below that line but above nothing is the
      "faded tail": still technically present, low mass, no longer worth full recall.
      Instead of deleting it, we MERGE a group of faded entries into one compacted
      record so the trace survives in reduced form — nothing is lost, just densified.

    HOW IT WORKS (pure math + JSON, zero LLM calls):
      1. Split live entries (mass >= min_mass) from the faded tail (0 < mass < min_mass,
         or below MIN_ENTRY_MASS). The faded tail is the compression candidate pool.
      2. Within that pool, take the OLDEST `keep_count` entries and merge them into a
         single summary entry: content = concatenated snippets (PII-scrubbed on write),
         mass   = the MAX of the members (we keep the strongest signal; we never invent
                 mass by summing it, which would let decayed junk out-mass fresh memory).
      3. The merged record is tagged "compressed_from" with its source entry_ids so a
         future reader can tell it's a compaction, not a raw conversation.

    This is a pure function: it returns (kept_entries, faded_survivors). It does NOT
    touch disk — the caller decides whether to save_swarm(). That keeps the decision
    (and any /halt override) with whoever owns the write path.

    Parameters
    ----------
    swarm        : {"entries": [...]} loaded from disk.
    keep_count   : how many faded entries to merge into one compaction. Default: all of them
                   that are below min_mass (one big compaction). Pass a smaller number if
                   you want incremental compression across repeated runs.
    min_mass     : the decay line. Entries at/above it are "live" and never touched here.
                   Defaults to constants.MIN_ENTRY_MASS (D-011).

    Returns
    -------
    (kept_entries, faded_survivors)
      kept_entries   : all entries that should be written back (live + compactions + any
                       faded survivors not yet compressed). Same dict shape as input.
      faded_survivors: the subset of faded-tail entries still waiting to be compacted on a
                       future run (empty if keep_count covered them all).
    """
    import constants as C
    try:
        import memory as _mem_for_zone
        _zone_const = _mem_for_zone.ZONE_RING_SWARM
    except Exception:
        _zone_const = "ring_swarm"
    if min_mass is None:
        min_mass = float(getattr(C, "MIN_ENTRY_MASS", 0.05) or 0.0)

    entries = list(swarm.get("entries", []))
    live   = [e for e in entries if float(e.get("mass", 0)) >= min_mass]
    faded  = [e for e in entries if float(e.get("mass", 0)) < min_mass]

    # Oldest first (by creation_ts; fall back to last_accessed, then id) so "older data"
    # is the thing that compresses, exactly as intended.
    faded.sort(key=lambda e: (float(e.get("creation_ts", 0)),
                              float(e.get("last_accessed", 0)), str(e.get("entry_id", ""))))

    to_compress = faded[:keep_count] if keep_count is not None else list(faded)
    survivors   = faded[len(to_compress):]

    kept = list(live) + list(survivors)
    if to_compress:
        merged_content = " | ".join(str(e.get("semantic_content", ""))[:120] for e in to_compress).strip()
        max_mass   = max(float(e.get("mass", 0.05)) for e in to_compress) * 0.9
        now = time.time()
        kept.append({
            "entry_id": f"ring_compact_{int(now * 1000)}",
            "vector_position": list(live[0]["vector_position"] if live else [0.0, 0.3, 0.1]),
            "mass": round(max_mass, 6),
            "semantic_content": merged_content,
            "creation_ts": now,
            "last_accessed": now,
            "decay_rate": float(getattr(C, "DECAY_GAMMA_BASE", 0.02)),
            "ring_membership": True,
            "zone": _zone_const,
            "compressed_from": [e.get("entry_id") for e in to_compress],
        })
    return kept, survivors


# ─── SEGMENT 6: USER ACCESS API (Core Law #3 — property rights) ─────────────
#
# John can read, export, and delete the Ring's swarm at any time. NO system
# resistance, NO confirmation gate, NO LLM involved. These are pure file I/O.
# The philosophy: it's HIS memory space. He owns it. The system simply provides
# the handles.
#
# All four functions accept an optional `swarm_path` so tests can operate on
# temp files without touching live state. Defaults point to ring/swarm.json.

def user_read_swarm(swarm_path: str | None = None) -> list[dict]:
    """Return ALL swarm entries (including faded/below-min-mass) for the user.

    Unlike read_ring_swarm_entries() which filters by MIN_ENTRY_MASS, this gives
    John the FULL picture — everything stored. He can see what's fading, what's
    been compressed, etc. Core Law #3: full transparency to the owner.

    Returns a list of entry dicts sorted newest-first (by creation_ts desc).
    """
    swarm = load_swarm(swarm_path)
    entries = list(swarm.get("entries", []))
    entries.sort(key=lambda e: float(e.get("creation_ts", 0)), reverse=True)
    return entries


def user_export_swarm(output_path: str, swarm_path: str | None = None) -> int:
    """Export the full swarm to a JSON file at output_path. Returns entry count.

    The export is a faithful copy — same structure as ring/swarm.json but written
    to wherever John specifies. Useful for backup, inspection in another tool,
    or archival. No modification of the source store occurs.
    """
    swarm = load_swarm(swarm_path)
    entries = list(swarm.get("entries", []))
    # Write a clean JSON document with metadata header
    export_doc = {
        "exported_at": time.time(),
        "source": str(swarm_path or _SWARM_PATH),
        "entry_count": len(entries),
        "entries": entries,
    }
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_doc, f, indent=2, ensure_ascii=False)
    return len(entries)


def user_delete_entry(entry_id: str, swarm_path: str | None = None) -> bool:
    """Delete a single swarm entry by its ID. Returns True if found and removed.

    Immediate persistence. No undo (if John wants undo he keeps an export).
    Core Law #3: no resistance, no confirmation, it just happens.
    """
    p = swarm_path or _SWARM_PATH
    swarm = load_swarm(p)
    entries = swarm.get("entries", [])
    original_count = len(entries)
    new_entries = [e for e in entries if e.get("entry_id") != entry_id]
    if len(new_entries) == original_count:
        return False  # not found
    swarm["entries"] = new_entries
    save_swarm(swarm, p)
    return True


def user_wipe_swarm(swarm_path: str | None = None) -> int:
    """Delete ALL swarm entries. Returns the count of entries that were removed.

    This is the 'reset my memories' command. The store file remains (valid JSON,
    empty entries list) so the system doesn't crash on next load. Core Law #3:
    John's property, his call, zero resistance.
    """
    p = swarm_path or _SWARM_PATH
    swarm = load_swarm(p)
    count = len(swarm.get("entries", []))
    swarm["entries"] = []
    save_swarm(swarm, p)
    return count


def format_swarm_for_display(entries: list[dict], max_show: int = 20) -> str:
    """Format swarm entries as human-readable text for display in a terminal or chat.

    Shows entry_id (short), age, mass, and content snippet. Faded entries are
    marked with [FADED]. Compressed entries show their source count.
    """
    if not entries:
        return "(swarm is empty — no memories stored yet)"
    lines = []
    now = time.time()
    shown = 0
    for e in entries[:max_show]:
        eid = str(e.get("entry_id", "?"))[:16]
        mass = float(e.get("mass", 0))
        created = float(e.get("creation_ts", now))
        age_days = (now - created) / 86400.0
        content = str(e.get("semantic_content", ""))[:80]
        faded = " [FADED]" if mass < 0.05 else ""
        compressed = f" [compressed from {len(e['compressed_from'])} entries]" if e.get("compressed_from") else ""
        lines.append(f"  {eid:>16} | {age_days:6.1f}d ago | mass={mass:.4f}{faded} | {content}{compressed}")
        shown += 1
    if len(entries) > max_show:
        lines.append(f"  ... and {len(entries) - max_show} more (use export for full list)")
    return "\n".join(lines)


# ─── SELF-TEST (offline, no LM Studio) ──────────────────────────────────────

def _sanity() -> None:
    import tempfile

    print("=" * 64)
    print("ring.py — Phase 6 Segments 1-6 self-test (offline, no LM Studio)")
    print("=" * 64)
    all_ok = True

    # Use temp files so we don't clobber live persona/relationship data.
    tmp_dir = tempfile.mkdtemp(prefix="ring_test_")
    tmp_persona = os.path.join(tmp_dir, "persona.json")
    tmp_log = os.path.join(tmp_dir, "relationship_log.json")
    tmp_swarm = os.path.join(tmp_dir, "swarm.json")

    # --- 1. Persona load / save round-trip -----------------------------------
    test_persona = {
        "name": "TestBot",
        "personality_vector": [0.5, -0.2, 0.1],
        "model_id": "auto",
        "idle_state": "active",
        "voice_notes": "Dry, concise.",
        "swarm_ref": "ring/swarm.json",
        "relationship_log_ref": "ring/relationship_log.json",
    }
    with open(tmp_persona, "w") as f:
        json.dump(test_persona, f)

    loaded = load_persona(tmp_persona)
    ok1 = loaded["name"] == "TestBot" and loaded["personality_vector"][0] == 0.5
    mark = "PASS" if ok1 else "FAIL"
    print(f"\n[1] Persona load round-trip: [{mark}]")
    if not ok1:
        all_ok = False

    # --- 2. Relationship log fresh state -------------------------------------
    fresh_log = {
        "session_count": 0,
        "topic_history": [],
        "emotional_valence_history": [],
        "last_session_ts": None,
        "first_contact_ts": None,
        "notes": "",
    }
    with open(tmp_log, "w") as f:
        json.dump(fresh_log, f)

    rl = load_relationship_log(tmp_log)
    ok2 = rl["session_count"] == 0 and rl["topic_history"] == []
    mark = "PASS" if ok2 else "FAIL"
    print(f"[2] Fresh relationship log loads: [{mark}]")
    if not ok2:
        all_ok = False

    # --- 3. ring_inbound — first session, no history --------------------------
    inbound_first = ring_inbound("hello world", persona=test_persona, rel_log=fresh_log)
    ok3 = (inbound_first["text"] == "hello world"
           and inbound_first["context"]["session"] == 0
           and inbound_first["context"]["is_first_session"] is True
           and inbound_first["persona_name"] == "TestBot")
    mark = "PASS" if ok3 else "FAIL"
    print(f"[3] ring_inbound (first session): [{mark}]")
    if not ok3:
        all_ok = False

    # --- 4. Update log → second inbound shows session count + topic -----------
    updated = update_relationship_log(topic="quantum gravity", valence=0.3,
                                      log=fresh_log, persist=False)
    assert updated["session_count"] == 1
    inbound_second = ring_inbound("more stuff", persona=test_persona, rel_log=updated)
    ok4 = (inbound_second["context"]["session"] == 1
           and inbound_second["context"]["is_first_session"] is False
           and inbound_second["context"]["recent_topics"] == ["quantum gravity"])
    mark = "PASS" if ok4 else "FAIL"
    print(f"[4] ring_inbound (after session update): [{mark}]")
    if not ok4:
        all_ok = False

    # --- 5. ring_outbound — normal output ------------------------------------
    out_normal = ring_outbound("Here is my answer.", persona=test_persona)
    ok5 = out_normal.startswith("TestBot:") and "Here is my answer." in out_normal
    mark = "PASS" if ok5 else "FAIL"
    print(f"[5] ring_outbound (normal): [{mark}]")
    if not ok5:
        all_ok = False

    # --- 6. ring_outbound — idle-awareness line present -----------------------
    out_idle = ring_outbound("Here is my answer.", persona=test_persona, idle_minutes=15.0)
    ok6 = ("thinking while you were away" in out_idle and "TestBot:" in out_idle)
    mark = "PASS" if ok6 else "FAIL"
    print(f"[6] ring_outbound (idle 15min): [{mark}]")
    if not ok6:
        all_ok = False

    # --- 7. ring_outbound — idle line ABSENT below threshold ------------------
    out_active = ring_outbound("Here is my answer.", persona=test_persona, idle_minutes=2.0)
    ok7 = "thinking while you were away" not in out_active and "TestBot:" in out_active
    mark = "PASS" if ok7 else "FAIL"
    print(f"[7] ring_outbound (active, 2min): [{mark}]")
    if not ok7:
        all_ok = False

    # --- 8. Swarm load (empty) ------------------------------------------------
    with open(tmp_swarm, "w") as f:
        json.dump({"entries": []}, f)
    swarm = load_swarm(tmp_swarm)
    ok8 = isinstance(swarm.get("entries"), list) and len(swarm["entries"]) == 0
    mark = "PASS" if ok8 else "FAIL"
    print(f"[8] Swarm load (empty): [{mark}]")
    if not ok8:
        all_ok = False

    # --- 9. Live persona.json loads without error ------------------------------
    try:
        live_persona = load_persona()
        ok9 = isinstance(live_persona.get("name"), str) and len(live_persona["personality_vector"]) == 3
        mark = "PASS" if ok9 else "FAIL"
    except Exception as e:
        ok9 = False
        mark = f"FAIL ({e})"
    print(f"[9] Live persona.json loads: [{mark}]")
    if not ok9:
        all_ok = False

    # --- 10. Persona name is data, not hardcoded behaviour --------------------
    # Editing the JSON should change what ring_inbound reports — proves no hardcoding.
    test_persona2 = dict(test_persona)
    test_persona2["name"] = "Zara"
    inbound_zara = ring_inbound("hi", persona=test_persona2, rel_log=fresh_log)
    ok10 = inbound_zara["persona_name"] == "Zara" and "Zara:" in ring_outbound("x", persona=test_persona2)
    mark = "PASS" if ok10 else "FAIL"
    print(f"[10] Persona name is swappable data: [{mark}]")
    if not ok10:
        all_ok = False

    # Cleanup temp dir.
    for fp in (tmp_persona, tmp_log, tmp_swarm):
        try:
            os.remove(fp)
        except OSError:
            pass
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass

    # ── SEGMENT 2 TESTS ────────────────────────────────────────────────────────

    # --- 11. should_write_to_ring_swarm — write-everything default -------------
    # Segment 2 decision: the swarm is the Ring's short-term working memory, so we
    # write by DEFAULT and let D-011 decay + mass handle pruning (relational content
    # keeps more mass and survives longer; pure informational fades faster). Every
    # real session — including a neutral "python tutorial" or an empty/noise case —
    # still gets written. The parameters are kept for a future "max swarm size" cap.
    ok_w_rel   = should_write_to_ring_swarm("life update", 0.2, has_relational_content=True) is True
    ok_w_val   = should_write_to_ring_swarm("career plan", 0.4, has_relational_content=False) is True
    ok_neutral = should_write_to_ring_swarm("python tutorial", 0.0, has_relational_content=False) is True
    ok_none    = should_write_to_ring_swarm(None, None, has_relational_content=False) is True
    ok11 = ok_w_rel and ok_w_val and ok_neutral and ok_none
    mark = "PASS" if ok11 else "FAIL"
    print(f"[11] should_write_to_ring_swarm write-everything default: [{mark}]")
    if not ok11:
        all_ok = False

    # --- 12. make_ring_swarm_entry — position near personality vector ----------
    test_persona3 = {
        "name": "TestBot",
        "personality_vector": [0.5, 0.3, 0.1],
        "model_id": "auto", "idle_state": "active",
        "voice_notes": "test", "swarm_ref": "ring/swarm.json",
        "relationship_log_ref": "ring/relationship_log.json",
    }
    entry = make_ring_swarm_entry("we talked about the Jester idea", persona=test_persona3)
    pv = test_persona3["personality_vector"]
    pos = entry["vector_position"]
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(pos, pv)))
    ok_pos_near = dist < 0.10
    ok_zone     = entry["zone"] == "ring_swarm" and entry["ring_membership"] is True
    ok12 = ok_pos_near and ok_zone
    mark = "PASS" if ok12 else "FAIL"
    print(f"[12] make_ring_swarm_entry position/zone: [{mark}]  (dist={dist:.4f})")
    if not ok12:
        all_ok = False

    # --- 13. write + read round-trip via temp dir ------------------------------
    tmp_base = tempfile.mkdtemp(prefix="ring_swarm_test_")
    try:
        path, count = write_ring_swarm_entry(entry, base_dir=tmp_base)
        ok_wrote   = os.path.exists(path) and count == 1
        swarm_data = load_swarm(os.path.join(tmp_base, "ring", "swarm.json"))
        ok_read    = len(swarm_data["entries"]) == 1
        e0         = swarm_data["entries"][0]
        ok_content = "Jester idea" in e0.get("semantic_content", "")
        ok13 = ok_wrote and ok_read and ok_content
        mark = "PASS" if ok13 else "FAIL"
        print(f"[13] Swarm write+read round-trip: [{mark}]")
    except Exception as ex:
        ok13 = False
        print(f"[13] Swarm write+read round-trip: [FAIL ({ex!r})]")
    finally:
        import shutil
        try:
            shutil.rmtree(tmp_base)
        except OSError:
            pass
    if not ok13:
        all_ok = False

    # --- 14. PII guard fires on swarm write ------------------------------------
    tmp_base2 = tempfile.mkdtemp(prefix="ring_pii_test_")
    try:
        pii_entry = make_ring_swarm_entry(
            "call me at john@example.com please", persona=test_persona3)
        path2, _ = write_ring_swarm_entry(pii_entry, base_dir=tmp_base2)
        with open(path2, encoding="utf-8") as f:
            raw_disk = f.read()
        ok_scrubbed = "john@example.com" not in raw_disk and "[REDACTED]" in raw_disk
        mark = "PASS" if ok_scrubbed else "FAIL"
        print(f"[14] PII guard on swarm write: [{mark}]")
    except Exception as ex:
        ok_scrubbed = False
        print(f"[14] PII guard on swarm write: [FAIL ({ex!r})]")
    finally:
        import shutil
        try:
            shutil.rmtree(tmp_base2)
        except OSError:
            pass
    if not ok_scrubbed:
        all_ok = False

    # --- 15. read_ring_swarm_entries returns empty for fresh store --------------
    tmp_base3 = tempfile.mkdtemp(prefix="ring_empty_test_")
    os.makedirs(os.path.join(tmp_base3, "ring"), exist_ok=True)
    with open(os.path.join(tmp_base3, "ring", "swarm.json"), "w") as f:
        json.dump({"entries": []}, f)
    entries_empty = read_ring_swarm_entries(path=os.path.join(tmp_base3, "ring", "swarm.json"))
    ok15 = len(entries_empty) == 0
    mark = "PASS" if ok15 else "FAIL"
    print(f"[15] read_ring_swarm_entries (empty store): [{mark}]")
    if not ok15:
        all_ok = False
    import shutil
    try:
        shutil.rmtree(tmp_base3)
    except OSError:
        pass

    # --- 16. get_ring_memory_context returns top-N by mass ----------------------
    tmp_base4 = tempfile.mkdtemp(prefix="ring_ctx_test_")
    os.makedirs(os.path.join(tmp_base4, "ring"), exist_ok=True)
    all_entries = []
    for i, (content, m) in enumerate([("low", 0.1), ("mid", 0.5), ("high", 0.9)]):
        all_entries.append({
            "entry_id": f"test_{i}",
            "vector_position": [0.1 * i, 0.2, 0.3],
            "mass": m,
            "semantic_content": content,
            "creation_ts": time.time(),
            "last_accessed": time.time(),
            "decay_rate": 0.02,
            "ring_membership": True,
            "zone": "ring_swarm",
        })
    swarm_file = os.path.join(tmp_base4, "ring", "swarm.json")
    with open(swarm_file, "w") as f:
        json.dump({"entries": all_entries}, f)
    ctx = get_ring_memory_context(test_persona3, max_entries=2, swarm_path=swarm_file)
    ok_top_n = len(ctx) == 2 and ctx[0]["mass"] >= ctx[1]["mass"]
    mark = "PASS" if ok_top_n else "FAIL"
    print(f"[16] get_ring_memory_context top-N by mass: [{mark}]")
    if not ok_top_n:
        all_ok = False
    import shutil
    try:
        shutil.rmtree(tmp_base4)
    except OSError:
        pass

    # --- 17. Mass via cosine alignment (aligned vs anti-aligned vectors) --------
    aligned_a = [1.0] * 384
    aligned_b = [1.0] * 384
    e_aligned = make_ring_swarm_entry("aligned", persona=test_persona3,
                                      semantic_vec=aligned_a, consensus_vec=aligned_b)
    anti_sem = [1.0] + [0.0] * 383
    anti_con = [-1.0] + [0.0] * 383
    e_anti   = make_ring_swarm_entry("anti", persona=test_persona3,
                                     semantic_vec=anti_sem, consensus_vec=anti_con)
    ok_mass_aligned = e_aligned["mass"] > 0.5
    ok_mass_anti    = e_anti["mass"] < 0.1
    ok17 = ok_mass_aligned and ok_mass_anti
    mark = "PASS" if ok17 else "FAIL"
    print(f"[17] Mass via cosine (aligned={e_aligned['mass']:.3f}, anti={e_anti['mass']:.3f}): [{mark}]")
    if not ok17:
        all_ok = False

    # --- 18. Decay rate is D-011 base gamma -------------------------------------
    import constants as _C_test
    expected_decay = float(getattr(_C_test, "DECAY_GAMMA_BASE", 0.02))
    ok18 = abs(entry["decay_rate"] - expected_decay) < 1e-6
    mark = "PASS" if ok18 else "FAIL"
    print(f"[18] Decay rate = D-011 base gamma ({entry['decay_rate']:.4f}): [{mark}]")
    if not ok18:
        all_ok = False

    # --- 19. compress_older_swarm_entries — merge faded tail, keep live ----------
    # Build a swarm with 2 LIVE entries (mass >= 0.05) and 3 FADED ones (< 0.05).
    _now = time.time()
    def _mk(eid, mass, ts_offset):
        return {"entry_id": eid, "vector_position": [0.1, 0.2, 0.3], "mass": mass,
                "semantic_content": f"content for {eid}",
                "creation_ts": _now + ts_offset, "last_accessed": _now + ts_offset,
                "decay_rate": 0.02, "ring_membership": True, "zone": "ring_swarm"}
    swarm19 = {"entries": [
        _mk("live_a", 0.8, 0),   # live
        _mk("live_b", 0.4, 0),   # live
        _mk("fade_1", 0.03, -50),
        _mk("fade_2", 0.02, -40),
        _mk("fade_3", 0.01, -30),
    ]}
    kept19, surv19 = compress_older_swarm_entries(swarm19)
    # The 3 faded entries should collapse into exactly ONE compaction; both live survive.
    compacted = [e for e in kept19 if "compressed_from" in e]
    ok_live_survive   = any(e["entry_id"] == "live_a" for e in kept19) and \
                        any(e["entry_id"] == "live_b" for e in kept19)
    ok_one_compaction = len(compacted) == 1
    ok_source_tracked = compacted and sorted(compacted[0]["compressed_from"]) == ["fade_1", "fade_2", "fade_3"]
    ok_no_faded_left  = not any(e["entry_id"].startswith("fade_") for e in kept19)
    ok_mass_not_inflated = compacted and compacted[0]["mass"] <= 0.03 * 0.9 + 1e-9
    ok19 = (ok_live_survive and ok_one_compaction and ok_source_tracked
            and ok_no_faded_left and ok_mass_not_inflated)
    mark = "PASS" if ok19 else "FAIL"
    print(f"[19] compress_older_swarm_entries (faded->compaction): [{mark}]")
    if not ok19:
        all_ok = False

    # ── SEGMENT 4 TESTS (OFF path only — no LLM, fully offline) ────────────────

    import constants as _C_s4

    # A temp empty swarm file so the OFF/threshold paths have a valid store to read
    # (they return before using it, but we pass an explicit path to avoid touching the
    # live ring/swarm.json). Note: tmp_dir was already cleaned up above, so use a fresh dir.
    import tempfile as _tf_s4
    s4_tmpdir = _tf_s4.mkdtemp(prefix="ring_s4_test_")
    tmp_swarm_empty_for_s4 = os.path.join(s4_tmpdir, "swarm.json")
    with open(tmp_swarm_empty_for_s4, "w") as f:
        json.dump({"entries": []}, f)

    # --- 20. generate_idle_reflection OFF => pure no-op "" --------------------
    # Toggle is False by default; confirm the function returns empty string with
    # NO side effects and never reaches the LLM branch (which would raise without LM Studio).
    saved_toggle = getattr(_C_s4, "RING_IDLE_BEHAVIOR_ENABLED", False)
    try:
        _C_s4.RING_IDLE_BEHAVIOR_ENABLED = False
        r_off = generate_idle_reflection(test_persona3, minutes_silent=120.0,
                                         swarm_path=tmp_swarm_empty_for_s4)
        ok20 = (r_off == "")
    finally:
        _C_s4.RING_IDLE_BEHAVIOR_ENABLED = saved_toggle
    mark = "PASS" if ok20 else "FAIL"
    print(f"[20] generate_idle_reflection OFF => no-op \"\": [{mark}]")
    if not ok20:
        all_ok = False

    # --- 21. threshold gate: below IDLE_THRESHOLD_MINUTES returns "" ----------
    # Even with the toggle ON, a short silence must NOT trigger an LLM call.
    try:
        _C_s4.RING_IDLE_BEHAVIOR_ENABLED = True   # force ON to test the threshold branch
        r_below = generate_idle_reflection(test_persona3, minutes_silent=2.0,
                                           swarm_path=tmp_swarm_empty_for_s4)
        ok21 = (r_below == "")
    finally:
        _C_s4.RING_IDLE_BEHAVIOR_ENABLED = saved_toggle
    mark = "PASS" if ok21 else "FAIL"
    print(f"[21] generate_idle_reflection below threshold => no-op: [{mark}]")
    if not ok21:
        all_ok = False

    # --- 22. OFF path never imports the LLM chamber ---------------------------
    # Prove the offline guarantee: with toggle OFF, cognitive_chamber must NOT be a
    # newly-loaded module as a result of calling generate_idle_reflection (it may
    # already be imported by other tests in this process; we only assert our call
    # did not force it). We do this by confirming the OFF return happens before any
    # chamber import — i.e. monkeypatching sys.modules is overkill, so instead we
    # verify the function returns "" even when cognitive_chamber CANNOT be imported.
    import sys as _sys_s4
    real_module = _sys_s4.modules.get("cognitive_chamber")
    try:
        if real_module is not None:
            _sys_s4.modules["cognitive_chamber"] = None  # force ImportError on any lazy import
        _C_s4.RING_IDLE_BEHAVIOR_ENABLED = False
        r_nochamber = generate_idle_reflection(test_persona3, minutes_silent=120.0,
                                               swarm_path=tmp_swarm_empty_for_s4)
        ok22 = (r_nochamber == "")
    except Exception as ex:
        ok22 = False
    finally:
        if real_module is not None:
            _sys_s4.modules["cognitive_chamber"] = real_module
        else:
            _sys_s4.modules.pop("cognitive_chamber", None)
        _C_s4.RING_IDLE_BEHAVIOR_ENABLED = saved_toggle
    mark = "PASS" if ok22 else "FAIL"
    print(f"[22] OFF path works even without cognitive_chamber importable: [{mark}]")
    if not ok22:
        all_ok = False

    # Clean up Segment 4 temp dir.
    try:
        os.remove(tmp_swarm_empty_for_s4)
        os.rmdir(s4_tmpdir)
    except OSError:
        pass

    # ── SEGMENT 5A TESTS (OFF path + pure trigger logic — no LLM, fully offline) ─

    import constants as _C_s5
    s5_tmpdir = _tf_s4.mkdtemp(prefix="ring_s5_test_") if 's5_tmpdir' not in dir() else None  # reuse pattern below
    import tempfile as _tf_s5
    s5_tmpdir = _tf_s5.mkdtemp(prefix="ring_s5_test_")
    tmp_g2 = os.path.join(s5_tmpdir, "g2_selfmodel.json")
    with open(tmp_g2, "w") as f:
        json.dump({"id": "g2", "name": "G2 Self-Model", "ring_buffer": [], "contents": []}, f)

    _now_s5 = time.time()
    base_log = {"session_count": 30, "topic_history": ["sleep cycle design",
               "swarm compression", "grant decision"],
                "emotional_valence_history": [0.2], "last_session_ts": _now_s5,
                "first_contact_ts": _now_s5 - 2 * 86400, "notes": ""}

    # --- 23. trigger OFF (default) => no fire even at exact threshold -----------
    saved_t5 = getattr(_C_s5, "RING_SELF_REVIEW_ENABLED", False)
    try:
        _C_s5.RING_SELF_REVIEW_ENABLED = False
        r_off5 = check_self_review_trigger(dict(base_log), g2_state={"ring_buffer": []},
                                           now=_now_s5)
        ok23 = (r_off5["fire"] is False) and (r_off5["reason"] is None) \
            and os.path.exists(tmp_g2)  # file untouched by the no-op
    finally:
        _C_s5.RING_SELF_REVIEW_ENABLED = saved_t5
    mark = "PASS" if ok23 else "FAIL"
    print(f"[23] self-review trigger OFF => never fires (no side effects): [{mark}]")
    if not ok23:
        all_ok = False

    # --- 24. ON + session_count == threshold, no prior review => fires ----------
    try:
        _C_s5.RING_SELF_REVIEW_ENABLED = True
        r_due = check_self_review_trigger(dict(base_log), g2_state={"ring_buffer": []},
                                          now=_now_s5)
        ok24 = (r_due["fire"] is True) and (r_due["reason"] == "session_threshold") \
            and (r_due["sessions_since_last_review"] == 30)
    finally:
        _C_s5.RING_SELF_REVIEW_ENABLED = saved_t5
    mark = "PASS" if ok24 else "FAIL"
    print(f"[24] trigger ON at threshold => fires (session_threshold): [{mark}]")
    if not ok24:
        all_ok = False

    # --- 25. below threshold AND within one month => no fire --------------------
    try:
        _C_s5.RING_SELF_REVIEW_ENABLED = True
        early = dict(base_log); early["session_count"] = 10
        r_early = check_self_review_trigger(early, g2_state={"ring_buffer": []}, now=_now_s5)
        ok25 = (r_early["fire"] is False) and (r_early["reason"] is None)
    finally:
        _C_s5.RING_SELF_REVIEW_ENABLED = saved_t5
    mark = "PASS" if ok25 else "FAIL"
    print(f"[25] trigger below threshold & <1 month => no fire: [{mark}]")
    if not ok25:
        all_ok = False

    # --- 26. month boundary fires when sessions are low but a month passed ------
    try:
        _C_s5.RING_SELF_REVIEW_ENABLED = True
        oldlog = dict(base_log); oldlog["session_count"] = 3
        g2_old = {"ring_buffer": []}
        r_month = check_self_review_trigger(oldlog, g2_state=g2_old,
                                            now=_now_s5 + 40 * 86400)   # 40 days later
        ok26 = (r_month["fire"] is True) and (r_month["reason"] == "month_boundary")
    finally:
        _C_s5.RING_SELF_REVIEW_ENABLED = saved_t5
    mark = "PASS" if ok26 else "FAIL"
    print(f"[26] trigger ON, 40 days since first contact => month_boundary fires: [{mark}]")
    if not ok26:
        all_ok = False

    # --- 27. anti-double-fire: a logged review at count 30 blocks re-fire -------
    try:
        _C_s5.RING_SELF_REVIEW_ENABLED = True
        g2_reviewed = {"ring_buffer": [{
            "role": "SELF_REVIEW_VERDICT", "tier": 1, "status": "committed",
            "ts": _now_s5 - 3600, "session_count": 30,
            "report_text": "prior review", "debate": {"all_emitted": True},
            "before": []}]}
        r_again = check_self_review_trigger(dict(base_log), g2_state=g2_reviewed, now=_now_s5)
        ok27 = (r_again["fire"] is False) and (r_again["sessions_since_last_review"] == 0)
    finally:
        _C_s5.RING_SELF_REVIEW_ENABLED = saved_t5
    mark = "PASS" if ok27 else "FAIL"
    print(f"[27] anti-double-fire: same session after logged review => no re-fire: [{mark}]")
    if not ok27:
        all_ok = False

    # --- 28. report skeleton contains stats + capped recent topics --------------
    skel = build_g2_change_report_skeleton(dict(base_log), persona=test_persona3, max_topics=2)
    ok28 = ("Sessions completed: 30" in skel) and ("swarm compression; grant decision" in skel) \
        and ("sleep cycle design" not in skel)   # capped at last 2 topics
    mark = "PASS" if ok28 else "FAIL"
    print(f"[28] change-report skeleton: stats + topic cap respected: [{mark}]")
    if not ok28:
        all_ok = False

    # --- 29. verdict log: anti-silence HOLD (all_emitted=False) ------------------
    g2_29 = {"id": "g2", "ring_buffer": [{"role": "OTHER", "ts": _now_s5 - 10}]}
    rec_hold = log_self_review_verdict("report text A", 
                                      debate_summary={"all_emitted": False, "approve": 4,
                                                      "redirect": 3, "error": ["rebel:phase_b empty"],
                                                      "session_count": 30},
                                      g2_state=g2_29, persist=False, now=_now_s5)
    ok29 = (rec_hold["status"] == "held_anti_silence") \
        and (len(g2_29["ring_buffer"]) == 2) \
        and (g2_29["ring_buffer"][-1]["before"] == [{"role": "OTHER", "ts": _now_s5 - 10}])
    mark = "PASS" if ok29 else "FAIL"
    print(f"[29] verdict log: silenced debate => HELD, before-state captured: [{mark}]")
    if not ok29:
        all_ok = False

    # --- 30. verdict log: clean debate COMMITS + append-only to temp G2 file -----
    rec_ok = log_self_review_verdict("report text B",
                                     debate_summary={"all_emitted": True, "approve": 5,
                                                     "redirect": 2, "error": [],
                                                     "session_count": 30},
                                     g2_path=tmp_g2, persist=True, now=_now_s5)
    with open(tmp_g2, "r", encoding="utf-8") as f:
        on_disk = json.load(f)
    ok30 = (
        rec_ok["status"] == "committed"
        and len(on_disk["ring_buffer"]) == 1
        and on_disk["ring_buffer"][-1]["role"] == "SELF_REVIEW_VERDICT"
        and on_disk["ring_buffer"][-1].get("tier", 1) == 1   # Seg-5: plain verdict stays Tier 1
        and on_disk["ring_buffer"][-1]["before"] == []       # buffer was empty before
    )
    mark = "PASS" if ok30 else "FAIL"
    print(f"[30] verdict log: clean debate => committed, append-only on disk: [{mark}]")
    if not ok30:
        all_ok = False

    # --- 31a. Seg-5 tier gate: structural finding in the debate => Tier 2 hold --
    rec_struct = log_self_review_verdict("report text C",
                                         debate_summary={"all_emitted": True, "approve": 6,
                                                         "redirect": 1, "error": [],
                                                         "structural_findings": 2,
                                                         "session_count": 30},
                                         g2_state={"id": "g2", "ring_buffer": []},
                                         persist=False, now=_now_s5)
    ok31a = (rec_struct["status"] == "pending_user_approval") \
        and rec_struct.get("tier") == 2 \
        and rec_struct.get("growth_policy", {}).get("tier") == 2
    mark = "PASS" if ok31a else "FAIL"
    print(f"[31a] verdict log: structural finding => Tier-2 hold (pending_user_approval): [{mark}]")
    if not ok31a:
        all_ok = False

    # --- 31b. anti-silence still wins over structural (held_anti_silence) --------
    rec_held = log_self_review_verdict("report text D",
                                       debate_summary={"all_emitted": False, "approve": 6,
                                                       "redirect": 0, "error": ["hero:phase_b empty"],
                                                       "structural_findings": 1,
                                                       "session_count": 30},
                                       g2_state={"id": "g2", "ring_buffer": []},
                                       persist=False, now=_now_s5)
    ok31b = rec_held["status"] == "held_anti_silence"
    mark = "PASS" if ok31b else "FAIL"
    print(f"[31b] verdict log: silenced debate with structural finding => held (silence wins): [{mark}]")
    if not ok31b:
        all_ok = False

    # --- 32. live G2 file not polluted by the OFFLINE suite ---------------------
    # A live self-review run (Segment 5b) legitimately appends a SELF_REVIEW_VERDICT
    # to ring_buffer, so we tolerate that one shape. Everything else must be absent.
    with open(os.path.join(_HERE, "giants", "g2_selfmodel.json"), "r", encoding="utf-8") as f:
        live_g2 = json.load(f)
    rb = live_g2.get("ring_buffer", [])
    contents = live_g2.get("contents", [])
    # Every entry in ring_buffer must be a well-formed SELF_REVIEW_VERDICT
    ok32 = (contents == [])
    for e in rb:
        if not isinstance(e, dict) or e.get("role") != "SELF_REVIEW_VERDICT":
            ok32 = False
            break
        # required keys present and non-None
        for k in ("ts", "session_count", "status", "report_text", "debate", "before"):
            if k not in e or e[k] is None:
                ok32 = False
                break
    mark = "PASS" if ok32 else "FAIL"
    rb_note = f"({len(rb)} legit SELF_REVIEW entry/entries)" if rb else "(empty)"
    print(f"[32] live g2_selfmodel.json not polluted by offline tests {rb_note}: [{mark}]")
    if not ok32:
        all_ok = False

    # ─── SEGMENT 6 CHECKS: User Access API (Core Law #3) ──────────────────────
    s6_tmpdir = tempfile.mkdtemp(prefix="ring_s6_test_")
    s6_swarm = os.path.join(s6_tmpdir, "swarm.json")

    # Seed a temp swarm with 3 entries at different ages/masses
    _now_s6 = time.time()
    seed_entries = [
        {"entry_id": "s6_entry_A", "vector_position": [0.1, 0.2, 0.3],
         "mass": 0.85, "semantic_content": "discussed the grant application options",
         "creation_ts": _now_s6 - 7 * 86400, "last_accessed": _now_s6 - 7 * 86400,
         "decay_rate": 0.02, "ring_membership": True},
        {"entry_id": "s6_entry_B", "vector_position": [0.4, 0.1, 0.5],
         "mass": 0.30, "semantic_content": "talked about moons on gas giants",
         "creation_ts": _now_s6 - 3 * 86400, "last_accessed": _now_s6 - 2 * 86400,
         "decay_rate": 0.02, "ring_membership": True},
        {"entry_id": "s6_entry_C", "vector_position": [0.2, 0.3, 0.1],
         "mass": 0.03, "semantic_content": "mentioned the fishy smell in the room",
         "creation_ts": _now_s6 - 5 * 86400, "last_accessed": _now_s6 - 5 * 86400,
         "decay_rate": 0.02, "ring_membership": True},
    ]
    with open(s6_swarm, "w", encoding="utf-8") as f:
        json.dump({"entries": seed_entries}, f)

    # --- 33. user_read_swarm returns ALL entries (including faded), newest first --
    all_entries = user_read_swarm(swarm_path=s6_swarm)
    ok33 = (
        len(all_entries) == 3
        and all_entries[0]["entry_id"] == "s6_entry_B"
        and all_entries[-1]["entry_id"] == "s6_entry_A"
    )
    mark = "PASS" if ok33 else "FAIL"
    print(f"[33] user_read_swarm: all entries, newest-first order: [{mark}]")
    if not ok33:
        all_ok = False

    # --- 34. user_export_swarm writes valid JSON with metadata -------------------
    s6_export = os.path.join(s6_tmpdir, "export.json")
    exported_count = user_export_swarm(output_path=s6_export, swarm_path=s6_swarm)
    with open(s6_export, "r", encoding="utf-8") as f:
        exp_doc = json.load(f)
    ok34 = (
        exported_count == 3
        and exp_doc["entry_count"] == 3
        and len(exp_doc["entries"]) == 3
        and "exported_at" in exp_doc
        and "source" in exp_doc
    )
    mark = "PASS" if ok34 else "FAIL"
    print(f"[34] user_export_swarm: valid JSON with metadata header: [{mark}]")
    if not ok34:
        all_ok = False

    # --- 35. user_delete_entry removes exactly one, persists to disk -------------
    deleted = user_delete_entry("s6_entry_C", swarm_path=s6_swarm)  # the faded one
    with open(s6_swarm, "r", encoding="utf-8") as f:
        after_del = json.load(f)
    ok35d = (
        deleted is True
        and len(after_del["entries"]) == 2
        and all(e["entry_id"] != "s6_entry_C" for e in after_del["entries"])
    )
    # also confirm deleting a non-existent ID returns False
    deleted_missing = user_delete_entry("nonexistent_id", swarm_path=s6_swarm)
    ok35d = ok35d and (deleted_missing is False)
    mark = "PASS" if ok35d else "FAIL"
    print(f"[35] user_delete_entry: removes one, persists; missing ID => False: [{mark}]")
    if not ok35d:
        all_ok = False

    # --- 36. user_wipe_swarm clears all, leaves valid empty structure ------------
    wiped_count = user_wipe_swarm(swarm_path=s6_swarm)
    with open(s6_swarm, "r", encoding="utf-8") as f:
        after_wipe = json.load(f)
    ok36w = (
        wiped_count == 2
        and after_wipe["entries"] == []
    )
    mark = "PASS" if ok36w else "FAIL"
    print(f"[36] user_wipe_swarm: clears all, valid empty JSON remains: [{mark}]")
    if not ok36w:
        all_ok = False

    # --- 37. format_swarm_for_display handles both populated and empty lists -----# Re-seed for display test
    with open(s6_swarm, "w", encoding="utf-8") as f:
        json.dump({"entries": seed_entries}, f)
    entries_fmt = user_read_swarm(swarm_path=s6_swarm)
    display_text = format_swarm_for_display(entries_fmt)
    ok37f = (
        "s6_entry_B" in display_text
        and "[FADED]" in display_text
        and "grant application" in display_text
    )
    empty_display = format_swarm_for_display([])
    ok37f = ok37f and ("empty" in empty_display.lower())
    mark = "PASS" if ok37f else "FAIL"
    print(f"[37] format_swarm_for_display: shows entries + [FADED]; empty => message: [{mark}]")
    if not ok37f:
        all_ok = False

    # --- 38. Backdated context recall: after 7 days, entry_A (mass=0.85) still ----
    # appears in get_ring_memory_context() with sufficient mass to influence framing.
    # This simulates the Phase 6 acceptance test's "two sessions a week apart" scenario.
    s6_recall_swarm = os.path.join(s6_tmpdir, "swarm_recall.json")
    recall_entries = [
        {"entry_id": "recall_1", "vector_position": [0.3, 0.2, 0.4],
         "mass": 0.85, "semantic_content": "decided to apply for the access grant",
         "creation_ts": _now_s6 - 7 * 86400, "last_accessed": _now_s6 - 7 * 86400,
         "decay_rate": 0.02, "ring_membership": True},
        {"entry_id": "recall_2", "vector_position": [0.5, 0.1, 0.3],
         "mass": 0.60, "semantic_content": "discussed the moon testing results",
         "creation_ts": _now_s6 - 7 * 86400 + 3600, "last_accessed": _now_s6 - 5 * 86400,
         "decay_rate": 0.02, "ring_membership": True},
    ]
    with open(s6_recall_swarm, "w", encoding="utf-8") as f:
        json.dump({"entries": recall_entries}, f)

    ctx = get_ring_memory_context(max_entries=5, swarm_path=s6_recall_swarm)
    # Both entries should still be above MIN_ENTRY_MASS (0.05) after 7 days decay
    ok38 = (
        len(ctx) == 2
        and all(float(e["mass"]) >= 0.05 for e in ctx)
        and ctx[0]["entry_id"] == "recall_1"
    )
    mark = "PASS" if ok38 else "FAIL"
    print(f"[38] backdated context: 7-day-old entries still above MIN_ENTRY_MASS for recall: [{mark}]")
    if not ok38:
        all_ok = False

    # Cleanup Segment 6 temp files
    try:
        os.remove(tmp_g2)
        os.rmdir(s5_tmpdir)
        for fn in os.listdir(s6_tmpdir):
            os.remove(os.path.join(s6_tmpdir, fn))
        os.rmdir(s6_tmpdir)
    except OSError:
        pass

    print("\n" + "=" * 64)
    print(f"Ring sanity (Segs 1-6): {'ALL PASS' if all_ok else 'SOME FAILED — check above'}")


if __name__ == "__main__":
    _sanity()
