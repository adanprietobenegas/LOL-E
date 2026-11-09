"""Enviar la build al cliente de League como «conjunto de objetos» propio: aparece en la tienda de la partida (y en la selección) como los que crea el jugador.

El cliente expone `/lol-item-sets/v1/item-sets/{summonerId}/sets` (comprobado en el propio cliente: existen GET, PUT y POST). El PUT sustituye TODA la
lista de conjuntos del jugador, así que se lee primero la lista y solo se tocan los de LOL-E (su `uid` empieza por «lole-»); los demás se devuelven tal cual.
Nada se envía sin que el jugador pulse el botón (o active el envío automático).
"""
import json, threading, urllib.error, urllib.request

import lol_advisor as core

PREFIX = "lole-"
KEEP = 12  # como mucho, los 12 conjuntos de LOL-E más recientes (uno por campeón y línea)
SR_MAP = 11


def make_set(uid, title, cid, blocks, rank=0):
    """Conjunto en el formato del cliente. `blocks`: [(nombre, [ids de objeto])]."""
    return {"uid": uid, "title": title, "mode": "any", "map": "any", "type": "custom", "sortrank": rank, "startedFrom": "blank",
            "associatedChampions": [cid], "associatedMaps": [SR_MAP], "preferredItemSlots": [],
            "blocks": [{"type": name, "items": [{"id": str(i), "count": 1} for i in ids]} for name, ids in blocks if ids]}


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


def send(conf, uid, title, cid, blocks):
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
        return True, f"Enviado al cliente: «{title}»."
    except urllib.error.HTTPError as e:
        return False, f"El cliente rechazó el conjunto (error {e.code})."
    except Exception as e:
        return False, f"No se pudo enviar ({type(e).__name__})."


def send_async(conf, uid, title, cid, blocks, result):
    """Como send(), en un hilo; deja el resultado en el dict `result` ({"state": "sending"|"done", "ok": bool, "msg": str})."""
    result.update(state="sending", ok=False, msg="")

    def go():
        ok, msg = send(conf, uid, title, cid, blocks)
        result.update(state="done", ok=ok, msg=msg)
    threading.Thread(target=go, daemon=True).start()
