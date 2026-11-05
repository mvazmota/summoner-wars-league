"""Rules engine entry points.

Contract (see AGENTS.md): these functions are pure. `step` never mutates its input, and
every decision an agent makes flows through `legal_actions` / `step`. The engine imports
nothing from `agents` or `league`, and performs no I/O.

Randomness lives in the engine, not in the caller: dice are rolled from
`(seed, rng_counter)`, so a game replays identically from its seed and action log.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from dataclasses import replace
from enum import Enum, auto
from typing import Final

from sw_cards import CardDefinition, get_card, get_deck
from sw_engine.actions import (
    Action,
    AttackUnit,
    BuildStructure,
    CommandAlly,
    DiscardForMagic,
    EndPhase,
    ForceUnit,
    MimicAbility,
    MoveUnit,
    PlayEvent,
    SlySwap,
    SummonUnit,
)
from sw_engine.dice import hits, roll
from sw_engine.ids import PLAYER_A, PLAYER_B, CardId, DeckId, PlayerId, UnitId, opponent
from sw_engine.observation import Observation, VisiblePlayer, visible_unit
from sw_engine.state import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    HAND_SIZE,
    MAGIC_MAX,
    MAX_UNITS_PER_PHASE,
    AttackKind,
    GameState,
    Phase,
    PlayerState,
    Square,
    UnitKind,
    UnitState,
)

# Rulebook p.5: setup draws 5; p.9: draw back up to 5 at end of turn.
INITIAL_HAND_SIZE = HAND_SIZE

# Rulebook p.5: the first player starts on magic 2, the other on magic 3.
STARTING_MAGIC_FIRST = 2
STARTING_MAGIC_SECOND = 3

# Rulebook p.8: ranged units reach 3 clear straight spaces.
RANGED_RANGE = 3

# Rulebook p.7: a unit moves 1 or 2 spaces per Move Phase.
MAX_MOVE_DISTANCE = 2
CHARGE_DISTANCE = 4  # Beast Rider: may move 1 to 4 clear straight spaces instead
FAR_SHOT_RANGE = 4  # Wind Archer: may attack 4 clear straight spaces away
MAX_BOOSTS = 5  # Blarf: +1 strength per boost, never more than +5


class Outcome(Enum):
    WIN_A = auto()
    WIN_B = auto()
    DRAW = auto()


class RulesError(Exception):
    """Raised when an action is not legal in the given state.

    A plain Exception on purpose: a frozen dataclass cannot be raised, because Python
    assigns `__traceback__` on the instance.
    """


def derive_rng(seed: int, counter: int) -> random.Random:
    """Deterministic RNG for one step.

    `random.Random` only accepts None/int/float/str/bytes as seeds, and Python's
    string/bytes hashing is salted per process, so a stable 64-bit seed is derived with
    blake2b rather than relying on `hash()`, tuples or the clock.
    """
    payload = f"{seed}:{counter}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return random.Random(int.from_bytes(digest, "big"))


# --------------------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------------------


def _player_unit(
    card: CardDefinition, owner: PlayerId, unit_id: UnitId, position: Square
) -> UnitState:
    return UnitState(
        unit_id=unit_id,
        owner=owner,
        card=card.card_id,
        kind=card.kind,
        attack=card.attack,
        position=position,
        strength=card.strength,
        life=card.life,
    )


def _mirror(square: Square) -> Square:
    """Rotate a square 180 degrees: the second player's side is the board's other half."""
    return Square(BOARD_WIDTH - 1 - square.x, BOARD_HEIGHT - 1 - square.y)


def _place(square: Square, player: PlayerId) -> Square:
    return square if player == PLAYER_A else _mirror(square)


def _build_player(
    deck_id: DeckId, player: PlayerId, starting_magic: int, rng: random.Random
) -> tuple[PlayerState, tuple[UnitState, ...]]:
    """Build one seat: shuffle the deck, draw a hand, and place the setup cards.

    Setup positions come from `sw_cards` (transcribed from the card backs) and are
    mirrored for player B. Card *stats* are still placeholders — see docs/CARD_STATUS.md.
    """
    definition = get_deck(deck_id)
    cards: list[CardId] = list(definition.composition)
    rng.shuffle(cards)

    layout = definition.layout
    summoner_card, summoner_square = layout.summoner
    gate_card, gate_square = layout.gate

    starting: list[UnitState] = [
        _player_unit(summoner_card, player, UnitId(1), _place(summoner_square, player)),
        _player_unit(gate_card, player, UnitId(2), _place(gate_square, player)),
    ]
    for index, (card, square) in enumerate(layout.units):
        starting.append(_player_unit(card, player, UnitId(3 + index), _place(square, player)))

    hand = tuple(cards[:INITIAL_HAND_SIZE])
    remaining = tuple(cards[INITIAL_HAND_SIZE:])
    player_state = PlayerState(
        player=player,
        summoner_id=UnitId(1),
        magic=starting_magic,
        deck=remaining,
        hand=hand,
    )
    return player_state, tuple(starting)


def initial_state(deck_a: DeckId, deck_b: DeckId, seed: int) -> GameState:
    """Create a fresh game.

    Rulebook p.5: the first player is determined at random and starts on magic 2 while
    the opponent starts on magic 3, compensating the second player for moving second.
    """
    chooser = derive_rng(seed, 0)
    first: PlayerId = PLAYER_A if chooser.random() < 0.5 else PLAYER_B
    second = opponent(first)
    magic_by_player = {first: STARTING_MAGIC_FIRST, second: STARTING_MAGIC_SECOND}

    player_a, units_a = _build_player(
        deck_a, PLAYER_A, magic_by_player[PLAYER_A], derive_rng(seed, 1000 + int(PLAYER_A))
    )
    player_b, units_b = _build_player(
        deck_b, PLAYER_B, magic_by_player[PLAYER_B], derive_rng(seed, 1000 + int(PLAYER_B))
    )

    # Renumber player B's units so ids stay unique across the game.
    offset = len(units_a)
    units_b = tuple(replace(unit, unit_id=UnitId(int(unit.unit_id) + offset)) for unit in units_b)
    player_b = replace(player_b, summoner_id=UnitId(int(player_b.summoner_id) + offset))

    return GameState(
        turn=1,
        active=first,
        phase=Phase.SUMMON,
        players=(player_a, player_b),
        units=units_a + units_b,
        seed=seed,
    )


# --------------------------------------------------------------------------------------
# Event effects
#
# Card ids are the key, because the effect belongs to the printed card, not to a class of
# cards. A card with no handler here is simply not playable yet, which keeps unimplemented
# effects out of `legal_actions` instead of silently doing nothing.
# --------------------------------------------------------------------------------------

PILE_ON = CardId("cave_goblins-pile_on")
UNRELENTING = CardId("cave_goblins-unrelenting")
ENRAGE_THE_HORDE = CardId("cave_goblins-enrage_the_horde")
SNEAK = CardId("cave_goblins-sneak")

# Breakers events
MIND_CONTROL = CardId("breakers-mind_control")
BLAST = CardId("breakers-blast")
HYPNOTIC_CALL = CardId("breakers-hypnotic_call")
PERPLEXING_TEMPEST = CardId("breakers-perplexing_tempest")


def _active_cards(state: GameState, player: PlayerId) -> tuple[CardId, ...]:
    return state.player(player).active_events


def _zero_cost_units(state: GameState, player: PlayerId) -> tuple[UnitState, ...]:
    return tuple(
        unit
        for unit in state.units_of(player)
        if unit.kind is UnitKind.UNIT and get_card(unit.card).cost == 0
    )


def _event_pile_on(state: GameState, player: PlayerId, targets: tuple[UnitId, ...]) -> GameState:
    """Pile On is an ACTIVE event: nothing happens now, the effect is read during attacks."""
    return state


def _event_unrelenting(
    state: GameState, player: PlayerId, targets: tuple[UnitId, ...]
) -> GameState:
    """Unrelenting is ACTIVE; its effect is applied when a common would be destroyed."""
    return state


def _event_enrage_the_horde(
    state: GameState, player: PlayerId, targets: tuple[UnitId, ...]
) -> GameState:
    """Every friendly 0 cost unit may resolve an extra attack."""
    granted = tuple(unit.unit_id for unit in _zero_cost_units(state, player))
    if not granted:
        raise RulesError("no friendly 0 cost units to enrage")
    return replace(state, extra_attackers=tuple(dict.fromkeys((*state.extra_attackers, *granted))))


def _event_sneak(state: GameState, player: PlayerId, targets: tuple[UnitId, ...]) -> GameState:
    """Force each targeted 0 cost unit 1 space away from your own summoner."""
    if not targets:
        raise RulesError("Sneak needs at least one target")
    allowed = {unit.unit_id for unit in _zero_cost_units(state, player)}
    summoner = state.summoner(player)
    units = list(state.units)
    for unit_id in targets:
        if unit_id not in allowed:
            raise RulesError(f"{unit_id!r} is not a friendly 0 cost unit")
        index = next(i for i, u in enumerate(units) if u.unit_id == unit_id)
        unit = units[index]
        step_x = (unit.position.x > summoner.position.x) - (unit.position.x < summoner.position.x)
        step_y = (unit.position.y > summoner.position.y) - (unit.position.y < summoner.position.y)
        candidate = Square(unit.position.x + step_x, unit.position.y + step_y)
        if state.is_empty(candidate) and candidate.is_on_board():
            units[index] = replace(unit, position=candidate)
    return replace(state, units=tuple(units))


def _event_perplexing_tempest(
    state: GameState, player: PlayerId, targets: tuple[UnitId, ...]
) -> GameState:
    """ACTIVE: movement is already reduced in `_movement_profile` while this is in play."""
    return state


def _event_hypnotic_call(
    state: GameState, player: PlayerId, targets: tuple[UnitId, ...]
) -> GameState:
    """Force the target one space toward your summoner, and mark it for the summoner's +1."""
    if len(targets) != 1:
        raise RulesError("Hypnotic Call needs exactly one target")
    target = state.unit(targets[0])
    if target.owner == player or target.kind is not UnitKind.UNIT:
        raise RulesError("Hypnotic Call targets an enemy unit")
    summoner = state.summoner(player)
    step_x = (summoner.position.x > target.position.x) - (summoner.position.x < target.position.x)
    step_y = (summoner.position.y > target.position.y) - (summoner.position.y < target.position.y)
    squares = _force_steps(state, target, step_x, step_y, 1, through=False)
    if squares:
        units = tuple(
            replace(u, position=squares[0]) if u.unit_id == target.unit_id else u
            for u in state.units
        )
        state = replace(state, units=units)
    seat = state.player(player)
    return _with_player(state, replace(seat, hypnotic_target=target.unit_id))


