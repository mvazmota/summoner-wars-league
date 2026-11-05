"""Turn a game into a JSON-friendly frame list.

One frame per action, so a viewer can step through the game without owning the rules.
Frames carry the full board plus a structured description of what just happened.
"""

from __future__ import annotations

import random
from typing import Any, Final

from sw_cards import get_card
from sw_core import DeckId
from sw_engine.engine import initial_state, is_terminal, outcome, step
from sw_engine.state import GameState, UnitState
from sw_league.playbook import load as load_playbook
from sw_league.policy import choose_action, describe_action

MAX_STEPS: Final[int] = 4000


def unit_payload(unit: UnitState) -> dict[str, Any]:
    card = get_card(unit.card)
    return {
        "id": int(unit.unit_id),
        "owner": int(unit.owner),
        "card": str(unit.card),
        "name": card.name,
        "card_class": card.card_class,
        "kind": unit.kind.name,
        "attack": unit.attack.name.lower(),
        "position": f"({unit.position.x},{unit.position.y})",
        "x": unit.position.x,
        "y": unit.position.y,
        "strength": unit.strength,
        "boosts": unit.boosts,
        "life": unit.life,
        "damage": unit.damage,
    }


def snapshot(state: GameState) -> dict[str, Any]:
    seats = []
    for seat in state.players:
        seats.append(
            {
                "player": int(seat.player),
                "magic": seat.magic,
                "deck": len(seat.deck),
                "discard": len(seat.discard),
                "hand": [get_card(card).name for card in seat.hand],
                "active_events": [get_card(card).name for card in seat.active_events],
                "summoner_life": state.summoner(seat.player).remaining_life(),
            }
        )
    return {
        "turn": state.turn,
        "active": int(state.active),
        "phase": state.phase.name,
        "players": seats,
        "units": [unit_payload(unit) for unit in state.units],
    }


def result_label(state: GameState) -> str:
    result = outcome(state)
    if result is None:
        return "unfinished"
    name = f"{result}".rsplit(".", 1)[-1]
    return {"WIN_A": "A wins", "WIN_B": "B wins"}.get(name, "draw")


def play_game(
    deck_a: DeckId,
    deck_b: DeckId,
    seed: int,
    max_steps: int = MAX_STEPS,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    state = initial_state(deck_a, deck_b, seed)
    books = {0: load_playbook(deck_a), 1: load_playbook(deck_b)}
    frames: list[dict[str, Any]] = [
        {"label": "Setup", "action": {"type": "Setup", "label": "Setup"}, "state": snapshot(state)}
    ]

    steps = 0
    while not is_terminal(state) and steps < max_steps:
        action = choose_action(state, rng, books[int(state.active)])
        actor = int(state.active)
        detail = describe_action(action)
        try:
            state = step(state, action)
        except Exception as error:
            frames.append(
                {
                    "label": f"ERROR: {error}",
                    "action": {"type": "Error", "label": str(error)},
                    "error": str(error),
                    "state": snapshot(state),
                }
            )
            break
        detail["actor"] = actor
        frames.append({"label": detail["label"], "action": detail, "state": snapshot(state)})
        steps += 1

    frames.append(
        {
            "label": "Game over",
            "action": {"type": "GameOver", "label": "Game over"},
            "result": result_label(state),
            "state": snapshot(state),
        }
    )
    return frames
