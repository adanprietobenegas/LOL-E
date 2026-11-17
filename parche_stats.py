"""Estadísticas del parche: cómo cambian las tasas de victoria, de uso y de baneo de cada campeón entre el parche elegido y el anterior (Lolalytics, partidas
clasificatorias en solitario del elo que se indique), y qué ha pasado con los campeones que tocaron las notas oficiales.

Todo el análisis es una función pura sobre diccionarios, para poder probarlo sin red. Los datos de un parche son «instantáneas»: se guardan en
cache/parche/stats_<parche>_<elo>.json (el parche en curso se refresca varias veces al día; los antiguos, casi nunca). Con el parche en curso
además se guarda una foto por día (cache/parche/dias_<parche>_<elo>.json) para poder ver cómo se mueve la muestra y, con los días, las tendencias.

Qué NO se hace: no se afirma causa y efecto. Las cifras de los primeros días de un parche tienen muy pocas partidas y se mueven mucho; por eso cada cifra
lleva su muestra y la pantalla avisa cuando el parche aún es provisional (ver `reliability`).
"""
import json, os, re, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

LANES = ("top", "jungle", "middle", "bottom", "support")
LANE_ES = {"top": "Superior", "jungle": "Jungla", "middle": "Central", "bottom": "Tirador", "support": "Apoyo"}
URL = "https://a1.lolalytics.com/mega/?ep=list&v=1&patch={patch}&lane={lane}&tier={tier}&queue=420&region=all"
UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)"}
VERSION = 2
TTL_CURRENT = 5 * 3600
TTL_OLD = 30 * 24 * 3600
MIN_GAMES = 300         # partidas mínimas (por campeón y línea) para comparar victorias entre parches
MIN_USE = 0.4           # uso mínimo (%) para que una subida de uso signifique algo
# muestra del parche (partidas sumadas de todos los campeones y líneas) respecto a la del parche anterior completo: por debajo, «provisional»
PROVISIONAL = 0.35


def internal(public):
    """«26.22» (numeración pública) -> «16.22» (la que usan Data Dragon y Lolalytics)."""
    try:
        a, b = str(public).split(".")[:2]
        return f"{int(a) - 10}.{int(b)}"
    except Exception:
        return str(public)


def public(internal_v):
    try:
        a, b = str(internal_v).split(".")[:2]
        return f"{int(a) + 10}.{int(b)}"
    except Exception:
        return str(internal_v)


def prev_version(v):
    """Versión anterior (misma numeración): «26.22» -> «26.21»; la primera del año no tiene (lo importante es no inventarla)."""
    try:
        a, b = str(v).split(".")[:2]
        return f"{a}.{int(b) - 1}" if int(b) > 1 else None
    except Exception:
        return None


# ---------------------------------------------------------------- descarga
def _fetch_lane(patch, lane, tier):
    req = urllib.request.Request(URL.format(patch=patch, lane=lane, tier=tier), headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode("utf8"))
    return parse_lane(d, lane), d.get("avgWr")


def parse_lane(d, lane):
    """{id_campeón: {wr, pr, br, games, share, home}} de la respuesta de Lolalytics para una línea; solo los que juegan de verdad en esa línea.
    `share`: % de las partidas del campeón que se juegan en ESTA línea; `home`: su línea más habitual."""
    out = {}
    for k, v in (d.get("cid") or {}).items():
        if not isinstance(v, dict) or v.get("lane", lane) != lane or not v.get("games"):
            continue
        try:
            out[int(k)] = {"wr": float(v["wr"]), "pr": float(v.get("pr") or 0), "br": float(v.get("br") or 0), "games": int(v["games"]),
                           "share": float(v.get("pctLane") or 0), "home": v.get("defaultLane") or lane}
        except (KeyError, TypeError, ValueError):
            continue
    if out:   # validador de forma: la tasa de victorias debe estar en porcentaje (≈ 50)
        wrs = sorted(x["wr"] for x in out.values())
        if not 35 <= wrs[len(wrs) // 2] <= 65:
            raise ValueError("el formato de Lolalytics ha cambiado (tasas de victoria fuera de rango)")
    return out


def total_games(snap):
    """Partidas distintas aproximadas: la suma de partidas por campeón y línea entre 10 (cada partida tiene 10 campeones)."""
    return int(sum(x["games"] for l in snap["lanes"].values() for x in l.values()) / 10)


def _path(cache_dir, name):
    return os.path.join(cache_dir, "parche", name)


def _read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)