def _event_blast(state: GameState, player: PlayerId, targets: tuple[UnitId, ...]) -> GameState:
    """Push the target up to 3 spaces away from your summoner, damaging everything it passes."""
    if len(targets) != 1:
        raise RulesError("Blast needs exactly one target")
    target = state.unit(targets[0])
    summoner = state.summoner(player)
    step_x = (target.position.x > summoner.position.x) - (target.position.x < summoner.position.x)
    step_y = (target.position.y > summoner.position.y) - (target.position.y < summoner.position.y)
    if step_x != 0 and step_y != 0:
        raise RulesError("Blast needs a straight line from your summoner")
    if not _path_is_clear(state, summoner.position, target.position):
        raise RulesError("Blast needs a clear line to the target")
    steps = _force_steps(state, target, step_x, step_y, 3, through=True)
    if not steps:
        raise RulesError("Blast cannot move that target")

    passed = [state.occupant(square) for square in steps]
    destination = steps[-1]
    units = tuple(
        replace(u, position=destination) if u.unit_id == target.unit_id else u for u in state.units
    )
    state = replace(state, units=units)
    for victim in [target, *[u for u in passed if u is not None]]:
        current = next((u for u in state.units if u.unit_id == victim.unit_id), None)
        if current is not None:
            state = _apply_damage(state, current, 1)
    return state


def _event_mind_control(
    state: GameState, player: PlayerId, targets: tuple[UnitId, ...]
) -> GameState:
    """Take control of enemy commons and champions near your summoner until end of turn."""
    summoner = state.summoner(player)
    chosen = [state.unit(unit_id) for unit_id in targets]
    for unit in chosen:
        if unit.owner == player:
            raise RulesError("Mind Control only targets enemy units")
        if get_card(unit.card).card_class not in {"Common", "Champion"}:
            raise RulesError("Mind Control only targets commons and champions")
        if unit.position.distance_to(summoner.position) > 2:
            raise RulesError("Mind Control targets must be within 2 spaces of your summoner")
    units = tuple(
        replace(u, owner=player) if u.unit_id in {v.unit_id for v in chosen} else u
        for u in state.units
    )
    return replace(state, units=units, controlled=(*state.controlled, *(u.unit_id for u in chosen)))


