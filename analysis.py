"""Análisis de una partida ya jugada, a partir de la línea de tiempo que guarda el propio cliente de LoL (sin claves ni webs).

Datos: `/lol-match-history/v1/game-timelines/<id>` (un fotograma por minuto con oro total, experiencia, súbditos, posición y los
eventos: muertes, torres y monstruos épicos) y `/lol-match-history/v1/games/<id>` (jugadores y estadísticas finales).

Rival directo: el cliente etiqueta mal las líneas (en una partida real marcaba como «jungla» a los dos de superior). Aquí la línea de
cada jugador se deduce de lo que hizo de verdad: el jungla lleva Smite (y más monstruos), y el resto se reparte por dónde estuvo entre
los minutos 3 y 9 (arriba a la izquierda = superior, abajo a la derecha = tirador/apoyo, centro = central). Todo son restas y umbrales
sencillos; cada consejo enseña el dato en que se basa.
"""
import json, os, statistics

import history

VERSION = 5
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
            "jcs": st.get("neutralMinionsKilled", 0), "aug": [st.get(f"playerAugment{i}", 0) for i in range(1, 7) if st.get(f"playerAugment{i}", 0)],
            "ks": st.get("largestKillingSpree", 0), "mk": st.get("largestMultiKill", 0), "pk": st.get("pentaKills", 0), "qk": st.get("quadraKills", 0),
            "tk3": st.get("tripleKills", 0), "heal": st.get("totalHeal", 0), "cc": st.get("totalTimeCrowdControlDealt", 0), "mit": st.get("damageSelfMitigated", 0),
            "dtur": st.get("damageDealtToTurrets", 0), "phys": st.get("physicalDamageDealtToChampions", 0), "magic": st.get("magicDamageDealtToChampions", 0),
            "true": st.get("trueDamageDealtToChampions", 0), "taken_p": st.get("physicalDamageTaken", 0), "taken_m": st.get("magicalDamageTaken", 0),
            "fb": bool(st.get("firstBloodKill")), "life": st.get("longestTimeSpentLiving", 0), "vision": st.get("visionScore", 0), "lvl": st.get("champLevel", 0),
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


ARAM_QUEUES = {450, 2400}


def default_opp(a):
    """Rival directo: el del equipo contrario con tu misma línea."""
    m = me(a)
    if a.get("queue") in ARAM_QUEUES:   # sin líneas: el rival que más daño hizo
        return max(enemies(a), key=lambda p: p["dmg"], default={}).get("pid")
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


def _rank(a, key, pid, team_only=False):
    """Puesto (1 = el que más) de un jugador en una cifra, entre los 10 o entre su equipo."""
    pool = [p for p in a["players"].values() if not team_only or p["team"] == player(a, pid)["team"]]
    vals = sorted((p[key] for p in pool), reverse=True)
    return vals.index(player(a, pid)[key]) + 1, len(pool)


