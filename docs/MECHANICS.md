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
| Pile On — Gang Up (+1 strength per other friendly unit adjacent to the target) | `engine._effective_strength` |
| Unrelenting (a friendly common that would be destroyed returns to hand) | `engine._apply_damage` |
| Enrage the Horde (0 cost units resolve an extra attack) | `engine.EFFECT_HANDLERS` |
| Sneak (force targeted 0 cost units 1 space away from your summoner) | `engine.EFFECT_HANDLERS` |

## Not implemented yet

- **Climb** (Horde Climber): +1 space and through structures during a move.
- **Cling** (Horde Clinger): follows a friendly unit that starts its move adjacent.
- **Sly** (Sneeks): exchange places with a friendly 0 cost unit.
- **Blood Runes / Imbued Strength** (Blarf): boosts at the start of the Attack Phase.
- **Magic Junkie** (Smeg): pay 1 magic at end of turn or be discarded.
- **Feed the Eater** (The Eater): discard a friendly adjacent unit or itself.
- Champion limits, if the rulebook imposes any beyond "one copy per deck".
- Structures other than gates (none are transcribed yet).
- Playing events is not yet part of any agent's policy: the league has no agents.

Anything not listed as implemented must be treated as absent, not as "probably fine": a
card whose text the engine ignores will underperform in every simulation.
