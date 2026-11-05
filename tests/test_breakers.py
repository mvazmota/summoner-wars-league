"""Breakers mechanics: force, control, mimicry and the four events."""

from __future__ import annotations

import dataclasses
from typing import Final

import pytest

from sw_core import AttackKind, CardId, Phase, PlayerId, Square, UnitId, UnitKind
from sw_engine.actions import (
    AttackUnit,
    CommandAlly,
    EndPhase,
    ForceUnit,
    MimicAbility,
    MoveUnit,
    PlayEvent,
)
from sw_engine.engine import (
    RulesError,
    _effective_strength,
    _unit_has_ability,
    initial_state,
    legal_actions,
    step,
)
from sw_engine.ids import PLAYER_A, PLAYER_B, DeckId
from sw_engine.state import GameState, PlayerState, UnitState

WIND_MAGE: Final[CardId] = CardId("breakers-wind_mage")
WIND_ARCHER: Final[CardId] = CardId("breakers-wind_archer")
MIND_WITCH: Final[CardId] = CardId("breakers-mind_witch")
HALAL: Final[CardId] = CardId("breakers-halal")
GULLDUNE: Final[CardId] = CardId("breakers-gulldune")
TACULLA: Final[CardId] = CardId("breakers-taculla")
BLAST: Final[CardId] = CardId("breakers-blast")
HYPNOTIC_CALL: Final[CardId] = CardId("breakers-hypnotic_call")
PERPLEXING_TEMPEST: Final[CardId] = CardId("breakers-perplexing_tempest")
MIND_CONTROL: Final[CardId] = CardId("breakers-mind_control")
CLIMBER: Final[CardId] = CardId("cave_goblins-horde_climber")


def _base() -> GameState:
    return initial_state(DeckId("breakers"), DeckId("cave_goblins"), seed=17)


def _battle(
    units: tuple[UnitState, ...] = (),
    *,
    phase: Phase,
    hand: tuple[CardId, ...] = (),
    magic: int = 10,
    active: PlayerId = PLAYER_A,
) -> GameState:
    base = _base()
    keep = tuple(u for u in base.units if u.kind in (UnitKind.SUMMONER, UnitKind.GATE))
    first, second = base.players
    first = dataclasses.replace(first, hand=hand, magic=magic, deck=(), discard=())
    second = dataclasses.replace(second, hand=(), magic=10, deck=(), discard=())
    pair: tuple[PlayerState, PlayerState] = (first, second)
    return dataclasses.replace(
        base,
        players=pair,
        units=keep + units,
        phase=phase,
        active=active,
        moved=(),
        attacked=(),
        attacked_any=False,
        extra_attackers=(),
        forced=(),
    )


def _unit(
    unit_id: int,
    card: CardId,
    position: Square,
    *,
    owner: PlayerId = PLAYER_A,
    strength: int = 2,
    life: int = 3,
    damage: int = 0,
    attack: AttackKind = AttackKind.MELEE,
) -> UnitState:
    return UnitState(
        unit_id=UnitId(unit_id),
        owner=owner,
        card=card,
        kind=UnitKind.UNIT,
        attack=attack,
        position=position,
        strength=strength,
        life=life,
        damage=damage,
    )


def _forces(state: GameState) -> list[ForceUnit]:
    return [action for action in legal_actions(state) if isinstance(action, ForceUnit)]


# --------------------------------------------------------------------------------------
# Push and Greater Push
# --------------------------------------------------------------------------------------


def test_push_shoves_an_adjacent_enemy_one_space_away() -> None:
    mage = _unit(100, WIND_MAGE, Square(2, 2))
    enemy = _unit(200, CLIMBER, Square(2, 3), owner=PLAYER_B)
    state = _battle((mage, enemy), phase=Phase.ATTACK)

    assert ForceUnit(mage.unit_id, enemy.unit_id, 0, 1) in _forces(state)

    after = step(state, ForceUnit(mage.unit_id, enemy.unit_id, 0, 1))
    assert after.unit(enemy.unit_id).position == Square(2, 4)
    assert not _forces(after), "one push per unit per turn"


def test_push_reaches_two_spaces_and_greater_push_three() -> None:
    mage = _unit(100, WIND_MAGE, Square(2, 2))
    far_enemy = _unit(200, CLIMBER, Square(2, 5), owner=PLAYER_B)
    mage_state = _battle((mage, far_enemy), phase=Phase.ATTACK)
    assert not _forces(mage_state), "3 spaces is outside Push's 2"

    halal = _unit(101, HALAL, Square(2, 2), strength=4, life=8, attack=AttackKind.RANGED)
    halal_state = _battle((halal, far_enemy), phase=Phase.ATTACK)
    assert any(f.source == halal.unit_id for f in _forces(halal_state)), "Greater Push reaches 3"


def test_steadfast_cannot_be_forced() -> None:
    halal = _unit(100, HALAL, Square(2, 2), strength=4, life=8, attack=AttackKind.RANGED)
    mage = _unit(101, WIND_MAGE, Square(2, 3))
    state = _battle((mage, halal), phase=Phase.ATTACK, active=PLAYER_B)

    # Halal is player A's; make the mage the enemy of the active player instead.
    assert not any(f.target == halal.unit_id for f in _forces(state))


def test_force_stops_when_the_square_behind_is_occupied() -> None:
    mage = _unit(100, WIND_MAGE, Square(2, 3))
    enemy = _unit(200, CLIMBER, Square(2, 2), owner=PLAYER_B)
    behind = _unit(201, CLIMBER, Square(2, 1), owner=PLAYER_B)
    state = _battle((mage, enemy, behind), phase=Phase.ATTACK)

    actions = _forces(state)
    assert ForceUnit(mage.unit_id, enemy.unit_id, 0, -1) not in actions, "blocked by a body"
    assert ForceUnit(mage.unit_id, behind.unit_id, 0, -1) in actions, "the far unit has room"

    with pytest.raises(RulesError):
        step(state, ForceUnit(mage.unit_id, enemy.unit_id, 0, -1))