def advice_aram(a, champs=None):
    """Datos interesantes de una partida de ARAM (sin líneas, sin objetivos de rankeds): daño, aguante, rachas, curación, control, torres y mejoras."""
    m = me(a)
    out = []

    def add(tone, title, detail, data, w):
        out.append({"tone": tone, "title": title, "detail": detail, "data": data, "w": w})
    team = mates(a)
    mins = max(1.0, a["dur"] / 60)
    # --- daño
    tdmg = sum(p["dmg"] for p in team) or 1
    r, n_ = _rank(a, "dmg", m["pid"])
    tot = (m["phys"] + m["magic"] + m["true"]) or 1
    mix = f"físico {m['phys'] / tot * 100:.0f} %, mágico {m['magic'] / tot * 100:.0f} %" + (f", verdadero {m['true'] / tot * 100:.0f} %" if m["true"] / tot >= .05 else "")
    data = f"{m['dmg']:,} de daño a campeones".replace(",", ".") + f" ({m['dmg'] / tdmg * 100:.0f} % de tu equipo, {r}.º de {n_}): {mix}."
    if r == 1:
        add("good", "El que más daño hizo de la partida", "Tu campeón brilló en las peleas.", data, 90)
    elif r <= 3:
        add("good", "Entre los que más daño hicieron", "", data, 70)
    else:
        add("info", "Tu daño", "Lo que haces en ARAM depende mucho de cuánto vives en la pelea y de a quién llegas.", data, 40)
    # --- aguante
    tt = sum(p["taken"] for p in team) or 1
    rt, _n = _rank(a, "taken", m["pid"])
    dat = f"Recibiste {m['taken']:,} de daño ({m['taken'] / tt * 100:.0f} % de tu equipo, {rt}.º de {n_})".replace(",", ".") + (f" y mitigaste {m['mit']:,} con escudos y resistencias".replace(",", ".") if m["mit"] else "") + "."
    if rt == 1 and m["taken"] / tt >= .25:
        add("info", "Fuiste el que más golpes recibió", "Si además sobreviviste, abriste las peleas para tu equipo.", dat, 66)
    elif rt >= 8:
        add("info", "Casi no recibiste daño", "O jugaste desde atrás con seguridad o llegaste tarde a las peleas.", dat, 30)
    # --- KDA y muertes
    kda = (m["k"] + m["a"]) / max(1, m["d"])
    rk, nk = _rank(a, "k", m["pid"], True)
    kdas = sorted(((p["k"] + p["a"]) / max(1, p["d"]), p["pid"]) for p in team)
    best_kda = kdas[-1][1] == m["pid"]
    worst_d = max(team, key=lambda p: p["d"])
    if best_kda:
        add("good", "Mejor KDA de tu equipo", "", f"KDA {kda:.2f} ({m['k']} / {m['d']} / {m['a']}).".replace(".", ",", 1), 62)
    elif worst_d["pid"] == m["pid"] and m["d"] >= 10:
        add("info", "El que más murió de tu equipo", "En ARAM morir es normal, pero hay que volver a la pelea con objetos.", f"{m['d']} muertes en {mins:.0f} minutos.", 45)
    else:
        add("info", "Tu KDA", "", f"KDA {kda:.2f} ({m['k']} / {m['d']} / {m['a']}).".replace(".", ",", 1), 25)
    # --- rachas y multikills
    if m["pk"]:
        add("good", f"{'¡PENTAKILL!' if m['pk'] == 1 else str(m['pk']) + ' pentakills'}", "Cinco rivales abatidos seguidos.", "", 100)
    elif m["qk"]:
        add("good", "Cuádruple muerte", "Casi un pentakill.", f"{m['qk']} vez/veces.", 80)
    elif m["tk3"]:
        add("good", "Triple muerte", "", f"{m['tk3']} vez/veces.", 60)
    if m["ks"] >= 4:
        add("good", f"Racha de {m['ks']} muertes sin morir", "", "", 58)
    # --- participación
    kteam = sum(1 for k in a["kills"] if player(a, k["killer"]) and player(a, k["killer"])["team"] == a["team"])
    if kteam:
        kp = (m["k"] + m["a"]) / kteam
        add("good" if kp >= .65 else "info", "Participación en las peleas",
            "Estuviste en casi todas las muertes de tu equipo." if kp >= .75 else "", f"{kp * 100:.0f} % de las muertes de tu equipo ({m['k'] + m['a']} de {kteam}).", 50 if kp >= .65 else 28)
    # --- curación y control
    rh, _x = _rank(a, "heal", m["pid"])
    if m["heal"] >= 6000 or rh == 1 and m["heal"] >= 3000:
        add("good" if rh <= 2 else "info", "Curación", "", f"Te curaste {m['heal']:,} de vida ({rh}.º de {n_}).".replace(",", "."), 48)
    rc, _x = _rank(a, "cc", m["pid"])
    if m["cc"] >= 60:
        add("good" if rc <= 2 else "info", "Control de masas", "", f"{m['cc'] // 60} min {m['cc'] % 60} s de control sobre rivales ({rc}.º de {n_}).", 46 if rc <= 2 else 26)
    # --- torres y marcha de la partida
    ours = [t for t in a["towers"] if t["owner"] != a["team"]]
    theirs = [t for t in a["towers"] if t["owner"] == a["team"]]
    if a["towers"]:
        add("good" if len(ours) > len(theirs) else "info", "Estructuras", "", f"Tu equipo derribó {len(ours)} y el rival {len(theirs)}.", 34)
    tg = team_gold_diff(a)
    if tg and a["minutes"]:
        ib, iw = tg.index(max(tg)), tg.index(min(tg))
        best, worst, end = max(tg), min(tg), tg[-1]
        if best >= 2500 and end < best - 2000:
            add("info", "Se escapó una ventaja", "", f"Ibais +{best:,} de oro a minuto {a['minutes'][ib]:.0f} y acabasteis en {_sg(end)}.".replace(",", "."), 64)
        elif worst <= -2500 and end > worst + 2000:
            add("good", "Remontada", "Aguantasteis y la partida se dio la vuelta.", f"Ibais {_sg(worst)} de oro a minuto {a['minutes'][iw]:.0f} y acabasteis en {_sg(end)}.", 74)
    # --- primera sangre
    if m["fb"]:
        add("good", "Primera sangre", "Fuiste el primero en abatir a un rival.", "", 44)
    # --- mejoras (Mayhem)
    if m.get("aug"):
        try:
            import augments
            names = ", ".join(f"{augments.info(x)['n']} ({augments.info(x)['r'].lower() or '—'})" for x in m["aug"])
        except Exception:
            names = ""
        if names:
            add("info", "Tus mejoras", "Las que elegiste en esta partida.", names, 56)
    out.sort(key=lambda x: -x["w"])
    return out


