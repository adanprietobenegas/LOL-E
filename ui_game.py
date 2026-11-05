"""Pestaña «Partida»: el plan de tu campeón (build, runas, enfrentamiento, consejos) y el análisis de partidas ya jugadas.

«Plan» se queda disponible tras la selección, durante la partida y después: no hay que buscarlo a mano.
«Análisis» usa la línea de tiempo que guarda el propio cliente de LoL: oro, experiencia y súbditos minuto a minuto, muertes,
objetivos y tu recorrido por el mapa, más consejos que dicen de dónde salen (ver analysis.py).
"""
import os
import threading
import tkinter as tk

import customtkinter as ctk

import history
import lol_advisor as core
import matchups
from ui_analysis import AnalysisView
from ui_build import build_panel
from ui_history import fecha, mode_of
from ui_kit import PAL, ROLES_ES
from ui_views import small_btn

TABS = ["Plan", "Análisis"]
CHARTS = ["Oro del equipo", "Oro vs rival", "Experiencia", "Súbditos", "Recorrido"]
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
        self.auto_try = 0
        self.opp, self.all_moments = {}, False   # rival elegido por partida; lista de momentos completa o resumida
        self.an = AnalysisView(ui, gui, self)

    # ---- ciclo de vida ----
    def refresh(self, ctx, force=False):
        ui = self.ui
        self.width = ctx["width"]
        plan = ctx.get("plan") or {}
        sig = (ui.epoch, self.width // 80, self.tab, self.chart, self.gid, plan.get("cid"), plan.get("opp"), plan.get("state"),
               tuple(plan.get("enemies") or ()), str(self.data.get(self.gid))[:20], self.opp.get(self.gid), self.all_moments, str(self.vs.get((plan.get("opp"), plan.get("role"))))[:20])
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
        if not data and gid == self.gid and self.auto_try < 4:  # esa partida ya no tiene línea de tiempo: se prueba con la siguiente
            ids = [g["id"] for g in self.games]
            if gid in ids and ids.index(gid) + 1 < len(ids):
                self.auto_try += 1
                self.gid = ids[ids.index(gid) + 1]
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
            build_panel(ui, host, cid, lane, opp or None, self.width - 110,
                        core.comp_stats(plan.get("enemies") or [], ui.champs, True)).pack(fill="x")
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

    # ---- análisis (el dibujo vive en ui_analysis.py) ----
    def load_games(self):
        try:
            self.games = history.load_all(os.path.join(core.CACHE, "history.json"), os.path.join(core.CACHE, "games.json"))[:30]
        except Exception:
            self.games = []

    def analysis_tab(self, ctx):
        self.an.render(self.host, ctx)

    def pick_game(self, gid):
        self.auto_try = 99  # si el usuario elige a mano, no se salta a otra partida
        self.gid = gid
        self.sig = None
        self.refresh(self.gui.make_ctx())

    def set_chart(self, v):
        self.chart = v
        self.sig = None
        self.refresh(self.gui.make_ctx())

    def toggle_moments(self):
        self.all_moments = not self.all_moments
        self.sig = None
        self.refresh(self.gui.make_ctx())