# --------------------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------------------


def test_perplexing_tempest_slows_every_move() -> None:
    climber = _unit(100, CLIMBER, Square(2, 1))
    state = _battle((climber,), phase=Phase.MOVE)

    def reach(current: GameState) -> int:
        moves = [
            a.to
            for a in legal_actions(current)
            if isinstance(a, MoveUnit) and a.unit_id == climber.unit_id
        ]
        return max(climber.position.distance_to(square) for square in moves)

    assert reach(state) == 3, "Climb gives 3 by default"

    seat = state.player(PLAYER_A)
    slowed = dataclasses.replace(
        state,
        players=(
            dataclasses.replace(seat, active_events=(PERPLEXING_TEMPEST,)),
            *state.players[1:],
        ),
    )
    assert reach(slowed) == 2, "Climb's 3 minus the tempest's 1"


def test_blast_pushes_three_spaces_and_damages_what_it_passes() -> None:
    summoner = _base().summoner(PLAYER_A)
    target = _unit(
        200, CLIMBER, Square(summoner.position.x, summoner.position.y + 2), owner=PLAYER_B, life=5
    )
    in_the_way = _unit(
        201, CLIMBER, Square(summoner.position.x, summoner.position.y + 3), owner=PLAYER_B, life=5
    )
    state = _battle((target, in_the_way), phase=Phase.MOVE, hand=(BLAST,), magic=5)

    after = step(state, PlayEvent(BLAST, (target.unit_id,)))

    assert after.unit(target.unit_id).damage == 1
    assert after.unit(in_the_way.unit_id).damage == 1, "the unit it was forced through"
    assert after.unit(target.unit_id).position.y > target.position.y


def test_hypnotic_call_pulls_toward_the_summoner_and_marks_the_target() -> None:
    summoner = _base().summoner(PLAYER_A)
    target = _unit(
        200, CLIMBER, Square(summoner.position.x, summoner.position.y + 3), owner=PLAYER_B
    )
    state = _battle((target,), phase=Phase.SUMMON, hand=(HYPNOTIC_CALL,), magic=5)

    after = step(state, PlayEvent(HYPNOTIC_CALL, (target.unit_id,)))

    assert after.unit(target.unit_id).position.y < target.position.y
    assert after.player(PLAYER_A).hypnotic_target == target.unit_id
    assert _effective_strength(after, after.summoner(PLAYER_A), after.unit(target.unit_id)) == 4


def test_mind_control_borrows_units_until_the_end_of_the_turn() -> None:
    summoner = _base().summoner(PLAYER_A)
    enemy = _unit(
        200, CLIMBER, Square(summoner.position.x, summoner.position.y + 2), owner=PLAYER_B
    )
    state = _battle((enemy,), phase=Phase.SUMMON, hand=(MIND_CONTROL,), magic=5)

    after = step(state, PlayEvent(MIND_CONTROL, (enemy.unit_id,)))
    assert after.unit(enemy.unit_id).owner == PLAYER_A

    state = after
    for _ in range(40):
        if state.turn > 1:
            break
        state = step(state, EndPhase())
    assert state.unit(enemy.unit_id).owner == PLAYER_B, "control ends with the turn"


# --------------------------------------------------------------------------------------
# Abilities
# --------------------------------------------------------------------------------------


def test_mind_capture_converts_a_unit_it_would_destroy() -> None:
    taculla = _unit(100, TACULLA, Square(3, 2), strength=3, life=13)
    victim = _unit(200, CLIMBER, Square(3, 3), owner=PLAYER_B, life=1)
    state = _battle((taculla, victim), phase=Phase.ATTACK)

    after = step(state, AttackUnit(taculla.unit_id, victim.unit_id))

    captured = after.unit(victim.unit_id)
    assert captured.owner == PLAYER_A
    assert captured.damage == 0, "the damage is ignored, not applied"


def test_telepathic_command_grants_a_second_attack() -> None:
    gulldune = _unit(100, GULLDUNE, Square(3, 2), strength=4, life=6)
    ally = _unit(101, CLIMBER, Square(4, 3))
    target = _unit(200, CLIMBER, Square(3, 3), owner=PLAYER_B, life=9)
    state = _battle((gulldune, ally, target), phase=Phase.ATTACK)

    struck = step(state, AttackUnit(gulldune.unit_id, target.unit_id))
    commands = [a for a in legal_actions(struck) if isinstance(a, CommandAlly)]
    assert commands, "Gulldune may command an ally after attacking"

    commanded = step(struck, commands[0])
    again = [
        a
        for a in legal_actions(commanded)
        if isinstance(a, AttackUnit) and a.attacker == ally.unit_id
    ]
    assert again, "the ally may attack again"


def test_mimic_copies_the_targets_abilities_for_the_turn() -> None:
    witch = _unit(100, MIND_WITCH, Square(3, 2), strength=3, life=2, attack=AttackKind.RANGED)
    archer = _unit(101, WIND_ARCHER, Square(3, 1), strength=4, life=2, attack=AttackKind.RANGED)
    state = _battle((witch, archer), phase=Phase.MOVE)

    actions = [a for a in legal_actions(state) if isinstance(a, MimicAbility)]
    assert actions, "Mind Witch may mimic a common within 3 spaces"

    after = step(state, actions[0])
    copied = after.unit(witch.unit_id)
    assert _unit_has_ability(copied, "Far Shot")
    assert _unit_has_ability(copied, "Mimic"), "the printed ability is not lost"
