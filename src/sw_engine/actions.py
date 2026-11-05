"""Action types.

M0 ships a single action, `EndTurn`, because it is the only transition whose rules
are fully specified at this milestone. Every other action lands in M1 together with
its legality check — adding an action type before its rules is how engines drift
away from the real game.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EndTurn:
    """Pass priority: the active player's turn ends and the opponent becomes active."""


type Action = EndTurn
