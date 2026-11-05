# AGENTS.md — Summoner Wars 2E Bot League

Guidance for AI coding agents working in this repository. Read this before touching code.

## 1. What this project is

A **local, offline simulator and league runner** for *Summoner Wars (Second Edition)*.

Purpose: run tens of thousands of headless games between parameterised bot agents, each locked
to one faction deck, and measure:

- per-faction and per-matchup win rates,
- the effect of agent style (aggression, magic economy, risk tolerance, champion timing, search depth),
- marginal value of individual units (leave-one-out experiments).

This is a personal research tool. It is not a product, has no server, no accounts, no network calls.

## 2. Non-negotiable constraints

- **No copyrighted card text or card artwork in this repo.** Encode mechanics in our own words.
  A card's `text` field is a short mechanical paraphrase, max ~140 chars, never the official wording.
- **Offline only.** No telemetry, no external APIs, no auto-downloads at runtime.
- **Deterministic.** Every game is reproducible from its seed. A rerun with the same seed and same
  agent parameters must produce a byte-identical action log.
- **Python 3.12+**, managed with `uv`. No global installs, no `pip install` into system Python.

## 3. Repository layout

```
src/sw_engine/      # rules engine: state, actions, legality, transitions. No AI. No I/O.
src/sw_cards/       # card definitions as data (Python dicts or TOML). Mechanics only.
src/agents/         # policies: random, greedy, search-based, MCTS. Parameterised.
src/league/         # scheduling, ratings, statistics, reports
scripts/            # one-off tools: calibration, fuzzing, card import, plots
tests/              # pytest. Unit, property, and integration tests
data/               # seeds, match results, exports (gitignored except fixtures)
docs/               # design notes, rules references, decision log
```

Rules:

- `sw_engine` must not import `agents`, `league`, or anything network/IO related.
- `agents` may import `sw_engine`. `league` may import both.
- Card data lives in `sw_cards`, never inline in engine code.

## 4. Core interfaces

Keep these stable; everything else is negotiable.

```python
# sw_engine
@dataclass(frozen=True)
class GameState: ...

class Action: ...                      # frozen dataclass or IntEnum-typed tagged union

def initial_state(deck_a: DeckId, deck_b: DeckId, seed: int) -> GameState: ...
def legal_actions(state: GameState) -> Sequence[Action]: ...
def step(state: GameState, action: Action) -> GameState: ...
def is_terminal(state: GameState) -> bool: ...
def outcome(state: GameState) -> Outcome | None:   # WIN_A | WIN_B | DRAW
def observation(state: GameState, player: PlayerId) -> Observation:  # hides opponent hand/deck
```

```python
# agents
@dataclass(frozen=True)
class AgentParams:
    aggression: float = 0.5  # 0 = grind board, 1 = race the summoner
    magic_hoarding: float = 0.5  # 0 = summon now, 1 = bank magic
    risk_aversion: float = 0.5  # weight on keeping own summoner safe
    champion_timing: float = 0.5  # hold champions vs. deploy on curve
    determinizations: int = 3  # opponent-hand samples for search
    search_depth: int = 1  # 0 = greedy, 1, 2 ...
    seed: int = 0


class Policy(Protocol):
    def choose(self, obs: Observation, legal: Sequence[Action], rng: random.Random) -> Action: ...
```

**Hard rule:** agents see only `Observation`. If an agent needs information the opponent should
not have, the bug is in the interface, not the agent.

## 5. Determinism and reproducibility

- One `random.Random` per game, seeded from `(game_seed, player_id)`. Never use `random` module globals.
- Never seed from wall-clock time, PID, or hash of an object (`hash()` is salted per process).
- Never iterate over `set`/`dict` where order affects decisions; sort by a stable key.
- Log every action with the state hash so a replay can be verified.

## 6. Milestones (do not skip, do not reorder)

### M0 — Skeleton
- Repo, `pyproject.toml`, ruff, mypy strict, pytest, CI-less pre-commit script.
- `GameState`, `Action`, `initial_state`, `legal_actions`, `step`, `is_terminal` compiling and typed.
- **Done when:** `uv run pytest` passes and `uv run python -m sw_engine.smoke` prints a state hash.

### M1 — Rules core, one faction vs itself
- Board, gates, summoning cost/magic pile, movement, attacks with dice counts, damage, summoner death.
- Vanilla units only: no abilities beyond keywords already implemented.
- **Done when:** a full game finishes; a hard 200-turn cap adjudicates by summoner HP.

