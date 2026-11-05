"""Validation for the hand-transcribed card data in data/cards/.

The JSON files are typed in from the physical cards, so they are the one place in this
project where a typo is invisible to the compiler. These tests are the safety net.
"""

from __future__ import annotations

import pytest

from sw_cards import get_deck, known_decks, load_verified_cards
from sw_engine.ids import DeckId

VALID_ATTACKS = {"melee", "ranged", "none"}


@pytest.mark.parametrize("deck_id", sorted(known_decks()))
def test_verified_entries_are_well_formed(deck_id: DeckId) -> None:
    for name, entry in load_verified_cards(deck_id).items():
        assert entry["id"].startswith(f"{deck_id}-"), f"{name}: id must be namespaced by faction"
        assert 0 <= entry["cost"] <= 12, f"{name}: implausible cost"
        assert 1 <= entry["life"] <= 15, f"{name}: implausible life"
        assert 0 <= entry["strength"] <= 8, f"{name}: implausible strength"
        assert entry["attack"] in VALID_ATTACKS, f"{name}: unknown attack kind"
        if entry.get("ability_name"):
            assert "ability" in entry, f"{name}: named ability without text or explicit null"


def test_every_transcribed_card_exists_in_its_deck() -> None:
    """A typo in the card name would silently fall back to placeholder stats."""
    verified = load_verified_cards(DeckId("cave_goblins"))
    names = {card.name for card in get_deck(DeckId("cave_goblins")).units}
    for name in verified:
        assert name in names, f"{name} is transcribed but not present in the deck definition"


def test_transcribed_stats_reach_the_engine() -> None:
    deck = get_deck(DeckId("cave_goblins"))
    by_name = {card.name: card for card in deck.units}
    slinger = by_name["Horde Slinger"]
    assert (slinger.cost, slinger.life, slinger.strength) == (0, 1, 2)
    assert slinger.ability_name == "Relentless"