def snapshot(cache_dir, public_v, tier, current=False, force=False):
    """Estadísticas del parche `public_v` («26.22») en el elo `tier` («emerald_plus»), o None si Lolalytics aún no tiene datos. Se guardan en disco."""
    patch = internal(public_v)
    p = _path(cache_dir, f"stats_{patch}_{tier}.json")
    saved = _read(p)
    ttl = TTL_CURRENT if current else TTL_OLD
    if saved and saved.get("schema") == VERSION and not force and time.time() - saved.get("ts", 0) < ttl:
        return _ints(saved)
    try:
        with ThreadPoolExecutor(max_workers=5) as ex:
            res = list(ex.map(lambda ln: _fetch_lane(patch, ln, tier), LANES))
        lanes = {ln: r[0] for ln, r in zip(LANES, res)}
        snap = {"schema": VERSION, "ts": time.time(), "patch": public_v, "tier": tier, "lanes": lanes,
                "avg": {ln: r[1] for ln, r in zip(LANES, res)}}
        if not any(lanes.values()):
            return _ints(saved) if saved else None
        _write(p, {**snap, "lanes": {ln: {str(c): v for c, v in d.items()} for ln, d in lanes.items()}})
        if current:
            _day(cache_dir, patch, tier, snap)
        return snap
    except Exception:
        return _ints(saved) if saved else None


def _ints(saved):
    return {**saved, "lanes": {ln: {int(c): v for c, v in d.items()} for ln, d in saved["lanes"].items()}}


def _day(cache_dir, patch, tier, snap):
    """Una foto por día del parche en curso (condensada): crece poco y deja ver cómo se mueve la muestra."""
    p = _path(cache_dir, f"dias_{patch}_{tier}.json")
    days = _read(p) or {}
    today = time.strftime("%Y-%m-%d")
    days[today] = {"games": total_games(snap), "rows": {f"{ln}:{c}": [round(x["wr"], 2), round(x["pr"], 2), x["games"]]
                                                       for ln, d in snap["lanes"].items() for c, x in d.items() if x["games"] >= 100}}
    for old in sorted(days)[:-21]:
        del days[old]
    _write(p, days)


def days(cache_dir, public_v, tier):
    """{día: {games, rows}} del parche (solo existe si LOL-E estaba abierto en esos días)."""
    return _read(_path(cache_dir, f"dias_{internal(public_v)}_{tier}.json")) or {}


# ---------------------------------------------------------------- análisis (funciones puras)
def reliability(cur, prev):
    """(0 a 1, texto): qué parte de la muestra de un parche completo lleva este. Con el primero se mide contra el anterior; sin anterior no se sabe."""
    if not cur:
        return 0.0, "sin datos"
    if not prev:
        return 1.0, ""
    a, b = total_games(cur), max(1, total_games(prev))
    r = min(1.0, a / b)
    if r >= PROVISIONAL:
        return r, ""
    return r, f"Datos provisionales: el parche lleva el {round(r * 100)} % de las partidas de un parche completo. Las cifras se mueven mucho los primeros días."


