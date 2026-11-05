"""Read a finished game back out of its frames.

The viewer shows what happened; this module explains it. Everything is derived from the
frame list, so a replay generated on one machine can be analysed on another without the
engine or a seed.
"""

from __future__ import annotations

from typing import Any, Final

SIDES: Final[tuple[str, str]] = ("A", "B")


def _side(player: int) -> str:
    return SIDES[player]


def _units_by_id(state: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {unit["id"]: unit for unit in state["units"]}


def _is_battle_unit(unit: dict[str, Any]) -> bool:
    return bool(unit["kind"] == "UNIT")


def summarise(
    frames: list[dict[str, Any]],
    *,
    faction_a: str,
    faction_b: str,
    seed: int | None = None,
) -> dict[str, Any]:
    names = {"A": faction_a, "B": faction_b}
    final = frames[-1]["state"]

    damage_taken = {side: 0 for side in SIDES}
    summoner_damage = {side: 0 for side in SIDES}
    units_summoned = {side: 0 for side in SIDES}
    units_lost = {side: 0 for side in SIDES}
    events_played = {side: 0 for side in SIDES}
    magic_spent = {side: 0 for side in SIDES}
    peak_board = {side: 0 for side in SIDES}
    biggest_hit: dict[str, Any] | None = None
    leader_changes = 0

    previous = frames[0]["state"]
    previous_leader = _leader(previous)
    for frame in frames[1:]:
        state = frame["state"]
        action = frame.get("action", {})
        kind = action.get("type")
        actor = action.get("actor")

        if kind in {"SummonUnit", "BuildStructure", "PlayEvent"} and actor is not None:
            side = _side(actor)
            magic_spent[side] += int(action.get("cost") or 0)
            if kind == "SummonUnit":
                units_summoned[side] += 1
            if kind == "PlayEvent":
                events_played[side] += 1

        before = _units_by_id(previous)
        after = _units_by_id(state)
        for unit_id, unit in before.items():
            if unit_id in after:
                continue
            if unit["kind"] == "SUMMONER":
                continue
            side = _side(unit["owner"])
            units_lost[side] += 1
            damage_taken[_side(1 - unit["owner"])] += max(0, unit["life"] - unit["damage"])
        for unit_id, unit in after.items():
            old = before.get(unit_id)
            if old is None:
                continue
            gained = unit["damage"] - old["damage"]
            if gained > 0:
                damage_taken[_side(1 - unit["owner"])] += gained
                if unit["kind"] == "SUMMONER":
                    summoner_damage[_side(unit["owner"])] += gained
                if biggest_hit is None or gained > biggest_hit["damage"]:
                    biggest_hit = {
                        "damage": gained,
                        "side": _side(unit["owner"]),
                        "card": unit["name"],
                        "turn": state["turn"],
                    }

        for side in SIDES:
            count = sum(
                1
                for unit in state["units"]
                if _is_battle_unit(unit) and _side(unit["owner"]) == side
            )
            peak_board[side] = max(peak_board[side], count)

        leader = _leader(state)
        if leader != previous_leader:
            leader_changes += 1
            previous_leader = leader
        previous = state

    life_left = {side: final["players"][index]["summoner_life"] for index, side in enumerate(SIDES)}
    result = frames[-1].get("result", "unfinished")
    winner = {"A wins": "A", "B wins": "B"}.get(result)
    loser = {"A": "B", "B": "A"}.get(winner or "")

    report: dict[str, Any] = {
        "winner": winner,
        "result": result,
        "factions": names,
        "seed": seed,
        "turns": final["turn"],
        "actions": len(frames) - 1,
        "life_left": life_left,
        "summoner_damage": summoner_damage,
        "damage_taken": damage_taken,
        "units_summoned": units_summoned,
        "units_lost": units_lost,
        "events_played": events_played,
        "magic_spent": magic_spent,
        "peak_board": peak_board,
        "biggest_hit": biggest_hit,
        "leader_changes": leader_changes,
    }
    report["highlights"] = _highlights(report, names)
    report["verdict"] = _verdict(report, names, winner, loser)
    return report


def _leader(state: dict[str, Any]) -> str | None:
    counts = {"A": 0, "B": 0}
    for unit in state["units"]:
        if _is_battle_unit(unit):
            counts[_side(unit["owner"])] += 1
    if counts["A"] == counts["B"]:
        return None
    return "A" if counts["A"] > counts["B"] else "B"


def _highlights(report: dict[str, Any], names: dict[str, str]) -> list[str]:
    items: list[str] = []
    winner = report["winner"]
    if winner:
        left = report["life_left"][winner]
        if left >= 8:
            items.append(
                f"{names[winner]} terminou com {left} de vida no summoner: o adversário "
                "nunca chegou a montar pressão suficiente."
            )
        elif left <= 2:
            items.append(
                f"Vitória ao fio da navalha: {names[winner]} acabou com apenas {left} de vida."
            )

    events_a = report["events_played"]["A"]
    events_b = report["events_played"]["B"]
    if events_a or events_b:
        busiest = "A" if events_a >= events_b else "B"
        items.append(
            f"{names[busiest]} jogou {max(events_a, events_b)} eventos contra "
            f"{min(events_a, events_b)} do adversário."
        )
    else:
        items.append("Nenhum dos dois lados jogou um único evento em todo o jogo.")

    losses_a = report["units_lost"]["A"]
    losses_b = report["units_lost"]["B"]
    if abs(losses_a - losses_b) >= 3:
        worse = "A" if losses_a > losses_b else "B"
        items.append(
            f"{names[worse]} perdeu {max(losses_a, losses_b)} unidades, contra "
            f"{min(losses_a, losses_b)} do outro lado — troca claramente desfavorável."
        )

    hit = report["biggest_hit"]
    if hit:
        items.append(
            f"Maior golpe do jogo: {hit['damage']} de dano em {hit['card']} "
            f"({names[hit['side']]}) no turno {hit['turn']}."
        )

    if report["leader_changes"] >= 4:
        items.append(
            f"O controlo do tabuleiro mudou de mãos {report['leader_changes']} vezes: "
            "jogo de resposta, sem domínio prolongado de nenhum lado."
        )
    return items


def _verdict(
    report: dict[str, Any], names: dict[str, str], winner: str | None, loser: str | None
) -> str:
    if winner is None:
        return (
            "Jogo sem vencedor dentro do limite de acções. "
            f"Vida final: {names['A']} {report['life_left']['A']}, "
            f"{names['B']} {report['life_left']['B']}."
        )

    left = report["life_left"][winner]
    damage = report["summoner_damage"][loser or "B"]
    turns = report["turns"]
    style = "vitória clara" if left >= 8 else "vitória sólida" if left >= 4 else "vitória apertada"
    return (
        f"{names[winner]} vence {names[loser or 'B']} ao turno {turns} — {style}, com "
        f"{left} de vida por gastar. Causou {damage} de dano ao summoner adversário, "
        f"invocou {report['units_summoned'][winner]} unidades e gastou "
        f"{report['magic_spent'][winner]} de magia ao longo de {report['actions']} acções."
    )
