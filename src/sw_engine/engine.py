"""Rules engine entry points.

Contract (see AGENTS.md): these functions are pure. `step` never mutates its input,
and every decision an agent makes flows through `legal_actions` / `step`. The engine
imports nothing from `agents` or `league`, and performs no I/O.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from enum import Enum, auto

from sw_cards import get_deck
from sw_engine.actions import Action, EndTurn
from sw_engine.ids import PLAYER_A, PLAYER_B, CardId, DeckId, PlayerId, opponent
from sw_engine.observation import Observation, VisiblePlayer, visible_unit
from sw_engine.state import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    HAND_SIZE,
    GameState,
    Phase,
    PlayerState,
    Square,
    SummonerState,
)

# Rulebook p.5: setup draws 5; p.9: draw back up to 5 at end of turn.
INITIAL_HAND_SIZE = HAND_SIZE

# Rulebook p.5: the first player starts on magic 2, the other on magic 3.
STARTING_MAGIC_FIRST = 2
STARTING_MAGIC_SECOND = 3

# Summoner life is per-card data (p.4 card anatomy), not a rule constant. This value is a
# placeholder until M3 wires real card data in; see docs/CARD_STATUS.md.
PLACEHOLDER_SUMMONER_HP = 12


class Outcome(Enum):
    WIN_A = auto()
    WIN_B = auto()
    DRAW = auto()


@dataclass(frozen=True, slots=True)
class RulesError(Exception):
    """Raised when an action is not legal in the given state."""

    message: str

    def __str__(self) -> str:
        return self.message


def derive_rng(seed: int, player: PlayerId) -> random.Random:
    """Deterministic per-player RNG.

    `random.Random` only accepts None/int/float/str/bytes as seeds, and Python's
    string/bytes hashing is salted per process, so we derive a stable 64-bit seed
    with blake2b instead of relying on `hash()` or on tuples.
    """
    payload = f"{seed}:{int(player)}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _starting_square(player: PlayerId) -> Square:
    """Summoner's starting square.

    TODO(rules): validate gate and summoner placement against the rulebook in M1.
    Until then the two summoners sit in the middle column on opposite edges.
    """
    x = BOARD_WIDTH // 2
    return Square(x, 0) if player == PLAYER_A else Square(x, BOARD_HEIGHT - 1)


def _build_player(
    deck_id: DeckId, player: PlayerId, starting_magic: int, rng: random.Random
) -> PlayerState:
    definition = get_deck(deck_id)
    cards: list[CardId] = list(definition.cards)
    rng.shuffle(cards)
    hand = tuple(cards[:INITIAL_HAND_SIZE])
    remaining = tuple(cards[INITIAL_HAND_SIZE:])
    return PlayerState(
        player=player,
        summoner=SummonerState(
            owner=player,
            card=CardId(f"{definition.deck_id}-summoner"),
            position=_starting_square(player),
            hp=PLACEHOLDER_SUMMONER_HP,
        ),
        magic=starting_magic,
        deck=remaining,
        hand=hand,
        discard=(),
    )


def initial_state(deck_a: DeckId, deck_b: DeckId, seed: int) -> GameState:
    """Create a fresh game.

    One `random.Random` per player, derived from the game seed, so that shuffles are
    independent and reproducible. Never seed from the clock or from `hash()`.

    Rulebook p.5: the first player is determined at random and starts on magic 2 while
    the opponent starts on magic 3, compensating the second player for moving second.
    """
    chooser = derive_rng(seed, PLAYER_A)
    first: PlayerId = PLAYER_A if chooser.random() < 0.5 else PLAYER_B
    second = opponent(first)
    magic_by_player = {first: STARTING_MAGIC_FIRST, second: STARTING_MAGIC_SECOND}

    players: tuple[PlayerState, PlayerState] = (
        _build_player(deck_a, PLAYER_A, magic_by_player[PLAYER_A], derive_rng(seed, PLAYER_A)),
        _build_player(deck_b, PLAYER_B, magic_by_player[PLAYER_B], derive_rng(seed, PLAYER_B)),
    )
    return GameState(turn=1, active=first, phase=Phase.SUMMON, players=players, seed=seed)


def legal_actions(state: GameState) -> tuple[Action, ...]:
    """Every action the active player may take.

    TODO(M1): summon / move / attack legality. At M0 only passing is legal, which
    keeps the fuzzer and the agent interface honest without pretending to model rules
    that are not implemented yet.
    """
    if is_terminal(state):
        return ()
    return (EndTurn(),)


def step(state: GameState, action: Action) -> GameState:
    """Apply an action, returning a new state. Raises RulesError if illegal."""
    if action not in legal_actions(state):
        raise RulesError(f"illegal action {action!r} in state {state.state_hash()}")
    match action:
        case EndTurn():
            return GameState(
                turn=state.turn + 1,
                active=opponent(state.active),
                phase=Phase.SUMMON,
                players=state.players,
                units=state.units,
                seed=state.seed,
            )
    raise RulesError(f"unhandled action type: {type(action).__name__}")


def is_terminal(state: GameState) -> bool:
    return (
        not state.player(PLAYER_A).summoner.is_alive()
        or not state.player(PLAYER_B).summoner.is_alive()
    )


def outcome(state: GameState) -> Outcome | None:
    """Result of a finished game, or None while it is still running."""
    a_alive = state.player(PLAYER_A).summoner.is_alive()
    b_alive = state.player(PLAYER_B).summoner.is_alive()
    if a_alive and b_alive:
        return None
    if a_alive:
        return Outcome.WIN_A
    if b_alive:
        return Outcome.WIN_B
    return Outcome.DRAW


def observation(state: GameState, viewer: PlayerId) -> Observation:
    """Project the state down to what `viewer` may legally see."""
    players: list[VisiblePlayer] = []
    for player_state in state.players:
        own = player_state.player == viewer
        players.append(
            VisiblePlayer(
                player=player_state.player,
                summoner=player_state.summoner,
                magic=player_state.magic,
                deck_size=len(player_state.deck),
                hand=player_state.hand if own else None,
                hand_size=len(player_state.hand),
                discard=player_state.discard,
            )
        )
    pair: tuple[VisiblePlayer, VisiblePlayer] = (players[0], players[1])
    return Observation(
        turn=state.turn,
        active=state.active,
        phase=state.phase,
        viewer=viewer,
        players=pair,
        units=tuple(visible_unit(unit) for unit in state.units),
    )


__all__ = [
    "Outcome",
    "RulesError",
    "derive_rng",
    "initial_state",
    "is_terminal",
    "legal_actions",
    "observation",
    "outcome",
    "step",
]
