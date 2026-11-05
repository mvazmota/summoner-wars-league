"""Validation for the hand-transcribed card data in data/cards/.

The JSON files are typed in from the physical cards, so they are the one place in this
project where a typo is invisible to the compiler. These tests are the safety net.
"""

from __future__ import annotations

import pytest

from sw_cards import DRAW_PILE_SIZE, get_deck, known_decks, load_verified_cards
from sw_engine.ids import DeckId

BATTLEFIELD_CLASSES = {"Summoner", "Champion", "Common"}
CARD_CLASSES = BATTLEFIELD_CLASSES | {"Epic Event", "Standard Event"}
VALID_ATTACKS = {"melee", "ranged", "none"}


@pytest.mark.parametrize("deck_id", sorted(known_decks()))
def test_verified_entries_are_well_formed(deck_id: DeckId) -> None:
    for name, entry in load_verified_cards(deck_id).items():
        assert entry["id"].startswith(f"{deck_id}-"), f"{name}: id must be namespaced by faction"
        assert entry["card_class"] in CARD_CLASSES, f"{name}: unknown class"
        assert entry["attack"] in VALID_ATTACKS, f"{name}: unknown attack kind"
        assert entry.get("ability"), f"{name}: transcribed without ability text"

        if entry["card_class"] in BATTLEFIELD_CLASSES:
            cost = entry["cost"]
            life = entry["life"]
            strength = entry["strength"]
            assert cost is None or 0 <= cost <= 12, f"{name}: implausible cost"
            assert isinstance(life, int) and 1 <= life <= 15, f"{name}: implausible life"
            assert isinstance(strength, int) and 0 <= strength <= 8, f"{name}: implausible strength"
        else:
            assert entry["life"] is None and entry["strength"] is None, (
                f"{name}: events never have life or strength"
            )
            assert entry["attack"] == "none", f"{name}: events never attack"
            assert isinstance(entry["cost"], int), f"{name}: events always cost magic"


def test_every_transcribed_card_is_known_to_the_project() -> None:
    """A typo in the card name would silently fall back to placeholder stats."""
    deck = get_deck(DeckId("cave_goblins"))
    known = {card.name for card in deck.units} | {deck.layout.summoner[0].name}
    # Champions and events are transcribed but not modelled by the engine yet.
    unmodelled = {"Blarf", "Smeg", "The Eater"} | {
        name
        for name, entry in load_verified_cards(DeckId("cave_goblins")).items()
        if entry["card_class"].endswith("Event")
    }
    for name in load_verified_cards(DeckId("cave_goblins")):
        assert name in known or name in unmodelled, f"{name} is transcribed but unknown"


def test_transcribed_stats_reach_the_engine() -> None:
    deck = get_deck(DeckId("cave_goblins"))
    by_name = {card.name: card for card in deck.units}

    slinger = by_name["Horde Slinger"]
    assert (slinger.cost, slinger.life, slinger.strength) == (0, 1, 2)
    assert slinger.ability_name == "Relentless"

    summoner = deck.layout.summoner[0]
    assert (summoner.name, summoner.life, summoner.strength) == ("Sneeks", 11, 3)


def test_event_slots_add_up_to_the_deck_requirement() -> None:
    """A 34 card deck carries 8 events: 2 epic plus 6 standard."""
    events = {
        name: entry
        for name, entry in load_verified_cards(DeckId("cave_goblins")).items()
        if entry["card_class"].endswith("Event")
    }
    total = sum(entry.get("copies") or 1 for entry in events.values())
    assert total == 8, f"events cover {total} of the 8 slots"
    epic = [n for n, e in events.items() if e["card_class"] == "Epic Event"]
    standard = [n for n, e in events.items() if e["card_class"] == "Standard Event"]
    assert len(epic) >= 1 and len(standard) == 3, (epic, standard)


def test_goblins_have_the_full_roster_of_commons() -> None:
    commons = {
        name
        for name, entry in load_verified_cards(DeckId("cave_goblins")).items()
        if entry["card_class"] == "Common"
    }
    assert commons == {"Beast Rider", "Horde Slinger", "Horde Climber", "Horde Clinger"}


def test_breakers_are_complete() -> None:
    deck = get_deck(DeckId("breakers"))
    assert deck.layout.summoner[0].name == "Taculla"
    assert (deck.layout.summoner[0].life, deck.layout.summoner[0].strength) == (13, 3)
    assert {card.name for card, _ in deck.layout.units} == {"Mind Witch", "Deceiver"}
    assert deck.is_complete
    assert len(deck.composition) == DRAW_PILE_SIZE

    champions = [card for card in deck.units if card.card_class == "Champion"]
    assert {card.name for card in champions} == {"Gwalark", "Gulldune", "Halal"}

    deceiver = next(card for card in deck.units if card.name == "Deceiver")
    assert (deceiver.cost, deceiver.life, deceiver.strength) == (1, 4, 1)
    assert deceiver.ability_name == "Stupefy / Engage"


def test_every_faction_has_a_summoner_with_stats() -> None:
    for deck_id in known_decks():
        deck = get_deck(deck_id)
        summoner = deck.layout.summoner[0]
        assert summoner.life >= 8, f"{deck_id}: summoned with implausible life"
        assert summoner.strength >= 1


def test_fallen_kingdom_is_transcribed() -> None:
    deck = get_deck(DeckId("fallen_kingdom"))
    assert deck.layout.summoner[0].name == "Ret-Talus"
    assert (deck.layout.summoner[0].life, deck.layout.summoner[0].strength) == (14, 2)
    assert {card.name for card, _ in deck.layout.units} == {"Undead Carrier", "Undead Archer"}

    by_name = {card.name: card for card in deck.units}
    assert (by_name["Hellfire Cultist"].cost, by_name["Hellfire Cultist"].life) == (0, 2)
    assert by_name["Elut-Bal"].strength == 6
    assert by_name["Gul-Dass"].life == 9

    # One common and one champion are still missing, so the pile is short of 30.
    assert not deck.is_complete
    assert len(deck.composition) == DRAW_PILE_SIZE - 5
