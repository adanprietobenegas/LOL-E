"""Pestaña «Partida»: el plan de tu campeón (build, runas, enfrentamiento, consejos) y el análisis de partidas ya jugadas.

«Plan» se queda disponible tras la selección, durante la partida y después: no hay que buscarlo a mano.
«Análisis» usa la línea de tiempo que guarda el propio cliente de LoL: oro, experiencia y súbditos minuto a minuto, muertes,
objetivos y tu recorrido por el mapa, más consejos que dicen de dónde salen (ver analysis.py).
"""
import os
import threading
import tkinter as tk

import customtkinter as ctk

import analysis
import history
import lol_advisor as core
import matchups
from ui_build import build_panel
from ui_history import fecha, mode_of
from ui_kit import PAL, ROLES_ES
from ui_views import small_btn

TABS = ["Plan", "Análisis"]
CHARTS = ["Oro del equipo", "Oro en tu línea", "Experiencia", "Súbditos", "Recorrido"]
STATE = {"select": "En selección", "game": "Partida en curso", "done": "Última partida"}
LANE_OF = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support"}


def nice(v):
    """Redondea hacia arriba a 1, 2, 2,5, 5 o 10 por una potencia de diez: las escalas quedan con números redondos."""
    import math
    p = 10 ** math.floor(math.log10(max(v, 1)))
    for k in (1, 2, 2.5, 5, 10):
        if v <= k * p:
            return k * p
    return 10 * p


