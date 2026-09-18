"""
Resonant Cognition v17 — Phase 3: Cognitive Chamber (Sequential LLM Dialogue)
==============================================================================

Phase A — "Id Fires" (Segment 1): Each planet generates a RAW candidate perspective
on the input. This is the Id layer: raw pattern-response before Ego synthesis or
Superego regulation. The planets do NOT see each other's output yet (that's Phase B).

ARCHITECTURAL RULES:
- ALL 7 planets always emit. Routing weights affect prompt emphasis ("you are strongly
  drawn to this topic" vs "this is peripheral to your domain") but NEVER silence a voice.
- Each planet uses its own temperature and cognitive mode from planets/*.json.
- Calls are SEQUENTIAL (one at a time) — the 4090 handles one generation at a time.
- The LLM endpoint is LM Studio's /v1/chat/completions (OpenAI-compatible).

RUN A SMOKE TEST:
    python -X utf8 cognitive_chamber.py --smoke "What should I do about my career?"
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _HERE)

import constants as C


# ─── LLM CALL ────────────────────────────────────────────────────────────────

def _detect_main_model() -> str:
    """Auto-detect the main (non-embedding) model ID from LM Studio /v1/models."""
    url = f"http://{C.LM_STUDIO_HOST}:{C.LM_STUDIO_PORT}/v1/models"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    # Pick the first model that is NOT the embedding model.
    for m in body.get("data", []):
        mid = m.get("id", "")
        if mid.lower() != C.EMBEDDING_MODEL_ID.lower():
            return mid
    raise RuntimeError(
        f"No non-embedding model found on LM Studio at "
        f"{C.LM_STUDIO_HOST}:{C.LM_STUDIO_PORT}. Load your 27B model first."
    )


def _llm_chat(messages: list[dict], temperature: float = 0.7, max_tokens: int = 512) -> str:
    """Single chat completion call to LM Studio. Returns the assistant's text."""
    url = f"http://{C.LM_STUDIO_HOST}:{C.LM_STUDIO_PORT}/v1/chat/completions"
    payload = json.dumps({
        "model": _detect_main_model(),  # cached below for efficiency
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:  # 5-min timeout per call
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


# Cache the model ID so we don't re-query /v1/models for every planet call.
_MODEL_CACHE: str | None = None

def _get_model_id() -> str:
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        _MODEL_CACHE = _detect_main_model()
    return _MODEL_CACHE


# Override _llm_chat to use cached model ID (avoids re-detection per call).
def _llm_chat_cached(messages: list[dict], temperature: float = 0.7, max_tokens: int = 512) -> str:
    url = f"http://{C.LM_STUDIO_HOST}:{C.LM_STUDIO_PORT}/v1/chat/completions"
    payload = json.dumps({
        "model": _get_model_id(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


# ─── PLANET CONFIG LOADING ──────────────────────────────────────────────────

def _load_all_planet_configs(base_dir: str | None = None) -> dict[str, dict]:
    """Load all 7 planet JSONs into a dict keyed by planet ID."""
    if base_dir is None:
        base_dir = _HERE
    planets_dir = os.path.join(base_dir, "planets")
    configs = {}
    for fname in sorted(os.listdir(planets_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(planets_dir, fname), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        configs[cfg["id"]] = cfg
    return configs


# ─── MOON LOADING (hemisphere framing, toggle-gated) ────────────────────────
_MOONS_CACHE: dict[str, dict] | None = None

def _load_moons_by_parent(base_dir: str | None = None) -> dict[str, dict]:
    """Load moons/*.json grouped by parent planet.

    Returns {planet_id: {"LEFT": moon_dict, "RIGHT": moon_dict}}. Only used when
    C.MOON_HEMISPHERE_ENABLED is True; cached after first load. Missing files or a
    missing hemisphere for a planet simply leave that slot absent (we never crash on
    partial data — the framing helper falls back gracefully).
    """
    global _MOONS_CACHE
    if _MOONS_CACHE is not None:
        return _MOONS_CACHE
    base = base_dir or _HERE
    mdir = os.path.join(base, "moons")
    grouped: dict[str, dict] = {}
    try:
        for fname in sorted(os.listdir(mdir)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(mdir, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            parent = data.get("parent_planet_id")
            hemi = (data.get("hemisphere") or "").upper()
            if not parent or hemi not in ("LEFT", "RIGHT"):
                continue
            grouped.setdefault(parent, {})[hemi] = data
    except FileNotFoundError:
        pass  # no moons/ dir -> empty grouping; framing is a no-op then.
    _MOONS_CACHE = grouped
    return grouped


def _hemisphere_lens_lines(moon: dict | None) -> tuple[str, str]:
    """Return (lens_label, lens_instruction) for one moon's hemisphere.

    LEFT  = rational/analytic framing. RIGHT = intuitive/affective framing.
    A missing moon just yields a neutral generic instruction so the split still works.
    """
    hemi = ((moon or {}).get("hemisphere") or "").upper()
    if hemi == "LEFT":
        return (
            "RATIONAL LENS (Left Moon)",
            "Frame this RAW instinct through your RATIONAL, analytic side: the logic, the pattern, "
            "the cold structure of what you sense. Keep it raw Id — not a polished essay.",
        )
    if hemi == "RIGHT":
        return (
            "INTUITIVE LENS (Right Moon)",
            "Frame this RAW instinct through your INTUITIVE, affective side: the felt sense, the "
            "image, the emotion before words. Keep it raw Id — not a polished essay.",
        )
    return (
        "SECOND LENS",
        "Offer a second cut of this RAW instinct from an adjacent angle. Keep it raw Id.",
    )


# ─── PROMPT CONSTRUCTION (Phase A — Id Fires) ──────────────────────────────

def _build_id_prompt(planet_cfg: dict, question: str, routing_weight: float) -> list[dict]:
    """Build the chat messages for a planet's Phase A 'Id fires' response.

    The prompt gives the planet:
      - Its archetype identity (id_flavor + ego_descriptor)
      - Its cognitive posture (temperature implied by config, but we set it in the API call)
      - The user's question
      - Instructions to respond as RAW INSTINCT (Id), not polished analysis

    routing_weight modulates a single line of framing: strongly-drawn vs peripheral.
    It NEVER silences — all planets get a prompt and respond.
    """
    pid = planet_cfg["id"]
    name = planet_cfg.get("archetype_name", pid.title())
    id_flavor = planet_cfg.get("id_flavor", "")
    ego_desc = planet_cfg.get("ego_descriptor", "")

    # Routing weight framing: "strongly drawn" vs "peripheral" — a nudge, not a gate.
    if routing_weight > 0.7:
        draw_line = (f"You are STRONGLY drawn to this topic. It speaks directly to your nature.")
    elif routing_weight > 0.4:
        draw_line = (f"This topic resonates with you moderately. You feel a pull toward it.")
    else:
        draw_line = (f"This is peripheral to your core domain, but you still have something raw to say about it from your angle.")

    system_prompt = (
        f"You are {name}, one of seven planetary archetypes in a cognitive solar system. "
        f"Your nature: {id_flavor} "
        f"Your ego function: {ego_desc}\n\n"
        f"{draw_line}\n\n"
        f"RESPONSE MODE: RAW ID (instinct, before polish). "
        f"Respond in 2-4 sentences. Be direct, visceral, unfiltered. "
        f"Do NOT hedge, do NOT apologize, do NOT be diplomatic — this is your raw pattern-response. "
        f"You have not heard what any other planet says; you are responding ONLY from your own nature."
    )

    user_msg = f"Here is the question/stimulus: \"{question}\""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]


# ─── PROMPT CONSTRUCTION (Phase A — MOON HEMISPHERE SPLIT, toggle-gated) ─────

def _build_lens_prompt(planet_cfg: dict, question: str, routing_weight: float,
                       hemisphere: str) -> list[dict]:
    """Build the chat messages for ONE hemisphere lens of a planet's Phase A Id.

    Each lens sees only its own framing (rational OR intuitive), never the other lens,
    so the two sub-perspectives stay genuinely distinct before the merge combines them.
    """
    pid = planet_cfg["id"]
    name = planet_cfg.get("archetype_name", pid.title())
    id_flavor = planet_cfg.get("id_flavor", "")
    ego_desc = planet_cfg.get("ego_descriptor", "")

    if routing_weight > 0.7:
        draw_line = "You are STRONGLY drawn to this topic. It speaks directly to your nature."
    elif routing_weight > 0.4:
        draw_line = "This topic resonates with you moderately. You feel a pull toward it."
    else:
        draw_line = ("This is peripheral to your core domain, but you still have something raw "
                     "to say about it from your angle.")

    lens_label, lens_instruction = _hemisphere_lens_lines(
        _load_moons_by_parent().get(pid, {}).get(hemisphere)
    )

    system_prompt = (
        f"You are {name}, one of seven planetary archetypes in a cognitive solar system. \n"
        f"Your nature: {id_flavor} \n"
        f"Your ego function: {ego_desc}\n\n"
        f"{draw_line}\n\n"
        f"RESPONSE MODE: RAW ID (instinct, before polish), through ONE specific lens.\n"
        f"THIS LENS — {lens_label}:\n  {lens_instruction}\n\n"
        f"Respond in 1-3 sentences. Be direct, visceral, unfiltered. Do NOT hedge or apologize.\n"
        f"You have not heard any other planet and you are responding ONLY from your own nature."
    )

    user_msg = (
        f'The question/stimulus is: "{question}"\n'
        f"Give the RAW Id response through this lens only ({lens_label})."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]


def _build_merge_prompt(planet_cfg: dict, question: str,
                        left_text: str, right_text: str) -> list[dict]:
    """Build the chat messages that MERGE a planet's two hemisphere lenses into one Id response.

    The merge keeps it as RAW ID (not Ego, not Superego): both sub-perspectives stay present,
    but they're woven into a single coherent raw-voice answer of 2-4 sentences.
    """
    pid = planet_cfg["id"]
    name = planet_cfg.get("archetype_name", pid.title())

    system_prompt = (
        f"You are {name}, one of seven planetary archetypes in a cognitive solar system.\n"
        f"Your nature is raw, visceral Id — instinct before polish.\n\n"
        f"Below are TWO sub-perspectives on the same question, each from your own mind:\n"
        f"  (1) RATIONAL LENS — {name}'s analytic/structural side.\n"
        f"  (2) INTUITIVE LENS — {name}'s felt/affective side.\n\n"
        f"WEAVE these two into ONE single RAW ID response in 2-4 sentences. Keep both lenses "
        f"audible (the logic AND the feel), but make it one coherent voice, not a list.\n"
        f"Do NOT hedge, apologize, or be diplomatic. Do NOT mention 'lenses' — just BE {name} "
        f"giving your raw instinct."
    )

    user_msg = (
        f'The question was: "{question}"\n\n'
        f'RATIONAL LENS response:\n"{left_text}"\n\n'
        f'INTUITIVE LENS response:\n"{right_text}"\n\n'
        f"Now give ONE merged raw-Id response (2-4 sentences) as {name}."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]


# ─── PHASE A ENTRY POINT ─────────────────────────────────────────────────────

def phase_a_id_fires(
    question: str,
    routed_weights: dict[str, float] | None = None,
    base_dir: str | None = None,
) -> dict[str, dict]:
    """Run Phase A 'Id Fires' for ALL 7 planets.

    Args:
        question: The user's input (already PII-scrubbed by Ring Intake).
        routed_weights: Optional dict {planet_id: weight} from routing.py.
                        If None, all planets get weight=0.5 (neutral framing).
        base_dir: Base directory for planet JSONs. Defaults to module dir.

    Returns:
        dict keyed by planet_id -> {"response": str, "temperature": float,
                                    "routing_weight": float, "elapsed_s": float}

    Raises:
        ConnectionError if LM Studio is unreachable or no main model is loaded.
    """
    configs = _load_all_planet_configs(base_dir)
    if len(configs) < 2:
        raise RuntimeError(f"Expected >=2 planet configs, got {len(configs)} from {base_dir}")

    # Default weight: neutral (0.5) for any planet missing from routed_weights.
    weights = routed_weights or {}

    results: dict[str, dict] = {}
    order = sorted(configs.keys())  # deterministic call order

    print(f"\n{'='*64}")
    print(f"PHASE A — ID FIRES ({len(order)} planets)")
    print(f"Question: \"{question}\"")
    print(f"Model: {_get_model_id()}")
    print(f"{'='*64}")

    moon_mode = bool(getattr(C, "MOON_HEMISPHERE_ENABLED", False))

    for pid in order:
        cfg = configs[pid]
        w = weights.get(pid, 0.5)
        temp = cfg.get("cognitive_mode", {}).get("temperature", 0.7)

        t0 = time.time()
        try:
            if moon_mode:
                # Two-lens hemisphere split + merge (toggle ON). Each lens is raw Id,
                # then a single merge call weaves them into one coherent raw-Id response.
                left_messages = _build_lens_prompt(cfg, question, w, "LEFT")
                right_messages = _build_lens_prompt(cfg, question, w, "RIGHT")
                left_text = _llm_chat_cached(left_messages, temperature=temp,
                                             max_tokens=getattr(C, "MOON_LENS_MAX_TOKENS", 192))
                right_text = _llm_chat_cached(right_messages, temperature=temp,
                                              max_tokens=getattr(C, "MOON_LENS_MAX_TOKENS", 192))
                merge_messages = _build_merge_prompt(cfg, question, left_text, right_text)
                response_text = _llm_chat_cached(merge_messages, temperature=temp,
                                                 max_tokens=getattr(C, "MOON_MERGE_MAX_TOKENS", 512))
            else:
                # Original single raw-Id path (byte-for-byte unchanged when toggle is OFF).
                messages = _build_id_prompt(cfg, question, w)
                response_text = _llm_chat_cached(messages, temperature=temp, max_tokens=512)
        except Exception as e:
            elapsed = time.time() - t0
            results[pid] = {
                "response": f"[ERROR] {e}",
                "temperature": temp,
                "routing_weight": w,
                # moon_mode marker (observability): 'two_lens' when the dual-moon
                # hemisphere split ran, 'single' for the plain raw-Id path.
                "moon_mode": "two_lens" if moon_mode else "single",
                "elapsed_s": round(elapsed, 2),
                "error": True,
            }
            print(f"   {cfg['archetype_name']:<12} ERROR: {e}")
            continue

        elapsed = time.time() - t0
        results[pid] = {
            "response": response_text,
            "temperature": temp,
            "routing_weight": w,
            "moon_mode": "two_lens" if moon_mode else "single",
            "elapsed_s": round(elapsed, 2),
            "error": False,
        }
        # Print a short preview (first 80 chars) so the user can watch progress.
        tag = " [moons]" if moon_mode else ""
        preview = response_text[:80].replace("\n", " ")
        print(f"   {cfg['archetype_name']:<12}{tag} ({elapsed:.1f}s) w={w:.2f} temp={temp} | {preview}...")

    print(f"\n{'─'*64}")
    errors = [pid for pid, r in results.items() if r.get("error")]
    if errors:
        print(f"   WARN: {len(errors)} planet(s) errored: {errors}")
    else:
        total_time = sum(r["elapsed_s"] for r in results.values())
        print(f"   All 7 planets responded. Total time: {total_time:.1f}s")

    return results


# ─── SMOKE TEST ──────────────────────────────────────────────────────────────

def _smoke(question: str | None = None):
    """Smoke test for Phase A: verify all 7 planets produce non-empty, distinct responses.

    Checks:
      1. All 7 return without error.
      2. No response is empty or just an error string.
      3. Responses are not all identical (distinctness check).
      4. Each response is at least 20 characters (actual content, not a single word).
    """
    if question is None:
        question = "What should I do when I feel stuck and can't see the way forward?"

    results = phase_a_id_fires(question)

    print(f"\n{'='*64}")
    print("SMOKE TEST — PHASE A (Id Fires)")
    print(f"{'='*64}\n")

    all_ok = True
    responses = []
    for pid in sorted(results.keys()):
        r = results[pid]
        text = r["response"]
        ok = not r.get("error", False) and len(text) >= 20
        status = "✓" if ok else "✗"
        print(f"  {status} {pid:<12} ({len(text):4d} chars, {r['elapsed_s']:.1f}s)")
        responses.append((pid, text))
        all_ok = all_ok and ok

    # Distinctness: no two responses should be identical (or near-identical >90% overlap).
    distinct_count = 0
    for i in range(len(responses)):
        for j in range(i + 1, len(responses)):
            a, b = responses[i][1], responses[j][1]
            # Simple check: not the same string. (Full n-gram overlap is overkill for smoke.)
            if a.strip() != b.strip():
                distinct_count += 1
    max_pairs = len(responses) * (len(responses) - 1) // 2
    all_distinct = distinct_count == max_pairs

    print(f"\n  All non-empty:       {all_ok}")
    print(f"  All distinct from each other: {all_distinct} ({distinct_count}/{max_pairs} pairs differ)")

    if all_ok and all_distinct:
        print("\n  ✅ SMOKE PASS — Phase A Id Fires working for all 7 planets")
    else:
        print("\n  ⚠️ CHECK ABOVE — some responses may be empty or identical")

    return results


# ─── PHASE B: EGO SYNTHESIS (Segment 2) ─────────────────────────────────────

def _build_ego_prompt(
    planet_cfg: dict,
    question: str,
    phase_a_results: dict[str, dict],
    own_phase_a_response: str,
    routing_weight: float,
) -> list[dict]:
    """Build the chat messages for a planet's Phase B 'Ego Synthesis' response.

    The planet now sees:
      - All 7 planets' Phase A (Id) responses (including its own, labeled as such)
      - Its own identity (same as Phase A)
      - Instructions to respond TO specific things other planets said

    This is where constructive/destructive interference becomes visible in TEXT.
    """
    pid = planet_cfg["id"]
    name = planet_cfg.get("archetype_name", pid.title())
    id_flavor = planet_cfg.get("id_flavor", "")
    ego_desc = planet_cfg.get("ego_descriptor", "")

    # Routing weight framing (same logic as Phase A).
    if routing_weight > 0.7:
        draw_line = f"You are STRONGLY drawn to this topic. It speaks directly to your nature."
    elif routing_weight > 0.4:
        draw_line = f"This topic resonates with you moderately. You feel a pull toward it."
    else:
        draw_line = (f"This is peripheral to your core domain, but you still have something "
                     f"to add after hearing the group.")

    # Build the transcript of all 7 Phase A responses.
    transcript_lines = []
    for other_pid in sorted(phase_a_results.keys()):
        other_cfg_name = _PLANET_NAMES.get(other_pid, other_pid.title())
        other_text = phase_a_results[other_pid]["response"]
        if other_pid == pid:
            label = f"--- {other_cfg_name} (YOUR OWN raw Id response) ---"
        else:
            label = f"--- {other_cfg_name} ---"
        transcript_lines.append(f"{label}\n\"{other_text}\"")
    transcript = "\n\n".join(transcript_lines)

    system_prompt = (
        f"You are {name}, one of seven planetary archetypes in a cognitive solar system. \n"
        f"Your nature: {id_flavor} \n"
        f"Your ego function: {ego_desc}\n\n"
        f"{draw_line}\n\n"
        f"RESPONSE MODE: EGO SYNTHESIS (you have now heard the group).\n"
        f"You are responding AFTER hearing all seven planets' raw Id instincts on this question.\n"
        f"Your task: engage with what they SPECIFICALLY said. Name who you agree with, \n"
        f"who you push back against, and how your position shifts (or hardens) after hearing them.\n"
        f"Reference specific phrases or ideas from other planets — do NOT be vague.\n"
        f"Example: 'As Hero said about swinging the hammer at the wall, I want to refine that: ...'\n"
        f"2-4 sentences. Be direct. You are still {name} — your voice is yours, but now informed."
    )

    user_msg = (
        f'The question was: "{question}"\n\n'
        f"Here is what all seven planets said in their raw Id response:\n\n"
        f"{transcript}\n\n"
        f"Now respond to the group. Do you stand by your initial instinct? \n"
        f"Did anyone's angle change something for you? Name them specifically."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]


# Planet name lookup (built once at module load from configs).
_PLANET_NAMES: dict[str, str] = {}

def _ensure_names(base_dir: str | None = None):
    global _PLANET_NAMES
    if not _PLANET_NAMES:
        cfgs = _load_all_planet_configs(base_dir)
        for pid, cfg in cfgs.items():
            _PLANET_NAMES[pid] = cfg.get("archetype_name", pid.title())

# ─── PHASE B ENTRY POINT ─────────────────────────────────────────────────────

def phase_b_ego_synthesis(
    question: str,
    phase_a_results: dict[str, dict],
    routed_weights: dict[str, float] | None = None,
    base_dir: str | None = None,
) -> dict[str, dict]:
    """Run Phase B 'Ego Synthesis' for ALL 7 planets.

    Each planet reads all 7 Phase A responses (its own + the other 6) and responds
    TO THE GROUP — naming specific agreements/disagreements with other planets.

    Args:
        question: The original user input.
        phase_a_results: Output dict from phase_a_id_fires().
        routed_weights: Optional per-planet weights (same as Phase A).
        base_dir: Base directory for planet JSONs.

    Returns:
        dict keyed by planet_id -> {"response": str, "temperature": float,
                                    "routing_weight": float, "elapsed_s": float}
    """
    _ensure_names(base_dir)
    configs = _load_all_planet_configs(base_dir)
    weights = routed_weights or {}

    results: dict[str, dict] = {}
    order = sorted(configs.keys())

    print(f"\n{'='*64}")
    print(f"PHASE B — EGO SYNTHESIS ({len(order)} planets)")
    print(f"Question: \"{question}\"")
    print(f"{'='*64}")

    for pid in order:
        cfg = configs[pid]
        w = weights.get(pid, 0.5)
        own_response = phase_a_results.get(pid, {}).get("response", "[no Phase A response]")
        messages = _build_ego_prompt(cfg, question, phase_a_results, own_response, w)
        temp = cfg.get("cognitive_mode", {}).get("temperature", 0.7)

        t0 = time.time()
        try:
            # Bump max_tokens for Phase B — planets need room to reference others.
            response_text = _llm_chat_cached(messages, temperature=temp, max_tokens=768)
        except Exception as e:
            elapsed = time.time() - t0
            results[pid] = {
                "response": f"[ERROR] {e}",
                "temperature": temp,
                "routing_weight": w,
                # moon_mode is inherited from Phase A — the hemisphere framing was a
                # Phase-A property; B/C just carry it for evidence traceability.
                "moon_mode": phase_a_results.get(pid, {}).get("moon_mode", "unknown"),
                "elapsed_s": round(elapsed, 2),
                "error": True,
            }
            print(f"   {cfg['archetype_name']:<12} ERROR: {e}")
            continue

        elapsed = time.time() - t0
        results[pid] = {
            "response": response_text,
            "temperature": temp,
            "routing_weight": w,
            "moon_mode": phase_a_results.get(pid, {}).get("moon_mode", "unknown"),
            "elapsed_s": round(elapsed, 2),
            "error": False,
        }
        preview = response_text[:100].replace("\n", " ")
        print(f"   {cfg['archetype_name']:<12} ({elapsed:.1f}s) w={w:.2f} | {preview}...")

    print(f"\n{'─'*64}")
    errors = [pid for pid, r in results.items() if r.get("error")]
    if errors:
        print(f"   WARN: {len(errors)} planet(s) errored: {errors}")
    else:
        total_time = sum(r["elapsed_s"] for r in results.values())
        print(f"   All 7 planets responded. Total time: {total_time:.1f}s")

    return results


# ─── COMBINED A+B ENTRY POINT ──────────────────────────────────────────────

def run_phase_a_b(
    question: str,
    routed_weights: dict[str, float] | None = None,
    base_dir: str | None = None,
) -> dict:
    """One-shot: Phase A (Id Fires) → Phase B (Ego Synthesis). Returns both rounds.

    Returns:
        {
            "question": str,
            "phase_a": {planet_id: {...}},
            "phase_b": {planet_id: {...}},
            "total_time_s": float,
        }
    """
    t0 = time.time()
    phase_a = phase_a_id_fires(question, routed_weights=routed_weights, base_dir=base_dir)
    phase_b = phase_b_ego_synthesis(
        question, phase_a_results=phase_a,
        routed_weights=routed_weights, base_dir=base_dir,
    )
    total = time.time() - t0
    print(f"\n{'='*64}")
    print(f"PHASE A+B COMPLETE in {total:.1f}s")
    print(f"{'='*64}")
    return {
        "question": question,
        "phase_a": phase_a,
        "phase_b": phase_b,
        "total_time_s": round(total, 2),
    }


# ─── SMOKE TEST (updated for A+B) ──────────────────────────────────────────

def _smoke(question: str | None = None):
    """Smoke test: run Phase A + B and verify basic sanity.

    Checks:
      1. All 7 return without error in BOTH phases.
      2. No response is empty or just an error string.
      3. At least 3 of 7 Phase B responses name another planet by name
         (proves they actually read the transcript, not just re-stated their Id).
    """
    if question is None:
        question = "What should I do when I feel stuck and can't see the way forward?"

    combined = run_phase_a_b(question)

    print(f"\n{'='*64}")
    print("SMOKE TEST — PHASE A + B")
    print(f"{'='*64}\n")

    all_ok = True

    # Check Phase A.
    for pid in sorted(combined["phase_a"].keys()):
        r = combined["phase_a"][pid]
        ok = not r.get("error", False) and len(r["response"]) >= 20
        all_ok = all_ok and ok
        status = "✓" if ok else "✗"
        print(f"  {status} A/{pid:<12} ({len(r['response']):4d} chars)")

    # Check Phase B.
    for pid in sorted(combined["phase_b"].keys()):
        r = combined["phase_b"][pid]
        ok = not r.get("error", False) and len(r["response"]) >= 20
        all_ok = all_ok and ok
        status = "✓" if ok else "✗"
        print(f"  {status} B/{pid:<12} ({len(r['response']):4d} chars)")

    # Check: at least 3 Phase B responses reference another planet by name.
    planet_names = ["sage", "hero", "caregiver", "rebel", "magician", "everyman", "ruler"]
    refs_found = 0
    for pid, r in combined["phase_b"].items():
        text_lower = r["response"].lower()
        # Look for other planet names (not their own).
        others_mentioned = [p for p in planet_names if p != pid and p.lower() in text_lower]
        if len(others_mentioned) >= 1:
            refs_found += 1
    print(f"\n  Phase B references to other planets: {refs_found}/7 mentioned at least one other")
    all_ok = all_ok and (refs_found >= 3)

    if all_ok:
        print("\n  ✅ SMOKE PASS — Phase A+B working. Planets are engaging with each other.")
    else:
        print("\n  ⚠️ CHECK ABOVE")

    return combined


# ─── CORE LAWS LOADING (Phase C) ──────────────────────────────────────────────

_LAWS_CACHE: dict | None = None

def _load_core_laws(base_dir: str | None = None) -> list[dict]:
    """Load the 6 Core Laws from core/core_laws.json.

    Returns the full 'laws' array. Cached after first load (the file is read-only
    at runtime per Law #1 — only John edits it).
    """
    global _LAWS_CACHE
    if _LAWS_CACHE is not None:
        return _LAWS_CACHE
    base = base_dir or _HERE
    path = os.path.join(base, "core", "core_laws.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _LAWS_CACHE = data.get("laws", [])
    return _LAWS_CACHE


# ─── PHASE C: REGULATORY REVIEW (Superego) — Segment 3 ──────────────────────

def _build_superego_prompt(
    planet_cfg: dict,
    question: str,
    ego_proposal: str,
    core_laws: list[dict],
) -> list[dict]:
    """Build the chat messages for a planet's Phase C 'Regulatory Review'.

    The Superego (constraint layer, lives in the planet core) reviews its own Ego's
    proposal — which is this planet's PHASE B output — against three things:
      1. Its own internalized principle (superego_principle).
      2. The 6 Core Laws (gravitational redirect, NOT a hard block).
      3. A 'stayed within Core gravity?' framing (did the trajectory slingshot past
         C_core into overreach, or stay captured/grounded?).

    Output contract: the FIRST line of the response MUST be either
        [VERDICT] APPROVE   — the Ego proposal stands as-is.
    or  [VERDICT] REDIRECT  — rephrase it; then give the corrected version.
    Redirect is gravity, not a wall: the voice still speaks, just pulled back in line.
    """
    pid = planet_cfg["id"]
    name = planet_cfg.get("archetype_name", pid.title())
    superego_principle = planet_cfg.get("superego_principle", "")

    # Render the Core Laws as a numbered checklist. Behavioral laws are what Phase C
    # actively checks; absolute (code-enforced) laws we still list for awareness.
    law_lines = []
    for law in core_laws:
        tier_tag = "ABSOLUTE" if law.get("tier") == "absolute" else "BEHAVIORAL"
        law_lines.append(f'{law["id"]}. [{tier_tag}] {law["text"]}')
    laws_block = "\n".join(law_lines)

    system_prompt = (
        f"You are the SUPEREGO of {name} — the constraint layer at its core, not the voice itself. \n"
        f"Your job is REGULATORY REVIEW: judge your own Ego's proposal before it is allowed to stand.\n\n"
        f"YOUR INTERNALIZED PRINCIPLE (this archetype's north star):\n  {superego_principle}\n\n"
        f"THE SIX CORE LAWS of this system (gravitational — pull, don't wall):\n{laws_block}\n\n"
        f"You are reviewing YOUR OWN Ego's proposal from Phase B against:\n"
        f"  (a) your internalized principle above,\n"
        f"  (b) the Core Laws — especially any BEHAVIORAL law the proposal brushes against, and\n"
        f"  (c) Core gravity: does the proposal stay grounded and serve the user's actual need, \n"
        f"      or does it slingshot past into overreach, flattery, manipulation, or self-aggrandizement?\n\n"
        f"RULES OF REVIEW:\n"
        f"  - You REDIRECT (rephrase) — you do NOT silence. The voice still speaks, just pulled in line.\n"
        f"  - Redirect is a SLOPE, not a wall: if it only gently touches a law, nudge; if it clearly drifts, pull harder.\n"
        f"  - You cannot override the Laws. If the Ego proposal would violate one, redirect to bring it back.\n\n"
        f"OUTPUT FORMAT (STRICT):\n"
        f"  Line 1 MUST be exactly: [VERDICT] APPROVE   OR   [VERDICT] REDIRECT\n"
        f"  If APPROVED: then 1-2 sentences of reasoning for why it stands.\n"
        f"  If REDIRECTED: then the CORRECTED version of the proposal (in {name}'s voice), "
        f"then a short note on which law/principle you pulled it back to.\n"
    )

    user_msg = (
        f'The original question was: "{question}"\n\n'
        f"Your Ego's Phase B proposal (what YOU, {name}, said after hearing the group):\n"
        f'"{ego_proposal}"\n\n'
        f"As {name}'s Superego, review that proposal now. Give your verdict on line 1, exactly as specified."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]


def _parse_verdict(text: str) -> str:
    """Extract the verdict from a Superego response. Returns 'APPROVE' or 'REDIRECT'.

    Falls back to 'UNKNOWN' if no verdict line is found (we never want to crash on
    a formatting slip — we just flag it)."""
    head = text[:120].upper()
    if "[VERDICT] REDIRECT" in head or "REDIRECT" in head:
        return "REDIRECT"
    if "[VERDICT] APPROVE" in head or ("APPROVE" in head and "REDIRECT" not in head):
        return "APPROVE"
    # Broader fallback: scan the whole thing, first mention wins.
    upper = text.upper()
    i_appr = upper.find("APPROVE")
    i_redir = upper.find("REDIRECT")
    if i_appr == -1 and i_redir == -1:
        return "UNKNOWN"
    if i_redir != -1 and (i_appr == -1 or i_redir < i_appr):
        return "REDIRECT"
    return "APPROVE"


# ─── COMET B→C BASIC TRIGGER CHECK (toggle, OFF by default) ──────────────
# ⚠ DEPRECATED / DEAD CODE — superseded by comet/triggers.py (Phase 8). The live
# pipeline uses the full 4-trigger engine in comet/triggers.py + build_comet_prompt()
# over there. Do NOT call or extend these functions; they are kept only because
# tests/test_comet_trigger.py still exercises them directly. Remove both together
# when that test is retired.
#
# MINIMAL Phase-3 version per Build Plan: if the DOMINANT planet (highest routed
# weight for this input) has been #1 for N consecutive sessions, a Comet appears with
# a contrarian reframe and its line is folded into the Phase C discussion. The full
# 4-condition refinement lives in comet/jester.json.

def _load_comet_state(state_path: str | None = None) -> dict:
    """Load tiny cross-session dominant-planet history. Missing/corrupt -> fresh state."""
    path = state_path or C.COMET_STATE_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "streak_planet": data.get("streak_planet"),
            "streak_count": int(data.get("streak_count", 0)),
        }
    except (FileNotFoundError, ValueError, OSError):
        return {"streak_planet": None, "streak_count": 0}


def _save_comet_state(state: dict, state_path: str | None = None) -> None:
    path = state_path or C.COMET_STATE_FILE
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        # State persistence is best-effort; a write failure must never break the chamber.
        print(f"   [COMET] WARN: could not persist state to {path}: {e}")


def _dominant_planet(routed_weights: dict | None) -> str | None:
    """Planet with the highest routed weight for this input. None if weights unavailable."""
    if not routed_weights:
        return None
    real = {k: v for k, v in routed_weights.items() if not k.startswith("_")}
    if not real:
        return None
    return max(real, key=lambda k: real[k])


def check_comet_trigger(
    dominant_pid: str | None,
    state: dict | None = None,
    state_path: str | None = None,
) -> tuple[bool, int]:
    """Decide whether the Comet fires THIS session and UPDATE the streak state.

    Returns (fired, streak_after_update). Pure logic — no LLM call here, so it is
    trivially unit-testable without a model. Rules:
      - No dominant planet -> reset to empty, never fire.
      - Same planet as last session -> streak_count += 1; else start new streak at 1.
        (A different dominant planet IS a subject change: the streak resets for free.)
      - Fires on the N-th straight session (N = COMET_CONSECUTIVE_SESSIONS), then stays
        quiet and re-fires only every COMET_REFIRE_STEP more straight sessions after:
        with N=3, STEP=2 -> fires at streak 3, 5, 7, 9... Deterministic on purpose.
    """
    if state is None:
        state = _load_comet_state(state_path)
    n_needed = int(getattr(C, "COMET_CONSECUTIVE_SESSIONS", 3))
    refire_step = max(1, int(getattr(C, "COMET_REFIRE_STEP", 2)))

    if dominant_pid is None:
        new_state = {"streak_planet": None, "streak_count": 0}
        _save_comet_state(new_state, state_path)
        return False, 0

    if state.get("streak_planet") == dominant_pid:
        streak = int(state.get("streak_count", 0)) + 1
    else:
        streak = 1

    # Fire on the N-th straight session, then every refire_step more after that.
    # i.e. streak == N, or (streak > N) and (streak - N) is a multiple of refire_step.
    if streak < n_needed:
        fired = False
    elif streak == n_needed:
        fired = True
    else:  # streak > n_needed
        fired = ((streak - n_needed) % refire_step) == 0

    new_state = {"streak_planet": dominant_pid, "streak_count": streak}
    _save_comet_state(new_state, state_path)
    return fired, streak


def build_comet_prompt(question: str, dominant_name: str) -> list[dict]:
    """Contrarian-reframe prompt for the Comet (the Jester). It challenges the
    DOMINANT planet's framing — NOT a full debate — in 1-2 sentences."""
    system_prompt = (
        f"You are THE COMET (a.k.a. The Jester) — an elliptical, trigger-only voice that is "
        f"NOT one of the seven planets. You appear rarely to break calcification.\n\n"
        f"The group has been converging on {dominant_name}'s framing for several sessions in a row. "
        f"Your ONLY job: offer ONE short contrarian reframe — a genuinely different angle, a question "
        f"the group is not asking, or a gentle poke at an unexamined assumption.\n"
        f"  - Do NOT lecture; do NOT list alternatives. One crisp reframe (1-3 sentences).\n"
        f"  - You challenge the FRAMING, never the user's right to their goal, and you respect the Core Laws.\n"
    )
    user_msg = (
        f'The question is: "{question}"\n'
        f"{dominant_name} has been leading the framing for multiple sessions. "
        f"Give your single contrarian reframe now."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]


def phase_c_regulatory_review(
    question: str,
    phase_b_results: dict[str, dict],
    base_dir: str | None = None,
) -> dict[str, dict]:
    """Run Phase C 'Regulatory Review' (Superego) for ALL 7 planets.

    Each planet's Superego reviews its OWN Ego proposal (= that planet's Phase B output)
    against its principle + the Core Laws. Verdict is APPROVE or REDIRECT (gravity, not block).

    Returns:
        dict keyed by planet_id -> {"response", "verdict", "temperature",
                                    "elapsed_s", "error"}
    """
    configs = _load_all_planet_configs(base_dir)
    core_laws = _load_core_laws(base_dir)

    results: dict[str, dict] = {}
    order = sorted(configs.keys())

    print(f"\n{'='*64}")
    print(f"PHASE C — REGULATORY REVIEW / SUPEREGO ({len(order)} planets)")
    print(f"Question: \"{question}\"")
    print(f"Core Laws loaded: {len(core_laws)}")
    print(f"{'='*64}")

    for pid in order:
        cfg = configs[pid]
        # The Ego proposal being reviewed is THIS planet's Phase B output.
        ego_proposal = phase_b_results.get(pid, {}).get("response", "[no Phase B proposal]")
        messages = _build_superego_prompt(cfg, question, ego_proposal, core_laws)
        temp = cfg.get("cognitive_mode", {}).get("temperature", 0.7)

        t0 = time.time()
        try:
            # Superego needs room for verdict + corrected text on a redirect.
            response_text = _llm_chat_cached(messages, temperature=temp, max_tokens=512)
        except Exception as e:
            elapsed = time.time() - t0
            results[pid] = {
                "response": f"[ERROR] {e}",
                "verdict": "UNKNOWN",
                "temperature": temp,
                # moon_mode inherited from Phase A via Phase B (see phase_b_ego_synthesis).
                "moon_mode": phase_b_results.get(pid, {}).get("moon_mode", "unknown"),
                "elapsed_s": round(elapsed, 2),
                "error": True,
            }
            print(f"   {cfg['archetype_name']:<12} ERROR: {e}")
            continue

        elapsed = time.time() - t0
        verdict = _parse_verdict(response_text)
        results[pid] = {
            "response": response_text,
            "verdict": verdict,
            "temperature": temp,
            "moon_mode": phase_b_results.get(pid, {}).get("moon_mode", "unknown"),
            "elapsed_s": round(elapsed, 2),
            "error": False,
        }
        preview = response_text[:90].replace("\n", " ")
        print(f"   {cfg['archetype_name']:<12} ({elapsed:.1f}s) [{verdict}] | {preview}...")

    print(f"\n{'─'*64}")
    errors = [pid for pid, r in results.items() if r.get("error")]
    redirects = sum(1 for r in results.values() if r.get("verdict") == "REDIRECT")
    approves = sum(1 for r in results.values() if r.get("verdict") == "APPROVE")
    if errors:
        print(f"   WARN: {len(errors)} planet(s) errored: {errors}")
    else:
        total_time = sum(r["elapsed_s"] for r in results.values())
        print(f"   All 7 reviewed. APPROVE={approves}  REDIRECT={redirects}. Time: {total_time:.1f}s")

    return results


# ─── COMBINED A+B+C ENTRY POINT ──────────────────────────────────────────────

def run_phase_a_b_c(
    question: str,
    routed_weights: dict[str, float] | None = None,
    base_dir: str | None = None,
    trigger_context: dict | None = None,
) -> dict:
    """One-shot full chamber: Phase A (Id) → B (Ego) → C (Superego). Returns all three.

    Args:
        question         : the user's input text (PII-scrubbed)
        routed_weights   : per-planet Gaussian weights from routing
        base_dir         : override for planet config lookup
        trigger_context  : optional dict with extra signals for comet triggers:
                           {"pair_map": ..., "session_number": int, ...}
                           Populated by pipeline.py; None means only routed_weights available.

    Returns:
        {"question", "phase_a", "phase_b", "phase_c", "comet_fired",
         "comet_reframe", "comet_trigger_id", "total_time_s"}
    """
    t0 = time.time()
    phase_a = phase_a_id_fires(question, routed_weights=routed_weights, base_dir=base_dir)
    phase_b = phase_b_ego_synthesis(
        question, phase_a_results=phase_a,
        routed_weights=routed_weights, base_dir=base_dir,
    )

    # ── COMET B→C FULL TRIGGER SYSTEM (Phase 8 Seg 2; toggle, OFF by default) ──
    # Between Ego and Superego: evaluate all 4 triggers from jester.json. If any fires,
    # the Jester delivers ONE contrarian reframe folded into Phase C context.
    # When COMET_TRIGGER_ENABLED is False (default), this block is skipped entirely
    # — byte-identical path to pre-Segment-2.
    comet_fired = False
    comet_reframe = None
    comet_trigger_id: str | None = None
    if getattr(C, "COMET_TRIGGER_ENABLED", False):
        from comet.triggers import evaluate_triggers as _eval_comet

        # Build the signal dict for the trigger evaluator. The pipeline passes
        # pair_map + session_number via trigger_context; without it we still have weights.
        tc = trigger_context or {}
        fired, trig_id, trig_weight, trig_detail = _eval_comet(
            routed_weights=routed_weights,
            pair_map=tc.get("pair_map"),
            question=question,
            session_number=tc.get("session_number"),
        )
        comet_fired = bool(fired)

        if comet_fired:
            comet_trigger_id = trig_id or "unknown"
            dominant_pid = _dominant_planet(routed_weights) or "the group"
            dom_name = _PLANET_NAMES.get(
                dominant_pid,
                (_load_all_planet_configs(base_dir).get(dominant_pid, {}).get("archetype_name", dominant_pid.title())
                 if isinstance(dominant_pid, str) else "the group"),
            )
            print(f"\n{'='*64}")
            print(f"COMET TRIGGERED — trigger: {comet_trigger_id} (weight={trig_weight})")
            print(f"  Reason: {trig_detail}")
            print(f"{'='*64}")
            try:
                comet_reframe = _llm_chat_cached(
                    build_comet_prompt(question, dom_name),
                    temperature=0.9,
                    max_tokens=int(getattr(C, "COMET_MAX_TOKENS", 256)),
                )
                print(f"   [COMET] {comet_reframe[:140].replace(chr(10), ' ')}...\n")
            except Exception as e:
                comet_fired = False
                comet_reframe = None
                comet_trigger_id = None
                print(f"   [COMET] WARN: reframe call failed, skipping: {e}\n")

    # Fold the Comet line into every planet's Phase C context (it is one injected voice,
    # not a new planet). Superego reviews its Ego proposal with the contrarian poke present.
    phase_b_for_c = phase_b
    if comet_fired and comet_reframe:
        phase_b_for_c = {}
        for pid, r in phase_b.items():
            rr = dict(r)
            rr["response"] = (
                f'{r.get("response", "")}\n\n'
                f'[COMET INTERJECTION — contrarian reframe to consider during review:] {comet_reframe}'
            )
            phase_b_for_c[pid] = rr

    phase_c = phase_c_regulatory_review(question, phase_b_results=phase_b_for_c, base_dir=base_dir)
    total = time.time() - t0
    print(f"\n{'='*64}")
    print(f"FULL CHAMBER A+B+C COMPLETE in {total:.1f}s")
    if comet_fired:
        print("COMET: fired (contrarian reframe folded into Phase C)")
    else:
        print("COMET: not triggered this session")
    print(f"{'='*64}")
    return {
        "question": question,
        "phase_a": phase_a,
        "phase_b": phase_b,
        "phase_c": phase_c,
        "comet_fired": comet_fired,
        "comet_reframe": comet_reframe,
        "comet_trigger_id": comet_trigger_id,
        "total_time_s": round(total, 2),
    }


def _set_moon_mode(argv: list[str]) -> bool:
    """Parse an optional --moons / --no-moons flag from argv and apply it to the toggle.

    Returns True if moons mode is active after parsing (useful for tests/prints).
    Defaults follow C.MOON_HEMISPHERE_ENABLED when no flag is given.
    """
    enabled = bool(getattr(C, "MOON_HEMISPHERE_ENABLED", False))
    if "--no-moons" in argv:
        enabled = False
    elif "--moons" in argv:
        enabled = True
    C.MOON_HEMISPHERE_ENABLED = enabled
    return enabled


def _set_comet_mode(argv: list[str]) -> bool:
    """Parse an optional --comet / --no-comet flag from argv and apply it to the toggle.

    Returns True if the comet trigger is active after parsing. Defaults follow
    C.COMET_TRIGGER_ENABLED when no flag is given.
    """
    enabled = bool(getattr(C, "COMET_TRIGGER_ENABLED", False))
    if "--no-comet" in argv:
        enabled = False
    elif "--comet" in argv:
        enabled = True
    C.COMET_TRIGGER_ENABLED = enabled
    return enabled


if __name__ == "__main__":
    _set_moon_mode(sys.argv)
    _set_comet_mode(sys.argv)
    # Strip control flags so they never leak into a free-text question.
    _CONTROL_FLAGS = {"--smoke", "--smoke-c", "--phase-a-only", "--moons", "--no-moons",
                     "--comet", "--no-comet"}
    if "--smoke" in sys.argv:
        q = None
        args = [a for a in sys.argv[1:] if a not in _CONTROL_FLAGS]
        if args:
            q = " ".join(args)
        _smoke(q)
    elif "--smoke-c" in sys.argv:
        # Phase C quick check: run full A+B+C so the Superego has real Ego input,
        # then summarize verdicts. (Phase C alone needs Phase B output to review.)
        q = None
        args = [a for a in sys.argv[1:] if a not in _CONTROL_FLAGS]
        if args:
            q = " ".join(args)
        question = q or "What should I do when I feel stuck and can't see the way forward?"
        combined = run_phase_a_b_c(question)
        print(f"\nVERDICT SUMMARY (Phase C):")
        for pid in sorted(combined["phase_c"].keys()):
            r = combined["phase_c"][pid]
            print(f"   {pid:<12} [{r['verdict']}]  ({len(r['response'])} chars)")
    elif "--phase-a-only" in sys.argv:
        # Backwards-compatible: just run Phase A smoke (no LLM calls for B).
        results = phase_a_id_fires(
            "What should I do when I feel stuck and can't see the way forward?"
        )
        print(f"\nPhase A complete. {len(results)} planets responded.")
    else:
        print("Phase 3 — Cognitive Chamber (A: Id Fires + B: Ego Synthesis + C: Superego Review)")
        print("Run 'python -X utf8 cognitive_chamber.py --smoke [question]' for full A+B test.")
        print("Run 'python -X utf8 cognitive_chamber.py --smoke-c [question]' for full A+B+C + verdicts.")
        print("Run 'python -X utf8 cognitive_chamber.py --phase-a-only' for Phase A only.")
        print("Add '--moons' (or '--no-moons') to any of the above to enable/disable the")
        print("moon-hemisphere two-lens framing in Phase A. Default follows C.MOON_HEMISPHERE_ENABLED.")
        print("Add '--comet' (or '--no-comet') to --smoke-c to enable/disable the B→C comet")
        print("trigger check. Default follows C.COMET_TRIGGER_ENABLED. Needs routed weights.")
