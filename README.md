# Solar Agent System (v17) — Resonant Cognition Engine

A 3D solar-system cognitive framework where 7 archetype "planets" orbit a Core Sun, each carrying its own Id/Ego/Superego triad. User prompts are embedded into the field, projected onto the planets' orbital positions, and resolved through a multi-voice debate (Phase A: Id fires → Phase B: Ego synthesis → Phase C: Superego regulatory review) before collapsing into a single response through the **Ring** — the only layer that talks to you.

Theory papers live in the companion repo [resonant-cognition](https://github.com/sg2john-cmd/resonant-cognition). This repository is the *implementation and its evidence*.

## Hardware & Benchmarks

Empirically verified running locally on consumer hardware:
- **GPU:** NVIDIA RTX 4090 (24 GB VRAM)
- **CPU / RAM:** Intel i9 13th gen, 64 GB system RAM
- **Model:** ~27B Q4 quantization via [LM Studio](https://lmstudio.ai/) at `127.0.0.1:1234`
- **Embeddings:** `text-embedding-allmini` (384-dim), same server

Full pipeline latency (moons ON, 7 planets × A/B/C): ~60–120 s per prompt on the above rig.
Smoke tests and offline gates run in < 5 s with no LLM calls.

## Memory & Edge Defense

The system uses a tiered memory architecture inspired by orbital mechanics:

- **Dyson Ring (the user-facing layer):** The only component that talks to you. Houses the persona's short-term swarm cache, PII vault (encrypted, ejectable), and EU AI Act guardrails. Everything enters and exits through here.
- **G1 Knowledge Archive:** Off-VRAM permanent long-term memory. A 3-pass moon-filtered sleep cycle promotes stable knowledge into the archive and rejects low-signal noise. Never loaded into GPU memory during inference.
- **G2 Self-Model (Gas Giant 2):** The system's dreaming sandbox — a parallel self-model that runs background consolidation, drift detection, and axiom distillation without consuming live-session VRAM.
- **Dyson Swarm (orbital decay cache):** A half-life-decay ring of recent context fragments. Entries lose mass over time; anything below threshold is compressed or ejected to G1. Acts as the system's working short-term memory between Ring sessions.

## Repository Layout

```
01 - Theory/                 # Design theory (see companion repo for formal papers)
02 - Architecture/           # Data flow, body inventory, archetype definitions
03 - Implementation/         # Build Plan.md — the authoritative phase tracker
04 - Decisions & Rationale/  # D-xxx decision log (every constraint documented)
05 - Issues & Postmortems/   # v16 postmortem + issue tracking
v17/resonant_cognition/      # THE CODE
├── pipeline.py              # Entry point: gate → ring → routing → chamber → response
├── cognitive_chamber.py     # 7-voice A/B/C debate (Id/Ego/Superego per planet)
├── collapse.py              # Waveform superposition + consensus collapse engine
├── routing.py / resonance.py / integrator.py   # Field physics, orbital mechanics
├── ring.py                  # The Ring — sole user-facing layer (swarm memory, persona)
├── giants/                  # G1 knowledge archive + G2 self-model (with their moons)
├── comet/                   # Jester/comet trigger engine
├── planets/ core/ moons/    # State files (all JSON, human-readable)
└── tests/                   # Self-contained test suites + evidence/ transcripts
```

## Quick Start — How to Run It

### 1. Prerequisites
- **Python 3.10+**
- **LM Studio** (or any OpenAI-compatible local server) running at `127.0.0.1:1234` with **two models loaded**:
  - A chat model (~27B Q4 recommended; any decent instruct model works for smoke tests)
  - An embedding model — `text-embedding-allmini` (384-dim), or set a different one in `constants.py` (`EMBEDDING_MODEL_ID`)

### 2. Point the code at your server (if not defaults)
Everything is configured in `v17/resonant_cognition/constants.py`. Defaults: host `127.0.0.1`, port `1234`. No API key needed for LM Studio; if you use another backend, set the header there.

### 3. Run it
```bash
cd v17/resonant_cognition
python -X utf8 pipeline.py --smoke     # offline: gates + ring + routing only (no LLM)
python -X utf8 pipeline.py             # live: full prompt → response through the Ring
```

### 4. Run the test suite (proof it works)
Tests are self-contained; each prints PASS/FAIL and exits non-zero on failure. Full index in [`tests/README.md`](v17/resonant_cognition/tests/README.md).

```bash
cd v17/resonant_cognition
python -X utf8 tests/test_routing.py                       # offline (embedding only)
python -X utf8 tests/run_e2e_light.py                      # light end-to-end, 3 prompts
python -X utf8 tests/run_production_config_verify.py       # production-config verify (~15-20 min)
```

**Evidence:** every successful test run is archived with a timestamped transcript in [`tests/evidence/`](v17/resonant_cognition/tests/evidence/) — that folder is the concrete proof-of-concept record.

## Status

Phases 0A–8 are **complete and verified** (see [Build Plan.md](03%20-%20Implementation/Build%20Plan.md)). Independent blind review passed; post-review re-verification green. Next up: **Phase 9 — Scaling & Multi-System**.

## Licensing

- **Code:** All rights reserved by the author. Free to use, study, and modify for research and non-commercial purposes. Commercial use requires a license from the author — see [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).
- **Theory & documentation:** CC BY-NC-SA 4.0 (credit required; no commercial redistribution without permission).

## Contact / License Requests

[sg2john-cmd](https://github.com/sg2john-cmd) — for commercial licensing or collaboration inquiries.
