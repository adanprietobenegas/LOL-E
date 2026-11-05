"""Análisis de una partida ya jugada, a partir de la línea de tiempo que guarda el propio cliente de LoL (sin claves ni webs).

Datos: `/lol-match-history/v1/game-timelines/<id>` (un fotograma por minuto con oro total, experiencia, súbditos, posición y los
eventos: muertes, torres y monstruos épicos) y `/lol-match-history/v1/games/<id>` (jugadores y estadísticas finales).

Rival directo: el cliente etiqueta mal las líneas (en una partida real marcaba como «jungla» a los dos de superior). Aquí la línea de
cada jugador se deduce de lo que hizo de verdad: el jungla lleva Smite (y más monstruos), y el resto se reparte por dónde estuvo entre
los minutos 3 y 9 (arriba a la izquierda = superior, abajo a la derecha = tirador/apoyo, centro = central). Todo son restas y umbrales
sencillos; cada consejo enseña el dato en que se basa.
"""
import json, os, statistics

VERSION = 3
SMITE = 11
MONSTERS = {"DRAGON": "dragón", "BARON_NASHOR": "Barón", "RIFTHERALD": "Heraldo", "HORDE": "larvas del Vacío", "ATAKHAN": "Atakhan"}
ROLE_ES = {"TOP": "Superior", "JUNGLE": "Jungla", "MIDDLE": "Central", "BOTTOM": "Tirador", "SUPPORT": "Apoyo"}
CHECK = (5, 10, 15, 20)


# ------------------------------------------------------------------ líneas
def _legacy(p):
    t = p.get("timeline", {})
    lane, role = t.get("lane", ""), t.get("role", "")
    if lane == "BOTTOM":
        return "SUPPORT" if role == "SUPPORT" else "BOTTOM"
    return "" if lane in ("", "NONE") else lane


def _pos(frames, pid, lo=3, hi=9):
    xs, ys = [], []
    for f in frames[lo:hi + 1]:
        p = (f["participantFrames"].get(str(pid)) or {}).get("position")
        if p:
            xs.append(p["x"])
            ys.append(p["y"])
    return (statistics.median(xs), statistics.median(ys)) if xs else None


def infer_roles(parts, frames):
    """{participantId: línea}. Jungla = Smite + más monstruos; el resto, por posición en los minutos 3-9."""
    roles = {}
    for team in sorted({p["teamId"] for p in parts}):
        ps = [p for p in parts if p["teamId"] == team]
        smiters = [p for p in ps if SMITE in (p.get("spell1Id"), p.get("spell2Id"))]
        jung = max(smiters or ps, key=lambda p: p["stats"].get("neutralMinionsKilled", 0))
        roles[jung["participantId"]] = "JUNGLE"
        rest = [p for p in ps if p is not jung]
        lanes = {}
        for p in rest:
            pos = _pos(frames, p["participantId"])
            if pos is None:
                lanes[p["participantId"]] = None
            else:
                x, y = pos
                lanes[p["participantId"]] = "TOP" if y - x > 4500 else "BOTTOM" if x - y > 4500 else "MIDDLE"
        cnt = {k: sum(1 for v in lanes.values() if v == k) for k in ("TOP", "MIDDLE", "BOTTOM")}
        if (cnt["TOP"], cnt["MIDDLE"], cnt["BOTTOM"]) != (1, 1, 2):  # partida rara (líneas cambiadas): se usan las etiquetas del cliente
            for p in rest:
                lg = _legacy(p)
                lanes[p["participantId"]] = {"TOP": "TOP", "MIDDLE": "MIDDLE", "BOTTOM": "BOTTOM", "SUPPORT": "BOTTOM", "JUNGLE": "TOP"}.get(lg, "MIDDLE")
        bot = [p for p in rest if lanes[p["participantId"]] == "BOTTOM"]
        for p in rest:
            roles[p["participantId"]] = lanes[p["participantId"]]
        if len(bot) >= 2:  # el apoyo es quien menos súbditos hace (o el que el cliente marca como apoyo)
            sup = next((p for p in bot if p.get("timeline", {}).get("role") == "SUPPORT"), None) or min(bot, key=lambda p: p["stats"].get("totalMinionsKilled", 0))
            roles[sup["participantId"]] = "SUPPORT"
    return roles


