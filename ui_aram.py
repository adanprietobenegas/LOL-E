"""Análisis de una partida de ARAM / ARAM: Mayhem: sin rival de línea. Tu campeón en grande, premios de la partida, clasificación de los 10 jugadores con filtros
(daño, KDA, daño recibido, curación, control...) y los momentos clave. Se dibuja dentro de AnalysisView (ui_analysis.py)."""
import customtkinter as ctk

import analysis
from ui_kit import PAL

# métrica -> (clave o función, etiqueta de valor, formato)
def _kda(p):
    return (p["k"] + p["a"]) / max(1, p["d"])


def _mmss(s):
    return f"{int(s) // 60}:{int(s) % 60:02d}"


METRICS = {
    "Daño": (lambda p: p["dmg"], lambda v: f"{int(v):,}".replace(",", ".")),
    "KDA": (_kda, lambda v: f"{v:.2f}".replace(".", ",")),
    "Asesinatos": (lambda p: p["k"], lambda v: str(int(v))),
    "Muertes": (lambda p: p["d"], lambda v: str(int(v))),
    "Asistencias": (lambda p: p["a"], lambda v: str(int(v))),
    "Daño recibido": (lambda p: p["taken"], lambda v: f"{int(v):,}".replace(",", ".")),
    "Daño mitigado": (lambda p: p["mit"], lambda v: f"{int(v):,}".replace(",", ".")),
    "Curación": (lambda p: p["heal"], lambda v: f"{int(v):,}".replace(",", ".")),
    "Control de masas": (lambda p: p["cc"], _mmss),
    "Oro": (lambda p: p["gold"], lambda v: f"{int(v):,}".replace(",", ".")),
}
AWARDS = [("Más daño", "Daño"), ("Más aguante", "Daño recibido"), ("Mejor KDA", "KDA"), ("Más curación", "Curación"),
          ("Más control", "Control de masas"), ("Más asesinatos", "Asesinatos")]
TEAMS = ["Los 10", "Mi equipo", "Rival"]


def body(an, host, a):
    """Cuerpo completo de la pestaña Análisis para ARAM."""
    ui, gv = an.ui, an.gv
    an.nosec = True
    an.hosts, an.folds, an.cur = {}, {}, (a, None)
    ev = an.events(a)
    an.cur = (a, None, ev)
    header(an, host, a)
    adv = analysis.advice(a, None, ui.champs)
    an.headline(host, a, adv)
    an.media(host, a)
    awards(an, host, a)
    an.kpis(host, a, None)
    ui.fold(host, "Lo más interesante de la partida", lambda p: an.advice(p, a, None, adv), f"{len(adv)} datos", "an_advice", True)
    an.aram_sort = getattr(an, "aram_sort", "Daño")
    an.aram_team = getattr(an, "aram_team", "Los 10")
    an.folds["aram"] = ui.fold(host, "Clasificación de los 10 jugadores", lambda p: ranking(an, p, a), f"por {an.aram_sort.lower()}", "an_aram", True)
    if a.get("queue") in (2400,) and any(p.get("aug") for p in a["players"].values()):
        import ui_mayhem
        ui.fold(host, "Mejoras elegidas", lambda p: ui_mayhem.analysis_block(ui, p, a, gv.width), "las de los 10 jugadores", "an_aug", True)
    mine = sum(1 for e in ev if e["cat"] == "kd")
    an.folds["moments"] = ui.fold(host, "Momentos clave", lambda p: an.mount("moments", p, a, None, ev), f"{len(ev)} eventos · {mine} tuyos", "an_moments", False)
    gv.chart = "Oro del equipo"
    an.folds["charts"] = ui.fold(host, "Evolución de la partida", lambda p: an.mount("charts", p, a, None, ev), gv.chart, "an_charts", False)


def header(an, host, a):
    ui = an.ui
    m = analysis.me(a)
    card = ctk.CTkFrame(host, fg_color=PAL["card2"], corner_radius=14)
    card.pack(fill="x", pady=(0, 8))
    row = ui.frame(card)
    row.pack(fill="x", padx=16, pady=16)
    ui.champ(row, m["champ"], 84, False, an.hx(ui.acc)).pack(side="left", padx=(0, 16))
    t = ui.frame(row)
    t.pack(side="left")
    ui.lbl(t, "TÚ  ·  " + ("ARAM: MAYHEM" if a.get("queue") == 2400 else "ARAM"), 9, "dim", True).pack(anchor="w")
    ui.lbl(t, an.cname(m["champ"]), 24, "fg", True, True).pack(anchor="w")
    ui.lbl(t, f"Nivel {m['lvl']}  ·  {m['k']} / {m['d']} / {m['a']}", 11, "dim").pack(anchor="w")
    right = ui.frame(row)
    right.pack(side="right")
    ui.lbl(right, "Victoria" if a["win"] else "Derrota", 22, "good" if a["win"] else "bad", True, True, anchor="e").pack(anchor="e")
    ui.lbl(right, f"{a['dur'] // 60}:{a['dur'] % 60:02d}", 11, "dim", anchor="e").pack(anchor="e")


