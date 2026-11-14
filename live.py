"""Partida en vivo: convierte lo que devuelve la API local del juego (puerto 2999, solo existe durante la partida) en un resumen
para la pantalla. Sin red ni ventana: solo datos, para poder probarlo.

Entrada: el JSON de /liveclientdata/allgamedata. Salida de `summarize`:
  {"t": segundos de partida, "mode": «CLASSIC», «KIWI»…, "gold": tu oro, "me_team": «ORDER»|«CHAOS»|«»,
   "players": [{"cid", "name", "team", "me", "level", "k", "d", "a", "cs", "dead", "respawn", "items": [ids], "value", "pos"}],
   "teams": {"ORDER": {"kills", "value", "towers", "inhibs", "dragons", "barons", "heralds", "grubs"}, "CHAOS": {…}}}
«value» es el oro gastado en objetos que lleva ahora (suma de los precios de lo que tiene en el inventario): una estimación, no el
oro total que ha ganado. Todo lo que falte en los datos queda en 0 o vacío: la API cambia entre modos y parches.
"""

PREFIX = "game_character_displayname_"
ORDER = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4, "SUPPORT": 4}
EMPTY_TEAM = {"kills": 0, "value": 0, "towers": 0, "inhibs": 0, "dragons": 0, "barons": 0, "heralds": 0, "grubs": 0}


def champ_id(p, champs):
    """Id del campeón de un jugador: por su clave interna (la del icono) y, si no, por su nombre; 0 si no se reconoce."""
    raw = (p.get("rawChampionName") or "").replace(PREFIX, "").lower()
    name = (p.get("championName") or "").lower()
    for cid, c in champs.items():
        if raw and c.get("icon", "").lower() == raw:
            return cid
    for cid, c in champs.items():
        if name and c.get("name", "").lower() == name:
            return cid
    return 0


def item_value(items):
    """Oro en objetos: suma de los precios (por unidades) de lo que lleva, sin consumibles ni la baliza (precio 0)."""
    return sum(int(i.get("price") or 0) * max(1, int(i.get("count") or 1)) for i in items or [] if not i.get("consumable"))


def _names(p):
    return {x for x in (p.get("riotId"), p.get("summonerName"), p.get("riotIdGameName")) if x}


def team_of_name(name, players):
    """Equipo del jugador con ese nombre (el que traen los eventos), o «» si no se encuentra."""
    return next((p["team"] for p in players if name and name in p["names"]), "")


def _side(code):
    """Equipo AL QUE PERTENECÍA la estructura destruida. Formato real (comprobado en una partida de la Grieta): «Turret_TOrder_L0_P3_…» y
    «Inhib_TChaos_L2_P1_…»; se aceptan también «_T1_» (azul) y «_T2_» (rojo) por si algún modo los usa."""
    for tag, team in (("_TOrder_", "ORDER"), ("_TChaos_", "CHAOS"), ("_T1_", "ORDER"), ("_T2_", "CHAOS")):
        if tag in (code or ""):
            return team
    return ""


