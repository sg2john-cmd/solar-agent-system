"""
Resonant Cognition v17 — Phase 1: Routing / Spike Detection (in progress)
=========================================================================

Takes the input vector + CURRENT orbital state -> outputs ranked planet activations
with weights. NO LLM dialogue calls here; only the embedding model is allowed to be
touched, and even that lives behind a caller-supplied input vector so this module can
run fully offline against pre-embedded inputs during tuning.

ARCHITECTURAL RULE (John): the planets live on a SEPARATE "phase" from the logic.
The physics phase (integrator.py) owns positions — it seeds them, persists them to
planets/*.json as a snapshot, and advances them in memory with integrate_step(). This
module therefore NEVER re-reads stale JSON as if it were current state and NEVER
advances physics itself. It consumes whatever live `core` + `planets` objects it is
handed (i.e. the integrator's output after it has run). That is exactly what makes
"identity travels with position" true: same input vector, different live field ->
possibly a different ranking.

SEGMENT STATUS (small-segment build — do not assume later pieces exist yet):
  Segment 1 : DONE — load orbital state + compute blended per-planet FIELD CENTER
              (Q1 approval):   w * wave_center_384d + (1-w) * lifted_orbital_pos
  Segment 2 : DONE — composite field Psi(x), per-planet activation weights, core bending,
              angular_z metric (tuning spike)
  Segment 3 : DONE — routed weights wired into collapse.emit_waves/run_collapse;
              pure-Gaussian weight fix (no double-mass); routed_collapse() one-shot entry
  Segment 4 : DONE (2026-09-17) — test_routing.py: 20/20 checks PASS. Equal-mass/sigma A/B
              confirms live orbital geometry drives the ranking (top-2 identical BASE vs NEUTRAL
              on all 3 probes); mass/sigma fine-tune only. Evidence:
              tests/evidence/routing_segment4_20260917_101208.log

RUN A QUICK SMOKE (Segment 1 only — needs LM Studio for wave centers):
    python -X utf8 routing.py --smoke
"""

from __future__ import annotations

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _HERE)

import constants as C
import integrator as I          # load_core / load_planets (state SOURCE — physics phase)
from resonance import axes_to_384  # inverse of project_to_axes: [x,y,z] -> 384-dim lift


# ─── VECTOR MATH HELPERS (mirror collapse.py's _norm/_unit; kept local so this module
#     has no hard dependency on the collapse engine until Segment 3 wires them together.)

def _norm(v) -> float:
    return math.sqrt(sum(x * x for x in v)) or 1.0


def _unit(v):
    n = _norm(list(v))
    return [x / n for x in v]


# ─── STATE LOADING (delegates to the physics phase; never advances it) ─────────

def load_orbital_state(base_dir: str | None = None):
    """Load current core + planet orbital state via the integrator's loaders.

    IMPORTANT (separate-phase rule): this reads the SEED snapshot from JSON only so a
    fresh process has SOMETHING to route against. In a live session you must hand this
    module the SAME `core`/`planets` objects after integrator.integrate_step() has run,
    because that is where positions are actually advanced — the JSON files do not move.

    Returns (core: CoreState, planets: list[Planet]).
    """
    if base_dir is None:
        base_dir = _HERE
    core = I.load_core(base_dir)
    planets = I.load_planets(base_dir)
    return core, planets


# ─── FIELD CENTER (Segment 1 — Q1 approval) ─────────────────────────────────

def compute_field_center(planet_wave_center_384d: list[float],
                         planet_orbital_pos_xyz: list[float]) -> list[float]:
    """Blend a planet's semantic identity with its current orbital position.

        field_center = w * wave_center + (1 - w) * lifted_position   then normalize

    where `w = C.FIELD_POSITION_WEIGHT`:
        w = 1.0 -> pure semantic identity (static game map; position ignored)
        w = 0.0 -> pure orbital position (rigid spatial map; identity ignored)

    The orbital [x,y,z] is lifted into the SAME 384-dim space as the wave center via
    axes_to_384() so the two are actually comparable before blending. "Identity travels
    with position": the planet carries its psychological weight along its orbit, and the
    knob lets you trade identity-vs-position without rewriting anything.

    Both inputs may be unnormalized; we normalize each first so `w` is a true blend of
    unit directions rather than being skewed by one vector's magnitude (the lifted
    position's length scales with orbital radius, which would otherwise dominate).
    """
    w = C.FIELD_POSITION_WEIGHT
    identity = _unit(planet_wave_center_384d)
    pos_lifted = axes_to_384(tuple(planet_orbital_pos_xyz))
    position = _unit(pos_lifted)

    blended = [w * i + (1.0 - w) * p for i, p in zip(identity, position)]
    return _unit(blended)


