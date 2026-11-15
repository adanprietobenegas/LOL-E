"""Datos de ejemplo de la demostración: un jugador y un historial INVENTADOS (deterministas, con una semilla fija), para enseñar la app llena sin tocar los datos de nadie.

Nada de aquí sale del PC del usuario. Los números son realistas y mediocres a propósito (un 51 % de victorias, algunas derrotas feas): una demo que solo enseña éxitos
hace esperar lo mismo de los datos propios. Cada función es pura: recibe el «ahora» y devuelve datos.

Contenido: historial (`history_entries`), rango y PL (`lp_entries`, `PROFILE`), un análisis de partida con la forma que produce analysis.compute (`analysis_sample`) y los
equipos de una selección y de una partida (`SESSION`, `ROSTER`, `rivals`, `mates`)."""
import random

DAY = 86_400_000

# campeones de la demo (ids de Data Dragon); todos existen en champions.json
TOP = [86, 54, 122, 266, 875]            # Garen, Malphite, Darius, Aatrox, Sett
MID = [103, 134]                         # Ahri, Syndra
OTHERS = [64, 222, 89, 412, 157]         # Lee Sin, Jinx, Leona, Thresh, Yasuo
ARAM = [103, 222, 51, 81, 99, 18]

PROFILE = {"name": "Jugador", "tag": "EUW", "level": 214, "icon": 29, "puuid": "yo",
           "solo": {"key": "GOLD", "tier": "Oro", "div": "II", "lp": 47, "w": 58, "l": 51, "wr": 58 / 109},
           "flex": {"key": "SILVER", "tier": "Plata", "div": "I", "lp": 12, "w": 9, "l": 7, "wr": 9 / 16}, "prem": None,
           "extra": {"peak": {"key": "GOLD", "tier": "Oro", "div": "I"}, "prev": {"key": "GOLD", "tier": "Oro", "div": "III"}}}


def history_entries(now_ms, n=80):
    """{id: entrada} con n partidas repartidas en los últimos ~45 días (la forma de history.json)."""
    rnd = random.Random(2026)
    out, t = {}, now_ms - 2 * 3600 * 1000
    for i in range(n):
        q = rnd.choices([420, 440, 450], [0.58, 0.14, 0.28])[0]
        aram = q == 450
        c = rnd.choice(ARAM) if aram else rnd.choices(TOP + MID + OTHERS, [4, 2, 2, 1, 1, 2, 1, 1, 1, 1, 1, 1])[0]
        role = "" if aram else ("TOP" if c in TOP else "MIDDLE" if c in MID else rnd.choice(["JUNGLE", "BOTTOM", "SUPPORT", "TOP"]))
        win = rnd.random() < 0.51
        dur = rnd.randint(1100, 2300) if not aram else rnd.randint(900, 1500)
        k = rnd.randint(2, 11) + (3 if win else 0)
        de = max(0, rnd.randint(2, 10) - (2 if win else 0))
        a = rnd.randint(3, 16)
        gid = str(8_030_000_000 + i * 411)
        out[gid] = {"id": gid, "t": t, "d": dur, "q": q, "c": c, "w": win, "r": role, "k": k, "de": de, "a": a, "cs": 0 if aram else rnd.randint(70, 260),
                    "lv": rnd.randint(13, 18), "dm": rnd.randint(11000, 34000), "g": rnd.randint(8000, 17000), "v": rnd.randint(6, 45), "rm": False,
                    "it": [3068, 3071, 6694, 3047, 0, 0, 3340], "gm": "ARAM" if aram else "CLASSIC", "gt": "MATCHED_GAME", "pl": 0, "au": []}
        t -= rnd.randint(2, 20) * 3_600_000 // 2
    return out


