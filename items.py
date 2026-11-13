"""Objetos del juego (Data Dragon, oficial de Riot): nombre, coste, descripción corta e icono, en español."""
import json, os, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)"}
SCHEMA = 4   # 4: añade «from» (la receta de cada objeto, con repetición)


def load(cache_dir, version):
    """{id: {n: nombre, g: coste total, d: descripción corta, i: archivo de icono}}. Se guarda por parche."""
    path = os.path.join(cache_dir, "items.json")
    try:
        saved = json.load(open(path, encoding="utf-8"))
        if saved.get("version") == version and saved.get("items") and saved.get("schema") == SCHEMA:
            return {int(k): v for k, v in saved["items"].items()}
    except Exception:
        saved = None
    try:
        req = urllib.request.Request(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES/item.json", headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf8"))["data"]
    except Exception:
        # sin red: lo guardado de este mismo parche sirve aunque sea de un esquema anterior (sin recetas: «Puedes comprar» no opinará)
        if isinstance(saved, dict) and saved.get("version") == version and saved.get("items"):
            return {int(k): v for k, v in saved["items"].items()}
        raise
    items = {int(k): {"n": v.get("name", ""), "g": (v.get("gold") or {}).get("total", 0), "d": v.get("plaintext", ""),
                      "i": (v.get("image") or {}).get("full", f"{k}.png"), "t": v.get("tags") or [], "into": [int(x) for x in v.get("into", [])],
                      "from": [int(x) for x in v.get("from", [])], "depth": v.get("depth"), "x": _effects(v.get("description", ""))}
             for k, v in data.items()}
    os.makedirs(cache_dir, exist_ok=True)
    json.dump({"version": version, "schema": SCHEMA, "items": items}, open(path, "w", encoding="utf-8"))
    return items


def _effects(desc):
    """Efectos útiles para elegir objetos según la situación, sacados de la descripción oficial: antiheal, tenacidad, vidamax…"""
    d = desc.lower()
    out = []
    if "heridas graves" in d:
        out.append("antiheal")
    if "tenacidad" in d:
        out.append("tenacidad")
    if "penetración de armadura" in d or "penetración de armadura".replace("ó", "o") in d:
        out.append("penarm")
    if "penetración mágica" in d:
        out.append("penmag")
    if "vida máxima" in d and "daño" in d and "objetivo" in d:
        out.append("vidamax")
    return out


def icon_url(version, iid):
    return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{iid}.png"
