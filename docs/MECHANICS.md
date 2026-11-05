# What the engine implements

Card data can be complete while the mechanics behind it are not. This file is the honest
ledger of which rules run and which are still text on a card.

## Implemented

| Rule | Where |
| --- | --- |
| Five phases in order, one `EndPhase` per transition (p.6) | `engine._end_phase` |
| Summon: pay cost, place adjacent to a gate you control (p.6) | `engine._summon` |
| Move: up to 3 units, 1–2 orthogonal spaces, clear path (p.7) | `engine._can_move` |
| Build: gates and structures in your back 3 rows or by your summoner (p.8) | `engine._build` |
| Attack: up to 3 units, dice equal to strength, melee adjacency / ranged line (p.8) | `engine._can_attack` |
| Magic: discard a card for 1 magic, +1 magic per enemy card destroyed (p.8–9) | `engine._discard_for_magic`, `_attack` |
| Cost of inaction: 1 damage to your summoner if you attacked nothing (p.8) | `engine._apply_cost_of_inaction` |
| Draw back up to 5, never reshuffle an empty pile (p.9, p.11) | `engine._draw_up_to_hand_size` |
| Events: play on the printed phase, pay the cost, then discard (p.9) | `engine._play_event` |
| Active events: parked in the active area, discarded at the start of your next turn, never two with the same name (p.9) | `engine._play_event`, `_end_phase` |
| Relentless (extra attack, ignores the three-unit limit) | `engine._can_attack` |
| Charge (1–4 clear straight spaces) | `engine._can_move` |
| Immobile (cannot move) | `engine._can_move` |
| Climb (+1 space, passes structures) | `engine._can_move`, `_path_is_clear` |
| Cling (follows a friendly unit that moved away from it) | `engine._apply_cling` |
| Sly (Sneeks swaps with a friendly 0 cost unit, once per turn) | `engine._sly_swap` |
| Blood Runes / Imbued Strength (start of Attack Phase: 1 magic for a boost, else 1 damage; +1 strength per boost, max +5) | `engine._start_of_attack_phase` |
| Magic Junkie (end of turn: pay 1 magic or be discarded) | `engine._end_of_turn_triggers` |
| Feed the Eater (end of Attack Phase without a kill: discard a neighbour or itself) | `engine._end_of_attack_phase` |
| Pile On — Gang Up (+1 strength per other friendly unit adjacent to the target) | `engine._effective_strength` |
| Unrelenting (a friendly common that would be destroyed returns to hand) | `engine._apply_damage` |
| Enrage the Horde (0 cost units resolve an extra attack) | `engine.EFFECT_HANDLERS` |
| Sneak (force targeted 0 cost units 1 space away from your summoner) | `engine.EFFECT_HANDLERS` |

## Cave Goblins: complete

All twelve transcribed cards now behave as printed. Two choices are worth knowing:

- **Cling is automatic.** The card says "you may"; the engine moves the Clinger whenever a
  legal square exists, because an optional trigger needs an action of its own and the action
  space has none yet. This can only make the Clinger better than a human would play it.
- **Cling follows only the unit that moved.** Several Clingers can chain off one move, but a
  unit that starts adjacent to two Clingers drags both.

## Not implemented yet

- Champion limits, if the rulebook imposes any beyond "one copy per deck".
- Structures other than gates (none are transcribed yet).
- Events and abilities for the other five factions: their cards are not transcribed.
- No agent policy exists, so nothing actually plays events yet.

Anything not listed as implemented must be treated as absent, not as "probably fine": a
card whose text the engine ignores will underperform in every simulation.
