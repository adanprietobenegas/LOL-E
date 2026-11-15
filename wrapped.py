"""«Tu año en LoL»: un resumen de tu temporada con lo que LOL-E ha guardado en el historial, y la imagen para compartirlo.

Dos bloques separados: **lo útil** (cifras que sirven para mejorar: campeones y líneas que te funcionan o no, tendencia, horas, qué pasa tras perder) y **curiosidades**
(rachas, la partida más larga, tu estilo…). Cada dato dice sobre cuántas partidas se calcula y, si es una partida concreta, cuándo fue.

`compute`, `useful` y `curious` son solo cuentas (se pueden probar sin ventana); `render` y `render_game` dibujan las imágenes con PIL. Cada entrada del historial trae
`t` (inicio, ms), `d` (duración, s), `c` (campeón), `w` (victoria), `rm` (remake), `r` (línea) y, si se guardó con detalle, `k`/`de`/`a` (bajas, muertes y asistencias)."""
import datetime
import os
from collections import Counter

import sesion

MIN_GAMES = 10          # con menos partidas no hay resumen que valga
MIN_BEST = 5            # partidas mínimas con un campeón para hablar de él
MIN_ROLE = 8            # y con una línea
DAY = 86_400_000
ROLES = {"TOP": "Superior", "JUNGLE": "Jungla", "MIDDLE": "Central", "BOTTOM": "Tirador", "SUPPORT": "Apoyo"}


def _start(now_ms, mode):
    if mode == "all":
        return 0
    return int(datetime.datetime(datetime.datetime.fromtimestamp(now_ms / 1000).year, 1, 1).timestamp() * 1000)


def _streaks(games):
    """(mejor racha de victorias, peor racha de derrotas): cada una (longitud, inicio ms, fin ms)."""
    best = (0, None, None)
    worst = (0, None, None)
    cur = [0, None]       # [longitud, inicio] de la racha en curso
    last = None
    for e in sorted(games, key=lambda e: e["t"]):
        if last is None or e["w"] != last:
            cur = [0, e["t"]]
        cur[0] += 1
        last = e["w"]
        row = (cur[0], cur[1], e["t"])
        if e["w"] and row[0] > best[0]:
            best = row
        if not e["w"] and row[0] > worst[0]:
            worst = row
    return best, worst


def _wr(rows):
    return sum(1 for e in rows if e["w"]) / len(rows) if rows else None


