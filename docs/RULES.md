# Rules digest — confirmed from the official rulebook

Source: *Summoner Wars (Second Edition)* Rulebook **v1.2**, Plaid Hat Games
<https://media.plaidhatgames.com/filer_public/7d/07/7d075572-2254-4248-bdb5-464ef4b97180/ph3600-rulebook-v1_2.pdf>
(retrieved 2026-11-05), plus the FAQ v1.2
<https://media.plaidhatgames.com/filer_public/33/48/33487e85-bd98-4001-bec7-16594aedfb3c/ph3600-faq-v1_2.pdf>.

Page numbers below refer to the rulebook PDF. Nothing in this file may be changed without
re-reading the cited page — the engine constants point here.

## Battlefield — p. 13–15, 17
- A **ROW** is "a full horizontal line of **6** adjacent spaces"; a **COLUMN** is "a full
  vertical line of **8** adjacent spaces". Board is therefore **6 wide × 8 tall = 48 spaces**.
- The battlefield has two **sides**: the 4 rows closest to a player are that player's side.
- A player's **back row** is the row closest to them; "back 3 rows" means the three rows
  closest to that player.
- Adjacency is orthogonal only: cards sharing an **edge**. Diagonals are never adjacent.

## Setup — p. 5
1. Battlefield between the players; supply of damage and boost tokens.
2. Each player brings a faction deck (34 cards) or a custom deck.
3. Each player places their **summoner, 2 starting units and starting gate** as printed on the
   back of their summoner card. **Starting gates have 10 life.**
4. Shuffle the remaining cards into a draw pile, then **draw 5**.
5. Determine first player at random: the first player puts their magic token on **2**, the
   other player on **3**.

## Turn sequence — p. 6
A turn is **five phases, in this order**:

1. **Summon** — summon any number of units from hand; pay the cost in magic, place each on an
   empty space **adjacent to a gate you control**.
2. **Move** — move **up to 3 different units** you control, **1 or 2 spaces** each, orthogonally,
   into or through **empty** spaces. Structures cannot move unless an effect allows it.
3. **Build** — build any number of gates/structures from hand; pay cost, place on an empty
   space **adjacent to your summoner or in your back 3 rows**.
4. **Attack** — attack with **up to 3 different units** (not necessarily the ones that moved).
   Melee units target any **adjacent** card; ranged units target any card up to **3 clear
   straight spaces** away.
5. **Magic** — discard any number of cards from hand, face down; **gain 1 magic per card**.

After all five phases: **draw back up to 5 cards**, resolve end-of-turn effects, then the
opponent's turn begins. p. 9

## Combat — p. 8
- Roll **a number of dice equal to the attacking unit's strength**.
- Each die whose symbol matches the unit's melee/ranged symbol deals **1 damage**. Ignore
  special results unless a card says otherwise.
- A card's **life is reduced by 1 per damage**; at 0 life the card is **destroyed**.
- **Gain 1 magic whenever a card you control destroys an enemy card.**
- **Cost of Inaction:** add 1 damage to **your own summoner** at the end of your Attack Phase
  if you did not target any enemy cards with an attack this turn.

## Magic — p. 15
- Magic is tracked on the magic track, **maximum 15**.
- Magic is gained by destroying enemy cards (1 each) and by discarding cards in the Magic Phase
  (1 each).

## Winning — p. 17
A player loses if their **summoner leaves the battlefield** (e.g. is destroyed). There is no
separate score.

## Deck construction — p. 12, 14 and SW Zone's deck-construction reference
Each faction deck is 34 cards, made of:

- 1 **summoner**
- 1 **ten-life gate** plus 3 **five-life gates**
- the **2 starting units** printed on the back of the summoner card (not in the draw pile)
- the **2 epic events** printed on the summoner card back
- **6 standard events**
- **3 champion units**
- **16 common units** (max 4 copies of each)
- no more than 1 copy of each **limited** card

Every card must share at least one deck symbol with its summoner.

The engine currently models only summoners, gates and units: events and champions are not
playable yet, so the placeholder composition is units + gates only (see `sw_cards`).

## Draw pile — p. 11
If a draw pile is empty, **do not reshuffle** the discard pile. A player cannot draw with an
empty draw pile. Draw pile **count** is public; its **contents** are secret.

## Event cards — p. 9
Play during the phase printed on the card, pay the cost, resolve, then discard. Cannot be played
while another effect is resolving.

## Gates — identical in every faction

- The **starting gate** is a structure: cost **0**, life **10**. It is placed during setup
  and never drawn.
- The other **three gates** are structures: cost **0**, life **5** each. They sit in the
  draw pile and are built during the Build Phase.
- A gate is not a unit: it never moves and never attacks (`strength 0`, `attack none`).
- Losing every gate loses the game (rulebook p.17), which is why the ten-life gate matters.

Encoded in `sw_cards` as `GATE_LIFE = 10`, `GATE_LIFE_STANDARD = 5`, `GATE_COST = 0`, and
exposed per deck as `DeckDefinition.gates = (starting_gate, five_life_gate)`.

## Events — p.9

- Play an event on your turn **during the phase printed on the card**, paying its cost.
  Resolve it, then discard it.
- An event with the **ACTIVE** keyword is not discarded: it goes to your active area, where
  its effect stays on. It is discarded at the start of your next turn.
- You cannot have two active events with the same name at the same time.
- Events cannot be played in the middle of resolving another effect.

Implemented events and their effects are listed in [`MECHANICS.md`](./MECHANICS.md).

## Force — rulebook + FAQ v1.2

To force a card N spaces, slide it N clear straight spaces in a single direction (horizontal or
vertical). **Forcing is not moving**: it does not count as the unit's move, does not trigger
"after this unit moves" abilities, and stops at the board edge or at a card the effect cannot
pass. Steadfast units cannot be forced at all.

## Timing conflicts — rulebook p.10

When two or more effects trigger at the same time, the player whose turn it is chooses the
order. The engine cannot ask, so it resolves triggers in a fixed order documented in
`MECHANICS.md`; when a card's outcome depends on the choice, the choice becomes an action.
