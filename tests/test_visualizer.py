"""The replay viewer must always be regenerable from a real game."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sw_engine.ids import DeckId

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from visualize import WEB_TEMPLATE, play_game  # noqa: E402


def test_play_game_records_a_full_game() -> None:
    frames = play_game(DeckId("cave_goblins"), DeckId("savanna_elves"), seed=3, max_steps=2000)

    assert len(frames) > 20, "a game should take more than a handful of actions"
    assert frames[0]["label"] == "Setup"
    assert frames[-1]["label"] == "Game over"
    assert frames[-1]["result"] in {"A wins", "B wins", "draw", "unfinished (step cap reached)"}


def test_snapshot_is_json_serialisable() -> None:
    frames = play_game(DeckId("cave_goblins"), DeckId("savanna_elves"), seed=5, max_steps=200)
    payload = json.loads(json.dumps([frame["state"] for frame in frames]))
    units = payload[0]["units"]
    assert units, "the board starts populated"
    assert {"id", "owner", "name", "kind", "x", "y", "life", "strength"} <= set(units[0])


def test_template_has_the_data_placeholder() -> None:
    assert "__REPLAY_DATA__" in WEB_TEMPLATE.read_text(encoding="utf-8")


def test_script_writes_a_viewer(tmp_path: Path) -> None:
    out = tmp_path / "replay.html"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "visualize.py"), "--seed", "9", "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    html = out.read_text(encoding="utf-8")
    assert "__REPLAY_DATA__" not in html, "the placeholder must be replaced"
    assert '"frames"' in html
    assert len(html) > 50_000