# ------------------------------------------------------------------ cálculo
def compute(detail, tl, my_pid):
    """Todo lo que hace falta de una partida, en un diccionario sencillo (se guarda como JSON)."""
    parts = {p["participantId"]: p for p in detail["participants"]}
    frames = tl.get("frames", [])
    roles = infer_roles(detail["participants"], frames)
    team = {pid: p["teamId"] for pid, p in parts.items()}
    pf = lambda f, pid, k: (f["participantFrames"].get(str(pid)) or {}).get(k, 0)
    a = {"v": VERSION, "gid": detail["gameId"], "dur": detail["gameDuration"], "me": my_pid, "team": team[my_pid],
         "win": bool(parts[my_pid]["stats"]["win"]), "queue": detail.get("queueId"), "created": detail.get("gameCreation"),
         "minutes": [round(f["timestamp"] / 60000, 1) for f in frames], "players": {}}
    for pid, p in parts.items():
        st = p["stats"]
        a["players"][str(pid)] = {
            "pid": pid, "champ": p["championId"], "team": p["teamId"], "role": roles.get(pid, ""), "spells": [p.get("spell1Id"), p.get("spell2Id")],
            "k": st.get("kills", 0), "d": st.get("deaths", 0), "a": st.get("assists", 0), "dmg": st.get("totalDamageDealtToChampions", 0),
            "taken": st.get("totalDamageTaken", 0), "gold": st.get("goldEarned", 0), "cs": st.get("totalMinionsKilled", 0) + st.get("neutralMinionsKilled", 0),
            "jcs": st.get("neutralMinionsKilled", 0), "vision": st.get("visionScore", 0), "lvl": st.get("champLevel", 0),
            "items": [st.get(f"item{i}", 0) for i in range(7)], "win": bool(st.get("win")),
            "gold_s": [pf(f, pid, "totalGold") for f in frames], "xp_s": [pf(f, pid, "xp") for f in frames],
            "cs_s": [pf(f, pid, "minionsKilled") + pf(f, pid, "jungleMinionsKilled") for f in frames],
            "lvl_s": [pf(f, pid, "level") for f in frames],
            "pos": [[(f["participantFrames"].get(str(pid)) or {}).get("position", {}).get("x"),
                     (f["participantFrames"].get(str(pid)) or {}).get("position", {}).get("y")] for f in frames]}
    kills, objs, towers = [], [], []
    for f in frames:
        for e in f.get("events", []):
            t, ts = e.get("type"), round(e.get("timestamp", 0) / 60000, 2)
            if t == "CHAMPION_KILL":
                kills.append({"t": ts, "killer": e.get("killerId", 0), "victim": e.get("victimId", 0), "assists": e.get("assistingParticipantIds") or []})
            elif t == "ELITE_MONSTER_KILL":
                objs.append({"t": ts, "killer": e.get("killerId", 0), "assists": e.get("assistingParticipantIds") or [],
                             "team": team.get(e.get("killerId")), "what": MONSTERS.get(e.get("monsterType"), (e.get("monsterType") or "").lower()),
                             "type": e.get("monsterType")})
            elif t == "BUILDING_KILL":
                towers.append({"t": ts, "owner": e.get("teamId"), "killer": e.get("killerId", 0), "kind": e.get("buildingType", ""), "lane": e.get("laneType", "")})
    a.update(kills=kills, objectives=objs, towers=towers)
    return a


# ------------------------------------------------------------------ consultas
def me(a):
    return a["players"][str(a["me"])]


def player(a, pid):
    return a["players"].get(str(pid))


def enemies(a):
    return [p for p in a["players"].values() if p["team"] != a["team"]]


def mates(a):
    return [p for p in a["players"].values() if p["team"] == a["team"]]


def default_opp(a):
    """Rival directo: el del equipo contrario con tu misma línea."""
    m = me(a)
    return next((p["pid"] for p in enemies(a) if p["role"] == m["role"]), None)