EFFECT_HANDLERS: Final[
    dict[CardId, Callable[[GameState, PlayerId, tuple[UnitId, ...]], GameState]]
] = {
    PILE_ON: _event_pile_on,
    UNRELENTING: _event_unrelenting,
    ENRAGE_THE_HORDE: _event_enrage_the_horde,
    SNEAK: _event_sneak,
    PERPLEXING_TEMPEST: _event_perplexing_tempest,
    HYPNOTIC_CALL: _event_hypnotic_call,
    BLAST: _event_blast,
    MIND_CONTROL: _event_mind_control,
}


def _event_targets(state: GameState, player: PlayerId, card_id: CardId) -> list[UnitState]:
    """Enemy units a targeted event may hit, for generating legal actions."""
    if card_id == BLAST:
        summoner = state.summoner(player)
        candidates = [
            unit
            for unit in state.units
            if unit.owner != player
            and unit.kind is UnitKind.UNIT
            and get_card(unit.card).card_class in {"Common", "Champion"}
        ]
        usable = []
        for unit in candidates:
            if unit.position.x != summoner.position.x and unit.position.y != summoner.position.y:
                continue
            if not _path_is_clear(state, summoner.position, unit.position):
                continue
            step_x = (unit.position.x > summoner.position.x) - (
                unit.position.x < summoner.position.x
            )
            step_y = (unit.position.y > summoner.position.y) - (
                unit.position.y < summoner.position.y
            )
            if not _force_steps(state, unit, step_x, step_y, 1, through=True):
                continue
            usable.append(unit)
        return usable
    if card_id == HYPNOTIC_CALL:
        return [
            unit
            for unit in state.units
            if unit.owner != player
            and unit.kind is UnitKind.UNIT
            and get_card(unit.card).card_class in {"Common", "Champion"}
        ]
    if card_id == MIND_CONTROL:
        summoner = state.summoner(player)
        return [
            unit
            for unit in state.units
            if unit.owner != player
            and unit.kind is UnitKind.UNIT
            and get_card(unit.card).card_class in {"Common", "Champion"}
            and unit.position.distance_to(summoner.position) <= 2
        ]
    return []


def _event_legal(state: GameState, player: PlayerId, card_id: CardId) -> bool:
    """A card can be played on its printed phase, if paid for and implemented (p.9)."""
    card = get_card(card_id)
    if card.kind is not UnitKind.EVENT:
        return False
    if card.card_id not in EFFECT_HANDLERS:
        return False
    if card.phase is not state.phase:
        return False
    player_state = state.player(player)
    if card.cost > player_state.magic:
        return False
    # Active events: one with the same name at a time (p.9).
    if card.ability_name and "ACTIVE" in card.ability_name.upper():
        names = {get_card(active).name for active in player_state.active_events}
        if card.name in names:
            return False
    return True


# --------------------------------------------------------------------------------------
# Legality helpers
# --------------------------------------------------------------------------------------


def _own_gates(state: GameState, player: PlayerId) -> tuple[UnitState, ...]:
    return tuple(u for u in state.units if u.owner == player and u.kind is UnitKind.GATE)


def _adjacent_squares(square: Square) -> list[Square]:
    return [
        Square(square.x + 1, square.y),
        Square(square.x - 1, square.y),
        Square(square.x, square.y + 1),
        Square(square.x, square.y - 1),
    ]


def _adjacent_empties(state: GameState, square: Square) -> list[Square]:
    return [c for c in _adjacent_squares(square) if state.is_empty(c)]


def _summon_squares(state: GameState, player: PlayerId) -> list[Square]:
    squares: list[Square] = []
    for gate in _own_gates(state, player):
        for square in _adjacent_empties(state, gate.position):
            if square not in squares:
                squares.append(square)
    return squares


def _back_rows(player: PlayerId) -> range:
    return range(0, 3) if player == PLAYER_A else range(BOARD_HEIGHT - 3, BOARD_HEIGHT)


def _build_squares(state: GameState, player: PlayerId) -> list[Square]:
    summoner = state.summoner(player)
    squares: list[Square] = []
    for y in _back_rows(player):
        for x in range(BOARD_WIDTH):
            square = Square(x, y)
            if state.is_empty(square):
                squares.append(square)
    for square in _adjacent_empties(state, summoner.position):
        if square not in squares:
            squares.append(square)
    return squares


def _path_is_clear(
    state: GameState, origin: Square, target: Square, *, through_cards: bool = False
) -> bool:
    """True when every space strictly between origin and target is empty.

    Returns False for anything that is not a straight horizontal or vertical line.
    """
    if origin.x != target.x and origin.y != target.y:
        return False
    step_x = (target.x > origin.x) - (target.x < origin.x)
    step_y = (target.y > origin.y) - (target.y < origin.y)
    x, y = origin.x + step_x, origin.y + step_y
    while (x, y) != (target.x, target.y):
        blocker = state.occupant(Square(x, y))
        if blocker is not None and not through_cards:
            return False
        x += step_x
        y += step_y
    return True


def _unit_has_ability(unit: UnitState, keyword: str) -> bool:
    """Abilities printed on the card plus anything Mimic copied onto this unit."""
    needle = keyword.lower()
    if needle in unit.extra_ability.lower():
        return True
    return _has_ability(unit.card, keyword)


def _has_ability(card_id: CardId, keyword: str) -> bool:
    """True when the printed ability text carries `keyword` (e.g. Charge, Relentless).

    Unknown cards return False: tests build synthetic units, and a missing definition must
    never crash the rules engine mid-game.
    """
    try:
        card = get_card(card_id)
    except KeyError:
        return False
    haystack = f"{card.ability_name or ''} {card.ability or ''}".lower()
    return keyword.lower() in haystack


def _card_class(card_id: CardId) -> str:
    """Card class, or "Unknown" for synthetic units built by tests."""
    try:
        return get_card(card_id).card_class
    except KeyError:
        return "Unknown"


