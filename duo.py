"""Tu historial con quien vas en dúo (o en grupo): cuántas veces habéis ganado juntos, cómo te va sin esa persona y la pareja de campeones que mejor
os ha salido. Sale de tus partidas guardadas (archivo de partidas: compañeros «p» y sus campeones «a», en el mismo orden). Sin ventana ni red.
Muestras pequeñas: nada con menos de 3 partidas juntos, y las cifras van como «7 de 12», no solo en porcentaje."""
import analysis
import history

SR = analysis.SR_QUEUES
MIN_TOGETHER, MIN_COMBO, MIN_ALONE = 3, 3, 8   # una pareja con 2 partidas era azar (visto con datos reales)


LIST_MIN, LIST_MAX = 2, 4   # en las listas, campeones con al menos 2 partidas juntos; como mucho 4


def together(cache_dir, puuid):
    """(partidas de la Grieta juntos, las jugadas sin esa persona). Cada una: {w, mine, theirs, role}; `theirs` es 0 si no se sabe su campeón."""
    if not puuid:
        return [], []
    hist = {str(g.get("id")): g for g in history.load_all(history.hpath(cache_dir), history.gpath(cache_dir))}
    saved = history._read(history.gpath(cache_dir), {}) or {}
    both, alone = [], []
    for gid, e in saved.items():
        if not isinstance(e, dict) or e.get("q") not in SR or hist.get(str(gid), {}).get("rm"):
            continue
        mates = e.get("p") or []
        if not mates:   # no se sabe con quién jugaste: no cuenta ni «juntos» ni «sin»
            continue
        champs = e.get("a") or []
        known = puuid in mates and len(champs) == len(mates)   # si faltó algún identificador, las listas no casan: no se adivina su campeón
        row = {"w": bool(e.get("w")), "mine": e.get("c") or 0, "theirs": champs[mates.index(puuid)] if known else 0, "role": e.get("r") or ""}
        (both if puuid in mates else alone).append(row)
    return both, alone


def _count(rows, key):
    """{valor de `key`: [victorias, partidas]} sin los valores desconocidos."""
    out = {}
    for r in rows:
        k = key(r)
        if k:
            c = out.setdefault(k, [0, 0])
            c[0] += r["w"]
            c[1] += 1
    return out


def _top(counts, limit=LIST_MAX):
    """[(valor, victorias, partidas)] de los más jugados juntos (a igualdad, los que más ganan)."""
    rows = [(k, w, g) for k, (w, g) in counts.items() if g >= LIST_MIN]
    return sorted(rows, key=lambda x: (-x[2], -x[1], str(x[0])))[:limit]


def _pairs(rows, limit=3):
    """Parejas (tu campeón, el suyo) con al menos 3 partidas y más victorias que derrotas, de mejor a peor."""
    counts = _count(rows, lambda r: (r["mine"], r["theirs"]) if r["mine"] and r["theirs"] else None)
    good = [(w / g, g, k, w) for k, (w, g) in counts.items() if g >= MIN_COMBO and w * 2 > g]
    return [(k[0], k[1], w, g) for _r, g, k, w in sorted(good, reverse=True)[:limit]]


def stats(cache_dir, puuid):
    """{n, wins, alone: (victorias, partidas) | None, combo: (tu campeón, el suyo, victorias, partidas) | None}, o None si habéis jugado poco juntos."""
    both, alone = together(cache_dir, puuid)
    if len(both) < MIN_TOGETHER:
        return None
    pairs = _pairs(both, 1)
    return {"n": len(both), "wins": sum(r["w"] for r in both),
            "alone": (sum(r["w"] for r in alone), len(alone)) if len(alone) >= MIN_ALONE else None, "combo": pairs[0] if pairs else None}


def detail(cache_dir, puuid, role="", their_champ=0):
    """Lo que ayuda a elegir campeón jugando con esa persona, o None si habéis jugado poco juntos:
    theirs / mine: [(campeón, victorias, partidas)] juntos (los tuyos, de tu línea `role` si hay partidas suficientes en ella: `mine_role` lo dice);
    pairs: las mejores parejas; with_theirs: con el campeón que lleva ahora, [(tu campeón, victorias, partidas)], o None."""
    both, _alone = together(cache_dir, puuid)
    if len(both) < MIN_TOGETHER:
        return None
    in_role = [r for r in both if role and r["role"] == role]
    by_role = len(in_role) >= MIN_TOGETHER
    mine_rows = in_role if by_role else both
    now = None
    if their_champ:
        rows = [r for r in mine_rows if r["theirs"] == their_champ]
        if rows:
            counts = _count(rows, lambda r: r["mine"])
            now = {"n": len(rows), "wins": sum(r["w"] for r in rows),
                   "mine": sorted(((k, w, g) for k, (w, g) in counts.items()), key=lambda x: (-x[2], -x[1], x[0]))[:LIST_MAX]}
    return {"theirs": _top(_count(both, lambda r: r["theirs"])), "mine": _top(_count(mine_rows, lambda r: r["mine"])), "mine_role": by_role,
            "pairs": _pairs(mine_rows), "with_theirs": now}


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
