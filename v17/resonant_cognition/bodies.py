"""
Resonant Cognition v17 — Body Type Definitions (Phase 0A)
==========================================================
All body types as Python dataclasses. These are the typed objects that
persist to JSON and drive the orbital integrator, resonance detection,
and cognitive chamber.

Creation phrase: "Let there be light."
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json
import os


# ─── CORE (THE SUN) ──────────────────────────────────────────────────────────

@dataclass
class CoreState:
    """The central gravitational anchor. Contains laws reference + geometry only.
    Identity/persona does NOT live here — that's Ring + Gas Giant 2."""
    position: list[float]           # [x, y, z] in cognitive space
    G_value: float                  # Gravitational constant for this system
    M_base: float                   # Base mass (dominates all planets)
    dissonance_alpha: float         # α in M = M_base + α(ΔD)^β
    dissonance_beta: float          # β exponent
    well_depth: float               # Capture radius for Phase C trajectory check
    session_counter: int            # Total sessions run
    laws_file_path: str             # Path to core_laws.json (read-only at runtime)

    def effective_mass(self, dissonance: float) -> float:
        """M_core = M_base + α(ΔD)^β. High tension → stronger pull."""
        return self.M_base + self.dissonance_alpha * (dissonance ** self.dissonance_beta)


# ─── PLANETS (THE 7 ARCHETYPES) ──────────────────────────────────────────────

@dataclass
class CognitiveModeConfig:
    """Per-planet LLM call parameters. One model plays all roles; these
    differentiate how each 'seat' behaves."""
    temperature: float = 0.7
    context_window_exchanges: int = 3   # How many prior exchanges to include
    cot_depth: int = 1                  # Chain-of-thought steps (0 = none)
    prompt_structure: str = "standard"  # "standard" | "creative" | "rigid"


@dataclass
class Planet:
    """One of the 7 archetype planets. Freudian triad lives INSIDE here.
    Moons are separate bodies bound to this planet."""
    id: str                          # e.g., "sage", "magician"
    archetype_name: str              # e.g., "Sage"
    position: list[float]            # [x, y, z] current orbital position
    velocity: list[float]            # [vx, vy, vz]
    mass: float                      # = energy (2.0–4.5)
    sigma: float                     # Semantic volume (Gaussian spread)
    cognitive_mode: CognitiveModeConfig = field(default_factory=CognitiveModeConfig)
    # Freudian triad — all in-planet:
    id_flavor: str = ""              # Raw impulse descriptor for this archetype
    ego_descriptor: str = ""         # How this planet synthesizes/acts
    superego_principle: str = ""     # Internalized moral principle checked in Phase C
    orbital_plane_tilt_deg: float = 0.0  # Random tilt from reference plane (set at init)


# ─── MOONS (DUAL HEMISPHERES + STABILIZERS) ──────────────────────────────────

@dataclass
class Moon:
    """Bound to one parent planet ONLY. Two roles:
    1. Stabilizer: damps parent's orbital wobble (Jupiter-style). Parent-only influence.
    2. Buffer: dual-hemisphere short-term memory (LEFT=rational, RIGHT=intuitive).
    Does NOT participate in inter-planet resonance."""
    id: str                          # e.g., "sage_left"
    parent_planet_id: str            # Which planet this moon orbits
    hemisphere: str                  # "left" | "right"
    offset_vector: list[float]       # [dx, dy, dz] relative to parent
    stabilizer_strength: float = 0.5  # How much damping force applied to parent orbit
    buffer_content: list[dict] = field(default_factory=list)  # Short-term memory entries


# ─── GAS GIANTS (LIBRARIES) ──────────────────────────────────────────────────

@dataclass
class GasGiant:
    """Far-out, high-mass library bodies. NOT stabilizers — knowledge stores."""
    id: str                          # "g1" | "g2"
    name: str                        # "Knowledge Giant" | "Self-Model Giant"
    position: list[float]
    velocity: list[float]
    mass: float = 80.0               # Far more massive than planets, very slow orbit
    contents: list[dict] = field(default_factory=list)        # Permanent entries
    ring_buffer: list[dict] = field(default_factory=list)     # Uncommitted candidates
    decay_profile: str = "none"      # G1="none", G2="4_week_half_life"
    moons: list[Moon] = field(default_factory=list)           # G1 only: A/B/C pre-filter


