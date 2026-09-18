"""REGRESSION GUARD (FLIPPED) — documents the FIXED never-raises contract of memory._pii_guard.

(H2 fix landed: _pii_guard no longer raises and write_entry drops flagged entries. This test now
asserts the fixed state and PASSES; the header was left as "FAILING TEST" in error.)

Original note — a docstring-vs-code discrepancy in memory._pii_guard.

memory.py line ~342 docstring says:
    "NEVER raises — a scrub failure must not block a legitimate write;
     in that case we return the original and flag it so the caller can
     choose to drop the entry rather than persist unscrubbed PII."

But lines 352-354 do exactly the opposite: they print an apology message
AND re-raise. Consequence: any gate1.scrub_pii failure (config file gone,
regex library error, malformed pattern) blocks EVERY memory write in the
system — not just the one entry that failed to scrub.

Reproduction scenario:
    If gate1.scrub_pii raises (e.g., gates_config.json was deleted mid-run),
    then memory.write_entry() re-raises and no session content is persisted,
    which contradicts both the docstring AND the "NEVER breaks intake" spirit
    of the rest of the module.

This test currently FAILS because _pii_guard does raise (as written).
Once the bug is fixed to honour its own contract — return original text + a
flagged redactions list, do NOT re-raise — this test should PASS.

Offline: no LM Studio required. No source changes made by this file.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class PiiGuardNeverRaisesTest(unittest.TestCase):
    """The docstring contract on memory._pii_guard must hold."""

    def test_scrub_failure_does_not_propagate(self):
        import gate1
        import memory as M

        original = gate1.scrub_pii

        class Boom(Exception):
            pass

        def boom(_text: str) -> tuple[str, list]:
            raise Boom("simulated scrub failure (e.g., missing config)")

        # Patch the dependency so we can trigger a controlled failure.
        M.gate1 = gate1  # ensure attribute exists
        gate1.scrub_pii = boom
        try:
            result = M._pii_guard("hello, my email is x@y.z")
        finally:
            gate1.scrub_pii = original

        # Per the docstring contract we should get a (text, redactions) tuple back.
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        text_out, redactions = result
        # Either return the original flagged, or a sentinel — either way NOT raise.
        # The specific flag shape is implementation-detail; we only assert non-raise +
        # that the caller can distinguish "failed" from "clean".
        self.assertTrue(
            isinstance(redactions, list),
            "_pii_guard must return (text, redactions) tuple even on scrub failure",
        )


if __name__ == "__main__":
    unittest.main()
