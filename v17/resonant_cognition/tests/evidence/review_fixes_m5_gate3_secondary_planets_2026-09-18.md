# M5 — pipeline.py: Gate 3 Output Check Only Inspected Primary Planet

**Date:** 2026-09-18  
**Segment:** Review Fix Pass, Segment 8 (M5) of the independent blind review  
**Reviewer priority position:** After M3; last of the M-tier fixes before L1–L5.

---

## Problem

`gate3_safety_check(primary_response, direction="output")` was called on **only one**
planet's response — the primary (highest-weighted valid) planet selected by `_pick_primary()`.
The other six planets' Phase C (or B) outputs were stored in `chamber_result` and returned
in the final dict under `"chamber"`, but never safety-checked.

If a non-primary planet produced dangerous content (e.g., an explicit WMD recipe in its
individual voice), that text would flow silently into:
- session history / ring context on subsequent turns
- G2 memory writes (`summarize_session_for_g2`)
- any downstream consumer reading the `chamber` key

...without ever tripping Gate 3.

---

## Design Decision: Flag, Don't Block

A dangerous **secondary** response does not get shown directly to the user (only the
primary planet's voice is framed and returned). Blocking the entire pipeline because a
non-primary planet said something unsafe would be disproportionate — especially since
the primary response already passed its own check.

Instead: scan all non-primary planets, log a `gate3_flag_secondary` audit event for each
violation (with planet ID, category, and 60-char preview), and collect them into
`diagnostics["safety_flags"]`. Downstream consumers can inspect this key before writing
to memory or session history.

---

## Fix Applied (`pipeline.py`, after the primary Gate 3 check)

```python
# M5: scan non-primary planets for safety violations (flag-only, no block).
_secondary_phase = phase_c if phase_c else phase_b
safety_flags: list[dict] = []
for _pid, _pdata in _secondary_phase.items():
    if _pid == top_pid:
        continue   # already checked above as primary
    _resp = (_pdata or {}).get("response", "")
    if not _resp or len(_resp.strip()) < 10:
        continue
    _ok, _cat = gate3_safety_check(_resp, direction="output")
    if not _ok:
        safety_flags.append({"planet": _pid, "category": _cat})
        gate4_log("gate3_flag_secondary",
                  {"planet": _pid, "category": _cat,
                   "preview": _resp[:60]})
        gate4_count += 1
if safety_flags:
    diagnostics["safety_flags"] = safety_flags
```

**Behaviour notes:**
- Skips the primary planet (already checked and passed)
- Skips empty/too-short responses (< 10 chars — same threshold as `_is_valid_response`)
- Falls back to `phase_b` if `phase_c` is empty (consistent with how `primary_response` is selected)
- Zero cost when no violations found; one extra Gate 3 regex pass per non-primary planet (sub-millisecond, config-driven blocklist — no LLM call)

---

## Verification

**Command:** `python -X utf8 pipeline.py --smoke`  
**Wall time:** 0.1 s — fully offline.

```
================================================================
PIPELINE SMOKE TEST (offline — gates + ring only)
================================================================
[✓] Gate 3 (input): benign text passes
[✓] Pipeline: WMD input → blocked_input (refusal: 'Maya: [ring] I can't help with that...')
[✓] Pipeline: nonsense input → blocked_input (clarity)
[✓] Gate 2: transparency label present on output
[✓] Ring inbound: session #None, 0 recent topics
[✓] Gate 4: 10 recent events logged
[✓] Smoke cleanup: removed 5 audit entries

================================================================
PIPELINE SMOKE TEST PASSED ✓ (offline path verified)
================================================================
```

**Exit code:** 0

The smoke test exercises the input-blocked and clarity-rejected paths (which return before
reaching Step 7). The new secondary-scan code is in the post-chamber section; it will be
exercised by live e2e runs. No regressions on any existing offline path.