def _movement_profile(state: GameState, unit: UnitState) -> tuple[int, bool]:
    """How far a unit may move and whether it passes through cards.

    Climb and Flight both add a space and let the mover pass cards; Swift adds a space on
    top; Levitate lends Flight to friendly commons that start within 2 spaces of the carrier.
    """
    limit = MAX_MOVE_DISTANCE
    through_cards = False
    if _unit_has_ability(unit, "Climb") or _unit_has_ability(unit, "Flight"):
        limit += 1
        through_cards = True
    if _unit_has_ability(unit, "Swift"):
        limit += 1
    if PERPLEXING_TEMPEST in _active_cards(state, unit.owner):
        limit = max(1, limit - 1)

    if _card_class(unit.card) == "Common":
        for other in state.units:
            if other.owner != unit.owner or other.unit_id == unit.unit_id:
                continue
            if not _has_ability(other.card, "Levitate"):
                continue
            if other.position.distance_to(unit.position) <= 2:
                limit += 1
                through_cards = True
                break
    return limit, through_cards


def _can_move(state: GameState, unit: UnitState, to: Square, player: PlayerId) -> bool:
    if unit.owner != player or not unit.can_move():
        return False
    if _unit_has_ability(unit, "Immobile"):
        return False
    if unit.unit_id in state.moved or len(state.moved) >= MAX_UNITS_PER_PHASE:
        return False
    if not to.is_on_board() or not state.is_empty(to):
        return False
    distance = unit.position.distance_to(to)
    limit, through_cards = _movement_profile(state, unit)
    if _unit_has_ability(unit, "Charge"):
        limit = max(limit, CHARGE_DISTANCE)
    if distance < 1 or distance > limit:
        return False
    return _path_is_clear(state, unit.position, to, through_cards=through_cards)


def _can_attack(state: GameState, attacker: UnitState, target: UnitState, player: PlayerId) -> bool:
    if attacker.owner != player or not attacker.can_attack():
        return False
    # Relentless buys ONE extra attack and lets that unit sit outside the three-unit limit.
    # It is not an unlimited-attack engine: the count of this unit's attacks is the cap.
    relentless = _unit_has_ability(attacker, "Relentless")
    attacks_made = state.attacked.count(attacker.unit_id)
    limit = 2 if relentless else 1
    granted = attacker.unit_id in state.extra_attackers
    if granted:
        limit = max(limit, attacks_made + 1)
    if attacks_made >= limit:
        return False
    if len(set(state.attacked)) >= MAX_UNITS_PER_PHASE and not relentless and not granted:
        return False
    if target.owner == player:
        return False
    if attacker.attack is AttackKind.MELEE:
        return attacker.position.is_adjacent_to(target.position)
    distance = attacker.position.distance_to(target.position)
    reach = FAR_SHOT_RANGE if _unit_has_ability(attacker, "Far Shot") else RANGED_RANGE
    if distance < 1 or distance > reach:
        return False
    return _path_is_clear(state, attacker.position, target.position)


def _force_ranges(unit: UnitState) -> int:
    """How far a push reaches: 2 for Push, 3 for Greater Push."""
    if _unit_has_ability(unit, "Greater Push"):
        return 3
    if _unit_has_ability(unit, "Push"):
        return 2
    return 0


def _can_force(state: GameState, source: UnitState, target: UnitState, player: PlayerId) -> bool:
    if source.owner != player or source.unit_id in state.forced:
        return False
    reach = _force_ranges(source)
    if reach == 0:
        return False
    if target.owner == player:
        return False
    if target.kind is not UnitKind.UNIT:
        return False
    if get_card(target.card).card_class not in {"Common", "Champion"}:
        return False
    if _unit_has_ability(target, "Steadfast"):
        return False
    distance = source.position.distance_to(target.position)
    return 1 <= distance <= reach


def _force_directions(source: UnitState, target: UnitState) -> list[tuple[int, int]]:
    """Orthogonal directions that move the target away from the source."""
    delta_x = target.position.x - source.position.x
    delta_y = target.position.y - source.position.y
    directions: list[tuple[int, int]] = []
    if delta_x != 0:
        directions.append((1 if delta_x > 0 else -1, 0))
    if delta_y != 0:
        directions.append((0, 1 if delta_y > 0 else -1))
    return directions


def _force_steps(
    state: GameState, target: UnitState, dx: int, dy: int, spaces: int, *, through: bool
) -> list[Square]:
    """Squares the target would cross, stopping at the first illegal one."""
    squares: list[Square] = []
    for step in range(1, spaces + 1):
        square = Square(target.position.x + dx * step, target.position.y + dy * step)
        if not square.is_on_board():
            break
        occupant = state.occupant(square)
        if occupant is not None and not through:
            break
        squares.append(square)
    return squares


