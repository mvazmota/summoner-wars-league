"""Engine contract tests for milestone M0.

These encode the invariants the rest of the project depends on: determinism,
immutability, legality closure, terminal semantics, and observation filtering.
"""

from __future__ import annotations

import dataclasses
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sw_engine.actions import EndTurn
from sw_engine.engine import (
    STARTING_MAGIC_FIRST,
    STARTING_MAGIC_SECOND,
    Outcome,
    RulesError,
    initial_state,
    is_terminal,
    legal_actions,
    observation,
    outcome,
    step,
)
from sw_engine.ids import PLAYER_A, PLAYER_B, DeckId, opponent
from sw_engine.state import HAND_SIZE, GameState, Phase, SummonerState

DECK_A = DeckId("placeholder_alpha")
DECK_B = DeckId("placeholder_beta")


def _state(seed: int = 7) -> GameState:
    return initial_state(DECK_A, DECK_B, seed)


def _with_dead_summoner(state: GameState, player: int) -> GameState:
    players = list(state.players)
    index = next(i for i, p in enumerate(players) if int(p.player) == player)
    target = players[index]
    dead = dataclasses.replace(target.summoner, damage=target.summoner.hp)
    players[index] = dataclasses.replace(target, summoner=dead)
    pair = (players[0], players[1])
    return dataclasses.replace(state, players=pair)


def test_same_seed_is_reproducible() -> None:
    assert _state(1).state_hash() == _state(1).state_hash()


def test_different_seed_shuffles_differently() -> None:
    assert _state(1).state_hash() != _state(2).state_hash()


def test_state_is_frozen() -> None:
    state = _state()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.turn = 99  # type: ignore[misc]


def test_initial_hand_and_deck_sizes() -> None:
    state = _state()
    for player in state.players:
        assert len(player.hand) == HAND_SIZE
        assert len(player.deck) == 30 - HAND_SIZE
        assert player.discard == ()


def test_first_player_starts_on_two_magic_and_opponent_on_three() -> None:
    """Rulebook p.5: the first player begins on 2, the other on 3."""
    state = _state()
    active = state.active_player()
    other = state.player(opponent(state.active))
    assert active.magic == STARTING_MAGIC_FIRST == 2
    assert other.magic == STARTING_MAGIC_SECOND == 3
    assert state.phase is Phase.SUMMON


def test_legal_actions_non_empty_and_pass_only() -> None:
    state = _state()
    actions = legal_actions(state)
    assert actions == (EndTurn(),)


def test_step_does_not_mutate_input() -> None:
    state = _state()
    before = state.state_hash()
    after = step(state, EndTurn())
    assert state.state_hash() == before
    assert after.state_hash() != before


def test_end_turn_switches_player_and_advances_turn() -> None:
    state = _state()
    after = step(state, EndTurn())
    assert after.active == opponent(state.active)
    assert after.turn == state.turn + 1
    assert after.phase is Phase.SUMMON


def test_illegal_action_raises() -> None:
    state = _state()
    with pytest.raises(RulesError):
        step(state, "not an action")  # type: ignore[arg-type]


def test_not_terminal_at_start_and_no_outcome() -> None:
    state = _state()
    assert is_terminal(state) is False
    assert outcome(state) is None
    assert legal_actions(state) != ()


def test_dead_summoner_ends_the_game() -> None:
    state = _with_dead_summoner(_state(), int(PLAYER_A))
    assert is_terminal(state) is True
    assert outcome(state) is Outcome.WIN_B
    assert legal_actions(state) == ()


def test_both_summoners_dead_is_a_draw() -> None:
    state = _with_dead_summoner(_with_dead_summoner(_state(), int(PLAYER_A)), int(PLAYER_B))
    assert outcome(state) is Outcome.DRAW


def test_observation_hides_opponent_hand() -> None:
    state = _state()
    obs = observation(state, PLAYER_A)
    assert obs.me().player == PLAYER_A
    assert obs.me().hand is not None
    assert obs.opponent().player == PLAYER_B
    assert obs.opponent().hand is None
    assert obs.opponent().hand_size == 5
    assert obs.opponent().deck_size == 25


def test_observation_exposes_no_hidden_cards_in_units() -> None:
    obs = observation(_state(), PLAYER_A)
    assert obs.units == ()


@settings(max_examples=25, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000), steps=st.integers(min_value=0, max_value=40)
)
def test_invariants_hold_under_random_legal_play(seed: int, steps: int) -> None:
    state = initial_state(DECK_A, DECK_B, seed)
    rng = random.Random(seed)
    for _ in range(steps):
        actions = legal_actions(state)
        if not actions or is_terminal(state):
            break
        state = step(state, rng.choice(actions))

        assert not is_terminal(state) or outcome(state) is not None
        for player in state.players:
            assert player.magic >= 0
            assert player.summoner.damage >= 0
            assert player.summoner.position.is_on_board()
            deck, hand, discard = player.zone_sizes()
            assert deck + hand + discard == 30
        for unit in state.units:
            assert unit.position.is_on_board()
            assert unit.damage >= 0


def test_summoner_state_defaults_are_sane() -> None:
    summoner = SummonerState(
        owner=PLAYER_A,
        card=_state().player(PLAYER_A).summoner.card,
        position=_state().player(PLAYER_A).summoner.position,
        hp=20,
    )
    assert summoner.is_alive()
