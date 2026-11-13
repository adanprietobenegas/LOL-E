"""Historial de partidas.

El cliente de LoL solo entrega las últimas ~20 partidas. LOL-E guarda cada partida que ve en `history.json`
(con campeón, resultado, K/D/A, farmeo, duración, modo…) para que el historial crezca mientras lo usas.
Las partidas guardadas por versiones anteriores (`games.json`) se incluyen, aunque sin K/D/A.
"""
import json, os, shutil, time


def _read(path, default):
    """Lee un JSON; si está dañado, usa la copia de seguridad (.bak) para no perder el historial."""
    for p in (path, path + ".bak"):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return default


# ---- la línea que jugaste ----
# La etiqueta de línea del cliente (timeline.lane) es una estimación suya y falla MUCHO: etiqueta «JUNGLE» a quien juega TOP, deja
# equipos con dos jungleros y ningún toplane, llama «TOP» a un mid, «BOTTOM» a un apoyo y «MIDDLE» a un tirador (en una partida real
# fallaron 4 de los 10 jugadores; de las 16 «Jungla» de las partidas del usuario solo 5 llevaban Aplastar). Dos señales sí son fiables:
#   · quien juega jungla lleva SIEMPRE Aplastar (hechizo 11);
#   · el objeto de rol del cliente (stats.roleBoundItem): 1220 y 1221 = top, 1209 = jungla, 1206 = mid, 1208 y 2055 = apoyo.
#     En esa misma partida real repartieron bien los cinco puestos de los dos equipos, y en las partidas con línea «NONE» dan
#     campeones coherentes (Fiora 1220, Hwei 1206, Illaoi 1221). El tirador lleva unas botas como objeto de rol (BOOT_ITEMS: en 30
#     partidas reales, 42 de 44 tiradores). Son valores OBSERVADOS, no documentados por Riot; si algo no cuadra, la línea sale de la
#     etiqueta o por eliminación dentro del equipo (team_roles) o queda vacía.
SMITE = 11
ROLE_V = 2   # versión de esta regla; las partidas guardadas con otra se recalculan (lol_advisor.load_player_data y _refresh_old_games)
ITEM_ROLE = {1220: "TOP", 1221: "TOP", 1209: "JUNGLE", 1206: "MIDDLE", 1208: "SUPPORT", 2055: "SUPPORT"}
BOOT_ITEMS = {3006, 3008, 3009, 3020, 3047, 3158}   # objeto de rol del tirador (solo se usa con etiqueta BOTTOM o MIDDLE)
TOP_ITEMS = {i for i, r in ITEM_ROLE.items() if r == "TOP"}
JUNGLE_ITEMS = {i for i, r in ITEM_ROLE.items() if r == "JUNGLE"}
SUPPORT_ITEMS = {i for i, r in ITEM_ROLE.items() if r == "SUPPORT"}
LINES = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT")


def _by_item(p):
    return ITEM_ROLE.get((p.get("stats") or {}).get("roleBoundItem") or 0, "")


def role_of(p):
    """Línea de un participante: «TOP», «JUNGLE», «MIDDLE», «BOTTOM», «SUPPORT» o «» si no se sabe (un dato equivocado es
    peor que ninguno). Manda el objeto de rol; sin él, Aplastar; sin él, la etiqueta del cliente salvo la de jungla."""
    por_objeto = _by_item(p)
    if por_objeto:
        return por_objeto
    t = p.get("timeline") or {}
    lane, role = t.get("lane") or "", t.get("role") or ""
    if (p.get("stats") or {}).get("roleBoundItem") in BOOT_ITEMS and lane in ("BOTTOM", "MIDDLE"):
        return "BOTTOM"                                # tirador (el cliente llega a llamarlo «MIDDLE»: Jhin con DUO)
    if SMITE in (p.get("spell1Id"), p.get("spell2Id")) and lane in ("JUNGLE", "NONE", ""):
        return "JUNGLE"
    if lane == "JUNGLE":
        return ""                                      # «jungla» sin Aplastar ni objeto de jungla: no se adivina
    if lane == "BOTTOM":
        return "SUPPORT" if role == "SUPPORT" else "BOTTOM"
    return "" if lane in ("", "NONE") else lane