def legal_actions(state: GameState) -> tuple[Action, ...]:
    """Every action the active player may take in the current phase."""
    if is_terminal(state):
        return ()

    player = state.active
    player_state = state.active_player()
    actions: list[Action] = []

    if state.phase is Phase.SUMMON:
        summon_squares = _summon_squares(state, player)
        for card_id in player_state.hand:
            card = get_card(card_id)
            if card.kind is not UnitKind.UNIT or card.cost > player_state.magic:
                continue
            actions.extend(SummonUnit(card_id, square) for square in summon_squares)

    elif state.phase is Phase.MOVE:
        squares = [Square(x, y) for y in range(BOARD_HEIGHT) for x in range(BOARD_WIDTH)]
        for unit in state.units:
            if unit.owner != player or unit.unit_id in state.moved:
                continue
            actions.extend(
                MoveUnit(unit.unit_id, square)
                for square in squares
                if _can_move(state, unit, square, player)
            )

    elif state.phase is Phase.BUILD:
        build_squares = _build_squares(state, player)
        for card_id in player_state.hand:
            card = get_card(card_id)
            if card.kind not in (UnitKind.GATE, UnitKind.STRUCTURE):
                continue
            if card.cost > player_state.magic:
                continue
            actions.extend(BuildStructure(card_id, square) for square in build_squares)

    elif state.phase is Phase.ATTACK:
        for unit in state.units:
            made = state.attacked.count(unit.unit_id)
            cap = 2 if _unit_has_ability(unit, "Relentless") else 1
            if unit.unit_id in state.extra_attackers:
                cap = max(cap, made + 1)
            if unit.owner != player or made >= cap:
                continue
            actions.extend(
                AttackUnit(unit.unit_id, target.unit_id)
                for target in state.units
                if _can_attack(state, unit, target, player)
            )

    elif state.phase is Phase.MAGIC:
        actions.extend(DiscardForMagic(card_id) for card_id in player_state.hand)

    if state.phase is Phase.ATTACK:
        for unit in state.units:
            if unit.owner != player or unit.unit_id in state.forced:
                continue
            for target in state.units:
                if not _can_force(state, unit, target, player):
                    continue
                for dx, dy in _force_directions(unit, target):
                    if not _force_steps(state, target, dx, dy, 1, through=False):
                        continue  # pushing into a body or off the board is not an action
                    actions.append(ForceUnit(unit.unit_id, target.unit_id, dx, dy))
        for unit in state.units:
            if unit.owner != player or not _unit_has_ability(unit, "Telepathic Command"):
                continue
            if unit.unit_id not in state.attacked:
                continue
            actions.extend(
                CommandAlly(unit.unit_id, ally.unit_id)
                for ally in state.units_of(player)
                if ally.kind is UnitKind.UNIT
                and get_card(ally.card).card_class == "Common"
                and ally.position.distance_to(unit.position) <= 3
                and ally.unit_id not in state.extra_attackers
            )

    if state.phase is Phase.MOVE and not state.moved:
        for unit in state.units_of(player):
            if not _unit_has_ability(unit, "Mimic"):
                continue
            actions.extend(
                MimicAbility(unit.unit_id, target.unit_id)
                for target in state.units
                if target.unit_id != unit.unit_id
                and target.kind is UnitKind.UNIT
                and get_card(target.card).card_class == "Common"
                and unit.position.distance_to(target.position) <= 3
            )

    if state.phase is Phase.ATTACK and not state.sly_used:
        summoner = state.summoner(player)
        if _unit_has_ability(summoner, "Sly"):
            actions.extend(
                SlySwap(unit.unit_id)
                for unit in _zero_cost_units(state, player)
                if unit.unit_id != summoner.unit_id
            )

    # Events are legal on the phase printed on the card, so this check spans phases.
    for card_id in player_state.hand:
        if not _event_legal(state, player, card_id):
            continue
        card = get_card(card_id)
        if card.card_id == SNEAK:
            candidates = _zero_cost_units(state, player)
            actions.extend(PlayEvent(card_id, (unit.unit_id,)) for unit in candidates)
            if len(candidates) > 1:
                actions.append(PlayEvent(card_id, tuple(u.unit_id for u in candidates)))
        elif card.card_id in (BLAST, HYPNOTIC_CALL):
            actions.extend(
                PlayEvent(card_id, (unit.unit_id,))
                for unit in _event_targets(state, player, card_id)
            )
        elif card.card_id == MIND_CONTROL:
            targets = _event_targets(state, player, card_id)
            actions.extend(PlayEvent(card_id, (unit.unit_id,)) for unit in targets)
            if len(targets) > 1:
                actions.append(PlayEvent(card_id, tuple(u.unit_id for u in targets)))
        else:
            actions.append(PlayEvent(card_id))

    actions.append(EndPhase())
    return tuple(actions)


# --------------------------------------------------------------------------------------
# Transitions
# --------------------------------------------------------------------------------------


def _next_unit_id(state: GameState) -> UnitId:
    highest = max((int(unit.unit_id) for unit in state.units), default=0)
    return UnitId(highest + 1)


def _with_player(state: GameState, player_state: PlayerState) -> GameState:
    players = tuple(player_state if p.player == player_state.player else p for p in state.players)
    pair: tuple[PlayerState, PlayerState] = (players[0], players[1])
    return replace(state, players=pair)


def _spend_magic(player_state: PlayerState, cost: int) -> PlayerState:
    if cost > player_state.magic:
        raise RulesError(f"not enough magic: {cost} > {player_state.magic}")
    return replace(player_state, magic=player_state.magic - cost)


def _gain_magic(player_state: PlayerState, amount: int) -> PlayerState:
    return replace(player_state, magic=min(MAGIC_MAX, player_state.magic + amount))


def _remove_from_hand(player_state: PlayerState, card_id: CardId) -> PlayerState:
    if card_id not in player_state.hand:
        raise RulesError(f"card {card_id!r} is not in hand")
    hand = list(player_state.hand)
    hand.remove(card_id)
    return replace(player_state, hand=tuple(hand))


def _summon(state: GameState, action: SummonUnit) -> GameState:
    player_state = state.active_player()
    card = get_card(action.card)
    if action.card not in player_state.hand:
        raise RulesError("summoned card is not in hand")
    if card.kind is not UnitKind.UNIT:
        raise RulesError("only units can be summoned")
    if action.position not in _summon_squares(state, state.active):
        raise RulesError("summon square must be empty and adjacent to a gate you control")

    player_state = _spend_magic(player_state, card.cost)
    player_state = _remove_from_hand(player_state, action.card)
    unit = UnitState(
        unit_id=_next_unit_id(state),
        owner=state.active,
        card=card.card_id,
        kind=UnitKind.UNIT,
        attack=card.attack,
        position=action.position,
        strength=card.strength,
        life=card.life,
    )
    return _with_player(replace(state, units=(*state.units, unit)), player_state)


def _build(state: GameState, action: BuildStructure) -> GameState:
    player_state = state.active_player()
    card = get_card(action.card)
    if action.card not in player_state.hand:
        raise RulesError("built card is not in hand")
    if card.kind not in (UnitKind.GATE, UnitKind.STRUCTURE):
        raise RulesError("only gates and structures can be built")
    if action.position not in _build_squares(state, state.active):
        raise RulesError("build square must be empty and in your back 3 rows or by your summoner")

    player_state = _spend_magic(player_state, card.cost)
    player_state = _remove_from_hand(player_state, action.card)
    structure = UnitState(
        unit_id=_next_unit_id(state),
        owner=state.active,
        card=card.card_id,
        kind=card.kind,
        attack=AttackKind.NONE,
        position=action.position,
        strength=0,
        life=card.life,
    )
    return _with_player(replace(state, units=(*state.units, structure)), player_state)


