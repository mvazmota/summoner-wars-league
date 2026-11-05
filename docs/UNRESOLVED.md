# Unresolved rules questions

Questions that block implementation. Nothing here may be guessed into code: the
engine stays silent (or raises `RulesError`) until the answer is confirmed against the
rulebook or an official FAQ.

Format: `- [ ] <question> — affects: <card or rule> — source needed: <rulebook page / FAQ>`

## Setup and geometry (blocks M1)

- [ ] Confirm the battlefield dimensions used by the engine (`BOARD_WIDTH = 6`,
      `BOARD_HEIGHT = 8`) — affects: `sw_engine.state`, all geometry — source: rulebook, battlefield board.
- [ ] Confirm player-side orientation: which edge belongs to the first player, and whether the
      engine's `(0, 0)` is a corner or a player's back row — affects: `_starting_square` — source: rulebook.
- [ ] Confirm summoner starting squares and gate placement per faction — affects: setup in `initial_state` — source: rulebook setup section.
- [ ] Confirm initial hand size (`INITIAL_HAND_SIZE = 5`) and starting magic (`0`) — affects: setup — source: rulebook setup section.
- [ ] Confirm whether the summoner starts on the board at setup or is placed during the first turn — affects: setup — source: rulebook.

## Turn structure (blocks M1)

- [ ] Exact ordering of the turn steps and whether steps may be interleaved — affects: `Phase`, `legal_actions` — source: rulebook, turn sequence.
- [ ] Whether unused magic carries over and any cap on the magic pile — affects: `PlayerState.magic` — source: rulebook, magic phase.

## Combat (blocks M1)

- [ ] Dice counts per unit, hit thresholds, and how damage is assigned to champions vs. summoners — affects: attack resolution — source: rulebook, combat section.
- [ ] Retreat/withdraw rules and their interaction with engagement — affects: movement legality — source: rulebook.
