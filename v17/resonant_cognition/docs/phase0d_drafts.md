# Phase 0D (Resonance) — Design Drafts for Review

**Status: PROPOSAL ONLY. No code written yet.** Nothing in this file is load-bearing until you approve it.
Two artifacts, per the plan: (A) semantic anchor coordinates for the 7 archetypes; (B) the embedding→[x,y,z] projection approach (Option B).

---

## A quick note on what's CONFIRMED vs GUESS here

- **Confirmed (Maya + you):** waveform collapse is *semantic-only* (cosine similarity, no gravity/position);
  resonance = sigmoid above threshold 0.7; `Weight_total = Σ(W_planet × Resonance_n)` → merged vector.
- **Guessing (me, for your veto):** the exact [x,y,z] numbers below and the axis direction vectors in §B.
  These are my best reading of each planet's own JSON flavor text — not pulled from any earlier spec.
  If a number feels wrong against how you imagine that archetype, change it; they're plain data.

---

## A. Semantic anchor coordinates [x,y,z] (7 archetypes)

### The axes (confirmed by Maya)
- **X: Rationality ↔ Intuition**   → +X = rational/analytical
- **Y: Preservation ↔ Disruption**  → +Y = preservation/stability, −Y = disruption/change
- **Z: Inward Reflection ↔ Outward Execution** → see the SIGN QUESTION below.

Anchors are placed on a unit-ish sphere (magnitude ~1) so cosine similarity is well-behaved and direction-only matters.
Rationale for each is quoted from that planet's own `id_flavor` / `ego_descriptor`.

| Planet | [x, y, z] | Why (from its JSON) | Confidence |
|---|---|---|---|
| **sage** | `[ 1.0, +0.4, -0.5 ]` | "raw pattern and hidden structure before it is named" = strong rationality; "verifies... grounded evidence" = preserving established truth; works *inward* on the structure itself. | high (most unambiguous) |
| **magician** | `[-0.6, -0.5, +0.7 ]` | "impulse to reshape reality — make the impossible obvious"; temp 0.9 = intuition-led disruption; reshaping is outward creative action. | medium-high |
| **caregiver** | `[+0.2, +1.0, -0.3 ]` | "protective instinct — shield what matters"; most preservation of all seven (temp 0.6, rigid-ish); mostly inward attending. | high |
| **hero** | `[+0.4, -0.2, +1.0 ]` | "the drive to act — charge in where others hesitate"; clearest outward executor; slightly disrupts status quo by acting; pragmatic not contemplative. | medium-high |
| **everyman** | `[+0.2, +0.5, -0.6 ]` | "need to belong... shared human experience"; preservation of the social bond (temp 0.7); inward — introspective/relational rather than outward-acting. ← *my least confident pick; see note.* | **low-medium** |
| **rebel** | `[-0.4, -1.0, +0.2 ]` | "urge to break what no longer works"; the strongest −Y (disruption) in the set; temp 0.85; acts on assumptions (mildly outward). | high |
| **ruler** | `[+1.0, +0.6, +0.3 ]` | "will to impose order — make the chaos choose a shape"; rational/systematic ordering (rigid structure, cot_depth 3); preserves and maintains order; mildly outward (imposes on others). | medium-high |

**Design intent baked into these numbers:**
- Each archetype occupies a distinct *corner* of the space so their directions are genuinely non-collinear — this is what lets "2 weaker planets resonate past 1 dominant one" actually work mathematically. No two anchors share an axis signature.
- `everyman` and `caregiver` both lean +Y (preservation) but are separated on Z: caregiver = inward shield, everyman = relational glue. If you want them *more* distinct, push everyman's Y down toward 0.

**⚠️ The one value I'd most like you to double-check: `everyman`'s Z.**
"Grounds the system in shared human experience / common thread" could read as either inward (relational, introspective) or outward (social connection with others). I picked **inward (−Z)** on the reading that "belonging/understanding without translation" is a felt internal state. If you think Everyman is fundamentally *out toward* other people, flip it to `+0.6`.

### SIGN CONVENTION — please confirm before we bake these in
`constants.py` currently says **Z: positive = outward**. I've used that convention above (hero +1.0 Z, sage −0.5 Z).
This is a *one-line* decision but it silently inverts an entire axis for every future resonance calc if wrong — so flagging explicitly: **do you agree "positive = outward"?** If your instinct is the opposite ("inward reflection is the 'real'/positive direction"), tell me and I flip all Z signs + the comment.

