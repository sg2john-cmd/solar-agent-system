"""REGRESSION GUARD (FLIPPED) — M2/guard fix: session-history dir-length validation.

Originally authored by an independent blind reviewer to document the BUG: run_collapse fed
session_history dirs straight into the wave superposition with no length check, so a
degenerate dir (empty or wrong dimension) either raised IndexError later or silently
truncated the consensus vector via zip. After the guard landed (skip-and-log empty/short
dirs; raise ValueError on a non-empty WRONG-length dir), this test asserts the FIXED state.

The historical bug it guarded against:


collapse.py lines ~392-394:
    if session_history:
        for i, (u_dir, amp) in enumerate(session_history):
            waves[f"_ctx_{i}"] = {"dir": list(u_dir), "amplitude": float(amp)}

There is no check that `u_dir` has the expected length or is non-empty. The direction
vector later flows into `_unit(dir)` (line ~90) which does `[x / n for x in v]` with
`n = _norm(v) or 1.0`. A zero-length list yields norm 0 → falls back to `or 1.0`, so
_unit returns an empty list, and subsequent vector arithmetic (`waves[pid]["dir"][i]`)
raises IndexError OR silently produces a shorter-than-384 wave that later breaks the
pair-map / consensus-vector math (zip stops at the shortest operand).

Reproduction scenario:
    If SessionMemory.get_background_waves() returns an entry with `question_vec=[]`
    (e.g., a malformed persisted turn where the embedding failed to save), then
    run_collapse's superposition contains a zero-length context wave, and the
    consensus-vector computation silently truncates — downstream readers see a
    shorter-than-384 vector and either crash on indexing or compute garbage.

The fix (now in place):
  * An EMPTY (zero-length) context dir is SKIPPED and logged — a failed embed that persisted
    an empty question_vec must not poison the field. run_collapse returns normally and no
    degenerate _ctx_* wave enters the superposition.
  * A non-empty dir whose length != C.EMBEDDING_DIM raises ValueError early, because that is
    a real bug in whatever produced the history and must surface loudly (not be silently
    truncated or padded).

This test now PASSES: the empty-dir case no longer crashes, and the wrong-length case raises
a clear ValueError.

Offline: no LM Studio required; we construct a minimal fake collapse input directly.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class CollapseSessionHistoryZeroLengthDirTest(unittest.TestCase):
    """run_collapse must reject or skip session_history entries with degenerate dirs."""

    def test_zero_length_context_dir_does_not_silently_poison_superposition(self):
        import collapse as Cc

        # Minimal synthetic input: a 3-dim space is enough to expose the arithmetic bug.
        # (We don't need full 384-d; _unit and the zip-based sums work in any dim.)
        DIM = 3

        # A legitimate planet center + a degenerate zero-length context direction.
        centers = {"pluto": [1.0, 0.0, 0.0]}
        input_vec = [0.5, 0.5, 0.5]

        session_history_bad = [([], 0.3)]   # empty dir — the degenerate case

        # FIXED STATE: a zero-length context dir is SKIPPED (and logged), so run_collapse must
        # NOT crash with an indexing/value error, and no degenerate _ctx_* wave may enter the
        # superposition. (The earlier bug let it propagate into later arithmetic.)
        result = Cc.run_collapse(
            "test question",
            session_history=session_history_bad,
            g2_bias_vector=None,
            routed_weights=None,
        )
        # The empty entry must have been skipped — no _ctx_0 key should exist in the waves.
        self.assertNotIn("_ctx_0", result.get("waves", {}),
                         "Empty context dir was not skipped; it entered the superposition.")

    def test_mismatched_length_context_dir_raises_valueerror(self):
        """FIXED STATE: a non-empty context dir of the WRONG length raises a clear ValueError
        (a real bug in the history producer must surface loudly, not be silently dropped)."""
        import collapse as Cc

        # A context dir with the WRONG length (2 instead of 384) — must raise ValueError.
        session_history_bad_len = [([1.0, 0.0], 0.3)]   # len 2 != EMBEDDING_DIM(384)

        raised = None
        try:
            Cc.run_collapse(
                "test question",
                session_history=session_history_bad_len,
                g2_bias_vector=None,
                routed_weights=None,
            )
        except Exception as e:
            raised = e

        self.assertIsInstance(
            raised, ValueError,
            f"M2/guard fix missing: expected a clear ValueError for mismatched context dir "
            f"length; got {type(raised).__name__ if raised else 'no exception'}"
        )


if __name__ == "__main__":
    unittest.main()