def at(a, series, m):
    """Valor de una serie en el minuto m (fotograma más cercano; None si no hay)."""
    mins = a["minutes"]
    if not series or not mins:
        return None
    i = min(range(len(mins)), key=lambda k: abs(mins[k] - m))
    return series[i] if abs(mins[i] - m) <= 1.2 else None


def team_gold_diff(a):
    mine = [p["gold_s"] for p in mates(a)]
    their = [p["gold_s"] for p in enemies(a)]
    return [sum(s[i] for s in mine) - sum(s[i] for s in their) for i in range(len(a["minutes"]))]


def diff(a, key, pid_a, pid_b):
    sa, sb = player(a, pid_a)[key], player(a, pid_b)[key]
    return [x - y for x, y in zip(sa, sb)]


def checkpoints(a, opp):
    """Comparación con el rival en los minutos 5, 10, 15, 20 y al final: {minuto: {oro, exp, cs, nivel: (tú, rival)}}."""
    m, o = me(a), player(a, opp)
    out = {}
    for c in CHECK:
        row = {}
        for k, key in (("gold", "gold_s"), ("xp", "xp_s"), ("cs", "cs_s"), ("lvl", "lvl_s")):
            x, y = at(a, m[key], c), at(a, o[key], c)
            if x is not None and y is not None:
                row[k] = (x, y)
        if row:
            out[c] = row
    out["final"] = {"gold": (m["gold"], o["gold"]), "cs": (m["cs"], o["cs"]), "lvl": (m["lvl"], o["lvl"]),
                    "xp": (m["xp_s"][-1], o["xp_s"][-1])}
    return out


# ------------------------------------------------------------------ consejos
def _n(x):
    return f"{abs(int(round(x))):,}".replace(",", ".")


def _sg(x):
    return ("+" if x >= 0 else "−") + _n(x)