def field_centers_for_all(wave_centers: dict[str, list[float]],
                          planets: list) -> dict[str, list[float]]:
    """Compute the blended field center for every planet.

    Args:
        wave_centers : {planet_id: 384-dim semantic identity} (collapse._planet_wave_centers())
        planets      : live Planet objects (position read from here — current state)
    Returns:
        {planet_id: blended_unit_field_center_384d}. Planets missing a wave center are
        skipped with their orbital position lifted alone (still defined, no crash).
    """
    out = {}
    for p in planets:
        wc = wave_centers.get(p.id)
        if wc is not None:
            out[p.id] = compute_field_center(wc, p.position)
        else:  # graceful: identity missing -> pure position center
            lifted = axes_to_384(tuple(p.position))
            out[p.id] = _unit(lifted)
    return out


# ─── SEGMENT 2: COMPOSITE FIELD + PER-PLANET WEIGHTS + CORE BENDING ─────────
# Design note (John's vision): all 7 planets STILL emit waves together and ALL get the
# prompt — routing never pre-selects or silences a planet. It only makes each of the 7
# voices' LOUDNESS responsive to live orbital geometry ("identity travels with position").
# collapse.py then superposes all 7 exactly as before. The "ranking" is a readout of the
# result, not a filter applied to emission.
#
# Distance metric (C.FIELD_DISTANCE_METRIC) is a TOGGLE so nothing is lost:
#   angular   : d = angle between unit directions (radians). Scale-invariant; immune to
#               the radius-gap problem where lifted positions sit at |v|~7-12 but inputs/
#               identities are unit (~1).
#   euclidean : d = straight-line 384-dim distance. Literal build-plan formula, more fragile.
#   angular_z : d = per-input z-score of the angular distances across all planets
#               (mean 0, sd 1 BY CONSTRUCTION). Why: MiniLM scatters real prompts ~90deg
#               from ALL archetype texts, so raw angular distances cluster in a narrow band
#               (~0.08 rad spread) and no sigma value can discriminate. Z-scoring re-sorts
#               the field for EVERY input relative to its own cohort — "closest planet"
#               becomes meaningful even when absolute distances are useless.

def _angular_sep(u: list[float], v: list[float]) -> float:
    """Angle in [0, pi] between two vectors (radians)."""
    num = sum(a * b for a, b in zip(u, v))
    den = _norm(list(u)) * _norm(list(v))
    c = max(-1.0, min(1.0, num / den if den else 0.0))
    return math.acos(c)


def _field_distance(input_unit: list[float], center_unit: list[float]) -> float:
    """Distance between the (bent) input and a planet's field center, per C.FIELD_DISTANCE_METRIC."""
    if C.FIELD_DISTANCE_METRIC == "euclidean":
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(input_unit, center_unit)))
    # default: angular
    return _angular_sep(input_unit, center_unit)


