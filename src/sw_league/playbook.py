"""Playbooks: the faction's strategic identity, as weights the policy can act on.

The text of a strategy guide cannot drive a bot directly, so each guide is distilled into a
small set of numbers — how much the deck wants to summon, to build, to attack, which targets it
values, and whether its summoner belongs in the fight. `source` keeps the provenance: if a
weight looks wrong, the paragraph behind it is one click away.

These are heuristics, not truth: they encode one strong player's plan for the faction, and the
league exists to test whether that plan actually wins.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from sw_core import DeckId

STRATEGY_DIR: Final[Path] = Path(__file__).resolve().parents[2] / "data" / "strategy"

ACTION_KINDS: Final[tuple[str, ...]] = (
    "SummonUnit",
    "BuildStructure",
    "AttackUnit",
    "MoveUnit",
    "PlayEvent",
    "ForceUnit",
    "SlySwap",
    "MimicAbility",
    "CommandAlly",
    "DiscardForMagic",
)


@dataclass(frozen=True, slots=True)
class Playbook:
    deck: str
    identity: str
    source: str
    summary: str
    notes: tuple[str, ...]
    weights: dict[str, float] = field(default_factory=dict)
    swarm_target_board: int = 3
    build_gate_below: int = 1
    event_value_from_board: int = 2
    keep_summoner_safe: bool = True
    prefer_ranged_attackers: bool = False
    target_priority: tuple[str, ...] = ("COMMON", "CHAMPION", "GATE", "SUMMONER")

    def weight(self, kind: str) -> float:
        return self.weights.get(kind, 1.0)

    def target_bonus(self, card_class: str) -> float:
        if card_class in self.target_priority:
            rank = self.target_priority.index(card_class)
            return 0.35 * (len(self.target_priority) - rank)
        return 0.0


def neutral(deck_id: DeckId) -> Playbook:
    """A faction with no guide yet: every action weighs the same."""
    return Playbook(
        deck=str(deck_id),
        identity="neutral",
        source="",
        summary="No strategy guide distilled for this faction yet; the bot plays by rules only.",
        notes=(),
        weights={kind: 1.0 for kind in ACTION_KINDS},
    )


def load(deck_id: DeckId) -> Playbook:
    path = STRATEGY_DIR / f"{deck_id}.json"
    if not path.exists():
        return neutral(deck_id)
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return Playbook(
        deck=str(payload.get("deck", deck_id)),
        identity=str(payload["identity"]),
        source=str(payload.get("source", "")),
        summary=str(payload.get("summary", "")),
        notes=tuple(str(note) for note in payload.get("notes", [])),
        weights={str(k): float(v) for k, v in payload.get("weights", {}).items()},
        swarm_target_board=int(payload.get("swarm_target_board", 3)),
        build_gate_below=int(payload.get("build_gate_below", 1)),
        event_value_from_board=int(payload.get("event_value_from_board", 2)),
        keep_summoner_safe=bool(payload.get("keep_summoner_safe", True)),
        prefer_ranged_attackers=bool(payload.get("prefer_ranged_attackers", False)),
        target_priority=tuple(str(c) for c in payload.get("target_priority", ())),
    )


def available() -> tuple[str, ...]:
    if not STRATEGY_DIR.exists():
        return ()
    return tuple(sorted(path.stem for path in STRATEGY_DIR.glob("*.json")))
