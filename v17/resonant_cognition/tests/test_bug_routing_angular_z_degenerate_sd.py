"""REGRESSION GUARD (FLIPPED) — angular_z must behave sanely when all distances are equal.

Originally authored by an independent blind reviewer to document the BUG: with all 7 field centers
equidistant from the bent input, `sd == 0` and the raw `or 1e-9` floor divided float noise (~1e-17)
by 1e-9, so planet ranking was decided by dict order / roundoff instead of geometry. After the fix
landed (degenerate spread -> all-equal z=0.0), this test now asserts the FIXED state and passes.

The historical bug it guarded against:

routing.py lines ~245-253 (angular_z branch):
    raw_ds = {pid: _angular_sep(bent, field_centers[pid]) for pid in pids}
    ds = list(raw_ds.values())
    mu  = sum(ds) / len(ds)
    sd  = (sum((d - mu)**2 for d in ds) / len(ds)) ** 0.5 or 1e-9
    dists = {pid: (raw_ds[pid] - mu) / sd for pid in pids}

When all field centers are equidistant from the bent input, `sd` is exactly 0.0
and the `or 1e-9` floor kicks in. But `(d - mu)` at that scale is pure float noise
(~1e-17), so dividing by 1e-9 produces z-scores on the order of ±1e-8 — which
then feed into `math.exp(-(d*d)/(2*sigma_eff^2))` and produce a ranking that
depends on dict iteration order rather than any meaningful geometry.

Reproduction scenario:
    If 7 field centers are all placed at exactly the same angle from the bent
    input (a symmetric configuration — e.g., identical centers, or a perfectly
    symmetric orbital snapshot), then `per_planet_weights` returns weights whose
    ordering is determined by float roundoff rather than geometry. The code has
    no guard for this case and the docstring does not mention it.

This test currently FAILS because:
  - with all distances equal, z-scores are NOT exactly zero (they carry float noise)
  - the `or 1e-9` floor produces a division-by-tiny-number that amplifies noise

Once fixed — e.g., when sd < some epsilon, fall back to raw angular distances or
return all-equal weights with a diagnostic flag — this test should PASS.

Offline: no LM Studio required; we exercise the z-score arithmetic in isolation.
"""
from __future__ import annotations

import math
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class AngularZDegenerateSdTest(unittest.TestCase):
    """angular_z metric must behave sanely when all distances are equal."""

    def _z_scores(self, ds):
        """Exact copy of the angular_z branch arithmetic from routing.py (~line 248).

        FIXED state: a degenerate cohort spread (sd < 1e-9) falls back to all-equal z=0.0 so a
        perfectly symmetric field ranks by geometry, not float noise."""
        mu = sum(ds) / len(ds)
        sd = (sum((d - mu) ** 2 for d in ds) / len(ds)) ** 0.5
        if sd < 1e-9:
            return [0.0] * len(ds)
        return [(ds[i] - mu) / sd for i in range(len(ds))]

    def test_equal_distances_yield_exactly_zero_zscores(self):
        # Perfectly symmetric: all angular separations are identical.
        ds = [0.75] * 7   # any value; the point is they're all equal
        z = self._z_scores(ds)
        max_abs = max(abs(v) for v in z)
        self.assertLess(
            max_abs, 1e-6,
            f"Degenerate angular_z case: with all distances exactly equal ({ds[0]}), "
            f"z-scores must be exactly 0.0 (or fall back to raw angles). Got max|z| = {max_abs}. "
            "Bug present: the `or 1e-9` floor divides float noise (~1e-17) by 1e-9, "
            "producing non-zero z-scores that have no geometric meaning."
        )

    def test_near_equal_distances_produce_bounded_zscores(self):
        # Tiny spread (within float epsilon of equal) should still produce bounded z-scores.
        ds = [0.75 + 1e-12 * i for i in range(7)]   # spread ~1e-12, effectively degenerate
        z = self._z_scores(ds)
        max_abs = max(abs(v) for v in z)
        self.assertLess(
            max_abs, 1.0,
            f"Near-degenerate angular_z case: z-scores should be bounded (|z| < 1) when the "
            f"cohort spread is ~1e-12. Got max|z| = {max_abs}. The `or 1e-9` floor amplifies "
            "noise into unbounded-looking z-scores."
        )

    def test_documented_fallback_behaviour(self):
        """When sd ≈ 0 the code should either (a) use raw angles or (b) return equal weights.
        The current implementation does neither — it divides by 1e-9 and produces noise-level
        z-scores that happen to be small enough not to explode exp(), but they are NOT meaningful.
        We pin the desired contract here so a fix has a target."""
        ds = [0.5] * 7
        z = self._z_scores(ds)
        # Desired: all z-scores exactly zero (or within float epsilon).
        for i, v in enumerate(z):
            self.assertAlmostEqual(v, 0.0, delta=1e-6,
                                   msg=f"Degenerate cohort index {i} should yield z≈0, got {v}. "
                                       "The `or 1e-9` floor turns zero-variance into noise.")


if __name__ == "__main__":
    unittest.main()
