"""Event cards: playing them, paying for them, and the four Cave Goblins effects.

Rules referenced: rulebook p.9 — play an event on the phase printed on the card, pay its
cost, resolve it, discard it; ACTIVE events go to the active area instead and are discarded
at the start of your next turn.
"""

from __future__ import annotations

import dataclasses
from typing import Final

import pytest

from sw_core import AttackKind, CardId, Phase, PlayerId, Square, UnitId, UnitKind
from sw_engine.actions import AttackUnit, EndPhase, MoveUnit, PlayEvent, SlySwap
from sw_engine.engine import (
    RulesError,
    _effective_strength,
    initial_state,
    legal_actions,
    step,
)
from sw_engine.ids import PLAYER_A, PLAYER_B, DeckId
from sw_engine.state import GameState, PlayerState, UnitState

PILE_ON: Final[CardId] = CardId("cave_goblins-pile_on")
UNRELENTING: Final[CardId] = CardId("cave_goblins-unrelenting")
ENRAGE: Final[CardId] = CardId("cave_goblins-enrage_the_horde")
SNEAK: Final[CardId] = CardId("cave_goblins-sneak")
CLIMBER: Final[CardId] = CardId("cave_goblins-horde_climber")
SLINGER: Final[CardId] = CardId("cave_goblins-slinger")
BEAST_RIDER: Final[CardId] = CardId("cave_goblins-beast_rider")


def _base() -> GameState:
    return initial_state(DeckId("cave_goblins"), DeckId("savanna_elves"), seed=11)


def _battle(
    units: tuple[UnitState, ...] = (),
    *,
    phase: Phase,
    hand: tuple[CardId, ...] = (),
    magic: int = 10,
    active: PlayerId = PLAYER_A,
) -> GameState:
    """A state with the given extra units, a stacked hand and a chosen phase."""
    base = _base()
    keep = tuple(u for u in base.units if u.kind in (UnitKind.SUMMONER, UnitKind.GATE))
    first, second = base.players
    first = dataclasses.replace(first, hand=hand, magic=magic, deck=(), discard=())
    second = dataclasses.replace(second, hand=(), magic=0, deck=(), discard=())
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


def test_an_event_is_only_legal_on_its_printed_phase() -> None:
    attack = _battle(phase=Phase.ATTACK, hand=(PILE_ON,))
    assert any(isinstance(a, PlayEvent) for a in legal_actions(attack))

    move = _battle(phase=Phase.MOVE, hand=(PILE_ON,))
    assert not any(isinstance(a, PlayEvent) for a in legal_actions(move))


def test_playing_an_event_pays_its_cost_and_discards_it() -> None:
    unit = _unit(100, CLIMBER, Square(1, 1))
    state = _battle((unit,), phase=Phase.MOVE, hand=(SNEAK,), magic=4)

    after = step(state, PlayEvent(SNEAK, (unit.unit_id,)))

    seat = after.player(PLAYER_A)
    assert seat.magic == 4  # Sneak costs 0
    assert SNEAK not in seat.hand
    assert seat.discard == (SNEAK,)


def test_an_active_event_sits_in_the_active_area_then_is_discarded_next_turn() -> None:
    state = _battle(phase=Phase.ATTACK, hand=(PILE_ON,), magic=3)
    after = step(state, PlayEvent(PILE_ON))
    assert after.player(PLAYER_A).active_events == (PILE_ON,)
    assert PILE_ON not in after.player(PLAYER_A).discard

    # Play out the rest of the turn and the opponent's turn.
    state = after
    for _ in range(20):
        if state.active == PLAYER_A and state.turn >= 3:
            break
        state = step(state, EndPhase())

    assert state.player(PLAYER_A).active_events == ()
    assert PILE_ON in state.player(PLAYER_A).discard