def summarize(d, champs):
    """Resumen de una muestra de la API en vivo; None si no se parece a una (sin jugadores)."""
    if not isinstance(d, dict) or not d.get("allPlayers"):
        return None
    ap = d.get("activePlayer") or {}
    mine = {x for x in (ap.get("riotId"), ap.get("summonerName"), ap.get("riotIdGameName")) if x}
    players = []
    for p in d["allPlayers"]:
        sc = p.get("scores") or {}
        items = [i for i in (p.get("items") or []) if i.get("itemID")]
        players.append({"cid": champ_id(p, champs), "name": p.get("championName") or "", "team": p.get("team") or "",
                        "me": bool(mine & _names(p)), "names": _names(p), "level": int(p.get("level") or 0),
                        "k": int(sc.get("kills") or 0), "d": int(sc.get("deaths") or 0), "a": int(sc.get("assists") or 0),
                        "cs": int(sc.get("creepScore") or 0), "dead": bool(p.get("isDead")), "respawn": float(p.get("respawnTimer") or 0),
                        "items": [i["itemID"] for i in sorted(items, key=lambda i: i.get("slot", 0))],
                        "value": item_value(items), "pos": p.get("position") or ""})
    teams = {"ORDER": dict(EMPTY_TEAM), "CHAOS": dict(EMPTY_TEAM)}
    for p in players:
        t = teams.setdefault(p["team"], dict(EMPTY_TEAM))
        t["kills"] += p["k"]
        t["value"] += p["value"]
    for e in (d.get("events") or {}).get("Events") or []:
        n = e.get("EventName")
        if n in ("TurretKilled", "InhibKilled"):
            lost = _side(e.get(n))
            gainer = {"ORDER": "CHAOS", "CHAOS": "ORDER"}.get(lost)
            if gainer:
                teams[gainer]["towers" if n == "TurretKilled" else "inhibs"] += 1
        elif n in ("DragonKill", "BaronKill", "HeraldKill", "HordeKill"):   # HordeKill: una larva del vacío (salen tres juntas)
            who = team_of_name(e.get("KillerName"), players)
            if who:
                teams[who][{"DragonKill": "dragons", "BaronKill": "barons", "HeraldKill": "heralds", "HordeKill": "grubs"}[n]] += 1
    baron_kills = sorted(float(e.get("EventTime") or 0) for e in (d.get("events") or {}).get("Events") or [] if e.get("EventName") == "BaronKill")
    for p in players:
        p.pop("names", None)
    me = next((p for p in players if p["me"]), None)
    players.sort(key=lambda p: (0 if p["team"] == "ORDER" else 1, ORDER.get(p["pos"], 9)))   # azul primero, y por línea
    return {"t": float((d.get("gameData") or {}).get("gameTime") or 0), "mode": (d.get("gameData") or {}).get("gameMode") or "",
            "baron_kills": baron_kills, "gold": int(ap.get("currentGold") or 0), "me_team": me["team"] if me else "", "players": players, "teams": teams}


def clock(t):
    """«14:32» a partir de los segundos de partida."""
    t = max(0, int(t))
    return f"{t // 60}:{t % 60:02d}"


def money(v):
    """«12,4k» para el oro."""
    return f"{v / 1000:.1f}k".replace(".", ",")


def itemization(players, items_db):
    """Qué llevan en objetos los jugadores dados, en oro: daño físico, daño mágico, armadura y resistencia mágica. Sale de las
    etiquetas oficiales de Data Dragon (`items_db`: {id: {"t": etiquetas, "g": coste}}); no cuenta consumibles ni la baliza."""
    ad = ap = armor = mr = 0
    for p in players:
        for iid in p.get("items") or []:
            it = items_db.get(iid) or {}
            tags, gold = set(it.get("t") or []), int(it.get("g") or 0)
            if tags & {"Trinket", "Consumable"}:
                continue
            if "SpellDamage" in tags:
                ap += gold
            elif tags & {"Damage", "CriticalStrike", "AttackSpeed"}:
                ad += gold
            if "Armor" in tags:
                armor += gold
            if tags & {"SpellBlock", "MagicResist"}:
                mr += gold
    return {"ad": ad, "ap": ap, "armor": armor, "mr": mr}


def reading(m, minimum=2500):
    """Frases cortas sobre un equipo rival a partir de `itemization`. Solo habla cuando hay oro suficiente para que signifique algo
    (con un par de objetos sueltos, cualquier porcentaje engaña)."""
    out = []
    attack = m["ad"] + m["ap"]
    if attack >= minimum:
        ad = round(100 * m["ad"] / attack)
        out.append(f"Su daño, según sus objetos: {ad} % físico · {100 - ad} % mágico.")
    if m["armor"] + m["mr"] >= minimum:
        if m["armor"] >= 1.8 * m["mr"]:
            out.append("Acumulan armadura: la penetración de armadura rinde más que el daño bruto.")
        elif m["mr"] >= 1.8 * m["armor"]:
            out.append("Acumulan resistencia mágica: la penetración mágica rinde más que el daño bruto.")
        else:
            out.append("Acumulan armadura y resistencia mágica por igual.")
    return out


