# Summoner Wars 2E — Bot League

Local, offline simulator and league runner for *Summoner Wars (Second Edition)*: parameterised bots,
each locked to one faction deck, playing thousands of headless games to measure matchup win rates,
agent-style effects, and marginal value of individual units.

**Read [`AGENTS.md`](./AGENTS.md) before writing any code.** It is the spec: architecture,
interfaces, determinism rules, milestones M0–M5 with acceptance criteria, testing and statistics
rules, and the things not to do.

## Status

**M0 complete** — typed engine surface, determinism guard, solver-independent rules contract.
Setup now follows the official rulebook v1.2 (random first player, magic 2/3, 6x8 battlefield,
draw to 5); see [`docs/RULES.md`](./docs/RULES.md). No real cards and no agents yet.
Next milestone: **M1 — rules core (one faction vs itself)**.

Verified on this machine:

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest -m "not slow"       # 18 passed
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