def advice(a, opp, champs=None):
    """Consejos [{tone, title, detail, data, w}] ordenados por importancia. tone: good | bad | info."""
    if a.get("queue") in ARAM_QUEUES:
        return advice_aram(a, champs)
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
SR_QUEUES = {400, 420, 430, 440, 480, 490, 700, 710}   # las de la Grieta (la misma lista que lol_advisor.SR_QUEUES)


def _mode_key(q):
    return "aram" if q in ARAM_QUEUES else "sr" if q in SR_QUEUES else q


def vs_average(game, games, min_games=3):
    """Compara UNA partida tuya con tu media. `game` y `games` son registros de history.py (c campeón, q cola, k/de/a, cs, d duración,
    rm rehecha). La media es con ese campeón si hay al menos `min_games` partidas más con él; si no, con las demás del mismo modo.
    Devuelve {scope: «champ»|«mode», n, kda: (esta, media), cspm: (esta, media)|None, wins: (victorias, n)} o None si no hay con qué
    comparar. KDA = (bajas + asistencias) / max(1, muertes), con la media sobre la suma de todas (no la media de cocientes)."""
    if not game or game.get("k") is None:
        return None
    otras = [g for g in games or [] if g.get("id") != game.get("id") and g.get("k") is not None and not g.get("rm")]
    mismas = [g for g in otras if g.get("c") == game.get("c") and _mode_key(g.get("q")) == _mode_key(game.get("q"))]
    if len(mismas) >= min_games:
        pool, scope = mismas, "champ"
    else:
        pool, scope = [g for g in otras if _mode_key(g.get("q")) == _mode_key(game.get("q"))], "mode"
        if len(pool) < min_games:
            return None

    def kda(rows):
        return (sum(g["k"] + g["a"] for g in rows)) / max(1, sum(g["de"] for g in rows))

    def cspm(rows):
        mins = sum(g["d"] / 60 for g in rows if g.get("d") and g.get("cs") is not None)
        return sum(g["cs"] for g in rows if g.get("d") and g.get("cs") is not None) / mins if mins else None
    cs_this = cspm([game]) if _mode_key(game.get("q")) != "aram" else None
    cs_avg = cspm(pool) if cs_this is not None else None
    return {"scope": scope, "n": len(pool), "kda": (kda([game]), kda(pool)),
            "cspm": (cs_this, cs_avg) if cs_this is not None and cs_avg else None, "wins": (sum(1 for g in pool if g.get("w")), len(pool))}


