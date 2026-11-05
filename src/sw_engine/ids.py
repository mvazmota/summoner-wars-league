"""Opaque identifier types.

NewType keeps the compiler honest: a CardId can never be passed where a DeckId is
expected, and a plain int is not a UnitId. All of them are zero-cost at runtime.
"""

from __future__ import annotations

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
