# Card data status

Card data is transcribed by hand from the physical cards into `data/cards/<deck>.json`
and loaded by `sw_cards.load_verified_cards`. Anything absent from those files is still a
placeholder and must never be trusted by the league.

## Verified

Only cards whose numbers and ability were read directly off a full-resolution card image.

| Faction | Card | Class | Cost | Life | Attack | Ability | Ability text |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cave Goblins | Beast Rider | Common | 2 | 3 | 3 melee | Charge | yes |
| Cave Goblins | Horde Slinger | Common | 0 | 1 | 2 ranged | Relentless | yes |
| Cave Goblins | Horde Climber | Common | 0 | 3 | 1 melee | Climb | yes |
| Cave Goblins | Horde Clinger | Common | 0 | 2 | 2 melee | Immobile / Cling | yes |

## Still placeholders

- Every summoner (strength/life seen on the summoner cards, not yet transcribed)
- Every gate beyond the ten-life starting gate
- All other factions' units, champions and events
- Every champion and every event, for every faction

## Transcription rules

- Numbers come from the card face: **cost** top-left, **life** on the heart, **strength**
  bottom-right next to the sword/bow.
- `ability` is a short mechanical paraphrase, never copied card text.
- Every entry records where it came from, so a low-resolution reading can be re-checked.