def core_bend(input_vec: list[float], core_position_xyz: list[float],
              dissonance: float = 0.0) -> tuple[list[float], dict]:
    """C_core gravitational bending (Segment 2).

    The build plan says: shift the effective input position toward C_core by
        G * M_core(r) / r^2   before field evaluation.
    M_core includes the dissonance component (Q5: dissonance=0 for now, plumbed through;
    G1 Moon C computes real Delta-D in Phase 2). With dissonance=0 this is pure geometry
    and matches how integrator.py already treats the core pull.

    We blend the raw input vector toward a unit direction pointing at the core by a
    fraction `bend_frac = force/(1+force*k)` derived from the inverse-square force.
    The result stays in 384-dim (we lift the [x,y,z] core position via axes_to_384 so it
    is comparable to the input). Distance r is measured between the input's PROJECTED
    cognitive axes and the orbital core position — NOT raw embedding components.

    Returns (bent_input_unit, info) where info has bend_frac and M_core for diagnostics.
    NOTE: this bends toward the 3D orbital core position — a subtle geometric nudge. It is
    intentionally gentle so it never overwhelms semantic identity (RULER-COLLAPSE guard).
    """
    G = C.G
    # M_core = M_base + alpha*(dD)^beta  (dissonance=0 -> just M_base)
    m_core = C.M_CORE_BASE + C.DISSONANCE_ALPHA * (dissonance ** C.DISSONANCE_BETA) if dissonance > 0 else C.M_CORE_BASE
    # Distance from the input's PROJECTED cognitive axes to the core position.
    # FIX: the raw input is a 384-dim embedding, not an [x,y,z]; its first three floats
    # have no geometric meaning. We project it onto the 3 cognitive axes (the same map
    # collapse.py uses) and measure r against the orbital core position in THAT space.
    from resonance import project_to_axes
    x, y, z = project_to_axes(list(input_vec)) if len(input_vec) >= 3 else (0.0, 0.0, 0.0)
    dx = x - core_position_xyz[0]
    dy = y - core_position_xyz[1]
    dz = z - core_position_xyz[2]
    r_sq = dx * dx + dy * dy + dz * dz
    r = math.sqrt(r_sq) if r_sq > 0 else 0.0
    # Inverse-square force magnitude, softened (mirror integrator's EPSILON).
    force = G * m_core / (r_sq + C.EPSILON ** 2)
    # Map the raw force to a gentle blend fraction in [0,1): proper squash
    # bend_frac = force/(1+force*k). FIX: the previous linear form min(0.5, force*0.02)
    # saturated at the cap for most planets (always 50% pull), which made bending a
    # blunt instrument. The squash saturates GENTLY toward k^-1 as r shrinks and decays
    # ~1/r^2 with distance — so near inputs bend more, far inputs barely move.
    BEND_K = 40.0                         # tuning constant (Segment 4); k^-1=0.025 max pull
    bend_frac = force / (1.0 + force * BEND_K)
    if r < 1e-9:
        # REVIEW-FIX (core_bend discontinuity at r≈0): previously this returned a HARD 0.0,
        # so just-below the guard you got no bend while just-above it the squash saturated
        # near k^-1=0.025 — a step in what is supposed to be a gentle, continuous nudge.
        # Now we return the SAME squashed bend_frac (monotone & bounded) but skip the unit-
        # direction blend: at r≈0 the input IS the core position, so there is no meaningful
        # toward-core direction and the vector stays unchanged. Continuous as r→0, and it
        # still "never overwhelms" identity because bend_frac ≤ k^-1 (RULER-COLLAPSE guard).
        return _unit(input_vec), {"bend_frac": round(bend_frac, 4), "M_core": m_core, "r": 0.0}
    # Direction from input toward core, lifted to the input's space via its own axes.
    # We approximate by moving the input vector a fraction of the way toward the lifted
    # core direction (unit). This keeps us in 384-dim without a full coordinate transform.
    core_dir = _unit(axes_to_384(tuple(core_position_xyz)))
    in_unit = _unit(input_vec)
    bent = [in_unit[i] * (1.0 - bend_frac) + core_dir[i] * bend_frac for i in range(len(in_unit))]
    return _unit(bent), {"bend_frac": round(bend_frac, 4), "M_core": m_core, "r": round(r, 3)}


