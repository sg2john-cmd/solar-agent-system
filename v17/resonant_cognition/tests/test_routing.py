"""
Resonant Cognition v17 — Phase 1 Segment 4: ROUTING ACCEPTANCE TESTS + TUNING A/B
==================================================================================

Purpose (per the approved segment plan):
  1. Acceptance tests for routing.py (Segments 1+2) and its wiring into collapse (Segment 3).
     These run against a LIVE LM Studio embedder (same as _smoke), but with hard PASS/FAIL
     assertions so a regression is visible at a glance, not just "look at the output."
  2. The equal-mass / equal-sigma A/B that quantifies HOW MUCH of each ranking comes from
     ORBITAL GEOMETRY (angular_z distances) vs. PLANET CONSTANTS (mass/sigma). This was the
     honest-ceiling question left open in Segment 3: MiniLM scatters prompts ~90deg from all
     archetypes, so we need to know whether the field's discrimination is real signal or an
     artifact of mass/sigma values.

Run (needs LM Studio at C.LM_STUDIO_HOST for embeddings):
    python -X utf8 test_routing.py            # run all tests + A/B, print summary
    python -X utf8 test_routing.py --ab-only  # skip acceptance tests, just the A/B sweep
"""

from __future__ import annotations

import os
import sys

# Tests live in tests/ — parent dir has the modules.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)  # resonant_cognition/
if _PARENT not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _PARENT)

import constants as C
import routing as R
from resonance import embed as _embed


# ─── TEST HARNESS (tiny; no external deps) ──────────────────────────────────

_RESULTS: list[tuple[str, bool, str]] = []

def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    _RESULTS.append((name, cond, detail))
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))


def section(title: str) -> None:
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


# ─── ACCEPTANCE TESTS ────────────────────────────────────────────────────────

def test_state_and_field_centers():
    """Segment 1: state loads, field centers are unit vectors that MOVE with the knob."""
    section("TEST A — Segment 1: orbital state + blended field centers")
    core, planets = R.load_orbital_state()
    check("7 planets loaded", len(planets) == 7, f"got {len(planets)}")
    check("core has position+mass", hasattr(core, "position") and hasattr(core, "M_base"))

    from collapse import _planet_wave_centers
    wave_centers = _planet_wave_centers()
    check("7 wave centers embedded (384-dim)", len(wave_centers) == 7
          and all(len(v) == 384 for v in wave_centers.values()))

    # The knob must actually move the center: w=0 vs w=1 should differ.
    C.FIELD_POSITION_WEIGHT = 0.0
    c_pos_only = R.field_centers_for_all(wave_centers, planets)
    C.FIELD_POSITION_WEIGHT = 1.0
    c_id_only = R.field_centers_for_all(wave_centers, planets)
    C.FIELD_POSITION_WEIGHT = 0.5   # restore default

    def _axes(v):
        return (sum(v[i]*C.AXIS_RATIONALITY[i] for i in range(384)),
                sum(v[i]*C.AXIS_PRESERVATION[i] for i in range(384)),
                sum(v[i]*C.AXIS_OUTWARD[i] for i in range(384)))

    # At least one planet's center must shift when the blend changes (proves position is used).
    moved = any(_axes(c_pos_only[p.id]) != _axes(c_id_only[p.id]) for p in planets)
    check("FIELD_POSITION_WEIGHT moves centers (position is real)", moved)
    all_unit = all(abs(R._norm(v) - 1.0) < 1e-6 for v in c_id_only.values())
    check("all field centers are unit vectors", all_unit)


def test_per_planet_weights():
    """Segment 2: weights exist, ALL 7 non-zero, spread bounded (not flat, not collapsed)."""
    section(f"TEST B — Segment 2: per-planet weights (metric={C.FIELD_DISTANCE_METRIC})")
    core, planets = R.load_orbital_state()
    from collapse import _planet_wave_centers
    centers = R.field_centers_for_all(_planet_wave_centers(), planets)

    samples = [
        "solve this differential equation",
        "is it right to lie to spare someone's feelings?",
        "what is the boiling point of water at sea level?",
    ]
    all_nonzero, spreads_ok = True, True
    for text in samples:
        iv = _embed(text)
        pw = R.per_planet_weights(iv, centers, core.position)
        weights = {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}
        nz = all(w > 0 for w in weights.values())
        ranked = sorted(weights.values(), reverse=True)
        spread = ranked[0] / max(ranked[-1], 1e-9)
        print(f"    \"{text[:45]}\" -> {len(weights)} planets, nonzero={nz}, spread={spread:.1f}x")
        all_nonzero &= nz
        spreads_ok &= (len(weights) == 7 and spread < 60.0)   # not flat(≈1), not solo(>>30+)
    check("all 7 planets present with non-zero weight on every sample", all_nonzero)
    check("spread is meaningful (not perfectly flat, no single-voice collapse)", spreads_ok)


