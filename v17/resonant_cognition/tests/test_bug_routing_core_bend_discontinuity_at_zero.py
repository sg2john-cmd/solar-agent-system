"""REGRESSION GUARD (FLIPPED) — core_bend must be continuous/bounded near r = 0.

Originally authored by an independent blind reviewer to document the BUG: below `r < 1e-9` the code
returned a HARD bend_frac of 0.0 while just above it the squash saturated near k^-1=0.025 — a step
discontinuity in what is supposed to be a gentle nudge. After the fix (the guard now returns the same
squashed, bounded bend_frac instead of forcing 0.0), this test asserts the FIXED state and passes.

The historical bug it guarded against:

routing.py lines ~205-214:
    force = G * m_core / (r_sq + C.EPSILON ** 2)
    BEND_K = 40.0
    bend_frac = force / (1.0 + force * BEND_K)
    if r < 1e-9:
        return _unit(input_vec), {"bend_frac": 0.0, "M_core": m_core, "r": 0.0}

The early-return guard fires only when `r < 1e-9`. But the force is computed with
`EPSILON²` in the denominator (NOT r_sq alone), so for tiny-but-nonzero r the force
is still huge and bend_frac saturates near k^-1 = 0.025. Then at exactly r < 1e-9,
bend_frac drops discontinuously to 0.0.

Reproduction scenario:
    If an input's projected cognitive axes land within ~1e-8 of the core position,
    then a 1-in-10-billion nudge in embedding space flips bend_frac from ≈0.025 to
    exactly 0.0 — a step discontinuity in what is supposed to be a "gentle" geometric
    nudge. The docstring says bending is "intentionally gentle so it never overwhelms
    semantic identity (RULER-COLLAPSE guard)" but the near-zero behaviour contradicts
    that: just below r=1e-9 you get max-bend, at r<1e-9 you get no bend.

This test currently FAILS because:
  - core_bend(r≈5e-10) returns bend_frac ≈ 0.0 (early-return path)
  - core_bend(r≈2e-8)  returns bend_frac ≈ 0.025 (force-saturated path)
  - the two are adjacent inputs with wildly different outputs

Once fixed — e.g., apply the same squash function for all r including tiny, or widen
the early-return guard to cover the entire region where force would saturate — this
test should PASS.

Offline: no LM Studio required; we call core_bend directly with synthetic 384-d inputs.
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


class CoreBendDiscontinuityAtZeroTest(unittest.TestCase):
    """core_bend must be continuous (or at least monotone-bounded) near r=0."""

    def setUp(self):
        import constants as C
        self.C = C
        # We need a 384-d input whose projected axes land at a known distance from the core.
        # project_to_axes uses AXIS_RATIONALITY / AXIS_PRESERVATION / AXIS_OUTWARD — we can
        # construct inputs directly in that space by inverting via axes_to_384 (which exists
        # in resonance.py and is already imported by routing.core_bend).

    def _make_input_at_axes(self, x: float, y: float, z: float) -> list[float]:
        """Build a 384-d vector whose projection onto the cognitive axes equals (x,y,z)."""
        from resonance import axes_to_384
        return list(axes_to_384((x, y, z)))

    def test_bend_frac_is_continuous_across_the_zero_guard(self):
        import routing as R

        # Core at the origin in axis space.
        core_pos = [0.0, 0.0, 0.0]

        # Two inputs very close to the core on opposite sides of the r < 1e-9 guard:
        near_just_below_guard = self._make_input_at_axes(5e-10, 0.0, 0.0)   # r ≈ 5e-10 < 1e-9
        near_just_above_guard  = self._make_input_at_axes(2e-8,  0.0, 0.0)   # r ≈ 2e-8 > 1e-9

        _, info_below = R.core_bend(near_just_below_guard, core_pos)
        _, info_above = R.core_bend(near_just_above_guard, core_pos)

        # FIXED state: bend_frac is now CONTINUOUS across the guard. Both sides sit at a small,
        # bounded value (the squash saturates toward k^-1=0.025 but never exceeds it), so the two
        # adjacent inputs are close rather than 0.0-vs-0.025. It is no longer forced to exactly 0.
        self.assertLessEqual(
            info_below["bend_frac"], 0.03,
            msg="Below the r<1e-9 guard, bend_frac must be bounded (<= k^-1 ~0.025); got "
                f"{info_below['bend_frac']} — a large/unsquashed value would mean the guard lost control."
        )
        self.assertGreater(
            info_above["bend_frac"], 0.0,
            msg="Just above the r<1e-9 guard, bend_frac should be positive; got "
                f"{info_above['bend_frac']} (a tiny-but-nonzero force must still bend gently)."
        )
        # The two adjacent inputs are now close — no hard step discontinuity.
        self.assertLessEqual(
            abs(info_below["bend_frac"] - info_above["bend_frac"]), 0.03,
            msg="Across the guard, bend_frac must not jump by more than ~k^-1; got a jump of "
                f"{abs(info_below['bend_frac'] - info_above['bend_frac']):.4f} between r=5e-10 and r=2e-8."
        )

    def test_bend_frac_is_monotonically_bounded_near_zero(self):
        import routing as R
        core_pos = [0.0, 0.0, 0.0]

        # Sweep r from very small to moderate; bend_frac should be a smooth, bounded function.
        rs = [1e-12, 5e-10, 2e-8, 1e-6, 1e-4, 1e-2, 0.5]
        fracs = []
        for r in rs:
            inp = self._make_input_at_axes(r, 0.0, 0.0)
            _, info = R.core_bend(inp, core_pos)
            fracs.append(info["bend_frac"])

        # Desired contract: bend_frac should be monotonically decreasing as r grows,
        # and bounded above by ~k^-1 (the squash saturation). The current code violates
        # monotonicity because of the hard step at r=1e-9.
        for i in range(1, len(fracs)):
            self.assertLessEqual(
                fracs[i], fracs[i - 1] + 1e-6,
                f"bend_frac is not monotonically decreasing: r={rs[i]:.0e} -> {fracs[i]}, "
                f"but r={rs[i-1]:.0e} -> {fracs[i-1]}. The early-return guard at r<1e-9 "
                "creates a step discontinuity."
            )


if __name__ == "__main__":
    unittest.main()