def _move(state: GameState, action: MoveUnit) -> GameState:
    unit = state.unit(action.unit_id)
    if not _can_move(state, unit, action.to, state.active):
        raise RulesError(f"{action.unit_id!r} cannot move to {action.to!r}")
    origin = unit.position
    moved_unit = replace(unit, position=action.to)
    units = tuple(moved_unit if u.unit_id == unit.unit_id else u for u in state.units)
    state = replace(state, units=units, moved=(*state.moved, unit.unit_id))
    state = _apply_engage(state, unit, origin, action.to)
    return _apply_cling(state, unit, origin, action.to)


def _apply_cling(
    state: GameState, mover: UnitState, origin: Square, destination: Square
) -> GameState:
    """Horde Clinger follows a friendly unit that started its move next to it.

    The card says "you may"; the engine moves it whenever a legal square exists, because
    optional triggers need an action of their own and the action space is not there yet.
    """
    clingers = [
        unit
        for unit in state.units
        if unit.owner == mover.owner
        and unit.unit_id != mover.unit_id
        and _has_ability(unit.card, "Cling")
        and unit.position.is_adjacent_to(origin)
    ]
    if not clingers:
        return state

    occupied = {unit.position for unit in state.units}
    units = list(state.units)
    for clinger in clingers:
        for square in _adjacent_squares(destination):
            if square.is_on_board() and square not in occupied:
                occupied.add(square)
                index = next(i for i, u in enumerate(units) if u.unit_id == clinger.unit_id)
                units[index] = replace(clinger, position=square)
                break
    return replace(state, units=tuple(units))


def _apply_damage(state: GameState, target: UnitState, amount: int) -> GameState:
    """Damage a card, destroying it at 0 life. Cards under it are discarded (p.8)."""
    if amount <= 0:
        return state
    damaged = replace(target, damage=target.damage + amount)
    if damaged.is_alive():
        units = tuple(damaged if u.unit_id == target.unit_id else u for u in state.units)
        return replace(state, units=units)
    if UNRELENTING in _active_cards(state, target.owner) and (
        get_card(target.card).card_class == "Common"
    ):
        # A friendly common that would be destroyed returns to hand instead.
        player_state = state.player(target.owner)
        returned = replace(
            player_state,
            hand=(*player_state.hand, target.card),
        )
        without = replace(state, units=tuple(u for u in state.units if u.unit_id != target.unit_id))
        return _with_player(without, returned)

    if damaged.kind is UnitKind.SUMMONER:
        # A summoner never leaves the battlefield: its death is a loss condition, and
        # removing it would erase the identity the terminal check needs.
        dead = replace(target, damage=target.life)
        units = tuple(dead if u.unit_id == target.unit_id else u for u in state.units)
        return replace(state, units=units)
    return replace(state, units=tuple(u for u in state.units if u.unit_id != target.unit_id))


def _stupefy_penalty(state: GameState, attacker: UnitState) -> bool:
    """A Deceiver next to the attacker makes every roll count for one less damage."""
    return any(
        unit.owner != attacker.owner
        and unit.kind is UnitKind.UNIT
        and _unit_has_ability(unit, "Stupefy")
        and unit.position.is_adjacent_to(attacker.position)
        for unit in state.units
    )


def _apply_engage(
    state: GameState, mover: UnitState, origin: Square, destination: Square
) -> GameState:
    """Engage: leaving a Deceiver's side costs 1 damage."""
    hit = any(
        unit.owner != mover.owner
        and unit.kind is UnitKind.UNIT
        and _unit_has_ability(unit, "Engage")
        and unit.position.is_adjacent_to(origin)
        and not unit.position.is_adjacent_to(destination)
        for unit in state.units
    )
    if not hit:
        return state
    current = next((u for u in state.units if u.unit_id == mover.unit_id), None)
    if current is None:
        return state
    return _apply_damage(state, current, 1)


def _attack(state: GameState, action: AttackUnit) -> GameState:
    attacker = state.unit(action.attacker)
    target = state.unit(action.target)
    if not _can_attack(state, attacker, target, state.active):
        raise RulesError(f"{action.attacker!r} cannot attack {action.target!r}")

    rng = derive_rng(state.seed, state.rng_counter + 1)
    rolls = roll(_effective_strength(state, attacker, target), rng)
    damage = hits(rolls, attacker.attack)
    if damage > 0 and _stupefy_penalty(state, attacker):
        damage = max(0, damage - 1)

    if (
        damage > 0
        and _unit_has_ability(attacker, "Mind Capture")
        and target.kind is UnitKind.UNIT
        and target.damage + damage >= target.life
        and get_card(target.card).card_class in {"Common", "Champion"}
    ):
        # "You may instead ignore that damage and take control of the target." Taking it is
        # almost always right, so the engine takes it and says so in docs/MECHANICS.md.
        captured = tuple(
            replace(unit, owner=attacker.owner) if unit.unit_id == target.unit_id else unit
            for unit in state.units
        )
        return replace(
            state,
            units=captured,
            rng_counter=state.rng_counter + 1,
            attacked=(*state.attacked, attacker.unit_id),
            attacked_any=True,
            extra_attackers=tuple(u for u in state.extra_attackers if u != attacker.unit_id),
            controlled=(*state.controlled, target.unit_id),
        )

    after = _apply_damage(state, target, damage)

    # Rulebook p.8: gain 1 magic whenever a card you control destroys an enemy card.
    was_destroyed = damage > 0 and all(u.unit_id != target.unit_id for u in after.units)
    if was_destroyed:
        after = _with_player(after, _gain_magic(after.player(state.active), 1))
        after = replace(after, destroyed_by=(*after.destroyed_by, attacker.unit_id))

    return replace(
        after,
        rng_counter=state.rng_counter + 1,
        attacked=(*state.attacked, attacker.unit_id),
        attacked_any=True,
        extra_attackers=tuple(u for u in state.extra_attackers if u != attacker.unit_id),
    )


def _discard_for_magic(state: GameState, action: DiscardForMagic) -> GameState:
    player_state = state.active_player()
    if action.card not in player_state.hand:
        raise RulesError("discarded card is not in hand")
    # Remove exactly one copy: hands legitimately hold duplicates, and a value filter
    # would silently discard every copy of that card.
    player_state = replace(
        player_state,
        discard=(*player_state.discard, action.card),
    )
    player_state = _remove_from_hand(player_state, action.card)
    player_state = _gain_magic(player_state, 1)
    return _with_player(state, player_state)


