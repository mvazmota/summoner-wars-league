"""Cross-process determinism guard.

The golden hash pins the RNG derivation, the deck shuffle and the state projection.
If this test breaks, the cause is almost always an accidental change in one of those
three — not a legitimate rules change. Update it only on purpose, and say why in the
commit message.
"""

from __future__ import annotations

from sw_engine.actions import EndTurn
from sw_engine.engine import initial_state, step
from sw_engine.ids import DeckId

GOLDEN_INITIAL_HASH = "beb751448e07c1b9"
GOLDEN_AFTER_PASS_HASH = "4bca973fbda8dd9c"

DECK_A = DeckId("placeholder_alpha")
DECK_B = DeckId("placeholder_beta")
SEED = 20261105


def test_initial_state_hash_is_stable_across_processes() -> None:
    state = initial_state(DECK_A, DECK_B, SEED)
    assert state.state_hash() == GOLDEN_INITIAL_HASH


def test_first_transition_hash_is_stable() -> None:
    state = step(initial_state(DECK_A, DECK_B, SEED), EndTurn())
    assert state.state_hash() == GOLDEN_AFTER_PASS_HASH
