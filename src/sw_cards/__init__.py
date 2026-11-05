"""Card and deck data.

Everything in this module is a **placeholder**: synthetic units with plausible stats and
no abilities, so the engine can be exercised before real card data lands in M3.

Rule: no official card text or artwork lives in this repository. Real cards will be
encoded as data — stats plus a short mechanical paraphrase — never as copied text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from sw_engine.ids import CardId, DeckId
from sw_engine.state import AttackKind, UnitKind

DECK_SIZE: Final[int] = 34
GATE_LIFE: Final[int] = 10  # rulebook p.5: starting gates have 10 life


@dataclass(frozen=True, slots=True)
class CardDefinition:
    card_id: CardId
    name: str
    kind: UnitKind
    attack: AttackKind
    cost: int
    strength: int
    life: int


@dataclass(frozen=True, slots=True)
class DeckDefinition:
    deck_id: DeckId
    faction: str
    summoner: CardDefinition
    gate: CardDefinition
    units: tuple[CardDefinition, ...]
    starting_units: tuple[CardDefinition, ...]
    composition: tuple[CardId, ...]


def _unit(
    deck: str, slug: str, *, cost: int, strength: int, life: int, attack: AttackKind
) -> CardDefinition:
    return CardDefinition(
        card_id=CardId(f"{deck}-{slug}"),
        name=f"{deck} {slug}",
        kind=UnitKind.UNIT,
        attack=attack,
        cost=cost,
        strength=strength,
        life=life,
    )


def _build_deck(deck: str, faction: str) -> DeckDefinition:
    summoner = CardDefinition(
        card_id=CardId(f"{deck}-summoner"),
        name=f"{faction} Summoner",
        kind=UnitKind.SUMMONER,
        attack=AttackKind.MELEE,
        cost=0,
        strength=2,
        life=12,
    )
    gate = CardDefinition(
        card_id=CardId(f"{deck}-gate"),
        name=f"{faction} Gate",
        kind=UnitKind.GATE,
        attack=AttackKind.NONE,
        cost=0,
        strength=0,
        life=GATE_LIFE,
    )
    scout = _unit(deck, "scout", cost=1, strength=1, life=2, attack=AttackKind.MELEE)
    brute = _unit(deck, "brute", cost=2, strength=2, life=3, attack=AttackKind.MELEE)
    archer = _unit(deck, "archer", cost=3, strength=2, life=2, attack=AttackKind.RANGED)

    composition: list[CardId] = []
    for card in (scout, brute, archer):
        composition.extend([card.card_id] * 10)
    composition.extend([gate.card_id] * 4)

    return DeckDefinition(
        deck_id=DeckId(deck),
        faction=faction,
        summoner=summoner,
        gate=gate,
        units=(scout, brute, archer),
        starting_units=(scout, brute),
        composition=tuple(composition),
    )


_DECKS: Final[tuple[DeckDefinition, ...]] = (
    _build_deck("placeholder_alpha", "Alpha"),
    _build_deck("placeholder_beta", "Beta"),
)

REGISTRY: Final[dict[DeckId, DeckDefinition]] = {deck.deck_id: deck for deck in _DECKS}

CARD_INDEX: Final[dict[CardId, CardDefinition]] = {
    card.card_id: card for deck in _DECKS for card in (deck.summoner, deck.gate, *deck.units)
}


def get_deck(deck_id: DeckId) -> DeckDefinition:
    try:
        return REGISTRY[deck_id]
    except KeyError as exc:
        raise KeyError(f"unknown deck: {deck_id!r}") from exc


def get_card(card_id: CardId) -> CardDefinition:
    try:
        return CARD_INDEX[card_id]
    except KeyError as exc:
        raise KeyError(f"unknown card: {card_id!r}") from exc


def known_decks() -> tuple[DeckId, ...]:
    return tuple(sorted(REGISTRY))
