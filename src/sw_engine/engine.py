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
from dataclasses import replace
from enum import Enum, auto

from sw_cards import CardDefinition, get_card, get_deck
from sw_engine.actions import (
    Action,
    AttackUnit,
    BuildStructure,
    DiscardForMagic,
    EndPhase,
    MoveUnit,
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
# Legality helpers
# --------------------------------------------------------------------------------------


def _own_gates(state: GameState, player: PlayerId) -> tuple[UnitState, ...]:
    return tuple(u for u in state.units if u.owner == player and u.kind is UnitKind.GATE)


def _adjacent_empties(state: GameState, square: Square) -> list[Square]:
    candidates = (
        Square(square.x + 1, square.y),
        Square(square.x - 1, square.y),
        Square(square.x, square.y + 1),
        Square(square.x, square.y - 1),
    )
    return [c for c in candidates if state.is_empty(c)]


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


def _path_is_clear(state: GameState, origin: Square, target: Square) -> bool:
    """True when every space strictly between origin and target is empty.

    Returns False for anything that is not a straight horizontal or vertical line.
    """
    if origin.x != target.x and origin.y != target.y:
        return False
    step_x = (target.x > origin.x) - (target.x < origin.x)
    step_y = (target.y > origin.y) - (target.y < origin.y)
    x, y = origin.x + step_x, origin.y + step_y
    while (x, y) != (target.x, target.y):
        if not state.is_empty(Square(x, y)):
            return False
        x += step_x
        y += step_y
    return True


def _can_move(state: GameState, unit: UnitState, to: Square, player: PlayerId) -> bool:
    if unit.owner != player or not unit.can_move():
        return False
    if unit.unit_id in state.moved or len(state.moved) >= MAX_UNITS_PER_PHASE:
        return False
    if not to.is_on_board() or not state.is_empty(to):
        return False
    distance = unit.position.distance_to(to)
    if distance < 1 or distance > MAX_MOVE_DISTANCE:
        return False
    return _path_is_clear(state, unit.position, to)


def _can_attack(state: GameState, attacker: UnitState, target: UnitState, player: PlayerId) -> bool:
    if attacker.owner != player or not attacker.can_attack():
        return False
    if attacker.unit_id in state.attacked or len(state.attacked) >= MAX_UNITS_PER_PHASE:
        return False
    if target.owner == player:
        return False
    if attacker.attack is AttackKind.MELEE:
        return attacker.position.is_adjacent_to(target.position)
    distance = attacker.position.distance_to(target.position)
    if distance < 1 or distance > RANGED_RANGE:
        return False
    return _path_is_clear(state, attacker.position, target.position)


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
            if unit.owner != player or unit.unit_id in state.attacked:
                continue
            actions.extend(
                AttackUnit(unit.unit_id, target.unit_id)
                for target in state.units
                if _can_attack(state, unit, target, player)
            )

    elif state.phase is Phase.MAGIC:
        actions.extend(DiscardForMagic(card_id) for card_id in player_state.hand)

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
    moved_unit = replace(unit, position=action.to)
    units = tuple(moved_unit if u.unit_id == unit.unit_id else u for u in state.units)
    return replace(state, units=units, moved=(*state.moved, unit.unit_id))


def _apply_damage(state: GameState, target: UnitState, amount: int) -> GameState:
    """Damage a card, destroying it at 0 life. Cards under it are discarded (p.8)."""
    if amount <= 0:
        return state
    damaged = replace(target, damage=target.damage + amount)
    if damaged.is_alive():
        units = tuple(damaged if u.unit_id == target.unit_id else u for u in state.units)
        return replace(state, units=units)
    if damaged.kind is UnitKind.SUMMONER:
        # A summoner never leaves the battlefield: its death is a loss condition, and
        # removing it would erase the identity the terminal check needs.
        dead = replace(target, damage=target.life)
        units = tuple(dead if u.unit_id == target.unit_id else u for u in state.units)
        return replace(state, units=units)
    return replace(state, units=tuple(u for u in state.units if u.unit_id != target.unit_id))


def _attack(state: GameState, action: AttackUnit) -> GameState:
    attacker = state.unit(action.attacker)
    target = state.unit(action.target)
    if not _can_attack(state, attacker, target, state.active):
        raise RulesError(f"{action.attacker!r} cannot attack {action.target!r}")

    rng = derive_rng(state.seed, state.rng_counter + 1)
    rolls = roll(attacker.strength, rng)
    damage = hits(rolls, attacker.attack)

    after = _apply_damage(state, target, damage)

    # Rulebook p.8: gain 1 magic whenever a card you control destroys an enemy card.
    was_destroyed = damage > 0 and all(u.unit_id != target.unit_id for u in after.units)
    if was_destroyed:
        after = _with_player(after, _gain_magic(after.player(state.active), 1))

    return replace(
        after,
        rng_counter=state.rng_counter + 1,
        attacked=(*state.attacked, attacker.unit_id),
        attacked_any=True,
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
        state = _apply_cost_of_inaction(state)
        if is_terminal(state):
            return state

    if state.phase is Phase.MAGIC:
        # Draw step, then hand the turn over (rulebook p.9).
        state = _with_player(state, _draw_up_to_hand_size(state.player(state.active)))
        if is_terminal(state):
            return state
        return replace(
            state,
            turn=state.turn + 1,
            active=opponent(state.active),
            phase=Phase.SUMMON,
            moved=(),
            attacked=(),
            attacked_any=False,
        )

    index = _PHASE_ORDER.index(state.phase)
    return replace(state, phase=_PHASE_ORDER[index + 1])


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
