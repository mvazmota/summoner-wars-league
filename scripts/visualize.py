"""Play one game and write a self-contained HTML viewer for it.

Usage:
    uv run python scripts/visualize.py --seed 7 --out out/replay.html

The output has no dependencies: the whole game is embedded as JSON and rendered by plain
JavaScript, so it can be opened from disk or served by `python -m http.server`.
For a pick-your-own-matchup version, run `scripts/serve.py` instead.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sw_cards import REGISTRY, known_decks
from sw_core import DeckId
from sw_league.analysis import summarise
from sw_league.replay import play_game

WEB_TEMPLATE = Path(__file__).resolve().parents[1] / "web" / "replay.html"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--deck-a", default="cave_goblins")
    parser.add_argument("--deck-b", default="savanna_elves")
    parser.add_argument("--out", default="out/replay.html")
    parser.add_argument("--max-steps", type=int, default=4000)
    args = parser.parse_args()

    available = {str(deck) for deck in known_decks()}
    for deck in (args.deck_a, args.deck_b):
        if deck not in available:
            parser.error(f"unknown deck {deck!r}; known: {sorted(available)}")

    frames = play_game(DeckId(args.deck_a), DeckId(args.deck_b), args.seed, args.max_steps)
    report = summarise(
        frames,
        faction_a=REGISTRY[DeckId(args.deck_a)].faction,
        faction_b=REGISTRY[DeckId(args.deck_b)].faction,
        seed=args.seed,
    )
    payload = {
        "meta": {
            "deck_a": args.deck_a,
            "deck_b": args.deck_b,
            "seed": args.seed,
            "frames": len(frames),
            "result": frames[-1].get("result"),
        },
        "report": report,
        "frames": frames,
    }

    html = WEB_TEMPLATE.read_text(encoding="utf-8").replace(
        "__REPLAY_DATA__", json.dumps(payload, separators=(",", ":"))
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size // 1024} KiB, {len(frames)} frames)")
    print(f"open: file://{out_path.resolve()}")
    print(report["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