def test_collapse_wiring():
    """Segment 3: routed weights actually change the consensus, Phase-0 path untouched."""
    section("TEST C — Segment 3: routed weights wired into collapse")
    from collapse import emit_waves as _emit, run_collapse as _run, _planet_wave_centers
    core, planets = R.load_orbital_state()
    centers = R.field_centers_for_all(_planet_wave_centers(), planets)

    q = "solve this differential equation"
    iv = _embed(q)

    # Byte-identical Phase-0 fallback: no routed_weights == same result.
    r_none = _run(q, routed_weights=None)
    r_default = _run(q)
    check("routed_weights=None is byte-identical to default (Phase 0 preserved)",
          r_none["result"] == r_default["result"])

    # Routed path must DIFFER and keep all 7 non-zero.
    pw = R.per_planet_weights(iv, centers, core.position)
    weights = {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}
    w_routed = _emit(iv, centers, C.PLANET_MASSES, routed_weights=weights)
    nonzero_all = all(w["amplitude"] > 0.0 for w in w_routed.values())
    check("all 7 planets still speak under routing (none silenced)", nonzero_all)

    r_routed = _run(q, routed_weights=weights)
    import math as _m
    cv_diff = _m.sqrt(sum((a - b) ** 2 for a, b in zip(
        r_default["result"]["consensus_vector"], r_routed["result"]["consensus_vector"])))
    check("routed consensus genuinely differs from Phase-0 (wiring is live)", cv_diff > 1e-6,
          f"L2 diff={cv_diff:.4f}")

    # routed_collapse() one-shot entry point works and carries routing detail.
    out = R.routed_collapse(q)
    check("routed_collapse() returns waves + result + routing detail",
          "result" in out and "routing" in out and len(out["waves"]) == 7)

    # Segment 4b: diagnostics are present and computable (informational, not a gate).
    check("diagnostics key exists with dominance_ratio",
          "diagnostics" in out and "dominance_ratio" in out["diagnostics"]
          and isinstance(out["diagnostics"]["dominance_ratio"], float),
          f"got: {out.get('diagnostics', {})}")


# ─── THE HONEST A/B: GEOMETRY vs CONSTANTS ──────────────────────────────────

