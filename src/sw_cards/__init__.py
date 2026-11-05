"""Card and deck data.

M0 ships synthetic placeholder decks only, so the engine can be exercised before any
real card is encoded. Real factions arrive in M3, as data, via the effect DSL.

Rule: no official card text or artwork lives in this repository. Card entries carry a
short mechanical paraphrase at most.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from sw_engine.ids import CardId, DeckId

PLACEHOLDER_DECK_SIZE: Final[int] = 30


@dataclass(frozen=True, slots=True)
class DeckDefinition:
    deck_id: DeckId
    faction: str
    cards: tuple[CardId, ...]


def _placeholder_deck(deck_id: str, faction: str) -> DeckDefinition:
    cards = tuple(CardId(f"{deck_id}-{index:02d}") for index in range(PLACEHOLDER_DECK_SIZE))
    return DeckDefinition(deck_id=DeckId(deck_id), faction=faction, cards=cards)


REGISTRY: Final[dict[DeckId, DeckDefinition]] = {
    DeckId("placeholder_alpha"): _placeholder_deck("placeholder_alpha", "Placeholder Alpha"),
    DeckId("placeholder_beta"): _placeholder_deck("placeholder_beta", "Placeholder Beta"),
}


def get_deck(deck_id: DeckId) -> DeckDefinition:
    try:
        return REGISTRY[deck_id]
    except KeyError as exc:
        raise KeyError(f"unknown deck: {deck_id!r}") from exc


def known_decks() -> tuple[DeckId, ...]:
    return tuple(sorted(REGISTRY))
