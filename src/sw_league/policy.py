"""The league's placeholder policy.

Deliberately simple and deliberately deterministic given a seed: the point is to exercise
every rule the engine implements, not to play well. A real league swaps this out per bot.
"""

from __future__ import annotations

import random
from typing import Final

from sw_cards import get_card
from sw_core import CardId, DeckId, PlayerId
from sw_engine.actions import (
    Action,
    AttackUnit,
    BuildStructure,
    CommandAlly,
    DiscardForMagic,
    EndPhase,
    ForceUnit,
    MimicAbility,
    MoveUnit,
    PlayEvent,
    SlySwap,
    SummonUnit,
)
from sw_engine.engine import legal_actions
from sw_engine.state import GameState
from sw_league.playbook import Playbook, neutral

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


def _battle_units(state: GameState, player: int) -> int:
    return sum(1 for unit in state.units if unit.owner == player and unit.kind.name == "UNIT")


def _gates(state: GameState, player: int) -> int:
    return sum(1 for unit in state.units if unit.owner == player and unit.kind.name == "GATE")


def score_action(state: GameState, action: Action, book: Playbook) -> float:
    """How much this playbook wants this action right now.

    The weights say what the deck is about; the situational bonuses say when. Both come from
    the distilled guide, and every term is small enough to be argued with.
    """
    kind = type(action).__name__
    score = book.weight(kind)
    mine = int(state.active)
    board = _battle_units(state, mine)

    if isinstance(action, SummonUnit):
        # Bodies are never wasted for a swarm deck, so the bonus never turns off; it just
        # matters most while the board is still thin.
        score += 0.8 if board < book.swarm_target_board else 0.4
        if get_card(action.card).cost == 0:
            score += 0.2
    elif isinstance(action, BuildStructure):
        if "gate" in str(action.card):
            score += 0.9 if _gates(state, mine) < book.build_gate_below else 0.0
    elif isinstance(action, AttackUnit):
        target = state.unit(action.target)
        card_class = get_card(target.card).card_class.upper().replace(" ", "_")
        score += book.target_bonus(card_class)
        if target.kind.name == "SUMMONER":
            score += 0.3
        attacker = state.unit(action.attacker)
        if attacker.kind.name == "SUMMONER" and book.keep_summoner_safe:
            score -= 0.4
        if book.prefer_ranged_attackers and attacker.attack.name == "RANGED":
            score += 0.3
        if action.attacker in state.extra_attackers:
            score += 0.2
    elif isinstance(action, PlayEvent):
        score += 0.3 if board >= book.event_value_from_board else -0.2
    elif isinstance(action, MoveUnit):
        unit = state.unit(action.unit_id)
        if book.prefer_ranged_attackers and unit.attack.name == "RANGED":
            # Ranged decks want the distance, so moving away from the enemy is good.
            nearest = min(
                (u for u in state.units if u.owner != mine),
                key=lambda u: u.position.distance_to(unit.position),
                default=None,
            )
            if nearest is not None and action.to.distance_to(nearest.position) > (
                unit.position.distance_to(nearest.position)
            ):
                score += 0.35
    return score


def choose_action(
    state: GameState,
    rng: random.Random,
    book: Playbook | None = None,
    event_chance: float = 0.6,
) -> Action:
    """Pick the action this playbook likes most, with a little randomness for ties.

    With no playbook the bot falls back to the plain priority order, which is what the league
    uses as its baseline opponent.
    """
    actions = legal_actions(state)
    if not actions:
        return EndPhase()

    if book is None:
        book = neutral(DeckId(str(state.active)))

    events = [action for action in actions if isinstance(action, PlayEvent)]
    if events and rng.random() < event_chance:
        return rng.choice(events)

    scored = [
        (score_action(state, action, book) + rng.random() * 0.25, action) for action in actions
    ]
    best = max(score for score, _ in scored)
    finalists = [action for score, action in scored if score >= best - 0.01]
    return rng.choice(finalists)


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
        case ForceUnit(source, target, dx, dy):
            return f"Unit {source} forces {target} by ({dx},{dy})"
        case CommandAlly(source, target):
            return f"Unit {source} commands {target} to attack again"
        case MimicAbility(unit, target):
            return f"Unit {unit} mimics unit {target}"
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
        case MoveUnit(unit_id, _to):
            payload.update(unit=int(unit_id))
        case ForceUnit(source, target, dx, dy):
            payload.update(source=int(source), target=int(target), dx=dx, dy=dy)
        case CommandAlly(source, target):
            payload.update(source=int(source), target=int(target))
        case MimicAbility(unit, target):
            payload.update(source=int(unit), target=int(target))
        case AttackUnit(attacker, target):
            payload.update(attacker=int(attacker), target=int(target))
        case SlySwap(target):
            payload.update(target=int(target))
    return payload


def who_acts(state: GameState) -> PlayerId:
    return state.active


def card_name(card: CardId) -> str:
    return get_card(card).name