def test_pile_on_adds_strength_per_adjacent_friendly_unit() -> None:
    target = _unit(200, CLIMBER, Square(3, 3), owner=PLAYER_B, life=6)
    attacker = _unit(100, BEAST_RIDER, Square(3, 2), strength=3)
    neighbours = (
        _unit(101, SLINGER, Square(2, 3)),
        _unit(102, SLINGER, Square(3, 4)),
    )
    state = _battle((target, attacker, *neighbours), phase=Phase.ATTACK)

    plain = _effective_strength(state, attacker, target)
    assert plain == 3

    seat = state.player(PLAYER_A)
    armed = dataclasses.replace(
        state, players=(dataclasses.replace(seat, active_events=(PILE_ON,)), *state.players[1:])
    )
    assert _effective_strength(armed, attacker, target) == 5  # 3 printed + 2 adjacent friends


def test_unrelenting_returns_a_common_to_hand_instead_of_destroying_it() -> None:
    doomed = _unit(100, CLIMBER, Square(3, 2), life=3, damage=2)
    killer = _unit(200, BEAST_RIDER, Square(3, 3), owner=PLAYER_B, strength=6)
    state = _battle((doomed, killer), phase=Phase.ATTACK, active=PLAYER_B)
    first, second = state.players
    ordered: tuple[PlayerState, PlayerState] = (
        dataclasses.replace(first, active_events=(UNRELENTING,)),
        second,
    )
    state = dataclasses.replace(state, players=ordered)

    after = step(state, AttackUnit(killer.unit_id, doomed.unit_id))

    assert all(u.unit_id != doomed.unit_id for u in after.units), "the unit leaves the battlefield"
    assert CLIMBER in after.player(PLAYER_A).hand


def test_enrage_lets_zero_cost_units_attack_again() -> None:
    climber = _unit(100, CLIMBER, Square(3, 2), strength=2)
    target = _unit(200, CLIMBER, Square(3, 3), owner=PLAYER_B, life=9)
    state = _battle((climber, target), phase=Phase.ATTACK, hand=(ENRAGE,), magic=5)

    struck = step(state, AttackUnit(climber.unit_id, target.unit_id))
    assert not any(
        isinstance(a, AttackUnit) and a.attacker == climber.unit_id for a in legal_actions(struck)
    )

    enraged = step(struck, PlayEvent(ENRAGE))
    again = [a for a in legal_actions(enraged) if isinstance(a, AttackUnit)]
    assert any(a.attacker == climber.unit_id for a in again), "the extra attack is granted"


def test_sneak_pushes_a_zero_cost_unit_away_from_my_summoner() -> None:
    unit = _unit(100, CLIMBER, Square(3, 2))
    state = _battle((unit,), phase=Phase.MOVE, hand=(SNEAK,))

    after = step(state, PlayEvent(SNEAK, (unit.unit_id,)))

    summoner = after.summoner(PLAYER_A)
    moved = after.unit(unit.unit_id)
    assert moved.position.distance_to(summoner.position) > unit.position.distance_to(
        summoner.position
    )


def test_an_event_without_an_effect_handler_cannot_be_played() -> None:
    """Card text without engine support stays out of legal_actions instead of doing nothing."""
    state = _battle(phase=Phase.ATTACK, hand=(PILE_ON,))
    with pytest.raises(RulesError):
        step(dataclasses.replace(state, phase=Phase.MOVE), PlayEvent(PILE_ON))


# --------------------------------------------------------------------------------------
# Printed unit abilities that the engine honours
# --------------------------------------------------------------------------------------


def test_immobile_units_cannot_move() -> None:
    clinger = _unit(100, CardId("cave_goblins-horde_clinger"), Square(2, 1))
    state = _battle((clinger,), phase=Phase.MOVE)
    assert not any(
        isinstance(a, MoveUnit) and a.unit_id == clinger.unit_id for a in legal_actions(state)
    )


def test_charge_extends_the_move_to_four_straight_spaces() -> None:
    rider = _unit(100, BEAST_RIDER, Square(2, 1))
    state = _battle((rider,), phase=Phase.MOVE)
    squares = {
        a.to for a in legal_actions(state) if isinstance(a, MoveUnit) and a.unit_id == rider.unit_id
    }
    assert Square(2, 5) in squares, "four spaces straight ahead"
    assert Square(0, 5) not in squares, "charge is straight only"


