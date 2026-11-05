"""The league's placeholder policy.

Deliberately simple and deliberately deterministic given a seed: the point is to exercise
every rule the engine implements, not to play well. A real league swaps this out per bot.
"""

from __future__ import annotations

import random
from typing import Final

from sw_cards import get_card
from sw_core import CardId, PlayerId
from sw_engine.actions import (
    Action,
    AttackUnit,
    BuildStructure,
    DiscardForMagic,
    EndPhase,
    MoveUnit,
    PlayEvent,
    SlySwap,
    SummonUnit,
)
from sw_engine.engine import legal_actions
from sw_engine.state import GameState

PRIORITY: Final[tuple[type, ...]] = (
    AttackUnit,
    SummonUnit,
    MoveUnit,
    BuildStructure,
    SlySwap,
    DiscardForMagic,
)


def rank(action: Action) -> int:
    for index, kind in enumerate(PRIORITY):
        if isinstance(action, kind):
            return index
    return len(PRIORITY)


def choose_action(state: GameState, rng: random.Random, event_chance: float = 0.6) -> Action:
    """Play an event when one is legal and the dice allow it, otherwise the best class.

    Without the event branch a greedy policy never plays events: an attack is almost always
    available, so the event would never be the top-ranked action.
    """
    actions = legal_actions(state)
    if not actions:
        return EndPhase()

    events = [action for action in actions if isinstance(action, PlayEvent)]
    if events and rng.random() < event_chance:
        return rng.choice(events)

    best = min(rank(action) for action in actions)
    candidates = [action for action in actions if rank(action) == best]
    return rng.choice(candidates)


def describe(action: Action) -> str:
    match action:
        case SummonUnit(card, position):
            return f"Summon {get_card(card).name} at ({position.x},{position.y})"
        case BuildStructure(card, position):
            return f"Build {get_card(card).name} at ({position.x},{position.y})"
        case MoveUnit(unit_id, to):
            return f"Move unit {unit_id} to ({to.x},{to.y})"
        case AttackUnit(attacker, target):
            return f"Unit {attacker} attacks unit {target}"
        case DiscardForMagic(card):
            return f"Discard {get_card(card).name} for magic"
        case PlayEvent(card, targets):
            suffix = f" targeting {', '.join(str(t) for t in targets)}" if targets else ""
            return f"Play {get_card(card).name}{suffix}"
        case SlySwap(target):
            return f"Sly: swap with unit {target}"
        case EndPhase():
            return "End phase"


def describe_action(action: Action) -> dict[str, object]:
    """Structured form of `describe`, so the analysis does not parse strings."""
    payload: dict[str, object] = {"type": type(action).__name__, "label": describe(action)}
    match action:
        case SummonUnit(card, _position):
            payload.update(card=str(card), cost=get_card(card).cost)
        case BuildStructure(card, _position):
            payload.update(card=str(card), cost=get_card(card).cost)
        case PlayEvent(card, _targets):
            payload.update(card=str(card), cost=get_card(card).cost, name=get_card(card).name)
        case AttackUnit(attacker, target):
            payload.update(attacker=int(attacker), target=int(target))
        case SlySwap(target):
            payload.update(target=int(target))
    return payload


def who_acts(state: GameState) -> PlayerId:
    return state.active


def card_name(card: CardId) -> str:
    return get_card(card).name
