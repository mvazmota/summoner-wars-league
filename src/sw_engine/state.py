"""Immutable game state.

Everything here is a frozen dataclass. `step()` returns a new state and never
mutates the input; that invariant is what makes the engine reproducible and safe
to fork for search and determinisation.

Rules coverage at milestone M0 is intentionally minimal: geometry, identity and
bookkeeping only. Unit abilities, magic generation and combat arrive in M1.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

from sw_engine.ids import CardId, PlayerId, UnitId

# Board dimensions. TODO(rules): confirm against the official board before M1 —
# tracked in docs/UNRESOLVED.md.
BOARD_WIDTH: Final[int] = 6
BOARD_HEIGHT: Final[int] = 8


class Phase(Enum):
    """Turn phases.

    Summoner Wars plays a turn as an ordered sequence of steps; the engine keeps the
    current one in the state so that legality checks and search do not have to carry
    a parallel cursor.
    """

    START = auto()
    BUILD_MAGIC = auto()
    SUMMON = auto()
    MOVE = auto()
    ATTACK = auto()
    END = auto()


@dataclass(frozen=True, slots=True, order=True)
class Square:
    """A board coordinate. Origin is the engine's own; do not assume player A's side."""

    x: int
    y: int

    def is_on_board(self) -> bool:
        return 0 <= self.x < BOARD_WIDTH and 0 <= self.y < BOARD_HEIGHT


@dataclass(frozen=True, slots=True)
class UnitState:
    unit_id: UnitId
    owner: PlayerId
    card: CardId
    position: Square
    hp: int
    damage: int = 0

    def is_alive(self) -> bool:
        return self.damage < self.hp


@dataclass(frozen=True, slots=True)
class SummonerState:
    owner: PlayerId
    card: CardId
    position: Square
    hp: int
    damage: int = 0

    def is_alive(self) -> bool:
        return self.damage < self.hp


@dataclass(frozen=True, slots=True)
class PlayerState:
    """Per-player zones.

    Zones are tuples, not lists: state must be hashable and comparable, and a shared
    mutable zone is the classic source of non-reproducible games.
    """

    player: PlayerId
    summoner: SummonerState
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

    def player(self, player: PlayerId) -> PlayerState:
        for state in self.players:
            if state.player == player:
                return state
        raise ValueError(f"player {player!r} is not in this state")

    def active_player(self) -> PlayerState:
        return self.player(self.active)

    def state_key(self) -> tuple[object, ...]:
        """Canonical, process-stable projection of the state.

        Never use `hash()` or `repr()` of containers whose iteration order can
        vary: both are salted per process and would break cross-run determinism.
        """
        players: tuple[object, ...] = tuple(
            (
                p.player,
                p.summoner.owner,
                p.summoner.card,
                p.summoner.position,
                p.summoner.hp,
                p.summoner.damage,
                p.magic,
                p.deck,
                p.hand,
                p.discard,
            )
            for p in self.players
        )
        units: tuple[object, ...] = tuple(
            (u.unit_id, u.owner, u.card, u.position, u.hp, u.damage)
            for u in sorted(self.units, key=lambda u: (u.owner, u.unit_id))
        )
        return (self.turn, self.active, self.phase.name, players, units, self.seed)

    def state_hash(self) -> str:
        payload = repr(self.state_key()).encode("utf-8")
        return hashlib.blake2b(payload, digest_size=8).hexdigest()
