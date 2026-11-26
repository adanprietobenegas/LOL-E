"""Enviar la página de runas que enseña LOL-E al cliente de League, solo cuando el jugador pulsa el botón.

El cliente expone `/lol-perks/v1/pages` (comprobado en el propio cliente: leer, crear y modificar una página, y elegir la activa). Reglas:
- LOL-E usa UNA sola página, la que se llame «LOL-E…»: la modifica en su sitio.
- Si no la hay y queda un hueco, la crea. Si no queda hueco, no toca nada y lo dice (el jugador libera uno o renombra la que quiera ceder).
- Nunca borra páginas, ni suyas ni del jugador.
"""
import threading
import urllib.error

import itemset
import lol_advisor as core

PREFIX = "LOL-E"
PAGES = "/lol-perks/v1/pages"
NAME_MAX = 25   # el cliente corta los nombres largos


def page_body(champ_name, rn, rd):
    """La página en el formato del cliente, o None si falta algún dato (no se manda una página a medias).
    `rn`: {keystone, primary[3], secondary[2], shards[3]}; `rd`: datos de runas ({runes: {id: {t: árbol}}})."""
    runes = (rd or {}).get("runes") or {}
    key, pri = (rn or {}).get("keystone"), list((rn or {}).get("primary") or [])
    sec, shards = list((rn or {}).get("secondary") or []), list((rn or {}).get("shards") or [])
    if not key or len(pri) != 3 or len(sec) != 2 or len(shards) != 3 or not all(shards):
        return None
    main = {(runes.get(i) or {}).get("t") for i in [key] + pri}
    other = {(runes.get(i) or {}).get("t") for i in sec}
    if len(main) != 1 or len(other) != 1 or None in main | other or main == other:
        return None
    name = f"{PREFIX} · {champ_name}"[:NAME_MAX]
    return {"name": name, "primaryStyleId": main.pop(), "subStyleId": other.pop(), "selectedPerkIds": [key] + pri + sec + shards, "current": True}


def own_page(pages):
    """La página que LOL-E puede modificar: la primera editable y permanente cuyo nombre empiece por «LOL-E», o None."""
    return next((p for p in pages or [] if str(p.get("name") or "").upper().startswith(PREFIX) and p.get("isEditable") and not p.get("isTemporary")), None)


def apply(lcu, body):
    """Escribe la página y la deja activa. Devuelve (ok, mensaje)."""
    pages = lcu.get(PAGES)
    if pages is None:
        return False, "El cliente aún no da tus páginas de runas. Inténtalo en unos segundos."
    page = own_page(pages)
    if page:
        pid = page["id"]
        itemset._call(lcu, "PUT", f"{PAGES}/{pid}", body)
    else:
        inv = lcu.get("/lol-perks/v1/inventory") or {}
        if inv.get("canAddCustomPage") is False:
            return False, ("No queda ningún hueco de runas y LOL-E no borra tus páginas. En el cliente, borra una o ponle de nombre «LOL-E» "
                           "a la que quieras ceder, y vuelve a pulsar.")
        pid = (itemset._call(lcu, "POST", PAGES, body) or {}).get("id")
        if not pid:
            return False, "El cliente no ha creado la página."
    itemset._call(lcu, "PUT", "/lol-perks/v1/currentpage", pid)
    back = lcu.get(f"{PAGES}/{pid}") or {}
    if sorted(back.get("selectedPerkIds") or []) != sorted(body["selectedPerkIds"]) or back.get("isValid") is False:   # el cliente puede reordenarlas
        return False, "El cliente no ha guardado las runas: compruébalas antes de empezar."
    return True, f"Runas enviadas a la página «{body['name']}» y seleccionada. Compruébala antes de que acabe la selección."


def send(conf, champ_name, rn, rd):
    """Envía la página. Devuelve (ok, mensaje). Bloquea: llamar desde un hilo."""
    if getattr(core, "DEMO_MODE", False):   # la demostración usa datos inventados: nunca escribe en tu cliente
        return False, "En la demostración no se envía nada a tu cliente."
    body = page_body(champ_name, rn, rd)
    if body is None:
        return False, "Faltan datos de esta página de runas: ponlas a mano."
    try:
        found = core.find_client(conf)
        if not found:
            return False, "El cliente de League no está abierto."
        return apply(core.LCU(*found), body)
    except urllib.error.HTTPError as e:
        return False, f"El cliente rechazó las runas (error {e.code}): ponlas a mano."
    except Exception as e:
        return False, f"No se pudieron enviar ({type(e).__name__})."


def send_async(conf, champ_name, rn, rd, result):
    """Como send(), en un hilo; deja el resultado en `result` ({"state": "sending"|"done", "ok": bool, "msg": str})."""
    result.update(state="sending", ok=False, msg="")

    def go():
        ok, msg = send(conf, champ_name, rn, rd)
        result.update(state="done", ok=ok, msg=msg)
    threading.Thread(target=go, daemon=True).start()