# ─── RING (USER-FACING PERSONA / FRONTEND) ──────────────────────────────────

@dataclass
class RingPersona:
    """The ONLY thing the user talks to. Swappable frontend — not inherently 'Maya'.
    model_id defaults to auto-detect (= chamber model) unless a dedicated small model is loaded."""
    name: str = "Maya"              # Deployment choice, not architectural identity
    personality_vector: list[float] = field(default_factory=lambda: [0.0, 0.3, 0.1])
    memory_swarm: list[dict] = field(default_factory=list)     # Spatial long-term memories
    relationship_log: dict = field(default_factory=dict)       # session_count, topics, valence
    idle_state: str = "active"      # "active" | "ambient_reflection" | "dormant"
    model_id: str = "auto"          # LM Studio model for Ring voice. "auto" = same as chamber


# ─── COMET (THE JESTER) ──────────────────────────────────────────────────────

@dataclass
class Comet:
    """Non-orbital, trigger-activated body. NOT an 8th planet.
    Challenges Law rigidity (royal privilege). Cannot override gates or Laws."""
    id: str = "jester"
    name: str = "The Jester"
    trigger_conditions: list[dict] = field(default_factory=list)  # Refined in Phase 8
    current_position: Optional[list[float]] = None  # Computed functionally when triggered
    last_appearance_session: int = -1
    intervention_history: list[dict] = field(default_factory=list)  # Logged to G2


# ─── MEMORY ENTRIES (SPATIAL) ────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    """A single memory with mass, position in the cognitive field, and decay."""
    entry_id: str                    # Unique identifier
    vector_position: list[float]     # [x, y, z] in cognitive space
    mass: float                      # M_μ (alignment equation, Paper III)
    semantic_content: str            # The actual text/vector content
    creation_ts: float               # Unix timestamp
    last_accessed: float             # Unix timestamp
    decay_rate: float                # Usage-frequency dependent (D-011)
    ring_membership: bool = False    # True if part of Ring's swarm (orbits Ring, not C_core)
    zone: str = "planet_vault"       # "planet_vault" | "ring_swarm" | "stochastic_periphery"


# ─── SESSION STATE ───────────────────────────────────────────────────────────

@dataclass
class SessionState:
    """Tracks the current session's live state."""
    input_history: list[dict] = field(default_factory=list)
    active_planet_set: list[str] = field(default_factory=list)
    resonance_field_snapshot: Optional[list[float]] = None
    dissonance_level: float = 0.0    # ΔD for current session
    sleep_pending: bool = False
    watchkeeper_ids: list[str] = field(default_factory=list)  # Populated during deep sleep
    is_halted: bool = False          # /halt active


# ─── GATE CONFIG (LOADED FROM JSON) ──────────────────────────────────────────

@dataclass
class GateConfig:
    """In-memory representation of gates_config.json. All 4 gates."""
    pii_enabled: bool = True
    pii_patterns: list[str] = field(default_factory=list)
    pii_replacement_token: str = "[REDACTED]"
    pii_store_raw: bool = False

    safety_enabled: bool = True
    safety_categories: list[dict] = field(default_factory=list)  # [{name, severity}]
    safety_pre_injection_check: bool = True
    safety_post_generation_check: bool = True
    safety_refusal_voice: str = "ring"

    transparency_enabled: bool = True
    transparency_mode: str = "metadata"  # "metadata" | "visible_footer" | "both"
    transparency_label_text: str = "[AI-Generated: Resonant Cognition v17]"

    audit_log_enabled: bool = True       # Structural invariant: cannot be disabled in practice
    audit_retention_days: int = 90
    audit_log_level: str = "full"
    halt_enabled: bool = True            # Structural invariant: /halt always works


# ─── PERSISTENCE HELPERS ─────────────────────────────────────────────────────

def save_json(obj, filepath: str) -> None:
    """Serialize a dataclass or dict to JSON file."""
    if hasattr(obj, '__dataclass_fields__'):
        from dataclasses import asdict
        obj = asdict(obj)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def load_json(filepath: str):
    """Load JSON file to dict."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)
