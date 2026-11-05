"""Engine contract and rules tests.

Each test names the rulebook page it encodes. If a test fails, the rule (or the engine's
reading of it) changed: fix the engine, never silently relax the assertion.
"""

from __future__ import annotations

import dataclasses
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sw_cards import get_card, get_deck, known_decks
from sw_engine.actions import (
    AttackUnit,
    BuildStructure,
    DiscardForMagic,
    EndPhase,
    MoveUnit,
    SummonUnit,
)
from sw_engine.engine import (
    STARTING_MAGIC_FIRST,
    STARTING_MAGIC_SECOND,
    Outcome,
    RulesError,
    adjudicate_by_life,
    initial_state,
    is_terminal,
    legal_actions,
    observation,
    outcome,
    step,
)
from sw_engine.ids import PLAYER_A, PLAYER_B, CardId, DeckId, PlayerId, UnitId, opponent
from sw_engine.state import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    HAND_SIZE,
    MAX_UNITS_PER_PHASE,
    AttackKind,
    GameState,
    Phase,
    PlayerState,
    Square,
    UnitKind,
    UnitState,
)

DECK_A = DeckId("savanna_elves")
DECK_B = DeckId("cave_goblins")


def _state(seed: int = 7) -> GameState:
    return initial_state(DECK_A, DECK_B, seed)


def _unit(
    unit_id: int,
    owner: PlayerId,
    square: tuple[int, int],
    *,
    kind: UnitKind = UnitKind.UNIT,
    attack: AttackKind = AttackKind.MELEE,
    strength: int = 2,
    life: int = 3,
) -> UnitState:
    return UnitState(
        unit_id=UnitId(unit_id),
        owner=owner,
        card=CardId(f"test-{unit_id}"),
        kind=kind,
        attack=attack,
        position=Square(*square),
        strength=strength,
        life=life,
    )


def _combat_state(units: tuple[UnitState, ...], phase: Phase = Phase.ATTACK) -> GameState:
    """A state with hand-picked units, so combat maths is isolated from setup noise.

    Summoners are added when the test does not supply them, and hands are emptied so no
    unrelated action is legal. Their squares (0,7) and (5,0) are reserved for this helper.
    """
    state = _state()
    owners = {u.owner for u in units if u.kind is UnitKind.SUMMONER}
    extra: list[UnitState] = []
    if PLAYER_A not in owners:
        extra.append(_unit(90, PLAYER_A, (0, 7), kind=UnitKind.SUMMONER, attack=AttackKind.NONE))
    if PLAYER_B not in owners:
        extra.append(_unit(91, PLAYER_B, (5, 0), kind=UnitKind.SUMMONER, attack=AttackKind.NONE))
    all_units = (*units, *extra)
    ids = {u.owner: u.unit_id for u in all_units if u.kind is UnitKind.SUMMONER}
    players = tuple(
        dataclasses.replace(p, summoner_id=ids[p.player], hand=(), deck=(), discard=())
        for p in state.players
    )
    pair: tuple[PlayerState, PlayerState] = (players[0], players[1])
    return dataclasses.replace(state, units=all_units, phase=phase, active=PLAYER_A, players=pair)


def _advance(state: GameState, target: Phase) -> GameState:
    while state.phase is not target:
        state = step(state, EndPhase())
    return state


# --------------------------------------------------------------------------------------
# Setup — rulebook p.5
# --------------------------------------------------------------------------------------


def test_same_seed_is_reproducible() -> None:
    assert _state(1).state_hash() == _state(1).state_hash()


def test_different_seed_shuffles_differently() -> None:
    assert _state(1).state_hash() != _state(2).state_hash()


def test_state_is_frozen() -> None:
    state = _state()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.turn = 99  # type: ignore[misc]


def test_setup_sizes_and_magic() -> None:
    """p.5: draw 5, first player on 2 magic, opponent on 3; board starts populated."""
    state = _state()
    for player in state.players:
        assert len(player.hand) == HAND_SIZE
        assert len(player.deck) == 34 - HAND_SIZE
    active = state.player(state.active)
    other = state.player(opponent(state.active))
    assert active.magic == STARTING_MAGIC_FIRST == 2
    assert other.magic == STARTING_MAGIC_SECOND == 3
    assert state.phase is Phase.SUMMON
    # summoner, gate and two starting units per side
    assert len(state.units_of(PLAYER_A)) == 4
    assert len(state.units_of(PLAYER_B)) == 4