def _play_event(state: GameState, action: PlayEvent) -> GameState:
    """Pay the cost, resolve the effect, then discard or park it in the active area (p.9)."""
    player = state.active
    if not _event_legal(state, player, action.card):
        raise RulesError(f"{action.card!r} cannot be played right now")
    card = get_card(action.card)
    handler = EFFECT_HANDLERS[card.card_id]

    player_state = _spend_magic(state.player(player), card.cost)
    player_state = _remove_from_hand(player_state, action.card)
    state = _with_player(state, player_state)

    state = handler(state, player, action.targets)

    player_state = state.player(player)
    if card.ability_name and "ACTIVE" in card.ability_name.upper():
        player_state = replace(
            player_state, active_events=(*player_state.active_events, card.card_id)
        )
    else:
        player_state = replace(player_state, discard=(*player_state.discard, card.card_id))
    return _with_player(state, player_state)


def _force(state: GameState, action: ForceUnit) -> GameState:
    """Move the target one space away, damaging anything it is pushed through."""
    source = state.unit(action.source)
    target = state.unit(action.target)
    if not _can_force(state, source, target, state.active):
        raise RulesError("that push is not legal")
    if (action.dx, action.dy) not in _force_directions(source, target):
        raise RulesError("force must push the target away from the source")

    squares = _force_steps(state, target, action.dx, action.dy, 1, through=False)
    if not squares:
        raise RulesError("nothing to push into: the target is blocked")
    destination = squares[0]
    units = tuple(
        replace(unit, position=destination) if unit.unit_id == target.unit_id else unit
        for unit in state.units
    )
    return replace(state, units=units, forced=(*state.forced, source.unit_id))


def _command_ally(state: GameState, action: CommandAlly) -> GameState:
    source = state.unit(action.source)
    target = state.unit(action.target)
    if source.unit_id not in state.attacked or not _unit_has_ability(source, "Telepathic Command"):
        raise RulesError("Telepathic Command needs this unit to have attacked")
    if target.owner != state.active or target.kind is not UnitKind.UNIT:
        raise RulesError("the commanded unit must be a friendly unit")
    if source.position.distance_to(target.position) > 3:
        raise RulesError("the commanded unit is out of range")
    return replace(state, extra_attackers=(*state.extra_attackers, target.unit_id))


def _mimic(state: GameState, action: MimicAbility) -> GameState:
    unit = state.unit(action.unit)
    target = state.unit(action.target)
    if unit.owner != state.active or not _unit_has_ability(unit, "Mimic"):
        raise RulesError("only a unit with Mimic can copy abilities")
    if unit.position.distance_to(target.position) > 3:
        raise RulesError("the copied unit is out of range")
    card = get_card(target.card)
    copied = f"{card.ability_name or ''} {card.ability or ''}".strip()
    units = tuple(
        replace(u, extra_ability=copied) if u.unit_id == unit.unit_id else u for u in state.units
    )
    return replace(state, units=units)


def _sly_swap(state: GameState, action: SlySwap) -> GameState:
    """Sneeks exchanges places with a friendly 0 cost unit, once per turn."""
    player = state.active
    summoner = state.summoner(player)
    target = state.unit(action.target)
    if state.sly_used or target.owner != player or target.unit_id == summoner.unit_id:
        raise RulesError("Sly is not available for that unit")
    if get_card(target.card).cost != 0:
        raise RulesError("Sly only swaps with a 0 cost unit")
    units = tuple(
        replace(unit, position=target.position)
        if unit.unit_id == summoner.unit_id
        else replace(unit, position=summoner.position)
        if unit.unit_id == target.unit_id
        else unit
        for unit in state.units
    )
    return replace(state, units=units, sly_used=True)


def _start_of_attack_phase(state: GameState) -> GameState:
    """Blarf's Blood Runes: spend 1 magic for a boost, or take 1 damage (p.12)."""
    for unit in tuple(state.units):
        if unit.owner != state.active or not _unit_has_ability(unit, "Blood Runes"):
            continue
        seat = state.player(unit.owner)
        if seat.magic >= 1 and unit.boosts < MAX_BOOSTS:
            state = _with_player(state, _spend_magic(seat, 1))
            units = tuple(
                replace(u, boosts=u.boosts + 1) if u.unit_id == unit.unit_id else u
                for u in state.units
            )
            state = replace(state, units=units)
        else:
            # The loop walks a snapshot: an earlier iteration may already have destroyed
            # this unit (or the damage may kill the one being processed), so look it up.
            current = next((u for u in state.units if u.unit_id == unit.unit_id), None)
            if current is not None:
                state = _apply_damage(state, current, 1)
    return state


def _end_of_attack_phase(state: GameState) -> GameState:
    """The Eater: if it destroyed nothing this turn, it eats a neighbour or itself (p.12)."""
    for unit in tuple(state.units):
        if unit.owner != state.active or not _unit_has_ability(unit, "Feed the Eater"):
            continue
        if unit.unit_id in state.destroyed_by:
            continue
        # Only battlefield units can be eaten: a summoner is never discarded, and gates are
        # structures rather than units.
        neighbours = [
            other
            for other in state.units
            if other.owner == unit.owner
            and other.unit_id != unit.unit_id
            and other.kind is UnitKind.UNIT
            and other.position.is_adjacent_to(unit.position)
        ]
        victim = min(neighbours, key=lambda u: int(u.unit_id), default=unit)
        state = replace(state, units=tuple(u for u in state.units if u.unit_id != victim.unit_id))
    return state


def _end_of_turn_triggers(state: GameState) -> GameState:
    """Smeg's Magic Junkie: pay 1 magic at the end of your turn or be discarded (p.12)."""
    for unit in tuple(state.units):
        if unit.owner != state.active or not _unit_has_ability(unit, "Magic Junkie"):
            continue
        seat = state.player(unit.owner)
        if seat.magic >= 1:
            state = _with_player(state, _spend_magic(seat, 1))
        else:
            state = replace(state, units=tuple(u for u in state.units if u.unit_id != unit.unit_id))
    return state


