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
    tracked: dict[int, dict[str, Any]] = {}

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

        for unit_id, unit in after.items():
            if not _is_battle_unit(unit):
                continue
            record = tracked.get(unit_id)
            if record is None:
                tracked[unit_id] = {
                    "id": unit_id,
                    "name": unit["name"],
                    "owner": _side(unit["owner"]),
                    "faction": names[_side(unit["owner"])],
                    "damage_dealt": 0,
                    "kills": 0,
                    "damage_taken": 0,
                    "first_turn": state["turn"],
                    "last_turn": state["turn"],
                    "boosts": unit["boosts"],
                    "life": unit["life"],
                    "survived": False,
                }
            else:
                record["last_turn"] = state["turn"]
                record["boosts"] = max(record["boosts"], unit["boosts"])

        if kind == "AttackUnit":
            attacker = tracked.get(int(action.get("attacker") or -1))
            victim_id = int(action.get("target") or -1)
            victim_before = before.get(victim_id)
            if attacker is not None and victim_before is not None:
                victim_after = after.get(victim_id)
                if victim_after is None:
                    dealt = max(0, victim_before["life"] - victim_before["damage"])
                    attacker["kills"] += 1
                else:
                    dealt = max(0, victim_after["damage"] - victim_before["damage"])
                attacker["damage_dealt"] += dealt
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
            if gained > 0 and unit_id in tracked:
                tracked[unit_id]["damage_taken"] += gained
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
    for unit in final["units"]:
        record = tracked.get(unit["id"])
        if record is not None:
            record["survived"] = bool(unit["life"] > unit["damage"])

    report["units"] = _rank_units(tracked)
    report["mvp"] = report["units"][0] if report["units"] else None
    report["mvp_sentence"] = mvp_sentence(report["mvp"]) if report["mvp"] else ""
    report["highlights"] = _highlights(report, names)
    report["verdict"] = _verdict(report, names, winner, loser)
    return report


def _score(record: dict[str, Any]) -> float:
    """One number for a unit's match: damage, kills, longevity, survival and boosts.

    Deliberately simple and readable — the components are all shown in the end screen, so
    the ranking can be argued with instead of trusted blindly.
    """
    turns = int(record["last_turn"]) - int(record["first_turn"]) + 1
    return round(
        2.0 * int(record["damage_dealt"])
        + 3.0 * int(record["kills"])
        + 0.3 * turns
        + (4.0 if record["survived"] else 0.0)
        + 0.5 * int(record["boosts"]),
        1,
    )


def _rank_units(tracked: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Best instance of each card per side, so the table reads as cards, not clones.

    A faction holds four copies of a common and they are separate units on purpose, but
    three identical rows in an "MVP" list tell the reader nothing. The best instance wins
    the row and the count travels along.
    """
    best: dict[tuple[str, str], dict[str, Any]] = {}
    counts: dict[tuple[str, str], int] = {}
    for record in tracked.values():
        entry = dict(record)
        entry["turns_on_board"] = int(record["last_turn"]) - int(record["first_turn"]) + 1
        entry["score"] = _score(record)
        key = (str(entry["owner"]), str(entry["name"]))
        counts[key] = counts.get(key, 0) + 1
        current = best.get(key)
        if current is None or (entry["score"], entry["damage_dealt"]) > (
            current["score"],
            current["damage_dealt"],
        ):
            best[key] = entry

    ranked = []
    for key, entry in best.items():
        entry["instances"] = counts[key]
        ranked.append(entry)
    ranked.sort(key=lambda item: (-item["score"], -item["damage_dealt"], item["id"]))
    for position, entry in enumerate(ranked, start=1):
        entry["rank"] = position
    return ranked


def mvp_sentence(mvp: dict[str, Any]) -> str:
    """A one-liner for the end screen, in the same PT-PT voice as the rest."""
    bits = [
        f"{mvp['damage_dealt']} de dano",
        f"{mvp['kills']} unidade{'s' if mvp['kills'] != 1 else ''} destruída"
        f"{'s' if mvp['kills'] != 1 else ''}",
    ]
    if mvp["survived"]:
        bits.append("sobreviveu ao jogo")
    else:
        bits.append(f"caiu ao turno {mvp['last_turn']}")
    if mvp["boosts"]:
        bits.append(f"{mvp['boosts']} boosts")
    return f"{mvp['name']} ({mvp['faction']}) foi o MVP: " + ", ".join(bits) + "."


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
    if report.get("mvp"):
        mvp = report["mvp"]
        items.append(
            f"MVP: {mvp['name']} ({mvp['faction']}) com {mvp['score']} pontos — "
            f"{mvp['damage_dealt']} de dano, {mvp['kills']} kills, "
            f"{mvp['turns_on_board']} turnos em jogo."
        )
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
