"""Objetos del juego (Data Dragon, oficial de Riot): nombre, coste, descripción corta e icono, en español."""
import json, os, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)"}


def load(cache_dir, version):
    """{id: {n: nombre, g: coste total, d: descripción corta, i: archivo de icono}}. Se guarda por parche."""
    path = os.path.join(cache_dir, "items.json")
    try:
        saved = json.load(open(path, encoding="utf-8"))
        if saved.get("version") == version and saved.get("items") and saved.get("schema") == 2:
            return {int(k): v for k, v in saved["items"].items()}
    except Exception:
        pass
    req = urllib.request.Request(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES/item.json", headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode("utf8"))["data"]
    items = {int(k): {"n": v.get("name", ""), "g": (v.get("gold") or {}).get("total", 0), "d": v.get("plaintext", ""),
                      "i": (v.get("image") or {}).get("full", f"{k}.png"), "t": v.get("tags") or [], "into": [int(x) for x in v.get("into", [])],
                      "depth": v.get("depth")} for k, v in data.items()}
    os.makedirs(cache_dir, exist_ok=True)
    json.dump({"version": version, "schema": 2, "items": items}, open(path, "w", encoding="utf-8"))
    return items


def icon_url(version, iid):
    return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/item/{iid}.png"