def duel(snap, opp_cid):
    """(tú, tu rival directo) a partir del resumen y del campeón rival de tu línea; None si falta alguno de los dos."""
    yo = next((p for p in snap.get("players", []) if p["me"]), None)
    if not yo or not opp_cid:
        return None
    rival = next((p for p in snap["players"] if p["cid"] == opp_cid and p["team"] != yo["team"]), None)
    return (yo, rival) if rival else None


BARON_SPAWN, BARON_RESPAWN = 1200, 360   # el Barón sale a los 20:00 y 6 min después de caer (parche 26.x; las fuentes coinciden). El dragón y las larvas NO se
# incluyen: las fuentes discrepan y no se ha podido confirmar el tiempo actual
BARON_WARN = 60                           # se avisa cuando falta menos de este tiempo


def timers(snap):
    """Frase del Barón según el reloj de la partida (estimada: no lee el estado real de la fosa), o None si no toca decir nada.
    Solo en la Grieta (modo CLASSIC)."""
    if not snap or snap.get("mode") != "CLASSIC":
        return None
    t = snap.get("t", 0)
    kills = snap.get("baron_kills") or []
    due = (kills[-1] + BARON_RESPAWN) if kills else BARON_SPAWN
    left = due - t
    if left > BARON_WARN:
        return None
    if left > 0:
        return f"El Barón {'reaparece' if kills else 'aparece'} en {clock(left)} (estimado)."
    return "El Barón debería estar disponible (estimado)." if left > -300 else None


SPIKE_LEVELS = (6, 11, 16)
SPIKE_GOLD = 1800        # lo que sube el oro en objetos del rival entre dos lecturas para avisar de una compra importante (≈ un objeto completo)
SPIKE_SHOW = 45          # segundos de partida que dura el aviso en pantalla


def spikes(prev, cur, opp_cid):
    """Avisos de pico de poder de tu rival directo entre dos lecturas seguidas: sube a nivel 6, 11 o 16, o compra objetos por mucho oro.
    Solo usa lo que el marcador del propio juego ya enseña a todos. Lista de frases (vacía si no hay nada)."""
    if not prev or not cur or cur.get("t", 0) < prev.get("t", 0):
        return []
    a, b = duel(prev, opp_cid), duel(cur, opp_cid)
    if not a or not b:
        return []
    (_y0, r0), (yo, r1) = a, b
    out = []
    for lv in SPIKE_LEVELS:
        if r0["level"] < lv <= r1["level"]:
            out.append(f"Tu rival directo ha llegado al nivel {lv}" + (" y tú aún no" if yo["level"] < lv else "") + ": ojo al intercambio.")
    gain = r1["value"] - r0["value"]
    if gain >= SPIKE_GOLD:
        out.append(f"Tu rival directo acaba de comprar objetos por {money(gain)}: su poder ha subido.")
    return out


def duel_line(yo, rival, name=""):
    """Una frase con cómo vas frente a tu rival directo: nivel, objetos y marcador. Solo opina de los objetos si la diferencia es clara
    (15 % o más y al menos 500 de oro): con menos, es ruido."""
    txt = (f"Tu rival directo{', ' + name if name else ''}: nivel {rival['level']} (tú {yo['level']}) · objetos {money(rival['value'])} "
           f"(tú {money(yo['value'])}) · {rival['k']}/{rival['d']}/{rival['a']}.")
    dif = rival["value"] - yo["value"]
    if abs(dif) >= 500 and abs(dif) >= 0.15 * max(1, yo["value"], rival["value"]):
        txt += " Va por delante en objetos." if dif > 0 else " Vas por delante en objetos."
    return txt
