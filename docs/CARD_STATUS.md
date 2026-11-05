# Card data status

Card data is transcribed by hand from the physical cards into `data/cards/<deck>.json`
and loaded by `sw_cards.load_verified_cards`. Anything absent from those files is still a
placeholder and must never be trusted by the league.

## Cave Goblins — 12 of 34 cards

The deck needs 1 summoner, 2 starting units, 16 commons, 3 champions, 4 gates and
8 events (2 epic + 6 standard).

| Card | Class | Cost | Life | Attack | Ability | Ability text |
| --- | --- | --- | --- | --- | --- | --- |
| Sneeks | Summoner | — | 11 | 3 melee | Sly | yes |
| Beast Rider | Common | 2 | 3 | 3 melee | Charge | yes |
| Horde Slinger | Common | 0 | 1 | 2 ranged | Relentless | yes |
| Horde Climber | Common | 0 | 3 | 1 melee | Climb | yes |
| Horde Clinger | Common | 0 | 2 | 2 melee | Immobile / Cling | yes |
| Blarf | Champion | 0 | 6 | 0 melee | Blood Runes / Imbued Strength | yes |
| Smeg | Champion | 0 | 4 | 2 ranged | Magic Junkie / Relentless | yes |
| The Eater | Champion | 6 | 9 | 5 melee | Feed the Eater | yes |
| Enrage the Horde | Epic Event (phase unknown) | 1 | — | — | — | yes |
| Unrelenting | Standard Event (Magic Phase) | 1 | — | — | Active | yes |
| Pile On | Standard Event (Attack Phase) | 0 | — | — | Active / Gang Up | yes |
| Sneak | Standard Event (Move Phase) | 0 | — | — | — | yes |

SW Zone's setup sheet marks events as **2 copies each**, so these four fill the eight
event slots exactly (2 epic + 6 standard).

**Gates are identical across every faction** and are encoded once: the starting gate is a
structure with cost 0 and 10 life, the other three cost 0 and have 5 life each.

Cave Goblins is therefore **complete: 34 of 34 cards**.

## Breakers — complete

Starting setup per SW Zone: **Mind Witch** and **Deceiver**. That photo was originally filed
under Shadow Elves, which is wrong: Mind Witch and Deceiver belong to the Breakers, and the
Shadow Elves start with Sage Ranger and Shadow Mage.

| Card | Class | Cost | Life | Attack | Ability | Ability text |
| --- | --- | --- | --- | --- | --- | --- |
| Taculla | Summoner | — | 13 | 3 melee | Mind Capture | yes |
| Gwalark | Champion | 6 | 8 | 3 melee | Flight / Levitate | yes |
| Gulldune | Champion | 6 | 6 | 4 melee | Telepathic Command | yes |
| Halal | Champion | 1 | 8 | 4 ranged | Greater Push / Steadfast | yes |
| Wind Archer | Common | 2 | 2 | 4 ranged | Swift / Far Shot | yes |
| Wind Mage | Common | 1 | 3 | 2 ranged | Push | yes |
| Mind Witch | Common | 1 | 2 | 3 ranged | Mimic | yes |
| Deceiver | Common | 1 | 4 | 1 ranged | Stupefy / Engage | yes |
| Mind Control | Epic Event (Summon Phase) | 0 | — | — | — | yes |
| Hypnotic Call | Standard Event (Summon Phase) | 0 | — | — | Active | yes |
| Blast | Standard Event (Move Phase) | 1 | — | — | — | yes |
| Perplexing Tempest | Standard Event (Magic Phase) | 0 | — | — | Active | yes |

The deck is **34 of 34**: four commons at 4 copies, three champions, four events at 2 copies
and the four gates.

## Still placeholders

- Every other faction: all cards
- Gates, for every faction
- The remaining events, for every faction

## Transcription rules

- Numbers come from the card face: **cost** top-left, **life** on the heart, **strength**
  bottom-right next to the sword/bow.
- `ability` is a short mechanical paraphrase, never copied card text.
- Events carry no life or strength; the loader skips them when building battlefield cards.
- Every entry records where it came from, so a doubtful reading can be re-checked.
