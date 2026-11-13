"""Picks en auge: qué campeones suben de uso en una línea, en tu servidor y en las regiones que suelen ir por delante.

Qué se mide y por qué. Se probó con datos reales de 10 parches seguidos (8 transiciones), 14 regiones y Esmeralda o superior:
  · Lo que importa es el CAMBIO de uso frente al parche anterior, no el nivel. Que un campeón se juegue más en Corea que en EUW es casi
    siempre una diferencia permanente de gustos y casi no avisa de nada (~1 % de acierto).
  · Que el uso SUBA (1,6 veces o más, con 60 partidas y 0,5 % de uso como mínimo) en una región líder sí precede a EUW:
      1 región líder sube        -> el uso en EUW acabó subiendo en ~1 de cada 10 casos
      2 o más regiones líderes   -> en ~1 de cada 4 (26 %, 27 casos)
      3 o más                    -> en ~4 de cada 10 (10 casos)
      una sola con subida x2,5   -> ~1 de cada 4 (34 casos)
    El azar da menos de 1 de cada 100. Muestra pequeña: es una pista, no una garantía; la ventaja suele ser de 1 a 2 parches.
  · Regiones líderes (las que mejor adelantan): Corea, Japón, Taiwán, Singapur, Vietnam, Norteamérica y Oceanía. Europa del Este, Turquía,
    Brasil y Latinoamérica no aportaron nada. China no está en las fuentes públicas. La tasa de victorias tampoco mejoró el acierto.
  · Un parche recién salido tiene pocas partidas: se indica el tamaño de la muestra.
"""
import json, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

LANES = ("top", "jungle", "middle", "bottom", "support")
LANE_ES = {"top": "superior", "jungle": "jungla", "middle": "central", "bottom": "tirador", "support": "apoyo"}
LEADERS = ("kr", "jp", "tw", "sg", "vn", "na", "oce")
REGION_ES = {"kr": "Corea", "jp": "Japón", "tw": "Taiwán", "sg": "Singapur", "vn": "Vietnam", "na": "Norteamérica", "oce": "Oceanía"}
REGIONS = {"euw", "eune", "na", "kr", "br", "vn", "jp", "tr", "ru", "oce", "lan", "las", "tw", "sg"}
URL = "https://a1.lolalytics.com/mega/?ep=list&v=1&patch={patch}&lane={lane}&tier=emerald_plus&queue=420&region={region}"
UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)"}
TTL = 12 * 3600
VERSION = 2


def prev_patch(p):
    try:
        major, minor = str(p).split(".")[:2]
        return f"{major}.{int(minor) - 1}" if int(minor) > 1 else None
    except Exception:
        return None


