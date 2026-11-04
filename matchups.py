"""Enfrentamientos globales: los mejores picks contra un campeón rival, sin tener en cuenta tu repertorio.

Fuente: la página pública de «counters» de Lolalytics. Una descarga por rival y línea (≈1,3 MB, 0,2 s), guardada un día.
Si la web cambia o falla, la pestaña lo dice y el resto de la aplicación sigue igual.
"""
import json, os, re, time, urllib.error, urllib.request

LANES = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support"}
LANE_NAMES = {"top": "Superior", "jungle": "Jungla", "middle": "Central", "bottom": "Tirador", "support": "Apoyo"}
SLUG_FIX = {"monkeyking": "wukong"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)", "Accept-Language": "en"}
ROW = re.compile(r"\|([^|]{2,26})\|(\d{1,2}(?:\.\d+)?)%\|VS\|Δ\|1\| ?(-?\d+(?:\.\d+)?)\| • \|Δ\|2\| ?(-?\d+(?:\.\d+)?)\|"
                 r"(\d{1,2}(?:\.\d+)?)%\|VS\|([\d,]+) Games")
TTL = 24 * 3600


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def slug(champ):
    s = champ["icon"].lower()
    return SLUG_FIX.get(s, s)


def url_for(champ, lane, tier=None):
    return f"https://lolalytics.com/lol/{slug(champ)}/counters/?lane={lane}" + (f"&tier={tier}" if tier else "")


def vs_url(mine, enemy, lane, vslane=None):
    return f"https://lolalytics.com/lol/{slug(mine)}/vs/{slug(enemy)}/build/?lane={lane}&vslane={vslane or lane}"


def parse(html):
    """Filas (nombre, % de victorias del rival contra él, diferencia, partidas) a partir del HTML de la página."""
    i = html.index("WR vs")
    seg = re.sub(r"<img[^>]*>|<!--.*?-->", "", html[i:], flags=re.S)
    txt = re.sub(r"\|+", "|", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", seg)))
    rows, seen = [], set()
    for name, wr, d1, d2, avg, games in ROW.findall(txt):
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "wr": float(wr), "d1": float(d1), "d2": float(d2), "avg": float(avg), "games": int(games.replace(",", ""))})
    return rows


def load(cache_dir, champ, lane, force=False):
    """Filas de la página del rival `champ` en la línea `lane` (nombre de línea de Lolalytics)."""
    path = os.path.join(cache_dir, "matchups", f"{slug(champ)}_{lane}.json")
    try:
        saved = json.load(open(path, encoding="utf-8"))
        if not force and time.time() - saved["ts"] < TTL:
            return saved["rows"]
    except Exception:
        pass
    rows = []
    for tier in (None, "all"):  # primero el rango por defecto; si no hay datos, todos los rangos (campeones o líneas poco jugados)
        try:
            req = urllib.request.Request(url_for(champ, lane, tier), headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                rows = parse(r.read().decode("utf8", "replace"))
        except (ValueError, urllib.error.HTTPError):
            rows = []
        if rows:
            for r_ in rows:
                r_["tier"] = tier or "default"
            break
    if not rows:  # un campeón nuevo puede tener pocos enfrentamientos con datos: con alguno basta
        raise RuntimeError("Lolalytics no tiene todavía enfrentamientos de este campeón en esa línea. Prueba otra línea.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"ts": time.time(), "rows": rows}, open(path, "w", encoding="utf-8"))
    return rows


def best_against(champs, enemy_cid, lane, cache_dir, force=False, min_games=100):
    """Campeones ordenados por su tasa de victorias contra `enemy_cid`. Devuelve [{cid, wr, delta, games}]."""
    rows = load(cache_dir, champs[enemy_cid], lane, force)
    ids = {norm(c["name"]): cid for cid, c in champs.items()}
    out = []
    for r in rows:
        cid = ids.get(norm(r["name"]))
        if cid and r["games"] >= min_games:
            out.append({"cid": cid, "wr": round(100 - r["wr"], 2), "delta": round(-r["d1"], 2), "games": r["games"],
                        "tier": r.get("tier", "default")})
    out.sort(key=lambda x: -x["wr"])
    return out
