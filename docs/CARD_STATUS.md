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
| Enrage the Horde | Epic Event | 1 | — | — | — | yes |
| Unrelenting | Standard Event | 1 | — | — | Active | yes |
| Pile On | Standard Event | 0 | — | — | Gang Up | yes, wording partly uncertain |
| Sneak | Standard Event | 0 | — | — | — | yes |

Missing for this faction: **1 epic event, 3 standard events and the four gates**
(one ten-life, three five-life).

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