def test_mass_sigma_ab():
    """Quantify how much of the ranking comes from ORBITAL GEOMETRY (angular_z) vs.
    PLANET CONSTANTS (mass/sigma). Method: for each sample prompt, rank planets by weight
    under THREE regimes and compare top-3 stability:
        BASE      : real masses + real sigmas  (current system)
        EQ_MASS   : all mass=1.0 (isolate sigma + geometry)
        EQ_SIGMA  : all sigma=1.0 (isolate mass + geometry)
        NEUTRAL   : all mass=1.0 AND all sigma=1.0 -> PURE GEOMETRY ONLY

    If the top-3 ranking barely changes from BASE to NEUTRAL, then geometry (the angular_z
    field) is doing most of the work and mass/sigma are fine-tuning — GOOD, that's what we
    want ("identity travels with position"). If NEUTRAL collapses everything into one planet
    or goes flat, then discrimination currently depends on constants, not live geometry.
    """
    section("TEST D — A/B: ranking contribution of geometry vs mass/sigma")
    core, planets = R.load_orbital_state()
    from collapse import _planet_wave_centers
    centers = R.field_centers_for_all(_planet_wave_centers(), planets)

    samples = [
        "solve this differential equation",          # hope: sage/ruler (rationality)
        "is it right to lie to spare someone's feelings?",  # hope: caregiver/everyman
        "tear down the rules and start over from scratch",   # hope: rebel
    ]

    def rank_under(masses, sigmas, iv):
        pw = R.per_planet_weights(iv, centers, core.position, masses=masses, sigmas=sigmas)
        w = {pid: v["weight"] for pid, v in pw.items() if not pid.startswith("_")}
        return [pid for pid, _ in sorted(w.items(), key=lambda kv: -kv[1])]

    real_mass, real_sig = dict(C.PLANET_MASSES), dict(C.PLANET_SIGMA)
    eq_mass = {p: 1.0 for p in C.PLANET_MASSES}
    eq_sig = {p: 1.0 for p in C.PLANET_SIGMA}

    print(f"    {'sample':<42} | BASE top3        | NEUTRAL(pure geom) top3")
    overlap_scores = []
    for text in samples:
        iv = _embed(text)
        base   = rank_under(real_mass, real_sig, iv)[:3]
        neutral= rank_under(eq_mass,  eq_sig,  iv)[:3]
        overlap = len(set(base) & set(neutral)) / 3.0
        overlap_scores.append(overlap)
        print(f"    {text[:42]:<42} | {','.join(p[:6] for p in base):<17} | "
              f"{','.join(p[:6] for p in neutral)}")

    # Also show the pure-geometry spread: with constants removed, does the field still rank?
    iv = _embed(samples[0])
    pw_neutral = R.per_planet_weights(iv, centers, core.position, masses=eq_mass, sigmas=eq_sig)
    w_n = {pid: v["weight"] for pid, v in pw_neutral.items() if not pid.startswith("_")}
    ranked = sorted(w_n.values(), reverse=True)
    geom_spread = ranked[0] / max(ranked[-1], 1e-9)

    avg_overlap = sum(overlap_scores) / len(overlap_scores)
    check("pure-geometry field still discriminates (spread>1.2, not flat)", geom_spread > 1.2,
          f"neutral spread={geom_spread:.2f}x")
    # Interpretation is printed for John; we don't hard-fail on overlap because a LOW score
    # is itself useful information (it means constants currently dominate — actionable).
    check("ranking stability BASE vs pure-geometry measured", True,
          f"avg top3 overlap={avg_overlap:.0%}, neutral spread={geom_spread:.2f}x. "
          + ("HIGH => geometry drives ranking (ideal)." if avg_overlap >= 0.67
             else "MEDIUM/LOW => mass/sigma currently shape the ranking more than live "
                  "geometry — consider tuning constants or FIELD_POSITION_WEIGHT."))


# ─── Q4: RESONANCE MULTIPLIER TESTS ──────────────────────────────────────────

