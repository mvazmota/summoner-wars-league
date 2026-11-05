# Summoner Wars 2E — Bot League

Local, offline simulator and league runner for *Summoner Wars (Second Edition)*: parameterised bots,
each locked to one faction deck, playing thousands of headless games to measure matchup win rates,
agent-style effects, and marginal value of individual units.

**Read [`AGENTS.md`](./AGENTS.md) before writing any code.** It is the spec: architecture,
interfaces, determinism rules, milestones M0–M5 with acceptance criteria, testing and statistics
rules, and the things not to do.

## Pick a matchup and watch it

```bash
uv run python scripts/serve.py --port 8765
```

Open `http://<this machine>:8765/`. The page lists every deck, lets you choose player A and
player B, runs the game on the server and plays it back on the board. When the game ends an
**end screen** appears with the verdict, the **MVP of the match** (damage dealt, kills, turns
on board, and the score behind the ranking), the highlights and the numbers behind them (turns,
summoner life, damage, summons, losses, events, magic spent, biggest hit).

The whole thing is stdlib only: `http.server` for the API (`/api/decks`, `/api/game`) and
plain JavaScript for the page. No Flask, no build step, no network access.

`scripts/visualize.py` still writes a single self-contained HTML file per game, which is
handy for sharing a specific replay offline.

## Watch a game

```bash
uv run python scripts/visualize.py --seed 7 --out out/replay.html
```

That plays one game with a simple greedy policy and writes a **self-contained HTML viewer**:
the whole game is embedded as JSON, so the page needs no server, no build step and no
network. Open `out/replay.html` directly, or serve it to another device on the LAN:

```bash
python -m http.server 8765 --directory out     # http://<this machine>:8765/replay.html
```

Controls: `←`/`→` step through actions, `space` plays, the slider scrubs, and clicking a card
on the board shows its stats. The policy is a placeholder — it attacks when it can and plays
an event when it is cheap — so the viewer shows the engine working, not good play.

## Status

**M1 complete** — typed engine surface, determinism guard, solver-independent rules contract.
Setup follows the official rulebook v1.2 (random first player, magic 2/3, 6x8 battlefield,
draw to 5) and each faction's printed starting layout — see [`docs/RULES.md`](./docs/RULES.md)
and [`docs/STARTING_LAYOUTS.md`](./docs/STARTING_LAYOUTS.md). The engine plays full turns:
summon, move, build, attack with dice, magic, draw. Card data is transcribed by hand into `data/cards/*.json` — see
[`docs/CARD_STATUS.md`](./docs/CARD_STATUS.md) for what is verified and what is still a
placeholder;
cards now play their printed events, and every
Cave Goblins card — events and abilities — is wired into the rules —
[`docs/MECHANICS.md`](./docs/MECHANICS.md) lists what runs and what is still just text. Next milestone: **M3 — card data and effect DSL** (M2 fuzzing
runs alongside).

Verified on this machine:

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest -m "not slow"       # 98 passed
uv run python -m sw_engine.smoke  # prints the canonical state hash
```

## Layout

```
src/sw_engine/   rules engine (pure, no AI, no I/O)
src/sw_cards/    card definitions as data
src/agents/      policies (random, greedy, search, MCTS)
src/league/      scheduling, ratings, statistics, reports
scripts/         fuzzing, calibration, plots
tests/           pytest
docs/            design notes, card status, unresolved rules
```

## Quick start (once M0 lands)

```bash
uv sync
uv run pytest -m "not slow"
```