def test_relentless_attacks_even_after_the_three_unit_limit() -> None:
    slinger = _unit(100, SLINGER, Square(3, 2), attack=AttackKind.RANGED, strength=2)
    others = tuple(_unit(110 + i, CLIMBER, Square(i, 2)) for i in range(3))
    target = _unit(200, CLIMBER, Square(3, 3), owner=PLAYER_B, life=9)
    state = _battle((slinger, *others, target), phase=Phase.ATTACK)

    state = dataclasses.replace(state, attacked=(UnitId(110), UnitId(111), UnitId(112)))
    attacks = [a for a in legal_actions(state) if isinstance(a, AttackUnit)]
    assert any(a.attacker == slinger.unit_id for a in attacks)


# --------------------------------------------------------------------------------------
# The remaining Cave Goblins abilities
# --------------------------------------------------------------------------------------

CLINGER: Final[CardId] = CardId("cave_goblins-horde_clinger")
BLARF: Final[CardId] = CardId("cave_goblins-blarf")
SMEG: Final[CardId] = CardId("cave_goblins-smeg")
EATER: Final[CardId] = CardId("cave_goblins-the_eater")
SNEEKS: Final[CardId] = CardId("cave_goblins-sneeks")


def test_climb_moves_three_spaces_and_passes_a_gate() -> None:
    climber = _unit(100, CLIMBER, Square(2, 1))
    state = _battle((climber,), phase=Phase.MOVE)
    squares = {
        a.to
        for a in legal_actions(state)
        if isinstance(a, MoveUnit) and a.unit_id == climber.unit_id
    }
    assert Square(2, 4) in squares, "climb moves one extra space"

    # A gate between origin and destination blocks everyone else but not the climber.
    base = _base()
    gate = next(u for u in base.units if u.kind is UnitKind.GATE and u.owner == PLAYER_B)
    blocked = dataclasses.replace(state, units=(*state.units, gate))
    through = {
        a.to
        for a in legal_actions(blocked)
        if isinstance(a, MoveUnit) and a.unit_id == climber.unit_id
    }
    assert any(square.x == gate.position.x for square in through)


def test_cling_follows_a_friendly_unit_that_moved_away() -> None:
    mover = _unit(100, CLIMBER, Square(2, 2))
    clinger = _unit(101, CLINGER, Square(2, 1))
    state = _battle((mover, clinger), phase=Phase.MOVE)

    after = step(state, MoveUnit(mover.unit_id, Square(2, 4)))

    moved = after.unit(clinger.unit_id)
    assert moved.position.is_adjacent_to(Square(2, 4))
    assert moved.position != Square(2, 1)


def test_sly_swaps_sneeks_with_a_zero_cost_unit_once_per_turn() -> None:
    base = _base()
    summoner = base.summoner(PLAYER_A)
    climber = _unit(100, CLIMBER, Square(2, 2))
    state = _battle((climber,), phase=Phase.ATTACK)

    swaps = [a for a in legal_actions(state) if isinstance(a, SlySwap)]
    assert swaps == [SlySwap(climber.unit_id)]

    after = step(state, swaps[0])
    assert after.unit(summoner.unit_id).position == Square(2, 2)
    assert after.unit(climber.unit_id).position == summoner.position
    assert not any(isinstance(a, SlySwap) for a in legal_actions(after)), "once per turn"


def test_blood_runes_spends_magic_for_a_boost_then_falls_back_to_damage() -> None:
    blarf = _unit(100, BLARF, Square(3, 2), strength=0, life=6)
    state = _battle((blarf,), phase=Phase.BUILD, magic=5)

    after = step(state, EndPhase())  # BUILD -> ATTACK
    boosted = after.unit(blarf.unit_id)
    assert after.phase is Phase.ATTACK
    assert boosted.boosts == 1 and after.player(PLAYER_A).magic == 4

    broke = _battle((blarf,), phase=Phase.BUILD, magic=0)
    after_broke = step(broke, EndPhase())
    assert after_broke.unit(blarf.unit_id).damage == 1, "no magic means one damage instead"


