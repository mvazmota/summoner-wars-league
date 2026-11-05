"""The local web app: deck catalogue and game API, over real HTTP."""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from serve import Handler  # noqa: E402


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    from functools import partial

    handler = partial(Handler, directory=str(ROOT / "web"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    host_text = host.decode() if isinstance(host, bytes) else host
    yield f"http://{host_text}:{port}"
    server.shutdown()
    server.server_close()


def get(url: str) -> tuple[int, dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.status, json.loads(response.read())


def test_deck_catalogue_lists_every_deck(base_url: str) -> None:
    status, payload = get(f"{base_url}/api/decks")
    assert status == 200
    decks = payload["decks"]
    assert len(decks) >= 6
    ids = {deck["id"] for deck in decks}
    assert "cave_goblins" in ids
    verified = {deck["id"] for deck in decks if deck["verified"]}
    assert verified == {"cave_goblins", "breakers"}, "factions with transcribed events"


def test_game_endpoint_returns_frames_and_a_report(base_url: str) -> None:
    status, payload = get(f"{base_url}/api/game?deck_a=cave_goblins&deck_b=savanna_elves&seed=42")
    assert status == 200
    assert payload["meta"]["seed"] == 42
    frames = payload["frames"]
    assert len(frames) > 20
    assert frames[-1]["label"] == "Game over"
    assert payload["report"]["winner"] in {"A", "B", None}
    assert payload["report"]["verdict"]


def test_unknown_deck_is_a_400(base_url: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as error:
        get(f"{base_url}/api/game?deck_a=nope&deck_b=cave_goblins")
    assert error.value.code == 400


def test_root_serves_the_app_shell(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/", timeout=30) as response:
        body = response.read().decode("utf-8")
    assert response.status == 200
    assert "Escolhe o matchup" in body
    assert "/api/game" in body
