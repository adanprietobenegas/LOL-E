"""Tu historial con quien vas en dúo (o en grupo): cuántas veces habéis ganado juntos, cómo te va sin esa persona y la pareja de campeones que mejor
os ha salido. Sale de tus partidas guardadas (archivo de partidas: compañeros «p» y sus campeones «a», en el mismo orden). Sin ventana ni red.
Muestras pequeñas: nada con menos de 3 partidas juntos, y las cifras van como «7 de 12», no solo en porcentaje."""
import analysis
import history

SR = analysis.SR_QUEUES
MIN_TOGETHER, MIN_COMBO, MIN_ALONE = 3, 3, 8   # una pareja con 2 partidas era azar (visto con datos reales)


def stats(cache_dir, puuid):
    """{n, wins, alone: (victorias, partidas) | None, combo: (tu campeón, el suyo, victorias, partidas) | None}, o None si habéis jugado poco juntos."""
    if not puuid:
        return None
    hist = {str(g.get("id")): g for g in history.load_all(history.hpath(cache_dir), history.gpath(cache_dir))}
    saved = history._read(history.gpath(cache_dir), {}) or {}
    n = wins = alone_n = alone_w = 0
    combos = {}
    for gid, e in saved.items():
        if not isinstance(e, dict) or e.get("q") not in SR or hist.get(str(gid), {}).get("rm"):
            continue
        mates = e.get("p") or []
        if not mates:   # no se sabe con quién jugaste: no cuenta ni «juntos» ni «sin»
            continue
        if puuid not in mates:
            alone_n += 1
            alone_w += bool(e.get("w"))
            continue
        n += 1
        wins += bool(e.get("w"))
        champs = e.get("a") or []
        if len(champs) == len(mates) and e.get("c"):   # si faltó algún identificador, las listas no casan: no se adivina su campeón
            c = combos.setdefault((e["c"], champs[mates.index(puuid)]), [0, 0])
            c[0] += bool(e.get("w"))
            c[1] += 1
    if n < MIN_TOGETHER:
        return None
    good = [(w / g, g, mine, theirs, w) for (mine, theirs), (w, g) in combos.items() if g >= MIN_COMBO and w * 2 > g]
    best = max(good, default=None)
    return {"n": n, "wins": wins, "alone": (alone_w, alone_n) if alone_n >= MIN_ALONE else None,
            "combo": (best[2], best[3], best[4], best[1]) if best else None}


def lines(cache_dir, puuid, who, champ_name):
    """Frases para la pantalla ([] si no hay bastante historial juntos). `who`: su nombre; `champ_name(id)`: nombre de un campeón."""
    s = stats(cache_dir, puuid)
    if not s:
        return []
    head = f"Con {who}: {s['wins']} {'victoria' if s['wins'] == 1 else 'victorias'} de {s['n']} partidas juntos ({round(100 * s['wins'] / s['n'])} %)"
    if s["alone"]:
        w, g = s["alone"]
        head += f". Sin {who}: {w} de {g} ({round(100 * w / g)} %)"
    out = [head + "."]
    if s["combo"]:
        mine, theirs, w, g = s["combo"]
        out.append(f"Lo que mejor os ha salido: tú con {champ_name(mine)} y {who} con {champ_name(theirs)} ({w} de {g}).")
    return out