def compute(games, now_ms, mode="year"):
    """Las cifras del resumen, o None si hay menos de MIN_GAMES partidas en el periodo («year» o «all»)."""
    g = sorted((e for e in games or [] if not e.get("rm") and e.get("t", 0) >= _start(now_ms, mode)), key=lambda e: e["t"])
    if len(g) < MIN_GAMES:
        return None
    wins = sum(1 for e in g if e["w"])
    det = [e for e in g if e.get("k") is not None and e.get("de") is not None and e.get("a") is not None]
    kills, deaths, assists = (sum(e[k] for e in det) for k in ("k", "de", "a"))
    mins_det = sum((e.get("d") or 0) for e in det) / 60
    by = Counter(e["c"] for e in g if e.get("c"))
    won = Counter(e["c"] for e in g if e.get("c") and e["w"])
    top = [(c, n, won[c]) for c, n in by.most_common(3)]
    cand = sorted(((won[c] / n, n, c) for c, n in by.items() if n >= MIN_BEST), reverse=True)
    best = (cand[0][2], cand[0][1], cand[0][0]) if cand else None
    worst = (cand[-1][2], cand[-1][1], cand[-1][0]) if len(cand) >= 2 and cand[-1][0] < 0.45 else None
    roles = {}
    for e in g:
        if ROLES.get(e.get("r")):
            roles.setdefault(e["r"], []).append(e)
    rc = sorted(((_wr(v), len(v), r) for r, v in roles.items() if len(v) >= MIN_ROLE), reverse=True)
    role_best = (rc[0][2], rc[0][1], rc[0][0]) if rc else None
    role_worst = (rc[-1][2], rc[-1][1], rc[-1][0]) if len(rc) >= 2 and rc[0][0] - rc[-1][0] >= 0.10 else None
    recent = [e for e in g if e["t"] >= now_ms - 30 * DAY]
    before = [e for e in g if e["t"] < now_ms - 30 * DAY]
    trend = (_wr(recent), len(recent), _wr(before), len(before)) if len(recent) >= 8 and len(before) >= 8 else None
    hours = sesion.by_hour(g)
    ok = sorted(((v[1] / v[0], v[0], n) for n, v in hours.items() if v[0] >= sesion.MIN_N), reverse=True)
    slot_best = (ok[0][2], ok[0][1], ok[0][0]) if ok else None
    slot_worst = (ok[-1][2], ok[-1][1], ok[-1][0]) if len(ok) >= 2 and ok[0][0] - ok[-1][0] >= 0.10 else None
    after = sesion.after_losses(g)
    dead = Counter()
    played = Counter()
    for e in det:
        if e.get("c"):
            dead[e["c"]] += e["de"]
            played[e["c"]] += 1
    mdc = max(((dead[c] / played[c], dead[c], played[c], c) for c in dead if played[c] >= 3), default=None)
    day = Counter(datetime.datetime.fromtimestamp(e["t"] / 1000).date() for e in g)
    bday, bn = day.most_common(1)[0]
    bw = sum(1 for e in g if e["w"] and datetime.datetime.fromtimestamp(e["t"] / 1000).date() == bday)
    longest = max(g, key=lambda e: e.get("d") or 0)
    topk = max(det, key=lambda e: e["k"], default=None)
    bs, ws = _streaks(g)
    return {
        "mode": mode, "year": datetime.datetime.fromtimestamp(now_ms / 1000).year, "first": g[0]["t"], "last": g[-1]["t"],
        "n": len(g), "wins": wins, "losses": len(g) - wins, "wr": wins / len(g), "hours": sum(e.get("d") or 0 for e in g) / 3600,
        "kills": kills, "deaths": deaths, "assists": assists, "kda": (kills + assists) / max(1, deaths) if det else None, "kda_n": len(det),
        "dpm": deaths / mins_det if det and mins_det else None,
        "top": top, "best": best, "worst": worst, "role_best": role_best, "role_worst": role_worst, "trend": trend,
        "slot_best": slot_best, "slot_worst": slot_worst, "after": after,
        "best_streak": bs, "worst_streak": ws, "busiest": (bday, bn, bw),
        "most_deaths": mdc, "longest": (longest.get("d") or 0, longest.get("c"), bool(longest["w"]), longest["t"]),
        "top_kills": (topk["k"], topk.get("c"), bool(topk["w"]), topk["t"]) if topk and topk["k"] >= 8 else None,
        "style": style(g),
    }


def style(games):
    """Tu estilo de juego, con un nombre simpático y el dato que lo justifica: (nombre, frase) o None si no hay datos de detalle suficientes.
    Es un guiño, no un diagnóstico: usa cifras tuyas (por minuto) y umbrales aproximados, y el primero que se cumple gana."""
    det = [e for e in games if e.get("k") is not None and e.get("de") is not None and e.get("a") is not None and e.get("d")]
    if len(det) < MIN_GAMES:
        return None
    mins = sum(e["d"] for e in det) / 60
    dpm = sum(e["de"] for e in det) / mins
    kills, assists = sum(e["k"] for e in det), sum(e["a"] for e in det)
    cs = [e for e in det if e.get("cs") is not None and e.get("r") not in ("SUPPORT", "", None) and e.get("gm") != "ARAM"]
    cspm = sum(e["cs"] for e in cs) / (sum(e["d"] for e in cs) / 60) if len(cs) >= MIN_GAMES else None
    vis = [e for e in det if e.get("v") is not None and e.get("gm") != "ARAM"]
    vpm = sum(e["v"] for e in vis) / (sum(e["d"] for e in vis) / 60) if len(vis) >= MIN_GAMES else None
    f = lambda x, d=1: f"{x:.{d}f}".replace(".", ",")
    if dpm >= 0.42:
        return ("El kamikaze", f"mueres {f(dpm, 2)} veces por minuto: vives al límite")
    if dpm <= 0.22:
        return ("El superviviente", f"solo {f(dpm, 2)} muertes por minuto: casi nunca regalas nada")
    if cspm and cspm >= 7:
        return ("El granjero", f"{f(cspm)} súbditos por minuto en tus líneas")
    if vpm and vpm >= 1.5:
        return ("El vigía", f"{f(vpm)} de visión por minuto: tu equipo ve por ti")
    if kills and assists / kills >= 2.4:
        return ("El asistente", f"{f(assists / kills)} asistencias por cada baja: juegas para el equipo")
    return ("El todoterreno", f"{f(dpm, 2)} muertes por minuto y un juego equilibrado")