def awards(an, host, a):
    """Los premios de la partida: quién fue el mejor de los 10 en cada cosa."""
    ui = an.ui
    players = list(a["players"].values())
    ui.lbl(host, "PREMIOS DE LA PARTIDA", 9, "dim", True, anchor="w").pack(anchor="w", pady=(4, 4))
    grid = ui.frame(host)
    grid.pack(fill="x", pady=(0, 8))
    for i in range(3):
        grid.columnconfigure(i, weight=1, uniform="aw")
    for i, (title, metric) in enumerate(AWARDS):
        fn, fmt = METRICS[metric]
        best = max(players, key=fn)
        card = ctk.CTkFrame(grid, fg_color=PAL["card2"], corner_radius=12)
        card.grid(row=i // 3, column=i % 3, sticky="nsew", padx=4, pady=4)
        inner = ui.frame(card)
        inner.pack(fill="x", padx=12, pady=8)
        mine_team = best["team"] == a["team"]
        ui.lbl(inner, title.upper(), 8, "dim", True, anchor="w").pack(anchor="w")
        line = ui.frame(inner)
        line.pack(anchor="w", pady=(4, 0))
        ui.champ(line, best["champ"], 34, False, "#3ddc84" if mine_team else "#ff5a5f").pack(side="left")
        txt = ui.frame(line)
        txt.pack(side="left", padx=8)
        ui.lbl(txt, an.cname(best["champ"]) + (" (tú)" if best["pid"] == a["me"] else ""), 10, "fg", True, anchor="w").pack(anchor="w")
        ui.lbl(txt, fmt(fn(best)), 11, "warn" if best["pid"] == a["me"] else "dim", True, anchor="w").pack(anchor="w")


def ranking(an, host, a):
    """Los 10 jugadores ordenados por la cifra elegida; tu fila, más grande."""
    ui = an.ui
    bar = ui.frame(host)
    bar.pack(fill="x", pady=(0, 8))
    ui.lbl(bar, "Ordenar por", 10, "dim").pack(side="left", padx=(0, 8))
    ui.menu(bar, list(METRICS), an.aram_sort, lambda v: set_sort(an, host, a, v), 160).pack(side="left")
    ui.seg(bar, TEAMS, an.aram_team, lambda v: set_team(an, host, a, v), height=28, width=250).pack(side="right")
    body = ui.frame(host)
    body.pack(fill="x")
    an.aram_body = body
    rows(an, body, a)


def set_sort(an, host, a, v):
    an.aram_sort = v
    refresh(an, a)


def set_team(an, host, a, v):
    an.aram_team = v
    refresh(an, a)


def refresh(an, a):
    """Repinta solo la lista (y el resumen del pliegue)."""
    body = getattr(an, "aram_body", None)
    if body is None or not body.winfo_exists():
        return
    an.ui.clear(body)
    rows(an, body, a)
    f = an.folds.get("aram")
    if f is not None:
        f.set_summary(f"por {an.aram_sort.lower()}")


def rows(an, host, a):
    ui = an.ui
    fn, fmt = METRICS[an.aram_sort]
    pool = [p for p in a["players"].values()
            if an.aram_team == "Los 10" or (an.aram_team == "Mi equipo") == (p["team"] == a["team"])]
    pool.sort(key=lambda p: -fn(p))
    top = max((fn(p) for p in pool), default=0) or 1
    for i, p in enumerate(pool, 1):
        me = p["pid"] == a["me"]
        mine_team = p["team"] == a["team"]
        row = ctk.CTkFrame(host, fg_color=PAL["card2"] if me else "transparent", corner_radius=10,
                           border_width=1 if me else 0, border_color=an.hx(an.ui.acc) if me else PAL["card2"])
        row.pack(fill="x", pady=2)
        inner = ui.frame(row)
        inner.pack(fill="x", padx=8, pady=8 if me else 3)
        ui.lbl(inner, f"{i}", 12 if me else 10, "warn" if i == 1 else "dim", True, width=24, anchor="w").pack(side="left")
        ui.champ(inner, p["champ"], 44 if me else 30, False, "#3ddc84" if mine_team else "#ff5a5f").pack(side="left", padx=(0, 8))
        mid = ui.frame(inner)
        mid.pack(side="left", fill="x", expand=True)
        head = ui.frame(mid)
        head.pack(fill="x")
        ui.lbl(head, an.cname(p["champ"]) + (" (tú)" if me else ""), 13 if me else 11, "fg", True, anchor="w").pack(side="left")
        ui.lbl(head, f"{p['k']} / {p['d']} / {p['a']}", 10, "dim", anchor="e").pack(side="right")
        ui.bar(mid, [(max(0.02, fn(p) / top), "good" if mine_team else "bad")], 6 if me else 5).pack(fill="x", pady=(4, 0))
        ui.lbl(inner, fmt(fn(p)), 13 if me else 11, "warn" if me else "fg", True, width=80, anchor="e").pack(side="right", padx=(8, 0))
