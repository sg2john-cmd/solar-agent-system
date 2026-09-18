"""
Resonant Cognition v17 — Phase 0D: Semantic Resonance (waveform collapse).

Implements the pipeline Maya confirmed in docs/mayas_questions_phase0d.md:

    embed(text) -> 384-dim MiniLM vector
        -> project_to_axes(vec) -> [x, y, z] cognitive axes   (Option B)
            -> for each of the 7 archetypes: cosine( input_dir , anchor_n )
                -> Resonance_n = sigmoid above RESONANCE_THRESHOLD
                    -> Weight_total = sum(W_planet_n * Resonance_n)
                        -> emergent merged vector = final Action State

Gravity / orbital position plays NO role here (Maya Q1/Q2: resonance is purely
semantic; gravity is spatial bookkeeping only). The comet is a SEPARATE path
(perturbation probe, not a resonance participant) and its trigger conditions are
still an open TODO — see the JESTER section below.

RUN A SANITY CHECK (no changes to other files):  python -X utf8 resonance.py
"""

from __future__ import annotations

import json as _json_module  # noqa: F401  (referenced below in except clause)
import math
import os
import time
import urllib.error
import urllib.request

# Import constants from the module next to this file (works regardless of cwd).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _HERE)
import constants as C


# ─── EMBEDDING ───────────────────────────────────────────────────────────────

# M2 fix (independent-review triage): a domain-specific exception so callers can catch
# "the embedding service is down / unreachable" distinctly from other failures, and the
# pipeline's catch-all no longer has to interpret raw urllib errors. Raised ONLY after
# the bounded retry budget is exhausted.
class EmbeddingUnavailableError(RuntimeError):
    """Raised when LM Studio embeddings cannot be reached even after retries."""


def _post_with_retry(payload: dict, *, op: str) -> dict:
    """POST a JSON payload to the local LM Studio /v1/embeddings endpoint.

    Bounded retry with exponential backoff (C.EMBED_RETRIES attempts total; attempt n
    waits C.EMBED_RETRY_BACKOFF_S * 2**(n-1) seconds before the next). Recovers from the
    classic transient case — model reloading between two calls in a long session, brief
    connection-refused, or a one-off 5xx. After the budget is exhausted it raises
    EmbeddingUnavailableError (NOT a raw urllib.error.URLError) so callers can catch and
    degrade gracefully. JSON decode errors are treated as transient too: a truncated body
    mid-restart should retry rather than crash.
    """
    url = f"http://{C.LM_STUDIO_HOST}:{C.LM_STUDIO_PORT}/v1/embeddings"
    attempts = max(1, int(getattr(C, "EMBED_RETRIES", 3)))
    base_backoff = float(getattr(C, "EMBED_RETRY_BACKOFF_S", 1.0))
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(
                url, data=_json_dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return _json_loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, _json_module.JSONDecodeError) as exc:
            last_exc = exc
            # Retryable network/parse failure. Back off before the next attempt unless it
            # was already the final one.
            if attempt < attempts:
                delay = base_backoff * (2 ** (attempt - 1))
                print(f"[resonance] {op}: attempt {attempt}/{attempts} failed ({exc!r}); "
                      f"retrying in {delay:.1f}s")
                time.sleep(delay)
    raise EmbeddingUnavailableError(
        f"{op}: LM Studio embeddings unreachable after {attempts} attempts. "
        f"Last error: {last_exc!r}. Is the model loaded at "
        f"http://{C.LM_STUDIO_HOST}:{C.LM_STUDIO_PORT}?"
    ) from last_exc