def _date(ms_or_date):
    d = ms_or_date if isinstance(ms_or_date, datetime.date) else datetime.datetime.fromtimestamp(ms_or_date / 1000).date()
    return d.strftime("%d/%m/%Y")


def _pct(x):
    return f"{round(x * 100)} %"


def _f1(x):
    return f"{x:.1f}".replace(".", ",")


def period(s):
    """«del 01/01/2026 al 15/11/2026 · 240 partidas»."""
    return f"del {_date(s['first'])} al {_date(s['last'])} · {s['n']} partidas"


def useful(s, name):
    """Lo que sirve para mejorar, con la muestra de cada dato: [{title, value, detail, tone}] (tone: good, bad o dim)."""
    out = []
    add = lambda title, value, detail, tone="dim": out.append({"title": title, "value": value, "detail": detail, "tone": tone})
    add("Victorias", _pct(s["wr"]), f"{s['wins']} V · {s['losses']} D · {period(s)}", "good" if s["wr"] >= .5 else "bad")
    t = s.get("trend")
    if t:
        diff = t[0] - t[2]
        add("Último mes", _pct(t[0]), f"{t[1]} partidas, frente al {_pct(t[2])} de las {t[3]} anteriores", "good" if diff >= .05 else "bad" if diff <= -.05 else "dim")
    if s.get("best"):
        b = s["best"]
        add("Tu mejor campeón", name(b[0]), f"{_pct(b[2])} de victorias en {b[1]} partidas", "good" if b[2] >= .5 else "dim")
    if s.get("worst"):
        w = s["worst"]
        add("Campeón a revisar", name(w[0]), f"{_pct(w[2])} de victorias en {w[1]} partidas", "bad")
    if s.get("role_best"):
        r = s["role_best"]
        add("Tu mejor línea", ROLES[r[0]], f"{_pct(r[2])} en {r[1]} partidas" + (f" · la peor: {ROLES[s['role_worst'][0]]} ({_pct(s['role_worst'][2])}, {s['role_worst'][1]})" if s.get("role_worst") else ""),
            "good" if r[2] >= .5 else "dim")
    if s.get("slot_best"):
        b = s["slot_best"]
        w = s.get("slot_worst")
        add("Tu mejor franja", b[0].capitalize(), f"{_pct(b[2])} en {b[1]} partidas" + (f" · la peor: {w[0]} ({_pct(w[2])}, {w[1]})" if w else ""), "dim")
    a = s.get("after") or {}
    base, bad = a.get(0), a.get(2)
    if base and bad and base[0] >= sesion.MIN_N and bad[0] >= sesion.MIN_N:
        add("Tras perder 2 seguidas", _pct(bad[1] / bad[0]), f"de victorias en {bad[0]} partidas, frente al {_pct(base[1] / base[0])} cuando empiezas o vienes de ganar ({base[0]})",
            "bad" if bad[1] / bad[0] < base[1] / base[0] - .05 else "dim")
    if s.get("kda") is not None:
        extra = f" · {s['dpm']:.2f} muertes por minuto".replace(".", ",") if s.get("dpm") else ""
        add("KDA", _f1(s["kda"]), f"{s['kills']} bajas · {s['deaths']} muertes · {s['assists']} asistencias en {s['kda_n']} partidas con detalle{extra}", "dim")
    return out


