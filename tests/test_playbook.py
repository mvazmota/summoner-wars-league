"""Playbooks: the distilled strategy guides the bots play by."""

from __future__ import annotations

import dataclasses

from sw_core import AttackKind, CardId, DeckId, Phase, Square, UnitId, UnitKind
from sw_engine.actions import AttackUnit, SummonUnit
from sw_engine.engine import initial_state, legal_actions
from sw_engine.ids import PLAYER_A, PLAYER_B
from sw_engine.state import GameState, PlayerState, UnitState
from sw_league.playbook import ACTION_KINDS, available, load, neutral
from sw_league.policy import score_action

GUIDED = ("breakers", "cave_goblins", "fallen_kingdom")


def test_every_guided_faction_loads_with_provenance() -> None:
    assert set(available()) >= set(GUIDED)
    for deck_id in GUIDED:
        book = load(DeckId(deck_id))
        assert book.identity != "neutral"
        assert book.source.startswith("https://sw-zone.com/")
        assert book.summary
        assert book.notes, "a playbook without notes is just numbers"
        for kind in ACTION_KINDS:
            assert kind in book.weights, f"{deck_id} has no weight for {kind}"


def test_unguided_factions_fall_back_to_neutral() -> None:
    book = load(DeckId("vanguards"))
    assert book.identity == "neutral"
    assert set(book.weights.values()) == {1.0}


def test_goblins_rank_summoning_above_a_plain_attack_early() -> None:
    goblins = load(DeckId("cave_goblins"))
    state, summon, attack = _early_state()

    summon_score = score_action(state, summon, goblins)
    attack_score = score_action(state, attack, goblins)
    assert summon_score > attack_score, (summon_score, attack_score)

    neutral_score = score_action(state, summon, neutral(DeckId("cave_goblins")))
    assert summon_score > neutral_score, "the guide must change the decision, not just the words"


def test_fallen_kingdom_prefers_the_attack() -> None:
    kingdom = load(DeckId("fallen_kingdom"))
    state, summon, attack = _early_state()

    assert score_action(state, attack, kingdom) > score_action(state, summon, kingdom)


def test_breakers_prefer_push_and_distance() -> None:
    breakers = load(DeckId("breakers"))
    goblins = load(DeckId("cave_goblins"))
    assert breakers.weight("ForceUnit") > goblins.weight("ForceUnit")
    assert breakers.prefer_ranged_attackers
    assert goblins.keep_summoner_safe


def _early_state() -> tuple[GameState, SummonUnit, AttackUnit]:
    """A turn-1-ish board: one goblin common in hand, one enemy unit in reach."""
    base = initial_state(DeckId("cave_goblins"), DeckId("fallen_kingdom"), seed=4)
    keep = tuple(u for u in base.units if u.kind in (UnitKind.SUMMONER, UnitKind.GATE))
    first, second = base.players
    first = dataclasses.replace(first, hand=(CardId("cave_goblins-horde_climber"),), magic=5)
    enemy = UnitState(
        unit_id=UnitId(500),
        owner=PLAYER_B,
        card=CardId("fallen_kingdom-hellfire_cultist"),
        kind=UnitKind.UNIT,
        attack=AttackKind.RANGED,
        position=Square(4, 5),
        strength=2,
        life=2,
    )
    attacker = UnitState(
        unit_id=UnitId(501),
        owner=PLAYER_A,
        card=CardId("cave_goblins-beast_rider"),
        kind=UnitKind.UNIT,
        attack=AttackKind.MELEE,
        position=Square(4, 6),
        strength=3,
        life=3,
    )
    pair: tuple[PlayerState, PlayerState] = (first, second)
    state = dataclasses.replace(base, players=pair, units=(*keep, enemy, attacker), active=PLAYER_A)

    summon_state = dataclasses.replace(state, phase=Phase.SUMMON)
    summons = [a for a in legal_actions(summon_state) if isinstance(a, SummonUnit)]
    attack_state = dataclasses.replace(state, phase=Phase.ATTACK)
    attacks = [a for a in legal_actions(attack_state) if isinstance(a, AttackUnit)]
    assert summons, "the fixture must allow a summon"
    assert attacks, "the fixture must allow an attack"
    return state, summons[0], attacks[0]


def test_playbook_does_not_change_legality() -> None:
    """Scoring must never invent legal moves; it only orders the ones the rules allow."""
    state, summon, _attack = _early_state()
    summon_legal = set(legal_actions(dataclasses.replace(state, phase=Phase.SUMMON)))
    attack_legal = set(legal_actions(dataclasses.replace(state, phase=Phase.ATTACK)))

    assert summon in summon_legal
    assert not any(isinstance(a, AttackUnit) for a in summon_legal), (
        "an attack cannot be legal during the Summon Phase"
    )
    assert not any(isinstance(a, SummonUnit) for a in attack_legal), (
        "a summon cannot be legal during the Attack Phase"
    )
