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
        if _cat and (lcu is None or getattr(catalog, "fresh", False)):
            return _cat
        saved = core.read_json(path("augments.json"), {})
        if saved:
            _cat.update({int(k): v for k, v in saved.items()})
        if lcu is not None and not getattr(catalog, "fresh", False):
            try:
                data = lcu.get("/lol-game-data/assets/v1/cherry-augments.json") or []
                new = {int(x["id"]): {"n": x.get("nameTRA") or x.get("augmentNameId", ""), "r": TIERS.get(x.get("rarity"), ""),
                                      "i": x.get("augmentSmallIconPath", ""), "a": str(x.get("augmentNameId", "")).startswith("ARAM"), "k": str(x.get("augmentNameId", ""))} for x in data}
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


def fetch_icons(ids, conf, done=None):
    """Baja en segundo plano los iconos que falten (del cliente) a cache/augicons/. Devuelve el hilo."""
    ids = [i for i in dict.fromkeys(ids) if not icon_path(i)]
    if not ids:
        return None

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
        if done:
            done()   # los iconos ya están: la pantalla se repinta una vez
    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t


def ensure_catalog(conf, done=None):
    """Si el catálogo guardado es de una versión vieja (sin el id interno), lo refresca desde el cliente en segundo plano. True si hay que esperar."""
    if any(v.get("k") for v in catalog().values()):
        return False

    def go():
        try:
            catalog(core.LCU(*core.find_client(conf)))
        except Exception:
            pass
        if done:
            done()
    threading.Thread(target=go, daemon=True).start()
    return True


def icon_path(aid):
    p = path(os.path.join("augicons", f"{aid}.png"))
    return p if os.path.exists(p) else None


def counts(games, champ):
    """Mejoras que más has elegido con un campeón en partidas de Mayhem: [(id, veces)], y cuántas partidas hay."""
    mine = [g for g in games if g.get("q") in MAYHEM_QUEUES and g.get("c") == champ and g.get("au")]
    cnt = Counter(a for g in mine for a in g["au"] if a)
    return cnt.most_common(8), len(mine)


def flat_live(found):
    """Lo que la API en vivo trae sobre mejoras, como textos legibles (ids de mejora -> nombre)."""
    out = []

    def one(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, int) and v in catalog():
            out.append(info(v)["n"] + (f" ({info(v)['r'].lower()})" if info(v)["r"] else ""))
        elif isinstance(v, (str, int, float)):
            out.append(str(v))
        elif isinstance(v, dict):
            nm = v.get("displayName") or v.get("name") or v.get("rawDisplayName")
            if nm:
                out.append(str(nm))
            else:
                for x in v.values():
                    one(x)
        elif isinstance(v, list):
            for x in v:
                one(x)
    for x in found:
        one(x)
    seen, res = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


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


def fetch_live():
    """Lo que devuelve la API de partida en vivo del juego (127.0.0.1:2999, solo existe durante la partida), o None si no responde.
    Es el ÚNICO sitio donde se lee ese puerto: usa un contexto sin verificar certificado porque el juego usa uno propio, y por eso
    la dirección está fija en este archivo (una prueba lo comprueba)."""
    import ssl, urllib.request
    try:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen("https://127.0.0.1:2999/liveclientdata/allgamedata", context=ctx, timeout=3) as r:
            return json.load(r)
    except Exception:
        return None


def live_probe(conf, d=None):
    """Mira la API de partida en vivo y guarda qué trae sobre mejoras (`d` es la muestra ya leída; si no, la pide).
    Escribe cache/live_probe.json con las claves que encuentre; devuelve la lista de mejoras detectadas (puede estar vacía)."""
    if d is None:
        d = fetch_live()
    if d is None:
        return None
    found = find_augments(d)
    try:   # muestras completas de lo que devuelve la API (hasta 6 por partida, una cada ~3 min de juego) para poder analizarlas después
        gt = float((d.get("gameData") or {}).get("gameTime", 0))
        st = live_probe.__dict__.setdefault("seen", {"t": 1e9, "buckets": set()})
        if gt < st["t"]:
            st["buckets"] = set()   # partida nueva
        st["t"] = gt
        b = int(gt // 180)
        if b not in st["buckets"] and len(st["buckets"]) < 6:
            st["buckets"].add(b)
            os.makedirs(path("live_samples"), exist_ok=True)
            with open(path(os.path.join("live_samples", f"allgamedata_{int(gt)}s.json")), "w", encoding="utf-8") as f:
                json.dump(core.scrub(d), f, ensure_ascii=False)   # sin los nombres de los 10 jugadores: solo interesa la forma de los datos
    except Exception:
        pass
    try:
        core.write_json(path("live_probe.json"), {"keys": list(d), "active_keys": list(d.get("activePlayer", {})),
                                                  "player_keys": list((d.get("allPlayers") or [{}])[0]), "game": d.get("gameData", {}),
                                                  "augment_fields": [(p, v) for p, v in found][:40]})
    except Exception:
        pass
    return found
