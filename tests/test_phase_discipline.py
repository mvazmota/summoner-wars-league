"""Turn discipline: nothing may happen outside its phase, and turns must alternate.

Rulebook p.6: Summon, Move, Build, Attack, Magic, then draw and pass. These tests walk real
generated games and assert the shape of the sequence rather than a single transition, which is
what catches an action that quietly leaks into the wrong phase.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any, Final

import pytest

from sw_cards import get_card
from sw_core import CardId, DeckId, Phase
from sw_league.replay import play_game

ALLOWED_PHASES: Final[dict[str, set[str]]] = {
    "SummonUnit": {"SUMMON"},
    "BuildStructure": {"BUILD"},
    "MoveUnit": {"MOVE"},
    "AttackUnit": {"ATTACK"},
    "DiscardForMagic": {"MAGIC"},
    "SlySwap": {"ATTACK"},
    "ForceUnit": {"ATTACK"},
    "CommandAlly": {"ATTACK"},
    "MimicAbility": {"MOVE"},
    "PlayEvent": {"SUMMON", "MOVE", "BUILD", "ATTACK", "MAGIC"},
    "EndPhase": {"SUMMON", "MOVE", "BUILD", "ATTACK", "MAGIC"},
}

SKIP_TYPES: Final[set[str]] = {"Setup", "GameOver", "Error"}
SEEDS: Final[tuple[int, ...]] = (3, 7, 11, 23, 42, 99)
PHASE_CYCLE: Final[list[str]] = ["SUMMON", "MOVE", "BUILD", "ATTACK", "MAGIC"]


def _game(seed: int) -> list[dict[str, Any]]:
    return play_game(DeckId("cave_goblins"), DeckId("breakers"), seed)


@pytest.mark.parametrize("seed", SEEDS)
def test_no_action_happens_outside_its_phase(seed: int) -> None:
    frames = _game(seed)
    previous = frames[0]["state"]
    for frame in frames[1:]:
        action = frame["action"]
        kind = str(action["type"])
        if kind in SKIP_TYPES:
            previous = frame["state"]
            continue
        assert previous["phase"] in ALLOWED_PHASES[kind], (
            f"seed {seed} turn {previous['turn']}: {kind} during {previous['phase']}"
        )
        previous = frame["state"]


@pytest.mark.parametrize("seed", SEEDS)
def test_events_only_play_on_their_printed_phase(seed: int) -> None:
    frames = _game(seed)
    previous = frames[0]["state"]
    for frame in frames[1:]:
        action = frame["action"]
        if action["type"] == "PlayEvent":
            card = get_card(CardId(str(action["card"])))
            assert card.phase is not None, f"{card.name} played with no printed phase"
            assert previous["phase"] == card.phase.name, (
                f"seed {seed}: {card.name} played during {previous['phase']}, "
                f"printed {card.phase.name}"
            )
        previous = frame["state"]


def test_phases_always_run_in_the_rulebook_order() -> None:
    for seed in SEEDS:
        frames = _game(seed)
        cycle: list[str] = []
        previous = frames[0]["state"]
        for frame in frames[1:]:
            if frame["action"]["type"] == "EndPhase":
                cycle.append(previous["phase"])
            previous = frame["state"]

        assert cycle, "a game must end phases"
        aligned = cycle[: len(cycle) - (len(cycle) % 5)]
        for index in range(0, len(aligned), 5):
            assert aligned[index : index + 5] == PHASE_CYCLE, aligned[index : index + 5]


def test_the_active_player_alternates_every_turn() -> None:
    for seed in SEEDS:
        frames = _game(seed)
        starts: list[tuple[int, int]] = []
        for index, frame in enumerate(frames):
            turn = int(frame["state"]["turn"])
            if index == 0 or int(frames[index - 1]["state"]["turn"]) != turn:
                starts.append((turn, int(frame["state"]["active"])))

        assert starts[0][0] == 1
        for (turn, active), (next_turn, next_active) in pairwise(starts):
            assert next_turn == turn + 1
            assert next_active != active, f"turn {next_turn} kept the same active player"


def test_a_turn_starts_in_the_summon_phase() -> None:
    frames = _game(SEEDS[0])
    for index, frame in enumerate(frames):
        turn = int(frame["state"]["turn"])
        if index == 0 or int(frames[index - 1]["state"]["turn"]) != turn:
            assert frame["state"]["phase"] == Phase.SUMMON.name
