"""Tu historial contra el rival de línea: lo que ninguna web sabe. Sale de tus partidas guardadas (resultado) y de las ya analizadas (cómo ibas en
el minuto 10). Sin ventana ni red. Solo dice lo que hay: sin partidas contra ese rival en esa línea no dice nada."""
import analysis
import history
import patrones

SR = analysis.SR_QUEUES


def _n(x):
    return ("+" if x > 0 else "−" if x < 0 else "±") + f"{abs(int(round(x))):,}".replace(",", ".")


def _veces(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def record(games, opp, role, cid=0):
    """Frase con tus partidas de la Grieta contra `opp` en la línea `role` (y, de ellas, las jugadas con `cid`), o None si no hay ninguna."""
    rows = matching(games, opp, role)
    if not rows:
        return None
    wins = sum(1 for g in rows if g.get("w"))
    text = f"{_veces(len(rows), 'partida', 'partidas')}, {_veces(wins, 'victoria', 'victorias')}"
    mine = [g for g in rows if cid and g.get("c") == cid]
    if mine and len(mine) < len(rows):
        text += f" (con este campeón: {sum(1 for g in mine if g.get('w'))} de {len(mine)})"
    elif mine:
        text += ", todas con este campeón" if len(rows) > 1 else ", con este campeón"
    return text


def saved_games(cache_dir):
    """Tus partidas con rival de línea. El rival («o») y la línea recalculada están en el archivo de partidas (games), no en el historial: se juntan
    ambos por id (el historial aporta el remake)."""
    hist = {str(g.get("id")): g for g in history.load_all(history.hpath(cache_dir), history.gpath(cache_dir))}
    extra = history._read(history.gpath(cache_dir), {}) or {}
    return [{**hist.get(str(gid), {}), **e, "id": str(gid)} for gid, e in extra.items() if isinstance(e, dict)]


def matching(games, opp, role):
    """Las partidas de la Grieta, sin remake, contra `opp` en la línea `role`."""
    return [g for g in games if g.get("o") == opp and g.get("r") == role and not g.get("rm") and g.get("q") in SR | {0}]


def minute10(analyses, opp, role):
    """(partidas, diferencia media de oro, de súbditos) en el minuto 10 contra `opp` en la línea `role`, o None."""
    diffs = []
    for a in analyses:
        try:
            if a.get("queue") not in SR or analysis.me(a)["role"] != role:
                continue
            pid = analysis.default_opp(a)
            if pid is None or analysis.player(a, pid)["champ"] != opp:
                continue
            row = analysis.checkpoints(a, pid).get(10) or {}
            if "gold" in row and "cs" in row:
                diffs.append((row["gold"][0] - row["gold"][1], row["cs"][0] - row["cs"][1]))
        except Exception:
            continue
    if not diffs:
        return None
    return len(diffs), sum(d[0] for d in diffs) / len(diffs), sum(d[1] for d in diffs) / len(diffs)


def lines(cache_dir, opp, role, cid=0, name="este rival"):
    """Las frases para la pantalla ([] si nunca has jugado contra él en esa línea)."""
    if not opp or not role:
        return []
    games = saved_games(cache_dir)
    head = record(games, opp, role, cid)
    if not head:
        return []
    out = [f"Tu historial contra {name} en esta línea: {head}."]
    ids = {str(g.get("id")) for g in matching(games, opp, role)}
    m = minute10([a for a in patrones.load(cache_dir) if str(a.get("gid")) in ids], opp, role)
    if m:
        n, gold, cs = m
        out.append(f"En el minuto 10 ({_veces(n, 'partida analizada', 'partidas analizadas')}): {_n(gold)} de oro y {_n(cs)} súbditos"
                   + (" de media frente a él." if n > 1 else " frente a él."))
    return out