def _fetch(patch, lane, region):
    try:
        req = urllib.request.Request(URL.format(patch=patch, lane=lane, region=region), headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf8"))
    except Exception:
        return {}
    return {k: {"g": v.get("games", 0), "pr": v.get("pr", 0.0), "wr": v.get("wr", 0.0)} for k, v in (d.get("cid") or {}).items()
            if isinstance(v, dict) and v.get("games", 0) >= 1}


def load(cache_dir, patch, force=False, region="all"):
    """{patch, prev, region, lanes: {línea: {id: {g, pr, wr, gp, pp, r: {región líder: [g, pr, pr anterior]}}}}} o lanza una excepción.

    «region» es tu servidor (euw, na…) o «all»; las regiones líderes se comparan siempre."""
    region = region if region in REGIONS else "all"
    path = os.path.join(cache_dir, "trends.json")
    saved = None
    try:
        saved = json.load(open(path, encoding="utf-8"))
        if not force and saved.get("v") == VERSION and saved["patch"] == patch and saved.get("region") == region and time.time() - saved["ts"] < TTL:
            return saved
    except Exception:
        pass
    prev = prev_patch(patch)
    regs = [region] + [r for r in LEADERS if r != region]
    jobs = [(p, ln, rg) for ln in LANES for rg in regs for p in (patch, prev) if p]
    with ThreadPoolExecutor(8) as ex:
        res = dict(zip(jobs, ex.map(lambda j: _fetch(*j), jobs)))
    lanes = {}
    for ln in LANES:
        cur, old = res.get((patch, ln, region), {}), res.get((prev, ln, region), {})
        rows = {}
        for cid in set(cur) | set(old):
            c, o = cur.get(cid, {}), old.get(cid, {})
            reg = {}
            for r in LEADERS:
                if r == region:
                    continue
                rc, ro = res.get((patch, ln, r), {}).get(cid), res.get((prev, ln, r), {}).get(cid)
                if rc:
                    reg[r] = [rc["g"], rc["pr"], ro["pr"] if ro else 0.0]
            rows[cid] = {"g": c.get("g", 0), "pr": c.get("pr", 0.0), "wr": c.get("wr", 0.0), "gp": o.get("g", 0), "pp": o.get("pr", 0.0), "r": reg}
        lanes[ln] = rows
    if not any(lanes.values()):
        if saved and saved.get("v") == VERSION and saved.get("lanes"):   # sin red: las últimas tendencias guardadas, marcadas
            return {**saved, "stale": True}
        raise RuntimeError("sin datos de tendencias")
    data = {"v": VERSION, "ts": time.time(), "patch": patch, "prev": prev, "region": region, "lanes": lanes}
    os.makedirs(cache_dir, exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"))
    return data


def entry(data, lane, cid):
    return ((data or {}).get("lanes", {}).get(lane) or {}).get(str(cid))


def pct(x):
    return f"{x:.1f}".replace(".", ",") if x >= 0.1 else f"{x:.2f}".replace(".", ",")


def analyse(e):
    """Señales de un campeón en una línea.

    rising: su uso sube en tu servidor. leaders: regiones líderes donde sube y aquí aún va por detrás.
    level: «fuerte» (2 o más regiones líderes, o una con subida de x2,5) o «posible» (una región)."""
    if not e:
        return {"rising": False, "leaders": [], "level": "", "strong": False}
    rising = e["g"] >= 50 and e["pr"] >= 0.3 and e["pr"] >= 1.6 * max(e["pp"], 0.05)
    leaders, big = [], False
    for r, (g, pr, pp) in (e.get("r") or {}).items():
        if g >= 60 and pr >= 0.5 and pr >= 1.6 * max(pp, 0.05) and pr > 1.2 * e["pr"]:
            leaders.append(r)
            big = big or pr >= 2.5 * max(pp, 0.05)
    level = "fuerte" if (len(leaders) >= 2 or (leaders and big)) else ("posible" if leaders else "")
    return {"rising": rising, "leaders": leaders, "level": level, "strong": level == "fuerte"}


def short_flag(data, lane, cid):
    a = analyse(entry(data, lane, cid))
    if a["rising"]:
        return "en auge"
    if a["level"] == "fuerte":
        return "en auge fuera de aquí"
    if a["leaders"]:
        return f"sube en {REGION_ES[a['leaders'][0]]}"
    return ""


def _names(regs):
    n = [REGION_ES[r] for r in regs]
    return n[0] if len(n) == 1 else ", ".join(n[:-1]) + " y " + n[-1]


def describe(data, lane, cid):
    """Explicación en español de cómo va un campeón en una línea (qué se sabe y con cuánta muestra)."""
    e = entry(data, lane, cid)
    nm = LANE_ES.get(lane, lane)
    if not e:
        return "Sin datos de uso en esa línea: casi no se juega ahí."
    a = analyse(e)
    out = []
    if a["rising"]:
        out.append(f"En auge aquí: su uso en {nm} sube de {pct(e['pp'])} % a {pct(e['pr'])} % respecto al parche anterior ({e['g']} partidas este parche).")
    if a["leaders"]:
        det = ", ".join(f"{REGION_ES[r]} {pct(e['r'][r][2])} → {pct(e['r'][r][1])} %" for r in a["leaders"][:4])
        out.append(f"Sube en {_names(a['leaders'])} ({det}) y aquí va por detrás ({pct(e['pr'])} %).")
        out.append("Señal fuerte: en las pruebas con parches anteriores, cuando varias regiones líderes subían a la vez, el uso en EUW acabó subiendo en "
                   "cerca de 1 de cada 4 casos (el azar da menos de 1 de cada 100); no es una garantía." if a["strong"] else
                   "Señal posible: con una sola región líder, el uso en EUW subió después en cerca de 1 de cada 10 casos.")
    if not out:
        if e["pr"] < 0.3:
            out.append(f"Pick marginal en {nm}: {pct(e['pr'])} % de uso (parche anterior: {pct(e['pp'])} %). Sin señales de que vaya a más en las "
                       f"regiones que suelen ir por delante; con {e['g']} partidas este parche la muestra es pequeña.")
        else:
            out.append(f"Uso estable en {nm}: {pct(e['pr'])} % (parche anterior: {pct(e['pp'])} %).")
    if e["g"] < 100 and not a["rising"]:
        out.append("El parche es reciente: los datos aún cambiarán.")
    return " ".join(out)


def rising(data, lane, n=6):
    """Campeones con más subida de uso en una línea: (id, etiqueta) con «sube» (aquí) o «fuera» (en regiones líderes)."""
    rows = []
    for cid, e in ((data or {}).get("lanes", {}).get(lane) or {}).items():
        a = analyse(e)
        if a["rising"] or a["level"]:
            gain = max(e["pr"] - e["pp"] if a["rising"] else 0, max((e["r"][r][1] - e["r"][r][2] for r in a["leaders"]), default=0))
            score = gain + (1.0 if a["level"] == "fuerte" else 0)
            rows.append((score, int(cid), "sube" if a["rising"] else "fuera"))
    rows.sort(reverse=True)
    return [(cid, tag) for _, cid, tag in rows[:n]]