class GameView:
    def __init__(self, ui, parent, gui):
        self.ui, self.gui = ui, gui
        self.box = ui.frame(parent)
        self.sig = None
        self.tab, self.chart, self.gid = "Plan", CHARTS[0], None
        self.data = {}          # id de partida -> análisis | "cargando" | "no"
        self.vs = {}            # (rival, línea) -> filas | "cargando" | ("error", texto)
        self.games, self.width, self.host = [], 520, None
        self.hover_lbl = None

    # ---- ciclo de vida ----
    def refresh(self, ctx, force=False):
        ui = self.ui
        self.width = ctx["width"]
        plan = ctx.get("plan") or {}
        sig = (ui.epoch, self.width // 80, self.tab, self.chart, self.gid, plan.get("cid"), plan.get("opp"), plan.get("state"),
               tuple(plan.get("enemies") or ()), str(self.data.get(self.gid))[:20], str(self.vs.get((plan.get("opp"), plan.get("role"))))[:20])
        if sig == self.sig and not force:
            return
        self.sig = sig
        for w in self.box.winfo_children():
            w.destroy()
        card = ui.card(self.box)
        top = ui.frame(card)
        top.pack(fill="x", pady=(0, 10))
        ui.lbl(top, "Tu partida", 16, "fg", True, True).pack(side="left")
        ui.seg(top, TABS, self.tab, self.set_tab, width=220, height=28).pack(side="right")
        self.host = ui.frame(card)
        self.host.pack(fill="x")
        (self.plan_tab if self.tab == "Plan" else self.analysis_tab)(ctx)

    def set_tab(self, v):
        self.tab = v
        self.sig = None
        self.refresh(self.gui.make_ctx())

    def on_data(self, gid, data):
        """Llega el análisis de una partida desde el hilo que lee el cliente."""
        self.data[gid] = data if data else "no"
        if self.gui.view == "game":
            self.refresh(self.gui.make_ctx(), True)

    def on_vs(self):
        if self.gui.view == "game":
            self.refresh(self.gui.make_ctx(), True)

    # ---- plan ----
    def plan_tab(self, ctx):
        ui, host = self.ui, self.host
        plan = ctx.get("plan")
        if not plan or plan["cid"] not in ui.champs:
            ui.lbl(host, "Cuando elijas campeón en una selección, aquí tendrás su build, sus runas, el enfrentamiento y consejos, "
                         "también durante la partida y después.", 11, "dim", anchor="w", justify="left",
                   wraplength=max(260, self.width - 110)).pack(anchor="w", pady=6)
            return
        cid, opp, role = plan["cid"], plan.get("opp") or 0, plan.get("role") or ""
        lane = LANE_OF.get(role)
        head = ui.frame(host)
        head.pack(fill="x", pady=(0, 8))
        ui.champ(head, cid, 56, False, ui.hexm(ui.acc)).pack(side="left", padx=(0, 12))
        txt = ui.frame(head)
        txt.pack(side="left")
        ui.lbl(txt, STATE.get(plan.get("state"), "").upper() + ("  ·  bloqueado" if plan.get("locked") and plan.get("state") == "select" else ""),
               9, "dim", True).pack(anchor="w")
        ui.lbl(txt, core.name(cid, ui.champs), 20, "fg", True, True).pack(anchor="w")
        sub = ROLES_ES.get(role, "").lower()
        if opp and opp in ui.champs:
            sub += f"  ·  contra {core.name(opp, ui.champs)}"
        ui.lbl(txt, sub or "sin línea asignada", 10, "dim").pack(anchor="w")
        if lane:
            self.ui.lbl(self.host, "", 4, "dim").pack()
            build_panel(ui, host, cid, lane, opp or None, min(self.width - 120, 720)).pack(fill="x")
        self.matchup_block(plan, lane)
        self.tips_block(plan, role)

    def section(self, title):
        self.ui.lbl(self.host, title, 10, "dim", True, anchor="w").pack(anchor="w", pady=(14, 4))

    def matchup_block(self, plan, lane):
        ui = self.ui
        cid, opp = plan["cid"], plan.get("opp") or 0
        if not opp or not lane or opp not in ui.champs:
            return
        self.section("TU ENFRENTAMIENTO")
        key = (opp, plan.get("role"))
        st = self.vs.get(key)
        if st is None:
            self.vs[key] = "cargando"

            def go():
                try:
                    rows = matchups.best_against(ui.champs, opp, lane, core.CACHE, min_games=20)
                except Exception as e:
                    rows = ("error", str(e))
                self.vs[key] = rows
                ui.notify("game_data")
            threading.Thread(target=go, daemon=True).start()
            st = "cargando"
        if st == "cargando":
            ui.lbl(self.host, "Cargando datos del enfrentamiento…", 10, "dim").pack(anchor="w")
            return
        if isinstance(st, tuple):
            ui.lbl(self.host, f"Sin datos de este enfrentamiento ({st[1]}).", 10, "dim", anchor="w").pack(anchor="w")
            return
        mine = next((x for x in st if x["cid"] == cid), None)
        if not mine:
            ui.lbl(self.host, f"Lolalytics no tiene suficientes partidas de {core.name(cid, ui.champs)} contra {core.name(opp, ui.champs)}.",
                   10, "dim", anchor="w").pack(anchor="w")
            return
        wr = mine["wr"]
        verdict = "favorable" if wr >= 52 else "desfavorable" if wr <= 48 else "igualado"
        col = "good" if wr >= 52 else "bad" if wr <= 48 else "fg"
        row = ui.frame(self.host)
        row.pack(anchor="w")
        ui.lbl(row, f"{wr:.1f} %".replace(".", ","), 22, col, True, True).pack(side="left")
        ui.lbl(row, f"   de victorias de {core.name(cid, ui.champs)} contra {core.name(opp, ui.champs)} en tu línea: enfrentamiento {verdict}",
               11, "dim").pack(side="left")
        better = [x for x in st if x["wr"] > wr + 1.5][:3]
        ui.lbl(self.host, f"Datos de {mine['games']:,} partidas de Lolalytics (todos los jugadores).".replace(",", ".") +
               ("" if not better else "  Mejores contra él: " + ", ".join(f"{core.name(x['cid'], ui.champs)} {x['wr']:.1f} %".replace(".", ",")
                                                                           for x in better) + "."), 9, "dim", anchor="w", justify="left",
               wraplength=max(260, self.width - 110)).pack(anchor="w", pady=(2, 0))

    def tips_block(self, plan, role):
        ui = self.ui
        champs = ui.champs
        ens = core.comp_stats(plan.get("enemies") or [], champs, True)
        als = core.comp_stats(plan.get("allies") or [], champs)
        tips = list(core.build_tips(champs[plan["cid"]], ens, als))
        if role == "JUNGLE":
            tips.append(("Recorrido", "Ninguna fuente pública fiable da recorridos de jungla por campeón. Al acabar la partida, en «Análisis → Recorrido» "
                                      "ves por dónde fuiste tú, minuto a minuto, para compararlo con lo que querías hacer."))
        if not tips:
            return
        self.section("CONSEJOS")
        for title, text in tips:
            row = ui.frame(self.host)
            row.pack(fill="x", pady=2)
            ui.lbl(row, title.upper(), 9, "dim", True, width=96, anchor="w").pack(side="left", anchor="n", pady=(3, 0))
            ui.lbl(row, text, 11, "fg", anchor="w", justify="left", wraplength=max(240, self.width - 250)).pack(side="left", fill="x", expand=True)
        ui.lbl(self.host, "Orientativo: sale de tus campeones y de la composición rival; no sustituye a la build del parche.", 9, "dim",
               anchor="w").pack(anchor="w", pady=(6, 0))

    # ---- análisis ----
    def load_games(self):
        try:
            self.games = history.load_all(os.path.join(core.CACHE, "history.json"), os.path.join(core.CACHE, "games.json"))[:30]
        except Exception:
            self.games = []

    def analysis_tab(self, ctx):
        ui, host = self.ui, self.host
        self.load_games()
        if not self.games:
            ui.lbl(host, "Todavía no hay partidas guardadas. Juega una con LoL abierto y aparecerá aquí.", 11, "dim").pack(anchor="w")
            return
        ids = [g["id"] for g in self.games]
        if self.gid not in ids:
            self.gid = ids[0]
        labels = {f"{fecha(g['t'])} · {ui.champs.get(g['c'], {}).get('name', g['c'])} · {'Victoria' if g['w'] else 'Derrota'}": g["id"]
                  for g in self.games[:15]}
        cur = next((k for k, v in labels.items() if v == self.gid), list(labels)[0])
        bar = ui.frame(host)
        bar.pack(fill="x", pady=(0, 8))
        ui.lbl(bar, "Partida", 10, "dim").pack(side="left", padx=(0, 8))
        ui.menu(bar, list(labels), cur, lambda v: self.pick_game(labels[v]), min(420, self.width - 160)).pack(side="left")
        a = self.data.get(self.gid)
        if a is None:
            self.data[self.gid] = "cargando"
            self.gui.cmds.put(("analysis", int(self.gid)))
            a = "cargando"
        if a == "cargando":
            ui.lbl(host, "Leyendo la línea de tiempo de la partida…", 11, "dim").pack(anchor="w", pady=6)
            return
        if a == "no":
            ui.lbl(host, "El cliente ya no guarda la línea de tiempo de esta partida (solo conserva las más recientes) o LoL está cerrado. "
                         "Prueba con una más reciente.", 11, "dim", anchor="w", justify="left", wraplength=max(260, self.width - 110)).pack(anchor="w", pady=6)
            return
        self.analysis_body(a)

    def pick_game(self, gid):
        self.gid = gid
        self.sig = None
        self.refresh(self.gui.make_ctx())

    def analysis_body(self, a):
        ui, host = self.ui, self.host
        k, d, s = a["kda"]
        kpis = [("Resultado", "Victoria" if a["win"] else "Derrota", "good" if a["win"] else "bad"),
                ("K / D / A", f"{k} / {d} / {s}", "fg"), ("Duración", f"{a['dur'] // 60}:{a['dur'] % 60:02d}", "fg"),
                ("Oro final", f"{a['gold'][-1]:,}".replace(",", "."), "fg")]
        row = ui.frame(host)
        row.pack(fill="x", pady=(0, 8))
        for i, (lb, v, col) in enumerate(kpis):
            c = ctk.CTkFrame(row, fg_color=PAL["card2"], corner_radius=10)
            c.pack(side="left", expand=True, fill="x", padx=(0 if i == 0 else 6, 0))
            ui.lbl(c, lb, 9, "dim").pack(anchor="w", padx=12, pady=(8, 0))
            ui.lbl(c, v, 15, col, True, True).pack(anchor="w", padx=12, pady=(0, 8))
        charts = [c for c in CHARTS if c in ("Oro del equipo", "Súbditos", "Recorrido") or a.get("lane_gold_diff")]
        if self.chart not in charts:
            self.chart = charts[0]
        ui.seg(host, charts, self.chart, self.set_chart, height=28).pack(fill="x", pady=(0, 6))
        self.hover_lbl = ui.lbl(host, "Pasa el ratón por el gráfico para ver cada minuto.", 9, "dim", anchor="w")
        self.hover_lbl.pack(anchor="w")
        W = min(self.width - 90, 860)
        if self.chart == "Recorrido":
            self.draw_path(a, min(W, 420))
        else:
            self.draw_chart(a, W)
        self.legend(a)
        ui.lbl(host, "CONSEJOS DE ESTA PARTIDA", 10, "dim", True, anchor="w").pack(anchor="w", pady=(14, 4))
        for tone, title, detail in analysis.advice(a, ui.champs):
            r = ctk.CTkFrame(host, fg_color=PAL["card2"], corner_radius=10)
            r.pack(fill="x", pady=3)
            inner = ui.frame(r)
            inner.pack(fill="x", padx=12, pady=8)
            ui.lbl(inner, "●", 12, {"good": "good", "bad": "bad"}.get(tone, "info")).pack(side="left", anchor="n", padx=(0, 8))
            col = ui.frame(inner)
            col.pack(side="left", fill="x", expand=True)
            ui.lbl(col, title, 12, "fg", True, anchor="w").pack(anchor="w")
            ui.lbl(col, detail, 10, "dim", anchor="w", justify="left", wraplength=max(240, self.width - 170)).pack(anchor="w")
        ui.lbl(host, "Los consejos salen de restas y umbrales sencillos sobre la línea de tiempo del cliente: cada uno enseña el dato en que se basa.",
               9, "dim", anchor="w", justify="left", wraplength=max(260, self.width - 110)).pack(anchor="w", pady=(8, 0))

    def set_chart(self, v):
        self.chart = v
        self.sig = None
        self.refresh(self.gui.make_ctx())

    def legend(self, a):
        ui = self.ui
        txt = {"Oro del equipo": "Ventaja de oro de tu equipo sobre el rival (arriba = vais por delante).",
               "Oro en tu línea": f"Tu oro menos el de {core.name(a['opp_champ'], ui.champs)} (arriba = vas por delante).",
               "Experiencia": f"Tu experiencia menos la de {core.name(a['opp_champ'], ui.champs)}.",
               "Súbditos": "Tus súbditos (y monstruos de jungla) frente a los de tu rival de línea.",
               "Recorrido": "Tu posición en el mapa al inicio de cada minuto; las bases están en las esquinas abajo-izquierda y arriba-derecha."}[self.chart]
        extra = "  ▲ tus muertes   ◆ objetivos (verde: tuyos, rojo: rivales)" if self.chart != "Recorrido" else ""
        ui.lbl(self.host, txt + extra, 9, "dim", anchor="w", justify="left", wraplength=max(260, self.width - 110)).pack(anchor="w", pady=(2, 0))

    # ---- gráficos ----
    def draw_chart(self, a, W):
        ui = self.ui
        sx = ui.scale_px()
        H, ml, mb, mt, mr = 230, 56, 26, 12, 14
        mins = a["minutes"]
        lines = {"Oro del equipo": [(a["team_gold_diff"], ui.hexm(ui.acc))],
                 "Oro en tu línea": [(a.get("lane_gold_diff") or [], ui.hexm(ui.acc))],
                 "Experiencia": [(a.get("lane_xp_diff") or [], ui.hexm(ui.acc))],
                 "Súbditos": [(a["cs"], ui.hexm(ui.acc)), (a.get("opp_cs") or [], ui.hexm(PAL["dim"]))]}[self.chart]
        vals = [v for s, _ in lines for v in s] or [0]
        diff = self.chart != "Súbditos"
        lo, hi = (min(vals + [0]), max(vals + [0])) if diff else (0, max(vals))
        if diff:
            lo, hi = -nice(max(abs(lo), abs(hi), 1)), nice(max(abs(lo), abs(hi), 1))
        else:
            hi = nice(hi * 1.02)
        x0, x1 = mins[0], max(mins[-1], 1)
        px = lambda m_: ml + (m_ - x0) / (x1 - x0) * (W - ml - mr)
        py = lambda v: mt + (hi - v) / (hi - lo) * (H - mt - mb)
        cv = tk.Canvas(self.host, width=int(W * sx), height=int(H * sx), bg=ui.bg(self.host), highlightthickness=0, bd=0)
        cv.pack(anchor="w", pady=(4, 0))
        S = lambda v: int(v * sx)
        card = ui.hexm(PAL["card2"])
        cv.create_rectangle(S(ml), S(mt), S(W - mr), S(H - mb), fill=card, outline="")
        dim = ui.hexm(PAL["dim"])
        f9 = ui.tkf(9, False, False)
        for i in range(5):  # líneas horizontales y su escala
            v = lo + (hi - lo) * i / 4
            y = S(py(v))
            cv.create_line(S(ml), y, S(W - mr), y, fill=ui.hexm(PAL["border"]))
            cv.create_text(S(ml - 6), y, text=f"{int(round(v)):,}".replace(",", "."), fill=dim, font=f9, anchor="e")
        if diff:
            cv.create_line(S(ml), S(py(0)), S(W - mr), S(py(0)), fill=dim, width=max(1, S(1)))
        step = 5 if x1 <= 40 else 10
        for m_ in range(0, int(x1) + 1, step):
            cv.create_text(S(px(m_)), S(H - mb + 12), text=f"{m_}'", fill=dim, font=f9)
        for s, color in lines:
            pts = [c for i, v in enumerate(s) for c in (S(px(mins[i])), S(py(v)))]
            if len(pts) >= 4:
                cv.create_line(*pts, fill=color, width=max(2, S(2)), smooth=False)
        bad, good = ui.hexm(PAL["bad"]), ui.hexm(PAL["good"])
        for t_ in a["deaths"]:
            x, y = S(px(t_)), S(H - mb)
            cv.create_polygon(x, y - S(9), x - S(5), y, x + S(5), y, fill=bad, outline="")
        for o in a["objectives"]:
            x, y = S(px(o["t"])), S(mt + 8)
            cv.create_polygon(x, y - S(6), x + S(6), y, x, y + S(6), x - S(6), y, fill=good if o["mine"] else bad, outline="")
        guide = {"id": None}
        data = lines[0][0]

        def move(e):
            if guide["id"]:
                for it in guide["id"]:
                    cv.delete(it)
            mx = e.x / sx
            i = min(range(len(mins)), key=lambda k: abs(px(mins[k]) - mx))
            x = S(px(mins[i]))
            ids = [cv.create_line(x, S(mt), x, S(H - mb), fill=dim, dash=(3, 3))]
            guide["id"] = ids
            txt = f"minuto {mins[i]:.0f}: "
            if diff:
                txt += f"{'+' if data[i] >= 0 else '−'}{abs(int(data[i])):,}".replace(",", ".")
            else:
                txt += f"tú {a['cs'][i]} · rival {(a.get('opp_cs') or [0] * len(mins))[i]}"
            self.hover_lbl.configure(text=txt)
        cv.bind("<Motion>", move)

    def draw_path(self, a, W):
        ui = self.ui
        sx = ui.scale_px()
        S = lambda v: int(v * sx)
        cv = tk.Canvas(self.host, width=S(W), height=S(W), bg=ui.hexm(PAL["card2"]), highlightthickness=0, bd=0)
        cv.pack(anchor="w", pady=(4, 0))
        top = 14900.0
        pts = [(p[0], p[1]) for p in a["path"] if p[0] is not None]
        if len(pts) < 2:
            return
        cv.create_line(S(0), S(W), S(W), S(0), fill=ui.hexm(PAL["border"]), dash=(4, 4))  # el río va de esquina a esquina
        cx = lambda x: x / top * (W - 20) + 10
        cy = lambda y: (1 - y / top) * (W - 20) + 10
        xy = [c for x, y in pts for c in (S(cx(x)), S(cy(y)))]
        cv.create_line(*xy, fill=ui.hexm(ui.acc), width=max(2, S(2)))
        f9 = ui.tkf(9, True, False)
        for i, (x, y) in enumerate(pts):
            r = 3
            cv.create_oval(S(cx(x) - r), S(cy(y) - r), S(cx(x) + r), S(cy(y) + r), fill=ui.hexm(ui.acc), outline="")
            if i % 5 == 0:
                cv.create_text(S(cx(x) + 9), S(cy(y) - 9), text=f"{i}'", fill=ui.hexm(PAL["fg"]), font=f9)
        self.hover_lbl.configure(text="Cada punto es un minuto; la cifra marca los minutos 0, 5, 10…")
