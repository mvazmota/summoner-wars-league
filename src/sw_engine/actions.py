"""Action types.

One action per rulebook operation. `EndPhase` advances the turn sequence; everything
else is only legal in the phase named after it (rulebook p.6).
"""

from __future__ import annotations

from dataclasses import dataclass

from sw_engine.ids import CardId, UnitId
from sw_engine.state import Square


@dataclass(frozen=True, slots=True)
class EndPhase:
    """Finish the current phase and move to the next one (p.6)."""


@dataclass(frozen=True, slots=True)
class SummonUnit:
    """Summon `card` from hand onto `position` during the Summon Phase (p.6)."""

    card: CardId
    position: Square


@dataclass(frozen=True, slots=True)
class BuildStructure:
    """Build `card` (a gate or structure) during the Build Phase (p.6)."""

    card: CardId
    position: Square


@dataclass(frozen=True, slots=True)
class MoveUnit:
    """Move `unit_id` to `to` during the Move Phase (p.7)."""

    unit_id: UnitId
    to: Square


@dataclass(frozen=True, slots=True)
class AttackUnit:
    """Attack `target` with `attacker` during the Attack Phase (p.8)."""

    attacker: UnitId
    target: UnitId


@dataclass(frozen=True, slots=True)
class DiscardForMagic:
    """Discard `card` from hand for one magic during the Magic Phase (p.9)."""

    card: CardId


type Action = EndPhase | SummonUnit | BuildStructure | MoveUnit | AttackUnit | DiscardForMagic
