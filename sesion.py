"""Tu sesión de juego: cuántas partidas llevas seguidas, cómo te va después de perder y a qué horas rindes más. Sin ventana ni red: solo cuentas
sobre el historial guardado (cada entrada: `t` inicio en ms, `d` duración en segundos, `w` victoria, `rm` remake), para poder probarlas.
Una «sesión» son las partidas separadas por menos de 2 horas entre el final de una y el inicio de la siguiente."""
import datetime

GAP = 2 * 3600 * 1000
MIN_N = 8                                   # por debajo de esto no se saca ninguna conclusión de una cifra
SLOTS = [("madrugada", 0, 6), ("mañana", 6, 12), ("tarde", 12, 20), ("noche", 20, 24)]


def _games(games):
    return sorted((e for e in games or [] if not e.get("rm") and e.get("t")), key=lambda e: e["t"])


def _end(e):
    return e["t"] + int(e.get("d") or 0) * 1000


def _same_session(a, b):
    return b["t"] - _end(a) <= GAP


def current(games, now_ms):
    """La sesión en curso (la última, si acabó hace menos de 2 horas): {n, w, l, loss_streak, win_streak}; None si no hay."""
    g = _games(games)
    if not g or now_ms - _end(g[-1]) > GAP:
        return None
    sess = [g[-1]]
    for e in reversed(g[:-1]):
        if not _same_session(e, sess[0]):
            break
        sess.insert(0, e)
    wins = sum(1 for e in sess if e["w"])
    ls = ws = 0
    for e in reversed(sess):
        if e["w"]:
            break
        ls += 1
    for e in reversed(sess):
        if not e["w"]:
            break
        ws += 1
    return {"n": len(sess), "w": wins, "l": len(sess) - wins, "loss_streak": ls, "win_streak": ws}


def after_losses(games):
    """Cómo te va según las derrotas seguidas que traías en la sesión: {0, 1, 2}: (partidas, victorias); el 2 es «2 o más»."""
    out = {0: [0, 0], 1: [0, 0], 2: [0, 0]}
    run, prev = 0, None
    for e in _games(games):
        if prev is None or not _same_session(prev, e):
            run = 0
        k = min(run, 2)
        out[k][0] += 1
        out[k][1] += 1 if e["w"] else 0
        run = 0 if e["w"] else run + 1
        prev = e
    return {k: tuple(v) for k, v in out.items()}


def by_hour(games):
    """Partidas y victorias por franja del día (hora local): {nombre: (partidas, victorias)}."""
    out = {n: [0, 0] for n, _a, _b in SLOTS}
    for e in _games(games):
        h = datetime.datetime.fromtimestamp(e["t"] / 1000).hour
        for n, a, b in SLOTS:
            if a <= h < b:
                out[n][0] += 1
                out[n][1] += 1 if e["w"] else 0
    return {k: tuple(v) for k, v in out.items()}


def wr(pair):
    return pair[1] / pair[0] if pair and pair[0] else None


def tilt_note(sess, after):
    """Frase para quien lleva 2 o más derrotas seguidas, con su propio dato si hay muestra suficiente; None si no hay nada que decir."""
    if not sess or sess["loss_streak"] < 2:
        return None
    txt = f"Llevas {sess['loss_streak']} derrotas seguidas en esta sesión."
    base, bad = after.get(0), after.get(2)
    if base and bad and base[0] >= MIN_N and bad[0] >= MIN_N and wr(base) - wr(bad) >= .08:
        txt += (f" Tras 2 o más seguidas ganas el {round(wr(bad) * 100)} % de tus partidas ({bad[0]}), frente al {round(wr(base) * 100)} % "
                f"cuando empiezas la sesión o vienes de ganar ({base[0]}): quizá toque parar un rato.")
    return txt


def best_slot(hours):
    """(franja, % de victorias, partidas) de la franja con mejor resultado y muestra suficiente, solo si se separa claramente del resto; None si no."""
    cand = [(wr(v), n, v[0]) for n, v in hours.items() if v[0] >= MIN_N]
    if len(cand) < 2:
        return None
    cand.sort(reverse=True)
    return (cand[0][1], cand[0][0], cand[0][2]) if cand[0][0] - cand[-1][0] >= .12 else None
