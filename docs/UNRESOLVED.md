# Unresolved rules questions

Questions that block implementation. Nothing here may be guessed into code: the engine
stays silent (or raises `RulesError`) until the answer is confirmed against the rulebook,
the FAQ, or the card itself.

Confirmed rules now live in [`RULES.md`](./RULES.md) with page citations. This file only
tracks what is still genuinely open.

Format: `- [ ] <question> — affects: <card or rule> — source needed: <rulebook page / FAQ>`

## Setup data (blocks a faithful `initial_state`)

- [ ] Per-summoner **starting layout**: exact squares of the summoner, its 2 starting units
      and its starting gate — placeholders live in `_starting_square()` — source: the back of
      each summoner card (not in the rulebook).
- [ ] Per-summoner **life values** (12, 13, 14 …) — placeholder is `PLACEHOLDER_SUMMONER_HP = 12` — source: card data.
- [ ] Which units are the 2 starting units per faction, and whether they are taken from the
      deck or are additional — source: back of the summoner card + FAQ.

## Card semantics (blocks M3)

- [ ] The exact meaning of each die's **special** symbol per card, and how "= " chains resolve — source: card text + FAQ v1.2.
- [ ] Which abilities are **mandatory** vs. optional ("may"), and their timing windows — source: FAQ v1.2 glossary.
- [ ] Boost tokens: how `boost` / `spend 1 boost` interact with cards that grant extra effects — source: FAQ v1.2.
- [ ] Cards under a destroyed card "are discarded but not destroyed" — confirm they grant no
      magic and trigger no "on destroy" abilities — source: rulebook p.8.

## Turn and combat edge cases (blocks M1/M2 fidelity)

- [ ] When drawing back up to 5 with fewer cards left in the draw pile, does the player draw
      only what remains (no reshuffle)? — source: rulebook p.9 vs. p.11.
- [ ] Can the same unit be chosen twice across a Move or Attack Phase (e.g. as two of the
      "up to 3")? — source: rulebook p.7 ("up to 3 different units").
- [ ] Does **Cost of Inaction** trigger when an attack was declared but dealt no damage, or
      was cancelled by an effect? — source: FAQ v1.2.
- [ ] Attacking through friendly structures (`Parapet`): is that the only exception, and does
      line of fire otherwise require clear spaces? — source: rulebook p.8 + card text.
