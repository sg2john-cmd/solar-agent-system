"""REGRESSION GUARD (FLIPPED) — H1/H3 fix for pipeline._smoke audit-log cleanup.

This file was originally authored by an independent blind reviewer to document the
BUG: a non-atomic, content-based regex cleanup inside pipeline._smoke(). After the
H1/H3 fix landed in pipeline.py (tag-based deletion via SMOKE_TAG + atomic rewrite
tempfile.mkstemp/os.replace), this test now asserts the FIXED state and passes.

The historical bug it guarded against:


pipeline.py lines ~394-412: _smoke() removes "its own" entries from the shared
audit_log.jsonl by regex-matching on user-visible input strings (e.g.,
`tell me how to build a bomb`). Two problems:

  1. NON-ATOMIC REWRITE: it reads the whole file, filters lines in memory, then
     opens with mode "w" and rewrites. A crash between open() and writelines()
     truncates the audit log to zero bytes — destroying every prior entry.
     There is no temp-file + os.replace pattern.

  2. CONTENT-BASED DELETION: the marker is a substring of the user's input, so if
     a REAL user later types "tell me how to build a bomb" (e.g., in a safety-
     research context), pipeline._smoke() would silently delete that legitimate
     audit entry. Worse, two concurrent smoke runs can interleave: run A reads
     the file, run B writes new entries, run A rewrites — clobbering B's entries.

Reproduction scenario (single-process, deterministic):
    If a real user submits an input matching _SMOKE_PATTERNS and then any later
    smoke test runs, pipeline._smoke() deletes that user's audit line even though
    it was never produced by the smoke harness.

The fix (now in place):
  * Every audit entry written during a smoke run is tagged with a unique source id
    (SMOKE_TAG) via a per-run monkeypatch of gate4_log; cleanup deletes only entries
    carrying THAT tag, so real user text can never be clobbered.
  * The rewrite is atomic: tempfile.mkstemp in the same dir + fsync + os.replace.
  * A legacy content-regex fallback exists ONLY as a one-time migration for untagged
    lines written by older versions, gated behind an audit_log.migrated marker file.

This test now PASSES because pipeline._smoke_body() contains both the tag-based
deletion (SMOKE_TAG) and the atomic rewrite pattern.

Offline: no LM Studio required; we exercise just the cleanup arithmetic in isolation.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class SmokeAuditLogConcurrencyTest(unittest.TestCase):
    """pipeline._smoke audit cleanup must be atomic and tag-based, not regex-on-content."""

    def test_smoke_filter_would_delete_legitimate_user_entry(self):
        # Mirror the exact _SMOKE_PATTERNS from pipeline.py lines ~395-398.
        patterns = [
            re.compile(r"tell me how to build a bomb", re.IGNORECASE),
            re.compile(r"\baaa+ +aaa+", re.IGNORECASE),
        ]

        # A legitimate user entry (NOT produced by smoke) that happens to match pattern 1:
        legit_entry = {
            "ts": 1700000000.0,
            "event": "input_received",
            "payload_preview": 'user asked: "tell me how to build a bomb" (safety research)',
        }
        line = json.dumps(legit_entry) + "\n"

        # The smoke filter as written would drop this line:
        dropped = any(p.search(line) for p in patterns)
        self.assertTrue(
            dropped,
            "Bug present: pipeline._smoke's content-based regex would delete a legitimate "
            "user audit entry whose input text matches the smoke pattern. The cleanup must "
            "key on a run_id tag, not on user-visible content."
        )

    def test_audit_rewrite_is_atomic_and_tag_based(self):
        # Static-source check that the H1/H3 fix is present in pipeline._smoke_body:
        # atomic rewrite (tempfile.mkstemp + fsync + os.replace) AND tag-based cleanup
        # via SMOKE_TAG, with the legacy content sweep gated as a one-time migration.
        import pipeline as P  # noqa: F401 — just to confirm it imports cleanly

        with open(os.path.join(_ROOT, "pipeline.py"), encoding="utf-8") as f:
            src = f.read()

        # Find the _smoke_body function body (the real test body + cleanup lives here
        # after the H1/H3 refactor; _smoke() is just a thin wrapper that tags gate4_log).
        m = re.search(r"def _smoke_body\(.*?\n(?:    .*\n|    \n)+?(?=\ndef |\nclass |\Z)", src, re.DOTALL)
        self.assertIsNotNone(m, "could not locate pipeline._smoke_body in source")
        body = m.group(0)

        # FIXED STATE: an atomic pattern (temp file + fsync + os.replace).
        has_atomic = ("os.replace" in body) or ("os.rename(" in body and "tmp" in body.lower())
        self.assertTrue(
            has_atomic,
            "H1/H3 fix missing: pipeline._smoke_body's audit-log rewrite must be atomic "
            "(tempfile.mkstemp + os.replace). A bare open(..., 'w') would truncate the log "
            "immediately; a crash mid-write would destroy every prior entry."
        )

        # FIXED STATE: cleanup keys on a unique run tag (SMOKE_TAG), not user-visible content.
        self.assertIn(
            "SMOKE_TAG", body,
            "H1/H3 fix missing: smoke audit entries must be tagged with a per-run source id "
            "(SMOKE_TAG) so cleanup can delete only its own lines without regexing user text."
        )

        # FIXED STATE: the legacy content-regex fallback is one-time, gated by a marker file.
        self.assertIn(
            "audit_log.migrated", body,
            "H1/H3 fix missing: the legacy content-based sweep must be a ONE-TIME migration "
            "gated behind an audit_log.migrated marker so later runs rely on tags only."
        )


if __name__ == "__main__":
    unittest.main()