def embed(text: str) -> list[float]:
    """Embed a single string via LM Studio MiniLM. Returns the raw 384-dim vector.

    M2: retries transient failures (see _post_with_retry); raises
    EmbeddingUnavailableError once the retry budget is exhausted instead of leaking a raw
    urllib error to the caller.
    """
    body = _post_with_retry({"model": C.EMBEDDING_MODEL_ID, "input": [text]}, op="embed")
    return body["data"][0]["embedding"]


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings in one request (same retry/exception contract as embed)."""
    body = _post_with_retry({"model": C.EMBEDDING_MODEL_ID, "input": texts}, op="_embed_batch")
    rows = sorted(body["data"], key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in rows]


# Thin json wrappers so we can keep imports minimal at top.
def _json_dumps(o) -> str:
    import json; return json.dumps(o, ensure_ascii=False)

def _json_loads(s: str):
    import json; return json.loads(s)


# ─── PROJECTION (Option B — fixed direction vectors from constants.py) ────────

def project_to_axes(vec: list[float]) -> tuple[float, float, float]:
    """Project a 384-dim embedding onto the 3 cognitive axes via dot products.

    Option B: fixed AXIS_* direction vectors (Option A / PCA can replace them
    later behind this exact signature). Returns (x, y, z):
        x = Rationality(+)/Intuition(-)
        y = Preservation(+)/Disruption(-)
        z = Outward(+)/Inward(-)
    """
    x = sum(a * b for a, b in zip(vec, C.AXIS_RATIONALITY))
    y = sum(a * b for a, b in zip(vec, C.AXIS_PRESERVATION))
    z = sum(a * b for a, b in zip(vec, C.AXIS_OUTWARD))
    return x, y, z


def axes_to_384(axes: tuple[float, float, float]) -> list[float]:
    """Lift an [x, y, z] point back into 384-dim space (inverse of project_to_axes).

    Uses the minimum-norm (Moore-Penrose) pseudo-inverse of the projection map:
        v = x*A_R + y*A_P + z*A_O   where A_R/A_P/A_O are the fixed AXIS_* vectors.
    This is the canonical point in 384-dim that projects to (x,y,z). It lives in the
    3-dimensional span of the three axes, NOT in full MiniLM embedding space — which
    is exactly what we want for blending a planet's ORBITAL position with its 384-dim
    semantic identity in routing.py (Phase 1). The result may be unnormalized;
    callers that need a unit direction should normalize it themselves.

    NOTE: the three AXIS_* vectors are weakly independent (cos ~0.26-0.33), so this
    lift is well-conditioned enough for our purposes but not an exact round-trip basis.
    """
    x, y, z = axes[0], axes[1], axes[2]
    a_r = C.AXIS_RATIONALITY
    a_p = C.AXIS_PRESERVATION
    a_o = C.AXIS_OUTWARD
    return [x * a_r[i] + y * a_p[i] + z * a_o[i] for i in range(len(a_r))]


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v)) or 1.0


def _cosine(u: list[float], w: list[float]) -> float:
    num = sum(a * b for a, b in zip(u, w))
    den = _norm(u) * _norm(w)
    return max(-1.0, min(1.0, num / den if den else 0.0))


# ─── RESONANCE CORE (Maya's formula) ─────────────────────────────────────────

def sigmoid(x: float) -> float:
    # Guard against overflow for large negative x.
    return 1.0 / (1.0 + math.exp(-x)) if x > -745 else 0.0


class ResonanceResult:
    """Per-planet resonance contribution + the merged Action State."""
    def __init__(self):
        self.planet: str = ""
        self.similarity: float = 0.0     # cosine(input_dir, anchor)
        self.resonance: float = 0.0      # sigmoid above threshold (clamped 0..1)
        self.weight: float = 0.0         # W_planet * Resonance_n

    def __repr__(self):
        return (f"ResonanceResult(planet={self.planet!r}, sim={self.similarity:.3f}, "
                f"res={self.resonance:.3f}, weight={self.weight:.3f})")


def compute_resonance(input_axes: tuple[float, float, float],
                      anchors: dict[str, list[float]],
                      masses: dict[str, float]) -> tuple[list[ResonanceResult], dict]:
    """Given a projected input [x,y,z] and per-planet anchors+masses, return the
    per-planet resonance results and the merged Action State vector.

    - similarity  = cosine of the *directions* (input point vs anchor point) in 3D.
      Using directions (not raw magnitudes) keeps this a pure alignment measure,
      matching Maya's "alignment, not proximity" rule.
    - Resonance_n = sigmoid(k*(sim - threshold)), clamped to [0,1]. Below ~threshold
      it is near 0; above it ramps toward 1 (k = RESONANCE_SIGMOID_K).
    - Weight_total vector = sum over planets of W_planet * Resonance_n * anchor_dir.
    """
    results: list[ResonanceResult] = []
    merged = [0.0, 0.0, 0.0]
    input_len = _norm(list(input_axes))

    for pid in anchors:
        anchor = anchors[pid]
        sim = _cosine([*input_axes], list(anchor)) if input_len else 0.0
        res = sigmoid(C.RESONANCE_SIGMOID_K * (sim - C.RESONANCE_THRESHOLD))
        w = masses.get(pid, 1.0) * res
        r = ResonanceResult()
        r.planet, r.similarity, r.resonance, r.weight = pid, sim, res, w
        results.append(r)
        # Merge along the anchor DIRECTION so contribution is a clean vector sum.
        an = _norm(anchor)
        for i in range(3):
            merged[i] += w * (anchor[i] / an if an else 0.0)

    return results, {"merged_vector": merged}


def resonance_for_input(text: str,
                        anchors: dict[str, list[float]] | None = None,
                        masses: dict[str, float] | None = None) -> tuple[list[ResonanceResult], dict]:
    """Full pipeline for one input string. Defaults to constants.py tables."""
    if anchors is None:
        anchors = C.SEMANTIC_ANCHORS
    if masses is None:
        masses = C.PLANET_MASSES
    vec = embed(text)
    axes = project_to_axes(vec)
    # compute_resonance already returns (results, state) — pass it through unchanged.
    return compute_resonance(axes, anchors, masses)


# ─── JESTER / COMET (challenger — SEPARATE path, NOT a resonance participant) ─
# Maya Q4: the comet is a perturbation event / system probe. It does NOT join the
# weighted average above. Role (from John): "the fool in the room" — breaks tension
# when things get too heavy / one-sided / depressive / over-intellectual.
# TRIGGER CONDITIONS ARE STILL UNRESOLVED (see docs/phase0d_drafts.md). We expose a
# hook here and leave the actual predicate as an explicit TODO rather than guessing.

def should_comet_fire(session_state, input_axes: tuple[float, float, float]) -> bool:
    """TODO(Phase 8 / John): decide the real trigger predicate.
    Candidates discussed but NOT chosen yet: high-dissonance threshold, explicit user
    command, periodic interval, or 'one-sidedness' of the resonance field (e.g. a single
    planet dominating with the rest near-zero). Do not ship a default behavior here."""
    raise NotImplementedError(
        "Comet trigger conditions are intentionally unspecified. See docs/phase0d_drafts.md."
    )


# ─── SANITY CHECK / DEMO ─────────────────────────────────────────────────────

def _demo() -> None:
    print("Phase 0D resonance sanity check\n" + "=" * 50)
    samples = {
        "sage-ish (rational/analytical)":   "Please derive and verify this claim step by step with evidence.",
        "magician-ish (creative/intuitive)": "Imagine a brand-new way to connect these unrelated ideas.",
        "caregiver-ish (preserve/safe)":     "Keep things safe and steady; protect what already works here.",
        "rebel-ish (disrupt/change)":        "Break this assumption — it no longer holds up. Dispute it.",
        "hero-ish (outward action)":         "Stop planning and take concrete action right now to fix it.",
    }
    for label, text in samples.items():
        vec = embed(text)
        axes = project_to_axes(vec)
        results, state = compute_resonance(axes, C.SEMANTIC_ANCHORS, C.PLANET_MASSES)
        ranked = sorted(results, key=lambda r: r.weight, reverse=True)[:3]
        top = ", ".join(f"{r.planet}({r.weight:.2f})" for r in ranked)
        print(f"\n[{label}]")
        print(f"  axes [x,y,z] = [{axes[0]:+.3f}, {axes[1]:+.3f}, {axes[2]:+.3f}]")
        print(f"  top-3: {top}")
        mv = state["merged_vector"]
        print(f"  merged Action State = [{mv[0]:+.3f}, {mv[1]:+.3f}, {mv[2]:+.3f}]")


if __name__ == "__main__":
    _demo()