def team_roles(parts):
    """{participantId: línea} de los jugadores de UN equipo (normalmente cinco). Lo seguro (objeto de rol o Aplastar) manda; una
    línea que solo viene de la etiqueta y ya tiene dueño seguro se descarta; y si queda un solo jugador sin línea y una sola línea
    sin jugador (el tirador, que no tiene objeto de rol), se le asigna esa. Si no, queda sin línea."""
    seguros, dudosos = {}, {}
    for p in parts:
        r = role_of(p)
        firme = bool(_by_item(p)) or (r == "JUNGLE")
        (seguros if firme else dudosos)[p.get("participantId")] = r
    tomadas = set(seguros.values())
    cuenta = {}
    for r in dudosos.values():
        cuenta[r] = cuenta.get(r, 0) + 1
    for pid, r in list(dudosos.items()):
        if r and (r in tomadas or cuenta[r] > 1):        # la etiqueta choca con otro jugador: no se fía
            dudosos[pid] = ""
    faltan = [x for x in LINES if x not in tomadas and x not in dudosos.values()]
    sin = [pid for pid, r in dudosos.items() if not r]
    if len(sin) == 1 and len(faltan) == 1:
        dudosos[sin[0]] = faltan[0]
    return {**seguros, **dudosos}


# ---- una carpeta, varias cuentas ----
# Cada cuenta guarda su historial en history_<puuid>.json y games_<puuid>.json. Los archivos antiguos (history.json y games.json,
# sin dueño) se copian a la primera cuenta que demuestre que son suyos: alguna de sus partidas del cliente ya está en ellos.
# No se borran: quedan como copia. Sin cuenta conocida se siguen leyendo los antiguos.
ACCOUNT = ""


def _safe(puuid):
    return "".join(ch for ch in str(puuid) if ch.isalnum() or ch == "-")[:80]


def hpath(cache):
    return os.path.join(cache, f"history_{_safe(ACCOUNT)}.json" if ACCOUNT else "history.json")


def gpath(cache):
    return os.path.join(cache, f"games_{_safe(ACCOUNT)}.json" if ACCOUNT else "games.json")


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def load_account(cache):
    """Al abrir sin cliente: se usa la última cuenta que se vio, para enseñar su historial y no el de otra."""
    global ACCOUNT
    if not ACCOUNT:
        ACCOUNT = _safe((_read(os.path.join(cache, "account.json"), {}) or {}).get("puuid", ""))
    return ACCOUNT


def set_account(cache, puuid, client_ids=()):
    """Activa la cuenta `puuid`. Devuelve «migrated» si en este momento heredó los archivos antiguos, «new» si empieza
    vacía, «» si ya tenía los suyos, si no hay cuenta o si aún no se puede decidir.
    `client_ids`: ids de las partidas que el cliente acaba de entregar."""
    global ACCOUNT
    puuid = _safe(puuid)
    if not puuid:
        return ""
    changed = puuid != ACCOUNT
    ACCOUNT = puuid
    try:
        if changed or not os.path.exists(os.path.join(cache, "account.json")):
            _write(os.path.join(cache, "account.json"), {"v": 1, "puuid": puuid})
    except OSError:
        pass
    hp, gp = hpath(cache), gpath(cache)
    if os.path.exists(hp) or os.path.exists(gp):
        return ""
    owner_file = os.path.join(cache, "history_owner.json")
    if (_read(owner_file, {}) or {}).get("puuid"):
        return "new"   # los antiguos ya son de otra cuenta
    old_h, old_g = os.path.join(cache, "history.json"), os.path.join(cache, "games.json")
    legacy = set(_read(old_h, {}) or {}) | set(_read(old_g, {}) or {})
    if not legacy:
        return "new"
    if not ({str(i) for i in client_ids} & legacy):
        return "new" if client_ids else ""   # sin partidas del cliente aún no se sabe de quién son: se decide más tarde
    for src, dst in ((old_h, hp), (old_g, gp)):
        if os.path.exists(src):
            shutil.copy2(src, dst)
    _write(owner_file, {"v": 1, "puuid": puuid, "t": int(time.time())})
    return "migrated"


