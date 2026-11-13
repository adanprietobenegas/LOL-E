"""Meta del parche: tasa de victoria, uso y baneo de cada campeón por línea (lista pública de Lolalytics).

Una petición por línea (5 en total) y se guarda un día. Si falla, la aplicación sigue sin meta.
"""
import json, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

LANES = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support"}
URL = "https://a1.lolalytics.com/mega/?ep=list&v=1&patch={patch}&lane={lane}&tier={tier}&queue=420&region=all"
UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)"}
TIER_NAMES = {"emerald_plus": "Esmeralda+", "platinum_plus": "Platino+", "diamond_plus": "Diamante+", "gold_plus": "Oro+",
              "silver_plus": "Plata+", "bronze_plus": "Bronce+", "iron_plus": "Hierro+", "master_plus": "Maestro+", "all": "todos los rangos"}


def _fetch(patch, lane, tier):
    req = urllib.request.Request(URL.format(patch=patch, lane=lane, tier=tier), headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode("utf8"))
    rows = d.get("cid") or {}
    out = {k: {"wr": v["wr"], "pr": v["pr"], "br": v["br"], "games": v["games"], "d": v.get("avgWrDelta", 0)}
           for k, v in rows.items() if isinstance(v, dict) and v.get("games", 0) >= 200 and v.get("lane", lane) == lane}
    return out, d.get("avgWr", 50)


def public_patch(v):
    """Numeración pública de Riot desde 2025: la versión interna «16.22» es el parche 26.22."""
    parts = str(v).split(".")
    try:
        return f"{int(parts[0]) + 10}.{parts[1]}"
    except Exception:
        return str(v)


def tier_for(rank_key):
    """Elo de referencia: el tuyo y superiores (así los datos son de jugadores como tú o mejores)."""
    k = (rank_key or "").lower()
    return f"{k}_plus" if k in ("iron", "bronze", "silver", "gold", "platinum", "emerald", "diamond", "master") else "emerald_plus"


def load(cache_dir, version, tier, force=False):
    """Devuelve {'patch','tier','avg':{línea:media},'lanes':{línea:{id_campeón:{wr,pr,br,games,d}}}} o lanza una excepción."""
    major, minor = (version.split(".") + ["0"])[:2]
    path = os.path.join(cache_dir, "meta.json")
    saved = None
    try:
        saved = json.load(open(path, encoding="utf-8"))
        cur = f"{major}.{minor}"
        fresh = time.time() - saved["ts"] < (20 * 3600 if saved["patch"] == cur else 3 * 3600)  # si falta el parche nuevo, se reintenta cada 3 h
        if not force and fresh and saved["tier"] == tier and saved.get("current", saved["patch"]) == cur:
            return _ints(saved)
    except Exception:
        pass
    last_err = None
    for patch in (f"{major}.{minor}", f"{major}.{max(0, int(minor) - 1)}"):
        for t in (tier, "emerald_plus", "all"):
            try:
                with ThreadPoolExecutor(5) as ex:
                    res = dict(zip(LANES.values(), ex.map(lambda ln: _fetch(patch, ln, t), LANES.values())))
                if sum(len(v[0]) for v in res.values()) < 100:
                    continue
                data = {"ts": time.time(), "patch": patch, "current": f"{major}.{minor}", "tier": t, "avg": {k: v[1] for k, v in res.items()},
                        "lanes": {k: v[0] for k, v in res.items()}}
                os.makedirs(cache_dir, exist_ok=True)
                json.dump(data, open(path, "w", encoding="utf-8"))
                return _ints(data)
            except Exception as e:
                last_err = e
    if saved and saved.get("lanes"):   # sin red o la fuente falla: mejor el último meta guardado (de otro día o de otro parche) que ninguno
        saved["stale"] = True
        return _ints(saved)
    raise RuntimeError(f"sin datos de meta ({last_err})")


def _ints(data):
    data["lanes"] = {ln: {int(k): v for k, v in rows.items()} for ln, rows in data["lanes"].items()}
    return data


ROLE_OF = {"top": "TOP", "jungle": "JUNGLE", "middle": "MIDDLE", "bottom": "BOTTOM", "support": "SUPPORT"}


def lane_shares(meta, cid):
    """Reparto de las partidas de un campeón por línea (0 a 1), según el meta. Sirve para saber en qué líneas se juega de verdad,
    aunque no sean las habituales. {} si no hay datos."""
    if not meta:
        return {}
    rows = {ln: r.get(cid) for ln, r in meta["lanes"].items() if r.get(cid)}
    tot = sum(v["games"] for v in rows.values())
    return {ROLE_OF[ln]: v["games"] / tot for ln, v in rows.items() if ln in ROLE_OF} if tot else {}


def get(meta, role, cid):
    """Datos de meta de un campeón en una línea (rol en formato del cliente: TOP, JUNGLE, MIDDLE, BOTTOM, SUPPORT)."""
    if not meta or role not in LANES:
        return None
    return meta["lanes"].get(LANES[role], {}).get(cid)