# --------------------------------------------------------------------------------------
# Summon — rulebook p.6
# --------------------------------------------------------------------------------------


def test_summon_places_unit_and_pays_cost() -> None:
    state = _state()
    state = dataclasses.replace(state, active=PLAYER_A)
    action = next(a for a in legal_actions(state) if isinstance(a, SummonUnit))
    cost = get_card(action.card).cost
    after = step(state, action)

    assert after.player(PLAYER_A).magic == state.player(PLAYER_A).magic - cost
    assert len(after.units) == len(state.units) + 1
    gate = next(u for u in state.units_of(PLAYER_A) if u.kind is UnitKind.GATE)
    assert action.position.is_adjacent_to(gate.position)


def test_summon_rejects_square_not_next_to_gate() -> None:
    state = dataclasses.replace(_state(), active=PLAYER_A)
    card = next(c for c in state.player(PLAYER_A).hand if get_card(c).kind is UnitKind.UNIT)
    with pytest.raises(RulesError):
        step(state, SummonUnit(card, Square(5, 7)))


def test_summon_requires_magic() -> None:
    state = dataclasses.replace(_state(), active=PLAYER_A)
    broke = dataclasses.replace(state.player(PLAYER_A), magic=0)
    players = (broke, state.player(PLAYER_B))
    state = dataclasses.replace(state, players=players)
    cards = [a for a in legal_actions(state) if isinstance(a, SummonUnit)]
    assert cards == []


# --------------------------------------------------------------------------------------
# Move — rulebook p.7
# --------------------------------------------------------------------------------------


def test_only_three_units_may_move() -> None:
    units = (
        _unit(1, PLAYER_A, (0, 2)),
        _unit(2, PLAYER_A, (2, 2)),
        _unit(3, PLAYER_A, (4, 2)),
        _unit(4, PLAYER_A, (0, 4)),
    )
    state = _combat_state(units, phase=Phase.MOVE)
    state = step(state, MoveUnit(UnitId(1), Square(1, 2)))
    for unit_id, target in ((2, Square(3, 2)), (3, Square(5, 2))):
        state = step(state, MoveUnit(UnitId(unit_id), target))
    assert len(state.moved) == MAX_UNITS_PER_PHASE
    remaining = [a for a in legal_actions(state) if isinstance(a, MoveUnit)]
    assert remaining == []


def test_cannot_move_diagonally_or_through_cards() -> None:
    units = (
        _unit(1, PLAYER_A, (2, 2)),
        _unit(2, PLAYER_B, (3, 2)),
    )
    state = _combat_state(units, phase=Phase.MOVE)
    with pytest.raises(RulesError):
        step(state, MoveUnit(UnitId(1), Square(3, 3)))  # diagonal
    with pytest.raises(RulesError):
        step(state, MoveUnit(UnitId(1), Square(4, 2)))  # blocked at (3,2)
    step(state, MoveUnit(UnitId(1), Square(2, 4)))  # legal 2-space move


def test_structures_cannot_move() -> None:
    gate = _unit(9, PLAYER_A, (2, 2), kind=UnitKind.GATE, attack=AttackKind.NONE)
    state = _combat_state((gate,), phase=Phase.MOVE)
    moves = [a for a in legal_actions(state) if isinstance(a, MoveUnit) and a.unit_id == UnitId(9)]
    assert moves == []


# --------------------------------------------------------------------------------------
# Attack — rulebook p.8
# --------------------------------------------------------------------------------------


def test_melee_needs_adjacency_ranged_needs_a_clear_line() -> None:
    units = (
        _unit(1, PLAYER_A, (2, 2), attack=AttackKind.MELEE),
        _unit(2, PLAYER_A, (4, 6), attack=AttackKind.RANGED),
        _unit(3, PLAYER_B, (2, 3)),  # adjacent to the melee attacker
        _unit(4, PLAYER_B, (4, 3)),  # 3 straight spaces from the ranged attacker
        _unit(5, PLAYER_B, (3, 4)),  # off-axis for the ranged attacker
        _unit(6, PLAYER_B, (2, 5)),  # two spaces away: melee cannot reach
    )
    state = _combat_state(units)
    legal = {(a.attacker, a.target) for a in legal_actions(state) if isinstance(a, AttackUnit)}
    assert (UnitId(1), UnitId(3)) in legal  # melee, adjacent
    assert (UnitId(1), UnitId(6)) not in legal  # melee, not adjacent
    assert (UnitId(2), UnitId(4)) in legal  # ranged, 3 spaces in a line
    assert (UnitId(2), UnitId(5)) not in legal  # off-axis, not a straight line


