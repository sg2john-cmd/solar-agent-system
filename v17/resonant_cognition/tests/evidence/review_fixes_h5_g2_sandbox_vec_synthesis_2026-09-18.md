# H5 — g2_sandbox.py: Baseline-Wave Vec Mismatch (Option B)

**Date:** 2026-09-18  
**Segment:** Review Fix Pass, Segment 5 of the independent blind review  
**Reviewer priority position:** 5th (after C1+M4, H1/H2/H3, M2, H4)  
**Approach chosen:** **Option B** — synthesize a semantic vec from entry text via local embedder when missing.  
User explicitly approved: *"if it works a, but if a just looks good but does nothing, b."*

---

## Diagnosis (two-vector-concept conflation)

Two distinct "vector" concepts had been conflated in the G2 sandbox:

| Key | Meaning | Written by | Used by |
|-----|---------|-----------|---------|
| `entry["vec"]` | 384-dim **semantic embedding** (session flavour) | `memory.summarize_session_for_g2()` → goes into `contents[]` | `_aggregate_bias`, `candidate_bias_wave` — the bias wave IS built from semantic embeddings |
| `entry["vector_position"]` | Short 3-dim **spatial delta** | `giants/g2_ops.py::g2_add_candidate()` → goes into `ring_buffer[]` | The argument actually passed to `try_candidate()` in production |

Because `g2_add_candidate()` writes `"vector_position"` (not `"vec"`) and no production
path ever added a semantic `"vec"` before calling `try_candidate`, **every ring-buffer
candidate** hit the "no vec → PASS-with-note" early-return. The sandbox gate therefore
never actually trialed anything in production — it was silently bypassing its own purpose.

Confirmed by grep of `sleep.py`: no caller adds `"vec"` to a ring_buffer entry before
calling `try_candidate`. Only self-tests and docs referenced the missing-key path.

---

## What Was Changed (`giants/g2_sandbox.py`, now 683 lines)

### 1. New helper `_synthesize_vec_if_needed(entry, embed_fn=None)` (~line 195)
- If `entry` already has a usable `"vec"` → return it unchanged + empty notes.
- Else if it has text and an `embed_fn` is available → call it **once**, attach the result to a **shallow copy** of the entry (original dict never mutated), append an auditable note.
- If embedding raises or returns empty → return original entry + specific failure note so the caller's existing PASS-with-note path still fires with full auditability.
- If no text and no vec → return original + "no text to embed" note.

### 2. `try_candidate()` signature changed (~line 240)
Added optional `embed_fn=None` parameter. Inside: if `embed_fn is None`, lazy-imports
`from resonance import embed as _default_embed` (only when needed; OFF path stays
import-free). Calls `_synthesize_vec_if_needed` **before** the existing "no vec" early-return,
so ring-buffer candidates now actually get trialed.

### 3. Docstrings updated
On `_aggregate_bias`, `candidate_bias_wave`, and `try_candidate` to explicitly distinguish
the two vector concepts and explain where synthesis happens. The "no vec → PASS-with-note"
note text in `try_candidate` was reworded to reflect that it's now only reachable when
synthesis **also** failed.

### 4. Self-test expanded (all offline, stubbed embed_fn — NO LM Studio needed)
- `[6b-H5a]–[6b-H5h]`: unit tests for `_synthesize_vec_if_needed` — ring-buffer entry gets synthesized vec on a copy; original not mutated; embedder called exactly once with the right text; existing-vec entries pass through unchanged; embed failure falls through to PASS-with-note note; no-text entry produces no embed call.
- `[6c-H5a]–[6c-H5c]`: end-to-end `try_candidate` test with a stubbed `embed_fn` AND a monkeypatched `collapse` module (`sys.modules["collapse"] = fake_collapse_mod`) so NO real LM call happens — proves a vector_position-only ring-buffer entry now results in `prompts_run == 3`, the synthesized-vec note is present, and `run_collapse` was called exactly 6 times (3 prompts × baseline+candidate).
- The pre-existing `[6b]` "candidate wave matches manual aggregation" check (accidentally deleted during a botched multi-edit in the prior session) was **restored**.

---

## Verification Output

Command: `python -X utf8 giants/g2_sandbox.py`  
Wall time: 0.1 s — fully offline, no network access required.

