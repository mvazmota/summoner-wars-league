"""Immutable game state.

Everything here is a frozen dataclass. `step()` returns a new state and never mutates the
input; that invariant is what makes the engine reproducible and safe to fork for search
and determinisation.

Constants, enums and geometry live in `sw_core` and are re-exported here so existing
imports keep working.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sw_core import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    HAND_SIZE,
    MAGIC_MAX,
    MAX_UNITS_PER_PHASE,
    AttackKind,
    CardId,
    Phase,
    PlayerId,
    Square,
    UnitId,
    UnitKind,
)

__all__ = [
    "BOARD_HEIGHT",
    "BOARD_WIDTH",
    "HAND_SIZE",
    "MAGIC_MAX",
    "MAX_UNITS_PER_PHASE",
    "AttackKind",
    "GameState",
    "Phase",
    "PlayerState",
    "Square",
    "UnitKind",
    "UnitState",
]


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
    active_events: tuple[CardId, ...] = ()

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
    extra_attackers: tuple[UnitId, ...] = ()

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
            (p.player, p.summoner_id, p.magic, p.deck, p.hand, p.discard, p.active_events)
            for p in self.players
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
            tuple(sorted(self.extra_attackers)),
        )

    def state_hash(self) -> str:
        payload = repr(self.state_key()).encode("utf-8")
        return hashlib.blake2b(payload, digest_size=8).hexdigest()
