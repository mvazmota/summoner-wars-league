"""Summoner Wars rules engine.

Pure functions over immutable state. Public surface: `initial_state`,
`legal_actions`, `step`, `is_terminal`, `outcome`, `observation`.
"""

from __future__ import annotations

from sw_engine.actions import Action, EndTurn
from sw_engine.engine import (
    INITIAL_HAND_SIZE,
    PLACEHOLDER_SUMMONER_HP,
    STARTING_MAGIC_FIRST,
    STARTING_MAGIC_SECOND,
    Outcome,
    RulesError,
    initial_state,
    is_terminal,
    legal_actions,
    observation,
    outcome,
    step,
)
from sw_engine.ids import PLAYER_A, PLAYER_B, PLAYERS, CardId, DeckId, PlayerId, UnitId, opponent
from sw_engine.observation import Observation, VisiblePlayer, VisibleUnit
from sw_engine.state import (
    BOARD_HEIGHT,
    BOARD_WIDTH,
    HAND_SIZE,
    MAGIC_MAX,
    GameState,
    Phase,
    PlayerState,
    Square,
    SummonerState,
    UnitState,
)

__all__ = [
    "BOARD_HEIGHT",
    "BOARD_WIDTH",
    "HAND_SIZE",
    "INITIAL_HAND_SIZE",
    "MAGIC_MAX",
    "PLACEHOLDER_SUMMONER_HP",
    "PLAYERS",
    "PLAYER_A",
    "PLAYER_B",
    "STARTING_MAGIC_FIRST",
    "STARTING_MAGIC_SECOND",
    "Action",
    "CardId",
    "DeckId",
    "EndTurn",
    "GameState",
    "Observation",
    "Outcome",
    "Phase",
    "PlayerId",
    "PlayerState",
    "RulesError",
    "Square",
    "SummonerState",
    "UnitId",
    "UnitState",
    "VisiblePlayer",
    "VisibleUnit",
    "initial_state",
    "is_terminal",
    "legal_actions",
    "observation",
    "opponent",
    "outcome",
    "step",
]