def average_lines(cmp, champ_name=""):
    """Frases (texto, tono «good»/«bad»/«dim») a partir de `vs_average`. Solo marca bueno o malo si se aleja un 25 % o más de tu media."""
    if not cmp:
        return []
    donde = f"con {champ_name} ({cmp['n']} partidas)" if cmp["scope"] == "champ" and champ_name else f"en este modo ({cmp['n']} partidas)"

    def tono(esta, media):
        return "good" if esta >= media * 1.25 else "bad" if esta <= media * 0.75 else "dim"

    def fmt(x):
        return f"{x:.1f}".replace(".", ",")
    ke, km = cmp["kda"]
    out = [(f"KDA {fmt(ke)} frente a tu media de {fmt(km)} {donde}.", tono(ke, km))]
    if cmp.get("cspm"):
        ce, cm = cmp["cspm"]
        out.append((f"Farmeo {fmt(ce)} cs/min frente a {fmt(cm)}.", tono(ce, cm)))
    return out


def headline(a, items):
    """Una frase con la conclusión de la partida, a partir de los mismos datos que los consejos (no añade juicio propio).
    En una derrota manda lo que más pesó; en una victoria, lo mejor. Vacía si no hay nada destacable."""
    bad = [x["title"] for x in items or [] if x.get("tone") == "bad"][:2]
    good = [x["title"] for x in items or [] if x.get("tone") == "good"][:2]
    if not bad and not good:
        return ""

    def junta(ts):
        ts = [t[:1].lower() + t[1:] for t in ts]
        return " y ".join(ts)
    if a.get("win"):
        s = ("Victoria. Lo mejor: " + junta(good) + "." if good else "Victoria, aunque con cosas a mejorar: " + junta(bad) + ".")
        if good and bad:
            s += " A mejorar: " + junta(bad[:1]) + "."
    else:
        s = ("Derrota. Lo que más pesó: " + junta(bad) + "." if bad else "Derrota, pese a hacerlo bien en: " + junta(good) + ".")
        if bad and good:
            s += " Lo mejor: " + junta(good[:1]) + "."
    return s


def load(lcu, gid, my_puuid, cache_dir):
    """Análisis de la partida `gid`, guardado en caché; None si el cliente ya no guarda su línea de tiempo."""
    path = os.path.join(cache_dir, "analysis", f"{gid}.json")
    saved = None
    try:
        saved = json.load(open(path, encoding="utf-8"))
        if saved.get("v") != VERSION:
            saved = None
    except Exception:
        saved = None
    if saved and saved.get("sure"):
        return saved
    if saved:  # guardado por una versión que podía equivocarse de jugador: se comprueba una vez y se corrige
        pid = _pid_from_history(saved, cache_dir, gid)
        if pid is None:
            try:
                pid = my_pid_in(lcu.get(f"/lol-match-history/v1/games/{gid}", timeout=20), my_puuid or _my_puuid(lcu))
            except Exception:
                pid = None
        if pid is None:
            return saved   # no hay con qué contrastarlo (partida antigua y cliente sin el detalle): se deja como estaba
        set_me(saved, pid)
        _write(path, saved)
        return saved
    detail = lcu.get(f"/lol-match-history/v1/games/{gid}", timeout=20)
    tl = lcu.get(f"/lol-match-history/v1/game-timelines/{gid}", timeout=30)
    if not detail or not tl or not tl.get("frames"):
        return None
    my_pid = my_pid_in(detail, my_puuid or _my_puuid(lcu))
    if my_pid is None:   # sin saber quién eres no se analiza: antes se tomaba al primer jugador y salía el campeón de otro
        return None
    a = compute(detail, tl, my_pid)
    a["sure"] = True
    _write(path, a)
    return a