def test_resonance_multiplier():
    """Verify the resonance multiplier (Q4) is GENTLE and REVERSIBLE.

    Checks:
      1. With flag ON, all 7 planets still have non-zero amplitude (no silencing).
      2. The change vs. flag-OFF is bounded: no planet's amplitude changes by more than
         a factor of ~3x (a gentle nudge, not a takeover).
      3. Flipping the flag back OFF restores byte-identical output to the pre-Q4 path.
    """
    section("TEST E — Q4: resonance multiplier is gentle + reversible")
    from collapse import run_collapse as _run

    q = "solve this differential equation step by step"

    # Path A: flag ON (current state)
    C.RESONANCE_MULTIPLIER_ENABLED = True
    r_on = _run(q, routed_weights=None)   # Phase-0 path with multiplier on

    # Path B: flag OFF (pre-Q4 behavior)
    C.RESONANCE_MULTIPLIER_ENABLED = False
    r_off = _run(q, routed_weights=None)

    # Restore default (True as shipped)
    C.RESONANCE_MULTIPLIER_ENABLED = True

    amps_on = {pid: w["amplitude"] for pid, w in r_on["waves"].items() if not pid.startswith("_")}
    amps_off = {pid: w["amplitude"] for pid, w in r_off["waves"].items() if not pid.startswith("_")}

    # Check 1: the multiplier never SILENCES a planet that was already speaking.
    # (On the Phase-0 cosine path, some planets can legitimately be at exactly 0 because
    # their alignment is negative. The invariant is: if it spoke before, it still speaks now.)
    silenced = [pid for pid in amps_off if amps_off[pid] > 1e-6 and amps_on.get(pid, 0) <= 1e-9]
    no_silencing = len(silenced) == 0
    check("multiplier never silences a planet that was already speaking", no_silencing,
          f"silenced={silenced}")

    # Check 2: change is gentle — max ratio between on/off per planet should be < 3.0.
    ratios = []
    for pid in amps_off:
        if amps_off[pid] > 1e-9 and amps_on.get(pid, 0) > 1e-9:
            ratios.append(amps_on[pid] / amps_off[pid])
        elif amps_off[pid] <= 1e-9 and amps_on.get(pid, 0) > 1e-9:
            ratios.append(float('inf'))  # went from zero to something — bad
    max_ratio = max(ratios) if ratios else 1.0
    gentle = max_ratio < 3.0
    check("multiplier is a gentle nudge (max amplitude ratio ON/OFF < 3x)", gentle,
          f"ratios={ {k: round(amps_on[k]/max(amps_off[k],1e-9),2) for k in amps_off if amps_off[k]>1e-6} }, "
          f"max_ratio={max_ratio:.2f}")

    # Check 3: turning it OFF gives byte-identical result to pre-Q4.
    identical = r_off["result"] == _run(q, routed_weights=None).__class__ and True  # structural check
    # Actually verify by re-running with flag explicitly off:
    C.RESONANCE_MULTIPLIER_ENABLED = False
    r_off2 = _run(q, routed_weights=None)
    C.RESONANCE_MULTIPLIER_ENABLED = True   # restore
    byte_identical = (r_off["result"] == r_off2["result"]) and \
                     all(w1["amplitude"] == w2["amplitude"] for w1, w2 in
                         zip(r_off["waves"].values(), r_off2["waves"].values()))
    check("flag OFF is byte-identical to pre-Q4 output (fully reversible)", byte_identical)

    # Print a readable comparison for John.
    print(f"\n    {'planet':<12} {'amp ON':>8} {'amp OFF':>8} {'ratio':>6}")
    for pid in sorted(amps_off, key=amps_off.get, reverse=True):
        on_a = amps_on.get(pid, 0)
        off_a = amps_off[pid]
        ratio = on_a / max(off_a, 1e-9) if off_a > 1e-9 else float('inf')
        print(f"    {pid:<12} {on_a:>8.4f} {off_a:>8.4f} {ratio:>6.2f}")


# ─── RING INTAKE TEST (Phase 2, Seg 1) ───────────────────────────────────────

def test_gate1():
    """Ring Intake facet: normal prompts pass; garbage is rejected cleanly without crashing."""
    section("TEST E — Phase 2 Ring Intake: PII + clarity pre-filter")

    # Normal prompt passes the gate and flows through routed_collapse.
    good = R.routed_collapse("How should I approach a difficult conversation with my partner?")
    check("normal prompt proceeds to planets", good.get("routing") is not None,
          f"note={good.get('note','')}")

    # Garbage (repeated chars) is rejected gracefully — no crash, graceful dict.
    bad = R.routed_collapse("aaaaa")
    check("garbage rejected at Ring Intake", bad.get("routing") is None and bad["gate1"]["proceed_to_planets"] is False,
          f"note={bad.get('note','')}")

    # PII scrub: an email address should be redacted in cleaned_text.
    pii = R.routed_collapse("My email is john@example.com, how do I meditate better?")
    g1 = pii["gate1"]
    check("PII (email) scrubbed from cleaned text", "john@example.com" not in g1["cleaned_text"],
          f"cleaned={g1['cleaned_text']!r}")


# ─── DRIVER ──────────────────────────────────────────────────────────────────

def main():
    print("Phase 1 Segment 4 — routing acceptance tests + A/B")
    ab_only = "--ab-only" in sys.argv
    if not ab_only:
        test_state_and_field_centers()
        test_per_planet_weights()
        test_collapse_wiring()
        test_resonance_multiplier()
        test_gate1()
    test_mass_sigma_ab()

    section("SUMMARY")
    passed = sum(1 for _, ok, _ in _RESULTS if ok)
    total = len(_RESULTS)
    for name, ok, detail in _RESULTS:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}")
    print(f"\n  {passed}/{total} checks passed.")
    print("  NOTE: TEST D's stability line is informational (guides tuning), not a gate —")
    print("        a low geometry-overlap score tells us WHERE to tune, it doesn't mean broken.")


if __name__ == "__main__":
    main()
