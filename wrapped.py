"""«Tu año en LoL»: un resumen sobrio de tu temporada con lo que LOL-E ha guardado en el historial, y la imagen para compartirlo.

`compute` y `lines` son solo cuentas (se pueden probar sin ventana); `render` dibuja la imagen con PIL. Cada entrada del historial trae `t` (inicio, ms),
`d` (duración, s), `c` (campeón), `w` (victoria), `rm` (remake) y, si se guardó con detalle, `k`/`de`/`a` (bajas, muertes y asistencias)."""
import datetime
import os
from collections import Counter

import sesion

MIN_GAMES = 10          # con menos partidas no hay resumen que valga
MIN_BEST = 5            # partidas mínimas con un campeón para que cuente como «el mejor»


def _start(now_ms, mode):
    if mode == "all":
        return 0
    return int(datetime.datetime(datetime.datetime.fromtimestamp(now_ms / 1000).year, 1, 1).timestamp() * 1000)


def _streaks(games):
    """(mejor racha de victorias, peor racha de derrotas) con la fecha en que acabaron."""
    best = (0, None)
    worst = (0, None)
    cw = cl = 0
    for e in sorted(games, key=lambda e: e["t"]):
        if e["w"]:
            cw, cl = cw + 1, 0
            if cw > best[0]:
                best = (cw, e["t"])
        else:
            cl, cw = cl + 1, 0
            if cl > worst[0]:
                worst = (cl, e["t"])
    return best, worst


def compute(games, now_ms, mode="year"):
    """Las cifras del resumen, o None si hay menos de MIN_GAMES partidas en el periodo («year» o «all»)."""
    g = [e for e in games or [] if not e.get("rm") and e.get("t", 0) >= _start(now_ms, mode)]
    if len(g) < MIN_GAMES:
        return None
    wins = sum(1 for e in g if e["w"])
    det = [e for e in g if e.get("k") is not None and e.get("de") is not None and e.get("a") is not None]
    kills, deaths, assists = (sum(e[k] for e in det) for k in ("k", "de", "a"))
    by = Counter(e["c"] for e in g if e.get("c"))
    won = Counter(e["c"] for e in g if e.get("c") and e["w"])
    top = [(c, n, won[c]) for c, n in by.most_common(3)]
    cand = [(won[c] / n, n, c) for c, n in by.items() if n >= MIN_BEST]
    best = max(cand) if cand else None
    day = Counter(datetime.datetime.fromtimestamp(e["t"] / 1000).date() for e in g)
    busiest = day.most_common(1)[0]
    dead = Counter()
    for e in det:
        if e.get("c"):
            dead[e["c"]] += e["de"]
    longest = max(g, key=lambda e: e.get("d") or 0)
    bw, wl = _streaks(g)
    return {
        "mode": mode, "year": datetime.datetime.fromtimestamp(now_ms / 1000).year, "n": len(g), "wins": wins, "losses": len(g) - wins,
        "wr": wins / len(g), "hours": sum(e.get("d") or 0 for e in g) / 3600,
        "kills": kills, "deaths": deaths, "assists": assists, "kda": (kills + assists) / max(1, deaths) if det else None, "kda_n": len(det),
        "top": top, "best": (best[2], best[1], best[0]) if best else None,
        "best_streak": bw, "worst_streak": wl,
        "busiest": (busiest[0], busiest[1]),
        "slot": sesion.best_slot(sesion.by_hour(g)),
        "most_deaths": dead.most_common(1)[0] if dead else None,
        "longest": (longest.get("d") or 0, longest.get("c"), bool(longest["w"])),
    }


def _date(ms_or_date):
    d = ms_or_date if isinstance(ms_or_date, datetime.date) else datetime.datetime.fromtimestamp(ms_or_date / 1000).date()
    return d.strftime("%d/%m/%Y")


