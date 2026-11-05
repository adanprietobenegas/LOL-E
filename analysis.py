"""Análisis de una partida ya jugada, a partir de la línea de tiempo que guarda el propio cliente de LoL (sin claves ni webs).

Datos: `/lol-match-history/v1/game-timelines/<id>` (un fotograma por minuto con oro total, experiencia, súbditos, posición y los
eventos: muertes, torres y monstruos épicos) y `/lol-match-history/v1/games/<id>` (jugadores y estadísticas finales).
Todo se calcula con restas y sumas sencillas; cada consejo dice de dónde sale.
"""
import json, os

MONSTERS = {"DRAGON": "dragón", "BARON_NASHOR": "Barón", "RIFTHERALD": "Heraldo", "HORDE": "larvas del Vacío", "ATAKHAN": "Atakhan"}


def _lane(p):
    t = p.get("timeline", {})
    lane, role = t.get("lane", ""), t.get("role", "")
    if lane == "BOTTOM":
        return "SUPPORT" if role == "SUPPORT" else "BOTTOM"
    return "" if lane in ("", "NONE") else lane


def compute(detail, tl, my_pid):
    """Series por minuto y datos clave de una partida. Devuelve un diccionario sencillo (se guarda como JSON)."""
    parts = {p["participantId"]: p for p in detail["participants"]}
    me = parts[my_pid]
    my_team = me["teamId"]
    team = {pid: p["teamId"] for pid, p in parts.items()}
    lane = _lane(me)
    opp = next((pid for pid, p in parts.items() if p["teamId"] != my_team and lane and _lane(p) == lane), None)
    frames = tl.get("frames", [])
    minutes = [round(f["timestamp"] / 60000, 1) for f in frames]
    pf = lambda f, pid, k: f["participantFrames"].get(str(pid), f["participantFrames"].get(pid, {})).get(k, 0)
    team_gold = [sum(pf(f, pid, "totalGold") for pid in parts if team[pid] == my_team) -
                 sum(pf(f, pid, "totalGold") for pid in parts if team[pid] != my_team) for f in frames]
    out = {"gid": detail["gameId"], "dur": detail["gameDuration"], "win": bool(me["stats"]["win"]), "champ": me["championId"], "lane": lane,
           "opp_champ": parts[opp]["championId"] if opp else 0, "minutes": minutes, "team_gold_diff": team_gold,
           "gold": [pf(f, my_pid, "totalGold") for f in frames], "cs": [pf(f, my_pid, "minionsKilled") + pf(f, my_pid, "jungleMinionsKilled") for f in frames],
           "xp": [pf(f, my_pid, "xp") for f in frames], "level": [pf(f, my_pid, "level") for f in frames],
           "path": [[f["participantFrames"].get(str(my_pid), {}).get("position", {}).get("x"),
                     f["participantFrames"].get(str(my_pid), {}).get("position", {}).get("y")] for f in frames]}
    if opp:
        out.update(lane_gold_diff=[pf(f, my_pid, "totalGold") - pf(f, opp, "totalGold") for f in frames],
                   lane_xp_diff=[pf(f, my_pid, "xp") - pf(f, opp, "xp") for f in frames],
                   opp_cs=[pf(f, opp, "minionsKilled") + pf(f, opp, "jungleMinionsKilled") for f in frames])
    deaths, kills, assists, obj, towers = [], [], [], [], []
    team_kills = 0
    for f in frames:
        for e in f.get("events", []):
            t, ts = e.get("type"), round(e.get("timestamp", 0) / 60000, 1)
            if t == "CHAMPION_KILL":
                if team.get(e.get("killerId")) == my_team:
                    team_kills += 1
                if e.get("victimId") == my_pid:
                    deaths.append(ts)
                if e.get("killerId") == my_pid:
                    kills.append(ts)
                elif my_pid in (e.get("assistingParticipantIds") or []):
                    assists.append(ts)
            elif t == "ELITE_MONSTER_KILL":
                obj.append({"t": ts, "mine": team.get(e.get("killerId")) == my_team, "what": MONSTERS.get(e.get("monsterType"), e.get("monsterType", "").lower())})
            elif t == "BUILDING_KILL":
                towers.append({"t": ts, "mine": e.get("teamId") != my_team})  # teamId es el equipo al que pertenecía el edificio
    st = me["stats"]
    team_dmg = sum(p["stats"].get("totalDamageDealtToChampions", 0) for p in parts.values() if p["teamId"] == my_team)
    team_vis = [p["stats"].get("visionScore", 0) for p in parts.values() if p["teamId"] == my_team]
    out.update(deaths=deaths, kills=kills, assists=assists, objectives=obj, towers=towers, team_kills=team_kills,
               kda=[st.get("kills", 0), st.get("deaths", 0), st.get("assists", 0)],
               dmg_share=(st.get("totalDamageDealtToChampions", 0) / team_dmg) if team_dmg else None,
               vision=st.get("visionScore", 0), team_vision_avg=sum(team_vis) / max(1, len(team_vis)))
    return out


def _at(series, minutes, m):
    """Valor de una serie en el minuto m (el fotograma más cercano)."""
    if not series:
        return None
    i = min(range(len(minutes)), key=lambda k: abs(minutes[k] - m))
    return series[i] if abs(minutes[i] - m) <= 1.2 else None


