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
    lane = tl.get("lane", "")
    role = "SUPPORT" if lane == "BOTTOM" and tl.get("role") == "SUPPORT" else ("" if lane in ("NONE", "") else lane)
    return {"id": str(g["gameId"]), "t": g.get("gameCreation", 0), "d": g.get("gameDuration", 0), "q": g.get("queueId", 0),
            "c": me.get("championId", 0), "w": bool(st.get("win")), "r": role,
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
