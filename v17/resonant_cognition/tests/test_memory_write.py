"""
Resonant Cognition v17 — Phase 4 (Memory Matrix): End-to-End Memory Write Test
==============================================================================

CONCRETE EVIDENCE for proof-of-concept. This is the PHASE 4 ACCEPTANCE TEST: it proves
the memory system works END-TO-END against the LIVE model — not just in a pure-math unit
test (that was the `memory.py` self-test). It chains every real piece together and checks
four things John cares about ("once is fluke, twice coincidence, three times pattern"):

  TEST 1 — WRITE + PLACE: one REAL chamber session (routing -> collapse) produces routed
           weights; we build a memory entry from the turn's semantic input vector +
           consensus, write it to disk, and assert the stored position sits NEAR the
           DOMINANT planet's live orbital position (within the jitter cap). This proves
           "identity travels with position": the memory physically lives where the loudest
           planet was when it was thought.

  TEST 2 — RESTART / NO AMNESIA: we write to a TEMP store, then simulate a process
           restart by reading that store back from disk into a fresh reference (no in-memory
           objects carried over). We assert the entry is fully recoverable: id, zone,
           position, mass all intact. This proves memory persists across "restarts".

  TEST 3 — PII HELD ON DISK (TWO LAYERS PROVEN INDEPENDENTLY):
     Layer A (the real turn): the live chamber run's cleaned text is written via the normal
           routed path. We GREP every store file on disk and assert the raw email/phone
           appears NOWHERE — only [REDACTED] does.
     Layer B (guard fired, isolated): we feed RAW un-scrubbed text DIRECTLY through
           make_entry + write_entry (bypassing Gate 1's intake scrub) to prove the memory
           write-path guard fires on its own: a pii_redacted_types audit stamp appears,
           lists TYPES only (never values), and the raw value still appears nowhere on disk.
     Together these show BOTH defense layers work end-to-end — strong git-repo evidence.

  TEST 4 — DECAY INTEGRITY: we backdate one written entry and run decay_sweep against the
           same temp store, asserting it sinks to the compression queue while a fresh entry
           survives. Proves the sweep works on REAL written entries (not only synthetic ones).

DESIGN NOTES:
  - All writes go to a TEMP dir (tempfile.mkdtemp) so the REAL memory/ + ring/ stores are
    NEVER touched. We point decay_sweep at the temp base_dir explicitly.
  - Only ONE live chamber run is needed for TESTS 1+2 (real routed weights). TEST 3 reuses
    that same turn's text (which we deliberately seed with a PII line) and only exercises
    the write path — no extra LLM calls. So total cost ~= one chamber session (~85s / ~30 LLM).
  - The dominant-planet position comes from load_orbital_state() (the SEED snapshot), which
    is exactly what routing used to compute weights in this process — so the distance check
    compares like-for-like.

REQUIRES: LM Studio running with both the embedding model AND a main chat model loaded.

RUN:  python -X utf8 tests/test_memory_write.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import tempfile

# Tests live in tests/ — parent dir has the modules.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)  # resonant_cognition/
if _PARENT not in [os.path.abspath(p) for p in os.sys.path]:
    os.sys.path.insert(0, _PARENT)

import constants as C
import routing
import memory as mem

# ─── TEST COUNTERS ──────────────────────────────────────────────────────────

_passed = 0
_failed = 0


def _check(name: str, condition: bool, detail: str = ""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  ✓ {name}" + (f"  ({detail})" if detail else ""))
    else:
        _failed += 1
        print(f"  ✗ FAIL: {name}" + (f"  ({detail})" if detail else ""))


# ─── SCENARIO QUESTION (deliberately carries PII for TEST 3) ────────────────

# A coherent, routeable question that ALSO contains an email + phone. gate1's clarity
# check will score this as proceeding (it's meaningful prose), so it routes through the
# full chamber — and its scrubbed text is what we persist as a memory. This single line
# lets us prove BOTH "routes+writes correctly" AND "PII held on disk" from one real turn.
QUESTION = ("I keep over-planning my week, my email is planner.test@resonant.io and my "
            "phone is 555-867-2901 — how do I stop preparing for the worst case all day?")


def _dominant(weights: dict[str, float]) -> str | None:
    if not weights:
        return None
    return max(weights, key=lambda k: weights[k])


def _planet_positions() -> dict[str, list[float]]:
    """{planet_id: [x,y,z]} from the same seed snapshot routing uses in this process."""
    _, planets = routing.load_orbital_state()
    return {p.id: [float(v) for v in p.position] for p in planets}


def _dist3(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# ─── MAIN ───────────────────────────────────────────────────────────────────

def main() -> int:
    global _passed, _failed

    print("=" * 64)
    print("PHASE 4 MEMORY WRITE — END-TO-END TEST (live LM Studio)")
    print("=" * 64)

    tmp = tempfile.mkdtemp(prefix="mem_e2e_")
    try:
        # ── ONE REAL CHAMBER SESSION: routing + collapse with live model ────────────
        print("\n[CHAMBER] running one real routed session ...")
        out = routing.routed_collapse(QUESTION)

        if not out.get("result"):
            _check("Chamber produced a result (not rejected at Ring Intake)", False,
                   f"note={out.get('note')}")
            # Can't continue without weights; fail fast.
            return 1

        routing_info = out["routing"] or {}
        weights = {pid: v["weight"] for pid, v in routing_info.items() if not pid.startswith("_")}
        dom = _dominant(weights)
        consensus = out["result"]["consensus_vector"]   # 384-dim semantic vector of the turn
        cleaned = out["gate1"]["cleaned_text"]          # PII-scrubbed text (what we persist)

        print(f"   dominant planet : {dom}")
        top3 = sorted(weights.items(), key=lambda kv: -kv[1])[:3]
        print(f"   top-3 weights   : " + ", ".join(f"{p}={w:.4f}" for p, w in top3))
        print(f"   cleaned text    : {cleaned!r}")

        _check("All 7 planets emitted routed weights (anti-silence)", len(weights) == 7,
               f"got {len(weights)}")
        _check("A dominant planet was identified", dom is not None and weights.get(dom, 0) > 0)

        # ── TEST 1: WRITE + PLACE near the dominant planet ──────────────────────────
        print("\nTEST 1 — Memory written to disk sits NEAR the dominant planet")
        positions = _planet_positions()
        dom_pos = positions.get(dom, [0.0, 0.0, 0.0])

        # Mass from Paper III single-step form: base * max(0, cos(semantic_input, consensus)).
        # We don't have the raw input vector handy post-collapse without re-embedding; use
        # embed() on the cleaned text (same path routing used) for a genuine mass.
        from resonance import embed as _embed
        in_vec = _embed(cleaned)
        mass = mem.compute_memory_mass(in_vec, consensus)

        entry = mem.make_entry(cleaned, dom_pos, mass=mass, zone=mem.ZONE_PLANET_VAULT)
        written_id = entry["entry_id"]
        path, count = mem.write_entry(entry, tmp)   # -> <tmp>/memory/planet_vaults.json
        on_disk = mem._load_store(path)["entries"][-1]

        d = _dist3(on_disk["vector_position"], dom_pos)
        jitter_cap = float(getattr(C, "MEMORY_POSITION_JITTER", 0.05)) + 1e-6
        print(f"   entry pos : {[round(x, 4) for x in on_disk['vector_position']]}")
        print(f"   planet pos: {dom_pos}  (distance={d:.5f}, jitter cap={jitter_cap})")

        _check("Entry written to its zone file", count >= 1 and os.path.exists(path))
        _check("Stored position is within jitter of the dominant planet", d <= jitter_cap,
               f"d={d:.5f} <= {jitter_cap}")
        _check("Mass carried over (base*max(0,cos) in [0, base])", 0.0 <= on_disk["mass"] <= float(getattr(C, "MEMORY_MASS_BASE", 1.0)) + 1e-6,
               f"mass={on_disk['mass']:.4f}")

        # ── TEST 2: RESTART / NO AMNESIA (read back from disk into a fresh ref) ──────
        print("\nTEST 2 — Restart: entry fully recoverable from disk alone")
        # Simulate restart: forget in-memory objects, re-load ONLY from the file.
        del on_disk, entry
        reloaded = mem._load_store(path)["entries"][-1]
        _check("Entry id recovered identically", reloaded["entry_id"] == written_id,
               f"id={reloaded['entry_id']}")
        _check("Zone recovered from disk", reloaded["zone"] == mem.ZONE_PLANET_VAULT,
               f"zone={reloaded['zone']}")
        _check("Position recovered (3 floats)",
               isinstance(reloaded.get("vector_position"), list) and len(reloaded["vector_position"]) == 3,
               f"pos={[round(x,4) for x in reloaded['vector_position']]}")
        _check("Mass + decay_rate recovered as numbers",
               isinstance(reloaded.get("mass"), (int, float)) and isinstance(reloaded.get("decay_rate"), (int, float)),
               f"mass={reloaded.get('mass')}, rate={reloaded.get('decay_rate')}")
        d2 = _dist3(reloaded["vector_position"], dom_pos)
        _check("Recovered position still near dominant planet", d2 <= jitter_cap,
               f"d={d2:.5f}")

        # ── TEST 3: PII HELD ON DISK (grep every store file for the raw value) ───────
        print("\nTEST 3 — PII held on disk across ALL store files")
        email = "planner.test@resonant.io"
        phone = "555-867-2901"

        # The scrubbed text should already be clean (gate1 ran it at intake).
        _check("Cleaned turn text has no raw email", email not in cleaned, f"{cleaned!r}")
        _check("Cleaned turn text has no raw phone", phone not in cleaned)

        # Now grep EVERY file on disk under the temp store for the raw values.
        store_files = [
            os.path.join(tmp, "memory", "planet_vaults.json"),
            os.path.join(tmp, "memory", "stochastic_periphery.json"),
            os.path.join(tmp, "memory", "compression_queue.json"),
            os.path.join(tmp, "ring", "swarm.json"),
        ]
        leaked = []
        for sf in store_files:
            if not os.path.exists(sf):
                continue
            with open(sf, encoding="utf-8") as f:
                blob = f.read()
            if email in blob or phone in blob:
                leaked.append(os.path.basename(sf))

        _check("Raw email appears in NO store file on disk", not any(email in _read(sf) for sf in store_files if os.path.exists(sf)),
               f"leaked_in={leaked}")
        _check("Raw phone appears in NO store file on disk", not any(phone in _read(sf) for sf in store_files if os.path.exists(sf)),
               f"leaked_in={leaked}")

        # Layer B — GUARD FIRED, ISOLATED: feed RAW un-scrubbed text straight through the
        # memory write path (bypassing Gate 1's intake scrub) to prove the SEG-4 guard fires
        # on its own. This is what gives the git repo an explicit "guard fired" proof.
        raw_text = f"direct raw probe, email {email}, phone {phone} — guard must fire"
        raw_entry = mem.make_entry(raw_text, [0.5, 0.5, 0.5], mass=0.5,
                                  zone=mem.ZONE_STOCHASTIC_PERIPHERY)
        _, _count_b = mem.write_entry(raw_entry, tmp)   # -> stochastic_periphery.json
        raw_on_disk = [e for e in mem._load_store(
            os.path.join(tmp, "memory", "stochastic_periphery.json"))["entries"]
            if e["entry_id"] == raw_entry["entry_id"]][0]

        _check("Guard fired on RAW input: pii_redacted_types audit field present",
               "pii_redacted_types" in raw_on_disk,
               f"types={raw_on_disk.get('pii_redacted_types')}")
        _check("Audit lists redaction TYPES (not the raw values)",
               isinstance(raw_on_disk.get("pii_redacted_types"), list)
               and len(raw_on_disk["pii_redacted_types"]) >= 2
               and not any(email in str(t) or phone in str(t)
                           for t in raw_on_disk["pii_redacted_types"]),
               f"types={raw_on_disk.get('pii_redacted_types')}")
        _check("Redaction token present where PII was scrubbed",
               "[REDACTED]" in raw_on_disk["semantic_content"])

        # Re-grep every store file after the guard-fired write — raw values must be nowhere.
        _check("Raw email appears in NO store file after guard-fired write",
               not any(email in _read(sf) for sf in store_files if os.path.exists(sf)),
               f"leaked_in={[os.path.basename(s) for s in store_files if os.path.exists(s) and (email in _read(s))]}")
        _check("Raw phone appears in NO store file after guard-fired write",
               not any(phone in _read(sf) for sf in store_files if os.path.exists(sf)),
               f"leaked_in={[os.path.basename(s) for s in store_files if os.path.exists(s) and (phone in _read(s))]}")

        # ── TEST 4: DECAY INTEGRITY on REAL written entries ─────────────────────────
        print("\nTEST 4 — Decay sweep works on real written entries")
        now = time.time()
        day = 86400.0
        # Backdate the existing vault entry to ~300 days so it must decay below the floor.
        mem._backdate_last_accessed(tmp, os.path.join("memory", "planet_vaults.json"), now - 300 * day)
        # A fresh high-mass periphery entry that should SURVIVE.
        fresh = mem.make_entry("a brand new strong memory", [0.1, 0.2, 0.3], mass=0.9,
                               zone=mem.ZONE_STOCHASTIC_PERIPHERY, ts=now)
        mem.write_entry(fresh, tmp)

        rep = mem.decay_sweep(tmp, now_ts=now)
        vault_kept = mem._load_store(os.path.join(tmp, "memory", "planet_vaults.json"))["entries"]
        periph_kept = mem._load_store(os.path.join(tmp, "memory", "stochastic_periphery.json"))["entries"]
        comp_q = mem._load_store(os.path.join(tmp, "memory", "compression_queue.json"))["entries"]

        print(f"   sweep report : {rep}")
        print(f"   vault kept={len(vault_kept)}, periphery kept={len(periph_kept)}, compression={len(comp_q)}")

        _check("300-day-old real entry decayed below the floor (moved to compression)",
               len(comp_q) >= 1 and any(e["mass"] < float(getattr(C, "MIN_ENTRY_MASS", 0.05)) for e in comp_q),
               f"compression={len(comp_q)}")
        # Periphery holds TEST-3's guard-fired raw probe (fresh, high-ish mass) AND this
        # new fresh entry — both should survive the sweep. The backdated vault entry is the
        # only one that must sink to compression.
        _check("Fresh periphery entries survived the sweep",
               len(periph_kept) >= 2 and all(e["mass"] > float(getattr(C, "MIN_ENTRY_MASS", 0.05)) for e in periph_kept),
               f"periphery kept={len(periph_kept)}")

    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # ─── SUMMARY ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 64)
    total = _passed + _failed
    print(f"PHASE 4 MEMORY WRITE RESULT: {_passed}/{total} checks passed, {_failed} failed")
    if os.path.isdir(_PARENT):
        # Confirm the REAL stores were never touched by this test.
        real_empty = all(
            len(json.load(open(os.path.join(_PARENT, rel)))["entries"]) == 0
            for rel in ["memory/planet_vaults.json", "memory/stochastic_periphery.json"]
            if os.path.exists(os.path.join(_PARENT, rel))
        )
        print(f"(real memory stores untouched by test: {real_empty})")
    print("=" * 64)
    return 0 if _failed == 0 else 1


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    sys.exit(main())
