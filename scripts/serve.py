"""Local web app: pick a matchup, watch the game, read the analysis.

Stdlib only — no Flask, no build step:

    uv run python scripts/serve.py --port 8765
    open http://<this machine>:8765/
"""

from __future__ import annotations

import argparse
import json
import random
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qs, urlparse

from sw_cards import REGISTRY, known_decks
from sw_core import DeckId
from sw_league.analysis import summarise
from sw_league.playbook import load as load_playbook
from sw_league.replay import play_game

WEB_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "web"
ART_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "art"
MAX_SEED: Final[int] = 2**31 - 1


def deck_catalogue() -> list[dict[str, Any]]:
    catalogue = []
    for deck_id in sorted(known_decks()):
        deck = REGISTRY[deck_id]
        catalogue.append(
            {
                "id": str(deck_id),
                "faction": deck.faction,
                "units": len(deck.units),
                "events": len(deck.events),
                "verified": bool(deck.events),
                "playbook": load_playbook(deck_id).identity,
            }
        )
    return catalogue


def _playbook_summary(deck_id: str) -> dict[str, Any]:
    book = load_playbook(DeckId(deck_id))
    return {
        "identity": book.identity,
        "summary": book.summary,
        "source": book.source,
        "notes": list(book.notes),
    }


def build_game(deck_a: str, deck_b: str, seed: int | None) -> dict[str, Any]:
    if seed is None:
        seed = random.randint(1, MAX_SEED)
    frames = play_game(DeckId(deck_a), DeckId(deck_b), seed)
    report = summarise(
        frames,
        faction_a=REGISTRY[DeckId(deck_a)].faction,
        faction_b=REGISTRY[DeckId(deck_b)].faction,
        seed=seed,
    )
    return {
        "meta": {
            "deck_a": deck_a,
            "deck_b": deck_b,
            "faction_a": REGISTRY[DeckId(deck_a)].faction,
            "faction_b": REGISTRY[DeckId(deck_b)].faction,
            "seed": seed,
            "frames": len(frames),
            "result": frames[-1].get("result"),
            "playbook_a": _playbook_summary(deck_a),
            "playbook_b": _playbook_summary(deck_b),
        },
        "frames": frames,
        "report": report,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, directory: str, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        if self.path.startswith("/api/"):
            super().log_message(format, *args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/decks":
            self._json({"decks": deck_catalogue()})
            return

        if parsed.path == "/api/game":
            query = parse_qs(parsed.query)
            deck_a = (query.get("deck_a") or [""])[0]
            deck_b = (query.get("deck_b") or [""])[0]
            raw_seed = (query.get("seed") or [""])[0]

            available = {str(deck) for deck in known_decks()}
            if deck_a not in available or deck_b not in available:
                self._json(
                    {"error": f"unknown deck; known: {sorted(available)}"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            if deck_a == deck_b:
                pass  # a mirror match is legitimate

            seed: int | None = None
            if raw_seed:
                try:
                    seed = int(raw_seed)
                except ValueError:
                    self._json({"error": "seed must be an integer"}, status=HTTPStatus.BAD_REQUEST)
                    return

            try:
                payload = build_game(deck_a, deck_b, seed)
            except Exception as error:
                self._json({"error": str(error)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._json(payload)
            return

        if parsed.path.startswith("/art/"):
            # Local-only card art, cropped from the owner's own photos. Git-ignored.
            name = parsed.path.removeprefix("/art/")
            if "/" in name or not name.endswith(".png"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            path = ART_DIR / name
            if not path.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path in ("/", "/index.html"):
            self.path = "/app.html"

        super().do_GET()

    def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    handler = partial(Handler, directory=str(WEB_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"serving {WEB_DIR} on http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
