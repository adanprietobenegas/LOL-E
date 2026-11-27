"""Pestaña «Partida»: el plan de tu campeón (build, runas, enfrentamiento, consejos) y el análisis de partidas ya jugadas.

«Plan» se queda disponible tras la selección, durante la partida y después: no hay que buscarlo a mano.
«Análisis» usa la línea de tiempo que guarda el propio cliente de LoL: oro, experiencia y súbditos minuto a minuto, muertes,
objetivos y tu recorrido por el mapa, más consejos que dicen de dónde salen (ver analysis.py).
"""
import os
import threading
import time
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
CHARTS = ["Oro del equipo", "Oro vs rival", "Experiencia", "Súbditos", "Ruta en el mapa"]
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
        hidden = getattr(self.gui, "hidden", None)
        if hidden is not None and hidden():   # minimizada: no se reconstruye nada (el PC es del juego); al restaurar se repinta
            self.sig = None
            self.gui._live_pending = True
            return
        self.width = ctx["width"]
        plan = ctx.get("plan") or {}
        sig = (ui.epoch, self.width // 80, self.tab, self.gid, plan.get("cid"), plan.get("opp"), plan.get("state"),
               tuple(plan.get("enemies") or ()), str(self.data.get(self.gid))[:20], self.opp.get(self.gid), self.all_moments, str(self.vs.get((plan.get("opp"), plan.get("role"))))[:20],
               len(ctx.get("roster") or ()), len(ctx.get("roster_pl") or {}), bool(ctx.get("live")))
        if sig == self.sig and not force:
            return
        self.sig = sig
        self.ui.clear(self.box)
        self.goal_until = None   # solo lo vuelve a fijar el plan que se pinte ahora (no vale el de la partida anterior)
        card = ui.card(self.box)
        top = ui.frame(card)
        self.compact = bool(self.tab == "Plan" and plan.get("state") == "game" and plan.get("cid") in ui.champs)   # en partida: cabecera de una fila
        top.pack(fill="x", pady=(0, 8 if self.compact else 12))
        ui.seg(top, TABS, self.tab, self.set_tab, width=150 if self.compact and self.width < 640 else 220, height=28).pack(side="right")   # primero: si falta sitio se recorta el nombre
        if self.compact:   # una sola fila: quién eres y contra quién, con las pestañas a la derecha
            cid, opp = plan["cid"], plan.get("opp") or 0
            ui.champ(top, cid, 32, False, ui.hexm(ui.acc)).pack(side="left", padx=(0, 10))
            line = core.name(cid, ui.champs) + (f" · {ROLES_ES.get(plan.get('role') or '', '').lower()}" if ROLES_ES.get(plan.get("role") or "") else "")
            if opp and opp in ui.champs:
                line += f" · contra {core.name(opp, ui.champs)}"
            if self.width < 640:   # estrecha: sin la línea, para que quepan las pestañas
                line = core.name(cid, ui.champs) + (f" · {core.name(opp, ui.champs)}" if opp and opp in ui.champs else "")
            ui.lbl(top, line, 14, "fg", True, True).pack(side="left")
        else:
            ui.lbl(top, "Tu partida", 16, "fg", True, True).pack(side="left")
        self.host = ui.frame(card)
        self.host.pack(fill="x")
        self.anchors = []
        (self.plan_tab if self.tab == "Plan" else self.analysis_tab)(ctx)
        try:
            self.gui.paint_game_jump(self.anchors if self.compact else [], self.width)
        except Exception:
            core.log_exc("Barra Ir a de la partida")
        shown = (self.tab, self.gid)
        if shown != getattr(self, "_shown", shown):   # otra pestaña u otra partida: se empieza arriba (visto en una partida real: al acabar, la pantalla pasa sola
            try:                                      # a «Análisis» y, si mirabas la parte baja del bloque en vivo, quedaba en blanco: el desplazamiento no existe ya)
                self.gui.body._parent_canvas.yview_moveto(0)
            except Exception:
                core.log_exc("Volver arriba en Partida")
        self._shown = shown

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
    def roster_block(self, ctx, plan):
        """«Jugadores de la partida»: los 10 de la pantalla de carga, cada uno con su rango, su forma reciente, lo que más juega y su maestría
        con el campeón que lleva. Los datos salen del cliente (el de cada jugador, igual que en la selección): no hay clave de Riot."""
        ros, ui = ctx.get("roster"), self.ui
        if not ros:
            return
        kind = (plan or {}).get("kind") or ((ctx.get("r") or {}).get("mode") or {}).get("kind") or "sr"
        import ui_vs
        # ARAM, Arena, personalizadas…: no hay líneas ni rival directo, así que no se usa el tablero enfrentado, pero los jugadores
        # se enseñan igualmente en lista (antes en esos modos no salía ninguno)
        if kind == "sr" and self.width >= ui_vs.MIN_WIDTH:   # con sitio: los 10 a la vez, cada línea frente a su rival; plegable para centrarse en la build
            opp = (plan or {}).get("opp")
            summ = "5 contra 5" + (f" · tu rival: {core.name(opp, ui.champs)}" if opp and opp in ui.champs else "")
            def fill(c):
                try:
                    ui_vs.Board(self).render(c, ctx, plan)
                except Exception:
                    core.log_exc("Tablero de jugadores")
                    ui.lbl(c, "No se pudo dibujar el tablero de jugadores. El motivo queda en Ajustes › «Abrir el registro de errores».", 10, "dim").pack(anchor="w")
            live = (plan or {}).get("state") == "game"   # en partida sale cerrado (primero tu build); fuera de ella, como lo dejaste
            ui.reg("partida.jugadores", ui_vs.collapsible(ui, self.host, "Jugadores de la partida", summ, "game_roster_live" if live else "game_roster", fill, not live))
            return
        from ui_sections import Lobby
        pl, r = ctx.get("roster_pl") or {}, ctx.get("r") or {}
        party, mates, qid = set(r.get("party") or ()), r.get("mates") or {}, (plan or {}).get("qid") or 0
        mine = next((x for x in ros if x["me"]), None)
        my_role = (plan or {}).get("role") or (mine or {}).get("role") or ""
        opp = (plan or {}).get("opp") or 0
        n_load = len([x for x in ros if x["puuid"]])
        ui.lbl(self.host, "JUGADORES DE LA PARTIDA", 10, "dim", True, anchor="w").pack(anchor="w", pady=(2, 4))
        if n_load and len(pl) < n_load:
            ui.lbl(self.host, f"Leyendo perfiles… {len(pl)} de {n_load}", 10, "dim", anchor="w").pack(anchor="w", pady=(0, 4))
        for team, title, ring in (("ally", "TU EQUIPO", "#3ddc84"), ("enemy", "EQUIPO RIVAL", "#ff5a5f")):
            grp = [x for x in ros if x["team"] == team]
            if not grp:
                continue
            ui.lbl(self.host, title, 9, "dim", True, anchor="w").pack(anchor="w", pady=(8, 0))
            for x in grp:
                a = {"champ": x["cid"], "role": x["role"], "puuid": x["puuid"]}
                tag = "Tu rival de línea" if kind == "sr" and team == "enemy" and my_role and x["role"] == my_role and (not opp or x["cid"] == opp) else None
                if x["me"]:
                    tag = "Tú"
                Lobby.row(self, self.host, a, pl.get(x["puuid"]) if x["puuid"] else None, x["puuid"] in party, len(party),
                          False, mates.get(x["puuid"]), ring, qid, tag)
        ui.lbl(self.host, "Rango y partidas recientes salen del cliente de cada jugador. Un rango oculto o sin partidas se marca como tal.", 9, "dim",
               anchor="w", justify="left", wraplength=max(260, self.width - 110)).pack(anchor="w", pady=(8, 12))

    def on_live(self, ctx):
        """Llegó un resumen nuevo de la partida en vivo: se ACTUALIZA en sitio la vista que ya existe (solo cambia lo que ha cambiado; repintar
        la pestaña entera cuesta más de un segundo y parpadeaba). La primera vez, o si no se está en el plan, se hace el refresco completo."""
        view = getattr(self, "live_view", None)
        try:
            if self.tab != "Plan":
                return   # se está mirando otra pestaña (p. ej. el análisis de la anterior): al volver a «Plan» el refresco ya trae el resumen más nuevo
            expired = bool(getattr(self, "goal_until", None)) and (ctx.get("live") or {}).get("t", 0) >= self.goal_until
            if view is not None and view.alive() and ctx.get("live") and not expired:
                view.update(ctx["live"], (ctx.get("plan") or {}).get("opp") or 0, ctx.get("plan"))
                return
        except Exception:
            core.log_exc("Vista en vivo")
        self.sig = None
        self.refresh(ctx, True)

    def live_block(self, ctx):
        """La tira compacta de «en vivo» (arriba). El pliegue con los diez jugadores se crea aquí pero se coloca más abajo (`place_live_detail`),
        debajo de tu build y tus runas, que son lo que se consulta durante la partida."""
        self.live_view = self.live_detail = None
        if not ctx.get("live") or (ctx.get("plan") or {}).get("state") == "done":   # terminada: el marcador, la compra y los temporizadores ya no sirven
            return
        try:
            import ui_live
            strip = self.ui.frame(self.host)
            strip.pack(fill="x", pady=(0, 8))
            self.live_detail = self.ui.frame(self.host)
            self.live_view = ui_live.LiveView(self.ui, strip, self.live_detail, self.width, compact=(ctx.get("plan") or {}).get("state") == "game")
            self.live_view.update(ctx["live"], (ctx.get("plan") or {}).get("opp") or 0, ctx.get("plan"))
        except Exception:
            core.log_exc("Bloque en vivo")
            self.live_view = self.live_detail = None

    def place_live_detail(self):
        if getattr(self, "live_detail", None) is not None:
            self.live_detail.pack(fill="x", pady=(0, 8))

    def goal_text(self, plan, now=0):
        """El objetivo de la partida a partir del patrón repetido de tus derrotas; solo en la Grieta. En partida (`now`: segundos de juego) desaparece al
        pasar su minuto límite. Deja en `goal_until` cuándo habrá que quitarlo."""
        self.goal_until = None
        if (plan.get("kind") or "sr") != "sr":
            return None
        try:
            import patrones
            p = patrones.current(core.CACHE)
            until = patrones.until(p)
            if plan.get("state") == "game" and until:
                if now >= until:
                    return None
                self.goal_until = until
            return patrones.goal(p)
        except Exception:
            return None

    def plan_tab(self, ctx):
        ui, host = self.ui, self.host
        plan = ctx.get("plan")
        self.live_block(ctx)
        import ui_vs
        has_plan = bool(plan) and plan["cid"] in ui.champs
        # ventana estrecha: la lista de 10 jugadores ocupa tres pantallas, así que con plan va al final (primero tu build y tu rival);
        # en ancho es un tablero plegable y se queda arriba
        late = has_plan and bool(ctx.get("roster")) and (self.width < ui_vs.MIN_WIDTH or (plan.get("kind") or "sr") != "sr")
        if not has_plan:
            self.place_live_detail()
            self.roster_block(ctx, plan)
            if ctx.get("roster"):
                return
            ui.lbl(host, "Cuando elijas campeón en una selección, aquí tendrás su build, sus runas, el enfrentamiento y consejos, "
                         "también durante la partida y después.", 11, "dim", anchor="w", justify="left",
                   wraplength=max(260, self.width - 110)).pack(anchor="w", pady=8)
            return
        cid, opp, role = plan["cid"], plan.get("opp") or 0, plan.get("role") or ""
        lane = LANE_OF.get(role)
        if getattr(self, "compact", False):   # la cabecera ya lo dice todo en una fila
            txt = ui.frame(host)
            txt.pack(fill="x")
        else:
            head = ui.frame(host)
            head.pack(fill="x", pady=(0, 8))
            ui.champ(head, cid, 56, False, ui.hexm(ui.acc)).pack(side="left", padx=(0, 12))
            txt = ui.frame(head)
            txt.pack(side="left")
            ui.lbl(txt, STATE.get(plan.get("state"), "").upper() + (("  ·  bloqueado" if plan.get("locked") else "  ·  sin confirmar") if plan.get("state") == "select" else ""),
                   9, "dim", True).pack(anchor="w")
            ui.lbl(txt, core.name(cid, ui.champs), 20, "fg", True, True).pack(anchor="w")
            sub = ROLES_ES.get(role, "").lower()
            if opp and opp in ui.champs:
                sub += f"  ·  contra {core.name(opp, ui.champs)}"
            ui.lbl(txt, sub or "sin línea asignada", 10, "dim").pack(anchor="w")
        try:   # tocado en las últimas notas del parche (solo lo ya guardado)
            import ui_patch
            chip = ui_patch.patch_chip(ui, txt, cid)
            if chip is not None:
                chip.pack(anchor="w", pady=(2, 0))
        except Exception:
            core.log_exc("Aviso de parche en Partida")
        if plan.get("kind") in (None, "sr") and plan.get("enemies") and plan.get("state") == "game":
            from ui_sections import comp_line
            line = comp_line(core.comp_stats(plan.get("enemies") or [], ui.champs, True))
            if line:
                ui.lbl(host, f"Rivales: {line}", 11, "dim", anchor="w", justify="left", wraplength=max(240, self.width - 110)).pack(anchor="w", pady=(0, 6))
        goal = self.goal_text(plan, (ctx.get("live") or {}).get("t", 0)) if plan.get("state") in ("select", "game") else None
        if goal:   # un solo objetivo medible, sacado de lo que te pasa en tus derrotas
            ui.reg("partida.objetivo", ui.lbl(host, goal, 11, "warn", True, anchor="w", justify="left", wraplength=max(240, self.width - 110))).pack(anchor="w", pady=(0, 8))
        go_roster = None
        if late:   # enlace que baja hasta ellos: al final de una pantalla larga había quien no los encontraba
            go_roster = ui.lbl(txt, "▾ Ver los jugadores de la partida (al final)", 10, "info", True)
            go_roster.pack(anchor="w", pady=(2, 0))
        if plan.get("mayhem") or (plan.get("kind") == "aram" and plan.get("qid") == 450):
            self.mark("Build")   # ARAM y Mayhem no tienen línea: su build también tiene atajo
        if plan.get("mayhem"):
            import ui_mayhem
            self.load_games()
            ui_mayhem.plan_block(ui, host, plan, ctx, self.games, self.width)
            ui_mayhem.build_block(ui, host, plan["cid"], plan.get("qid") or 2400, self.width)
        elif plan.get("kind") == "aram" and plan.get("qid") == 450:
            import ui_mayhem
            ui_mayhem.build_block(ui, host, plan["cid"], 450, self.width)
        elif plan.get("kind") not in (None, "sr"):
            ui.lbl(host, f"En {plan.get('group') or 'este modo'} no hay plan de línea ni build recomendada. Cuando termine la partida, la pestaña Análisis te la cuenta.",
                   11, "dim", anchor="w", justify="left", wraplength=max(260, self.width - 110)).pack(anchor="w", pady=(8, 0))
        if lane:
            self.ui.lbl(self.host, "", 4, "dim").pack()
            self.mark("Build")
            build_panel(ui, host, cid, lane, opp or None, self.width - 110,
                        core.comp_stats(plan.get("enemies") or [], ui.champs, True), in_game=plan.get("state") == "game",
                        export=plan.get("state") != "done").pack(fill="x")   # al acabar la partida ya no hay nada que enviar
        if lane and plan.get("kind") in (None, "sr") and plan.get("enemies"):
            import ui_opp
            if plan.get("state") == "game":   # en partida el rival ya está claro: el selector queda plegado, con el rival actual como resumen
                def fill_opp(c):
                    pk_ = ui_opp.picker(ui, c, cid, lane, plan["enemies"], plan.get("opp_auto") or 0, ui.opp_now(), ui.set_opp, self.width - 130)
                    if pk_ is not None:
                        pk_.pack(fill="x", pady=(4, 8))
                ui.reg("partida.rival", ui.fold(host, "Rival de línea", fill_opp, ("contra " + core.name(opp, ui.champs)) if opp and opp in ui.champs else "automático", "game_opp", False, padx=0))
            else:
                pk = ui_opp.picker(ui, host, cid, lane, plan["enemies"], plan.get("opp_auto") or 0, ui.opp_now(), ui.set_opp, self.width - 110)
                if pk is not None:
                    pk.pack(fill="x", pady=(0, 8))
                    ui.reg("partida.rival", pk)
        # tras tu build y tus runas (lo que se consulta durante la partida): los diez jugadores en directo, el tablero y las claves
        if getattr(self, "live_detail", None) is not None:
            self.mark("Los 10")
        self.place_live_detail()
        if not late:
            if ctx.get("roster"):
                self.mark("Jugadores")
            self.roster_block(ctx, plan)
        import ui_claves
        import claves
        if claves.for_champ((ui.champs.get(cid) or {}).get("icon")):
            self.mark("Claves")
        ui_claves.block(ui, host, cid, self.width - 110, in_game=plan.get("state") == "game")   # claves del campeón (evoluciones, acumulaciones, formas…) en cualquier modo
        if plan.get("opp") and lane:
            self.mark("Enfrentamiento")
        self.matchup_block(plan, lane)
        if lane and plan.get("kind") in (None, "sr"):
            import ui_guide
            ui_guide.guide_block(ui, host, cid, opp or None, lane, self.width, in_game=plan.get("state") == "game")
        if plan.get("kind") in (None, "sr"):
            self.mark("Consejos")
            self.tips_block(plan, role)
        if late:
            self.mark("Jugadores")
            mark = self.ui.lbl(self.host, "", 4, "dim")
            mark.pack()
            self.roster_block(ctx, plan)

            def jump(_e=None):
                try:
                    cv = self.gui.body._parent_canvas
                    self.gui.root.update_idletasks()
                    total = max(1, (cv.bbox("all") or (0, 0, 0, 1))[3])
                    y = mark.winfo_rooty() - cv.winfo_rooty() + cv.canvasy(0)
                    cv.yview_moveto(max(0.0, min(1.0, y / total)))
                except Exception:
                    core.log_exc("Bajar a los jugadores")
            go_roster.configure(cursor="hand2")
            go_roster.bind("<Button-1>", jump)
            self.jump_roster = jump

    def mark(self, name):
        """Marca invisible donde empieza un bloque, para la barra «Ir a» (solo durante la partida)."""
        if getattr(self, "compact", False):
            m = tk.Frame(self.host, width=1, height=1, bg=self.ui.bg(self.host))
            m.pack(anchor="w")
            self.anchors.append((name, m))

    def section(self, title):
        self.ui.lbl(self.host, title, 10, "dim", True, anchor="w").pack(anchor="w", pady=(16, 4))

    def matchup_block(self, plan, lane):
        ui = self.ui
        cid, opp = plan["cid"], plan.get("opp") or 0
        if not opp or not lane or opp not in ui.champs:
            return
        self.section("TU ENFRENTAMIENTO")
        from ui_sections import rival_lines
        rival_lines(ui, self.host, opp, plan.get("role"), cid, self.width - 110)
        key = (opp, plan.get("role"))
        st = self.vs.get(key)
        if isinstance(st, tuple) and time.time() - st[2] > 90:
            st = None   # un fallo puntual (sin red, Lolalytics caído) se reintenta solo
        if st is None:
            self.vs[key] = "cargando"

            def go():
                try:
                    rows = matchups.best_against(ui.champs, opp, lane, core.CACHE, min_games=20)
                except Exception as e:
                    rows = ("error", str(e), time.time())
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
        moe = 98 / max(1, mine["games"]) ** 0.5   # margen de error (95 %) en puntos: con 20 partidas es ±22, con 1.000 ±3
        fav, des = wr - moe > 50, wr + moe < 50
        verdict = "favorable" if fav else "desfavorable" if des else "igualado" if mine["games"] >= 100 else "aún sin datos suficientes para saber si es favorable"
        col = "good" if fav else "bad" if des else "fg"
        row = ui.frame(self.host)
        row.pack(anchor="w")
        ui.lbl(row, f"{wr:.1f} %".replace(".", ","), 22, col, True, True).pack(side="left")
        ui.lbl(self.host, f"de victorias de {core.name(cid, ui.champs)} contra {core.name(opp, ui.champs)} en tu línea: enfrentamiento {verdict}",
               11, "dim", anchor="w", justify="left", wraplength=max(240, self.width - 110)).pack(anchor="w")
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
            tips.append(("Ruta en el mapa", "Ninguna fuente pública fiable da recorridos de jungla por campeón. Al acabar la partida, en «Análisis → Ruta en el mapa» "
                                      "ves por dónde fuiste tú, minuto a minuto, para compararlo con lo que querías hacer."))
        if not tips:
            return
        self.section("CONSEJOS")
        for title, text in tips:
            row = ui.frame(self.host)
            row.pack(fill="x", pady=2)
            ui.lbl(row, title.upper(), 9, "dim", True, width=96, anchor="w").pack(side="left", anchor="n", pady=(4, 0))
            ui.lbl(row, text, 11, "fg", anchor="w", justify="left", wraplength=max(240, self.width - 190)).pack(side="left", fill="x", expand=True)
        ui.lbl(self.host, "Orientativo: sale de tus campeones y de la composición rival; no sustituye a la build del parche.", 9, "dim",
               anchor="w").pack(anchor="w", pady=(8, 0))

    # ---- análisis (el dibujo vive en ui_analysis.py) ----
    def load_games(self):
        try:
            self.games = history.load_all(history.hpath(core.CACHE), history.gpath(core.CACHE))[:30]
        except Exception:
            self.games = []
        # al terminar una partida nueva se muestra esa, no la que se estaba mirando (antes seguía la anterior)
        newest = self.games[0]["id"] if self.games else None
        if newest != getattr(self, "newest", None):
            if getattr(self, "newest", None) is not None and newest is not None:
                self.gid, self.auto_try = newest, 0
            self.newest = newest

    def analysis_tab(self, ctx):
        self.an.render(self.host, ctx)

    def pick_game(self, gid):
        self.auto_try = 99  # si el usuario elige a mano, no se salta a otra partida
        self.gid = gid
        self.sig = None
        self.refresh(self.gui.make_ctx())

    def set_chart(self, v):
        self.chart = v
        if not (self.tab == "Análisis" and self.an.rerender("charts", v)):
            self.sig = None
            self.refresh(self.gui.make_ctx())

    def toggle_moments(self):
        self.all_moments = not self.all_moments
        self.sig = None
        self.refresh(self.gui.make_ctx())
