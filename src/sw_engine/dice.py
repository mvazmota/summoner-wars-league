"""Combat dice.

The game ships custom dice with three faces (rulebook p.4): melee hit, ranged hit and
special. This module models the face distribution only, never a physical die: rolling
is driven by a caller-supplied `random.Random` so the engine stays deterministic.

Special results are ignored at M1 (rulebook p.8: "Ignore special results unless
otherwise specified"); card-specific special handling arrives with the effect DSL in M3.
"""

from __future__ import annotations

import random
from enum import Enum, auto
from typing import Final

from sw_engine.state import AttackKind


class Die(Enum):
    MELEE_HIT = auto()
    RANGED_HIT = auto()
    SPECIAL = auto()


# Three melee faces, two ranged faces, one special face.
DICE_FACES: Final[tuple[Die, ...]] = (
    Die.MELEE_HIT,
    Die.MELEE_HIT,
    Die.MELEE_HIT,
    Die.RANGED_HIT,
    Die.RANGED_HIT,
    Die.SPECIAL,
)


def roll(count: int, rng: random.Random) -> tuple[Die, ...]:
    """Roll `count` dice. Negative counts are a programming error, not a rule case."""
    if count < 0:
        raise ValueError(f"cannot roll a negative number of dice: {count}")
    return tuple(rng.choice(DICE_FACES) for _ in range(count))


def hits(rolls: tuple[Die, ...], attack: AttackKind) -> int:
    """Count successes for the given attack kind.

    A melee unit scores melee faces only; a ranged unit scores ranged faces only.
    Specials never count at M1.
    """
    if attack is AttackKind.MELEE:
        return sum(1 for die in rolls if die is Die.MELEE_HIT)
    if attack is AttackKind.RANGED:
        return sum(1 for die in rolls if die is Die.RANGED_HIT)
    return 0
