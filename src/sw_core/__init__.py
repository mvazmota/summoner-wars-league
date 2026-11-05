"""Shared value types.

Kept in its own package so data modules (`sw_cards`) can use ids, geometry and enums
without importing the engine — importing a submodule of `sw_engine` would execute
`sw_engine/__init__.py`, which imports the engine itself and closes a cycle.

Dependency rule: `sw_core` imports nothing from this project. Everything else may import
`sw_core`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Final, NewType

PlayerId = NewType("PlayerId", int)
CardId = NewType("CardId", str)
DeckId = NewType("DeckId", str)
UnitId = NewType("UnitId", int)

PLAYER_A: Final[PlayerId] = PlayerId(0)
PLAYER_B: Final[PlayerId] = PlayerId(1)
PLAYERS: Final[tuple[PlayerId, PlayerId]] = (PLAYER_A, PLAYER_B)


def opponent(player: PlayerId) -> PlayerId:
    """Return the other player. Only two players exist; anything else is a bug."""
    if player == PLAYER_A:
        return PLAYER_B
    if player == PLAYER_B:
        return PLAYER_A
    raise ValueError(f"unknown player id: {player!r}")


# Battlefield geometry — rulebook p.13/15: ROW = "6 adjacent spaces", COLUMN = "8".
BOARD_WIDTH: Final[int] = 6
BOARD_HEIGHT: Final[int] = 8

# Magic track maximum — rulebook p.15.
MAGIC_MAX: Final[int] = 15

# Hand size kept at end of turn — rulebook p.5 (setup draws 5) and p.9 (draw up to 5).
HAND_SIZE: Final[int] = 5

# Rulebook p.7: move up to 3 different units; p.8: attack with up to 3 different units.
MAX_UNITS_PER_PHASE: Final[int] = 3


class Phase(Enum):
    """Turn phases, in the order the rulebook mandates (p.6)."""

    SUMMON = auto()
    MOVE = auto()
    BUILD = auto()
    ATTACK = auto()
    MAGIC = auto()
    DRAW = auto()


class UnitKind(Enum):
    """Everything that can stand on the battlefield."""

    SUMMONER = auto()
    UNIT = auto()
    STRUCTURE = auto()
    GATE = auto()


class AttackKind(Enum):
    """How a unit attacks. NONE for structures, gates and other non-attackers."""

    NONE = auto()
    MELEE = auto()
    RANGED = auto()


@dataclass(frozen=True, slots=True, order=True)
class Square:
    """A board coordinate. Origin is the engine's own; do not assume player A's side."""

    x: int
    y: int

    def is_on_board(self) -> bool:
        return 0 <= self.x < BOARD_WIDTH and 0 <= self.y < BOARD_HEIGHT

    def is_adjacent_to(self, other: Square) -> bool:
        """Orthogonal adjacency only — rulebook p.6: diagonals are never adjacent."""
        return abs(self.x - other.x) + abs(self.y - other.y) == 1

    def distance_to(self, other: Square) -> int:
        """Orthogonal distance in spaces. Diagonals count as two."""
        return abs(self.x - other.x) + abs(self.y - other.y)
