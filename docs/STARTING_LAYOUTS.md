# Starting layouts (per summoner card back)

Source: photographs of the physical summoner cards supplied by the project owner.
Coordinates are **own-side**: column `0–5` left to right as printed on the card back,
row `0` = the owner's back row, increasing towards the opponent.

Derivation: the six board photographs share one render, so positions are read relative to
the summoner (always the bottom-most card, row 0) and to the gate. All six layouts below were confirmed by the project owner on 2026-11-05 and are encoded in
`sw_cards` — the engine now places setup cards from this table.

Status: `confirmed` = checked by the owner against the physical card; `unconfirmed` =
read from a photo and awaiting confirmation.

Card names below were verified against SW Zone's per-faction setup sheets
(`/faction/<faction>/overview/pdf`); positions come from the owner's photos.

| Faction | Summoner | Gate | Unit 1 | Unit 2 | Status |
|---|---|---|---|---|---|
| Savanna Elves | Abua Shi (4,0) | (4,1) | Lioness (3,0) | Border Archer (3,3) | confirmed |
| Cave Goblins | Sneeks (5,0) | (4,1) | Slinger (5,1) | Beast Rider (3,3) | confirmed |
| Shadow Elves | Taculla (3,0) | (4,1) | Mind Witch (3,1) | Deceiver (5,3) | confirmed |
| Vanguards | Sera (4,0) | (4,2) | Temple Priest (5,2) | Citadel Knight (3,3) | confirmed |
| Fallen Kingdom | Ret-Talus (4,0) | (4,2) | Archer (3,1) | Carrier (3,2) | confirmed |
| Polar Dwarves | Svara (4,0) | (4,2) | Ice Golem (3,1) | Frost Mage (3,2) | confirmed |

## Resolved: the Mind Witch photo was the Breakers

The photo that put **Mind Witch** and **Deceiver** on the board was filed under Shadow Elves,
but both cards are printed as **Breakers** commons and SW Zone's Breakers setup sheet lists
exactly those two. The layout `(3,0) Taculla · (4,1) gate · (3,1) Mind Witch · (5,3) Deceiver`
therefore belongs to the Breakers deck.

Shadow Elves start with **Sage Ranger** and **Shadow Mage**; there is no photo of that
summoner card yet, so its layout is a shape-alike, not a transcription.

## Invariants every layout must satisfy

- exactly one summoner, one gate and two units per faction;
- all four cards inside the owner's half (rows 0–3);
- no two cards share a square;
- the gate is **not** required to be adjacent to the summoner: several factions place it
  further forward, so no adjacency assertion is made here.