def per_planet_weights(input_vec: list[float],
                       field_centers: dict[str, list[float]],
                       core_position_xyz: list[float],
                       sigmas: dict[str, float] | None = None,
                       masses: dict[str, float] | None = None,
                       dissonance: float = 0.0) -> dict:
    """Compute per-planet activation weights from the composite field (Segment 2).

    For each planet i with blended field center c_i and spread sigma_i:
        E_i = mass_i * exp( -d(input_bent, c_i)^2 / (2 * sigma_eff_i^2) )
    where d uses C.FIELD_DISTANCE_METRIC and sigma_eff = PLANET_SIGMA[i] * SIGMA_SCALE.

    ALL 7 planets contribute — none are filtered out. Returns a dict keyed by planet id:
        {pid: {"weight": E_i, "distance": d, "sigma_eff": ...}}
    This is the per-planet Gaussian contribution along the input; local maxima here ARE
    the spike activations (Q2 approval).
    """
    sigmas = sigmas if sigmas is not None else C.PLANET_SIGMA
    masses = masses if masses is not None else C.PLANET_MASSES
    bent, info = core_bend(input_vec, core_position_xyz, dissonance=dissonance)

    # Compute per-planet distances; for angular_z we need the full cohort to z-score.
    pids = list(field_centers.keys())
    if C.FIELD_DISTANCE_METRIC == "angular_z":
        raw_ds = {pid: _angular_sep(bent, field_centers[pid]) for pid in pids}
        ds = list(raw_ds.values())
        mu = sum(ds) / len(ds)
        # REVIEW-FIX (angular_z degenerate-sd): when the cohort spread is ~0 (all centers
        # equidistant from the bent input), the raw `or 1e-9` floor divided float noise
        # (~1e-17) by 1e-9 and produced z-scores decided by roundoff/dict order, not geometry.
        # Now: a degenerate spread (sd < 1e-9) means every planet is equally close — fall back
        # to ALL-EQUAL z=0.0 so the ranking reflects real symmetry instead of noise.
        # NB: threshold is 1e-9, NOT C.EPSILON (=0.1): that constant is a softening length in a
        # different (geometric) unit domain; using it here would zero out legitimate small spreads.
        sd = (sum((d - mu) ** 2 for d in ds) / len(ds)) ** 0.5
        if sd < 1e-9:
            dists = {pid: 0.0 for pid in pids}
        else:
            dists = {pid: (raw_ds[pid] - mu) / sd for pid in pids}
    else:
        dists = {pid: _field_distance(bent, field_centers[pid]) for pid in pids}

    # SEGMENT-3 FIX: the routed weight is now the PURE GAUSSIAN LOUDNESS SHAPE
    # exp(-d^2 / 2 sigma_eff^2) WITHOUT mass. collapse.emit_waves already multiplies by
    # masses[pid] when it consumes this value, so baking mass in here too would apply it
    # TWICE (measured: routed energy ~37x Phase-0 for the same prompt — a real bug, not a
    # tuning quirk). Mass stays where it belongs: with the wave amplitude. This also makes
    # Segment 4's planned equal-mass A/B meaningful. The `masses` param is retained in the
    # signature (still used for diagnostics if callers want it) but no longer multiplies E_i.
    out = {}
    for pid in pids:
        d = dists[pid]
        sigma_eff = max(1e-6, sigmas.get(pid, 1.0) * C.SIGMA_SCALE)
        e = math.exp(-(d * d) / (2.0 * sigma_eff * sigma_eff))
        out[pid] = {"weight": e, "distance": round(d, 4), "sigma_eff": round(sigma_eff, 3)}
    out["_meta"] = {**info, "metric": C.FIELD_DISTANCE_METRIC,
                    "field_position_weight": C.FIELD_POSITION_WEIGHT}
    return out


# ─── SEGMENT 3: FULL PIPELINE ORCHESTRATOR (one entry point for John) ──────

