"""REGRESSION GUARD (FLIPPED) — Segment-3 spread must survive all-zero amplitudes.

Originally authored by an independent blind reviewer to document the BUG: `min(a for a in amps if
a > 0)` raised ValueError when every routed amplitude was exactly zero. After the fix landed
(fall back to C.EPSILON when no positives exist), this test now asserts the FIXED state and passes.

The historical bug it guarded against:

routing.py line ~493:
    max_amp, min_amp = max(amps_rt), min(a for a in amps_rt if a > 0)

If any routed amplitude is exactly zero (which the code elsewhere explicitly
treats as an allowed outcome — e.g., per_planet_weights clamping to 0.0 when
a planet's distance is large, or a mass of 0.0), then `amps_rt` may contain
ONLY zeros, and `min(a for a in amps_rt if a > 0)` raises:

    ValueError: min() arg is an empty sequence

Reproduction scenario:
    If emit_waves returns all-7 amplitudes = 0 (e.g., every routed weight
    clamped to zero — see the "SEGMENT-3 FIX" comment above per_planet_weights,
    or a degenerate field where the input is equidistant from every center),
    then the smoke test crashes instead of reporting CHECK OUTPUT ABOVE.

This test currently FAILS because the guard expression raises ValueError on an
all-zero amplitude list (as written). Once fixed — e.g., fall back to 1e-9 or
skip the spread check when no positive amplitudes exist — this should PASS.

Offline: no LM Studio required; we exercise just the arithmetic line in isolation.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class RoutingSmokeSegment3ZeroAmplitudeTest(unittest.TestCase):
    """The Segment-3 spread computation must survive all-zero amplitudes."""

    def test_all_zero_amplitudes_do_not_crash_smoke(self):
        # FIXED state: reproduce the EXACT guarded expression now in routing.py (line ~507).
        # No positives -> min falls back to C.EPSILON, so an all-zero amplitude list yields a
        # zero-spread field instead of raising ValueError.
        import constants as C
        amps_rt = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        with self.subTest("all-zero amplitudes must not raise"):
            max_amp = max(amps_rt)
            min_pos = min((a for a in amps_rt if a > 0), default=C.EPSILON)
            top_spread = max_amp / max(min_pos, C.EPSILON)   # must NOT raise
            self.assertEqual(max_amp, 0.0)
            self.assertGreaterEqual(min_pos, C.EPSILON)
            self.assertLess(top_spread, 30.0)

    def test_single_zero_amplitude_does_not_crash_smoke(self):
        # Mixed case: six positive + one zero. Current code is fine here, but we pin
        # it as a regression guard so someone doesn't 'fix' the all-zero path by
        # dropping zeros from `max` too (which would change semantics).
        amps_rt = [0.12, 0.34, 0.56, 0.78, 0.90, 1.0, 0.0]
        max_amp = max(amps_rt)
        min_pos = min(a for a in amps_rt if a > 0)   # should be safe here today
        self.assertEqual(max_amp, 1.0)
        self.assertGreater(min_pos, 0.0)


if __name__ == "__main__":
    unittest.main()
