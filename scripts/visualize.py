"""Play one game and write a self-contained HTML viewer for it.

Usage:
    uv run python scripts/visualize.py --seed 7 --out out/replay.html

The output has no dependencies: the whole game is embedded as JSON and rendered by plain
JavaScript, so it can be opened from disk or served by `python -m http.server`.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Final

from sw_cards import get_card, known_decks
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
from sw_engine.engine import initial_state, is_terminal, legal_actions, outcome, step
from sw_engine.ids import DeckId
from sw_engine.state import GameState, UnitState

WEB_TEMPLATE: Final[Path] = Path(__file__).resolve().parents[1] / "web" / "replay.html"

# A deliberately simple policy: attack, then summon, then play an event, then move, then
# end the phase. Good enough to show the engine working, not a serious opponent.
PRIORITY: Final[tuple[type, ...]] = (
    AttackUnit,
    SummonUnit,
    PlayEvent,
    MoveUnit,
    BuildStructure,
    SlySwap,
    DiscardForMagic,
)


def _rank(action: Action) -> int:
    for index, kind in enumerate(PRIORITY):
        if isinstance(action, kind):
            return index
    return len(PRIORITY)


def choose_action(state: GameState, rng: random.Random) -> Action:
    """Events first when they are available and paid for, then attacks, summons, moves.

    Playing events early is what makes the viewer show them at all; a strictly greedy
    "attack first" policy never reaches the event branch because an attack almost always
    exists.
    """
    actions = legal_actions(state)
    if not actions:
        return EndPhase()

    events = [action for action in actions if isinstance(action, PlayEvent)]
    if events and rng.random() < 0.6:
        return rng.choice(events)

    best = min(_rank(action) for action in actions)
    candidates = [action for action in actions if _rank(action) == best]
    return rng.choice(candidates)


def describe(action: Action) -> str:
    match action:
        case SummonUnit(card, position):
            return f"Summon {get_card(card).name} at {_square(position)}"
        case BuildStructure(card, position):
            return f"Build {get_card(card).name} at {_square(position)}"
        case MoveUnit(unit_id, to):
            return f"Move unit {unit_id} to {_square(to)}"
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


def _square(position: Any) -> str:
    return f"({position.x},{position.y})"


def _unit_payload(unit: UnitState) -> dict[str, Any]:
    card = get_card(unit.card)
    return {
        "id": int(unit.unit_id),
        "owner": int(unit.owner),
        "card": str(unit.card),
        "name": card.name,
        "card_class": card.card_class,
        "kind": unit.kind.name,
        "attack": unit.attack.name.lower(),
        "position": _square(unit.position),
        "x": unit.position.x,
        "y": unit.position.y,
        "strength": unit.strength,
        "boosts": unit.boosts,
        "life": unit.life,
        "damage": unit.damage,
    }


def snapshot(state: GameState) -> dict[str, Any]:
    players = []
    for seat in state.players:
        players.append(
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
        "players": players,
        "units": [_unit_payload(unit) for unit in state.units],
    }


def record(state: GameState, label: str) -> dict[str, Any]:
    return {"label": label, "state": snapshot(state)}


def play_game(
    deck_a: DeckId, deck_b: DeckId, seed: int, max_steps: int = 4000
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    state = initial_state(deck_a, deck_b, seed)
    frames = [record(state, "Setup")]

    steps = 0
    while not is_terminal(state) and steps < max_steps:
        action = choose_action(state, rng)
        try:
            state = step(state, action)
        except Exception as error:
            frames.append(record(state, f"ERROR: {error}"))
            break
        frames.append(record(state, describe(action)))
        steps += 1

    frames.append(
        {
            "label": "Game over",
            "state": snapshot(state),
            "result": _result_label(state),
        }
    )
    return frames


def _result_label(state: GameState) -> str:
    result = outcome(state)
    if result is None:
        return "unfinished (step cap reached)"
    name = f"{result}".rsplit(".", 1)[-1]
    return {"WIN_A": "A wins", "WIN_B": "B wins"}.get(name, "draw")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--deck-a", default="cave_goblins")
    parser.add_argument("--deck-b", default="savanna_elves")
    parser.add_argument("--out", default="out/replay.html")
    parser.add_argument("--max-steps", type=int, default=4000)
    args = parser.parse_args()

    available = {str(deck) for deck in known_decks()}
    for deck in (args.deck_a, args.deck_b):
        if deck not in available:
            parser.error(f"unknown deck {deck!r}; known: {sorted(available)}")

    frames = play_game(DeckId(args.deck_a), DeckId(args.deck_b), args.seed, args.max_steps)
    payload = {
        "meta": {
            "deck_a": args.deck_a,
            "deck_b": args.deck_b,
            "seed": args.seed,
            "frames": len(frames),
            "result": frames[-1].get("result"),
        },
        "frames": frames,
    }

    template = WEB_TEMPLATE.read_text(encoding="utf-8")
    html = template.replace("__REPLAY_DATA__", json.dumps(payload, separators=(",", ":")))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size // 1024} KiB, {len(frames)} frames)")
    print(f"open: file://{out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
