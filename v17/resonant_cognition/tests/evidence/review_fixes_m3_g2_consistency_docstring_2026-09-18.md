# M3 — g2_ops.py: `g2_moon_consistency` Docstring/Code Mismatch (Magnitude vs Direction)

**Date:** 2026-09-18  
**Segment:** Review Fix Pass, Segment 7 (M3) of the independent blind review  
**Reviewer priority position:** After M1; second of the M-tier fixes.

---

## Problem

The docstring for `g2_moon_consistency()` described step 2 as a **directional** check:

> *"check that its direction doesn't point 'away from' the Core's center of mass (C_core at origin) in a way that would increase distance beyond a threshold"*

The inline comment inside the function body reinforced this reading:

> *"does this delta point AWAY from origin... A self-model change that increases the system's distance from its center of gravity is a 'gravitational escape' risk..."*

**What the code actually does:** computes `_vector_magnitude(vec)` — a pure magnitude check with no directionality. A large inward-pointing vector (negative radial component) would be flagged identically to a large outward one.

---

## Why Magnitude-Only Is Correct Here

The reviewer offered two options: fix the docstring, or add directionality to the code.
**Magnitude-only is intentionally more conservative:**

| Vector type | Directional check only | Magnitude check (current) |
|-------------|----------------------|--------------------------|
| Large outward delta ("escape") | Flagged ✓ | Flagged ✓ |
| Large inward delta (collapse toward core) | Missed ✗ | Flagged ✓ |
| Small delta, any direction | Passes ✓ | Passes ✓ |

A large inward vector would compress the system's internal spacing — also a structural risk under Law #1/#3. The current behaviour is therefore correct; only the documentation was misleading.

---

## Fix Applied (`giants/g2_ops.py`)

**Docstring (step 2)** rewritten to accurately describe the magnitude check and explicitly note why directionality is intentionally omitted:

```
2. If the entry has a vector_position, check its MAGNITUDE against an
   escape threshold (G2_MAGNITUDE_CAP * 2). A large-magnitude delta in ANY
   direction — inward or outward — is held for review, because both
   "escaping gravitational containment" (outward) and a violent collapse
   toward the core (inward) are structural risks Law #1/#3 guard against.
   Directionality is intentionally NOT checked: magnitude-only is the more
   conservative bound and avoids false-passing a large inward vector that
   would compress the system's internal spacing.
```

**Inline comment** updated to remove the misleading "point AWAY from origin" language and reference the docstring for rationale.

**No code logic changed.** `G2_MAGNITUDE_CAP` value, threshold formula (`CAP * 2`), and all return paths are unchanged.

---

## Verification

**Command:** `python -X utf8 giants/g2_ops.py`  
**Wall time:** 0.1 s — fully offline.

```
g2_ops.py Segment 3 self-test: ALL PASS (G2 Self-Model Moons)   [34/34]
```

All pre-existing checks pass unchanged, confirming no behavioural drift from the doc-only fix.

**Exit code:** 0
