"""Tu rango en el tiempo: la serie que dibuja la gráfica de PL. Sin ventana ni red: solo cuentas, para poder probarla.

Dos fuentes, mezcladas:
  · tus partidas que LOL-E vio con la app abierta (`lp.json`: PL ganados o perdidos y rango resultante, más el historial: fecha, campeón y
    si ganaste). Son puntos «de partida».
  · fotos diarias de tu rango que da op.gg (`opgg_lp.json`), que solo enseña las últimas jornadas: cada vez que LOL-E las lee se guardan y
    así la historia crece sola. Son puntos «del día», y solo se usan en los días en los que no hay ninguna partida propia.
El rango se mide en una sola escala, `analysis.ladder_value` (cada división son 100; de maestro para arriba, el PL a secas)."""
import datetime
import json
import os

import analysis
from players import TIERS_ES

KEY_OF = {v: k for k, v in TIERS_ES.items()}          # «Platino» -> PLATINUM
QUEUE_OF = {420: "solo", 440: "flex"}
ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV"}
RANGES = [("20 partidas", "n20"), ("7 días", "7"), ("30 días", "30"), ("90 días", "90"), ("Este año", "year"), ("Todo", "all")]
DAY_MS = 86_400_000


def value_of(key, div, lp):
    """Rango (clave inglesa del tier, división romana o «», PL) como número de la escala, o None si no se entiende."""
    return analysis.ladder_value({"key": key, "div": div or "", "lp": lp or 0}) if key in analysis.TIER_ORDER else None


def parse_tier_text(txt):
    """«Platino III» -> («PLATINUM», «III»); «Maestro» -> («MASTER», «»); (None, «») si no se reconoce."""
    parts = (txt or "").strip().rsplit(" ", 1)
    if len(parts) == 2 and parts[1] in analysis.DIV_ORDER and parts[0] in KEY_OF:
        return KEY_OF[parts[0]], parts[1]
    if (txt or "").strip() in KEY_OF:
        return KEY_OF[txt.strip()], ""
    return None, ""


