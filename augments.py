"""Mejoras (augments) de ARAM: Mayhem. Nombres, nivel e iconos salen del propio cliente de LoL; lo que elegiste, de tu historial.

IMPORTANTE: las normas de Riot para desarrolladores no permiten que una aplicación muestre porcentajes de victoria de las mejoras. Por eso aquí
solo hay cuentas de veces elegidas y datos del juego, nunca victorias por mejora. Tampoco se inventa una puntuación de «mejor mejora».
"""
import json, os, threading
from collections import Counter

import lol_advisor as core

TIERS = {"kSilver": "Plata", "kGold": "Oro", "kPrismatic": "Prismática"}
MAYHEM_QUEUES = {2400}
_cat = {}
_lock = threading.Lock()


def path(name):
    return os.path.join(core.CACHE, name)


def catalog(lcu=None):
    """{id: {n: nombre, r: nivel}} de todas las mejoras. Se guarda en caché; si hay cliente, se refresca una vez por sesión."""
    with _lock:
        if _cat:
            return _cat
        saved = core.read_json(path("augments.json"), {})
        if saved:
            _cat.update({int(k): v for k, v in saved.items()})
        if lcu is not None and not getattr(catalog, "fresh", False):
            try:
                data = lcu.get("/lol-game-data/assets/v1/cherry-augments.json") or []
                new = {int(x["id"]): {"n": x.get("nameTRA") or x.get("augmentNameId", ""), "r": TIERS.get(x.get("rarity"), ""),
                                      "i": x.get("augmentSmallIconPath", ""), "a": str(x.get("augmentNameId", "")).startswith("ARAM")} for x in data}
                if new:
                    _cat.clear()
                    _cat.update(new)
                    core.write_json(path("augments.json"), {str(k): v for k, v in new.items()})
                    catalog.fresh = True
            except Exception:
                pass
        return _cat


def info(aid):
    return catalog().get(int(aid)) or {"n": f"Mejora {aid}", "r": "", "i": ""}


def fetch_icons(ids, conf):
    """Baja en segundo plano los iconos que falten (del cliente) a cache/augicons/. Devuelve el hilo."""
    def go():
        try:
            lcu = core.LCU(*core.find_client(conf))
            catalog(lcu)
            os.makedirs(path("augicons"), exist_ok=True)
            for aid in ids:
                dest = path(os.path.join("augicons", f"{aid}.png"))
                p = info(aid).get("i")
                if os.path.exists(dest) or not p:
                    continue
                data = lcu.get_bytes(p)
                if data:
                    with open(dest, "wb") as f:
                        f.write(data)
        except Exception:
            pass
    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t


def icon_path(aid):
    p = path(os.path.join("augicons", f"{aid}.png"))
    return p if os.path.exists(p) else None


def counts(games, champ):
    """Mejoras que más has elegido con un campeón en partidas de Mayhem: [(id, veces)], y cuántas partidas hay."""
    mine = [g for g in games if g.get("q") in MAYHEM_QUEUES and g.get("c") == champ and g.get("au")]
    cnt = Counter(a for g in mine for a in g["au"] if a)
    return cnt.most_common(8), len(mine)


def mayhem_games(games):
    return [g for g in games if g.get("q") in MAYHEM_QUEUES]


def find_augments(obj, path_=""):
    """Busca en un JSON cualquier clave con «augment» (para saber si la API de partida en vivo las trae). Devuelve [(ruta, valor)]."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path_}.{k}" if path_ else k
            if "ugment" in k:
                out.append((p, v))
            else:
                out += find_augments(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += find_augments(v, f"{path_}[{i}]")
    return out


def live_probe(conf):
    """Mira la API de partida en vivo (127.0.0.1:2999, solo existe durante la partida) y guarda qué trae sobre mejoras.
    Escribe cache/live_probe.json con las claves que encuentre; devuelve la lista de mejoras detectadas (puede estar vacía)."""
    import ssl, urllib.request
    try:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen("https://127.0.0.1:2999/liveclientdata/allgamedata", context=ctx, timeout=3) as r:
            d = json.load(r)
    except Exception:
        return None
    found = find_augments(d)
    try:
        core.write_json(path("live_probe.json"), {"keys": list(d), "active_keys": list(d.get("activePlayer", {})),
                                                  "player_keys": list((d.get("allPlayers") or [{}])[0]), "game": d.get("gameData", {}),
                                                  "augment_fields": [(p, v) for p, v in found][:40]})
    except Exception:
        pass
    return found