def compare(cur, prev):
    """Filas de comparación por (campeón, línea) presentes en los dos parches:
    {cid, lane, wr, wr0, dwr, pr, pr0, dpr, br, br0, dbr, games, games0, share, share0, home}. Sin `prev`, filas con deltas a None."""
    rows = []
    for ln in LANES:
        for cid, x in (cur["lanes"].get(ln) or {}).items():
            y = ((prev or {}).get("lanes", {}).get(ln) or {}).get(cid)
            rows.append({"cid": cid, "lane": ln, "wr": x["wr"], "pr": x["pr"], "br": x["br"], "games": x["games"], "share": x["share"], "home": x["home"],
                         "wr0": y["wr"] if y else None, "pr0": y["pr"] if y else None, "br0": y["br"] if y else None, "games0": y["games"] if y else 0,
                         "share0": y["share"] if y else None,
                         "dwr": round(x["wr"] - y["wr"], 2) if y else None, "dpr": round(x["pr"] - y["pr"], 2) if y else None,
                         "dbr": round(x["br"] - y["br"], 2) if y else None})
    return rows


def zscore(r):
    """Cuántas veces mayor es el cambio de victorias que su margen de error (≈ 50/√partidas puntos en cada parche): por debajo de ~2 puede ser solo ruido."""
    if r["dwr"] is None or not r["games"] or not r["games0"]:
        return 0.0
    se = ((50 / r["games"] ** 0.5) ** 2 + (50 / r["games0"] ** 0.5) ** 2) ** 0.5
    return abs(r["dwr"]) / se if se else 0.0


def rankings(rows, lane=None, only=None, n=8, min_games=MIN_GAMES, scale=1.0):
    """Las listas de la pantalla. `lane`: una línea o None (todas); `only`: conjunto de campeones o None; `scale`: fracción de muestra del parche (0 a 1) para
    rebajar el mínimo de partidas cuando el parche es nuevo. Las victorias solo cuentan si el cambio supera su margen de error (z ≥ 1,8) y hay muestra
    de verdad (≥ 1.500 partidas, escalado); el uso, con un mínimo de uso; los baneos van por campeón (una fila por campeón, en su línea principal).
    Devuelve {clave: [filas]}."""
    sc = max(0.15, min(1.0, scale))
    mg = max(120, int(1500 * sc))
    pool = [r for r in rows if (lane is None or r["lane"] == lane) and (only is None or r["cid"] in only)]
    for r in pool:
        r["z"] = zscore(r)
    both = [r for r in pool if r["dwr"] is not None and r["games"] >= mg and r["games0"] >= 400 and r["z"] >= 1.8 and r["pr"] >= 0.3]
    used = [r for r in pool if r["dpr"] is not None and r["pr"] >= MIN_USE and r["pr0"] is not None and r["pr0"] >= MIN_USE * 0.5]
    wr_up = sorted((r for r in both if r["dwr"] > 0), key=lambda r: -r["dwr"])[:n]
    wr_dn = sorted((r for r in both if r["dwr"] < 0), key=lambda r: r["dwr"])[:n]
    pr_up = sorted((r for r in used if r["dpr"] > 0), key=lambda r: -r["dpr"] / max(0.3, r["pr0"]))[:n]
    pr_dn = sorted((r for r in used if r["dpr"] < 0), key=lambda r: r["dpr"] / max(0.3, r["pr0"]))[:n]
    main = {}
    for r in pool:   # el baneo es del campeón, no de la línea: una sola fila por campeón (la línea donde más juega)
        if r["cid"] not in main or r["games"] > main[r["cid"]]["games"]:
            main[r["cid"]] = r
    bans = sorted((r for r in main.values() if r["br"] >= 1.0), key=lambda r: -r["br"])[:n]
    ban_up = sorted((r for r in main.values() if r["dbr"] is not None and r["dbr"] >= 0.8), key=lambda r: -r["dbr"])[:n]
    return {"wr_up": wr_up, "wr_dn": wr_dn, "pr_up": pr_up, "pr_dn": pr_dn, "bans": bans, "ban_up": ban_up}


