# Where the rules come from

The engine is built from official sources, not from memory. This file records what they are,
where the local copies live, and which one wins when they disagree.

## Local copies (never committed)

`rules/` is git-ignored: every file in it belongs to Plaid Hat Games and must not be published.

| File | What it is | Source |
| --- | --- | --- |
| `rules/summoner-wars-rulebook-v1.2.pdf` | Core rulebook, 20 pages, v1.2 | media.plaidhatgames.com/.../ph3600-rulebook-v1_2.pdf |
| `rules/rulebook-text.txt` | Text layer of the rulebook, greppable | extracted with pypdf |
| `rules/glossary-and-timing.txt` | Glossary, card effects, timing conflicts, priority order | tail of the rulebook |
| `rules/faq-v1.2.pdf` | Official FAQ and expanded rules, April 2024 | media.plaidhatgames.com/.../ph3600-faq-v1_2.pdf |
| `rules/faq-v1.2.txt` | Text layer of the FAQ | extracted with pypdf |
| `rules/rules-changes.pdf` | What changed from first edition | media.plaidhatgames.com/.../rules_changes.pdf |

The FAQ is the document that matters most for card work: it has a section per faction
(Breakers, Cave Goblins, Fallen Kingdom, …), "Commonly Missed Rules", "Minor Errata" and
"Expanded Rules", and it states its own precedence — **FAQ beats rulebook** when they conflict.

Card text itself is not in either document: it lives on the cards, which is why
`data/cards/*.json` is transcribed from photographs and cross-checked against SW Zone's setup
sheets. Check `https://plaidhatgames.com/summoner-wars-card-adjustments/` before trusting a
printed card: that page carries errata'd cards.

## Rules that decided engine behaviour

- **Precedence**: card text beats the rulebook; FAQ beats both when it contradicts them.
- **Timing conflicts**: when two effects trigger at once, the player whose turn it is decides
  the order. This is why every trigger in the engine resolves in a fixed, documented order
  instead of pretending simultaneity.
- **Force is not movement**: "slide it that many clear straight spaces in a single direction;
  forcing a card is NOT considered moving it." Consequences already in the engine: Engage only
  fires on moves, Cling only follows moves, and a forced unit may be pushed into a body only
  when the effect says so (Blast).
- **Boost tokens**: place a token, no maximum; spending boost removes tokens. Blarf's Blood
  Runes, Undead Warrior's Blood Fury and Sacrificial Pyre all share this vocabulary, so boosts
  are a first-class field on `UnitState`, not a per-card counter.
- **Specials are ignored** unless a card says otherwise (Life Drain turns them into melee hits).
- **Magic**: gain 1 only when a card you control destroys an **enemy** card; Soulless cancels it.

## What is still missing

- The mechanics of the Fallen Kingdom (see `MECHANICS.md`).
- Text for Savanna Elves, Shadow Elves, Vanguards and Polar Dwarves.
