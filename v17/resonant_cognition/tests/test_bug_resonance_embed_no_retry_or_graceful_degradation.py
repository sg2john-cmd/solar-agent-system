"""REGRESSION GUARD (FLIPPED) — M2 fix: retry + domain exception in resonance embedding.

Originally authored by an independent blind reviewer to document the BUG: raw urlopen with
no retry and no try/except, so any transient LM Studio hiccup propagated a raw urllib error
up to pipeline.run()'s catch-all. After the M2 fix landed (bounded exponential-backoff retry
+ EmbeddingUnavailableError), this test now asserts the FIXED state and passes.

The historical bug it guarded against:


resonance.py lines 36-59: both functions do a raw `urllib.request.urlopen(req, timeout=120)`
with NO retry and NO try/except. Any transient LM Studio hiccup (connection refused during a
restart, 5xx from the server, malformed JSON) propagates straight up to pipeline.run()'s
catch-all at STEP 4 → status="error". There is no back-off, no circuit breaker, no fallback
to a cached embedding, and no user-facing explanation of WHICH planet wave failed.

Reproduction scenario:
    If LM Studio is momentarily unavailable (e.g., the model is re-loading between
    two calls in a long session), then `resonance.embed("hello")` raises urllib.error.URLError
    and pipeline.run() returns {"status": "error", ...}. A single retry with exponential
    backoff would have recovered, but the code has no such logic.

The fix (now in place):
  * embed / _embed_batch route through _post_with_retry, which retries C.EMBED_RETRIES times
    with exponential backoff before giving up.
  * After the budget is exhausted it raises resonance.EmbeddingUnavailableError — a domain-
    specific type callers can catch to degrade gracefully (not a raw urllib.error.URLError).

This test now PASSES because embedding an unreachable endpoint raises EmbeddingUnavailableError
and the module exposes that domain exception plus a retry helper.

Offline: no LM Studio required; we point at a closed local port to trigger the failure path.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class EmbedNoRetryOrGracefulDegradationTest(unittest.TestCase):
    """resonance.embed must degrade gracefully (or retry) when LM Studio is unreachable."""

    def test_embed_against_closed_port_raises_domain_error(self):
        import constants as C
        import resonance as R

        # Save and swap in a dead port so we don't depend on LM Studio state.
        saved_host, saved_port = C.LM_STUDIO_HOST, C.LM_STUDIO_PORT
        try:
            C.LM_STUDIO_HOST = "127.0.0.1"
            C.LM_STUDIO_PORT = 1   # port 1 is effectively closed on Windows/Linux/macOS

            raised = None
            try:
                R.embed("hello world")
            except Exception as e:
                raised = e

            self.assertIsNotNone(
                raised,
                "Expected resonance.embed to raise when LM Studio is unreachable; it did not."
            )
            # FIXED STATE: the exception is a domain-specific EmbeddingUnavailableError that
            # callers can catch and recover from — NOT a raw urllib.error.URLError.
            self.assertIsInstance(
                raised, R.EmbeddingUnavailableError,
                f"M2 fix missing: expected EmbeddingUnavailableError, got {type(raised).__name__}: {raised}"
            )
        finally:
            C.LM_STUDIO_HOST, C.LM_STUDIO_PORT = saved_host, saved_port

    def test_embed_batch_has_same_guard(self):
        import constants as C
        import resonance as R

        saved_host, saved_port = C.LM_STUDIO_HOST, C.LM_STUDIO_PORT
        try:
            C.LM_STUDIO_HOST = "127.0.0.1"
            C.LM_STUDIO_PORT = 1

            raised = None
            try:
                R._embed_batch(["a", "b"])
            except Exception as e:
                raised = e

            self.assertIsNotNone(raised, "Expected _embed_batch to raise when LM Studio is unreachable")
            # FIXED STATE: same domain exception contract as embed.
            self.assertIsInstance(
                raised, R.EmbeddingUnavailableError,
                f"M2 fix missing in _embed_batch: expected EmbeddingUnavailableError, got {type(raised).__name__}: {raised}"
            )
        finally:
            C.LM_STUDIO_HOST, C.LM_STUDIO_PORT = saved_host, saved_port

    def test_embed_exposes_retry_and_domain_exception(self):
        """FIXED STATE: the module now exposes BOTH a retry mechanism AND a domain-specific
        exception, so a transient LM Studio hiccup no longer kills the whole pipeline."""
        import resonance as R

        has_retry = (hasattr(R, "embed_with_retry") or hasattr(R, "_retry_embed")
                     or hasattr(R, "_post_with_retry"))
        has_domain_exc = (hasattr(R, "EmbeddingUnavailableError")
                          or hasattr(R, "EmbeddingTimeoutError")
                          or hasattr(R, "LMStudioError"))
        self.assertTrue(
            has_retry,
            f"M2 fix missing: resonance exposes no retry mechanism. has_retry={has_retry}"
        )
        self.assertTrue(
            has_domain_exc,
            f"M2 fix missing: resonance exposes no domain-specific exception. "
            f"has_domain_exc={has_domain_exc}. A single transient LM Studio hiccup would kill the pipeline."
        )


if __name__ == "__main__":
    unittest.main()
