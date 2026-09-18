"""
Resonant Cognition v17 — Phase 0D/E: Waveform Collapse (superposition engine).

CONCEPT (John + Maya, see docs/future_3d_wavefield.md for the full "quantum engine"
vision this is a minimal reduction of):
    The QUESTION is the wave. Each of the 7 archetypes, hearing it, emits its own
    wave in embedding space (a vector = amplitude x semantic direction). The waves
    superpose: aligned voices reinforce (constructive), opposing voices cancel
    (destructive). "Observing" collapses the pattern into two readings:

        consensus field  -> what REMAINS  (the surviving, reinforced answer)
        tension field    -> what was LOST (amplitude cancelled by opposition)

    We keep BOTH. Tension is polarity-aware so we can tell a real debate apart from
    two weak voices washing out to zero noise (John's "both negatives agree" trap).

WAVE SPEECH MODES (toggle via C.WAVE_SPEECH_MODE):
    "vector"  (now) : each planet's wave = its semantic field-center, pulled toward the
                      input by relevance. Cheap: zero extra LLM calls ("dumb planets").
    "llm"     (later): each planet actually generates a short response via the Ring/chamber
                      model; that text is embedded into the wave vector. 7 distinct voices
                      genuinely debating. Same collapse math runs on top either way — only
                      step 1 changes, so flipping this flag is not a rewrite.

RUN: python -X utf8 collapse.py   (runs the double-split test)
"""

from __future__ import annotations

import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _HERE)

import json
import glob

import constants as C
from resonance import embed, _embed_batch, _norm, sigmoid as _sigmoid


# ─── PLANET WAVE CENTERS (cached field centers per archetype, 384-dim) ───────
# A planet's "home" wave direction = full embedding of its own identity text.
# We embed (id_flavor + ego_descriptor) from each planet JSON so the wave center
# lives in the SAME 384-dim space as the input question. This gives far better
# per-planet discrimination than projecting everything onto 3 coarse axes.

