"""«Qué aprender»: huecos de tu repertorio por línea, con datos que ya tiene LOL-E (tus partidas, el meta de Lolalytics y tus campeones).

Solo se aconseja donde hay una conclusión clara: una línea que juegas mucho y en la que casi todo depende de un único campeón. Se proponen
campeones que ya tienes, con buena tasa de victoria en esa línea y con uso suficiente (no rarezas), prefiriendo los que ya conoces de otros modos.
Sin red ni ventana.
"""
SR_QUEUES = (400, 420, 430, 440, 490)      # modos con líneas (normales, clasificatorias, rápido)
ROLES = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT")
LANE_KEY = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support"}
ROLE_FIX = {"UTILITY": "SUPPORT"}


def advice(games, meta, owned=(), mastery=None, min_games=8, dependence=0.7, max_lanes=2, per_lane=3, min_pick=1.0, min_games_meta=3000):
    """Lista (de la línea más jugada a la menos) de {"role", "n", "main", "main_g", "main_wr", "cands": [(cid, wr_meta)]}.
    `games`: partidas del historial; `meta`: datos de meta.py (puede ser None: entonces no hay candidatos y no se aconseja);
    `owned`: ids que posees (vacío = no se sabe, no se filtra); `mastery`: {id: puntos}."""
    if not meta:
        return []
    mastery = mastery or {}
    lanes = {}
    for e in games:
        r = ROLE_FIX.get(e.get("r"), e.get("r"))
        if r in ROLES and e.get("q") in SR_QUEUES and not e.get("rm"):
            lanes.setdefault(r, []).append(e)
    out = []
    for role, gs in sorted(lanes.items(), key=lambda kv: -len(kv[1])):
        n = len(gs)
        if n < min_games:
            continue
        cnt = {}
        for e in gs:
            c = cnt.setdefault(e["c"], [0, 0])
            c[0] += 1
            c[1] += bool(e["w"])
        main, (mg, mw) = max(cnt.items(), key=lambda kv: kv[1][0])
        if mg / n < dependence:
            continue
        rows = (meta.get("lanes") or {}).get(LANE_KEY[role]) or {}
        avg = (meta.get("avg") or {}).get(LANE_KEY[role], 50)
        played = {c for c, (g, _w) in cnt.items() if g >= 2}
        cands = [(cid, v["wr"]) for cid, v in rows.items()
                 if cid not in played and (not owned or cid in owned) and v["wr"] >= avg + 0.5 and v.get("pr", 0) >= min_pick and v.get("games", 0) >= min_games_meta]
        cands.sort(key=lambda x: (mastery.get(x[0], 0) <= 0, -x[1]))   # primero los que ya conoces de otros modos, luego mejor tasa
        if cands:
            out.append({"role": role, "n": n, "main": main, "main_g": mg, "main_wr": mw / mg, "cands": cands[:per_lane]})
        if len(out) >= max_lanes:
            break
    return out


def line(item, name):
    """Frase para la pantalla; `name(cid)` devuelve el nombre del campeón."""
    pct = round(item["main_g"] / item["n"] * 100)
    return (f"El {pct} % de tus partidas en esta línea ({item['main_g']} de {item['n']}) son con {name(item['main'])}. "
            f"Un segundo campeón te cubre si te lo banean o te lo roban en la selección. Con buena tasa en el parche y que ya tienes:")
