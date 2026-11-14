"""Patrones que se repiten en tus partidas analizadas: no «qué pasó en esta», sino «qué te pasa una y otra vez cuando pierdes».

Sin ventana ni red. Entrada: los análisis guardados en cache/analysis (uno por partida, ver analysis.compute). Solo cuentan partidas de la Grieta
(las colas con línea y rival directo) y solo se enseña un patrón si hay muestra suficiente y se separa claramente entre derrotas y victorias."""
import glob
import json
import os

import analysis

QUEUES = {400, 420, 430, 440}
MIN_GAMES, MIN_LOSSES, MIN_WINS = 8, 4, 3
MIN_RATE, MIN_GAP = 0.6, 0.25          # en derrotas ≥ 60 % y al menos 25 puntos más que en victorias
EARLY = 15                            # minuto límite de «temprano»


def early_deaths(a):
    """Veces que moriste antes del minuto 15."""
    return sum(1 for k in a.get("kills") or [] if k.get("victim") == a["me"] and k.get("t", 99) < EARLY)


def _checks(a):
    """Cada condición de la partida: {clave: bool o None si no se puede saber}."""
    out = {"muertes_pronto": early_deaths(a) >= 2}
    opp = analysis.default_opp(a)
    m = analysis.me(a)
    cp = analysis.checkpoints(a, opp) if opp and analysis.player(a, opp) else {}
    cs10 = (cp.get(10) or {}).get("cs")
    out["farmeo_10"] = (cs10[0] - cs10[1] <= -10) if cs10 and m.get("role") in ("TOP", "MIDDLE", "BOTTOM") else None
    g15 = (cp.get(15) or {}).get("gold")
    out["oro_15"] = (g15[0] - g15[1] <= -1000) if g15 else None
    return out


TEXT = {
    "muertes_pronto": "moriste 2 o más veces antes del minuto 15",
    "farmeo_10": "ibas 10 súbditos o más por detrás de tu rival en el minuto 10",
    "oro_15": "ibas 1.000 de oro o más por detrás de tu rival en el minuto 15",
}


def find(analyses):
    """El patrón más claro entre las derrotas, o None. Resultado: {clave, texto, derrotas: (cumplen, total), victorias: (cumplen, total)}."""
    rows = []
    for a in analyses:
        try:
            if a.get("queue") not in QUEUES or not a.get("players") or str(a.get("me")) not in a["players"]:
                continue
            rows.append((bool(a.get("win")), _checks(a)))
        except Exception:
            continue
    if len(rows) < MIN_GAMES:
        return None
    best = None
    for key, text in TEXT.items():
        lo = [c[key] for w, c in rows if not w and c.get(key) is not None]
        wi = [c[key] for w, c in rows if w and c.get(key) is not None]
        if len(lo) < MIN_LOSSES or len(wi) < MIN_WINS:
            continue
        rl, rw = sum(lo) / len(lo), sum(wi) / len(wi)
        if rl >= MIN_RATE and rl - rw >= MIN_GAP and (best is None or rl - rw > best[0]):
            best = (rl - rw, {"clave": key, "texto": text, "derrotas": (sum(lo), len(lo)), "victorias": (sum(wi), len(wi))})
    return best[1] if best else None


def sentence(p):
    """La frase para el jugador."""
    if not p:
        return None
    (a, b), (c, d) = p["derrotas"], p["victorias"]
    return f"Patrón en tus derrotas: en {a} de {b} {p['texto']}; en tus victorias, en {c} de {d}."


GOAL = {
    "muertes_pronto": "no mueras más de una vez antes del minuto 15.",
    "farmeo_10": "llega al minuto 10 a menos de 10 súbditos de tu rival.",
    "oro_15": "no vayas 1.000 de oro por detrás en el minuto 15: si pierdes la línea, juega seguro y cede el farmeo.",
}


def goal(p):
    """Un objetivo medible para la próxima partida, sacado del patrón (None si no hay patrón)."""
    return "Tu objetivo: " + GOAL[p["clave"]] if p and p.get("clave") in GOAL else None


def result(a, p):
    """¿Se cumplió el objetivo en esta partida? (cumplido, frase), o None si no hay patrón, no es de la Grieta o no se puede saber."""
    try:
        if not p or p.get("clave") not in GOAL or a.get("queue") not in QUEUES or str(a.get("me")) not in a["players"]:
            return None
        bad = _checks(a).get(p["clave"])
    except Exception:
        return None
    if bad is None:
        return None
    return (not bad), ("Objetivo cumplido: " if not bad else "Objetivo no cumplido: ") + GOAL[p["clave"]]


_CACHE = {}
_NOW = {}      # cache_dir -> (instante, patrón): lo calculado se reutiliza unos segundos, porque el Plan se repinta a menudo


def current(cache_dir, every=30):
    """El patrón vigente (None si no hay), recalculado como mucho cada `every` segundos: leer y analizar hasta 80 partidas en cada repintado costaría."""
    import time
    t, p = _NOW.get(cache_dir, (0, None))
    if time.time() - t < every:
        return p
    try:
        p = find(load(cache_dir))
    except Exception:
        p = None
    _NOW[cache_dir] = (time.time(), p)
    return p




def load(cache_dir, limit=80):
    """Los análisis guardados más recientes (se releen solo si cambia la carpeta)."""
    files = glob.glob(os.path.join(cache_dir, "analysis", "*.json"))
    sig = (len(files), max((os.path.getmtime(f) for f in files), default=0))
    if _CACHE.get(cache_dir, (None,))[0] == sig:
        return _CACHE[cache_dir][1]
    out = []
    for f in sorted(files, key=os.path.getmtime, reverse=True)[:limit]:
        try:
            with open(f, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except Exception:
            continue
    _CACHE[cache_dir] = (sig, out)
    return out
