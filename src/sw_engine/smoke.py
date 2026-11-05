"""M0 acceptance check: build a game and print its canonical hash.

Usage: `uv run python -m sw_engine.smoke`
"""

from __future__ import annotations

from sw_engine.engine import initial_state, legal_actions, step
from sw_engine.ids import DeckId

DEFAULT_DECK_A = DeckId("placeholder_alpha")
DEFAULT_DECK_B = DeckId("placeholder_beta")
DEFAULT_SEED = 20261105


def main() -> int:
    state = initial_state(DEFAULT_DECK_A, DEFAULT_DECK_B, DEFAULT_SEED)
    print(f"deck_a={DEFAULT_DECK_A} deck_b={DEFAULT_DECK_B} seed={DEFAULT_SEED}")
    print(f"initial  hash={state.state_hash()} legal={len(legal_actions(state))}")

    action = legal_actions(state)[0]
    after = step(state, action)
    print(f"after {action.__class__.__name__:<8} hash={after.state_hash()} active={after.active}")

    assert state.state_hash() != after.state_hash(), "step must change the state"
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