### Where these live
New field `semantic_anchor` in each `planets/*.json`. This is safe from clobbering: `persist_seeded_state()` only rewrites the keys `position`, `velocity`, `orbital_plane_tilt_deg` — it does **not** touch any other key, so a new `semantic_anchor` field survives every passing test run. (Verified against integrator.py lines 645–686.)

---

## B. Embedding → [x,y,z] projection (Option B — fixed direction vectors)

### Why Option B over A
- **Option A (PCA)** needs a *labeled corpus* of "this is rational / this is disruptive..." to learn the axes from real data first. That's its own sub-project and risks repeating the "perfect foundation before anything works" stall we've hit before.
- **Option B** = 3 hand-picked, fixed 384-dim direction vectors, one per axis. Arbitrary but stable, fully inspectable (you can read them), and swappable later for a real PCA result with **zero interface change**.

### What it is concretely
Three named constant vectors in `constants.py`, each 384 floats, unit-normalized:

```python
# Option B placeholders — fixed, hand-picked direction vectors in MiniLM-384 space.
# Replace with PCA-derived axes (Option A) later WITHOUT changing any calling code.
# Interface is identical either way: project_to_axes(vec384) -> [x, y, z].
AXIS_RATIONALITY   = [...]  # 384 floats; dot(v, this) = x-component
AXIS_PRESERVATION  = [...]  # 384 floats; dot(v, this) = y-component
AXIS_OUTWARD       = [...]  # 384 floats; dot(v, this) = z-component
```

### How to *generate* the actual numbers (my recommendation — not a pure guess)
Rather than hand-typing 1152 random floats (uninspectable), I'd derive each axis vector by **averaging MiniLM embeddings of a handful of anchor phrases** that clearly sit at an extreme of that pole, then normalizing. E.g.:

- `AXIS_RATIONALITY` ← mean embedding of: *"a rigorous logical proof", "step-by-step mathematical derivation", "evidence and verification"*
- `AXIS_PRESERVATION` ← mean embedding of: *"maintain the status quo", "preserve what works", "keep things stable and safe"*
- `AXIS_OUTWARD` ← mean embedding of: *"take concrete action now", "implement and execute", "act on the world directly"*

This runs **once** against your LM Studio MiniLM (port 1234), bakes the resulting 384-floats into constants as a one-time calibration, and gives you vectors that are *meaningfully aligned* with how the model actually encodes those concepts — far better than uniform random. The phrase lists themselves are swappable if your instinct differs.

### Exact interface Phase 0D will consume
```python
def embed(text: str) -> list[float]:            # MiniLM via LM Studio -> 384-dim, L2-normalized
    ...

def project_to_axes(vec: list[float]) -> tuple[float, float, float]:
    """Option B: dot with each fixed axis direction. Returns (x, y, z)."""
    x = sum(a*b for a, b in zip(vec, AXIS_RATIONALITY))
    y = sum(a*b for a, b in zip(vec, AXIS_PRESERVATION))
    z = sum(a*b for a, b in zip(vec, AXIS_OUTWARD))
    return x, y, z

def resonance_for_input(text: str) -> list[ResonanceResult]:
    """embed -> project -> cosine vs each planet.semantic_anchor -> sigmoid>0.7 -> Weight_total."""
```

The 384-dim→[x,y,z] projection is a pure linear map; the anchor comparison (§A) then happens in that same 3D space, so everything downstream (sigmoid, weighting, merged vector) operates on comparable geometry.

### The one honest caveat about Option B
Because the axes are *chosen* rather than *learned*, "how rational" an input scores is only as good as my anchor-phrase list. That's fine for v1 — it gets you a working, inspectable, swappable system now; when you later have real labeled data, Option A drops in behind the exact same `project_to_axes` signature and the anchors (§A) don't need to move at all.

---

## Open sub-question (flagging, NOT guessing): what triggers the comet?
Maya confirmed the Jester is a **perturbation event / system probe**, not a resonance participant. But she never specified *what actually sends it in* — e.g.:
- high dissonance threshold (ΔD above X)?
- explicit user command?
- random/periodic interval?

`bodies.py:Comet.trigger_conditions` is already an empty list stub, so this won't block Phase 0D core work. I'll leave it as a clearly-marked TODO rather than inventing trigger logic. **Your call when you get to it.**

---

## What happens next
1. You review §A (anchors + everyman Z + sign convention) and §B (phrase lists / interface).
2. Tell me what to adjust — or "looks good."
3. Only then do I build `resonance.py` implementing: embed → project → cosine vs each anchor → sigmoid>0.7 → `Weight_total = Σ(W×Resonance)` → Action State, plus the one-time axis-vector calibration step.