def advice(a, opp, champs=None):
    """Consejos [{tone, title, detail, data, w}] ordenados por importancia. tone: good | bad | info."""
    name = lambda pid: (champs or {}).get((player(a, pid) or {}).get("champ"), {}).get("name", "tu rival")
    m, role = me(a), me(a)["role"]
    o = player(a, opp) if opp else None
    out = []

    def add(tone, title, detail, data, w):
        out.append({"tone": tone, "title": title, "detail": detail, "data": data, "w": w})
    mins = a["minutes"]
    # --- fase inicial contra tu rival directo
    if o and role != "SUPPORT":
        zone = "en la jungla" if role == "JUNGLE" else "en tu línea"
        g10, x10 = at(a, diff(a, "gold_s", m["pid"], opp), 10), at(a, diff(a, "xp_s", m["pid"], opp), 10)
        g15 = at(a, diff(a, "gold_s", m["pid"], opp), 15)
        if g10 is not None:
            data = f"Minuto 10 contra {name(opp)}: oro {_sg(g10)}" + (f", experiencia {_sg(x10)}" if x10 is not None else "") + \
                   (f". Minuto 15: oro {_sg(g15)}." if g15 is not None else ".")
            if g10 <= -600:
                add("bad", f"Perdiste el inicio {zone}", "Empezar por detrás complica todo lo demás: revisa en «Plan» sus puntos fuertes, o juega más seguro hasta tener tus objetos.", data, 90)
            elif g10 >= 600:
                add("good", f"Ganaste el inicio {zone}", "Aprovecha esa ventaja para presionar objetivos y no dejar que se iguale.", data, 60)
            else:
                add("info", f"Inicio igualado {zone}", f"Nadie despegó a minuto 10 frente a {name(opp)}: la partida se decidió después.", data, 30)
    # --- farmeo
    if o and role in ("TOP", "MIDDLE", "BOTTOM"):
        c10, oc10 = at(a, m["cs_s"], 10), at(a, o["cs_s"], 10)
        if c10 is not None and oc10 is not None:
            data = f"Minuto 10: {c10} súbditos ({c10 / 10:.1f} por minuto) frente a {oc10} de {name(opp)}. Final: {m['cs']} frente a {o['cs']}."
            if c10 - oc10 <= -10:
                add("bad", "Farmeo por debajo de tu rival", "Cada súbdito perdido son unos 20 de oro: intenta rematar con el ataque básico y no dejar morir olas.", data, 70)
            elif c10 - oc10 >= 10:
                add("good", "Farmeo por encima de tu rival", "Buen control de las olas.", data, 40)
            elif c10 < 55:
                add("bad", "Farmeo bajo", "Como referencia, 7 por minuto es un buen ritmo; practica rematar súbditos.", data, 55)
    if o and role == "JUNGLE":
        data = f"Monstruos de jungla: {m['jcs']} frente a {o['jcs']} de {name(opp)} (súbditos: {m['cs'] - m['jcs']} y {o['cs'] - o['jcs']})."
        if o["jcs"] and m["jcs"] < o["jcs"] * 0.8:
            add("bad", "Farmeaste menos jungla que tu rival", "Menos campamentos son menos oro y nivel. Una ruta más eficiente o menos viajes a líneas ayudan; el recorrido está en la pestaña «Recorrido».", data, 65)
        elif o["jcs"] and m["jcs"] > o["jcs"] * 1.2:
            add("good", "Farmeaste más jungla que tu rival", "Buen aprovechamiento de los campamentos.", data, 40)
    # --- muertes
    early = [k for k in a["kills"] if k["victim"] == m["pid"] and k["t"] <= 15]
    deaths = [k for k in a["kills"] if k["victim"] == m["pid"]]
    if len(early) >= 2:
        add("bad", f"{len(early)} muertes antes del minuto 15", "Cada muerte temprana regala oro y experiencia y te hace perder oleadas o monstruos.",
            "Minutos: " + ", ".join(f"{k['t']:.0f}" for k in early) + ".", 80)
    if deaths:
        costly = []
        for k in deaths:  # muerte seguida (en 45 s) de un objetivo o una torre del rival
            evs = [x for x in a["objectives"] if x.get("team") != a["team"]] + [{"t": t_["t"], "what": "torre"} for t_ in a["towers"] if t_["owner"] == a["team"]]
            for ev in evs:
                if 0 <= ev["t"] - k["t"] <= 0.75:
                    costly.append((k["t"], ev["what"]))
                    break
        if len(costly) >= 2:
            add("bad", "Muertes que costaron objetivos", "Morir justo antes de un objetivo lo regala. Si no tienes visión o tu equipo no está, espera.",
                "Tras tus muertes en los minutos " + ", ".join(f"{t:.0f} ({w})" for t, w in costly[:5]) + " el rival cogió un objetivo en menos de 45 s.", 85)
    if not deaths:
        add("good", "Sin muertes", "No moriste en toda la partida.", "", 50)
    elif o and m["d"] <= o["d"] - 3:
        add("good", "Moriste mucho menos que tu rival", "Jugaste seguro.", f"Muertes: {m['d']} frente a {o['d']} de {name(opp)}.", 35)
    elif o and m["d"] >= o["d"] + 5:
        add("bad", "Moriste bastante más que tu rival", "Muertes de más son oro y experiencia para él.", f"Muertes: {m['d']} frente a {o['d']} de {name(opp)}.", 72)
    # --- equipo
    tg = team_gold_diff(a)
    if tg:
        i15 = min(range(len(mins)), key=lambda i: abs(mins[i] - 15))
        best, worst, end = max(tg), min(tg), tg[-1]
        ib, iw = tg.index(best), tg.index(worst)
        if best >= 2500 and end < best - 2000:
            add("bad", "Perdisteis una ventaja", "Con ventaja, cerrad objetivos (torres, dragón, Barón) antes de que los objetos se igualen.",
                f"Llegasteis a {_sg(best)} de oro a minuto {mins[ib]:.0f} y acabasteis en {_sg(end)}.", 88)
        elif worst <= -2500 and end > worst + 2000:
            add("good", "Remontada", "Aguantasteis y la partida se dio la vuelta.", f"Ibais {_sg(worst)} de oro a minuto {mins[iw]:.0f} y acabasteis en {_sg(end)}.", 55)
        elif abs(tg[i15]) >= 2000:
            add("good" if tg[i15] > 0 else "bad", "Estado de la partida a minuto 15", "Quien llega por delante al medio de la partida suele marcar el ritmo.",
                f"Diferencia de oro de equipo a minuto 15: {_sg(tg[i15])}.", 45)
    ours = [x for x in a["objectives"] if x["team"] == a["team"]]
    theirs = [x for x in a["objectives"] if x["team"] != a["team"]]
    if a["objectives"]:
        joined = sum(1 for x in ours if m["pid"] == x["killer"] or m["pid"] in x["assists"])
        data = f"Tu equipo {len(ours)} y el rival {len(theirs)}. Tú participaste en {joined} de los {len(ours)} de tu equipo."
        weight = 75 if role in ("JUNGLE", "SUPPORT") else 38
        if len(ours) < len(theirs):
            add("bad", "Perdisteis la lucha por los objetivos épicos", "Dragones, Heraldo, Barón y larvas dan ventajas que se acumulan.", data, weight)
        elif role == "JUNGLE" and ours and joined < len(ours) * 0.6:
            add("bad", "Poca presencia en los objetivos de tu equipo", "Como jungla, tu sitio está en ellos: llega con tiempo y pon visión.", data, weight)
        else:
            add("good" if len(ours) > len(theirs) else "info", "Objetivos épicos", "", data, 36)
    kteam = sum(1 for k in a["kills"] if player(a, k["killer"]) and player(a, k["killer"])["team"] == a["team"])
    if kteam:
        kp = (m["k"] + m["a"]) / kteam
        exp = 0.65 if role in ("JUNGLE", "SUPPORT") else 0.5
        add("good" if kp >= exp else "bad" if kp < exp - 0.2 else "info", "Participación en muertes",
            "Estar en las peleas es la base de ganarlas." if kp < exp else "Estuviste en el centro de las peleas de tu equipo.",
            f"{kp * 100:.0f} % de las muertes de tu equipo ({m['k'] + m['a']} de {kteam}).", 60 if kp < exp - 0.2 else 30)
    # --- visión y daño
    if o and role == "SUPPORT":
        add("good" if m["vision"] >= o["vision"] else "bad" if m["vision"] < o["vision"] * 0.8 else "info", "Visión",
            "La visión es tu aportación principal: balizas de control y centinelas antes de cada objetivo." if m["vision"] < o["vision"] else "",
            f"Puntuación de visión: {m['vision']} frente a {o['vision']} de {name(opp)} (media de tu equipo: "
            f"{sum(p['vision'] for p in mates(a)) / 5:.0f}).", 68 if m["vision"] < o["vision"] * 0.8 else 32)
    elif role != "SUPPORT":
        avg = sum(p["vision"] for p in mates(a)) / 5
        if avg and m["vision"] < avg * 0.6:
            add("bad", "Poca visión", "Colocar y limpiar centinelas da información y evita emboscadas.",
                f"Tu puntuación de visión fue {m['vision']}, la media de tu equipo {avg:.0f}.", 45)
    if role in ("TOP", "MIDDLE", "BOTTOM"):
        tdmg, tgold = sum(p["dmg"] for p in mates(a)), sum(p["gold"] for p in mates(a))
        if tdmg and tgold and m["gold"] / tgold >= 0.2 and m["dmg"] / tdmg < 0.14:
            add("bad", "Poco daño para el oro que tuviste", "Con tanto oro se espera más impacto en las peleas: posición segura y objetos de daño.",
                f"{m['dmg'] / tdmg * 100:.0f} % del daño de tu equipo con el {m['gold'] / tgold * 100:.0f} % de su oro.", 58)
    out.sort(key=lambda x: -x["w"])
    return out


# ------------------------------------------------------------------ carga
def load(lcu, gid, my_puuid, cache_dir):
    """Análisis de la partida `gid`, guardado en caché; None si el cliente ya no guarda su línea de tiempo."""
    path = os.path.join(cache_dir, "analysis", f"{gid}.json")
    try:
        saved = json.load(open(path, encoding="utf-8"))
        if saved.get("v") == VERSION:
            return saved
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