def my_part(g, puuid=""):
    """Tu participante en una partida del cliente, o None si no se puede saber con certeza.

    Se busca por tu puuid en `participantIdentities`. La lista de partidas trae un solo participante (tú) y entonces
    vale ese; el detalle trae los diez, y ahí NUNCA se supone que eres el primero (así salía el campeón de otro)."""
    parts = g.get("participants") or []
    if puuid:
        pid = next((i.get("participantId") for i in g.get("participantIdentities") or []
                    if (i.get("player") or {}).get("puuid") == puuid), None)
        hit = next((p for p in parts if p.get("participantId") == pid), None) if pid is not None else None
        if hit is not None:
            return hit
    return parts[0] if len(parts) == 1 else None


def from_game(g, puuid=""):
    """Registro compacto de una partida del cliente; None si no se sabe cuál de los jugadores eres."""
    me = my_part(g, puuid)
    if me is None:
        return None
    st, tl = me.get("stats", {}), me.get("timeline", {})
    role = role_of(me)
    return {"id": str(g["gameId"]), "t": g.get("gameCreation", 0), "d": g.get("gameDuration", 0), "q": g.get("queueId", 0),
            "c": me.get("championId", 0), "w": bool(st.get("win")), "r": role, "rv": ROLE_V,
            "k": st.get("kills", 0), "de": st.get("deaths", 0), "a": st.get("assists", 0),
            "cs": st.get("totalMinionsKilled", 0) + st.get("neutralMinionsKilled", 0), "lv": st.get("champLevel", 0),
            "dm": st.get("totalDamageDealtToChampions", 0), "g": st.get("goldEarned", 0), "v": st.get("visionScore", 0),
            "rm": bool(st.get("gameEndedInEarlySurrender")), "it": [st.get(f"item{i}", 0) for i in range(7)],
            "gm": g.get("gameMode", ""), "gt": g.get("gameType", ""), "pl": st.get("subteamPlacement"),
            "au": [st.get(f"playerAugment{i}", 0) for i in range(1, 7) if st.get(f"playerAugment{i}", 0)]}


def save(path, games):
    """Añade o actualiza partidas en el archivo (por identificador)."""
    data = _read(path, {})
    changed = False
    for e in games:
        if data.get(e["id"]) != e:
            data[e["id"]] = e
            changed = True
    if changed:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        bak = path + ".bak"
        try:  # una copia por día como máximo: si el archivo se dañara, el historial se recupera de aquí
            if os.path.exists(path) and (not os.path.exists(bak) or time.time() - os.path.getmtime(bak) > 86400):
                shutil.copy2(path, bak)
        except OSError:
            pass
        os.replace(tmp, path)


def load_all(history_path, legacy_path):
    """Todas las partidas conocidas, de la más reciente a la más antigua."""
    data = _read(history_path, {})
    for gid, v in (_read(legacy_path, {}) or {}).items():
        if gid not in data and isinstance(v, dict) and v.get("t"):
            data[gid] = {"id": gid, "t": v["t"], "d": 0, "q": v.get("q", 0), "c": v["c"], "w": bool(v["w"]), "r": v.get("r", ""),
                         "k": None, "de": None, "a": None, "cs": None, "lv": None, "dm": None, "g": None, "v": None, "rm": False}
    return sorted(data.values(), key=lambda e: -e["t"])


def kda(e):
    if e.get("k") is None:
        return None
    return (e["k"] + e["a"]) / max(1, e["de"])


def summary(games):
    n = len(games)
    wins = sum(1 for e in games if e["w"])
    with_k = [e for e in games if e.get("k") is not None]
    k = sum(e["k"] for e in with_k)
    d = sum(e["de"] for e in with_k)
    a = sum(e["a"] for e in with_k)
    return {"n": n, "wins": wins, "wr": wins / n if n else 0, "kda": (k + a) / max(1, d) if with_k else None,
            "avg": (k / len(with_k), d / len(with_k), a / len(with_k)) if with_k else None}