def routed_collapse(question: str,
                    base_dir: str | None = None,
                    session_history=None,
                    g2_bias_vector=None,
                    dissonance: float = 0.0) -> dict:
    """ONE entry point for the full Phase-1 pipeline.

        load orbital state (live objects via integrator, separate-phase rule)
          -> embed(question)                                  [384-dim]
          -> planet wave centers                              [semantic identity]
          -> field_centers_for_all(...)                       [Q1 blend: w*id + (1-w)*pos]
          -> per_planet_weights(...)                          [Gaussian spikes, Q2]
          -> run_collapse(..., routed_weights=weights)        [all 7 emit, loudness routed]

    When `routed_weights` is None inside this call it still works — but that would only
    happen if routing failed; here we always pass the computed weights. All 7 planets
    emit together; routing only sets each voice's loudness (never filters).

    Returns run_collapse()'s dict plus a "routing" key with the per-planet weights,
    distances, and _meta so callers can inspect WHY each planet was as loud as it was.
    """
    # ── RING INTAKE FACET (Phase 2, Seg 1): PII scrub + clarity — BEFORE any embedding ──
    # A facet of THE RING (user-facing layer), NOT Gas Giant 1. Garbage input is
    # rejected gracefully here; no planetary processing runs at all.
    from gate1 import gate1_filter
    g1 = gate1_filter(question)
    if not g1["proceed_to_planets"]:
        return {"gate1": g1, "routing": None, "waves": {}, "result": None,
                "diagnostics": None,
                "note": f"Input rejected at Ring Intake: {g1['clarity']['reason']}"}
    clean_q = g1["cleaned_text"]   # PII-scrubbed text used for embedding downstream

    # ── DISSONANCE PRE-READ (Ring Intake facet, D-020 / Phase 2 Seg 2b‑2) ───────
    # If the caller didn't explicitly pass a dissonance value, use the early ΔD estimate
    # computed at intake. This is what makes core mass respond to tension BEFORE the
    # planets run (M = M_base + α(ΔD)^β). An explicit dissonance arg always wins.
    if dissonance == 0.0:
        dissonance = g1.get("dissonance", 0.0)

    from collapse import _planet_wave_centers, run_collapse
    from resonance import embed as _embed
    core, planets = load_orbital_state(base_dir)
    wave_centers = _planet_wave_centers()
    centers = field_centers_for_all(wave_centers, planets)
    pw = per_planet_weights(_embed(clean_q),
                            centers, core.position,
                            dissonance=dissonance)
    weights = {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}
    out = run_collapse(clean_q,
                       session_history=session_history,
                       g2_bias_vector=g2_bias_vector,
                       routed_weights=weights)
    out["routing"] = {pid: pw[pid] for pid in weights}   # full per-planet detail
    out["gate1"] = g1                                    # Ring Intake report (cleaned_text, redactions)

    # ── SEGMENT 4b: READ-ONLY DIAGNOSTICS (Option A — no amplitude changes) ───────
    # dominance_ratio: top/bottom amplitude spread across the 7 planets.
    #   High (>5x) = "leans hard on one voice"; low (~1x) = "contested, multiple voices matter."
    # breakthrough_pair: when dominance IS high BUT a far-away planet is in active productive
    #   opposition (elevated cancellation from pair_map), flag it — an out-of-area voice is
    #   pushing back against the dominant one rather than being drowned out.
    amps = {pid: w["amplitude"] for pid, w in out["waves"].items() if not pid.startswith("_")}
    ranked_amps = sorted(amps.values(), reverse=True)
    dominance_ratio = round(ranked_amps[0] / max(min(a for a in amps.values()), 1e-9), 2)

    # Breakthrough: high dominance + at least one pair where the CANCELLED amplitude is elevated.
    # "Elevated" = cancelled > 5% of that pair's minimum amplitude (a real pushback, not noise).
    pm = out["result"]["pair_map"]
    breakthrough_pair = None
    if dominance_ratio > 5.0:   # threshold is a tunable judgment call; informational only
        for key, val in pm.items():
            cancelled = val.get("cancelled", 0.0)
            a, b = key.split("|")
            min_amp_pair = min(amps.get(a, 0.0), amps.get(b, 0.0))
            if min_amp_pair > 1e-9 and (cancelled / min_amp_pair) > 0.05:
                breakthrough_pair = {"pair": key, "cancelled": val["cancelled"],
                                     "alignment": val["align"]}
                break   # report the strongest one found

    out["diagnostics"] = {
        "dominance_ratio": dominance_ratio,
        "breakthrough_pair": breakthrough_pair,
        "note": ("READ-ONLY: these do not change any amplitudes. dominance_ratio>5x means one "
                 "planet dominates loudness; breakthrough_pair flags an out-of-area voice in "
                 "active opposition to the dominant one.")
    }
    return out


def composite_field_at(input_vec: list[float], field_centers: dict[str, list[float]],
                       core_position_xyz: list[float]) -> float:
    """Sum of all per-planet Gaussian contributions at the (bent) input point = Psi(x).

        Psi(x) = sum_i E_i * exp(-d(input_bent, c_i)^2 / 2 sigma_eff_i^2)
    Returned as a single scalar for diagnostics / spike-magnitude readout.
    """
    w = per_planet_weights(input_vec, field_centers, core_position_xyz)
    return sum(v["weight"] for k, v in w.items() if not k.startswith("_"))


# ─── SMOKE TEST (Segments 1+2 — blend + composite field + weights) ──