def test_magic_junkie_pays_or_is_discarded_at_the_end_of_the_turn() -> None:
    smeg = _unit(100, SMEG, Square(3, 2), life=4)
    rich = _battle((smeg,), phase=Phase.MAGIC, magic=3)
    after = step(rich, EndPhase())
    assert any(u.unit_id == smeg.unit_id for u in after.units)
    assert after.player(PLAYER_A).magic == 2

    poor = _battle((smeg,), phase=Phase.MAGIC, magic=0)
    after_poor = step(poor, EndPhase())
    assert all(u.unit_id != smeg.unit_id for u in after_poor.units)


def test_the_eater_discards_a_neighbour_when_it_destroyed_nothing() -> None:
    eater = _unit(100, EATER, Square(3, 2), strength=5, life=9)
    snack = _unit(101, CLIMBER, Square(3, 1))
    state = _battle((eater, snack), phase=Phase.ATTACK)

    after = step(state, EndPhase())

    assert any(u.unit_id == eater.unit_id for u in after.units)
    assert all(u.unit_id != snack.unit_id for u in after.units), "the neighbour is eaten"


def test_the_eater_never_eats_its_own_summoner() -> None:
    eater = _unit(100, EATER, Square(3, 2), strength=5, life=9)
    state = _battle((eater,), phase=Phase.ATTACK)
    summoner = state.summoner(PLAYER_A)
    state = dataclasses.replace(
        state, units=tuple(u for u in state.units if u.unit_id != summoner.unit_id)
    )
    state = dataclasses.replace(
        state,
        units=(*state.units, dataclasses.replace(summoner, position=Square(3, 1))),
    )

    after = step(state, EndPhase())

    assert any(u.unit_id == summoner.unit_id for u in after.units), "the summoner stays"
    assert all(u.unit_id != eater.unit_id for u in after.units), "the Eater eats itself instead"


def test_the_eater_eats_itself_when_alone() -> None:
    eater = _unit(100, EATER, Square(3, 2), strength=5, life=9)
    state = _battle((eater,), phase=Phase.ATTACK)

    after = step(state, EndPhase())
    assert all(u.unit_id != eater.unit_id for u in after.units)


# --------------------------------------------------------------------------------------
# Breakers movement and range abilities
# --------------------------------------------------------------------------------------

WIND_ARCHER: Final[CardId] = CardId("breakers-wind_archer")
GWALARK: Final[CardId] = CardId("breakers-gwalark")
WIND_MAGE: Final[CardId] = CardId("breakers-wind_mage")


def test_climb_moves_one_space_further_than_a_plain_unit() -> None:
    mage = _unit(100, WIND_MAGE, Square(2, 1))
    climber = _unit(101, CLIMBER, Square(0, 1))
    state = _battle((mage, climber), phase=Phase.MOVE)

    def reach(unit: UnitState) -> int:
        squares = [
            a.to
            for a in legal_actions(state)
            if isinstance(a, MoveUnit) and a.unit_id == unit.unit_id
        ]
        return max(unit.position.distance_to(square) for square in squares)

    assert reach(mage) == 2, "a plain unit moves 2"
    assert reach(climber) == 3, "Climb adds one"


def test_swift_alone_reaches_three_spaces() -> None:
    # Wind Archer has Swift only (no Climb): 3 spaces, straight, cards still block.
    archer = _unit(100, WIND_ARCHER, Square(2, 1), attack=AttackKind.RANGED, strength=4)
    state = _battle((archer,), phase=Phase.MOVE)
    squares = {
        a.to
        for a in legal_actions(state)
        if isinstance(a, MoveUnit) and a.unit_id == archer.unit_id
    }
    assert Square(2, 4) in squares
    assert Square(2, 5) not in squares


