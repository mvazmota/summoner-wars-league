"""Card and deck data.

Names and starting layouts are transcribed from the physical cards (see
`docs/STARTING_LAYOUTS.md`). **Stats are still placeholders**: exact strength, life and
cost values are not encoded yet, so every number below is provisional and marked
`TODO(data)`. Abilities do not exist at all until the effect DSL lands in M3.

Rule: no official card text or artwork lives in this repository. Real cards will be
encoded as data — stats plus a short mechanical paraphrase — never as copied text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from sw_core import AttackKind, CardId, DeckId, Phase, Square, UnitKind

DECK_SIZE: Final[int] = 34
"""Cards in a faction deck, counting the summoner and the two starting units."""

GATE_LIFE: Final[int] = 10  # rulebook p.5: the starting gate has 10 life
GATE_LIFE_STANDARD: Final[int] = 5  # the three other gates have 5 life each
GATE_COST: Final[int] = 0  # gates are structures and cost no magic

# Everything that is dealt rather than placed during setup: 16 commons + 3 champions +
# 8 events + the 3 five-life gates. The summoner, the ten-life gate and the two starting
# units are on the board before anyone draws.
DRAW_PILE_SIZE: Final[int] = DECK_SIZE - 4

COMMON_COPIES: Final[int] = 4  # rulebook p.12: at most 4 of each common
CHAMPION_COPIES: Final[int] = 1
EVENT_COPIES: Final[int] = 2  # 3 standard + 1 epic, two copies each, is 8 event slots


@dataclass(frozen=True, slots=True)
class CardDefinition:
    card_id: CardId
    name: str
    kind: UnitKind
    attack: AttackKind
    cost: int
    strength: int
    life: int
    card_class: str = "Common"
    ability_name: str | None = None
    ability: str | None = None
    phase: Phase | None = None


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
    gates: tuple[CardDefinition, CardDefinition]
    events: tuple[CardDefinition, ...]
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


class VerifiedCard(TypedDict):
    """Shape of one entry in data/cards/<deck>.json."""

    id: str
    name: str
    card_class: str
    cost: int | None
    life: int | None
    attack: str
    strength: int | None
    ability: str | None
    ability_name: NotRequired[str]
    copies: NotRequired[int | None]
    phase: NotRequired[str | None]
    source: NotRequired[str]


CARDS_DIR: Final[Path] = Path(__file__).resolve().parents[2] / "data" / "cards"

_PHASE_BY_NAME: Final[dict[str, Phase]] = {
    "Summon Phase": Phase.SUMMON,
    "Move Phase": Phase.MOVE,
    "Build Phase": Phase.BUILD,
    "Attack Phase": Phase.ATTACK,
    "Magic Phase": Phase.MAGIC,
}

_ATTACK_BY_NAME: Final[dict[str, AttackKind]] = {
    "melee": AttackKind.MELEE,
    "ranged": AttackKind.RANGED,
    "none": AttackKind.NONE,
}


def load_verified_cards(deck_id: DeckId) -> dict[str, VerifiedCard]:
    """Read the hand-verified card data for a faction, keyed by card name.

    The JSON files in `data/cards/` are transcribed from the physical cards. Anything not
    present there is still a placeholder and must be marked as such in docs/CARD_STATUS.md.
    """
    path = CARDS_DIR / f"{deck_id}.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    cards: list[VerifiedCard] = payload.get("cards", [])
    return {entry["name"]: entry for entry in cards}


def _apply_verified(card: CardDefinition, verified: dict[str, VerifiedCard]) -> CardDefinition:
    entry = verified.get(card.name)
    if entry is None:
        return card
    # Events are cards in the deck but never stand on the battlefield, so their life and
    # strength are null; every other class must carry real numbers.
    life = entry["life"]
    strength = entry["strength"]
    if life is None or strength is None:
        return card
    cost = entry["cost"]
    return replace(
        card,
        cost=card.cost if cost is None else cost,
        life=life,
        strength=strength,
        attack=_ATTACK_BY_NAME[entry["attack"]],
        card_class=entry.get("card_class", "Common"),
        ability_name=entry.get("ability_name"),
        ability=entry.get("ability"),
    )


def _build_deck(
    slug: str,
    faction: str,
    *,
    summoner: str,
    units: tuple[tuple[str, str, AttackKind, int, int, int], ...],
    layout: tuple[tuple[int, int], tuple[int, int], tuple[tuple[int, int], ...]],
    starting: tuple[str, str],
) -> DeckDefinition:
    """Build one faction deck from names, placeholder stats and a setup layout."""
    verified = load_verified_cards(DeckId(slug))
    summoner_card = _apply_verified(
        _card(slug, "summoner", summoner, kind=UnitKind.SUMMONER, cost=0, strength=2, life=12),
        verified,
    )
    gate_card = _card(
        slug,
        "gate",
        f"{faction} Gate",
        kind=UnitKind.GATE,
        attack=AttackKind.NONE,
        cost=GATE_COST,
        strength=0,
        life=GATE_LIFE,
    )
    extra_gate_card = _card(
        slug,
        "gate_5",
        f"{faction} Gate",
        kind=UnitKind.GATE,
        attack=AttackKind.NONE,
        cost=GATE_COST,
        strength=0,
        life=GATE_LIFE_STANDARD,
    )
    unit_cards = tuple(
        _apply_verified(
            _card(slug, unit_slug, name, attack=attack, cost=cost, strength=strength, life=life),
            verified,
        )
        for unit_slug, name, attack, cost, strength, life in units
    )

    summoner_square, gate_square, unit_squares = layout

    # Only the two units printed on the summoner card back start on the board; the rest of
    # the faction's units go into the draw pile.
    by_slug = {entry[0]: card for entry, card in zip(units, unit_cards, strict=True)}
    starting_units = tuple(
        (by_slug[unit_slug], Square(*square))
        for unit_slug, square in zip(starting, unit_squares, strict=True)
    )
    starting_layout = StartingLayout(
        summoner=(summoner_card, Square(*summoner_square)),
        gate=(gate_card, Square(*gate_square)),
        units=starting_units,
    )

    event_cards = tuple(
        CardDefinition(
            card_id=CardId(entry["id"]),
            name=entry["name"],
            kind=UnitKind.EVENT,
            attack=AttackKind.NONE,
            cost=entry["cost"] or 0,
            strength=0,
            life=0,
            card_class=entry["card_class"],
            ability_name=entry.get("ability_name"),
            ability=entry.get("ability"),
            phase=_PHASE_BY_NAME.get(entry.get("phase") or ""),
        )
        for entry in verified.values()
        if entry["card_class"].endswith("Event")
    )

    # Real recipe: 4 copies of each common, 1 of each champion, 2 of each standard event
    # (epic events print on the summoner card and also come in 2), and 3 five-life gates.
    # Factions without verified data still use the even spread placeholder.
    composition: list[CardId] = [extra_gate_card.card_id] * 3
    commons = [c for c in unit_cards if c.card_class == "Common"]
    champions = [c for c in unit_cards if c.card_class == "Champion"]
    if commons and champions and event_cards:
        for card in commons:
            composition.extend([card.card_id] * COMMON_COPIES)
        for card in champions:
            composition.extend([card.card_id] * CHAMPION_COPIES)
        for card in event_cards:
            composition.extend([card.card_id] * EVENT_COPIES)
    else:
        unit_slots = DRAW_PILE_SIZE - len(composition)
        per_card, remainder = divmod(unit_slots, len(unit_cards))
        for index, card in enumerate(unit_cards):
            copies = per_card + (1 if index < remainder else 0)
            composition.extend([card.card_id] * copies)

    return DeckDefinition(
        deck_id=DeckId(slug),
        faction=faction,
        layout=starting_layout,
        units=unit_cards,
        gates=(gate_card, extra_gate_card),
        events=event_cards,
        composition=tuple(composition),
    )


# Layouts confirmed by the owner against the physical summoner cards
# (docs/STARTING_LAYOUTS.md). Stats are TODO(data).
_DECKS: Final[tuple[DeckDefinition, ...]] = (
    _build_deck(
        "cave_goblins",
        "Cave Goblins",
        starting=("slinger", "beast_rider"),
        summoner="Sneeks",
        units=(
            ("slinger", "Horde Slinger", AttackKind.RANGED, 1, 1, 1),
            ("beast_rider", "Beast Rider", AttackKind.MELEE, 2, 3, 3),
            ("horde_climber", "Horde Climber", AttackKind.MELEE, 0, 1, 3),
            ("horde_clinger", "Horde Clinger", AttackKind.MELEE, 2, 2, 2),
            # Champions: one copy each (rulebook p.12).
            ("blarf", "Blarf", AttackKind.MELEE, 0, 0, 6),
            ("smeg", "Smeg", AttackKind.RANGED, 0, 2, 4),
            ("the_eater", "The Eater", AttackKind.MELEE, 6, 5, 9),
        ),
        layout=((5, 0), (4, 1), ((5, 1), (3, 3))),
    ),
    _build_deck(
        "shadow_elves",
        "Shadow Elves",
        starting=("mind_witch", "deceiver"),
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
        starting=("lioness", "border_archer"),
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
        starting=("temple_priest", "citadel_knight"),
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
        starting=("archer", "carrier"),
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
        starting=("ice_golem", "frost_mage"),
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
        *deck.gates,
        *deck.events,
        *deck.units,
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
