"""
Resonant Cognition v17 — One-time axis calibration + semantic anchor writer.

WHAT THIS DOES (run once, or re-run if you change AXIS_ANCHOR_PHRASES / anchors):
  1. For each of the 3 cognitive axes, embed a handful of clearly-polar phrases
     via LM Studio MiniLM and average them -> a fixed direction vector in the
     384-dim embedding space (Option B, per phase0d_drafts.md).
  2. Replaces ONLY the three AXIS_* = [...] vector lines inside the EXISTING
     constants.py with these freshly-calibrated unit vectors.
  3. Adds a "semantic_anchor" [x,y,z] field to each planets/*.json (the values
     you approved in docs/phase0d_drafts.md), with a clobber-guard so the orbital
     integrator never overwrites them.

WHY IT IS SAFE TO RE-RUN (H4 fix — independent blind review):
  - constants.py is NOT rewritten from a fixed template anymore. build_constants()
    reads the CURRENT constants.py and surgically replaces only the three
    AXIS_* vector lines, so every Phase 1-8 feature toggle (moons, comet,
    ring, sandbox, embedding retry params, etc.) passes through untouched.
    Re-running calibration can no longer silently wipe the safety rails.
  - planet JSONs get ONLY the semantic_anchor key added/updated; position,
    velocity, mass, etc. are preserved exactly as-is on disk.

RUN:  python -X utf8 calibrate_axes.py
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── LM Studio connection (matches constants.py) ─────────────────────────────
LM_HOST = "127.0.0.1"
LM_PORT = 1234
EMBEDDING_MODEL_ID = "text-embedding-allmini"   # confirmed via /v1/models

# ─── Option B: axis anchor phrases (per phase0d_drafts.md, approved) ─────────
# Each axis vector = unit-normalized mean of these phrases' MiniLM embeddings.
AXIS_ANCHOR_PHRASES = {
    "AXIS_RATIONALITY": [
        "a rigorous logical proof",
        "step-by-step mathematical derivation",
        "evidence and verification",
        "careful analysis and deduction",
    ],
    "AXIS_PRESERVATION": [
        "maintain the status quo",
        "preserve what works",
        "keep things stable, safe, and unchanged",
        "protect established order and tradition",
    ],
    "AXIS_OUTWARD": [
        "take concrete action now",
        "implement and execute directly",
        "act on the world immediately",
        "outward execution rather than reflection",
    ],
}

# ─── Approved semantic anchors (docs/phase0d_drafts.md §A) ────────────────────
SEMANTIC_ANCHORS = {
    "sage":       [ 1.0,  0.4, -0.5],
    "magician":   [-0.6, -0.5,  0.7],
    "caregiver":  [ 0.2,  1.0, -0.3],
    "hero":       [ 0.4, -0.2,  1.0],
    "everyman":   [ 0.2,  0.5, -0.6],
    "rebel":      [-0.4, -1.0,  0.2],
    "ruler":      [ 1.0,  0.6,  0.3],
}

# ─── helpers ──────────────────────────────────────────────────────────────────

def embed(texts: list[str]) -> list[list[float]]:
    """POST to LM Studio /v1/embeddings; returns list of raw vectors."""
    url = f"http://{LM_HOST}:{LM_PORT}/v1/embeddings"
    payload = json.dumps({"model": EMBEDDING_MODEL_ID, "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.load(resp)
    # Preserve input order via the index field.
    rows = sorted(body["data"], key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in rows]


def mean_unit(vecs: list[list[float]]) -> list[float]:
    """Average a set of vectors, then L2-normalize to a unit direction."""
    n = len(vecs)
    dim = len(vecs[0])
    acc = [sum(v[i] for v in vecs) / n for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in acc)) or 1.0
    return [x / norm for x in acc]


def fmt_vec(v: list[float]) -> str:
    """Compact, paste-able Python literal for a vector."""
    return "[" + ", ".join(f"{x:.6f}" for x in v) + "]"


# ─── constants.py AXIS_* vector refresh (H4 fix — surgical, non-destructive) ──
# H4 BUG (independent blind review): build_constants() used to emit constants.py
# from a FIXED template. That template drifted behind the live file across Phases 1-8,
# so re-running calibration silently DELETED every feature toggle added after Phase 0H
# (resonance multiplier, field routing knobs, moon/comet/ring/sandbox toggles, embedding
# retry params, etc.) — reverting all the safety rails to stale/absent values.
#
# FIX: stop templating. Instead, read the CURRENT constants.py and replace ONLY the
# three `AXIS_* = [...]` vector lines with freshly-calibrated values. Everything else
# (all toggles, comments, SEMANTIC_ANCHORS) is preserved verbatim, so regenerating is
# idempotent and non-destructive.

def build_constants(axis_vectors: dict[str, list[float]]) -> str:
    """Return a new constants.py string with only the AXIS_* vectors refreshed.

    The three axis direction vectors (the ONLY things calibration is meant to
    change) are replaced in place. Every other line — including all Phase 1-8
    feature toggles and comments — passes through untouched, so re-running the
    calibrator can no longer wipe any toggle John has added since Phase 0H.

    Raises RuntimeError if an expected AXIS_* vector line is missing from the live
    file (guards against silently clobbering a malformed constants.py).
    """
    cpath = os.path.join(BASE_DIR, "constants.py")
    with open(cpath, "r", encoding="utf-8") as f:
        current = f.read()

    replaced: dict[str, int] = {}
    for name in ("AXIS_RATIONALITY", "AXIS_PRESERVATION", "AXIS_OUTWARD"):
        # Match the full line and capture leading indent + trailing whitespace so we can
        # preserve them exactly; only the vector literal itself is swapped out.
        pattern = rf"^([ \t]*){re.escape(name)}\s*=.*?\]([^\S\n]*)([ \t]*)$"
        def _sub(m, _name=name):
            indent = m.group(1) or ""
            trail  = (m.group(2) or "") + (m.group(3) or "")
            return f"{indent}{_name} = {fmt_vec(axis_vectors[_name])}{trail}"
        new_current, n = re.subn(pattern, _sub, current, count=1, flags=re.MULTILINE)
        replaced[name] = n
        current = new_current

    # Fail loudly if any axis line was not found (guards against a malformed live file).
    missing = [name for name, n in replaced.items() if n != 1]
    if missing:
        raise RuntimeError(
            f"build_constants: could not find AXIS_* vector lines to refresh: {missing}. "
            "Refusing to rewrite constants.py — check the live file is intact."
        )

    return current


# ─── planet JSON writer (clobber-guarded) ─────────────────────────────────────

def write_planet_anchors() -> None:
    pdir = os.path.join(BASE_DIR, "planets")
    for pid, anchor in SEMANTIC_ANCHORS.items():
        path = os.path.join(pdir, f"{pid}.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Clobber-guard: never touch the orbital keys. Only add/replace semantic_anchor.
        data["semantic_anchor"] = anchor
        data["_semantic_anchor_guard"] = (
            "static cognitive-space direction — do NOT overwrite with orbital state"
        )
        # Atomic write (L1 fix): a crash mid-write must not leave a corrupt planet JSON.
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        print(f"  semantic_anchor written -> planets/{pid}.json : {anchor}")


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Calibrating Option B axis vectors via LM Studio MiniLM...")
    all_phrases = []
    for name, phrases in AXIS_ANCHOR_PHRASES.items():
        print(f"  embedding {len(phrases)} anchor phrases for {name} ...")
        vecs = embed(phrases)
        assert len(vecs) == len(phrases), f"{name}: got {len(vecs)} vectors, expected {len(phrases)}"
        axis = mean_unit(vecs)
        all_phrases.append((name, axis))

    axis_vectors = dict(all_phrases)

    # Sanity: confirm each axis vector is unit-length.
    for name, ax in all_phrases:
        nrm = math.sqrt(sum(x * x for x in ax))
        print(f"  {name}: unit vector ready (dim={len(ax)}, norm={nrm:.4f})")

    # Cross-axis orthogonality check — warns if two axes are nearly parallel.
    names = [n for n, _ in all_phrases]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            dot = sum(a * b for a, b in zip(axis_vectors[names[i]], axis_vectors[names[j]]))
            print(f"  cos({names[i]} vs {names[j]}) = {dot:+.3f}")

    # Write constants.py (surgical AXIS_* refresh — all other toggles preserved).
    # Atomic write (L1 fix): same tmp+os.replace convention used elsewhere in the codebase.
    cpath = os.path.join(BASE_DIR, "constants.py")
    tmp = cpath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(build_constants(axis_vectors))
    os.replace(tmp, cpath)
    print("\nconstants.py updated in place (only AXIS_* vectors refreshed; all other toggles preserved).")

    # Write semantic_anchor into each planet JSON (clobber-guarded).
    print("Writing semantic_anchor fields into planets/*.json ...")
    write_planet_anchors()

    print("\nDone. Next: python -X utf8 resonance.py  (sanity check the full pipeline)")


if __name__ == "__main__":
    main()
