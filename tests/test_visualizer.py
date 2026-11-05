"""The replay viewer, the analysis it ships with, and the game API."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from sw_cards import REGISTRY
from sw_core import DeckId
from sw_league.analysis import summarise
from sw_league.replay import play_game

ROOT = Path(__file__).resolve().parents[1]
WEB_TEMPLATE = ROOT / "web" / "replay.html"


def _frames(seed: int = 3, max_steps: int = 2000) -> list[dict[str, Any]]:
    return play_game(DeckId("cave_goblins"), DeckId("savanna_elves"), seed, max_steps)


def test_play_game_records_a_full_game() -> None:
    frames = _frames()

    assert len(frames) > 20, "a game should take more than a handful of actions"
    assert frames[0]["label"] == "Setup"
    assert frames[-1]["label"] == "Game over"
    assert frames[-1]["result"] in {"A wins", "B wins", "draw", "unfinished"}


def test_snapshot_is_json_serialisable() -> None:
    frames = _frames(seed=5, max_steps=200)
    payload = json.loads(json.dumps([frame["state"] for frame in frames]))
    units = payload[0]["units"]
    assert units, "the board starts populated"
    assert {"id", "owner", "name", "kind", "x", "y", "life", "strength"} <= set(units[0])


def test_frames_carry_structured_actions() -> None:
    kinds = {frame["action"]["type"] for frame in _frames(max_steps=600)}
    assert "GameOver" in kinds
    assert kinds & {"SummonUnit", "MoveUnit", "AttackUnit"}


def test_summary_explains_the_result() -> None:
    frames = _frames()
    report = summarise(
        frames,
        faction_a=REGISTRY[DeckId("cave_goblins")].faction,
        faction_b=REGISTRY[DeckId("savanna_elves")].faction,
        seed=3,
    )

    assert report["winner"] in {"A", "B"}
    assert int(report["turns"]) >= 1
    assert report["highlights"], "the end screen needs something to say"
    assert report["factions"][report["winner"]] in report["verdict"]
    assert report["units_summoned"]["A"] + report["units_summoned"]["B"] > 0


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