def advice(a, champs=None):
    """Consejos con su motivo: [(tono, título, detalle)] con tono good | bad | info."""
    out = []
    mins = a["minutes"]
    n = lambda x: f"{abs(int(round(x))):,}".replace(",", ".")
    name = lambda cid: (champs or {}).get(cid, {}).get("name", "tu rival")
    lg = a.get("lane_gold_diff")
    if lg and a["lane"]:
        g10 = _at(lg, mins, 10)
        if g10 is not None:
            who = name(a["opp_champ"])
            if g10 <= -600:
                out.append(("bad", "Perdiste la línea al principio", f"A minuto 10 ibas {n(g10)} de oro por debajo de {who}. "
                            "Mira en «Plan» sus puntos fuertes y la build contra él, o juega más seguro hasta tener tus objetos."))
            elif g10 >= 600:
                out.append(("good", "Ganaste la línea", f"A minuto 10 ibas {n(g10)} de oro por encima de {who}. Aprovéchalo para presionar objetivos."))
            else:
                out.append(("info", "Línea igualada", f"A minuto 10 la diferencia con {who} era de {n(g10)} de oro: nadie despegó."))
    if a["lane"] != "JUNGLE" and a["lane"] != "SUPPORT" and a.get("opp_cs") and len(a["cs"]) > 10:
        c10, o10 = _at(a["cs"], mins, 10), _at(a["opp_cs"], mins, 10)
        if c10 is not None and o10 is not None:
            if c10 < 55:
                out.append(("bad", "Farmeo bajo", f"{c10} súbditos a minuto 10 ({c10 / 10:.1f} por minuto). Una referencia habitual es 7 por minuto; "
                            f"tu rival llevaba {o10}."))
            elif c10 >= 70:
                out.append(("good", "Buen farmeo", f"{c10} súbditos a minuto 10 ({c10 / 10:.1f} por minuto), tu rival llevaba {o10}."))
    early = [d for d in a["deaths"] if d <= 15]
    if len(early) >= 2:
        out.append(("bad", f"{len(early)} muertes antes del minuto 15", "Cada muerte temprana regala oro y experiencia. Si te pasa a menudo, "
                    "reduce los cambios arriesgados mientras tu rival tenga habilidades listas."))
    elif not a["deaths"]:
        out.append(("good", "Sin muertes", "No moriste en toda la partida."))
    tg = a["team_gold_diff"]
    if tg:
        best_i = max(range(len(tg)), key=lambda i: tg[i])
        worst_i = min(range(len(tg)), key=lambda i: tg[i])
        end = tg[-1]
        if tg[best_i] >= 2500 and end < tg[best_i] - 2000:
            out.append(("bad", "Perdisteis una ventaja", f"Llegasteis a +{n(tg[best_i])} de oro de equipo a minuto {mins[best_i]:.0f} y acabasteis en "
                        f"{'+' if end >= 0 else '−'}{n(end)}. Con ventaja, cerrad objetivos (torres, dragón, Barón) antes de que se igualen los objetos."))
        elif tg[worst_i] <= -2500 and end > tg[worst_i] + 2000:
            out.append(("good", "Remontada", f"Ibais {n(tg[worst_i])} de oro por debajo a minuto {mins[worst_i]:.0f} y lo recuperasteis."))
    mine_o = [o for o in a["objectives"] if o["mine"]]
    their_o = [o for o in a["objectives"] if not o["mine"]]
    if a["objectives"]:
        out.append(("good" if len(mine_o) >= len(their_o) else "bad", "Objetivos épicos",
                    f"Tu equipo: {len(mine_o)} · rival: {len(their_o)} (dragones, Heraldo, Barón…)."))
    if a["towers"]:
        mt, tt = sum(1 for t in a["towers"] if t["mine"]), sum(1 for t in a["towers"] if not t["mine"])
        out.append(("good" if mt >= tt else "bad", "Edificios", f"Derribasteis {mt} y os derribaron {tt}."))
    k, d, s = a["kda"]
    if a["team_kills"]:
        kp = (k + s) / a["team_kills"]
        out.append(("good" if kp >= .6 else "info" if kp >= .4 else "bad", "Participación en muertes",
                    f"{kp * 100:.0f} % de las muertes de tu equipo ({k + s} de {a['team_kills']})."))
    if a["dmg_share"] is not None:
        out.append(("info", "Daño a campeones", f"{a['dmg_share'] * 100:.0f} % del daño de tu equipo."))
    if a["lane"] == "SUPPORT" and a["vision"] < a["team_vision_avg"] * 1.2:
        out.append(("bad", "Visión", f"Tu puntuación de visión ({a['vision']}) fue baja para un apoyo; la media de tu equipo es {a['team_vision_avg']:.0f}."))
    return out


def load(lcu, gid, my_puuid, cache_dir):
    """Análisis de la partida `gid`, guardado en caché; None si el cliente ya no guarda su línea de tiempo."""
    path = os.path.join(cache_dir, "analysis", f"{gid}.json")
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        pass
    detail = lcu.get(f"/lol-match-history/v1/games/{gid}", timeout=20)
    tl = lcu.get(f"/lol-match-history/v1/game-timelines/{gid}", timeout=30)
    if not detail or not tl or not tl.get("frames"):
        return None
    ident = next((i for i in detail["participantIdentities"] if i["player"].get("puuid") == my_puuid), None)
    my_pid = ident["participantId"] if ident else detail["participants"][0]["participantId"]
    a = compute(detail, tl, my_pid)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(a, open(path, "w", encoding="utf-8"))
    return a
