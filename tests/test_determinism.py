"""Cross-process determinism guard.

The golden hashes pin the RNG derivation, the deck shuffle, the setup and the state
projection. If this test breaks, the cause is almost always an accidental change in one
of those — not a legitimate rules change. Update it only on purpose, and say why in the
commit message.
"""

from __future__ import annotations

from sw_engine.actions import EndPhase, SummonUnit
from sw_engine.engine import initial_state, legal_actions, step
from sw_engine.ids import DeckId
from sw_engine.state import GameState

GOLDEN_INITIAL_HASH = "445fb064a9766796"
GOLDEN_AFTER_SUMMON_HASH = "6e56f6e8987e218d"
GOLDEN_AFTER_END_PHASE_HASH = "4decfceb1804b045"

DECK_A = DeckId("placeholder_alpha")
DECK_B = DeckId("placeholder_beta")
SEED = 20261105


def _initial() -> GameState:
    return initial_state(DECK_A, DECK_B, SEED)


def test_initial_state_hash_is_stable_across_processes() -> None:
    assert _initial().state_hash() == GOLDEN_INITIAL_HASH


def test_first_summon_hash_is_stable() -> None:
    state = _initial()
    action = next(a for a in legal_actions(state) if isinstance(a, SummonUnit))
    assert step(state, action).state_hash() == GOLDEN_AFTER_SUMMON_HASH


def test_end_phase_hash_is_stable() -> None:
    assert step(_initial(), EndPhase()).state_hash() == GOLDEN_AFTER_END_PHASE_HASH