def my_pid_in(detail, my_puuid):
    """Tu número de participante en el detalle de una partida (buscado por tu puuid), o None."""
    if not detail or not my_puuid:
        return None
    return next((i.get("participantId") for i in detail.get("participantIdentities") or []
                 if (i.get("player") or {}).get("puuid") == my_puuid), None)


def set_me(a, pid):
    """Fija quién eres en un análisis ya calculado (lo demás no depende de ello)."""
    p = a["players"][str(pid)]
    a.update(me=pid, team=p["team"], win=bool(p["win"]), sure=True)
    return a


def _my_puuid(lcu):
    try:
        return (lcu.get("/lol-summoner/v1/current-summoner") or {}).get("puuid", "")
    except Exception:
        return ""


def _pid_from_history(a, cache_dir, gid):
    """Tu participante según el historial guardado (campeón y resultado de esa partida), si es inequívoco."""
    try:
        e = json.load(open(history.hpath(cache_dir), encoding="utf-8")).get(str(gid))
    except Exception:
        e = None
    if not e or not e.get("c"):
        return None
    hit = [p["pid"] for p in a["players"].values() if p["champ"] == e["c"] and bool(p["win"]) == bool(e["w"])
           and (e.get("k") is None or (p["k"], p["d"], p["a"]) == (e["k"], e["de"], e["a"]))]
    return hit[0] if len(hit) == 1 else None


def _write(path, a):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(a, f)
    os.replace(tmp, path)


# ---- puntos de liga (PL) ganados o perdidos en cada partida clasificatoria ----
TIER_ORDER = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
DIV_ORDER = {"IV": 0, "III": 1, "II": 2, "I": 3}


def ladder_value(rk):
    """Rango como un solo número de PL (cada división son 100). En maestro o más es solo el PL."""
    if not rk:
        return None
    t = rk.get("key", "")
    if t not in TIER_ORDER:
        return None
    if TIER_ORDER.index(t) >= TIER_ORDER.index("MASTER"):
        return TIER_ORDER.index("MASTER") * 400 + rk.get("lp", 0)
    return TIER_ORDER.index(t) * 400 + DIV_ORDER.get(rk.get("div", ""), 0) * 100 + rk.get("lp", 0)


def lp_delta(before, after):
    """Dict con la variación de PL entre dos fotos del rango, o None si no se puede saber."""
    a, b = ladder_value(before), ladder_value(after)
    if a is None or b is None:
        return None
    ch = ""
    if before["key"] != after["key"] or before.get("div") != after.get("div"):
        ch = f"{before['tier']} {before['div']}".strip() + " → " + f"{after['tier']} {after['div']}".strip()
    return {"d": b - a, "now": after["lp"], "tier": f"{after['tier']} {after['div']}".strip(), "move": ch}


def _lp_path(cache_dir):
    return os.path.join(cache_dir, "lp.json")


def save_lp(cache_dir, gid, data):
    try:
        cur = json.load(open(_lp_path(cache_dir), encoding="utf-8"))
    except Exception:
        cur = {}
    old = cur.get(str(gid))
    if old and old.get("d") and not data.get("d"):
        return   # nunca se sustituye una variación real por un 0 (el rango aún no se había actualizado, o no se movió)
    cur[str(gid)] = data
    tmp = _lp_path(cache_dir) + ".tmp"
    json.dump(cur, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, _lp_path(cache_dir))


def lp_for(cache_dir, gid):
    try:
        return json.load(open(_lp_path(cache_dir), encoding="utf-8")).get(str(gid))
    except Exception:
        return None