def test_far_shot_reaches_four_spaces() -> None:
    archer = _unit(100, WIND_ARCHER, Square(3, 1), attack=AttackKind.RANGED, strength=4)
    far = _unit(200, CLIMBER, Square(3, 5), owner=PLAYER_B, life=5)
    near = _unit(201, CLIMBER, Square(3, 4), owner=PLAYER_B, life=5)
    state = _battle((archer, far), phase=Phase.ATTACK)
    attacks = {a.target for a in legal_actions(state) if isinstance(a, AttackUnit)}
    assert far.unit_id in attacks, "4 spaces is inside Far Shot"

    blocked = _battle((archer, far, near), phase=Phase.ATTACK)
    attacks_blocked = {a.target for a in legal_actions(blocked) if isinstance(a, AttackUnit)}
    assert far.unit_id not in attacks_blocked, "the line must still be clear"
    assert near.unit_id in attacks_blocked


def test_gwalark_flies_and_lends_flight_to_nearby_commons() -> None:
    gwalark = _unit(100, GWALARK, Square(3, 2), life=8, strength=3)
    common = _unit(101, WIND_MAGE, Square(3, 0))
    far_common = _unit(102, WIND_MAGE, Square(0, 7))
    state = _battle((gwalark, common, far_common), phase=Phase.MOVE)

    def reach(unit: UnitState) -> int:
        squares = [
            a.to
            for a in legal_actions(state)
            if isinstance(a, MoveUnit) and a.unit_id == unit.unit_id
        ]
        return max((unit.position.distance_to(s) for s in squares), default=0)

    assert reach(gwalark) == 3, "Flight: base 2 plus 1"
    assert reach(common) == 3, "within 2 spaces of Gwalark, so it has Flight"
    assert reach(far_common) == 2, "too far from Gwalark, no Flight"


# --------------------------------------------------------------------------------------
# Deceiver: Stupefy and Engage
# --------------------------------------------------------------------------------------

DECEIVER: Final[CardId] = CardId("breakers-deceiver")


def test_stupefy_costs_the_attacker_one_damage() -> None:
    target_b = _unit(200, CLIMBER, Square(3, 3), owner=PLAYER_B, life=9)
    attacker = _unit(100, BEAST_RIDER, Square(3, 2), strength=6)
    deceiver = _unit(
        101, DECEIVER, Square(2, 2), owner=PLAYER_B, strength=1, attack=AttackKind.RANGED
    )

    plain = _battle((attacker, target_b), phase=Phase.ATTACK)
    with_deceiver = _battle((attacker, target_b, deceiver), phase=Phase.ATTACK)

    plain_after = step(plain, AttackUnit(attacker.unit_id, target_b.unit_id))
    stupefied = step(with_deceiver, AttackUnit(attacker.unit_id, target_b.unit_id))

    without = next(u for u in plain_after.units if u.unit_id == target_b.unit_id).damage
    with_penalty = next(u for u in stupefied.units if u.unit_id == target_b.unit_id).damage
    assert without - with_penalty == 1, f"{without} vs {with_penalty}"


def test_engage_damages_a_unit_that_walks_away() -> None:
    deceiver = _unit(
        101, DECEIVER, Square(3, 3), owner=PLAYER_B, strength=1, attack=AttackKind.RANGED
    )
    walker = _unit(100, CLIMBER, Square(3, 2))
    state = _battle((walker, deceiver), phase=Phase.MOVE)

    after = step(state, MoveUnit(walker.unit_id, Square(3, 0)))

    assert after.unit(walker.unit_id).damage == 1


def test_engage_does_not_fire_when_the_mover_never_stood_beside_it() -> None:
    deceiver = _unit(
        101, DECEIVER, Square(0, 7), owner=PLAYER_B, strength=1, attack=AttackKind.RANGED
    )
    walker = _unit(100, CLIMBER, Square(3, 2))
    state = _battle((walker, deceiver), phase=Phase.MOVE)

    after = step(state, MoveUnit(walker.unit_id, Square(3, 0)))

    assert after.unit(walker.unit_id).damage == 0
