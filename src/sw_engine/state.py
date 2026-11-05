"""Immutable game state.

Everything here is a frozen dataclass. `step()` returns a new state and never mutates
the input; that invariant is what makes the engine reproducible and safe to fork for
search and determinisation.

Every constant is sourced in `docs/RULES.md`, which cites the page of the official
rulebook v1.2 it came from. Do not change a constant without updating that file.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

from sw_engine.ids import CardId, PlayerId, UnitId

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
    """Turn phases, in the order the rulebook mandates (p.6).

    The five phases are completed in this exact order; the draw step happens after
    MAGIC and before the opponent's turn (p.9).
    """

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


@dataclass(frozen=True, slots=True)
class UnitState:
    unit_id: UnitId
    owner: PlayerId
    card: CardId
    kind: UnitKind
    attack: AttackKind
    position: Square
    strength: int
    life: int
    damage: int = 0

    def is_alive(self) -> bool:
        return self.damage < self.life

    def remaining_life(self) -> int:
        return max(0, self.life - self.damage)

    def can_move(self) -> bool:
        """Structures and gates cannot move unless a card says otherwise (p.7)."""
        return self.kind in (UnitKind.UNIT, UnitKind.SUMMONER)

    def can_attack(self) -> bool:
        return self.kind is UnitKind.UNIT and self.attack is not AttackKind.NONE


@dataclass(frozen=True, slots=True)
class PlayerState:
    """Per-player zones and bookkeeping.

    Zones are tuples, not lists: state must be hashable and comparable, and a shared
    mutable zone is the classic source of non-reproducible games.
    """

    player: PlayerId
    summoner_id: UnitId
    magic: int
    deck: tuple[CardId, ...]
    hand: tuple[CardId, ...]
    discard: tuple[CardId, ...] = ()

    def zone_sizes(self) -> tuple[int, int, int]:
        return (len(self.deck), len(self.hand), len(self.discard))


@dataclass(frozen=True, slots=True)
class GameState:
    turn: int
    active: PlayerId
    phase: Phase
    players: tuple[PlayerState, PlayerState]
    units: tuple[UnitState, ...] = ()
    seed: int = 0
    rng_counter: int = 0
    moved: tuple[UnitId, ...] = ()
    attacked: tuple[UnitId, ...] = ()
    attacked_any: bool = False

    def player(self, player: PlayerId) -> PlayerState:
        for state in self.players:
            if state.player == player:
                return state
        raise ValueError(f"player {player!r} is not in this state")

    def active_player(self) -> PlayerState:
        return self.player(self.active)

    def unit(self, unit_id: UnitId) -> UnitState:
        for unit in self.units:
            if unit.unit_id == unit_id:
                return unit
        raise ValueError(f"unit {unit_id!r} is not on the battlefield")

    def units_of(self, player: PlayerId) -> tuple[UnitState, ...]:
        return tuple(u for u in self.units if u.owner == player)

    def summoner(self, player: PlayerId) -> UnitState:
        return self.unit(self.player(player).summoner_id)

    def occupant(self, square: Square) -> UnitState | None:
        for unit in self.units:
            if unit.position == square:
                return unit
        return None

    def is_empty(self, square: Square) -> bool:
        return square.is_on_board() and self.occupant(square) is None

    def state_key(self) -> tuple[object, ...]:
        """Canonical, process-stable projection of the state.

        Never use `hash()` or `repr()` of containers whose iteration order can
        vary: both are salted per process and would break cross-run determinism.
        """
        players: tuple[object, ...] = tuple(
            (p.player, p.summoner_id, p.magic, p.deck, p.hand, p.discard) for p in self.players
        )
        units: tuple[object, ...] = tuple(
            (
                u.unit_id,
                u.owner,
                u.card,
                u.kind.name,
                u.attack.name,
                u.position,
                u.strength,
                u.life,
                u.damage,
            )
            for u in sorted(self.units, key=lambda u: (u.owner, u.unit_id))
        )
        return (
            self.turn,
            self.active,
            self.phase.name,
            players,
            units,
            self.seed,
            self.rng_counter,
            tuple(sorted(self.moved)),
            tuple(sorted(self.attacked)),
            self.attacked_any,
        )

    def state_hash(self) -> str:
        payload = repr(self.state_key()).encode("utf-8")
        return hashlib.blake2b(payload, digest_size=8).hexdigest()