def _smoke():
    """Smoke test for Segments 1+2: field-center blend + composite field Psi(x) + weights.

    Confirms: state loads, wave centers embed, the blend is a unit vector that MOVES as
    FIELD_POSITION_WEIGHT changes (Segment 1), AND per-planet Gaussian weights exist and
    are non-zero for ALL 7 planets with no planet filtered out (Segment 2) — plus a
    sanity check that core bending stays gentle (bend_frac well below the old 0.5 cap).
    Requires LM Studio (wave-center embeddings + sample input embeddings).
    """
    print("Routing Segments 1+2 smoke test\n" + "=" * 64)
    core, planets = load_orbital_state()
    print(f"core position={core.position}  M_base={core.M_base}")

    # Import here so the module import path stays light and offline-safe.
    from collapse import _planet_wave_centers
    from resonance import embed as _embed
    wave_centers = _planet_wave_centers()
    print(f"embedded {len(wave_centers)} planet identity vectors (384-dim)")

    for w in (0.0, C.FIELD_POSITION_WEIGHT, 1.0):
        C.FIELD_POSITION_WEIGHT = w
        centers = field_centers_for_all(wave_centers, planets)
        # Verify every center is a unit vector in the correct dimensionality.
        ok = all(abs(_norm(v) - 1.0) < 1e-6 and len(v) == 384 for v in centers.values())
        print(f"\nFIELD_POSITION_WEIGHT={w:.2f}  (all-unit-vectors: {ok})")
        for p in planets:
            c = centers[p.id]
            # Project back to axes so we can SEE the identity<->position movement.
            x, y, z = sum(c[i]*C.AXIS_RATIONALITY[i] for i in range(384)), \
                       sum(c[i]*C.AXIS_PRESERVATION[i] for i in range(384)), \
                       sum(c[i]*C.AXIS_OUTWARD[i] for i in range(384))
            print(f"   {p.id:<10} pos={['%.2f'%v for v in p.position]} "
                  f"-> center axes [{x:+.2f}, {y:+.2f}, {z:+.2f}]")
    # restore the knob so we don't leak a mutated constant into other tests
    C.FIELD_POSITION_WEIGHT = 0.5

    # ── Segment 2: composite field + per-planet weights for sample inputs ────────
    print("\n" + "=" * 64)
    print(f"Segment 2 — per-planet weights (metric={C.FIELD_DISTANCE_METRIC}, w=0.5, sigma_scale={C.SIGMA_SCALE})")
    centers = field_centers_for_all(wave_centers, planets)
    # HONESTY NOTE (measured during tuning spike): MiniLM scatters these prompts ~90deg
    # from ALL archetype texts, so the strongest *semantic* signal available is soft.
    # Z-scoring makes the field discriminate (no longer flat), but "Sage wins clearly on
    # math" may be at or near this model's ceiling — the equal-mass/sigma A/B in Segment 4
    # will quantify exactly how much mass/σ vs. geometry drives each ranking.
    samples = {
        "solve this differential equation": "hope: sage region (soft signal)",
        "is it right to lie to spare someone's feelings?": "hope: caregiver region (soft signal)",
    }
    all_ok = True
    spreads = []
    for text, note in samples.items():
        iv = _embed(text)
        pw = per_planet_weights(iv, centers, core.position)
        meta = pw.pop("_meta")
        ranked = sorted(pw.items(), key=lambda kv: -kv[1]["weight"])
        nonzero = all(v["weight"] > 0 for v in pw.values())
        spread = (ranked[0][1]["weight"] / max(ranked[-1][1]["weight"], 1e-9))
        top3 = [pid for pid, _ in ranked[:3]]
        print(f"\nINPUT: \"{text}\"   ({note})")
        print(f"   bend_frac={meta['bend_frac']}  r_to_core={meta['r']}")
        for pid, info in ranked:
            bar = "#" * int(info["weight"] * 6)
            # For angular_z: d is a z-score — NEGATIVE means CLOSER than cohort mean.
            closeness = ("closer" if info["distance"] < 0 else "farther") \
                if meta["metric"] == "angular_z" else ""
            print(f"   {pid:<10} w={info['weight']:.4f} d={info['distance']:+.3f} ({closeness}) | {bar}")
        psi = sum(v["weight"] for v in pw.values())
        print(f"   Psi(x)={psi:.4f}  all-7-nonzero: {nonzero}  top/bottom spread: {spread:.1f}x")
        all_ok = all_ok and nonzero
        spreads.append(spread)
    ok_spread = all(s < 6.0 for s in spreads) if len(spreads) == len(samples) else False
    print("\nSMOKE RESULT (Segments 1+2):")
    print(f"   all-7-nonzero: {all_ok}   spread<6x (not flat, not collapsed): {ok_spread}")
    if all_ok and ok_spread:
        print("   PASS — all 7 planets emit with meaningful differentiation")
    else:
        print("   CHECK OUTPUT ABOVE")

    # ── Segment 3: full-pipeline wiring check (routed weights -> collapse) ────────
    # Proves the new routed_weights param is LIVE: same prompt, Phase-0 path vs
    # routed path must DIFFER in consensus vector AND energy; all 7 planets must
    # still have non-zero amplitude under routing; and the difference must be GENTLE
    # (energy change bounded — not a collapse into one voice).
    print("\n" + "=" * 64)
    print("Segment 3 — routed weights wired into collapse.emit_waves")
    from collapse import run_collapse as _run, emit_waves as _emit
    q = samples[list(samples)[0]]   # reuse first sample prompt (already embedded above? re-embed once)
    iv = _embed(q)
    # Phase-0 path: no routed weights.
    w_p0 = _emit(iv, centers, C.PLANET_MASSES)
    r_p0 = _run(q)                  # full pipeline unweighted (re-embeds internally; fine for smoke)
    # Routed path: per_planet_weights -> emit_waves with routed_weights.
    pw = per_planet_weights(iv, centers, core.position)
    weights3 = {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}
    w_routed = _emit(iv, centers, C.PLANET_MASSES, routed_weights=weights3)
    r_routed = _run(q, routed_weights=weights3)

    nonzero_all = all(w["amplitude"] > 0.0 for p, w in w_routed.items())
    e_p0 = r_p0["result"]["total_energy"]
    e_rt = r_routed["result"]["total_energy"]
    dE = abs(e_rt - e_p0)
    # Vector difference: are the consensus vectors actually different?
    import math as _m
    cv_diff = _m.sqrt(sum((a - b) ** 2 for a, b in zip(r_p0["result"]["consensus_vector"], r_routed["result"]["consensus_vector"])))
    print(f"\nPROMPT: \"{q}\"")
    print(f"   Phase-0 total_energy={e_p0:.4f}  routed total_energy={e_rt:.4f}  ΔE={dE:.4f}")
    print(f"   consensus-vector L2 diff = {cv_diff:.4f} (should be > 0: wiring is live)")
    print(f"   all-7-amplitudes-nonzero under routing: {nonzero_all}")
    for pid in sorted(w_routed):
        a_p0, a_rt = w_p0[pid]["amplitude"], w_routed[pid]["amplitude"]
        print(f"     {pid:<10} amp Phase-0={a_p0:.4f}  routed={a_rt:.4f}")
    # GENTLENESS = no single voice dominates the field under routing. The two paths have
    # different amplitude SCALES by design (Phase-0 uses raw MiniLM cosines ~0.1; routed
    # weights are normalized Gaussian shapes 0..1), so ΔE-vs-baseline is NOT a fair test.
    # What actually matters for the all-7-speak invariant: top amplitude isn't an order of
    # magnitude above the rest (a collapse into one voice would show ~50x+ spread).
    amps_rt = [w["amplitude"] for w in w_routed.values()]
    # REVIEW-FIX (Segment-3 all-zero crash): when every routed amplitude is exactly 0
    # (input equidistant from / far from all centers), the old `min(a for a in amps if a>0)`
    # raised ValueError on an empty sequence. Now we fall back to EPSILON so no-positives
    # simply yields a zero-spread field instead of crashing; the normal case is unchanged.
    max_amp = max(amps_rt)
    min_pos = min((a for a in amps_rt if a > 0), default=C.EPSILON)
    top_spread = max_amp / max(min_pos, C.EPSILON)
    gentle = top_spread < 30.0   # bounded spread: field stays a chorus, not a solo
    seg3_ok = nonzero_all and cv_diff > 1e-6 and gentle
    print(f"\nSMOKE RESULT (Segment 3): wiring-live={cv_diff>1e-6}  all-nonzero={nonzero_all}  "
          f"no-single-voice-dominance(top/bottom spread {top_spread:.1f}x < 30x)={gentle}")
    if seg3_ok:
        print("   PASS — routed weights reach emit_waves, all 7 still speak, no voice dominates")


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        _smoke()
    else:
        print("Segment 1 exposes compute_field_center()/field_centers_for_all().")
        print("Run 'python -X utf8 routing.py --smoke' for a field-center smoke test.")
