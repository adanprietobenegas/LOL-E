"""Pestaña «Partida → Análisis»: cabecera con tu rival directo, cifras clave, gráficos minuto a minuto, comparación en cada fase,
marcador de los dos equipos, consejos con su dato y momentos clave. Los datos salen de analysis.py (línea de tiempo del cliente)."""
import math
import tkinter as tk

import customtkinter as ctk

import analysis
import lol_advisor as core
from ui_history import fecha
from ui_kit import PAL

CHARTS = ["Oro del equipo", "Oro vs rival", "Experiencia", "Súbditos", "Ruta en el mapa"]
ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT"]
ROLE_ES = analysis.ROLE_ES


def nice(v):
    """Redondea hacia arriba a 1, 2, 2,5, 5 o 10 por una potencia de diez: las escalas quedan con números redondos."""
    p = 10 ** math.floor(math.log10(max(v, 1)))
    for k in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= k * p:
            return k * p
    return 10 * p


def n(x):
    return f"{int(round(x)):,}".replace(",", ".")


def sg(x):
    return ("+" if x >= 0 else "−") + n(abs(x))


def mix(c1, c2, t):
    """Mezcla dos colores «#rrggbb»: t=0 es c1 y t=1 es c2 (los lienzos de Tk no tienen transparencia)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(x + (y - x) * t):02x}" for x, y in zip(a, b))


SORTS = ["Línea", "KDA", "Daño", "Oro", "Súbditos", "Visión"]


class AnalysisView:
    def __init__(self, ui, gui, gv):
        self.ui, self.gui, self.gv = ui, gui, gv
        self.hover = None
        self.sort = "Línea"   # orden del marcador de equipos
        self.together = False  # marcador: por equipos o los 10 juntos
        self.mfilter = "Todo"  # filtro de los momentos clave
        self.nosec = False
        self.hosts, self.folds, self.cur = {}, {}, None   # cuerpo y cabecera de cada sección plegable, y los datos con que se pintó

    # ------------------------------------------------------------ utilidades
    def rl(self, a, role):
        """Texto de la línea de un jugador; en ARAM no hay líneas."""
        return "" if a.get("queue") in analysis.ARAM_QUEUES else ROLE_ES.get(role, "?")

    def avail(self):
        """Ancho útil para lienzos, en unidades lógicas: el ancho de la ventana está en píxeles reales y los lienzos se escalan después."""
        return max(300, min(self.gv.width - 90, 1100))

    def hx(self, c):
        return self.ui.hexm(PAL[c]) if isinstance(c, str) and c in PAL else self.ui.hexm(c)

    def cname(self, cid):
        return self.ui.champs.get(cid, {}).get("name", "?")

    # ------------------------------------------------------------ entrada
    def render(self, host, ctx):
        ui, gv = self.ui, self.gv
        gv.load_games()
        if not gv.games:
            ui.lbl(host, "Todavía no hay partidas guardadas. Juega una con LoL abierto y aparecerá aquí.", 11, "dim").pack(anchor="w")
            return
        ids = [g["id"] for g in gv.games]
        if gv.gid not in ids:
            gv.gid = ids[0]
        labels = {f"{fecha(g['t'])} · {ui.champs.get(g['c'], {}).get('name', g['c'])} · {'Victoria' if g['w'] else 'Derrota'}": g["id"] for g in gv.games[:15]}
        cur = next((k for k, v in labels.items() if v == gv.gid), list(labels)[0])
        bar = ui.frame(host)
        bar.pack(fill="x", pady=(0, 10))
        ui.lbl(bar, "Partida", 10, "dim").pack(side="left", padx=(0, 8))
        ui.menu(bar, list(labels), cur, lambda v: gv.pick_game(labels[v]), min(430, gv.width - 160)).pack(side="left")
        a = gv.data.get(gv.gid)
        if a is None:
            gv.data[gv.gid] = "cargando"
            self.gui.cmds.put(("analysis", int(gv.gid)))
            a = "cargando"
        if a == "cargando":
            ui.lbl(host, "Leyendo la línea de tiempo de la partida…", 11, "dim").pack(anchor="w", pady=6)
            return
        if a == "no":
            ui.lbl(host, "El cliente ya no guarda la línea de tiempo de esta partida (solo conserva las más recientes) o LoL está cerrado.",
                   11, "dim", anchor="w", justify="left", wraplength=max(260, gv.width - 110)).pack(anchor="w", pady=(6, 4))
            have = [g for g in gv.games if isinstance(gv.data.get(g["id"]), dict)]
            if have:
                from ui_views import small_btn
                small_btn(ui, host, "Ir a la última partida con análisis", lambda: gv.pick_game(have[0]["id"]), 240).pack(anchor="w", pady=4)
            else:
                ui.lbl(host, "Se analizan solas las partidas que acaban con LOL-E abierto; también puedes abrir una reciente desde el menú de arriba.",
                       10, "dim", anchor="w", justify="left", wraplength=max(260, gv.width - 110)).pack(anchor="w")
            return
        self.body(host, a)

    def body(self, host, a):
        ui, gv = self.ui, self.gv
        if a.get("queue") in analysis.ARAM_QUEUES:   # ARAM: sin rival de línea, todos los jugadores (ui_aram.py)
            import ui_aram
            ui_aram.body(self, host, a)
            return
        opp = gv.opp.get(gv.gid) or analysis.default_opp(a)
        if opp is None or analysis.player(a, opp) is None:
            opp = (analysis.enemies(a) or [{"pid": None}])[0]["pid"]
        self.nosec = True
        self.hosts, self.folds, self.cur = {}, {}, (a, opp)
        self.header(host, a, opp)
        self.kpis(host, a, opp)
        adv = analysis.advice(a, opp, ui.champs)
        ev = self.events(a)
        nb, ng = sum(1 for x in adv if x["tone"] == "bad"), sum(1 for x in adv if x["tone"] == "good")
        if a.get("queue") in analysis.ARAM_QUEUES:
            ui.fold(host, "Lo más interesante de la partida", lambda p: self.advice(p, a, opp, adv), f"{len(adv)} datos", "an_advice", True)
        else:
            ui.fold(host, "Consejos de esta partida", lambda p: self.advice(p, a, opp, adv),
                    f"{nb} a mejorar · {ng} bien" if adv else "sin nada destacable", "an_advice", True)
        if a.get("queue") in (2400,) and any(p.get("aug") for p in a["players"].values()):
            import ui_mayhem
            ui.fold(host, "Mejoras elegidas", lambda p: ui_mayhem.analysis_block(ui, p, a, gv.width), "las de los 10 jugadores", "an_aug", True)
        mine = sum(1 for e in ev if e["cat"] == "kd")
        self.cur = (a, opp, ev)
        self.folds["moments"] = ui.fold(host, "Momentos clave", lambda p: self.mount("moments", p, a, opp, ev), f"{len(ev)} eventos · {mine} tuyos", "an_moments", True)
        self.folds["charts"] = ui.fold(host, "Evolución de la partida", lambda p: self.mount("charts", p, a, opp, ev), gv.chart, "an_charts", True)
        if opp is not None:
            o = analysis.player(a, opp)
            g10 = analysis.at(a, analysis.diff(a, "gold_s", a["me"], opp), 10)
            ui.fold(host, f"Tú frente a {self.cname(o['champ'])}", lambda p: self.table(p, a, opp),
                    f"oro a minuto 10: {sg(g10)}" if g10 is not None else "", "an_table", False)
        self.folds["teams"] = ui.fold(host, "Los dos equipos", lambda p: self.mount("teams", p, a, opp, ev), f"orden: {self.sort.lower()}", "an_teams", False)

    def mount(self, name, host, a, opp, ev):
        """Pinta una sección y guarda su contenedor para poder repintar solo esa."""
        self.hosts[name] = host
        {"moments": lambda: self.moments(host, a, ev), "charts": lambda: self.charts(host, a, opp), "teams": lambda: self.scoreboard(host, a, opp)}[name]()

    def rerender(self, name, summary=None):
        """Repinta una sola sección (si existe). Devuelve False si hay que reconstruir la pestaña entera."""
        host = self.hosts.get(name)
        if host is None and name in self.folds and self.folds[name].winfo_exists():
            if summary is not None:  # la sección está plegada y aún sin construir: se pintará bien al abrirla
                self.folds[name].set_summary(summary)
            return True
        if host is None or not host.winfo_exists() or not self.cur:
            return False
        a, opp = self.cur[0], self.cur[1]
        ev = self.cur[2] if len(self.cur) > 2 else []
        self.ui.clear(host)
        self.mount(name, host, a, opp, ev)
        if summary is not None and name in self.folds:
            self.folds[name].set_summary(summary)
        return True

    def section(self, host, title, sub=None):
        if self.nosec:
            return
        ui = self.ui
        row = ui.frame(host)
        row.pack(fill="x", pady=(18, 6))
        ui.lbl(row, title, 10, "dim", True).pack(side="left")
        if sub:
            ui.lbl(row, "   " + sub, 9, "dim").pack(side="left")

    # ------------------------------------------------------------ cabecera: tú contra tu rival
    def header(self, host, a, opp):
        ui, gv = self.ui, self.gv
        m = analysis.me(a)
        card = ctk.CTkFrame(host, fg_color=PAL["card2"], corner_radius=14)
        card.pack(fill="x", pady=(0, 8))
        row = ui.frame(card)
        row.pack(fill="x", padx=16, pady=12)
        left = ui.frame(row)
        left.pack(side="left")
        ui.champ(left, m["champ"], 56, False, self.hx(ui.acc)).pack(side="left", padx=(0, 10))
        t = ui.frame(left)
        t.pack(side="left")
        ui.lbl(t, "TÚ", 9, "dim", True).pack(anchor="w")
        ui.lbl(t, self.cname(m["champ"]), 17, "fg", True, True).pack(anchor="w")
        ui.lbl(t, self.rl(a, m["role"]) or "ARAM", 10, "dim").pack(anchor="w")
        mid = ui.frame(row)
        mid.pack(side="left", expand=True)
        ui.lbl(mid, "Victoria" if a["win"] else "Derrota", 20, "good" if a["win"] else "bad", True, True).pack()
        ui.lbl(mid, f"{a['dur'] // 60}:{a['dur'] % 60:02d}", 11, "dim").pack()
        lp = analysis.lp_for(core.CACHE, self.gv.gid)
        if lp:
            d = lp["d"]
            txt = f"{'+' if d > 0 else '−' if d < 0 else ''}{abs(d)} PL"
            ui.lbl(mid, txt, 13, "good" if d > 0 else "bad" if d < 0 else "dim", True).pack(pady=(2, 0))
            ui.lbl(mid, (lp["move"] + " · " if lp.get("move") else "") + f"ahora {lp['tier']} · {lp['now']} PL", 9, "dim").pack()
        if opp is None:
            return
        o = analysis.player(a, opp)
        right = ui.frame(row)
        right.pack(side="right")
        t2 = ui.frame(right)
        t2.pack(side="left", padx=(0, 10))
        ui.lbl(t2, "COMPARADO CON", 9, "dim", True, anchor="e").pack(anchor="e")
        ui.lbl(t2, self.cname(o["champ"]), 17, "fg", True, True, anchor="e").pack(anchor="e")
        ui.lbl(t2, (self.rl(a, o["role"]) or "ARAM") + ((" · el que más daño hizo" if a.get("queue") in analysis.ARAM_QUEUES else " · rival directo") if opp == analysis.default_opp(a) else ""),
               10, "dim", anchor="e").pack(anchor="e")
        ui.champ(right, o["champ"], 56, False, self.hx("bad")).pack(side="left")
        # el rival se puede cambiar: por si la línea no se deduce bien o quieres compararte con otro
        labels = {f"{self.cname(p['champ'])}" + (f" · {self.rl(a, p['role'])}" if self.rl(a, p['role']) else ""): p["pid"] for p in sorted(analysis.enemies(a), key=lambda p: ORDER.index(p["role"]) if p["role"] in ORDER else 9)}
        cur = next(k for k, v in labels.items() if v == opp)
        sel = ui.frame(host)
        sel.pack(fill="x", pady=(0, 6))
        ui.lbl(sel, "Comparar con", 10, "dim").pack(side="left", padx=(0, 8))
        ui.menu(sel, list(labels), cur, lambda v: self.set_opp(labels[v]), 240).pack(side="left")
        ui.lbl(sel, ("  En ARAM no hay líneas: por defecto, el rival que más daño hizo." if a.get("queue") in analysis.ARAM_QUEUES else
                     "  La línea de cada jugador se deduce de su Smite y de dónde estuvo en los minutos 3 a 9."), 9, "dim").pack(side="left")

    def set_together(self, v):
        self.together = v == "Los 10 juntos"
        if not self.rerender("teams"):
            self.gv.sig = None
            self.gv.refresh(self.gui.make_ctx())

    def set_sort(self, v):
        self.sort = v
        if not self.rerender("teams", f"orden: {v.lower()}"):
            self.gv.sig = None
            self.gv.refresh(self.gui.make_ctx())

    def set_opp(self, pid):
        self.gv.opp[self.gv.gid] = pid
        self.gv.sig = None
        self.gv.refresh(self.gui.make_ctx())

    # ------------------------------------------------------------ cifras clave
    def kpis(self, host, a, opp):
        ui = self.ui
        m = analysis.me(a)
        o = analysis.player(a, opp) if opp is not None else None
        team = analysis.mates(a)
        tk_ = sum(1 for k in a["kills"] if (analysis.player(a, k["killer"]) or {}).get("team") == a["team"])
        kp = (m["k"] + m["a"]) / tk_ if tk_ else None
        tdmg = sum(p["dmg"] for p in team)
        vis_avg = sum(p["vision"] for p in team) / max(1, len(team))
        cards = [("K / D / A", f"{m['k']} / {m['d']} / {m['a']}", f"KDA {(m['k'] + m['a']) / max(1, m['d']):.2f}".replace(".", ",") + (f" · {kp * 100:.0f} % de las muertes" if kp is not None else ""), "fg"),
                 ("Oro", n(m["gold"]), (f"{sg(m['gold'] - o['gold'])} vs {self.cname(o['champ'])}" if o else ""), "good" if o and m["gold"] >= o["gold"] else "bad" if o else "fg"),
                 ("Súbditos", n(m["cs"]), (f"{sg(m['cs'] - o['cs'])} vs rival · {m['cs'] / max(1, a['dur'] / 60):.1f}/min".replace(".", ",") if o else ""), "fg"),
                 ("Daño", n(m["dmg"]), f"{m['dmg'] / tdmg * 100:.0f} % de tu equipo" if tdmg else "", "fg"),
                 ("Visión", str(m["vision"]), f"media de tu equipo {vis_avg:.0f}", "fg")]
        if a.get("queue") in analysis.ARAM_QUEUES:   # en ARAM los súbditos y la visión no cuentan: daño recibido y curación sí
            ttk = sum(p["taken"] for p in team) or 1
            cards[2] = ("Daño recibido", n(m["taken"]), f"{m['taken'] / ttk * 100:.0f} % de tu equipo", "fg")
            cards[4] = ("Curación", n(m["heal"]), f"mitigaste {n(m['mit'])}" if m["mit"] else "", "fg")
        row = ui.frame(host)
        row.pack(fill="x", pady=(0, 4))
        for i, (lb, val, sub, col) in enumerate(cards):
            c = ctk.CTkFrame(row, fg_color=PAL["card2"], corner_radius=10)
            c.pack(side="left", expand=True, fill="x", padx=(0 if i == 0 else 6, 0))
            ui.lbl(c, lb, 9, "dim").pack(anchor="w", padx=12, pady=(8, 0))
            ui.lbl(c, val, 15, col, True, True).pack(anchor="w", padx=12)
            ui.lbl(c, sub, 8, "dim", anchor="w", wraplength=max(90, (self.gv.width - 120) // 5 - 24), justify="left").pack(anchor="w", padx=12, pady=(0, 8))

    # ------------------------------------------------------------ gráficos
    def charts(self, host, a, opp):
        ui, gv = self.ui, self.gv
        o = analysis.player(a, opp) if opp is not None else None
        names = [c for c in CHARTS if opp is not None or c in ("Oro del equipo", "Ruta en el mapa")]
        if a.get("queue") in analysis.ARAM_QUEUES:
            names = ["Oro del equipo"]   # sin rival de línea: solo la ventaja de oro de los equipos
        if gv.chart not in names:
            gv.chart = names[0]
        self.section(host, "EVOLUCIÓN DE LA PARTIDA")
        ui.seg(host, names, gv.chart, gv.set_chart, height=28).pack(fill="x", pady=(0, 6))
        self.hover = ui.lbl(host, "Pasa el ratón por el gráfico para ver cada minuto.", 9, "dim", anchor="w")
        self.hover.pack(anchor="w", pady=(0, 2))
        W = self.avail()
        if gv.chart == "Ruta en el mapa":
            self.path(host, a, min(W, 460))
        else:
            self.chart(host, a, opp, gv.chart, W)
        legend = {"Oro del equipo": "Ventaja de oro de tu equipo sobre el rival (verde = vais por delante, rojo = por detrás).",
                  "Oro vs rival": f"Tu oro menos el de {self.cname(o['champ']) if o else 'tu rival'}.",
                  "Experiencia": f"Tu experiencia menos la de {self.cname(o['champ']) if o else 'tu rival'}.",
                  "Súbditos": f"Súbditos y monstruos: tú (color) y {self.cname(o['champ']) if o else 'tu rival'} (gris).",
                  "Ruta en el mapa": "Tu posición al inicio de cada minuto; la cifra marca los minutos 0, 5, 10… Las bases están en las esquinas."}[gv.chart]
        extra = "   ▲ tus muertes   ● tus asesinatos   ◆ objetivos épicos (verde: tuyos, rojo: rivales)" if gv.chart != "Ruta en el mapa" else ""
        ui.lbl(host, legend + extra, 9, "dim", anchor="w", justify="left", wraplength=max(260, gv.width - 110)).pack(anchor="w", pady=(2, 0))

    def chart(self, host, a, opp, which, W):
        ui = self.ui
        sx = ui.scale_px()
        S = lambda v: int(v * sx)
        H, ml, mb, mt, mr = 250, 56, 28, 14, 14
        mins = a["minutes"]
        m, o = analysis.me(a), analysis.player(a, opp) if opp is not None else None
        acc, good, bad, dim = self.hx(ui.acc), self.hx("good"), self.hx("bad"), self.hx("dim")
        card, border = self.hx("card2"), self.hx("border")
        if which == "Oro del equipo":
            data, diff = analysis.team_gold_diff(a), True
        elif which == "Oro vs rival":
            data, diff = analysis.diff(a, "gold_s", m["pid"], opp), True
        elif which == "Experiencia":
            data, diff = analysis.diff(a, "xp_s", m["pid"], opp), True
        else:
            data, diff = m["cs_s"], False
        second = o["cs_s"] if which == "Súbditos" and o else None
        vals = list(data) + (list(second) if second else [])
        if diff:
            top = nice(max(max(abs(v) for v in vals), 1))
            lo, hi = -top, top
        else:
            lo, hi = 0, nice(max(max(vals), 1) * 1.02)
        x0, x1 = mins[0], max(mins[-1], 1)
        px = lambda t: ml + (t - x0) / (x1 - x0) * (W - ml - mr)
        py = lambda v: mt + (hi - v) / (hi - lo) * (H - mt - mb)
        cv = tk.Canvas(host, width=S(W), height=S(H), bg=ui.bg(host), highlightthickness=0, bd=0)
        cv.pack(anchor="w", pady=(4, 0))
        cv.create_rectangle(S(ml), S(mt), S(W - mr), S(H - mb), fill=card, outline="")
        f9 = ui.tkf(9, False, False)
        for i in range(5):  # líneas horizontales y su escala
            v = lo + (hi - lo) * i / 4
            cv.create_line(S(ml), S(py(v)), S(W - mr), S(py(v)), fill=border)
            cv.create_text(S(ml - 6), S(py(v)), text=n(v) if which != "Súbditos" else str(int(v)), fill=dim, font=f9, anchor="e")
        step = 5 if x1 <= 40 else 10
        for t in range(0, int(x1) + 1, step):
            cv.create_text(S(px(t)), S(H - mb + 13), text=f"{t}'", fill=dim, font=f9)
        if diff:  # áreas: verde por encima de cero, rojo por debajo
            fp, fn = mix(card, good, 0.28), mix(card, bad, 0.28)
            for i in range(len(data) - 1):
                xa, xb, va, vb = px(mins[i]), px(mins[i + 1]), data[i], data[i + 1]
                if va * vb >= 0:
                    col = fp if (va + vb) >= 0 else fn
                    cv.create_polygon(S(xa), S(py(0)), S(xa), S(py(va)), S(xb), S(py(vb)), S(xb), S(py(0)), fill=col, outline="")
                else:
                    xc = xa + (xb - xa) * (va / (va - vb))
                    cv.create_polygon(S(xa), S(py(0)), S(xa), S(py(va)), S(xc), S(py(0)), fill=fp if va > 0 else fn, outline="")
                    cv.create_polygon(S(xc), S(py(0)), S(xb), S(py(vb)), S(xb), S(py(0)), fill=fp if vb > 0 else fn, outline="")
            cv.create_line(S(ml), S(py(0)), S(W - mr), S(py(0)), fill=dim)
        series = [(second, dim)] if second else []
        series.append((data, acc))
        for s, col in series:
            pts = [c for i, v in enumerate(s) for c in (S(px(mins[i])), S(py(v)))]
            if len(pts) >= 4:
                cv.create_line(*pts, fill=col, width=max(2, S(2)))
        for c in analysis.CHECK:  # puntos de control: minutos 5, 10, 15 y 20
            v = analysis.at(a, data, c)
            if v is not None:
                cv.create_oval(S(px(c) - 3), S(py(v) - 3), S(px(c) + 3), S(py(v) + 3), fill=acc, outline="")
        # marcadores
        who = lambda pid: self.cname((analysis.player(a, pid) or {}).get("champ")) if analysis.player(a, pid) else "una torre o los súbditos"
        for k in a["kills"]:
            if k["victim"] == m["pid"]:
                x, y = S(px(k["t"])), S(H - mb)
                it = cv.create_polygon(x, y - S(10), x - S(6), y, x + S(6), y, fill=bad, outline="")
                ui.canvas_tip(cv, it, f"Minuto {k['t']:.0f}: te mató {who(k['killer'])}")
            elif k["killer"] == m["pid"]:
                x, y = S(px(k["t"])), S(H - mb - 6)
                it = cv.create_oval(x - S(4), y - S(4), x + S(4), y + S(4), fill=good, outline="")
                ui.canvas_tip(cv, it, f"Minuto {k['t']:.0f}: mataste a {who(k['victim'])}")
        for ob in a["objectives"]:
            x, y = S(px(ob["t"])), S(mt + 9)
            mine = ob["team"] == a["team"]
            it = cv.create_polygon(x, y - S(7), x + S(7), y, x, y + S(7), x - S(7), y, fill=good if mine else bad, outline="")
            ui.canvas_tip(cv, it, f"Minuto {ob['t']:.0f}: {ob['what']} ({'tu equipo' if mine else 'rival'})")
        guide = []
        ref = (analysis.team_gold_diff(a), None)

        def move(e):
            for it in guide:
                cv.delete(it)
            guide.clear()
            i = min(range(len(mins)), key=lambda k: abs(px(mins[k]) - e.x / sx))
            x = S(px(mins[i]))
            guide.append(cv.create_line(x, S(mt), x, S(H - mb), fill=dim, dash=(3, 3)))
            guide.append(cv.create_oval(x - S(4), S(py(data[i])) - S(4), x + S(4), S(py(data[i])) + S(4), fill=acc, outline=""))
            if which == "Súbditos":
                txt = f"minuto {mins[i]:.0f}: tú {data[i]} · {self.cname(o['champ']) if o else 'rival'} {second[i] if second else '-'}"
            elif which == "Oro del equipo":
                txt = f"minuto {mins[i]:.0f}: tu equipo {sg(data[i])} de oro"
            else:
                txt = f"minuto {mins[i]:.0f}: {sg(data[i])} frente a {self.cname(o['champ']) if o else 'tu rival'}" + \
                      (f"  (tú {n(m['gold_s' if which == 'Oro vs rival' else 'xp_s'][i])} · rival {n(o['gold_s' if which == 'Oro vs rival' else 'xp_s'][i])})" if o else "")
            if self.hover is not None and self.hover.winfo_exists():
                self.hover.configure(text=txt)
        cv.bind("<Motion>", move)

    def path(self, host, a, W):
        ui = self.ui
        sx = ui.scale_px()
        S = lambda v: int(v * sx)
        m = analysis.me(a)
        cv = tk.Canvas(host, width=S(W), height=S(W), bg=self.hx("card2"), highlightthickness=0, bd=0)
        cv.pack(anchor="w", pady=(4, 0))
        top = 14900.0
        pts = [(p[0], p[1]) for p in m["pos"] if p[0] is not None]
        if len(pts) < 2:
            return
        cx = lambda x: x / top * (W - 24) + 12
        cy = lambda y: (1 - y / top) * (W - 24) + 12
        cv.create_line(S(10), S(W - 10), S(W - 10), S(10), fill=self.hx("border"), dash=(4, 4))
        for base, col in (((900, 900), self.hx("info")), ((14000, 14000), self.hx("bad"))):  # las dos bases
            cv.create_oval(S(cx(base[0]) - 9), S(cy(base[1]) - 9), S(cx(base[0]) + 9), S(cy(base[1]) + 9), outline=col, width=S(2))
        # un punto por minuto, del azul (inicio) al dorado (final); el trazo entre puntos es solo una guía tenue
        xy = [c for x, y in pts for c in (S(cx(x)), S(cy(y)))]
        cv.create_line(*xy, fill=mix(self.hx("card2"), self.hx("fg"), 0.22), width=max(1, S(1)))
        f9 = ui.tkf(9, True, False)
        first, last = self.hx("info"), self.hx(ui.acc)
        for i, (x, y) in enumerate(pts):
            col = mix(first, last, i / max(1, len(pts) - 1))
            r = 5 if i % 5 == 0 else 3
            it = cv.create_oval(S(cx(x) - r), S(cy(y) - r), S(cx(x) + r), S(cy(y) + r), fill=col, outline="")
            ui.canvas_tip(cv, it, f"Minuto {i}")
            if i % 5 == 0:
                cv.create_text(S(cx(x) + 12), S(cy(y) - 10), text=f"{i}'", fill=self.hx("fg"), font=f9)
        self.hover.configure(text="Cada punto es un minuto; las cifras marcan los minutos 0, 5, 10…")

    # ------------------------------------------------------------ comparación por fases
    def table(self, host, a, opp):
        ui = self.ui
        o = analysis.player(a, opp)
        self.section(host, f"TÚ FRENTE A {self.cname(o['champ']).upper()}", "diferencia en cada momento · entre paréntesis, tú / rival")
        cp = analysis.checkpoints(a, opp)
        cols = [c for c in (5, 10, 15, 20) if c in cp] + ["final"]
        sx = ui.scale_px()
        S = lambda v: int(v * sx)
        W = self.avail()
        lab_w, row_h = 92, 44
        H = 30 + row_h * 4 + 6
        cv = tk.Canvas(host, width=S(W), height=S(H), bg=ui.bg(host), highlightthickness=0, bd=0)
        cv.pack(anchor="w")
        ui.rrect(cv, 0, 0, S(W) - 1, S(H) - 1, S(10), fill=self.hx("card2"), outline="")
        fb, f9, f12b = ui.tkf(10, True, False), ui.tkf(9, False, False), ui.tkf(13, True, False)
        dim, fg = self.hx("dim"), self.hx("fg")
        cw = (W - lab_w - 14) / len(cols)
        for j, c in enumerate(cols):
            cv.create_text(S(lab_w + cw * j + cw / 2), S(16), text="Final" if c == "final" else f"Minuto {c}", fill=dim, font=fb)
        rows = [("gold", "Oro"), ("xp", "Experiencia"), ("cs", "Súbditos"), ("lvl", "Nivel")]
        for i, (k, label) in enumerate(rows):
            y = 30 + row_h * i
            if i:
                cv.create_line(S(10), S(y), S(W - 10), S(y), fill=self.hx("border"))
            cv.create_text(S(14), S(y + row_h / 2), text=label, fill=fg, font=fb, anchor="w")
            for j, c in enumerate(cols):
                v = cp.get(c, {}).get(k)
                cx = S(lab_w + cw * j + cw / 2)
                if not v:
                    cv.create_text(cx, S(y + row_h / 2), text="—", fill=dim, font=f12b)
                    continue
                d = v[0] - v[1]
                col = self.hx("good") if d > 0 else self.hx("bad") if d < 0 else dim
                cv.create_text(cx, S(y + row_h / 2 - 7), text=("=" if d == 0 else sg(d)), fill=col, font=f12b)
                cv.create_text(cx, S(y + row_h / 2 + 11), text=f"({n(v[0])} / {n(v[1])})", fill=dim, font=f9)

    # ------------------------------------------------------------ marcador de los dos equipos
    def scoreboard(self, host, a, opp):
        ui = self.ui
        self.section(host, "LOS DOS EQUIPOS", "pulsa una columna para ordenar, como en el marcador del juego")
        top = ui.frame(host)
        top.pack(fill="x", pady=(0, 6))
        ui.seg(top, ["Por equipos", "Los 10 juntos"], "Los 10 juntos" if self.together else "Por equipos", self.set_together, height=26, width=240).pack(side="left", padx=(0, 10))
        ui.seg(top, SORTS, self.sort, self.set_sort, height=26).pack(side="left", fill="x", expand=True)
        sx = ui.scale_px()
        S = lambda v: int(v * sx)
        W = self.avail()
        wide = W >= 780
        groups = [(None, "LOS 10 JUGADORES")] if self.together else [(a["team"], "TU EQUIPO"), (300 - a["team"], "EQUIPO RIVAL")]
        for team, title in groups:
            keyf = {"Línea": lambda p: ORDER.index(p["role"]) if p["role"] in ORDER else 9, "KDA": lambda p: -(p["k"] + p["a"]) / max(1, p["d"]),
                    "Daño": lambda p: -p["dmg"], "Oro": lambda p: -p["gold"], "Súbditos": lambda p: -p["cs"], "Visión": lambda p: -p["vision"]}[self.sort]
            ps = sorted([p for p in a["players"].values() if team is None or p["team"] == team], key=keyf)
            metric = {"Oro": ("gold", "Oro"), "Súbditos": ("cs", "Súb."), "Visión": ("vision", "Vis.")}.get(self.sort, ("dmg", "Daño"))
            tmax = max((p[metric[0]] for p in a["players"].values()), default=1) or 1
            row_h, head = 36, 24
            H = head + row_h * len(ps) + 6
            cv = tk.Canvas(host, width=S(W), height=S(H), bg=ui.bg(host), highlightthickness=0, bd=0)
            cv.pack(anchor="w", pady=(0, 8))
            cv.image = []
            ui.rrect(cv, 0, 0, S(W) - 1, S(H) - 1, S(10), fill=self.hx("card2"), outline="")
            fb, f9, f11 = ui.tkf(11, True, False), ui.tkf(9, False, False), ui.tkf(11, False, False)
            dim, fg, acc = self.hx("dim"), self.hx("fg"), self.hx(ui.acc)
            bw = max(110, int(W * 0.15))
            x_kda, x_dmg = 190, 290
            x_items = W - 12 - 150
            span_end = (x_items if wide else W - 12) - 20
            x_gold = x_dmg + bw + 30
            gap = max(48, (span_end - x_gold - 40) / 3)
            x_cs, x_vis = x_gold + gap, x_gold + 2 * gap
            cv.create_text(S(12), S(13), text=title, fill=dim, font=ui.tkf(9, True, False), anchor="w")
            for x, t, key in ((x_kda, "K / D / A", "KDA"), (x_dmg, metric[1] if self.sort not in ("Oro", "Súbditos", "Visión") else "Daño", "Daño"),
                              (x_gold, "Oro", "Oro"), (x_cs, "Súb.", "Súbditos"), (x_vis, "Vis.", "Visión")):
                on = self.sort == key
                it = cv.create_text(S(x), S(13), text=t + (" ▾" if on else ""), fill=acc if on else dim, font=ui.tkf(9, on, False), anchor="w", tags=("h_" + key,))
                cv.tag_bind("h_" + key, "<Button-1>", lambda e, k=key: self.set_sort(k))
                cv.tag_bind("h_" + key, "<Enter>", lambda e, c=cv: c.configure(cursor="hand2"))
                cv.tag_bind("h_" + key, "<Leave>", lambda e, c=cv: c.configure(cursor=""))
            for i, p in enumerate(ps):
                y = head + row_h * i
                mine, rival = p["pid"] == a["me"], p["pid"] == opp
                if self.together:  # una franja marca el equipo de cada uno
                    cv.create_rectangle(S(5), S(y + 3), S(8), S(y + row_h - 3), fill=acc if p["team"] == a["team"] else self.hx("bad"), outline="")
                if mine or rival:
                    ui.rrect(cv, S(4), S(y + 1), S(W - 4), S(y + row_h - 1), S(8), fill=mix(self.hx("card2"), acc if mine else self.hx("bad"), 0.18), outline="")
                ph = ui.champ_photo(p["champ"], 26)
                if ph is not None:
                    cv.create_image(S(12), S(y + 5), image=ph, anchor="nw")
                    cv.image.append(ph)
                cv.create_text(S(46), S(y + 11), text=ui.fit(self.cname(p["champ"]), fb, S(130)), fill=fg, font=fb, anchor="w")
                cv.create_text(S(46), S(y + 25), text=self.rl(a, p["role"]) if self.rl(a, p["role"]) != "?" else "", fill=dim, font=f9, anchor="w")
                cv.create_text(S(x_kda), S(y + row_h / 2), text=f"{p['k']} / {p['d']} / {p['a']}", fill=fg, font=f11, anchor="w")
                cv.create_rectangle(S(x_dmg), S(y + 12), S(x_dmg + bw), S(y + 18), fill=self.hx("card"), outline="")
                cv.create_rectangle(S(x_dmg), S(y + 12), S(x_dmg + max(2, bw * p[metric[0]] / tmax)), S(y + 18), fill=acc if p["team"] == a["team"] else self.hx("bad"), outline="")
                cv.create_text(S(x_dmg), S(y + 28), text=n(p[metric[0]]), fill=dim, font=f9, anchor="w")
                cv.create_text(S(x_gold), S(y + row_h / 2), text=n(p["gold"]), fill=fg, font=f11, anchor="w")
                cv.create_text(S(x_cs), S(y + row_h / 2), text=str(p["cs"]), fill=fg, font=f11, anchor="w")
                cv.create_text(S(x_vis), S(y + row_h / 2), text=str(p["vision"]), fill=fg, font=f11, anchor="w")
                if wide:
                    for q, iid in enumerate(p["items"][:6]):
                        iph = ui.item_photo(iid, 22) if iid else None
                        if iph is not None:
                            it = cv.create_image(S(x_items + q * 25), S(y + 7), image=iph, anchor="nw")
                            cv.image.append(iph)
                            info = ui.items.get(iid)
                            if info:
                                ui.canvas_tip(cv, it, f"{info['n']}  ·  {info['g']} de oro")
                        else:
                            cv.create_rectangle(S(x_items + q * 25), S(y + 7), S(x_items + q * 25 + 22), S(y + 29), fill=self.hx("card"), outline="")

    # ------------------------------------------------------------ consejos
    def advice(self, host, a, opp, items=None):
        ui = self.ui
        items = items if items is not None else analysis.advice(a, opp, ui.champs)
        if not items:
            ui.lbl(host, "No hay nada destacable que decir de esta partida.", 11, "dim").pack(anchor="w")
            return
        bad = [x["title"] for x in items if x["tone"] == "bad"][:2]
        good = [x["title"] for x in items if x["tone"] == "good"][:2]
        key = bad if (bad and not a["win"]) or (bad and not good) else good or bad
        if key:
            line = ui.frame(host)
            line.pack(anchor="w", pady=(0, 6))
            ui.lbl(line, "Lo que más pesó:  " if key is bad else "Lo mejor:  ", 11, "dim", True).pack(side="left")
            ui.lbl(line, " · ".join(key), 11, "bad" if key is bad else "good", True, anchor="w", justify="left",
                   wraplength=max(240, self.gv.width - 260)).pack(side="left")
        for it in items[:9]:
            color = {"good": "good", "bad": "bad"}.get(it["tone"], "info")
            card = tk.Frame(host, bg=self.hx("card2"))
            card.pack(fill="x", pady=3)
            tk.Frame(card, bg=self.hx(color), width=4).pack(side="left", fill="y")
            inner = ui.frame(card)
            inner.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            ui.lbl(inner, it["title"], 12, "fg", True, anchor="w").pack(anchor="w")
            if it["detail"]:
                ui.lbl(inner, it["detail"], 10, "fg", anchor="w", justify="left", wraplength=max(240, self.gv.width - 150)).pack(anchor="w")
            if it["data"]:
                ui.lbl(inner, "Dato: " + it["data"], 9, "dim", anchor="w", justify="left", wraplength=max(240, self.gv.width - 150)).pack(anchor="w", pady=(2, 0))
        ui.lbl(host, "Salen de restas y umbrales sencillos sobre la línea de tiempo del cliente; son orientativos y no tienen en cuenta lo que pasó fuera de los datos "
                     "(comunicación, decisiones, composición).", 9, "dim", anchor="w", justify="left", wraplength=max(260, self.gv.width - 110)).pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------ momentos clave
    PHASES = [("Inicio", 0, 14), ("Medio", 14, 25), ("Final", 25, 999)]
    FILTERS = {"Todo": None, "Mis K/D/A": "kd", "Objetivos": "obj", "Torres": "tower"}

    def events(self, a):
        """Lista de eventos para pintar: {t, kind, mine, cat, champs, text, part}."""
        m = analysis.me(a)
        T = a["team"]
        pl = lambda pid: analysis.player(a, pid)
        who = lambda pid: self.cname(pl(pid)["champ"]) if pl(pid) else "una torre o los súbditos"
        champ_of = lambda pid: [pl(pid)["champ"]] if pl(pid) else []
        ev = []
        for idx, k in enumerate(a["kills"]):
            if k["victim"] == m["pid"]:
                ev.append(dict(t=k["t"], kind="death", mine=False, cat="kd", champs=champ_of(k["killer"]), text=f"Te mató {who(k['killer'])}", part=True))
            elif k["killer"] == m["pid"]:
                ev.append(dict(t=k["t"], kind="kill", mine=True, cat="kd", champs=champ_of(k["victim"]), text=f"Mataste a {who(k['victim'])}", part=True))
            elif m["pid"] in k["assists"]:
                ev.append(dict(t=k["t"], kind="assist", mine=True, cat="kd", champs=champ_of(k["victim"]), text=f"Asististe en la muerte de {who(k['victim'])}", part=True))
            elif idx == 0:
                ev.append(dict(t=k["t"], kind="first", mine=None, cat="kd", champs=champ_of(k["killer"]), text=f"Primera sangre: {who(k['killer'])} mató a {who(k['victim'])}", part=False))
        for ob in a["objectives"]:
            mine = ob["team"] == T
            kind = {"DRAGON": "dragon", "BARON_NASHOR": "baron", "RIFTHERALD": "herald", "HORDE": "grubs", "ATAKHAN": "baron"}.get(ob.get("type"), "dragon")
            part = mine and (ob["killer"] == m["pid"] or m["pid"] in ob["assists"])
            ev.append(dict(t=ob["t"], kind=kind, mine=mine, cat="obj", champs=champ_of(ob["killer"]),
                           text=f"{ob['what'].capitalize()} {'de tu equipo' if mine else 'del rival'}" + (" (participaste)" if part else ""), part=part))
        lanes = {"TOP_LANE": "superior", "MID_LANE": "central", "BOT_LANE": "inferior"}
        for t in a["towers"]:
            mine = t["owner"] != T  # lo derriba tu equipo si el edificio era del rival
            inhib = t["kind"] == "INHIBITOR_BUILDING"
            lane = lanes.get(t.get("lane"), "")
            what = "Inhibidor" if inhib else "Torre"
            ev.append(dict(t=t["t"], kind="inhib" if inhib else "tower", mine=mine, cat="tower", champs=champ_of(t["killer"]),
                           text=(f"{what} {lane} derribada por tu equipo" if mine else f"{what} {lane} de tu equipo caída").replace("  ", " "), part=False))
        ev.sort(key=lambda e: e["t"])
        return ev

    def color_of(self, e):
        if e["kind"] == "first":
            return self.hx("dim")
        if e["kind"] == "death":
            return self.hx("bad")
        return self.hx("good") if e["mine"] else self.hx("bad")

    def icon(self, cv, x, y, kind, col, r, ring=None):
        """Iconos sencillos dibujados con formas: asesinato ●, asistencia ○, muerte ▼, dragón ◆, Barón ⬢, Heraldo ◇, larvas □, torre ▮, inhibidor ⬡."""
        o = {"fill": col, "outline": ""}
        if ring:
            cv.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3, outline=ring, width=2)
        if kind in ("kill",):
            cv.create_oval(x - r, y - r, x + r, y + r, **o)
        elif kind in ("assist", "first"):
            cv.create_oval(x - r, y - r, x + r, y + r, outline=col, width=2)
        elif kind == "death":
            cv.create_polygon(x - r, y - r * 0.7, x + r, y - r * 0.7, x, y + r, **o)
        elif kind == "dragon":
            cv.create_polygon(x, y - r - 1, x + r + 1, y, x, y + r + 1, x - r - 1, y, **o)
        elif kind == "herald":
            cv.create_polygon(x, y - r - 1, x + r + 1, y, x, y + r + 1, x - r - 1, y, fill="", outline=col, width=2)
        elif kind == "baron":
            k = r + 1
            cv.create_polygon(x - k * 0.5, y - k, x + k * 0.5, y - k, x + k, y, x + k * 0.5, y + k, x - k * 0.5, y + k, x - k, y, **o)
        elif kind == "inhib":
            k = r + 1
            cv.create_polygon(x - k * 0.5, y - k, x + k * 0.5, y - k, x + k, y, x + k * 0.5, y + k, x - k * 0.5, y + k, x - k, y, fill="", outline=col, width=2)
        elif kind == "grubs":
            cv.create_rectangle(x - r + 1, y - r + 1, x + r - 1, y + r - 1, outline=col, width=2)
        else:  # torre
            cv.create_rectangle(x - r + 1, y - r, x + r - 1, y + r, **o)
            cv.create_rectangle(x - r + 3, y - r - 2, x - r + 5, y - r, **o)
            cv.create_rectangle(x + r - 5, y - r - 2, x + r - 3, y - r, **o)

    def set_mfilter(self, v):
        self.mfilter = v
        if not self.rerender("moments"):
            self.gv.sig = None
            self.gv.refresh(self.gui.make_ctx())

    def moments(self, host, a, ev):
        ui, gv = self.ui, self.gv
        if not ev:
            ui.lbl(host, "No hay eventos registrados en esta partida.", 11, "dim").pack(anchor="w")
            return
        cat = self.FILTERS[self.mfilter]
        ui.seg(host, list(self.FILTERS), self.mfilter, self.set_mfilter, height=26, width=min(440, gv.width - 120)).pack(anchor="w", pady=(0, 8))
        W = self.avail()
        self.timeline(host, a, ev, W, cat)
        ui.lbl(host, "● asesinato   ○ asistencia   ▼ muerte   ◆ dragón   ⬢ Barón   ◇ Heraldo   □ larvas   ▮ torre   ·   verde: tuyo o de tu equipo, rojo: rival, "
                     "aro dorado: participaste", 9, "dim", anchor="w", justify="left", wraplength=max(260, gv.width - 110)).pack(anchor="w", pady=(0, 8))
        shown = [e for e in ev if cat is None or e["cat"] == cat]
        for i, (name_, lo, hi) in enumerate(self.PHASES):
            part = [e for e in shown if lo <= e["t"] < hi]
            if not part:
                continue
            span = f"{lo}–{hi}'" if hi < 999 else f"{lo}' en adelante"
            ui.fold(host, f"{name_} · {span}", lambda p, part=part: self.rows(p, a, part, W), f"{len(part)} eventos", f"an_ph{i}", i == 0)

    def timeline(self, host, a, ev, W, cat):
        """Línea de tiempo horizontal: arriba objetivos y torres, abajo tus muertes, asesinatos y asistencias."""
        ui = self.ui
        sx = ui.scale_px()
        S = lambda v: int(v * sx)
        H, ml, mr = 92, 12, 12
        dur = max(a["minutes"][-1] if a["minutes"] else 1, 1)
        px = lambda t: ml + t / dur * (W - ml - mr)
        cv = tk.Canvas(host, width=S(W), height=S(H), bg=ui.bg(host), highlightthickness=0, bd=0)
        cv.pack(anchor="w", pady=(0, 8))
        card, dim = self.hx("card2"), self.hx("dim")
        for i, (name_, lo, hi) in enumerate(self.PHASES):
            x0, x1 = px(lo), px(min(hi, dur))
            if x1 <= x0:
                continue
            cv.create_rectangle(S(x0), S(0), S(x1), S(H - 18), fill=mix(card, self.hx("fg"), 0.05 if i % 2 else 0.0), outline="")
            cv.create_text(S(x0 + 8), S(10), text=name_.upper(), fill=dim, font=ui.tkf(8, True, False), anchor="w")
        cv.create_line(S(ml), S(H - 18), S(W - mr), S(H - 18), fill=self.hx("border"))
        for t in range(0, int(dur) + 1, 5):
            cv.create_text(S(px(t)), S(H - 8), text=f"{t}'", fill=dim, font=ui.tkf(8, False, False))
        ring = self.hx(ui.acc)
        order = list(ev)
        state = {"i": 0}

        def draw(e):
            y = S(34) if e["cat"] in ("obj", "tower") else S(64)
            col = self.color_of(e)
            if cat is not None and e["cat"] != cat:
                col = mix(card, col, 0.22)
            self.icon(cv, S(px(e["t"])), y, e["kind"], col, S(5), ring if (e["part"] and e["cat"] == "obj" and (cat is None or e["cat"] == cat)) else None)
            hot = cv.create_rectangle(S(px(e["t"]) - 7), y - S(9), S(px(e["t"]) + 7), y + S(9), outline="", fill="")
            ui.canvas_tip(cv, hot, f"{int(e['t'])}' · {e['text']}")

        def step():
            if not cv.winfo_exists():
                return
            n = max(1, len(order) // 22)  # unos 22 pasos: la animación dura menos de medio segundo
            for _ in range(n):
                if state["i"] < len(order):
                    draw(order[state["i"]])
                    state["i"] += 1
            if state["i"] < len(order):
                cv.after(16, step)
        if ui.anim_on():
            step()
        else:
            for e in order:
                draw(e)

    def rows(self, host, a, part, W):
        """Filas de una fase en un solo lienzo: minuto, icono, campeón implicado y texto; resalta la fila bajo el ratón."""
        ui = self.ui
        sx = ui.scale_px()
        S = lambda v: int(v * sx)
        RH = 30
        H = RH * len(part) + 4
        cv = tk.Canvas(host, width=S(W), height=S(H), bg=ui.bg(host), highlightthickness=0, bd=0)
        cv.pack(anchor="w", pady=(2, 4))
        cv.image = []
        card, fg, dim, acc = self.hx("card2"), self.hx("fg"), self.hx("dim"), self.hx(ui.acc)
        hl = cv.create_rectangle(0, 0, 0, 0, fill=mix(card, fg, 0.10), outline="")
        fb, f10 = ui.tkf(10, True, False), ui.tkf(10, False, False)
        for i, e in enumerate(part):
            y = i * RH + 2
            cv.create_line(S(8), S(y + RH), S(W - 8), S(y + RH), fill=self.hx("border"))
            cv.create_text(S(14), S(y + RH / 2), text=f"{int(e['t'])}'", fill=dim, font=fb, anchor="w")
            self.icon(cv, S(64), S(y + RH / 2), e["kind"], self.color_of(e), S(5), acc if e["part"] and e["cat"] == "obj" else None)
            x = 92
            for cid in e["champs"][:1]:
                ph = ui.champ_photo(cid, 22)
                if ph is not None:
                    cv.create_image(S(x), S(y + 4), image=ph, anchor="nw")
                    cv.image.append(ph)
                    x += 30
            cv.create_text(S(x), S(y + RH / 2), text=ui.fit(e["text"], f10, S(W - x - 20)), fill=fg, font=f10, anchor="w")

        def move(ev):
            i = int(ev.y / sx // RH)
            if 0 <= i < len(part):
                cv.coords(hl, 0, S(i * RH + 2), S(W), S(i * RH + 2 + RH))
        cv.bind("<Motion>", move)
        cv.bind("<Leave>", lambda e: cv.coords(hl, 0, 0, 0, 0))
