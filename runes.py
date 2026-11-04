"""Runas y hechizos de invocador en español (Data Dragon, oficial de Riot): nombre, icono y descripción corta."""
import json, os, re, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)"}
SHARDS = {5008: ("Fuerza adaptable", "+9 de fuerza adaptable"), 5005: ("Velocidad de ataque", "+10 % de velocidad de ataque"),
          5007: ("Aceleración de habilidad", "+8 de aceleración de habilidad"), 5001: ("Vida escalable", "+10-180 de vida según el nivel"),
          5002: ("Armadura", "+6 de armadura"), 5003: ("Resistencia mágica", "+8 de resistencia mágica"),
          5010: ("Velocidad de movimiento", "+2 % de velocidad de movimiento"), 5011: ("Vida", "+65 de vida"),
          5013: ("Tenacidad y ralentización", "+10 % de tenacidad y resistencia a ralentizaciones")}


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
        return json.loads(r.read().decode("utf8"))


def clean(t):
    return re.sub(r"<[^>]+>", "", t or "").replace("&nbsp;", " ").strip()


def load(cache_dir, version):
    """{runes: {id: {n, i, d, t}}, trees: {id: nombre}, spells: {id: {n, i}}}. Se guarda por parche."""
    path = os.path.join(cache_dir, "runes.json")
    try:
        saved = json.load(open(path, encoding="utf-8"))
        if saved.get("version") == version:
            return {"runes": {int(k): v for k, v in saved["runes"].items()}, "trees": {int(k): v for k, v in saved["trees"].items()},
                    "spells": {int(k): v for k, v in saved["spells"].items()}}
    except Exception:
        pass
    base = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES"
    runes, trees = {}, {}
    for tree in _get(base + "/runesReforged.json"):
        trees[tree["id"]] = tree["name"]
        for slot in tree["slots"]:
            for r in slot["runes"]:
                runes[r["id"]] = {"n": r["name"], "i": r["icon"], "d": clean(r.get("shortDesc")), "t": tree["id"]}
    spells = {int(v["key"]): {"n": v["name"], "i": v["image"]["full"]} for v in _get(base + "/summoner.json")["data"].values()}
    os.makedirs(cache_dir, exist_ok=True)
    json.dump({"version": version, "runes": runes, "trees": trees, "spells": spells}, open(path, "w", encoding="utf-8"))
    return {"runes": runes, "trees": trees, "spells": spells}
