# Summoner Wars 2E — Bot League

Local, offline simulator and league runner for *Summoner Wars (Second Edition)*: parameterised bots,
each locked to one faction deck, playing thousands of headless games to measure matchup win rates,
agent-style effects, and marginal value of individual units.

**Read [`AGENTS.md`](./AGENTS.md) before writing any code.** It is the spec: architecture,
interfaces, determinism rules, milestones M0–M5 with acceptance criteria, testing and statistics
rules, and the things not to do.

## Status

Scaffolding only. No engine, no cards, no agents yet. Current milestone: **M0 — skeleton**.

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