```
============================================================
g2_sandbox.py — Phase 7 Segment 4 self-test (G2 Sandbox)
============================================================
  [PASS] [1a] Toggle OFF: status=skipped
  [PASS] [1b] Toggle OFF: zero prompts run
  [PASS] [1c] Toggle OFF: reason mentions disabled
  [PASS] [1d] Toggle OFF: no new pipeline modules loaded (collapse/memory not imported fresh)
  [PASS] [2a] cos(identical) ≈ 1.0
  [PASS] [2b] cos(opposite) ≈ −1.0
  [PASS] [2c] cos(orthogonal) = 0.0
  [PASS] [2d] cos(mismatched dims) = 0.0
  [PASS] [2e] cos(zero vector) = 0.0
  [PASS] [3a] shift(2.0, 2.5) = 0.5
  [PASS] [3b] shift is symmetric
  [PASS] [3c] shift identical = 0.0
  [PASS] [4a] small shift + high coherence → PASS
  [PASS] [4b] huge tension shift → FAIL even if coherent
  [PASS] [4c] low coherence → FAIL even if tension stable
  [PASS] [4d] exactly at thresholds → PASS (<= and >= are inclusive)
  [PASS] [5a] Two same-direction entries: unit dir points +x
  [PASS] [5c] Vec-less entry ignored: dir still +x
  [PASS] [5d] Opposing entries: net dir flips to the stronger (−x)
  [PASS] [5e] No usable vecs at all → None
  [PASS] [6a] candidate_bias_wave(plain entry) → None
  [PASS] [6b-H5a] Ring-buffer entry (no vec) gets a synthesized vec
  [PASS] [6b-H5b] Synthesized vec attached to a COPY — original not mutated
  [PASS] [6b-H5c] Embedder was called exactly once with the entry's text
  [PASS] [6b-H5d] Synthesis note explains what happened (auditable)
  [PASS] [6b-H5e] Entry with existing vec is returned unchanged
  [PASS] [6b-H5f] Embed failure → original entry returned (no vec added)
  [PASS] [6b-H5g] Embed failure note is recorded for audit
  [PASS] [6b-H5h] No-text entry: no embed call, note recorded
  [PASS] [6c-H5a] Ring-buffer candidate now actually TRIED (prompts_run>0)
  [PASS] [6c-H5b] Report notes include the synthesis explanation
  [PASS] [6c-H5c] run_collapse was called (baseline + candidate per prompt)
  [PASS] [6b] candidate wave matches manual aggregation (cos ≈ 1)
  [PASS] [7a] Multiday scaffold returns not_implemented
  [PASS] [7b] Scaffold points to the documented upgrade path
  [PASS] [8a] G2_SANDBOX_ENABLED matches constants
  [PASS] [8b] Tension-shift threshold matches constants (0.30)
  [PASS] [8c] Coherence minimum matches constants (0.70)
  (info) live G2_SANDBOX_ENABLED = False (dev default OFF; flip in constants.py for production)

g2_sandbox.py Segment 4 self-test: ALL PASS (G2 Sandbox, offline)
```

**Exit code:** 0  
**All checks passed**, including all new H5 cases.

---

## Operational Note

`try_candidate()` now makes **ONE embedding HTTP call per ring-buffer candidate it trials**,
only when `G2_SANDBOX_ENABLED=True`. The OFF path (`G2_SANDBOX_ENABLED=False`) remains
zero-call and import-free — no change to the dev-time behaviour. At final release, with
moons mandatory ON and sandbox presumably ON in production, expect one additional local
MiniLM embed call per candidate commit — negligible against the existing LLM pipeline cost.

---

## Remaining Fix List (per reviewer, after H5)

| Priority | Item | File(s) | Description |
|----------|------|---------|-------------|
| M1 | Fragile `dir()` guards in pipeline diagnostics | `pipeline.py` | Check consistency with M2 fix style |
| M3 | `g2_moon_consistency` doc claims directional check, code only checks magnitude | `giants/g2_ops.py` or related | Align docstring or add directionality |
| M5 | Gate 3 output only checks the chosen planet, not all 7 | gates module | Extend to full-panel check |
| L1–L5 | Hygiene / dead code (incl. stray repo-root `nul` artifact) | various | Clean up |