### M2 — Legal-move fuzzing
- Random-legal-action bots play 100k games across all implemented factions.
- Invariants checked every step: no negative HP, magic in range, units on legal squares,
  hand+deck+discard size constant, no duplicate unit ids, no action that is illegal by definition.
- **Done when:** 0 crashes, 0 invariant violations, and a **mirror test** (same agent both sides,
  sides swapped) lands within 50% ± 1.5% over 20k games.

### M3 — Cards as data
- Effect DSL: triggers (`on_summon`, `on_attack`, `on_damage`, `on_death`, `on_move`, ...) with
  declarative targets and effects; no card-specific `if` in the engine loop.
- `NotImplemented` abilities must raise a typed `UnsupportedAbility` in strict mode and be
  recorded in `docs/CARD_STATUS.md`.
- **Done when:** one full faction is encoded and no engine file mentions a card name.

### M4 — Agents and calibration
- Random, greedy (evaluation function over the 5 parameter axes), 1-ply, 2-ply; determinisation for
  hidden hands.
- Calibration: reproduce a known human matchup win rate from public league data within ±5 points.
- **Done when:** calibration report exists in `docs/`, with the source of the reference numbers.

### M5 — The league
- 20 agents, balanced deck assignment (each deck used 3–4 times), round-robin with sides swapped,
  configurable games per pair, parallel execution.
- Ratings: Bradley–Terry with covariates (`skill`, `deck`, `side`), bootstrap confidence intervals.
- Full matchup matrix exported; Nash equilibrium over decks solved and reported.
- Anchors: a frozen random agent and a frozen strong heuristic, always present in the pool.
- **Done when:** a league run produces a report with win rates, CIs, per-deck effects, and the
  equilibrium mix — and the results are reproducible from the run config.

## 7. Testing rules

- Every new rule gets a unit test with a hand-built state, not a full game.
- Property tests (hypothesis) for invariants: conservation of cards, bounded HP, legality closure.
- No test may depend on the number of games played in another test.
- Bug fixes require a regression test that fails before and passes after.
- Keep a `tests/fixtures/` with at least 3 recorded real games to validate the engine end-to-end.
- Fast suite must stay under 60 seconds: `uv run pytest -m "not slow"`.

## 8. Style and quality

- Type hints everywhere; `mypy --strict` must pass. No `Any` without a comment explaining why.
- `ruff` with line length 100, isort, and the default rule set plus `B`, `SIM`, `RUF`.
- Prefer `frozen=True` dataclasses. No mutable default arguments. No module-level mutable state.
- Pure functions in the engine: `step` returns a new state, never mutates the input.
- Names in English. Comments explain *why*, never *what*.
- No premature optimisation. Profile first (`py-spy`), then optimise the hot path, and record the
  before/after numbers in the commit message.

## 9. Performance targets

- Engine (rules only, no search): **≥ 500 games/second** single core for the simplified card set.
- League run of 20k games: **< 10 minutes** on 8 cores.
- If Python cannot hit the target, first reduce allocations and use tuples/ints over objects.
  Only then consider a Rust core with `pyo3` — and only behind a feature flag.

## 10. Statistics rules

- Report **confidence intervals**, never bare win rates.
- Always block by deck when comparing agents; deck effects dominate.
- Never rank agents on fewer than 200 games per pair.
- Write down the sample size and seed range in every report.
- Treat non-transitivity as expected: publish the matchup matrix, not just a single ranking.

## 11. What the agent must NOT do

- Do **not** invent rules. If the official rule or card behaviour is unclear, implement nothing,
  add a `TODO(rules)` comment with the exact question, and list it in `docs/UNRESOLVED.md`.
- Do **not** silently approximate an ability to make a test pass.
- Do **not** copy card text, card images, or official rulebook prose into the repo.
- Do **not** add network dependencies, telemetry, or background services.
- Do **not** start M5 work while M2 or M3 acceptance criteria are unmet.
- Do **not** reformat or refactor files unrelated to the task at hand.
- Do **not** commit `data/` outputs or generated reports.

## 12. Commands

```bash
uv sync                                  # install deps
uv run pytest -m "not slow"              # fast suite
uv run pytest                            # full suite
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run python -m scripts.fuzz --games 100000
uv run python -m sw_league.run --config configs/league_default.toml
uv run python -m scripts.calibrate --matchup "savanna_elves:cave_goblins"
```

## 13. Definition of done (every change)

1. Types pass (`mypy --strict`), lint passes, fast tests pass.
2. New behaviour is covered by a test that would fail without the change.
3. Determinism preserved: same seed → same action log.
4. Docs updated if a rule, card status, or CLI changed.
5. The change is small enough to review in one sitting.