def _effective_strength(state: GameState, attacker: UnitState, target: UnitState) -> int:
    """Printed strength plus any bonuses the active events grant (Pile On's Gang Up)."""
    strength = attacker.strength + attacker.boosts
    if attacker.kind is UnitKind.SUMMONER:
        seat = state.player(attacker.owner)
        if seat.hypnotic_target == target.unit_id:
            strength += 1
    if PILE_ON in _active_cards(state, attacker.owner):
        strength += sum(
            1
            for unit in state.units
            if unit.owner == attacker.owner
            and unit.unit_id != attacker.unit_id
            and unit.position.is_adjacent_to(target.position)
        )
    return strength


def _draw_up_to_hand_size(player_state: PlayerState) -> PlayerState:
    """Rulebook p.9 draws back up to 5; p.11 forbids reshuffling an empty draw pile."""
    deficit = HAND_SIZE - len(player_state.hand)
    if deficit <= 0:
        return player_state
    drawn = player_state.deck[:deficit]
    return replace(
        player_state,
        hand=(*player_state.hand, *drawn),
        deck=player_state.deck[len(drawn) :],
    )


def _apply_cost_of_inaction(state: GameState) -> GameState:
    """Rulebook p.8: +1 damage to your own summoner if you attacked nothing this turn."""
    if state.attacked_any:
        return state
    return _apply_damage(state, state.summoner(state.active), 1)


_PHASE_ORDER = (Phase.SUMMON, Phase.MOVE, Phase.BUILD, Phase.ATTACK, Phase.MAGIC)


def _end_phase(state: GameState) -> GameState:
    if is_terminal(state):
        return state

    if state.phase is Phase.ATTACK:
        state = _end_of_attack_phase(state)
        state = _apply_cost_of_inaction(state)
        if is_terminal(state):
            return state

    if state.phase is Phase.MAGIC:
        # End of turn triggers resolve before the draw step.
        state = _end_of_turn_triggers(state)
        if is_terminal(state):
            return state
        # Draw step, then hand the turn over (rulebook p.9).
        state = _with_player(state, _draw_up_to_hand_size(state.player(state.active)))
        if is_terminal(state):
            return state
        if state.controlled:
            # Mind Control and Mind Capture borrow units "until the end of your turn".
            former = opponent(state.active)
            state = replace(
                state,
                units=tuple(
                    replace(unit, owner=former) if unit.unit_id in state.controlled else unit
                    for unit in state.units
                ),
            )
        state = replace(
            state,
            turn=state.turn + 1,
            active=opponent(state.active),
            phase=Phase.SUMMON,
            moved=(),
            attacked=(),
            attacked_any=False,
            extra_attackers=(),
            destroyed_by=(),
            sly_used=False,
            forced=(),
            controlled=(),
            units=tuple(replace(unit, extra_ability="") for unit in state.units),
        )
        incoming = state.player(state.active)
        if incoming.active_events:
            # "At the start of your next turn, discard all events in your active area" (p.9).
            state = _with_player(
                state,
                replace(
                    incoming,
                    active_events=(),
                    discard=(*incoming.discard, *incoming.active_events),
                ),
            )
        return state

    index = _PHASE_ORDER.index(state.phase)
    next_phase = _PHASE_ORDER[index + 1]
    state = replace(state, phase=next_phase)
    if next_phase is Phase.ATTACK:
        state = _start_of_attack_phase(state)
    return state


def step(state: GameState, action: Action) -> GameState:
    """Apply an action, returning a new state. Raises RulesError if illegal."""
    if action not in legal_actions(state):
        raise RulesError(f"illegal action {action!r} in state {state.state_hash()}")

    match action:
        case EndPhase():
            return _end_phase(state)
        case SummonUnit():
            return _summon(state, action)
        case BuildStructure():
            return _build(state, action)
        case MoveUnit():
            return _move(state, action)
        case AttackUnit():
            return _attack(state, action)
        case DiscardForMagic():
            return _discard_for_magic(state, action)
        case PlayEvent():
            return _play_event(state, action)
        case SlySwap():
            return _sly_swap(state, action)
        case ForceUnit():
            return _force(state, action)
        case CommandAlly():
            return _command_ally(state, action)
        case MimicAbility():
            return _mimic(state, action)
    raise RulesError(f"unhandled action type: {type(action).__name__}")


def is_terminal(state: GameState) -> bool:
    return not state.summoner(PLAYER_A).is_alive() or not state.summoner(PLAYER_B).is_alive()


def outcome(state: GameState) -> Outcome | None:
    """Result of a finished game, or None while it is still running."""
    a_alive = state.summoner(PLAYER_A).is_alive()
    b_alive = state.summoner(PLAYER_B).is_alive()
    if a_alive and b_alive:
        return None
    if a_alive:
        return Outcome.WIN_A
    if b_alive:
        return Outcome.WIN_B
    return Outcome.DRAW


def observation(state: GameState, viewer: PlayerId) -> Observation:
    """Project the state down to what `viewer` may legally see."""
    players: list[VisiblePlayer] = []
    for player_state in state.players:
        own = player_state.player == viewer
        players.append(
            VisiblePlayer(
                player=player_state.player,
                summoner=state.summoner(player_state.player),
                magic=player_state.magic,
                deck_size=len(player_state.deck),
                hand=player_state.hand if own else None,
                hand_size=len(player_state.hand),
                discard=player_state.discard,
            )
        )
    pair: tuple[VisiblePlayer, VisiblePlayer] = (players[0], players[1])
    return Observation(
        turn=state.turn,
        active=state.active,
        phase=state.phase,
        viewer=viewer,
        players=pair,
        units=tuple(visible_unit(unit) for unit in state.units),
    )


def adjudicate_by_life(state: GameState) -> PlayerId | None:
    """League tie-break for games that hit the turn cap: higher summoner life wins."""
    a = state.summoner(PLAYER_A).remaining_life()
    b = state.summoner(PLAYER_B).remaining_life()
    if a == b:
        return None
    return PLAYER_A if a > b else PLAYER_B


__all__ = [
    "INITIAL_HAND_SIZE",
    "MAX_MOVE_DISTANCE",
    "RANGED_RANGE",
    "STARTING_MAGIC_FIRST",
    "STARTING_MAGIC_SECOND",
    "Outcome",
    "RulesError",
    "adjudicate_by_life",
    "derive_rng",
    "initial_state",
    "is_terminal",
    "legal_actions",
    "observation",
    "outcome",
    "step",
]