def lane_shifts(rows, n=8, min_share=6.0, jump=7.0):
    """Campeones que cambian de sitio: su línea principal ya no es la del parche anterior, o ganan o pierden `jump` puntos del reparto de sus partidas en una línea
    en la que juegan al menos `min_share` %. [{cid, lane, share, share0, dshare, home, kind}] con kind «main» (cambia de línea principal) o «grow»/«fall»."""
    by = {}
    for r in rows:
        by.setdefault(r["cid"], []).append(r)
    out = []
    for cid, rs in by.items():
        cur_main = max(rs, key=lambda r: r["games"])
        prev_rows = [r for r in rs if r["share0"] is not None]
        if len(prev_rows) < 1:
            continue
        prev_main = max(prev_rows, key=lambda r: r["games0"])
        if cur_main["lane"] != prev_main["lane"] and cur_main["games"] >= 150 and prev_main["games0"] >= 150 and cur_main["share"] - (cur_main["share0"] or 0) >= 10:
            out.append({"cid": cid, "lane": cur_main["lane"], "from": prev_main["lane"], "share": cur_main["share"], "share0": cur_main["share0"] or 0.0,
                        "dshare": round(cur_main["share"] - (cur_main["share0"] or 0.0), 1), "kind": "main", "games": cur_main["games"]})
            continue
        for r in rs:
            if r["share0"] is None:
                continue
            d = r["share"] - r["share0"]
            if abs(d) >= jump and max(r["share"], r["share0"]) >= min_share and r["games"] >= 150:
                out.append({"cid": cid, "lane": r["lane"], "from": None, "share": r["share"], "share0": r["share0"], "dshare": round(d, 1),
                            "kind": "grow" if d > 0 else "fall", "games": r["games"]})
    out.sort(key=lambda x: (-abs(x["dshare"]), -x["games"]))
    return out[:n]


def champion_index(champs):
    """{clave: id} para casar fichas de las notas con campeones: por la clave del enlace oficial, por el icono y por el nombre sin signos."""
    idx = {}
    for cid, c in champs.items():
        for k in (c.get("icon"), c.get("name"), c.get("key")):
            if k:
                idx.setdefault(re.sub(r"[^a-z0-9]", "", str(k).lower()), cid)
    idx.setdefault("wukong", idx.get("monkeyking"))
    idx.setdefault("nunu", idx.get("nunuywillump"))
    idx.setdefault("renataglasc", idx.get("renata"))
    return {k: v for k, v in idx.items() if v}


def note_effects(changes, rows, index):
    """Para cada campeón tocado en las notas (parche.changes): cómo se ha movido su línea principal.
    [{cid, name, verdict, lane, dwr, dpr, games, wr, pr, expected}] ordenado por tamaño del cambio de victorias; `expected`: True si el cambio de victorias va en el sentido de
    la nota (mejora y sube, debilitación y baja), False si va al revés, None si no hay veredicto claro o no hay datos."""
    by = {}
    for r in rows:
        by.setdefault(r["cid"], []).append(r)
    out, seen = [], set()
    for ch in changes:
        if ch.get("section") not in ("champions", "other", None) and ch.get("section") != "champions":
            continue
        cid = index.get(re.sub(r"[^a-z0-9]", "", ch["slug"].lower())) or index.get(re.sub(r"[^a-z0-9]", "", ch["name"].lower()))
        if not cid or cid in seen or cid not in by:
            continue
        seen.add(cid)
        main = max(by[cid], key=lambda r: r["games"])
        exp = None
        if main["dwr"] is not None and ch["verdict"] in ("buff", "nerf"):
            exp = (main["dwr"] > 0) == (ch["verdict"] == "buff") if abs(main["dwr"]) >= 0.3 else None
        out.append({"cid": cid, "name": ch["name"], "verdict": ch["verdict"], "lane": main["lane"], "dwr": main["dwr"], "dpr": main["dpr"], "games": main["games"],
                    "wr": main["wr"], "pr": main["pr"], "expected": exp})
    out.sort(key=lambda x: -abs(x["dwr"] if x["dwr"] is not None else 0))
    return out


def summary_line(cur, prev):
    """Una frase con lo esencial del parche (para la cabecera)."""
    if not cur:
        return "Aún no hay estadísticas de este parche."
    n = total_games(cur)
    s = f"{n:,} partidas analizadas".replace(",", ".")
    if prev:
        s += f" (el parche anterior: {total_games(prev):,})".replace(",", ".")
    return s