def label_of(value):
    """Nombre de la división que empieza en ese valor de la escala («Oro II»), o «Maestro+» para el techo."""
    tier = int(value // 400)
    if tier >= analysis.TIER_ORDER.index("MASTER"):
        return "Maestro+"
    div = {v: k for k, v in analysis.DIV_ORDER.items()}.get(int((value % 400) // 100), "")
    return f"{TIERS_ES[analysis.TIER_ORDER[tier]]} {div}"


def game_points(lp, games, queue):
    """Puntos de partida de una cola («solo» o «flex»), por orden de fecha. `lp`: contenido de lp.json; `games`: partidas del historial."""
    out = []
    for e in sorted(games, key=lambda e: e.get("t", 0)):
        if QUEUE_OF.get(e.get("q")) != queue or e.get("rm"):
            continue
        v = (lp or {}).get(str(e.get("id")))
        if not isinstance(v, dict) or not isinstance(v.get("d"), (int, float)):
            continue
        key, div = parse_tier_text(v.get("tier"))
        value = value_of(key, div, v.get("now")) if key else None
        if value is None:
            continue
        out.append({"t": e["t"], "v": value, "d": int(v["d"]), "cid": e.get("c"), "w": bool(e.get("w")), "tier": v["tier"], "lp": v.get("now", 0), "src": "game", "id": str(e.get("id"))})
    return out


def parse_snapshots(histories):
    """Fotos diarias de op.gg (`lpHistories`: [{created_at, tier_info: {lp, tier, label}}]) -> {fecha: {t, key, div, lp}}. Ignora lo que no entienda."""
    out = {}
    for h in histories or []:
        try:
            t = int(datetime.datetime.fromisoformat(h["created_at"]).timestamp() * 1000)
            info = h["tier_info"]
            key = str(info["tier"]).upper()
            div = "" if key in ("MASTER", "GRANDMASTER", "CHALLENGER") else ROMAN.get(str(info.get("label", "")).strip()[-1:], "")
            if key not in analysis.TIER_ORDER or (key not in ("MASTER", "GRANDMASTER", "CHALLENGER") and not div):
                continue
            out[h["created_at"][:10]] = {"t": t, "key": key, "div": div, "lp": int(info["lp"])}
        except (KeyError, TypeError, ValueError):
            continue
    return out


def load_snapshots(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_snapshots(path, new):
    """Suma fotos nuevas a las guardadas (por fecha) y devuelve cuántas eran nuevas."""
    cur = load_snapshots(path)
    added = sum(1 for k in new if k not in cur)
    cur.update(new)
    tmp = path + ".tmp"
    json.dump(cur, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, path)
    return added


def day_points(snaps, taken_days):
    """Puntos «del día» de op.gg en los días sin partida propia (`taken_days`: conjunto de fechas AAAA-MM-DD con partida)."""
    out = []
    for day, s in sorted(snaps.items()):
        value = value_of(s.get("key"), s.get("div"), s.get("lp"))
        if value is not None and day not in taken_days:
            out.append({"t": s["t"], "v": value, "d": None, "cid": None, "w": None,
                        "tier": f"{TIERS_ES.get(s['key'], s['key'])} {s.get('div', '')}".strip(), "lp": s.get("lp", 0), "src": "day"})
    return out


def _day(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).astimezone().strftime("%Y-%m-%d")


GAIN, LOSS = 21, 19   # PL medios por victoria y por derrota mientras no haya suficientes partidas propias con PL reales


def text_of(value):
    """Rango legible y PL de un valor de la escala: (« Oro II», 45); en maestro o más, («Maestro», PL)."""
    tier = min(int(value // 400), len(analysis.TIER_ORDER) - 1)
    if tier >= analysis.TIER_ORDER.index("MASTER"):
        return TIERS_ES["MASTER"], int(value - analysis.TIER_ORDER.index("MASTER") * 400)
    div = {v: k for k, v in analysis.DIV_ORDER.items()}.get(int((value % 400) // 100), "")
    return f"{TIERS_ES[analysis.TIER_ORDER[tier]]} {div}", int(value % 100)


def typical(real):
    """(PL por victoria, PL por derrota) típicos: la mediana de tus partidas con PL reales, o los valores medios si hay menos de 3 de cada."""
    import statistics
    wins = [p["d"] for p in real if p["w"] and p["d"] > 0]
    loss = [-p["d"] for p in real if not p["w"] and p["d"] < 0]
    return (statistics.median(wins) if len(wins) >= 3 else GAIN), (statistics.median(loss) if len(loss) >= 3 else LOSS)


def estimate(lp, games, snaps, queue="solo"):
    """Puntos ESTIMADOS (`src` «est») de las partidas de la cola sin PL guardado. Se apoyan en los puntos seguros (partidas con PL real y fotos
    de op.gg): entre dos de ellos se reparte lo que falta para que cuadre; antes del primero se resta, partida a partida, lo típico de una
    victoria o derrota. Es una aproximación: no sabe de escudos de ascenso, de lo que ganó o perdió cada partida de verdad ni de reinicios de temporada."""
    real = game_points(lp, games, queue)
    anchors = [(p["t"], p["v"] - p["d"], p["v"]) for p in real]           # (hora, valor antes, valor después)
    if queue == "solo":
        anchors += [(p["t"], p["v"], p["v"]) for p in day_points(snaps, set())]
    if not anchors:
        return []
    anchors.sort()
    have = {p["id"] for p in real}
    todo = sorted((e for e in games if QUEUE_OF.get(e.get("q")) == queue and not e.get("rm") and str(e.get("id")) not in have and e.get("t")),
                  key=lambda e: e["t"])
    gain, loss = typical(real)
    est = lambda e: gain if e.get("w") else -loss
    out = []

    def add(e, after, d):
        tier, pl = text_of(after)
        out.append({"t": e["t"], "v": after, "d": int(round(d)), "cid": e.get("c"), "w": bool(e.get("w")), "tier": tier, "lp": pl, "src": "est", "id": str(e.get("id"))})

    first = anchors[0]
    before = [e for e in todo if e["t"] < first[0]]
    cur = first[1]
    for e in reversed(before):                 # hacia atrás desde el primer punto seguro
        if cur < 0:
            break
        add(e, cur, est(e))
        cur -= est(e)
    for (ta, _ua, va), (tb, ub, _vb) in zip(anchors, anchors[1:]):   # entre dos puntos seguros: se reparte lo que falta
        mid = [e for e in todo if ta < e["t"] < tb]
        if not mid:
            continue
        fix = (ub - va - sum(est(e) for e in mid)) / len(mid)
        cur = va
        for e in mid:
            d = est(e) + fix
            cur += d
            add(e, cur, d)
    return [p for p in out if p["v"] >= 0]


def series(lp, games, snaps, queue="solo", with_estimate=False):
    """Todos los puntos de una cola por orden de fecha: partidas propias, las estimadas si se piden y, en los días sin partida, fotos de op.gg
    (que son de Solo/Dúo)."""
    mine = game_points(lp, games, queue) + (estimate(lp, games, snaps, queue) if with_estimate else [])
    extra = day_points(snaps, {_day(p["t"]) for p in mine}) if queue == "solo" else []
    return sorted(mine + extra, key=lambda p: p["t"])


def select(points, mode, now_ms):
    """Recorta la serie a un tramo: «n20» (las últimas 20 partidas), «7», «30», «90» (días), «year» (este año) o «all»."""
    if mode == "all" or not points:
        return list(points)
    if mode == "n20":
        games = [p for p in points if p["src"] in ("game", "est")]
        start = games[-20]["t"] if len(games) > 20 else 0
        return [p for p in points if p["t"] >= start]
    if mode == "year":
        start = datetime.datetime(datetime.datetime.fromtimestamp(now_ms / 1000).year, 1, 1).timestamp() * 1000
    else:
        start = now_ms - int(mode) * DAY_MS
    return [p for p in points if p["t"] >= start]


def bands(vmin, vmax):
    """Líneas de división visibles en el tramo: [(valor, nombre)] cada 100 de la escala (y la de maestro, que es el techo)."""
    top = analysis.TIER_ORDER.index("MASTER") * 400
    out = []
    v = int(vmin // 100) * 100
    while v <= vmax:
        if v >= vmin and (v <= top):
            out.append((v, label_of(v)))
        v += 100
    return out


def summary(points):
    """(PL ganados o perdidos en las partidas del tramo, partidas, victorias, derrotas). Cuentan los puntos de partida, reales y estimados."""
    games = [p for p in points if p["src"] in ("game", "est")]
    return sum(p["d"] for p in games), len(games), sum(1 for p in games if p["w"]), sum(1 for p in games if not p["w"])


def load_all(cache_dir):
    """(lp.json, fotos de op.gg) de la carpeta de datos; vacíos si no existen."""
    try:
        lp = json.load(open(os.path.join(cache_dir, "lp.json"), encoding="utf-8"))
    except Exception:
        lp = {}
    return (lp if isinstance(lp, dict) else {}), load_snapshots(os.path.join(cache_dir, "opgg_lp.json"))
