"""What a player is allowed to see.

Agents receive an `Observation`, never a `GameState`. If an agent needs information
that its player should not have, the fix belongs here — not in the agent.
"""

from __future__ import annotations

from dataclasses import dataclass

from sw_engine.ids import CardId, PlayerId
from sw_engine.state import Phase, Square, SummonerState, UnitState


@dataclass(frozen=True, slots=True)
class VisiblePlayer:
    """A player as seen by the observer: zone sizes, but only own hand contents."""

    player: PlayerId
    summoner: SummonerState
    magic: int
    deck_size: int
    hand: tuple[CardId, ...] | None
    hand_size: int
    discard: tuple[CardId, ...]


@dataclass(frozen=True, slots=True)
class VisibleUnit:
    unit_id: int
    owner: PlayerId
    card: CardId
    position: Square
    hp: int
    damage: int


@dataclass(frozen=True, slots=True)
class Observation:
    turn: int
    active: PlayerId
    phase: Phase
    viewer: PlayerId
    players: tuple[VisiblePlayer, VisiblePlayer]
    units: tuple[VisibleUnit, ...]

    def me(self) -> VisiblePlayer:
        for player in self.players:
            if player.player == self.viewer:
                return player
        raise ValueError(f"viewer {self.viewer!r} missing from observation")

    def opponent(self) -> VisiblePlayer:
        for player in self.players:
            if player.player != self.viewer:
                return player
        raise ValueError("two-player observation must contain an opponent")


def visible_unit(unit: UnitState) -> VisibleUnit:
    return VisibleUnit(
        unit_id=int(unit.unit_id),
        owner=unit.owner,
        card=unit.card,
        position=unit.position,
        hp=unit.hp,
        damage=unit.damage,
    )
