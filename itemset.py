"""Enviar la build al cliente de League como «conjunto de objetos» propio: aparece en la tienda de la partida (y en la selección) como los que crea el jugador.

El cliente expone `/lol-item-sets/v1/item-sets/{summonerId}/sets` (comprobado en el propio cliente: existen GET, PUT y POST). El PUT sustituye TODA la
lista de conjuntos del jugador, así que se lee primero la lista y solo se tocan los de LOL-E (su `uid` empieza por «lole-»); los demás se devuelven tal cual.
Nada se envía sin que el jugador pulse el botón (o active el envío automático).
"""
import json, os, threading, time, urllib.error, urllib.request

import lol_advisor as core

PREFIX = "lole-"
KEEP = 12  # como mucho, los 12 conjuntos de LOL-E más recientes (uno por campeón y línea)
SR_MAP = 11


def make_set(uid, title, cid, blocks, rank=0):
    """Conjunto en el formato del cliente. `blocks`: [(nombre, [ids de objeto])]."""
    return {"uid": uid, "title": title, "mode": "any", "map": "any", "type": "custom", "sortrank": rank, "startedFrom": "blank",
            "associatedChampions": [cid], "associatedMaps": [SR_MAP], "preferredItemSlots": [],
            "blocks": [{"type": name, "items": [{"id": str(i), "count": 1} for i in ids]} for name, ids in blocks if ids]}

def config_dir(conf):
    """Carpeta Config de League (donde el juego lee los conjuntos de objetos), o None si no se encuentra."""
    cands = [conf.get("lol_path") or ""] + [rf"{d}:\Riot Games\League of Legends" for d in "CDEFG"]
    for c in cands:
        if c and os.path.isdir(os.path.join(c, "Config")):
            return os.path.join(c, "Config")
    return None


def game_file(conf, key):
    """Ruta del archivo propio de LOL-E para un campeón (key = id de Data Dragon, p. ej. «MonkeyKing»), o None."""
    cfg = config_dir(conf)
    return os.path.join(cfg, "Champions", key, "Recommended", "LOLE_ItemSet.json") if cfg and key else None


def game_json(title, blocks):
    """El mismo conjunto en el formato de archivo que lee el juego al empezar la partida (Config\\Champions\\<campeón>\\Recommended)."""
    return {"title": title, "type": "custom", "map": "SR", "mode": "any", "priority": False, "sortrank": 0,
            "blocks": [{"type": name, "recMath": False, "minSummonerLevel": -1, "maxSummonerLevel": -1, "showIfSummonerSpell": "",
                        "hideIfSummonerSpell": "", "items": [{"id": str(i), "count": 1} for i in ids]} for name, ids in blocks if ids]}


def write_game_file(conf, key, title, blocks):
    """Escribe el archivo del juego. Devuelve la ruta o None si no se pudo (no es grave: el cliente también lo copia por su cuenta)."""
    path = game_file(conf, key)
    if not path:
        return None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(game_json(title, blocks), f, ensure_ascii=False)
        return path
    except OSError:
        return None


def client_copied(conf, key, uid, wait=6.0):
    """¿Ha copiado el cliente el conjunto a la carpeta del juego? Espera unos segundos a que lo haga."""
    cfg = config_dir(conf)
    if not cfg or not key:
        return False
    folder = os.path.join(cfg, "Champions", key, "Recommended")
    end = time.time() + wait
    while True:
        try:
            for fn in os.listdir(folder):
                if fn.startswith("RIOT_ItemSet"):
                    with open(os.path.join(folder, fn), encoding="utf-8", errors="ignore") as f:
                        if uid in f.read():
                            return True
        except OSError:
            pass
        if time.time() >= end:
            return False
        time.sleep(0.5)


def merge(existing, new):
    """Lista final: los conjuntos ajenos intactos, los de LOL-E (sin el que se sustituye) y el nuevo al principio de los de LOL-E."""
    others = [s for s in existing if not str(s.get("uid", "")).startswith(PREFIX)]
    ours = [s for s in existing if str(s.get("uid", "")).startswith(PREFIX) and s.get("uid") != new["uid"]]
    return others + [new] + ours[:KEEP - 1]


def _call(lcu, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(lcu.base + path, data=data, method=method,
                                 headers={"Authorization": lcu.auth, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=core.CTX, timeout=10) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def send(conf, uid, title, cid, blocks, key=None):
    """Envía el conjunto. Devuelve (ok, mensaje). Bloquea: llamar desde un hilo."""
    if not any(ids for _, ids in blocks):
        return False, "No hay objetos que enviar."
    try:
        found = core.find_client(conf)
        if not found:
            return False, "El cliente de League no está abierto."
        lcu = core.LCU(*found)
        me = lcu.get("/lol-summoner/v1/current-summoner")
        sid = me and me.get("summonerId")
        if not sid:
            return False, "El cliente aún no ha iniciado sesión."
        path = f"/lol-item-sets/v1/item-sets/{sid}/sets"
        cur = lcu.get(path) or {}
        new = make_set(uid, title, cid, blocks)
        _call(lcu, "PUT", path, {"accountId": cur.get("accountId", 0), "timestamp": cur.get("timestamp", 0),
                                 "itemSets": merge(cur.get("itemSets") or [], new)})
        back = lcu.get(path) or {}
        if not any(s.get("uid") == uid for s in back.get("itemSets", [])):
            return False, "El cliente no ha guardado el conjunto."
        wrote = write_game_file(conf, key, title, blocks)
        copied = client_copied(conf, key, uid) if key else False
        if wrote or copied:
            return True, (f"Enviado: «{title}». Ya está en la carpeta del juego: aparecerá en la tienda si la partida aún no ha empezado "
                          "(el juego lo lee al arrancar). Si ya estás en partida, será para la siguiente.")
        return True, (f"Guardado en el cliente: «{title}». No he podido copiarlo a la carpeta del juego; si no lo ves en la tienda, "
                      "envíalo antes de que empiece la partida.")
    except urllib.error.HTTPError as e:
        return False, f"El cliente rechazó el conjunto (error {e.code})."
    except Exception as e:
        return False, f"No se pudo enviar ({type(e).__name__})."


def send_async(conf, uid, title, cid, blocks, result, key=None):
    """Como send(), en un hilo; deja el resultado en el dict `result` ({"state": "sending"|"done", "ok": bool, "msg": str})."""
    result.update(state="sending", ok=False, msg="")

    def go():
        ok, msg = send(conf, uid, title, cid, blocks, key)
        result.update(state="done", ok=ok, msg=msg)
    threading.Thread(target=go, daemon=True).start()