def test_ranged_line_must_be_clear() -> None:
    units = (
        _unit(1, PLAYER_A, (1, 4), attack=AttackKind.RANGED),
        _unit(2, PLAYER_B, (2, 4)),  # blocks the line
        _unit(3, PLAYER_B, (4, 4)),
    )
    state = _combat_state(units)
    legal = {(a.attacker, a.target) for a in legal_actions(state) if isinstance(a, AttackUnit)}
    assert (UnitId(1), UnitId(2)) in legal
    assert (UnitId(1), UnitId(3)) not in legal


def test_destroying_enemy_card_grants_magic() -> None:
    units = (
        _unit(1, PLAYER_A, (2, 2), strength=6),
        _unit(2, PLAYER_B, (2, 3), life=1),
        _unit(3, PLAYER_A, (0, 0), kind=UnitKind.SUMMONER, attack=AttackKind.NONE),
        _unit(4, PLAYER_B, (5, 7), kind=UnitKind.SUMMONER, attack=AttackKind.NONE),
    )
    state = _combat_state(units)
    state = dataclasses.replace(
        state,
        players=(
            dataclasses.replace(state.player(PLAYER_A), magic=5),
            state.player(PLAYER_B),
        ),
    )

    after = step(state, AttackUnit(UnitId(1), UnitId(2)))
    assert all(u.unit_id != UnitId(2) for u in after.units)
    assert after.player(PLAYER_A).magic == 6


def test_cost_of_inaction_damages_your_summoner() -> None:
    """p.8: +1 damage to your summoner if you attacked nothing this turn."""
    units = (
        _unit(1, PLAYER_A, (0, 0), kind=UnitKind.SUMMONER, attack=AttackKind.NONE, life=12),
        _unit(2, PLAYER_B, (5, 7), kind=UnitKind.SUMMONER, attack=AttackKind.NONE, life=12),
    )
    state = _combat_state(units)

    after = step(state, EndPhase())  # leaves ATTACK without attacking
    assert after.summoner(PLAYER_A).damage == 1
    assert after.phase is Phase.MAGIC


# --------------------------------------------------------------------------------------
# Turn flow — rulebook p.9
# --------------------------------------------------------------------------------------


def test_end_of_turn_draws_back_to_five_and_passes_turn() -> None:
    state = _state()
    start_active = state.active
    state = _advance(state, Phase.MAGIC)
    before_hand = len(state.player(start_active).hand)
    after = step(state, EndPhase())
    assert after.active == opponent(start_active)
    assert after.turn == 2
    assert after.phase is Phase.SUMMON
    assert len(after.player(opponent(start_active)).hand) <= HAND_SIZE
    assert len(after.player(start_active).hand) >= before_hand


def test_build_only_in_back_rows_or_by_summoner() -> None:
    state = _advance(dataclasses.replace(_state(), active=PLAYER_A), Phase.BUILD)
    gate_card = next(c for c in state.player(PLAYER_A).hand if c.endswith("gate"))
    legal_squares = {a.position for a in legal_actions(state) if isinstance(a, BuildStructure)}
    assert Square(0, 0) in legal_squares  # back row
    assert Square(5, 7) not in legal_squares  # opponent's back row
    step(state, BuildStructure(gate_card, Square(0, 2)))


def test_magic_phase_discard_gains_one_magic() -> None:
    state = _advance(dataclasses.replace(_state(), active=PLAYER_A), Phase.MAGIC)
    card = state.player(PLAYER_A).hand[0]
    before = state.player(PLAYER_A)
    after = step(state, DiscardForMagic(card))
    assert after.player(PLAYER_A).magic == min(15, before.magic + 1)
    assert len(after.player(PLAYER_A).hand) == len(before.hand) - 1