def lp_entries(hist, label_of):
    """lp.json de la demo: los PL de las últimas partidas de Solo/Dúo, subiendo con altibajos. `label_of(valor)` da el nombre de la división."""
    games = sorted((e for e in hist.values() if e["q"] == 420), key=lambda e: e["t"])[-26:]
    rnd = random.Random(7)
    v = 1000 + 3 * 100 + 20          # Oro III, 20 PL
    out = {}
    for e in games:
        d = rnd.randint(17, 23) if e["w"] else -rnd.randint(14, 19)
        before = v
        v += d
        move = ""
        if int(before // 100) != int(v // 100):
            move = f"{label_of(before // 100 * 100)} → {label_of(v // 100 * 100)}"
        out[e["id"]] = {"d": d, "now": int(v % 100), "tier": label_of(v // 100 * 100), "move": move}
    return out


def analysis_sample(gid, created_ms, my_champ=86):
    """Un análisis de partida (la forma de analysis.compute): 10 jugadores con series por minuto. Tú eres el jugador 1, arriba del equipo azul (100)."""
    rnd = random.Random(int(gid) % 10_007)
    dur = 28 * 60 + 14
    mins = list(range(0, 29))
    champs = [my_champ, 64, 103, 222, 89, 122, 23, 134, 51, 412]
    roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT"] * 2
    players = {}
    for pid in range(1, 11):
        team = 100 if pid <= 5 else 200
        base = {"TOP": 0, "JUNGLE": -1, "MIDDLE": 0, "BOTTOM": 1, "SUPPORT": -3}[roles[pid - 1]] * 0.4 + (0.2 if team == 100 else 0)
        gold, xp, cs = [0], [0], [0]
        for m in mins[1:]:
            gold.append(gold[-1] + int(rnd.randint(330, 440) * (1 + base * 0.05)))
            xp.append(xp[-1] + rnd.randint(380, 520))
            cs.append(cs[-1] + (rnd.randint(4, 9) if roles[pid - 1] not in ("SUPPORT",) else rnd.randint(0, 1)))
        lvl = [min(18, 1 + int(x / 1250)) for x in xp]
        players[str(pid)] = {"pid": pid, "champ": champs[pid - 1], "team": team, "role": roles[pid - 1], "spells": [4, 12 if roles[pid - 1] == "TOP" else 14],
                             "k": rnd.randint(1, 9), "d": rnd.randint(1, 9), "a": rnd.randint(2, 14), "dmg": rnd.randint(9000, 36000), "taken": rnd.randint(11000, 40000),
                             "gold": gold[-1], "cs": cs[-1], "jcs": 0, "vision": rnd.randint(8, 50), "lvl": lvl[-1], "items": [3068, 3047, 6694, 3071, 0, 0, 3340],
                             "win": team == 100, "gold_s": gold, "xp_s": xp, "cs_s": cs, "lvl_s": lvl,
                             "pos": [[rnd.randint(1200, 13500), rnd.randint(1200, 13500)] for _ in mins]}
    kills = []
    for _ in range(26):
        victim = rnd.randint(1, 10)
        killer = rnd.choice([p for p in range(1, 11) if (p <= 5) != (victim <= 5)])
        kills.append({"t": round(rnd.uniform(2, 27), 2), "killer": killer, "victim": victim, "assists": []})
    kills.sort(key=lambda k: k["t"])
    return {"v": 3, "gid": int(gid), "dur": dur, "me": 1, "team": 100, "win": True, "queue": 420, "created": created_ms, "minutes": mins, "players": players, "kills": kills,
            "objectives": [{"t": 7.8, "killer": 2, "assists": [], "team": 100, "what": "dragón", "type": "DRAGON"},
                           {"t": 14.1, "killer": 3, "assists": [2], "team": 100, "what": "heraldo", "type": "RIFTHERALD"},
                           {"t": 21.4, "killer": 8, "assists": [], "team": 200, "what": "dragón", "type": "DRAGON"}],
            "towers": [{"t": 14.28, "owner": 200, "killer": 2, "kind": "TOWER_BUILDING", "lane": "TOP_LANE"},
                       {"t": 19.9, "owner": 200, "killer": 3, "kind": "TOWER_BUILDING", "lane": "MID_LANE"}]}


# ---- una selección de campeón y una partida (los mismos equipos que usan las capturas) ----
SESSION = {"localPlayerCellId": 0,
           "myTeam": [{"cellId": 0, "championId": 0, "assignedPosition": "top"}, {"cellId": 1, "championId": 64, "assignedPosition": "jungle", "puuid": "fake0"},
                      {"cellId": 2, "championId": 103, "assignedPosition": "middle", "puuid": "fake1"}, {"cellId": 3, "championId": 222, "assignedPosition": "bottom", "puuid": "fake2"},
                      {"cellId": 4, "championId": 89, "assignedPosition": "utility", "puuid": "fake3"}],
           "theirTeam": [{"cellId": 5, "championId": 157, "assignedPosition": "top"}, {"cellId": 6, "championId": 23, "assignedPosition": "jungle"}],
           "bans": {"myTeamBans": [238, 60], "theirTeamBans": [99, 777, 4]},
           "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 40000, "totalTimeInPhase": 60000},
           "actions": [[{"actorCellId": 0, "type": "pick", "isInProgress": True, "completed": False}]]}

ROSTER = ([{"team": "ally", "cid": 86, "puuid": "yo", "role": "TOP", "spells": [4, 12], "me": True, "icon": 29}]
          + [{"team": "ally", "cid": c, "puuid": f"fake{n}", "role": r, "spells": [4, 14], "me": False, "icon": 1 + n}
             for n, (c, r) in enumerate(((64, "JUNGLE"), (103, "MIDDLE"), (222, "BOTTOM"), (89, "SUPPORT")))]
          + [{"team": "enemy", "cid": c, "puuid": f"fake{n}", "role": r, "spells": [4, 14], "me": False, "icon": 1 + n}
             for n, (c, r) in ((5, (157, "TOP")), (6, (23, "JUNGLE")), (7, (134, "MIDDLE")), (8, (51, "BOTTOM")), (9, (412, "SUPPORT")))])
