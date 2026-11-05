"""Card and deck data.

Names and starting layouts are transcribed from the physical cards (see
`docs/STARTING_LAYOUTS.md`). **Stats are still placeholders**: exact strength, life and
cost values are not encoded yet, so every number below is provisional and marked
`TODO(data)`. Abilities do not exist at all until the effect DSL lands in M3.

Rule: no official card text or artwork lives in this repository. Real cards will be
encoded as data — stats plus a short mechanical paraphrase — never as copied text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from sw_engine.ids import CardId, DeckId
from sw_engine.state import AttackKind, Square, UnitKind

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
class StartingLayout:
    """Where a faction's four setup cards go, in **own-side** coordinates.

    Column 0-5 left to right as printed on the card back; row 0 is the owner's back row.
    The engine mirrors this for the second player (x -> 5-x, y -> 7-y).
    """

    summoner: tuple[CardDefinition, Square]
    gate: tuple[CardDefinition, Square]
    units: tuple[tuple[CardDefinition, Square], ...]


@dataclass(frozen=True, slots=True)
class DeckDefinition:
    deck_id: DeckId
    faction: str
    layout: StartingLayout
    units: tuple[CardDefinition, ...]
    composition: tuple[CardId, ...]


def _card(
    faction_slug: str,
    slug: str,
    name: str,
    *,
    kind: UnitKind = UnitKind.UNIT,
    attack: AttackKind = AttackKind.MELEE,
    cost: int,
    strength: int,
    life: int,
) -> CardDefinition:
    return CardDefinition(
        card_id=CardId(f"{faction_slug}-{slug}"),
        name=name,
        kind=kind,
        attack=attack,
        cost=cost,
        strength=strength,
        life=life,
    )


def _build_deck(
    slug: str,
    faction: str,
    *,
    summoner: str,
    units: tuple[tuple[str, str, AttackKind, int, int, int], ...],
    layout: tuple[tuple[int, int], tuple[int, int], tuple[tuple[int, int], ...]],
) -> DeckDefinition:
    """Build one faction deck from names, placeholder stats and a setup layout."""
    summoner_card = _card(
        slug, "summoner", summoner, kind=UnitKind.SUMMONER, cost=0, strength=2, life=12
    )
    gate_card = _card(
        slug,
        "gate",
        f"{faction} Gate",
        kind=UnitKind.GATE,
        attack=AttackKind.NONE,
        cost=0,
        strength=0,
        life=GATE_LIFE,
    )
    unit_cards = tuple(
        _card(slug, unit_slug, name, attack=attack, cost=cost, strength=strength, life=life)
        for unit_slug, name, attack, cost, strength, life in units
    )

    summoner_square, gate_square, unit_squares = layout
    starting = StartingLayout(
        summoner=(summoner_card, Square(*summoner_square)),
        gate=(gate_card, Square(*gate_square)),
        units=tuple(
            (card, Square(*square)) for card, square in zip(unit_cards, unit_squares, strict=True)
        ),
    )

    composition: list[CardId] = []
    for card in unit_cards:
        composition.extend([card.card_id] * 15)
    composition.extend([gate_card.card_id] * 4)

    return DeckDefinition(
        deck_id=DeckId(slug),
        faction=faction,
        layout=starting,
        units=unit_cards,
        composition=tuple(composition),
    )


# Layouts confirmed by the owner against the physical summoner cards
# (docs/STARTING_LAYOUTS.md). Stats are TODO(data).
_DECKS: Final[tuple[DeckDefinition, ...]] = (
    _build_deck(
        "cave_goblins",
        "Cave Goblins",
        summoner="Sneeks",
        units=(
            ("slinger", "Horde Slinger", AttackKind.RANGED, 1, 1, 1),
            ("beast_rider", "Beast Rider", AttackKind.MELEE, 2, 3, 3),
        ),
        layout=((5, 0), (4, 1), ((5, 1), (3, 3))),
    ),
    _build_deck(
        "shadow_elves",
        "Shadow Elves",
        summoner="Taculla",
        units=(
            ("mind_witch", "Mind Witch", AttackKind.RANGED, 1, 2, 2),
            ("deceiver", "Deceiver", AttackKind.MELEE, 3, 4, 3),
        ),
        layout=((3, 0), (4, 1), ((3, 1), (5, 3))),
    ),
    _build_deck(
        "savanna_elves",
        "Savanna Elves",
        summoner="Abua Shi",
        units=(
            ("lioness", "Lioness", AttackKind.MELEE, 2, 3, 4),
            ("border_archer", "Border Archer", AttackKind.RANGED, 2, 2, 2),
        ),
        layout=((4, 0), (4, 1), ((3, 0), (3, 3))),
    ),
    _build_deck(
        "vanguards",
        "Vanguards",
        summoner="Sera",
        units=(
            ("temple_priest", "Temple Priest", AttackKind.MELEE, 2, 2, 2),
            ("citadel_knight", "Citadel Knight", AttackKind.MELEE, 3, 5, 4),
        ),
        layout=((4, 0), (4, 2), ((5, 2), (3, 3))),
    ),
    _build_deck(
        "fallen_kingdom",
        "Fallen Kingdom",
        summoner="Ret-Talus",
        units=(
            ("archer", "Undead Archer", AttackKind.RANGED, 2, 2, 2),
            ("carrier", "Undead Carrier", AttackKind.MELEE, 1, 3, 2),
        ),
        layout=((4, 0), (4, 2), ((3, 1), (3, 2))),
    ),
    _build_deck(
        "polar_dwarves",
        "Polar Dwarves",
        summoner="Svara",
        units=(
            ("ice_golem", "Ice Golem", AttackKind.MELEE, 2, 2, 5),
            ("frost_mage", "Frost Mage", AttackKind.RANGED, 1, 1, 4),
        ),
        layout=((4, 0), (4, 2), ((3, 1), (3, 2))),
    ),
)

REGISTRY: Final[dict[DeckId, DeckDefinition]] = {deck.deck_id: deck for deck in _DECKS}

CARD_INDEX: Final[dict[CardId, CardDefinition]] = {
    card.card_id: card
    for deck in _DECKS
    for card in (
        deck.layout.summoner[0],
        deck.layout.gate[0],
        *(card for card, _ in deck.layout.units),
    )
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