def curious(s, name):
    """Lo anecdótico, también con muestra y fecha: [{title, value, detail, tone}]."""
    out = []
    add = lambda title, value, detail, tone="dim": out.append({"title": title, "value": value, "detail": detail, "tone": tone})
    if s.get("style"):
        add("Tu estilo", s["style"][0], s["style"][1])
    bs, ws = s["best_streak"], s["worst_streak"]
    if bs[0] >= 3:
        add("Mejor racha", f"{bs[0]} victorias seguidas", f"del {_date(bs[1])} al {_date(bs[2])}", "good")
    if ws[0] >= 3:
        add("Peor racha", f"{ws[0]} derrotas seguidas", f"del {_date(ws[1])} al {_date(ws[2])}", "bad")
    d, n, w = s["busiest"]
    add("Día más intenso", f"{n} partidas", f"{_date(d)} · {w} V · {n - w} D")
    ln = s["longest"]
    if ln[0]:
        add("Partida más larga", f"{ln[0] // 60} min", f"{name(ln[1])} · {'victoria' if ln[2] else 'derrota'} · {_date(ln[3])}")
    if s.get("top_kills"):
        k = s["top_kills"]
        add("Más bajas en una partida", f"{k[0]} bajas", f"{name(k[1])} · {'victoria' if k[2] else 'derrota'} · {_date(k[3])}", "good")
    md = s.get("most_deaths")
    if md:
        add("Con el que más mueres", name(md[3]), f"{_f1(md[0])} muertes por partida ({md[1]} en {md[2]} partidas)")
    add("Horas jugadas", f"{s['hours']:.0f} h", f"{s['hours'] / 24:.1f} días seguidos de partida".replace(".", ","))
    return out


def lines(s, name):
    """Todo como frases sueltas: [(título, texto)]. Lo usa quien no dibuja fichas."""
    return [(x["title"], f"{x['value']} · {x['detail']}") for x in useful(s, name) + curious(s, name)]