def _load_planet_identity() -> dict[str, str]:
    """Load {planet_id: identity_text} from planets/*.json."""
    out = {}
    for f in sorted(glob.glob(os.path.join(_HERE, "planets", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        pid = d["id"]
        text = (d.get("id_flavor", "") + ". " + d.get("ego_descriptor", "")).strip()
        out[pid] = text
    return out

_wave_center_cache: dict[str, list[float]] | None = None

def _planet_wave_centers() -> dict[str, list[float]]:
    """Return {planet_id: 384-dim unit direction} for wave emission.

    Embeds each planet's identity text via MiniLM. Cached after first call.
    In LLM mode this would instead be the embedding of each planet's generated speech;
    same dict shape so downstream code is unchanged.
    """
    global _wave_center_cache
    if _wave_center_cache is not None:
        return _wave_center_cache
    identities = _load_planet_identity()
    texts = list(identities.values())
    vectors = _embed_batch(texts)
    pids = list(identities.keys())
    _wave_center_cache = {}
    for pid, vec in zip(pids, vectors):
        n = _norm(vec) or 1.0
        _wave_center_cache[pid] = [v / n for v in vec]
    return _wave_center_cache


def _cos(u, w) -> float:
    num = sum(a * b for a, b in zip(u, w))
    den = _norm(list(u)) * _norm(list(w))
    return max(-1.0, min(1.0, num / den if den else 0.0))


def _unit(v):
    n = _norm(list(v)) or 1.0
    return [x / n for x in v]


# ─── STEP 1: each planet emits a wave (vector mode) ──────────────────────────

def emit_waves(input_vec, centers, masses,
               routed_weights: dict | None = None):
    """Vector-mode 'speech': each planet emits a wave.

    input_vec is the full 384-dim embedding of the question (NOT projected to 3 axes).
    Each planet's center is also 384-dim.

    Amplitude rules:
      Phase 0 default (routed_weights=None):
        amplitude = mass * max(0, cosine(input, center))   # constructive side only
      Phase 1 routed (routed_weights provided):
        amplitude = mass * routed_weight[pid]              # full replacement — the routing
                                                           # weight IS the loudness signal;
                                                           # multiplying by cosine again would
                                                           # double-count geometry. Reversible:
                                                           # pass None to get back to Phase 0.
        Planets missing from routed_weights fall back to the Phase-0 formula so a partial
        dict can never crash the pipeline or silence a planet silently.

    ALL planets in `centers` still get an entry — routing only changes loudness, it never
    filters (all 7 emit together; Q3 approval + John's "drowning out" reconfirmation).

    Returns {planet: {"dir": unit_center(384d), "amplitude": float}}.

    NOTE on RESONANCE_MULTIPLIER_ENABLED (Q4): OFF by default. When it is flipped ON in a
    later phase, the sigmoid multiplier would plug in as an additional post-collapse scaling
    of each planet's amplitude using its semantic-identity cosine — it deliberately does NOT
    live inside emit_waves because pair_map (which resonance pairs exist) only exists AFTER
    collapse() has run. Do not build dead code paths here while the flag is off.
    """
    input_unit = _unit(input_vec)
    waves = {}
    for pid, center in centers.items():
        cdir = _unit(center)
        if routed_weights is not None and pid in routed_weights:
            amplitude = masses.get(pid, 1.0) * max(0.0, float(routed_weights[pid]))
        else:
            align = _cos(input_unit, cdir)              # -1..+1 in full 384-dim space
            relevance = max(0.0, align)                 # constructive side only (Phase-0 path)
            amplitude = masses.get(pid, 1.0) * relevance
        waves[pid] = {"dir": cdir, "amplitude": amplitude}
    return waves


# ─── STEP 2: superpose -> consensus + tension (the collapse) ────────────────

def collapse(waves):
    """Superpose all planet wave-vectors and read the interference pattern.

    Works in whatever dimensionality the wave dirs are (currently 384).

    Returns a dict with:
      consensus_vector : sum of all wave vectors            (what remains — reinforced answer)
      total_energy     : ||consensus||                       (how strong the surviving signal is)
      raw_energy       : sum of individual amplitudes        (energy BEFORE interference)
      tension          : polarity-aware measure of what was CANCELLED (the debate), see below
      pair_map         : per-pair {a,b: {"align":cos, "cancelled":float}} — John's 7-stone nodes
    """
    dim = len(next(iter(waves.values()))["dir"])
    vectors = [[w["amplitude"] * comp for comp in w["dir"]] for w in waves.values()]
    consensus = [sum(v[i] for v in vectors) for i in range(dim)]

    raw_energy   = sum(w["amplitude"] for w in waves.values())
    total_energy = _norm(consensus)

    # TENSION (what was lost): the difference between energy going in and energy surviving.
    #   tension_raw = max(0, raw - consensus). A big gap means real amplitude got cancelled.
    tension_raw  = max(0.0, raw_energy - total_energy)

    # Polarity-aware filter (John's "both negatives agree" trap): a cancellation only counts as
    # genuine *debate* if it came from at least two HIGH-amplitude opponents that were opposed.
    # Two tiny waves cancelling to ~zero is noise, not disagreement -> down-weighted heavily.
    amps = [w["amplitude"] for w in waves.values()]
    top2 = sorted(amps, reverse=True)[:2]
    meaningful = min(top2[0], top2[1]) if len(top2) == 2 else 0.0   # the weaker of the two loudest
    polarity_factor = max(0.0, meaningful / (max(amps) or 1.0))     # 1.0 only if BOTH loud voices opposed

    tension = tension_raw * (0.5 + 0.5 * polarity_factor)          # noise floor halved, real debate kept

    # Per-pair cancellation map: which two planets cancelled/reinforced where.
    pids = list(waves.keys())
    pair_map = {}
    for i in range(len(pids)):
        for j in range(i + 1, len(pids)):
            a, b = pids[i], pids[j]
            align = _cos(waves[a]["dir"], waves[b]["dir"])          # +1 agree, -1 oppose, 0 neutral
            # Cancellation only bites when BOTH actually spoke (have amplitude).
            both_spoke = min(waves[a]["amplitude"], waves[b]["amplitude"])
            cancelled = both_spoke * max(0.0, -(align))             # opposes -> positive cancellation
            pair_map[f"{a}|{b}"] = {"align": round(align, 3), "cancelled": round(cancelled, 4)}

    return {
        "consensus_vector": [round(x, 4) for x in consensus],
        "total_energy": round(total_energy, 4),
        "raw_energy": round(raw_energy, 4),
        "tension_raw": round(tension_raw, 4),
        "tension": round(tension, 4),
        "polarity_factor": round(polarity_factor, 3),
        "pair_map": pair_map,
    }


# ─── STEP 1 (LLM MODE) — placeholder for the 7 distinct voices ──────────────

def emit_waves_llm(question: str, centers, masses):
    """FUTURE (Phase 2): generate one short 'piece' per archetype via the Ring/chamber LLM,
    embed each -> wave vector. NOT implemented yet. Interface mirrors emit_waves so
    C.WAVE_SPEECH_MODE can flip without touching collapse(). See docs/future_3d_wavefield.md.

    ─── PHASE-2 TODO (decided 2025, do BEFORE writing this function) ──────────────
    DECISION: single batched call. One LLM generation produces all 7 labeled stanzas at once:
        prompt -> "As each archetype respond in <=40 words:\nSAGE:...\nMAGICIAN:...\n..."
        split on labels -> embed each stanza -> 7 wave vectors -> collapse().
    WHY BATCHED (not 7 sequential calls): latency. On a 24GB 4090 + 27B Q4, 7 sequential
      generations = ~7-15s/prompt; one batched gen of 7 short stanzas ~= ~1-2s total.
    CORRECTNESS IS UNAFFECTED BY ORDER: collapse() superposes a SET of vectors — there is no
      arrival sequence. "All 7 speak at once" (John's vision) is satisfied by the superposition,
      not by wall-clock simultaneity. The invariant to preserve is: all 7 present, none filtered.
    TRUNCATE EACH VOICE HARD (~40 tokens): the wave math only needs each voice's DIRECTION
      (meaning), not prose length. Shorter = faster + cheaper + more faithful to "one note."
    WATCH FOR PROMPT BLEED: in one batched call, later stanzas can be influenced by earlier ones
      (the model "hears" SAGE before writing MAGICIAN). Mitigations to evaluate during Phase 2:
        - order labels least-to-most dominant, or randomize order per call;
        - strong delimiters / explicit "do not reference the other archetypes" instruction;
        - A/B: batched vs. 7 separate system-prompt calls — if bleed measurably distorts
          per-voice direction (check via cosine drift between modes), fall back to option 2.
    OPTIONAL CROSS-ARGUMENT INJECTION (captures John's "overlap + complexity" goal cheaply):
        feed each voice not just its archetype prompt but the strongest opposing/resonating
        positions from pair_map (already computed in collapse()) — e.g. SAGE also hears how
        RULER will push back and engages with it. Zero training, fully reversible.
    HARDWARE NOTE: 27B Q4 (~17-18GB) fits the 4090's 24GB VRAM with headroom; engine overhead
      is ~200MB RAM total. The bottleneck when voices go live is LATENCY/TOKENS (x7), not memory.
    ─── FAR-FUTURE IDEA (NOT for this project — recorded so it isn't lost) ─────────
    "Train 7 replacement LLMs, one per archetype (each on its home questions + cross-arguments),
    deploy as a new voice set." VERDICT: shelved. As framed it yields 7 close cousins from the
    same base (less distinct, not more complex), bakes identity into weights and destroys the
    "identity travels with position" property, costs 7x training for this stage, and pre-empts
    measuring whether LLM voices even feel right. Its GOOD SEED = richer overlap/complexity in a
    SINGLE model via debate-transcript fine-tuning (1x cost, preserves distinctness + adds
    nuance) — revisit only if/when per-voice depth becomes a real requirement.
    ──────────────────────────────────────────────────────────────────────────────
    """
    raise NotImplementedError(
        "LLM wave-speech mode is a later phase. It requires the Ring/chamber model to generate "
        "one short 'piece' per archetype, then embed each. The collapse() math already works on "
        "whatever wave vectors you hand it — only this emitter needs building.")


# ─── DARK MATTER FIELD (Phase 0G — Collective Unconscious) ────────────────

_dm_cache = None

def _load_dark_matter():
    """Load and cache the Dark Matter Field from dark_matter.json.
    
    Returns dict with 'vector_384d' (list of 384 floats) and 'amplitude' (float).
    Returns None if file doesn't exist or is malformed (graceful degradation:
    engine runs without the field, identical to pre-0G behavior)."""
    global _dm_cache
    if _dm_cache is not None:
        return _dm_cache if _dm_cache != "_none" else None
    try:
        path = os.path.join(_HERE, "dark_matter.json")
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        vec = d.get("vector_384d", [])
        amp = float(d.get("amplitude", 0.0))
        if len(vec) != 384 or amp <= 0.0:
            _dm_cache = "_none"
            return None
        # Normalize to unit vector for directional blending
        n = math.sqrt(sum(x * x for x in vec)) or 1.0
        _dm_cache = {"vec": [x / n for x in vec], "amplitude": amp}
        return _dm_cache
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        _dm_cache = "_none"
        return None


def _apply_dark_matter_pull(waves: dict, dm: dict) -> dict:
    """Rotate each wave's direction slightly toward the Dark Matter Field.
    
    This is a DIRECTIONAL PULL, not an additive wave. Each planet's unit direction
    vector is blended: new_dir = (1 - amp) * old_dir + amp * dm_vec. Then re-normalized.
    Energy (amplitude) is preserved; only angles shift subtly.
    
    At amplitude=0.08, each wave rotates ~4.6 degrees toward the DM field direction.
    Subtle enough to preserve planetary individuality, strong enough to prevent
    total incoherence on alien inputs."""
    dm_vec = dm["vec"]
    amp = dm["amplitude"]
    for pid in waves:
        w_dir = waves[pid]["dir"]
        blended = [wd * (1.0 - amp) + dv * amp for wd, dv in zip(w_dir, dm_vec)]
        n = math.sqrt(sum(x * x for x in blended)) or 1.0
        waves[pid]["dir"] = [x / n for x in blended]
    return waves


# ─── MULTI-PASS RECURSIVE FEEDBACK (Phase 0H — the Echo) ────────────────────
# "Waves reacting to waves." After a superposition pass we feed that result back into
# the planets so they feel how the group reacted and adjust posture BEFORE observing.
# Two forces, both GUESS-tuned (see constants):
#   1. REPULSION from opposition — a planet moves its wave direction AWAY from any voice
#      it cancelled against in the previous pass (the debate response / counter-ripple).
#   2. CONSENSUS PULL — every wave leans slightly toward the group consensus vector
#      (echo-chamber convergence). Kept LOW so individuality survives.
# Only planetary keys are adjusted; synthetic _ctx_* and _g2_bias waves pass through,
# so context memory is never distorted by the echo. Energy/amplitude is preserved —
# directions bend, nothing inflates (same discipline as the Dark Matter pull).

def _apply_echo(waves: dict, prev_result: dict) -> dict:
    """Adjust planetary wave directions using the previous pass's collapse result.

    Mutates and returns `waves`. `prev_result` is a collapse() output with 'pair_map'
    (per-pair {a|b: {align, cancelled}}) and 'consensus_vector'.
    """
    if not C.ECHO_ENABLED:
        return waves
    pair_map = prev_result.get("pair_map", {})
    consensus = prev_result.get("consensus_vector") or []
    cons_unit = _unit(consensus) if consensus else None
    tension_prev = max(0.0, float(prev_result.get("tension", 0.0)))
    # Global pullback: the tenser the field was, the more every voice retracts a touch.
    tension_retract = C.ECHO_TENSION_GAIN * min(tension_prev, 1.0)

    pids = [k for k in waves if not k.startswith("_")]
    max_amp = amps_max(waves) or 1.0   # normalizer so gains stay stable across loud/quiet fields
    # Build per-planet repulsion vector from its opposition pairs (align < 0).
    for pid in pids:
        wdir = waves[pid]["dir"]
        unit_dir = _unit(wdir)
        amp = max(0.0, waves[pid]["amplitude"])
        repel = [0.0] * len(unit_dir)
        for key, val in pair_map.items():
            a, b = key.split("|")
            if pid not in (a, b):
                continue
            other = b if pid == a else a
            align = float(val.get("align", 0.0))
            if align < 0.0 and amp > 0.0:          # genuine opposition, we actually spoke
                opp_dir = _unit(waves[other]["dir"])
                strength = C.ECHO_ALIGN_REPEL * min(1.0, -align) * (amp / max_amp)
                for i in range(len(unit_dir)):
                    repel[i] -= opp_dir[i] * strength
        # Consensus echo-chamber pull.
        if cons_unit is not None and amp > 0.0:
            for i in range(len(unit_dir)):
                repel[i] += cons_unit[i] * (C.ECHO_CONSENSUS_PULL * min(1.0, amp))

        blended = [unit_dir[i] + repel[i] for i in range(len(unit_dir))]
        n = math.sqrt(sum(x * x for x in blended)) or 1.0
        waves[pid]["dir"] = [x / n for x in blended]
        # Slight global amplitude retraction under high tension (feels the heat, pulls back).
        if tension_retract > 0.0:
            waves[pid]["amplitude"] = amp * (1.0 - 0.5 * tension_retract)
    return waves

def amps_max(waves: dict) -> float:
    """Largest amplitude among planetary + synthetic waves (normalizer for echo gains)."""
    return max((w["amplitude"] for w in waves.values()), default=0.0)


# ─── FULL PIPELINE (dumb/vector mode) ──────────────────────────────────────
def run_collapse(question: str,
                 session_history=None,
                 g2_bias_vector=None,
                 routed_weights=None):
    """Question -> embed (384-dim) -> each planet emits a wave in same space
         (+ optional prior-turn background waves + G2 bias wave) -> collapse.

    Args:
        question: the current user input string.
        session_history: list[(unit_dir_384d, amplitude), ...] from
            SessionMemory.get_background_waves(). If None/empty, runs stateless
            (identical to previous behavior — backward compatible).
        g2_bias_vector: tuple(unit_dir_384d, amplitude) from memory.load_g2_bias_wave(),
            or None. Adds a single persistent low-amplitude "mood" wave.
        routed_weights (Phase 1): optional {planet_id: weight} from
            routing.per_planet_weights(). When provided, planetary amplitudes become
            mass * routed_weight instead of the Phase-0 cosine-relevance path. Synthetic
            context/G2 waves are NOT affected by routing (they're not planets).

    Returns {"vec_norm":..., "waves": {pid:{dir,amplitude}}, "result": collapse(...)}.
    Extra context waves are stored under synthetic keys "_ctx_0", "_ctx_1", ... and
    "_g2_bias" so reports can show them without polluting the planet namespace.
    Note: 'dir' in waves is 384-dim; we store it for completeness but the report only
    prints amplitudes + consensus energy (printing 384 floats would be noise).
    """
    if C.WAVE_SPEECH_MODE == "llm":
        raise NotImplementedError("LLM mode emitter not built yet (see emit_waves_llm).")
    vec = embed(question)
    centers = _planet_wave_centers()
    waves = emit_waves(vec, centers, C.PLANET_MASSES, routed_weights=routed_weights)

    # Add prior-turn context waves as synthetic "planets" in the superposition.
    # Collapse guard (independent-review triage): validate each dir's length against the
    # canonical embedding dim BEFORE it enters the vector math. A zero-length / short dir
    # would otherwise flow into _unit() -> an empty/short wave, and the zip-based sums in
    # collapse() silently truncate the consensus vector to the shortest operand (garbage or
    # a later IndexError). We SKIP (and log) degenerate entries rather than crash — a failed
    # embed that persisted an empty question_vec shouldn't poison the whole field — but we
    # RAISE ValueError on a non-empty dir of the WRONG length, because that is a real bug in
    # whatever produced the history and must surface loudly instead of being silently dropped.
    expected_dim = int(getattr(C, "EMBEDDING_DIM", 384))
    if session_history:
        for i, (u_dir, amp) in enumerate(session_history):
            d = list(u_dir)
            n = len(d)
            if n == 0:
                print(f"[collapse] WARNING: session_history[{i}] has an EMPTY dir; skipping "
                      f"this context wave (a failed embed must not poison the superposition).")
                continue
            if n != expected_dim:
                raise ValueError(
                    f"run_collapse: session_history[{i}] dir length {n} != expected embedding "
                    f"dim {expected_dim}. A non-empty context wave of the wrong dimension is a "
                    f"bug in the history producer — refusing to silently truncate or pad it."
                )
            waves[f"_ctx_{i}"] = {"dir": d, "amplitude": float(amp)}

    # Add G2 bias wave (self-model mood) as one more synthetic entry.
    if g2_bias_vector is not None:
        u, a = g2_bias_vector
        waves["_g2_bias"] = {"dir": list(u), "amplitude": float(a)}

    # Phase 0G: Dark Matter Field directional pull (Collective Unconscious).
    # Subtly rotates all wave directions toward baseline human semantics.
    # Graceful degradation: if dark_matter.json is missing, this is a no-op.
    dm = _load_dark_matter()
    if dm is not None:
        waves = _apply_dark_matter_pull(waves, dm)

    # MULTI-PASS ECHO (Phase 0H): pass 1 = the initial splash above. Each further pass
    # feeds the previous collapse result back in so planets feel the reaction and adjust.
    # With ECHO_ENABLED=False or ECHO_PASSES=1 this loop never runs -> identical to pre-0H.
    result = collapse(waves)
    if C.ECHO_ENABLED:
        passes = max(1, int(C.ECHO_PASSES))
        for _ in range(passes - 1):
            waves = _apply_echo(waves, result)      # planets react to the last field
            result = collapse(waves)                # re-observe after they adjust

    # ── Q4: RESONANCE MULTIPLIER (post-collapse, toggleable) ─────────────────────
    # When enabled, each planet's amplitude is gently scaled by sigmoid(k*(cos_sim - thresh)).
    # This is a "you resonate with this question" nudge — planets whose semantic identity
    # aligns well with the input get a small boost; misaligned ones are slightly dampened.
    # It NEVER creates amplitude from zero (sigmoid below threshold ≈ 0, so quiet voices stay
    # near-zero) and it operates on ALREADY-COMPUTED amplitudes (post-collapse), so it cannot
    # change which planets participate in the interference — only their relative loudness after.
    # Reversible: flip RESONANCE_MULTIPLIER_ENABLED=False to get byte-identical pre-Q4 output.
    if C.RESONANCE_MULTIPLIER_ENABLED:
        input_unit = _unit(vec)
        for pid, w in waves.items():
            if pid.startswith("_"):   # skip synthetic context/G2 waves — not planets
                continue
            center = centers.get(pid)
            if center is None:
                continue
            sim = _cos(input_unit, _unit(center))
            multiplier = _sigmoid(C.RESONANCE_SIGMOID_K * (sim - C.RESONANCE_MULTIPLIER_THRESHOLD))
            # Clamp to avoid amplifying beyond 2x (gentle nudge, not a takeover).
            waves[pid]["amplitude"] *= min(multiplier, 2.0)
        result = collapse(waves)   # re-observe the field after the loudness adjustment

    return {"vec_norm": round(_norm(vec), 3), "waves": {p: w for p, w in waves.items()},
            "result": result, "echo_passes": (max(1, int(C.ECHO_PASSES)) if C.ECHO_ENABLED else 1)}


# ─── DOUBLE-SPLIT TEST (agreement vs opposition) ─────────────────────────────

def _fmt_report(label: str, out: dict):
    res = out["result"]
    print(f"\n=== {label} ===")
    print(f"  input ||vec|| = {out.get('vec_norm', '?')}")
    spoken = sorted(
        ((p, w) for p, w in out["waves"].items() if w["amplitude"] > 0.05),
        key=lambda kv: kv[1]["amplitude"], reverse=True,
    )
    print("  voices that spoke (planet -> amplitude):")
    for p, w in spoken:
        print(f"     {p:<12} {w['amplitude']:.3f}")
    print(f"  CONSENSUS ||surviving|| = {res['total_energy']}  (384-dim, not printing full vec)")
    print(f"  energy in={res['raw_energy']:.3f}  surviving={res['total_energy']:.3f}  "
          f"tension(lost)={res['tension']:.3f}  [polarity={res['polarity_factor']}]")
    # Show the strongest cancellation nodes (John's 7-stone intersections).
    nodes = sorted(res["pair_map"].items(), key=lambda kv: kv[1]["cancelled"], reverse=True)
    top_nodes = [(k, v) for k, v in nodes if v["cancelled"] > 0.05][:3]
    print("  strongest cancellation nodes (a|b -> cancelled):")
    for k, v in top_nodes:
        a, b = k.split("|")
        print(f"     {a:<12} vs {b:<12} align={v['align']:+.3f}  cancelled={v['cancelled']}")


def _demo():
    print("Waveform Collapse — double-split test\n" + "=" * 56)

    # AGREEMENT: a question most archetypes can lean into constructively (rational, orderly).
    agree = "Please give me a clear, well-ordered, step-by-step analysis with solid evidence."
    out_a = run_collapse(agree)
    _fmt_report("AGREEMENT test", out_a)

    # OPPOSITION: a question that pits disruption vs order head-on (Rebel vs Ruler).
    oppose = "We should tear down the existing rules and break everything to start over from scratch."
    out_o = run_collapse(oppose)
    _fmt_report("OPPOSITION test", out_o)

    print("\n--- interpretation (me standing in for the Ring) ---")
    ra, ro = out_a["result"], out_o["result"]
    print(f"Agreement : surviving={ra['total_energy']:.3f}  tension={ra['tension']:.3f}")
    print(f"Opposition: surviving={ro['total_energy']:.3f}  tension={ro['tension']:.3f}")
    if ro["tension"] > ra["tension"]:
        print(">>> As intended: the opposition question produced MORE tension (debate) "
              "than the agreement one.")
    else:
        print(">>> NOTE: opposition did NOT out-tension agreement — worth reviewing anchor geometry.")


if __name__ == "__main__":
    _demo()