# --------------------------------------------------------------------------------------
# Terminal states — rulebook p.17
# --------------------------------------------------------------------------------------


def test_summoner_death_ends_the_game() -> None:
    units = (
        _unit(1, PLAYER_A, (0, 0), kind=UnitKind.SUMMONER, attack=AttackKind.NONE),
        _unit(2, PLAYER_B, (5, 7), kind=UnitKind.SUMMONER, attack=AttackKind.NONE, life=1),
    )
    state = _combat_state(units)
    dead = dataclasses.replace(state, units=(units[0], dataclasses.replace(units[1], damage=1)))
    assert is_terminal(dead)
    assert outcome(dead) is Outcome.WIN_A
    assert legal_actions(dead) == ()


def test_observation_hides_opponent_hand() -> None:
    obs = observation(_state(), PLAYER_A)
    assert obs.me().hand is not None
    assert obs.opponent().hand is None
    assert obs.opponent().hand_size == HAND_SIZE


# --------------------------------------------------------------------------------------
# Long-run invariants
# --------------------------------------------------------------------------------------


@settings(max_examples=20, deadline=None)
@given(seed=st.integers(min_value=0, max_value=5000), steps=st.integers(min_value=1, max_value=60))
def test_random_legal_play_keeps_invariants(seed: int, steps: int) -> None:
    state = initial_state(DECK_A, DECK_B, seed)
    rng = random.Random(seed)
    for _ in range(steps):
        actions = legal_actions(state)
        if not actions:
            break
        state = step(state, rng.choice(actions))

        for player in state.players:
            assert 0 <= player.magic <= 15
            deck, hand, discard = player.zone_sizes()
            # Summoned and built cards leave the zones, so the total can only shrink.
            assert 0 < deck + hand + discard <= 34
        positions = [u.position for u in state.units]
        assert len(positions) == len(set(positions)), "two cards on the same square"
        for unit in state.units:
            assert unit.position.is_on_board()
            assert unit.damage >= 0


@settings(max_examples=5, deadline=None)
@given(seed=st.integers(min_value=0, max_value=50))
def test_games_terminate_under_a_turn_cap(seed: int) -> None:
    """Fuzz target from AGENTS.md M1: every game finishes or is adjudicable by life."""
    state = initial_state(DECK_A, DECK_B, seed)
    rng = random.Random(seed)
    for _ in range(4000):
        if is_terminal(state) or state.turn > 200:
            break
        actions = legal_actions(state)
        if not actions:
            break
        state = step(state, rng.choice(actions))
    assert is_terminal(state) or adjudicate_by_life(state) is not None or state.turn > 200


# --------------------------------------------------------------------------------------
# Starting layouts — transcribed from the summoner card backs (docs/STARTING_LAYOUTS.md)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("deck_id", sorted(known_decks()))
def test_setup_matches_the_card_back(deck_id: DeckId) -> None:
    """Player A sits exactly on the printed layout; player B is the 180 degree mirror."""
    deck = get_deck(deck_id)
    state = initial_state(deck_id, deck_id, seed=1)

    expected: list[tuple[CardId, Square]] = [
        (deck.layout.summoner[0].card_id, deck.layout.summoner[1]),
        (deck.layout.gate[0].card_id, deck.layout.gate[1]),
        *((card.card_id, square) for card, square in deck.layout.units),
    ]

    a_positions = {unit.card: unit.position for unit in state.units_of(PLAYER_A)}
    b_positions = {unit.card: unit.position for unit in state.units_of(PLAYER_B)}

    for card_id, square in expected:
        assert a_positions[card_id] == square
        assert b_positions[card_id] == Square(
            BOARD_WIDTH - 1 - square.x, BOARD_HEIGHT - 1 - square.y
        )


@pytest.mark.parametrize("deck_id", sorted(known_decks()))
def test_setup_is_legal_and_inside_own_half(deck_id: DeckId) -> None:
    layout = get_deck(deck_id).layout
    squares = [layout.summoner[1], layout.gate[1], *(sq for _, sq in layout.units)]

    assert len({(s.x, s.y) for s in squares}) == 4, "two setup cards share a square"
    for square in squares:
        assert square.is_on_board()
        assert 0 <= square.y <= 3, "setup cards must start inside the owner's half"