def render_game(e, name, icon_path, path, lp=None, extra=()):
    """La tarjeta de UNA partida (1080×1080, sobria) para compartirla. `e`: registro del historial; `lp`: {d, now, tier} de analysis.lp_for o None;
    `extra`: hasta 3 frases cortas (p. ej. tu partida frente a tu media)."""
    from PIL import Image, ImageDraw
    from ui_kit import pil_font
    W, H = 1080, 1080
    bg, card, ink, dim, gold = (5, 10, 16), (17, 27, 40), (240, 232, 214), (150, 162, 178), (200, 169, 110)
    good, bad = (61, 220, 132), (255, 90, 99)
    col = dim if e.get("rm") else good if e["w"] else bad
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 18, H), fill=col)
    d.text((72, 64), "MI PARTIDA", font=pil_font("med", 28), fill=gold)
    p = icon_path(e.get("c"))
    if p and os.path.exists(p):
        im.paste(Image.open(p).convert("RGB").resize((200, 200), Image.LANCZOS), (72, 120))
        d.rectangle((72, 120, 272, 320), outline=col, width=5)
    d.text((310, 124), name(e.get("c")), font=pil_font("bold", 76), fill=ink)
    res = "Remake" if e.get("rm") else "Victoria" if e["w"] else "Derrota"
    d.text((310, 218), res, font=pil_font("bold", 64), fill=col)
    if lp and lp.get("d"):
        d.text((310, 292), f"{lp['d']:+d} PL".replace("-", "−") + f" · {lp.get('tier', '')} {lp.get('now', '')} PL", font=pil_font("med", 28), fill=dim)
    cells = []
    if e.get("k") is not None:
        cells.append((f"{e['k']} / {e['de']} / {e['a']}", "bajas / muertes / asistencias"))
    if e.get("cs") is not None and e.get("d"):
        cells.append((f"{e['cs']}", f"súbditos ({e['cs'] / (e['d'] / 60):.1f} por min)".replace(".", ",")))
    if e.get("dm"):
        cells.append((f"{e['dm'] / 1000:.1f}k".replace(".", ","), "de daño a campeones"))
    if e.get("d"):
        cells.append((f"{e['d'] // 60}:{e['d'] % 60:02d}", "de duración"))
    for i, (big, small) in enumerate(cells[:4]):
        x, y = 72 + (i % 2) * 490, 380 + (i // 2) * 190
        d.rounded_rectangle((x, y, x + 466, y + 166), radius=22, fill=card)
        d.text((x + 28, y + 24), big, font=pil_font("bold", 64), fill=ink)
        d.text((x + 28, y + 108), small, font=pil_font("med", 26), fill=dim)
    y = 780
    for t in list(extra)[:3]:
        d.text((72, y), t if len(t) < 70 else t[:67] + "…", font=pil_font("bold", 28), fill=ink)
        y += 52
    d.text((72, H - 90), "LOL-E", font=pil_font("bold", 30), fill=gold)
    d.text((W - 72, H - 84), datetime.datetime.fromtimestamp(e["t"] / 1000).strftime("%d/%m/%Y"), font=pil_font("med", 24), fill=dim, anchor="ra")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    im.save(path)
    return path


def render(s, name, icon_path, path, theme=None):
    """Dibuja la imagen (1080×1350) y la guarda en `path`. `icon_path(cid)` da la ruta del icono del campeón o None."""
    from PIL import Image, ImageDraw
    from ui_kit import pil_font
    W, H = 1080, 1350
    bg, card, ink, dim, gold = (5, 10, 16), (17, 27, 40), (240, 232, 214), (150, 162, 178), (200, 169, 110)
    good, bad = (61, 220, 132), (255, 90, 99)
    tone = {"good": good, "bad": bad, "dim": ink}
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.text((72, 56), "TU AÑO EN LOL" if s["mode"] == "year" else "TODAS TUS PARTIDAS EN LOL", font=pil_font("med", 28), fill=gold)
    d.text((72, 92), str(s["year"]) if s["mode"] == "year" else "Tu historial", font=pil_font("bold", 110), fill=ink)
    d.text((72, 212), period(s), font=pil_font("med", 24), fill=dim)
    cells = [(f"{s['n']}", "partidas"), (f"{round(s['wr'] * 100)} %", "de victorias"), (f"{s['hours']:.0f} h", "jugadas")]
    for i, (big, small) in enumerate(cells):
        x = 72 + i * 316
        d.rounded_rectangle((x, 262, x + 292, 402), radius=22, fill=card)
        d.text((x + 24, 278), big, font=pil_font("bold", 64), fill=good if (i == 1 and s["wr"] >= .5) else bad if i == 1 else ink)
        d.text((x + 24, 350), small, font=pil_font("med", 26), fill=dim)
    d.text((72, 430), "TUS CAMPEONES", font=pil_font("med", 22), fill=gold)
    for i, (cid, n, w) in enumerate(s["top"]):
        x = 72 + i * 316
        d.rounded_rectangle((x, 466, x + 292, 646), radius=22, fill=card)
        p = icon_path(cid)
        if p and os.path.exists(p):
            im.paste(Image.open(p).convert("RGB").resize((84, 84), Image.LANCZOS), (x + 24, 482))
        d.text((x + 24, 574), name(cid), font=pil_font("bold", 30), fill=ink)
        d.text((x + 24, 608), f"{n} partidas · {round(w / n * 100)} %", font=pil_font("med", 21), fill=dim)

    import textwrap

    def block(title, rows, x, y):
        """Una columna de 4 datos: título pequeño, valor grande y el detalle (muestra y fechas) en una o dos líneas."""
        d.text((x, y), title, font=pil_font("med", 22), fill=gold)
        y += 40
        for r in rows[:4]:
            d.text((x, y), r["title"].upper(), font=pil_font("med", 17), fill=dim)
            d.text((x, y + 22), r["value"], font=pil_font("bold", 28), fill=tone.get(r["tone"], ink))
            for k, ln in enumerate(textwrap.wrap(r["detail"], 40)[:2]):
                d.text((x, y + 60 + k * 24), ln if k == 0 or len(ln) <= 40 else ln[:37] + "…", font=pil_font("med", 19), fill=dim)
            y += 132

    block("LO ÚTIL", useful(s, name)[1:], 72, 676)
    block("CURIOSIDADES", curious(s, name), 568, 676)
    d.text((72, H - 64), "LOL-E", font=pil_font("bold", 30), fill=gold)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    im.save(path)
    return path