def lines(s, name):
    """Los datos curiosos, como frases: [(titulo, texto)]. `name(cid)` da el nombre del campeón."""
    out = []
    bs, ws = s["best_streak"], s["worst_streak"]
    if bs[0] >= 3:
        out.append(("Mejor racha", f"{bs[0]} victorias seguidas (hasta el {_date(bs[1])})"))
    if ws[0] >= 3:
        out.append(("Peor racha", f"{ws[0]} derrotas seguidas (hasta el {_date(ws[1])})"))
    out.append(("Día más intenso", f"{_date(s['busiest'][0])}: {s['busiest'][1]} partidas"))
    if s.get("slot"):
        out.append(("Tu mejor franja", f"la {s['slot'][0]}, con un {round(s['slot'][1] * 100)} % de victorias"))
    if s.get("best"):
        out.append(("Tu mejor campeón", f"{name(s['best'][0])}: {round(s['best'][2] * 100)} % en {s['best'][1]} partidas"))
    if s.get("most_deaths"):
        out.append(("El que más te mata", f"{name(s['most_deaths'][0])}: {s['most_deaths'][1]} muertes"))
    d = s["longest"]
    if d[0]:
        out.append(("Partida más larga", f"{d[0] // 60} min con {name(d[1])} ({'victoria' if d[2] else 'derrota'})"))
    return out


def render(s, name, icon_path, path, theme=None):
    """Dibuja la imagen (1080×1350) y la guarda en `path`. `icon_path(cid)` da la ruta del icono del campeón o None."""
    from PIL import Image, ImageDraw
    from ui_kit import pil_font
    W, H = 1080, 1350
    bg, card, ink, dim, gold = (5, 10, 16), (17, 27, 40), (240, 232, 214), (150, 162, 178), (200, 169, 110)
    good, bad = (61, 220, 132), (255, 90, 99)
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.text((72, 60), "TU AÑO EN LOL" if s["mode"] == "year" else "TODAS TUS PARTIDAS EN LOL", font=pil_font("med", 28), fill=gold)
    d.text((72, 96), str(s["year"]) if s["mode"] == "year" else "Tu historial", font=pil_font("bold", 120), fill=ink)
    # tres cifras grandes
    cells = [(f"{s['n']}", "partidas"), (f"{round(s['wr'] * 100)} %", "de victorias"), (f"{s['hours']:.0f} h", "jugadas")]
    for i, (big, small) in enumerate(cells):
        x = 72 + i * 316
        d.rounded_rectangle((x, 262, x + 292, 402), radius=22, fill=card)
        d.text((x + 24, 278), big, font=pil_font("bold", 64), fill=good if (i == 1 and s["wr"] >= .5) else bad if i == 1 else ink)
        d.text((x + 24, 350), small, font=pil_font("med", 26), fill=dim)
    # campeones
    d.text((72, 432), "TUS CAMPEONES", font=pil_font("med", 24), fill=gold)
    for i, (cid, n, w) in enumerate(s["top"]):
        x = 72 + i * 316
        d.rounded_rectangle((x, 474, x + 292, 684), radius=22, fill=card)
        p = icon_path(cid)
        if p and os.path.exists(p):
            ic = Image.open(p).convert("RGB").resize((96, 96), Image.LANCZOS)
            im.paste(ic, (x + 24, 494))
        d.text((x + 24, 604), name(cid), font=pil_font("bold", 32), fill=ink)
        d.text((x + 24, 642), f"{n} partidas · {round(w / n * 100)} %", font=pil_font("med", 22), fill=dim)
    # datos curiosos
    y = 724
    for title, text in lines(s, name)[:6]:
        d.text((72, y), title.upper(), font=pil_font("med", 20), fill=gold)
        d.text((72, y + 26), text, font=pil_font("bold", 28), fill=ink)
        y += 78
    if s.get("kda") is not None:
        d.text((72, H - 120), f"KDA medio {s['kda']:.2f}".replace(".", ",") + f"  ·  {s['kills']} bajas · {s['deaths']} muertes · {s['assists']} asistencias", font=pil_font("med", 24), fill=dim)
    d.text((72, H - 70), "LOL-E", font=pil_font("bold", 30), fill=gold)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    im.save(path)
    return path
