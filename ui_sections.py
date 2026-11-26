"""Secciones independientes de la ventana de LOL-E.

Cada sección calcula una clave con los datos que usa; si la clave no cambia, no se toca. Así, cuando llega
un dato nuevo (un aliado que elige, un jugador que carga…) solo se repinta su parte y no toda la pantalla.
"""
import json, os, threading, time, tkinter as tk, re

import ayuda
from collections import Counter

import customtkinter as ctk
from PIL import Image

import history
import lpseries
import lol_advisor as core
from players import TIERS_ES
from ui_build import build_panel
from ui_pool import PoolPanel
from lol_advisor import name
import matchups
from ui_kit import PAL, TIER_COLORS, ROLES_ES, PHASES, ON_FILL, REC_VIEWS, ctl, col, hexc, partidas, pct_es
from ui_history import fecha as history_fecha_full, mode_of
from ui_views import breakdown_rows, mini_bar, open_url, small_btn


class Section:
    def __init__(self, ui, parent):
        self.ui = ui
        self.box = ui.frame(parent)
        self.box.pack(fill="x")
        self.sig = None

    def refresh(self, ctx, force=False):
        sig = (self.key(ctx), self.ui.epoch)
        if sig == self.sig and not force:
            return False
        self.sig = sig
        self.ui.clear(self.box)
        self.build(ctx)
        if not self.box.winfo_children():
            self.box.configure(height=1)  # un contenedor vacío de Tk conserva su último tamaño: se colapsa a mano
        return True

    def key(self, ctx):
        raise NotImplementedError

    def build(self, ctx):
        raise NotImplementedError


# ------------------------------------------------------------------ pantalla de espera
def rank_block(ui, parent, title, rk):
    box = ctk.CTkFrame(parent, fg_color=PAL["card2"], corner_radius=12)
    inner = ui.frame(box)
    inner.pack(fill="x", padx=12, pady=12)
    ui.lbl(inner, title.upper(), 9, "dim", True).pack(anchor="w")
    row = ui.frame(inner)
    row.pack(anchor="w", pady=(4, 0))
    if rk:
        em = ui.emblem(rk["key"], 44)
        if em:
            ctk.CTkLabel(row, image=em, text="").pack(side="left", padx=(0, 12))
        txt = ui.frame(row)
        txt.pack(side="left")
        ui.lbl(txt, f"{rk['tier']} {rk['div']}".strip(), 15, TIER_COLORS.get(rk["key"], "fg"), True, True).pack(anchor="w")
        ui.lbl(txt, f"{rk['lp']} PL  ·  {rk['w']}V {rk['l']}D  ·  {rk['wr'] * 100:.0f} %", 10, "dim", anchor="w", wraplength=170,
               justify="left").pack(anchor="w")
    else:
        ui.lbl(row, "Sin clasificar", 13, "dim", True).pack(anchor="w", pady=12)
    return box


class ProfileCard(Section):
    def key(self, ctx):
        i = ctx["info"] or {}
        return (json.dumps(i.get("profile"), sort_keys=True, default=str), tuple(i.get("form", [])), i.get("games"))

    def build(self, ctx):
        ui = self.ui
        info = ctx["info"] or {}
        pr = info.get("profile") or {}
        c = ui.card(self.box)
        ui.reg("inicio.perfil", c)
        top = ui.frame(c)
        top.pack(fill="x")
        img = ui.profile_icon(pr["icon"], 56) if pr.get("icon") else None
        if img:
            ctk.CTkLabel(top, image=img, text="").pack(side="left", padx=(0, 16))
        mid = ui.frame(top)
        mid.pack(side="left")
        ui.lbl(mid, pr.get("name") or "Invocador", 20, "fg", True, True).pack(anchor="w")
        sub = f"#{pr['tag']}   ·   Nivel {pr['level']}" if pr.get("tag") else ""
        ui.lbl(mid, sub, 11, "dim").pack(anchor="w")
        right = ui.frame(top)
        right.pack(side="right", anchor="n")
        ui.lbl(right, "ÚLTIMAS 5 PARTIDAS", 9, "dim", True).pack(anchor="e")
        row = ui.frame(right)
        row.pack(anchor="e", pady=(4, 0))
        for w in info.get("form") or []:
            ctk.CTkLabel(row, text="V" if w else "D", width=26, height=24, corner_radius=7, font=ui.font(11, True, True),
                         fg_color=PAL["good" if w else "bad"], text_color=ON_FILL).pack(side="left", padx=2)
        if not info.get("form"):
            ui.lbl(row, "—", 12, "dim").pack()
        if info.get("form") and info["form"][-3:] == [False] * 3:
            ui.lbl(right, "Llevas 3 derrotas seguidas", 10, "warn", True).pack(anchor="e", pady=(4, 0))
        grid = ui.frame(c)
        grid.pack(fill="x", pady=(12, 0))
        for k in range(2):
            grid.columnconfigure(k, weight=1, uniform="rk")
        rank_block(ui, grid, "Solo / Dúo", pr.get("solo")).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        rank_block(ui, grid, "Flexible", pr.get("flex")).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        if pr.get("prem"):
            rank_block(ui, grid, "Clasificatorias de 5", pr["prem"]).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))


class TourOffer(Section):
    """Una tarjeta pequeña, una sola vez, para quien acaba de instalar la app (sin historial guardado): ofrece el recorrido guiado de la demostración. «Ahora no» no vuelve a preguntar
    (el botón «?» de la cabecera siempre lleva a la guía). Nunca sale en la propia demostración ni con partidas ya guardadas."""

    def wanted(self):
        try:
            if self.ui.conf.get("tour_offered") or getattr(core, "DEMO_MODE", False):
                return False
            return bool(self.ui.conf.get("tour_pending")) or not history.load_all(history.hpath(core.CACHE), history.gpath(core.CACHE))
        except Exception:
            return False

    def key(self, ctx):
        return self.wanted()

    def build(self, ctx):
        if not self.wanted():
            return
        ui = self.ui
        c = ui.card(self.box, pad=4)
        ui.lbl(c, "¿Primera vez en LOL-E?", 15, "fg", True, True).pack(anchor="w")
        ui.autowrap(ui.lbl(c, "Te enseño la app en 3 o 4 minutos con una demostración: datos de ejemplo, todo lo que verás al buscar partida, elegir campeón, jugar y revisar. "
                              "No toca tus datos.", 11, "dim", anchor="w", justify="left"), c).pack(anchor="w", pady=(4, 8))
        row = ui.frame(c)
        row.pack(anchor="w")

        def done(launch):
            ui.conf["tour_offered"] = True
            core.save_conf(ui.conf)
            if launch:
                ui.launch_demo()
            self.refresh(ctx, force=True)
        ctk.CTkButton(row, text="Ver el recorrido guiado", height=34, corner_radius=10, font=ui.font(12, True), fg_color=ui.acc, text_color=PAL["bg"], hover_color=ui.acc,
                      command=lambda: done(True)).pack(side="left")
        ctk.CTkButton(row, text="Ahora no", height=34, corner_radius=10, font=ui.font(12), fg_color=PAL["card2"], text_color=PAL["fg"], hover_color=PAL["border"],
                      command=lambda: done(False)).pack(side="left", padx=(8, 0))


def ago_text(t_ms, now=None):
    """«hace 5 min», «hace 3 h», «ayer», «hace 4 días» a partir de la hora de inicio de una partida (milisegundos)."""
    if not t_ms:
        return ""
    s = max(0, (now if now is not None else time.time()) - t_ms / 1000)
    if s < 3600:
        return f"hace {max(1, int(s // 60))} min"
    if s < 86400:
        return f"hace {int(s // 3600)} h"
    d = int(s // 86400)
    return "ayer" if d == 1 else f"hace {d} días"


class WaitCard(Section):
    def tilt(self):
        """Aviso de sesión (2+ derrotas seguidas) con tu propio dato, para antes de entrar en otra cola; None si no toca."""
        try:
            import sesion
            games = history.load_all(history.hpath(core.CACHE), history.gpath(core.CACHE))
            return sesion.tilt_note(sesion.current(games, int(time.time() * 1000)), sesion.after_losses(games))
        except Exception:
            return None

    def last_game(self):
        """(partida, PL ganados o perdidos | None, objetivo | None) de lo último que jugaste, o None. Solo lee lo que ya está guardado."""
        try:
            games = history.load_all(history.hpath(core.CACHE), history.gpath(core.CACHE))
            e = next((g for g in games if not g.get("rm") and g.get("t")), None)
            if e is None:
                return None
            import analysis
            lp = analysis.lp_for(core.CACHE, e.get("id"))
            goal = None
            try:
                import patrones
                goal = patrones.goal(patrones.current(core.CACHE))
            except Exception:
                pass
            return e, (lp or {}).get("d"), goal
        except Exception:
            core.log_exc("Tu última partida")
            return None

    def key(self, ctx):
        last = self.last_game()
        return (ctx["msg"], ctx["linked"], self.tilt(), last and (last[0].get("id"), last[1], last[2], ago_text(last[0].get("t", 0))))

    def draw_last(self, ctx):
        last = self.last_game()
        if last is None:
            return
        ui, (e, lp, goal) = self.ui, last
        c = ui.card(self.box, "Tu última partida")
        row = ui.frame(c)
        row.pack(fill="x")
        if e.get("c") in ui.champs:
            ui.champ(row, e["c"], 44, False, "#3ddc84" if e.get("w") else "#ff5a5f").pack(side="left", padx=(0, 12))
        if e.get("id") is not None:
            ctk.CTkButton(row, text="Ver análisis", width=110, height=30, corner_radius=10, font=ui.font(11, True), fg_color=PAL["card2"], text_color=PAL["fg"],
                          hover_color=PAL["border"], command=lambda g=str(e["id"]): ui.open_analysis(g)).pack(side="right")
        mid = ui.frame(row)
        mid.pack(side="left", fill="x", expand=True)
        title = "Victoria" if e.get("w") else "Derrota"
        if lp is not None:
            title += f"  ·  {'+' if lp > 0 else '−' if lp < 0 else '±'}{abs(lp)} PL"
        ui.lbl(mid, title, 15, "good" if e.get("w") else "bad", True, True).pack(anchor="w")
        bits = [name(e["c"], ui.champs) if e.get("c") in ui.champs else "", mode_of(e)]
        if e.get("k") is not None:
            bits.append(f"{e['k']} / {e['de']} / {e['a']}")
        bits.append(ago_text(e.get("t", 0)))
        ui.lbl(mid, "  ·  ".join(x for x in bits if x), 10, "dim", anchor="w").pack(anchor="w")
        if goal:
            ui.autowrap(ui.lbl(c, goal, 11, "warn", True, anchor="w", justify="left"), c).pack(anchor="w", pady=(8, 0))

    def build(self, ctx):
        ui = self.ui
        c = ui.card(self.box, pad=4)
        row = ui.frame(c)
        row.pack(fill="x")
        ui.lbl(row, "●", 12, "good" if ctx["linked"] else "warn").pack(side="left", padx=(0, 8))
        # el título dice lo que toca hacer ahora; la pista va debajo, en su propia línea (al lado se montaba sobre el título en ventanas estrechas)
        ui.lbl(row, "Esperando la selección de campeón" if ctx["linked"] else "Abre League of Legends", 13, "fg", True, True).pack(side="left")
        hint = ("Entra en una cola: esta ventana se activa sola al empezar la selección." if ctx["linked"]
                else "Después entra en una cola: esta ventana se activa sola al empezar la selección.")
        ui.autowrap(ui.lbl(c, hint, 10, "dim", anchor="w", justify="left"), c).pack(anchor="w", pady=(4, 0))
        note = self.tilt()
        if note and ctx["linked"]:
            lab = ui.autowrap(ui.lbl(c, note, 10, "warn", True, anchor="w", justify="left"), c)
            lab.pack(anchor="w", pady=(8, 0))
            ui.reg("inicio.sesion", lab)
        msg = ctx["msg"] or ""
        if msg and not any(s in msg for s in ("Conectado al cliente", "Abre el cliente", "Esperando al cliente")):
            ui.autowrap(ui.lbl(c, msg, 10, "dim", anchor="w", justify="left"), c).pack(anchor="w", pady=(2, 0))
        self.draw_last(ctx)


class ModesCard(Section):
    def key(self, ctx):
        return json.dumps((ctx["info"] or {}).get("modes"), default=str)

    def build(self, ctx):
        ui = self.ui
        modes = (ctx["info"] or {}).get("modes") or []
        if not modes:
            return
        c = ui.card(self.box, "Tus modos de juego")
        for m in modes:
            row = ui.frame(c)
            row.pack(fill="x", pady=4)
            wr = m["wins"] / m["games"]
            ui.lbl(row, m["name"], 12, "fg", True, True, width=92, anchor="w").pack(side="left")
            ui.lbl(row, partidas(m["games"]), 10, "dim", width=76, anchor="w").pack(side="left")
            ui.lbl(row, f"{wr * 100:.0f} %", 13, "good" if wr >= .5 else "bad", True, True, width=44).pack(side="left")
            ui.dots(row, m["last"]).pack(side="right")


class AchievementsCard(Section):
    """Rango y logros: lo que el cliente sabe de ti (rango máximo, retos y su percentil, maestría, honor) y tus rachas guardadas."""
    CATS = {"COLLECTION": "Colección", "TEAMWORK": "Trabajo en equipo", "EXPERTISE": "Pericia", "VETERANCY": "Veteranía",
            "IMAGINATION": "Imaginación"}

    def streaks(self):
        try:
            games = [e for e in history.load_all(history.hpath(core.CACHE), history.gpath(core.CACHE))
                     if not e.get("rm")]
        except Exception:
            return None
        if not games:
            return None
        cur, n = games[0]["w"], 0
        for e in games:
            if e["w"] != cur:
                break
            n += 1
        best = run = 0
        for e in reversed(games):
            run = run + 1 if e["w"] else 0
            best = max(best, run)
        return {"cur_win": cur, "cur": n, "best": best, "n": len(games)}

    def key(self, ctx):
        ex = ((ctx["info"] or {}).get("profile") or {}).get("extra")
        st = self.streaks()
        return (json.dumps(ex, sort_keys=True, default=str), json.dumps(st, sort_keys=True), ctx["width"] // 300)

    def tile(self, grid, i, cols, label, value, sub="", color="fg", span=1):
        ui = self.ui
        cell = ctk.CTkFrame(grid, fg_color=PAL["card2"], corner_radius=12)
        cell.grid(row=i // cols, column=i % cols, columnspan=span, sticky="nsew", padx=4, pady=4)
        inner = ui.frame(cell)
        inner.pack(fill="x", padx=12, pady=12)
        wl = getattr(self, "tile_wl", 200)
        ui.lbl(inner, label.upper(), 9, "dim", True, anchor="w", wraplength=wl, justify="left").pack(anchor="w")
        ui.lbl(inner, value, 15, color, True, True, anchor="w", wraplength=wl, justify="left").pack(anchor="w", pady=(4, 0))
        if sub:
            ui.lbl(inner, sub, 10, "dim", anchor="w", wraplength=wl, justify="left").pack(anchor="w")

    def build(self, ctx):
        ui = self.ui
        pr = (ctx["info"] or {}).get("profile") or {}
        ex = pr.get("extra") or {}
        st = self.streaks()
        es = lambda x: f"{x:.1f}".replace(".", ",")
        miles = lambda n: f"{int(n):,}".replace(",", ".")
        tiles = []
        if ex.get("peak"):
            p = ex["peak"]
            tiles.append(("Mejor rango de la temporada", f"{p['tier']} {p['div']}".strip(), "tu punto más alto este año",
                          TIER_COLORS.get(p["key"], "fg")))
        if ex.get("prev"):
            p = ex["prev"]
            tiles.append(("Temporada anterior", f"{p['tier']} {p['div']}".strip(), "rango con el que acabaste",
                          TIER_COLORS.get(p["key"], "fg")))
        ch = ex.get("challenges")
        if ch:
            lv = TIERS_ES.get(ch["level"], ch["level"].title())
            sub = (f"Entre el {es(ch['pct'])} % mejor · " if ch.get("pct") is not None else "") + f"{miles(ch['points'])} puntos"
            tiles.append(("Retos", lv, sub, TIER_COLORS.get(ch["level"], "fg")))
            cats = [c for c in ch.get("cats", []) if c.get("pct") is not None]
            if cats:
                b = min(cats, key=lambda c: c["pct"])
                tiles.append(("Tu mejor categoría de retos", self.CATS.get(b["cat"], b["cat"].title()),
                              f"{TIERS_ES.get(b['level'], b['level'].title())} · entre el {es(b['pct'])} % mejor",
                              TIER_COLORS.get(b["level"], "fg")))
        if ex.get("mastery_score"):
            tiles.append(("Maestría total", miles(ex["mastery_score"]), "suma de los niveles de todos tus campeones", "fg"))
        if ex.get("honor") is not None:
            tiles.append(("Nivel de honor", str(ex["honor"]), "cómo te valoran tus compañeros", "fg"))
        if st:
            txt = (f"{st['cur']} victoria{'s' if st['cur'] != 1 else ''}" if st["cur_win"] else
                   f"{st['cur']} derrota{'s' if st['cur'] != 1 else ''}")
            tiles.append(("Racha actual", txt, f"Mejor racha de victorias guardada: {st['best']}", "good" if st["cur_win"] else "bad"))
        if not tiles:
            return
        c = ui.card(self.box, "Rango y logros")
        cols = 2 if ctx["width"] < 740 else 3 if ctx["width"] < 1040 else 4
        self.tile_wl = max(100, min(220, (ctx["width"] - 110) // cols - 34))  # el texto se ajusta al ancho de cada ficha
        grid = ui.frame(c)
        grid.pack(fill="x")
        for k in range(cols):
            grid.columnconfigure(k, weight=1, uniform="lg")
        for i, (label, value, sub, color) in enumerate(tiles):
            self.tile(grid, i, cols, label, value, sub, color, span=(cols - i % cols) if i == len(tiles) - 1 else 1)   # la última, si queda sola, ocupa todo el ancho
        ui.lbl(c, "Datos de tu cliente de LoL. La posición exacta en el ranking de tu servidor no la da el cliente; el porcentaje de los "
                  "retos sí es de tu servidor.", 9, "dim", anchor="w", wraplength=min(ctx["width"] - 90, 760), justify="left").pack(
            anchor="w", pady=(8, 0))


def history_fecha(ms):
    return history_fecha_full(ms, False)[:5]


class SummaryCard(Section):
    """Resumen interactivo de la pantalla principal: rango y logros y modos en una sola tarjeta con pestañas (el repertorio tiene ya su pestaña).

    Cada ficha enseña una previsualización al pasar el ratón y, al pulsarla, un detalle que se despliega con animación.
    """
    TABS = ["Rango y logros", "Modos"]
    CATS = {"COLLECTION": "Colección", "TEAMWORK": "Trabajo en equipo", "EXPERTISE": "Pericia", "VETERANCY": "Veteranía",
            "IMAGINATION": "Imaginación"}
    DIVS = {"IV": "III", "III": "II", "II": "I"}

    def __init__(self, ui, parent):
        super().__init__(ui, parent)
        self.tab, self.sel, self.tiles, self.slot, self.body = self.TABS[0], None, {}, None, None
        self.hist = []

    # ---- datos ----
    def load_hist(self):
        try:
            self.hist = [e for e in history.load_all(history.hpath(core.CACHE), history.gpath(core.CACHE))
                         if not e.get("rm")]
        except Exception:
            self.hist = []

    def streaks(self):
        games = self.hist
        if not games:
            return None
        cur, n = games[0]["w"], 0
        for e in games:
            if e["w"] != cur:
                break
            n += 1
        best = run = 0
        for e in reversed(games):
            run = run + 1 if e["w"] else 0
            best = max(best, run)
        return {"cur_win": cur, "cur": n, "best": best, "n": len(games)}

    def key(self, ctx):
        info = ctx["info"] or {}
        self.load_hist()
        return (json.dumps((info.get("profile") or {}).get("extra"), sort_keys=True, default=str), json.dumps(info.get("modes"), default=str),
                json.dumps(info.get("pool"), default=str), json.dumps(self.streaks()), self.lp_key(), ctx["width"] // 300)

    def lp_key(self):
        """Datos de la gráfica de rango (lp.json y las fotos de op.gg) y su huella, para repintar solo si cambian."""
        lp, snaps = lpseries.load_all(core.CACHE, core.snaps_path(self.ui.conf))
        self.lp = (lp, snaps) if len(lp) + len(snaps) >= 3 else None
        return (len(lp), len(snaps), max(snaps) if snaps else "", self.hist[0]["id"] if self.hist else "") if self.lp else None

    # ---- estructura ----
    def build(self, ctx):
        ui = self.ui
        self.ctx, self.sel, self.tiles = ctx, None, {}
        c = ui.card(self.box)
        ui.seg(c, self.TABS, self.tab, self.switch, height=30).pack(fill="x")
        self.body = ui.frame(c)
        self.body.pack(fill="x", pady=(12, 0))
        self.paint_tab(False)

    def switch(self, name):
        if name == self.tab:
            return
        self.tab, self.sel, self.tiles = name, None, {}
        self.paint_tab(True)

    def paint_tab(self, animate):
        ui = self.ui
        self.ui.clear(self.body)
        fn = {"Rango y logros": self.tab_logros, "Modos": self.tab_modos}.get(self.tab, self.tab_logros)   # (una pestaña recordada de otra versión)
        if animate and ui.anim_on():
            ui.reveal(self.body, fn)
        else:
            fn(self.body)

    def cols(self, small=2, mid=3, big=4):
        w = self.ctx["width"]
        return small if w < 600 else mid if w < 960 else big

    # ---- ficha con previsualización y pulsación ----
    def tile(self, grid, i, cols, key, label, value, sub="", color="fg", preview="", span=1):
        ui = self.ui
        cell = ctk.CTkFrame(grid, fg_color=PAL["card2"], corner_radius=12, border_width=1, border_color=PAL["card2"])
        cell.grid(row=i // cols, column=i % cols, columnspan=span, sticky="nsew", padx=4, pady=4)
        inner = ui.frame(cell)
        inner.pack(fill="x", padx=12, pady=12)
        wl = max(100, min(220, (self.ctx["width"] - 110) // cols - 40))
        head = ui.frame(inner)
        head.pack(fill="x")
        ui.lbl(head, label.upper(), 9, "dim", True, anchor="w", wraplength=wl, justify="left").pack(side="left")
        ui.lbl(head, "▸", 9, "dim").pack(side="right")
        ui.lbl(inner, value, 15, color, True, True, anchor="w", wraplength=wl, justify="left").pack(anchor="w", pady=(4, 0))
        if sub:
            ui.lbl(inner, sub, 10, "dim", anchor="w", wraplength=wl, justify="left").pack(anchor="w")
        self.tiles[key] = cell
        ui.clickable(cell, lambda k=key: self.toggle(k))
        if preview:
            ui.tip(cell, preview)
        hi, lo = ui.hexm(ui.acc), ui.hexm(PAL["card2"])

        def over(_e, c=cell, k=key):
            if self.sel != k:
                c.configure(border_color=hi)

        def out(_e, c=cell, k=key):
            if self.sel != k:
                c.configure(border_color=lo)
        cell.bind("<Enter>", over, add="+")
        cell.bind("<Leave>", out, add="+")
        return cell

    def mark(self):
        hi, lo = self.ui.hexm(self.ui.acc), self.ui.hexm(PAL["card2"])
        for k, c in self.tiles.items():
            try:
                c.configure(border_color=hi if k == self.sel else lo)
            except Exception:
                pass

    def toggle(self, key):
        ui = self.ui
        if self.slot is None or not self.slot.winfo_exists():
            return
        same = self.sel == key
        self.sel = None if same else key
        self.mark()
        self.ui.clear(self.slot)
        if same:
            return
        fn = self.details.get(key)
        if fn is None:
            return
        wrap = ctk.CTkFrame(self.slot, fg_color=PAL["card2"], corner_radius=12)
        wrap.pack(fill="x", padx=4, pady=(4, 2))
        holder = ui.frame(wrap)
        holder.pack(fill="x", padx=16, pady=12)
        if ui.anim_on():
            ui.reveal(holder, fn)
        else:
            fn(holder)

    # ---- pestaña: rango y logros ----
    def tab_logros(self, parent):
        ui = self.ui
        pr = (self.ctx["info"] or {}).get("profile") or {}
        ex = pr.get("extra") or {}
        self.pr, self.ex = pr, ex
        st = self.streaks()
        es = lambda x: f"{x:.1f}".replace(".", ",")
        miles = lambda n: f"{int(n):,}".replace(",", ".")
        tiles, self.details = [], {}
        if getattr(self, "lp", None):   # tu rango en el tiempo: siempre visible, sin pulsar nada
            import ui_lp
            try:
                marks = []
                for key, name in (("peak", "Pico de la temporada"), ("prev", "Fin de la temporada anterior")):
                    r = ex.get(key)
                    v = lpseries.value_of(r["key"], r.get("div") or "", 0) if r else None
                    if v is not None:
                        marks.append((v, name))
                self.lp_chart = ui_lp.LpChart(ui, parent, self.ctx["width"], self.hist, self.lp[0], self.lp[1], marks=marks)
                ui.frame(parent, height=10).pack()
            except Exception:
                core.log_exc("Gráfica de rango")
        if ex.get("peak"):
            p = ex["peak"]
            tiles.append(("peak", "Mejor rango de la temporada", f"{p['tier']} {p['div']}".strip(), "tu punto más alto este año",
                          TIER_COLORS.get(p["key"], "fg"), "Pulsa para ver tus rangos y cuánto te falta para subir"))
            self.details["peak"] = self.d_peak
        if ex.get("prev"):
            p = ex["prev"]
            tiles.append(("prev", "Temporada anterior", f"{p['tier']} {p['div']}".strip(), "rango con el que acabaste",
                          TIER_COLORS.get(p["key"], "fg"), "Pulsa para ver tus rangos"))
            self.details["prev"] = self.d_prev
        lad = (self.ctx["info"] or {}).get("ladder")
        if lad:  # tu puesto entre todos los jugadores clasificados de tu servidor (op.gg)
            reg = (self.ui.conf.get("opgg_region") or "").upper()
            tiles.append(("ladder", f"Tu puesto en {reg}" if reg else "Tu puesto", f"Top {es(lad['top'])} %",
                          f"puesto {miles(lad['rank'])} de la clasificación de tu servidor", "info",
                          "Posición entre los jugadores con partidas clasificatorias (op.gg)"))
            self.details["ladder"] = self.d_rank
        if ex.get("mastery_score"):
            tiles.append(("mast", "Maestría total", miles(ex["mastery_score"]), "suma de los niveles de tus campeones", "fg",
                          "Pulsa para ver tus campeones con más maestría"))
            self.details["mast"] = self.d_mastery
        if st:
            txt = (f"{st['cur']} victoria{'s' if st['cur'] != 1 else ''}" if st["cur_win"] else f"{st['cur']} derrota{'s' if st['cur'] != 1 else ''}")
            tiles.append(("streak", "Racha actual", txt, f"Mejor racha de victorias guardada: {st['best']}", "good" if st["cur_win"] else "bad",
                          "Pulsa para ver tus últimas partidas"))
            self.details["streak"] = self.d_streak
        if not tiles:
            ui.lbl(parent, "Aún no hay datos de rango o logros: abre el cliente de LoL con tu cuenta.", 11, "dim").pack(anchor="w")
            self.slot = None
            return
        cols = self.cols()
        grid = ui.frame(parent)
        grid.pack(fill="x")
        for k in range(cols):
            grid.columnconfigure(k, weight=1, uniform="lg")
        for i, (key, label, value, sub, color, prev) in enumerate(tiles):
            self.tile(grid, i, cols, key, label, value, sub, color, prev, span=(cols - i % cols) if i == len(tiles) - 1 else 1)
        self.slot = ui.frame(parent)
        self.slot.pack(fill="x")
        ui.lbl(parent, "Datos de tu cliente de LoL. Pulsa cualquier ficha para ver el detalle. La posición exacta en el ranking de tu servidor "
                       "no la da el cliente; el puesto general es de op.gg.", 9, "dim", anchor="w",
               wraplength=min(self.ctx["width"] - 90, 760), justify="left").pack(anchor="w", pady=(8, 0))

    def next_rank(self, rk):
        order = list(TIERS_ES)
        if rk["key"] in ("MASTER", "GRANDMASTER", "CHALLENGER"):
            return None
        if rk["div"] in self.DIVS:
            return f"{rk['tier']} {self.DIVS[rk['div']]}"
        i = order.index(rk["key"]) + 1 if rk["key"] in order else None
        if i is None or i >= len(order):
            return None
        nk = order[i]
        return f"{TIERS_ES[nk]} IV" if nk not in ("MASTER", "GRANDMASTER", "CHALLENGER") else TIERS_ES[nk]

    DIV_VAL = {"IV": 0, "III": 1, "II": 2, "I": 3}

    def rank_val(self, rk):
        """Número para comparar rangos: hierro IV = 0, y +1 por cada división. Los rangos altos (sin divisiones) cuentan como la división I."""
        order = list(TIERS_ES)
        if not rk or rk.get("key") not in order:
            return None
        return order.index(rk["key"]) * 4 + self.DIV_VAL.get(rk.get("div"), 3)

    def d_compare(self, parent, rk, title, verb_up, verb_down, verb_same):
        """Compara un rango de referencia (tu pico o tu final de temporada) con el que tienes ahora."""
        ui = self.ui
        pr = self.pr
        cur = pr.get("solo") or pr.get("flex")
        row = ui.frame(parent)
        row.pack(fill="x", pady=4)
        ui.lbl(row, title.upper(), 9, "dim", True, width=110, anchor="w").pack(side="left")
        em = ui.emblem(rk["key"], 34)
        if em:
            ctk.CTkLabel(row, image=em, text="").pack(side="left", padx=(0, 8))
        ui.lbl(row, f"{rk['tier']} {rk['div']}".strip(), 13, TIER_COLORS.get(rk["key"], "fg"), True, anchor="w").pack(side="left")
        if cur:
            row2 = ui.frame(parent)
            row2.pack(fill="x", pady=4)
            ui.lbl(row2, "AHORA", 9, "dim", True, width=110, anchor="w").pack(side="left")
            em2 = ui.emblem(cur["key"], 34)
            if em2:
                ctk.CTkLabel(row2, image=em2, text="").pack(side="left", padx=(0, 8))
            ui.lbl(row2, f"{cur['tier']} {cur['div']}".strip() + f"  ·  {cur['lp']} PL", 13, TIER_COLORS.get(cur["key"], "fg"), True, anchor="w").pack(side="left")
            a, b = self.rank_val(cur), self.rank_val(rk)
            if a is not None and b is not None:
                d = a - b
                msg = (f"{verb_same}" if d == 0 else f"{verb_up}: {d} {'divisiones' if d > 1 else 'división'} por encima" if d > 0
                       else f"{verb_down}: {'te faltan' if -d > 1 else 'te falta'} {-d} {'divisiones' if -d > 1 else 'división'} para igualarlo")
                ui.lbl(parent, msg, 11, "good" if d >= 0 else "warn", True, anchor="w").pack(anchor="w", pady=(8, 0))

    def d_peak(self, parent):
        rk = (self.ex or {}).get("peak")
        if rk:
            self.d_compare(parent, rk, "Tu pico", "Estás por encima de tu pico", "Aún por debajo de tu pico", "Estás justo en tu pico")
        self.d_rank(parent, lines=False)

    def d_prev(self, parent):
        rk = (self.ex or {}).get("prev")
        if rk:
            self.d_compare(parent, rk, "Fin de la anterior", "Has subido respecto a la temporada pasada", "Has bajado respecto a la temporada pasada",
                           "Igual que al acabar la temporada pasada")
        self.d_rank(parent, lines=False)

    def d_rank(self, parent, lines=True):
        ui = self.ui
        pr, ex = self.pr, self.ex
        for title, rk in (("Solo / Dúo", pr.get("solo")), ("Flexible", pr.get("flex"))):
            row = ui.frame(parent)
            row.pack(fill="x", pady=4)
            ui.lbl(row, title.upper(), 9, "dim", True, width=84, anchor="w").pack(side="left")
            if not rk:
                ui.lbl(row, "Sin clasificar", 11, "dim").pack(side="left")
                continue
            em = ui.emblem(rk["key"], 34)
            if em:
                ctk.CTkLabel(row, image=em, text="").pack(side="left", padx=(0, 8))
            box = ui.frame(row)
            box.pack(side="left")
            ui.lbl(box, f"{rk['tier']} {rk['div']}".strip() + f"  ·  {rk['lp']} PL", 12, TIER_COLORS.get(rk["key"], "fg"), True, anchor="w").pack(anchor="w")
            nxt = self.next_rank(rk)
            if nxt:
                mini_bar(ui, box, min(rk["lp"], 100) / 100, "good", 200, 6).pack(anchor="w", pady=(4, 2))
                ui.lbl(box, f"Te faltan {max(0, 100 - rk['lp'])} PL para {nxt}", 10, "dim", anchor="w").pack(anchor="w")
            else:
                ui.lbl(box, f"{rk['w']}V {rk['l']}D · {round(rk['wr'] * 100)} %", 10, "dim", anchor="w").pack(anchor="w")
        info = []
        if lines and ex.get("peak"):
            info.append(f"Tu mejor rango de esta temporada: {ex['peak']['tier']} {ex['peak']['div']}".strip())
        if lines and ex.get("prev"):
            info.append(f"Acabaste la temporada anterior en {ex['prev']['tier']} {ex['prev']['div']}".strip())
        if info:
            ui.lbl(parent, "  ·  ".join(info), 10, "dim", anchor="w", wraplength=min(self.ctx["width"] - 130, 700), justify="left").pack(anchor="w", pady=(8, 0))

    def d_challenges(self, parent):
        ui = self.ui
        ch = (self.ex or {}).get("challenges") or {}
        es = lambda x: f"{x:.1f}".replace(".", ",")
        for c in sorted(ch.get("cats", []), key=lambda c: (c.get("pct") is None, c.get("pct") or 0)):
            row = ui.frame(parent)
            row.pack(fill="x", pady=4)
            ui.lbl(row, self.CATS.get(c["cat"], c["cat"].title()), 11, "fg", True, width=120 if self.ctx["width"] < 640 else 140, anchor="w").pack(side="left")
            ui.lbl(row, TIERS_ES.get(c["level"], c["level"].title()), 11, TIER_COLORS.get(c["level"], "fg"), True,
                   width=70 if self.ctx["width"] < 640 else 84, anchor="w").pack(side="left")
            narrow = self.ctx["width"] < 640
            mini_bar(ui, row, (c.get("pts", 0) / c["max"]) if c.get("max") else 0, "good", 60 if narrow else 110, 7).pack(side="left", padx=(0, 8))
            if not narrow:
                ui.lbl(row, f"{c.get('pts', 0)} / {c.get('max', '?')}", 10, "dim", width=90, anchor="w").pack(side="left")
            if c.get("pct") is not None:
                ui.lbl(row, f"top {es(c['pct'])} %" if narrow else f"entre el {es(c['pct'])} % mejor", 10,
                       "good" if c["pct"] <= 5 else "dim", anchor="w").pack(side="left")
        if ch.get("next"):
            ui.lbl(parent, f"Para el siguiente rango global de Retos te faltan {int(ch['next']):,} puntos.".replace(",", "."), 10, "dim", anchor="w").pack(
                anchor="w", pady=(8, 0))

    def d_mastery(self, parent):
        ui = self.ui
        top = (self.ctx["info"] or {}).get("mastery_top") or []
        if not top:
            ui.lbl(parent, "Sin datos de maestría por campeón: abre el cliente de LoL con tu cuenta y se leerán solos.", 11, "dim").pack(anchor="w")
            return
        mx = max(p for _, p in top) or 1
        for cid, pts in top[:6]:
            row = ui.frame(parent)
            row.pack(fill="x", pady=4)
            ui.champ(row, cid, 28, False).pack(side="left")
            ui.lbl(row, name(cid, ui.champs), 11, "fg", True, width=120, anchor="w").pack(side="left", padx=8)
            mini_bar(ui, row, pts / mx, "good", 160, 7).pack(side="left", padx=(0, 8))
            ui.lbl(row, f"{pts // 1000} k" if pts >= 1000 else str(pts), 11, ui.acc, True, anchor="w").pack(side="left")

    def d_honor(self, parent):
        ui = self.ui
        lv = int((self.ex or {}).get("honor") or 0)
        row = ui.frame(parent)
        row.pack(anchor="w")
        for i in range(1, 6):
            tk.Frame(row, width=int(34 * ui.scale_px()), height=int(10 * ui.scale_px()),
                     bg=ui.hexm(ui.acc if i <= lv else PAL["border"])).pack(side="left", padx=2)
        ui.lbl(parent, f"Nivel {lv} de 5. El honor lo dan tus compañeros y rivales al acabar una partida si te has portado bien. Sube con el "
                       "tiempo y con buen comportamiento.", 10, "dim", anchor="w", justify="left", wraplength=min(self.ctx["width"] - 130, 640)).pack(
            anchor="w", pady=(8, 0))

    def d_streak(self, parent):
        ui = self.ui
        games = self.hist[:20]
        st = self.streaks() or {}
        ui.lbl(parent, "ÚLTIMAS 20 PARTIDAS", 9, "dim", True, anchor="w").pack(anchor="w")
        ui.dots(parent, [e["w"] for e in games[::-1]], 12).pack(anchor="w", pady=(4, 8))
        w = sum(1 for e in games if e["w"])
        ui.lbl(parent, f"{w} {'victoria' if w == 1 else 'victorias'} y {len(games) - w} {'derrota' if len(games) - w == 1 else 'derrotas'} ({round(w / max(1, len(games)) * 100)} %). Mejor racha de victorias guardada: "
                       f"{st.get('best', 0)}. Partidas guardadas: {st.get('n', 0)}.", 10, "dim", anchor="w", justify="left",
               wraplength=min(self.ctx["width"] - 130, 640)).pack(anchor="w")

    # ---- pestaña: modos ----
    def tab_modos(self, parent):
        ui = self.ui
        modes = (self.ctx["info"] or {}).get("modes") or []
        self.slot = None
        if not modes:
            ui.lbl(parent, "Aún no hay partidas guardadas por modo. LOL-E guarda las que ve: aparecerán cuando juegues con la app abierta.", 11, "dim").pack(anchor="w")
            return
        self.mode_slots = {}
        for m in modes:
            box = ui.frame(parent)
            box.pack(fill="x")
            row = ctk.CTkFrame(box, fg_color=PAL["card2"], corner_radius=10, border_width=1, border_color=PAL["card2"])
            row.pack(fill="x", pady=4)
            inner = ui.frame(row)
            inner.pack(fill="x", padx=12, pady=8)
            wr = m["wins"] / m["games"]
            ui.lbl(inner, m["name"], 12, "fg", True, True, width=96, anchor="w").pack(side="left")
            ui.lbl(inner, partidas(m["games"]), 10, "dim", width=76, anchor="w").pack(side="left")
            ui.lbl(inner, f"{wr * 100:.0f} %", 13, "good" if wr >= .5 else "bad", True, True, width=44).pack(side="left")
            ui.lbl(inner, "▸", 9, "dim").pack(side="right", padx=(8, 0))
            ui.dots(inner, m["last"]).pack(side="right")
            slot = ui.frame(box)
            slot.pack(fill="x")
            self.mode_slots[m["name"]] = slot
            ui.clickable(row, lambda n=m["name"], s=slot, r=row: self.open_mode(n, s, r))
            ui.tip(row, "Pulsa para ver tus últimas partidas y campeones en este modo")
        self.open_row = None

    def open_mode(self, mname, slot, row):
        ui = self.ui
        was = slot.winfo_children()
        for sl in self.mode_slots.values():  # un solo detalle abierto a la vez
            for ch in sl.winfo_children():
                ch.destroy()
        if was:
            return
        games = [e for e in self.hist if mode_of(e) == mname]
        wrap = ctk.CTkFrame(slot, fg_color=PAL["card"], corner_radius=10, border_width=1, border_color=PAL["border"])
        wrap.pack(fill="x", padx=8, pady=(0, 8))
        holder = ui.frame(wrap)
        holder.pack(fill="x", padx=12, pady=12)

        def fill(p):
            s = history.summary(games)
            if not games:
                ui.lbl(p, "No hay partidas guardadas con detalle en este modo.", 10, "dim").pack(anchor="w")
                return
            line = f"{partidas(s['n'])} {'guardada' if s['n'] == 1 else 'guardadas'} · {s['wins']}V {s['n'] - s['wins']}D"
            if s["kda"] is not None:
                line += f" · KDA {s['kda']:.2f}".replace(".", ",")
            durs = [e["d"] for e in games if e.get("d")]
            if durs:
                m_ = sum(durs) / len(durs)
                line += f" · {int(m_ // 60)}:{int(m_ % 60):02d} de media"
            ui.lbl(p, line, 11, "fg", anchor="w", wraplength=min(self.ctx["width"] - 140, 640), justify="left").pack(anchor="w")
            ui.dots(p, [e["w"] for e in games[:20][::-1]], 11).pack(anchor="w", pady=(8, 8))
            cnt, win = Counter(e["c"] for e in games), Counter(e["c"] for e in games if e["w"])
            r2 = ui.frame(p)
            r2.pack(anchor="w")
            for cid, g in cnt.most_common(4):
                cell = ui.frame(r2)
                cell.pack(side="left", padx=(0, 12))
                ui.champ(cell, cid, 30, False).pack(side="left")
                ui.lbl(cell, f" {g} · {round(win[cid] / g * 100)} %", 10, "good" if win[cid] * 2 >= g else "bad", True).pack(side="left")
        if ui.anim_on():
            ui.reveal(holder, fill)
        else:
            fill(holder)

class PoolCard(Section):
    def key(self, ctx):
        return json.dumps((ctx["info"] or {}).get("pool"), default=str)

    def build(self, ctx):
        ui = self.ui
        pool = (ctx["info"] or {}).get("pool") or []
        if not pool:
            return
        c = ui.card(self.box, "Tu repertorio de la temporada")
        grid = ui.frame(c)
        grid.pack(fill="x")
        for k in range(3):
            grid.columnconfigure(k, weight=1, uniform="pool")
        for n, (cid, g, w) in enumerate(pool):
            cell = ctk.CTkFrame(grid, fg_color=PAL["card2"], corner_radius=12)
            cell.grid(row=n // 3, column=n % 3, sticky="ew", padx=4, pady=4)
            inner = ui.frame(cell)
            inner.pack(padx=8, pady=12)
            ui.champ(inner, cid, 48, True).pack()
            wr = w / g
            ui.lbl(inner, f"{wr:.0%}", 20, "good" if wr >= .5 else "bad", True, True).pack(pady=(4, 0))
            ui.lbl(inner, f"{w} de {partidas(g)}", 9, "dim").pack(pady=(0, 4))
            ui.bar(inner, [(wr, "good" if wr >= .5 else "bad")], 5, True).pack(fill="x", padx=8)


# ------------------------------------------------------------------ selección de campeón
class ProfileStrip(Section):
    """Resumen en una línea mientras se elige: lo importante ocupa el sitio de lo recomendado."""

    def key(self, ctx):
        r = ctx["r"]
        return (json.dumps(r["profile"], sort_keys=True, default=str), tuple(r["form"]), ctx["width"] // 100)

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        pr = r["profile"] or {}
        c = ui.card(self.box, pad=4)
        row = ui.frame(c)
        row.pack(fill="x")
        right = ui.frame(row)  # se coloca primero: si falta sitio, se recorta lo de la izquierda y los resultados siempre se ven
        right.pack(side="right")
        img = ui.profile_icon(pr["icon"], 30) if pr.get("icon") else None
        if img:
            ctk.CTkLabel(row, image=img, text="").pack(side="left", padx=(0, 12))
        solo = pr.get("solo")
        ui.lbl(row, r["rank"] or "Sin clasificar", 15, TIER_COLORS.get(solo["key"], "fg") if solo else "dim", True, True).pack(side="left")
        if r["record"] and ctx["width"] >= 600:
            ui.lbl(row, f"   {r['record']}", 11, "dim").pack(side="left")
        if r["form"][-3:] == [False] * 3 and ctx["width"] >= 820:  # el aviso solo cabe en ventanas anchas
            ui.lbl(right, "Cuidado con el tilt  ", 10, "warn", True).pack(side="left")
        for w in r["form"]:
            ctk.CTkLabel(right, text="V" if w else "D", width=22, height=20, corner_radius=6, font=ui.font(10, True, True),
                         fg_color=PAL["good" if w else "bad"], text_color=ON_FILL).pack(side="left", padx=2)


def comp_line(st):
    """«daño físico 3 · mágico 1 · tanques 1 · control alto» de un equipo (comp_stats), o "" si aún no hay campeones. Solo datos de composición."""
    if not st or not (st.get("ad", 0) + st.get("ap", 0)):
        return ""
    return f"daño físico {st['ad']} · mágico {st['ap']} · tanques {st.get('tanks', 0)} · control {ctl(st.get('cc', 0))}"


class TurnCard(Section):
    """Tu turno: icono de línea, estado, fases de la selección y cuenta atrás en anillo."""
    STEPS = ["Planificación", "Bans", "Picks", "Final"]

    def __init__(self, ui, parent):
        super().__init__(ui, parent)
        self.timer_lbl = None

    def step(self, session):
        ph = session["timer"]["phase"]
        ban = any(a.get("type") == "ban" and not a.get("completed") for g in session.get("actions", []) for a in g)
        return 0 if ph == "PLANNING" else (1 if ban else 2) if ph == "BAN_PICK" else 3

    def key(self, ctx):
        r, s = ctx["r"], ctx["session"]
        return (r["turn"], s["timer"]["phase"], r["role"], self.step(s), r["mode"]["kind"], comp_line(r.get("enemy_stats")), comp_line(r.get("ally_stats")))

    def build(self, ctx):
        ui, r, session = self.ui, ctx["r"], ctx["session"]
        sr = r["mode"]["kind"] == "sr"
        c = ui.card(self.box)
        row = ui.frame(c)
        row.pack(fill="x")
        st_col = {"ban": "bad", "pick": "good"}.get(r["turn"])
        tk.Frame(row, width=4, bg=ui.hexm(PAL[st_col]) if st_col else ui.hexm(ui.acc)).pack(side="left", fill="y", padx=(0, 12))
        if sr and r["role"] in ROLES_ES:
            ctk.CTkLabel(row, image=ui.role_icon(r["role"], 56), text="").pack(side="left", padx=(0, 16))
        left = ui.frame(row)
        left.pack(side="left")
        turn = r["turn"]
        dot = {"ban": "bad", "pick": "good"}.get(turn, "dim")
        title = {"ban": "Te toca banear", "pick": "Te toca elegir"}.get(turn, "Selección en curso")
        head = ui.frame(left)
        head.pack(anchor="w")
        dot_lbl = ui.lbl(head, "●", 16, dot)
        dot_lbl.pack(side="left", padx=(0, 8))
        ui.lbl(head, title, 20, "fg", True, True).pack(side="left")
        if turn and ui.anim_on():
            ui.pulse(dot_lbl, ui.hexm(dot), ui.hexm("dim"))
        if sr:
            role = ROLES_ES.get(r["role"], "sin asignar")
            ui.lbl(left, f"Tu línea: {role.lower()}", 11, "dim").pack(anchor="w", pady=(2, 4))
            steps = ui.frame(left)
            steps.pack(anchor="w")
            idx = self.step(session)
            for i, name in enumerate(self.STEPS):
                ui.lbl(steps, "●" if i <= idx else "○", 9, ui.acc if i <= idx else "dim").pack(side="left")
                ui.lbl(steps, f" {name}", 9, "fg" if i == idx else "dim", i == idx).pack(side="left")
                if i < len(self.STEPS) - 1:
                    ui.lbl(steps, "  ─  ", 9, "dim").pack(side="left")
        else:
            ui.lbl(left, f"{r['mode']['group'] or 'Otro modo'}  ·  sin roles ni bans", 11, "dim").pack(anchor="w", pady=(2, 0))
        self.timer_lbl = ctk.CTkLabel(row, text="")
        self.timer_lbl.pack(side="right")
        lines = [(t, v) for t, v in (("Rivales", comp_line(r.get("enemy_stats"))), ("Tu equipo", comp_line(r.get("ally_stats")))) if v] if sr else []
        if lines:
            box = ui.frame(c)
            box.pack(fill="x", pady=(10, 0))
            for who, text in lines:
                ui.lbl(box, f"{who}: {text}", 11, "fg" if who == "Rivales" else "dim", anchor="w", justify="left",
                       wraplength=max(260, ctx["width"] - 110)).pack(anchor="w")
        self.tick(ctx)

    def tick(self, ctx):
        """Solo cambia la imagen del anillo: no se repinta nada más."""
        if self.timer_lbl is None or not self.timer_lbl.winfo_exists() or not ctx.get("session"):
            return
        secs, inf = core.timer_left(ctx["session"], ctx["got"])
        total = max(1.0, ctx["session"]["timer"].get("totalTimeInPhase", 30000) / 1000)
        img = self.ui.ring(0 if inf else secs / total, 58, "∞" if inf else str(secs), "bad" if secs <= 8 and not inf else self.ui.acc)
        self.timer_lbl.configure(image=img)
        self.timer_lbl.image = img


class MyPick(Section):
    """El campeón que has marcado o bloqueado: su build y runas aparecen solos, estuviera o no entre las recomendaciones."""
    LANES = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support"}
    opened = set()   # campeones sin bloquear cuya build el usuario ha abierto a mano

    def key(self, ctx):
        r = ctx["r"]
        return (r.get("mine"), r.get("mine_locked"), r.get("mine") in self.opened, r["role"], r["lane_opp"], r["mode"]["kind"], tuple(r.get("enemies") or ()), r.get("lane_opp_auto"))

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        cid, lane = r.get("mine"), self.LANES.get(r["role"])
        if r["mode"]["kind"] != "sr" or not cid or cid not in ui.champs or not lane:
            self.box.configure(height=1)
            return
        c = ui.card(self.box)
        head = ui.frame(c)
        head.pack(fill="x", pady=(0, 8))
        ui.champ(head, cid, 44, False).pack(side="left", padx=(0, 12))
        txt = ui.frame(head)
        txt.pack(side="left")
        ui.lbl(txt, "TU CAMPEÓN ELEGIDO" if r.get("mine_locked") else "SIN CONFIRMAR · LO ESTÁS MARCANDO", 10, "dim" if r.get("mine_locked") else "warn", True).pack(anchor="w")
        ui.lbl(txt, name(cid, ui.champs), 18, "fg", True, True).pack(anchor="w")
        try:   # si las últimas notas del parche tocaron a este campeón, una línea lo dice (sin red: solo lo ya guardado)
            import ui_patch
            chip = ui_patch.patch_chip(ui, txt, cid)
            if chip is not None:
                chip.pack(anchor="w", pady=(2, 0))
        except Exception:
            core.log_exc("Aviso de parche en la selección")
        if not r.get("mine_locked") and cid not in self.opened:
            # marcado pero sin bloquear: puede cambiar, así que no se despliega su build entera (empujaba las recomendaciones fuera de la pantalla); un clic la abre
            more = ui.lbl(c, "▸ Ver su build y su enfrentamiento (aún sin confirmar)", 10, "info", True, anchor="w")
            more.pack(anchor="w")
            more.configure(cursor="hand2")

            def open_it(_e=None, cid=cid):
                self.opened.add(cid)
                self.refresh(ctx, True)
            more.bind("<Button-1>", open_it)
            return
        import ui_opp
        pk = ui_opp.picker(ui, c, cid, lane, r.get("enemies") or [], r.get("lane_opp_auto") or 0,
                           ui.opp_now(), ui.set_opp, ctx["width"] - 110)
        if pk is not None:
            pk.pack(fill="x", pady=(0, 12))
        build_panel(ui, c, cid, lane, r["lane_opp"] or None, ctx["width"] - 110, r.get("enemy_stats")).pack(fill="x")
        import ui_claves
        ui_claves.block(ui, c, cid, ctx["width"] - 110)
        import ui_guide
        ui_guide.guide_block(ui, c, cid, r["lane_opp"] or None, lane, ctx["width"])


class JumpBar(Section):
    """Fila de atajos «Ir a: Tu campeón · Recomendaciones · …» arriba de la selección: la pantalla es larga y cada bloque está a varias pantallas del siguiente.
    Solo salen los bloques que ahora tienen contenido. Se repinta la última (después de las demás secciones) para saber cuáles hay."""

    def __init__(self, ui, parent, gui):
        super().__init__(ui, parent)
        self.gui, self.targets = gui, []

    def present(self):
        return [(n, s) for n, s in self.targets if s.box.winfo_children()]   # (la altura aún no se ha calculado justo tras repintar: se mira si hay contenido)

    def key(self, ctx):
        return tuple(n for n, _s in self.present()) + (ctx["r"]["mode"]["kind"], ctx["width"] < 660)

    def build(self, ctx):
        items = self.present()
        if len(items) < 2:
            self.box.configure(height=1)
            return
        per = 3 if ctx["width"] < 660 else len(items)   # estrecha: dos filas, para que no se corten los últimos
        row = None
        for i, (n, s) in enumerate(items):
            if i % per == 0:
                row = self.ui.frame(self.box)
                row.pack(fill="x", pady=(0, 6))
                self.ui.lbl(row, "IR A" if i == 0 else "", 9, "dim", True, width=34, anchor="w").pack(side="left", padx=(2, 8))
            ctk.CTkButton(row, text=n, width=0, height=26, corner_radius=13, font=self.ui.font(11), fg_color=PAL["card2"], text_color=PAL["fg"],
                          hover_color=PAL["border"], command=lambda s=s: self.go(s)).pack(side="left", padx=(0, 6))

    def go(self, sec):
        """Baja (o sube) hasta el bloque, dejando su cabecera en lo alto de la ventana."""
        self.gui.go_to(sec.box)


class BanIdeas(Section):
    def key(self, ctx):
        r = ctx["r"]
        return (r["turn"] == "ban" or ctx["session"]["timer"]["phase"] == "PLANNING", tuple(x[3] for x in r["ban_ideas"]),
                tuple((x[2], round(x[1], 1)) for x in r.get("meta_bans") or []), r["mode"]["kind"])

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        if r["mode"]["kind"] != "sr" or not (r["turn"] == "ban" or ctx["session"]["timer"]["phase"] == "PLANNING"):
            return
        threats = r.get("meta_bans") or []
        if not r["ban_ideas"] and threats:   # sin partidas suficientes (instalación nueva o línea nueva): se enseña lo que más gana en tu línea
            c = ui.card(self.box, "Lo que más gana en tu línea este parche")
            row = ui.frame(c)
            row.pack(anchor="w")
            for n, wr, cid in threats:
                cell = ui.frame(row)
                cell.pack(side="left", padx=(0, 16))
                ui.champ(cell, cid, 40, False, "#ff5a5f").pack(side="left")
                ui.lbl(cell, f"{n}\n{wr:.1f} %".replace(".", ","), 10, "bad").pack(side="left", padx=8)
            ui.lbl(c, "Ningún rival de tu línea destaca todavía en tus partidas: son datos de todos los jugadores (Lolalytics).", 9, "dim",
                   anchor="w", justify="left", wraplength=max(240, ctx["width"] - 110)).pack(anchor="w", pady=(6, 0))
            return
        c = ui.card(self.box, "Banea a quien te gana en tu línea")
        if not r["ban_ideas"]:
            ui.lbl(c, "Aún no tienes partidas suficientes contra nadie en tu línea para sugerir un baneo. Mira el meta en «Enfrentamiento».", 11, "dim").pack(anchor="w")
            return
        row = ui.frame(c)
        row.pack(anchor="w")
        for n, w, g, cid in r["ban_ideas"]:
            cell = ui.frame(row)
            cell.pack(side="left", padx=(0, 16))
            ui.champ(cell, cid, 40, False, "#ff5a5f").pack(side="left")
            ui.lbl(cell, f"{n}\n{g - w} {'derrota' if g - w == 1 else 'derrotas'} de {g}", 10, "bad").pack(side="left", padx=8)


CLASES = {"Todas": None, "Tanque": "Tank", "Luchador": "Fighter", "Asesino": "Assassin", "Mago": "Mage",
          "Tirador": "Marksman", "Soporte": "Support"}
ORDENES = ["Afinidad", "Meta", "Sinergia", "Maestría"]
TABS = ["Resumen", "Contra rival", "Sinergias", "Meta y build"]


class Recs(Section):
    """Recomendaciones: carrusel de tarjetas o lista, con filtros, orden y pestañas de información."""

    def __init__(self, ui, parent):
        super().__init__(ui, parent)
        self.sel, self.tab, self.r, self.dyn, self.hero, self.vis, self.width = 0, "Resumen", None, None, None, [], 520
        self.hero_lab, self.info_host, self.pages, self.cur_page, self.cells = None, None, {}, None, []
        self.menu_order = self.menu_class = None
        self.toggles = {}
        self.list_tab, self.info = "Afinidad", {}

    def key(self, ctx):
        r, cf = ctx["r"], self.ui.conf
        return (tuple((c["cid"], round(c["score"], 1), c["off_role"]) for c in r["cands"]), tuple(r["allies"]),
                tuple(r["enemies"]), r["lane_opp"], cf["rec_view"], cf["compact"], cf["top_n"],
                bool(r["meta_info"]), r["mode"]["kind"])

    def build(self, ctx):
        ui = self.ui
        self.r, self.width, self.info = ctx["r"], ctx["width"], ctx.get("info") or {}
        compact = ui.conf["compact"]
        self.keep_cid = self.vis[self.sel]["cid"] if self.vis and 0 < self.sel < len(self.vis) else None
        if self.kind() == "other":
            self.dyn = None
            c = ui.card(self.box, "Recomendado para ti")
            ui.lbl(c, f"Este modo ({self.r['mode']['group'] or 'sin identificar'}) no tiene recomendaciones.\nLOL-E está pensado para la "
                      "Grieta del Invocador y, con menos datos, para ARAM.", 11, "dim", anchor="w", justify="left", wraplength=max(240, self.width - 110)).pack(anchor="w")
            return
        c = ui.card(self.box)
        head = ui.frame(c)
        head.pack(fill="x", pady=(0, 8))
        ctk.CTkFrame(head, width=3, height=14, corner_radius=2, fg_color=ui.acc).pack(side="left", padx=(0, 8))
        ui.lbl(head, "CAMBIO DE CAMPEÓN (BANQUILLO)" if self.kind() == "aram" else "RECOMENDADO PARA TI", 10, "fg", True).pack(side="left")
        if not compact:
            ui.seg(head, list(REC_VIEWS.values()), REC_VIEWS.get(ui.conf["rec_view"], "Carrusel"),
                   self.set_view, width=280, height=26).pack(side="right")
            if self.kind() == "sr":
                self.filter_bar(c)
        self.dyn = ui.frame(c)
        self.dyn.pack(fill="x")
        for cand in self.r["cands"][:10]:
            ui.splash(cand["cid"])  # descarga el arte para que cambiar de tarjeta sea instantáneo
        self.hero = None
        self.render()

    def kind(self):
        return (self.r or {}).get("mode", {}).get("kind", "sr")

    def tabs(self):
        return TABS if self.kind() == "sr" else ["Resumen", "Build"]

    # ---- filtros ----
    def filter_bar(self, parent):
        ui, f = self.ui, self.ui.conf["filters"]
        # plegados por defecto: una línea con el botón y lo que hay activo; las dos filas de controles empujaban la recomendación hacia abajo
        folds = ui.conf.setdefault("folds", {})
        line = ui.frame(parent)
        line.pack(fill="x", pady=(0, 8))
        self.filter_btn = small_btn(ui, line, "", self.toggle_filters, 86)
        self.filter_btn.pack(side="left")
        self.filter_sum = ui.lbl(line, "", 10, "dim", anchor="w")
        self.filter_sum.pack(side="left", padx=(12, 0))
        bar = ui.frame(parent)
        self.filter_box, self.filter_line, self.filter_built = bar, line, False
        self.paint_filter_line()
        if folds.get("rec_filters"):
            self.build_filter_controls()
            bar.pack(fill="x", pady=(0, 12))

    def build_filter_controls(self):
        """Los controles (dos menús desplegables y los botones) solo se construyen cuando se van a ver: con los filtros plegados, que es lo
        habitual, cada repintado de la selección se ahorra ~200 ms (los menús de CustomTkinter son lo más caro de esta tarjeta)."""
        if self.filter_built:
            return
        self.filter_built = True
        ui, f, bar = self.ui, self.ui.conf["filters"], self.filter_box
        r1 = ui.frame(bar)
        r1.pack(fill="x")
        ui.lbl(r1, "Ordenar", 10, "dim").pack(side="left", padx=(0, 8))
        self.menu_order = ui.menu(r1, ORDENES, f["orden"], lambda v: self.set_filter("orden", v), 112)
        self.menu_order.pack(side="left")
        ui.lbl(r1, "Clase", 10, "dim").pack(side="left", padx=(16, 8))
        self.menu_class = ui.menu(r1, list(CLASES), f["clase"], lambda v: self.set_filter("clase", v), 112)
        self.menu_class.pack(side="left")
        r2 = ui.frame(bar)
        r2.pack(fill="x", pady=(8, 0))
        for text, key in (("Mi rol", "mi_rol"), ("Mis campeones", "mios"), ("Meta fuerte", "meta")):
            self.toggle(r2, text, key)
        small_btn(ui, r2, "Quitar filtros" if self.width < 500 else "Restablecer filtros", self.reset_filters, 104 if self.width < 500 else 140).pack(side="right")   # en estrecho (o al 130 %) el texto largo salía cortado

    def filter_summary(self):
        """Lo que está activo, en una línea: el orden y solo los filtros que recortan la lista."""
        f = self.ui.conf["filters"]
        parts = [f"orden: {f['orden'].lower()}"]
        if f["clase"] != "Todas":
            parts.append(f["clase"].lower())
        parts += [t for t, k in (("mi rol", "mi_rol"), ("mis campeones", "mios"), ("meta fuerte", "meta")) if f[k]]
        return "  ·  ".join(parts)

    def paint_filter_line(self):
        try:
            opened = bool(self.ui.conf.get("folds", {}).get("rec_filters"))
            self.filter_btn.configure(text=("▾  " if opened else "▸  ") + "Filtros")
            self.filter_sum.configure(text=self.filter_summary())
        except Exception:
            pass

    def toggle_filters(self):
        ui = self.ui
        folds = ui.conf.setdefault("folds", {})
        folds["rec_filters"] = not folds.get("rec_filters")
        core.save_conf(ui.conf)
        if folds["rec_filters"]:
            self.build_filter_controls()
            self.filter_box.pack(fill="x", pady=(0, 12), after=self.filter_line)
        else:
            self.filter_box.pack_forget()
        self.paint_filter_line()

    def toggle(self, parent, text, key):
        ui = self.ui
        on = ui.conf["filters"][key]
        b = ctk.CTkButton(parent, text=text, height=26, width=10, corner_radius=13, font=ui.font(11), border_width=1,
                          border_color=PAL["border"], fg_color=ui.acc if on else PAL["card2"],
                          text_color=ON_FILL if on else PAL["fg"], hover_color=PAL["border"])
        b.configure(command=lambda: self.flip(b, key))
        b.pack(side="left", padx=(0, 8))
        if ayuda.glossary(text):
            ui.tip(b, ayuda.glossary(text))
        self.toggles[key] = b

    def flip(self, btn, key):
        ui = self.ui
        on = not ui.conf["filters"][key]
        ui.conf["filters"][key] = on
        btn.configure(fg_color=ui.acc if on else PAL["card2"], text_color=ON_FILL if on else PAL["fg"])
        self.filters_changed()

    def set_filter(self, key, v):
        self.ui.conf["filters"][key] = v
        self.filters_changed()

    def filters_changed(self):
        core.save_conf(self.ui.conf)
        self.paint_filter_line()
        self.sel = 0
        self.render()

    def pool(self):
        """Candidatos que pasan los filtros de arriba (sin ordenar ni recortar)."""
        ui, f = self.ui, self.ui.conf["filters"]
        out = []
        for c in self.r["cands"]:
            if f["mi_rol"] and c["off_role"] and self.r["role"]:
                continue
            if f["mios"] and c["games"] < ui.conf["params"]["min_games_mine"]:
                continue
            if f["meta"] and not (c["meta"] and c["meta"]["wr"] >= ui.conf["params"]["meta_filter"]):
                continue
            tag = CLASES.get(f["clase"])
            if tag and tag not in c["tags"]:
                continue
            out.append(c)
        return out

    def visible(self):
        ui, f = self.ui, self.ui.conf["filters"]
        if self.kind() != "sr":
            return sorted(self.r["cands"], key=lambda c: -c["score"])[: 3 if ui.conf["compact"] else ui.conf["top_n"]]
        out = self.pool()
        order = {"Afinidad": lambda c: -c["score"], "Meta": lambda c: -(c["meta"]["wr"] if c["meta"] else 0),
                 "Sinergia": lambda c: -c["syn"]["score"], "Maestría": lambda c: -c["mastery"]}[f["orden"]]
        out.sort(key=order)
        return out[: 3 if ui.conf["compact"] else ui.conf["top_n"]]

    def pct(self, c):
        return self.ui.pct(c["score"], self.r["pct_scale"])

    def pct_text(self, c):
        """La afinidad como texto. En ARAM solo sale de tu historial: sin partidas con el campeón no hay dato, y un «0» parecía una mala nota."""
        if self.kind() == "aram" and self.pct(c) == 0:
            return "—"
        return str(self.pct(c))

    def eyebrow(self):
        if self.sel:
            return f"Opción {self.sel + 1} de {len(self.vis)}"
        if self.kind() == "aram":
            return "Tu campeón actual" if self.vis[0]["cid"] == (self.r or {}).get("mine") else "Mejor del banquillo para ti"
        return "Mejor opción para ti"

    # ---- navegación ----
    def set_view(self, v):
        self.ui.conf["rec_view"] = next((k for k, t in REC_VIEWS.items() if t == v), v.lower())
        core.save_conf(self.ui.conf)
        self.render()

    def carousel_alive(self):
        return self.hero_lab is not None and self.hero_lab.winfo_exists()

    def pick(self, i):
        self.sel = i
        if self.carousel_alive() and not self.ui.conf["compact"] and self.ui.conf["rec_view"] == "carrusel":
            self.show_card(fade=True)  # solo cambia la tarjeta, no se reconstruye nada más
        else:
            self.render(fade=True)

    def go(self, d):
        if self.vis:
            self.pick((self.sel + d) % len(self.vis))

    def set_tab(self, v):
        self.tab = v
        if self.carousel_alive():
            self.show_page(self.vis[self.sel])

    # ---- dibujo del cuerpo (lo único que cambia al elegir tarjeta o pestaña) ----
    def render(self, fade=False):
        ui = self.ui
        if self.dyn is None or not self.dyn.winfo_exists():
            return
        fast = self.carousel_alive() and not ui.conf["compact"] and ui.conf["rec_view"] == "carrusel"
        self.vis = self.visible()
        keep, self.keep_cid = getattr(self, "keep_cid", None), None
        if keep is not None:  # la lista cambió de orden: sigues viendo el mismo campeón, no el que ocupa ahora esa posición
            ids = [c["cid"] for c in self.vis]
            if keep in ids:
                self.sel = ids.index(keep)
        if fast and self.vis:
            self.refilter(fade)  # el esqueleto (flechas, pestañas) se conserva: solo cambian franja y páginas
            return
        self.ui.clear(self.dyn)
        self.pages, self.cur_page, self.hero_lab, self.cells, self.list_hero = {}, None, None, [], None
        if ui.conf["rec_view"] == "listas" and not ui.conf["compact"] and self.kind() == "sr":
            self.lists_view()
            return
        ui.root.after(90, self.fit_hero)
        if not self.vis and not self.r["cands"]:  # nada que comparar todavía (por ejemplo, un banquillo de ARAM aún vacío)
            ui.lbl(self.dyn, "Todavía no hay campeones para comparar. Aparecerán cuando el cliente los muestre.", 11, "dim").pack(anchor="w", pady=(4, 8))
            return
        if not self.vis:
            ui.lbl(self.dyn, "Ningún campeón cumple los filtros.", 11, "dim").pack(anchor="w", pady=(4, 8))
            ctk.CTkButton(self.dyn, text="Restablecer filtros", height=28, font=ui.font(11), fg_color=PAL["card2"], text_color=PAL["fg"],
                          hover_color=PAL["border"], command=self.reset_filters).pack(anchor="w")
            return
        self.sel = min(self.sel, len(self.vis) - 1)
        if ui.conf["compact"] or ui.conf["rec_view"] == "lista":
            self.list_view()
        else:
            self.carousel(fade)

    def refilter(self, fade):
        for pg in self.pages.values():
            pg.destroy()
        self.pages, self.cur_page = {}, None
        self.strip_row.destroy()
        self.build_strip()
        self.sel = min(self.sel, len(self.vis) - 1)
        self.show_card(fade)

    def resized(self, width):
        """Cambio de ancho de la ventana: solo se rehace la imagen de la tarjeta principal."""
        self.width = width
        for pg_ in self.pages.values():
            pg_.destroy()
        self.pages, self.cur_page = {}, None  # el ancho cambió: las páginas de información se rehacen con la columna nueva
        if self.carousel_alive():
            self.hero_w = max(260, min(2400, width - 52 - 2 * (38 + 6)))
            self.hero = None
            self.show_card(False)
        elif self.vis:
            self.render()

    def reset_filters(self):
        ui = self.ui
        ui.conf["filters"].update({"orden": "Afinidad", "clase": "Todas", "mi_rol": True, "mios": False, "meta": False})
        core.save_conf(ui.conf)
        for w, v in ((self.menu_order, "Afinidad"), (self.menu_class, "Todas")):
            if w is not None:
                w.set(v)
        for key, b in self.toggles.items():  # se actualizan en el sitio, sin reconstruir la barra
            on = ui.conf["filters"][key]
            b.configure(fg_color=ui.acc if on else PAL["card2"], text_color=ON_FILL if on else PAL["fg"])
        self.paint_filter_line()
        self.sel = 0
        self.render()

    def fit_hero(self):
        """El ancho de la imagen grande se ajusta al sitio que de verdad tiene (en una partida real se veía recortada a los lados)."""
        try:
            if self.dyn is None or not self.dyn.winfo_exists():
                return
            dw = self.dyn.winfo_width() / self.ui.scale_px()
            if dw < 120:
                return
            if self.carousel_alive():
                want = max(260, dw - 2 * (38 + 6) - 6)
                if abs(want - self.hero_w) > 6:
                    self.hero_w, self.hero = want, None
                    self.show_card(False)
            elif getattr(self, "list_hero", None):
                lab, cand, pct, w = self.list_hero
                want = max(260, dw - 6)
                if abs(want - w) > 6 and lab.winfo_exists():
                    pil = self.ui.hero_pil(cand["cid"], "Mejor opción para ti", pct, want)
                    im = ctk.CTkImage(light_image=pil, dark_image=pil, size=(want, 150))
                    lab.configure(image=im)
                    lab.image = im
                    self.list_hero = (lab, cand, pct, want)
        except Exception:
            core.log_exc("Ajuste de la imagen principal")

    def list_view(self):
        ui, compact = self.ui, self.ui.conf["compact"]
        for i, c in enumerate(self.vis, 1):
            pct = self.pct(c)
            if i == 1:
                w = max(340, min(2400, self.width - 52))
                lab = self.hero_label(self.dyn, c, pct, w, "Mejor opción para ti")
                lab.pack(pady=(0, 8))
                self.list_hero = (lab, c, pct, w)
                if not compact:
                    ui.chips(self.dyn, c["why"] or ["encaja con tu rol"], 3 if self.width < 900 else 4)
                continue
            row = ctk.CTkFrame(self.dyn, fg_color=PAL["card2"], corner_radius=12)
            row.pack(fill="x", pady=4)
            inner = ui.frame(row)
            inner.pack(fill="x", padx=12, pady=12)
            ui.champ(inner, c["cid"], 40, False).pack(side="left")
            right = ui.frame(inner)   # antes que el centro: si no, las etiquetas se comían su sitio y «afinidad» salía cortada
            right.pack(side="right", anchor="n")
            ui.lbl(right, str(pct), 22, ui.acc, True, True).pack(anchor="e")
            ui.lbl(right, "afinidad", 9, "dim").pack(anchor="e")
            mid = ui.frame(inner)
            mid.pack(side="left", fill="x", expand=True, padx=12)
            ui.lbl(mid, f"{i}.  {name(c['cid'], ui.champs)}", 14, "fg", True, True).pack(anchor="w")
            if not compact:
                ui.chips(mid, c["why"] or ["encaja con tu rol"])
            if not compact:
                ui.clickable(row, lambda i=i: (self.set_view("carrusel"), self.pick(i - 1)))

    # ---- vista «Listas»: muchos campeones de un vistazo, con varios criterios ----
    LISTS = ["Afinidad", "Meta", "Contra tu rival", "Ventaja vs rival", "Mis campeones"]
    COUNTERS = {}  # (rival, línea) -> filas | "cargando" | ("error", texto, momento)

    def counters(self):
        """Mejores campeones contra tu rival de línea (Lolalytics), descargados en segundo plano."""
        opp, lane = self.r["lane_opp"], matchups.LANES.get(self.r["role"])
        if not opp or not lane:
            return None
        key = (opp, lane)
        st = Recs.COUNTERS.get(key)
        if isinstance(st, tuple) and time.time() - st[2] > 90:  # un fallo se reintenta al cabo de un rato
            st = None
        if st is None:
            Recs.COUNTERS[key] = "cargando"
            ui = self.ui

            def go():
                try:
                    rows = matchups.best_against(ui.champs, opp, lane, core.CACHE, min_games=50)
                except Exception as e:
                    rows = ("error", str(e), time.time())
                Recs.COUNTERS[key] = rows
                ui.notify("recs_data")
            threading.Thread(target=go, daemon=True).start()
            return "cargando"
        return st

    def list_items(self, which):
        """[(campeón, valor grande, color, texto pequeño)] y una explicación, según la lista elegida."""
        ui, f = self.ui, self.ui.conf["filters"]
        tag = CLASES.get(f["clase"])
        owned = set(self.info.get("owned") or [])
        only_mine = f.get("solo_mios", False)
        opp = self.r["lane_opp"]
        oname = name(opp, ui.champs) if opp else ""
        if which == "Afinidad":
            rows = sorted(self.pool(), key=lambda c: -c["score"])
            return [(c["cid"], str(self.pct(c)), ui.acc, (c["why"] or ["encaja con tu rol"])[0]) for c in rows], \
                "Cuánto encaja cada campeón contigo ahora mismo (0 a 100): tu historial, tu rol, tu equipo, sinergias y meta."
        if which == "Meta":
            rows = sorted((c for c in self.pool() if c["meta"]), key=lambda c: -c["meta"]["wr"])
            return [(c["cid"], f"{c['meta']['wr']:.1f} %".replace(".", ","), "good" if c["meta"]["wr"] >= 50 else "bad",
                     f"{c['meta']['games']:,} partidas".replace(",", ".")) for c in rows], \
                "Porcentaje de victorias de cada campeón en tu línea este parche (Lolalytics), sin tener en cuenta a tu rival."
        if which == "Mis campeones":
            rows = sorted((c for c in self.pool() if c["games"]), key=lambda c: (-(c["wins"] + 1) / (c["games"] + 2), -c["games"]))
            return [(c["cid"], f"{c['wins']}/{c['games']}", "good" if c["wins"] * 2 >= c["games"] else "bad",
                     f"maestría {c['mastery'] // 1000}k" if c["mastery"] >= 1000 else "") for c in rows], \
                "Los que ya has jugado en esta línea, de más a menos victorias (con suavizado: 1 de 1 no cuenta como 100 %)."
        st = self.counters()
        if st is None:
            return None, "Tu rival de línea todavía no ha elegido campeón: esta lista aparece en cuanto lo haga."
        if st == "cargando":
            return None, f"Cargando los mejores campeones contra {oname}…"
        if isinstance(st, tuple):
            return None, f"No hay datos de enfrentamientos contra {oname}: {st[1]}"
        gone = set(self.r["bans"]) | set(self.r["allies"]) | set(self.r["enemies"])   # baneados o ya elegidos: no se pueden coger
        rows = [x for x in st if x["cid"] not in gone and (not tag or tag in ui.champs[x["cid"]]["tags"]) and (not only_mine or not owned or x["cid"] in owned)]
        if which == "Contra tu rival":
            return [(x["cid"], f"{x['wr']:.1f} %".replace(".", ","), "good" if x["wr"] >= 50 else "bad",
                     f"{x['games']:,} partidas".replace(",", ".")) for x in rows], \
                f"Porcentaje de victorias de cada campeón contra {oname} en tu línea (Lolalytics, todos los jugadores, no solo tú)."
        rows = sorted(rows, key=lambda x: -x["delta"])
        return [(x["cid"], f"{'+' if x['delta'] >= 0 else '−'}{abs(x['delta']):.1f}".replace(".", ","), "good" if x["delta"] >= 0 else "bad",
                 f"{x['wr']:.1f} % · {x['games']:,} partidas".replace(",", ".").replace(".", ",", 1)) for x in rows], \
            f"Puntos de victoria que gana cada campeón contra {oname} respecto a su media (Lolalytics). Mide ventaja del enfrentamiento; " \
            "las fuentes públicas no dan la diferencia de oro."

    def lists_view(self):
        ui, f, tk_ = self.ui, self.ui.conf["filters"], tk
        names = [n for n in self.LISTS if n in ("Afinidad", "Meta", "Mis campeones") or self.r["lane_opp"]]
        if self.r["lane_opp"]:
            names = ["Afinidad", "Meta", "Contra tu rival", "Ventaja vs rival", "Mis campeones"]
        if self.list_tab not in names:
            self.list_tab = names[0]
        ui.seg(self.dyn, names, self.list_tab, self.set_list_tab, height=28).pack(fill="x", pady=(0, 8))
        bar = ui.frame(self.dyn)
        bar.pack(fill="x", pady=(0, 8))
        ui.lbl(bar, "Mostrar", 10, "dim").pack(side="left", padx=(0, 8))
        n = ui.conf.get("list_n", 20)
        ui.seg(bar, ["12", "20", "30", "40"], str(n), self.set_list_n, width=190, height=26).pack(side="left")
        if self.list_tab in ("Contra tu rival", "Ventaja vs rival") and (self.info.get("owned") or []):
            on = f.get("solo_mios", False)
            b = ctk.CTkButton(bar, text="Solo los que tengo", height=26, width=10, corner_radius=13, font=ui.font(11), border_width=1,
                              border_color=PAL["border"], fg_color=ui.acc if on else PAL["card2"], text_color=ON_FILL if on else PAL["fg"],
                              hover_color=PAL["border"], command=self.flip_owned)
            b.pack(side="left", padx=(12, 0))
        items, why = self.list_items(self.list_tab)
        ui.lbl(self.dyn, why, 9, "dim", anchor="w", justify="left", wraplength=max(260, self.width - 110)).pack(anchor="w", pady=(0, 8))
        if not items:
            if items is not None:
                ui.lbl(self.dyn, "Ningún campeón cumple los filtros. Abre «Filtros» y quita alguno.", 11, "dim").pack(anchor="w", pady=4)
            return
        items = items[:n]
        cols = 1 if self.width < 620 else 2 if self.width < 980 else 3
        grid = tk_.Frame(self.dyn, bg=ui.bg(self.dyn))
        grid.pack(fill="x")
        for k in range(cols):
            grid.columnconfigure(k, weight=1, uniform="ls")
        card, fg, dim = ui.hexm(PAL["card2"]), ui.hexm(PAL["fg"]), ui.hexm(PAL["dim"])
        fb, f9, f14 = ui.tkf(12, True, False), ui.tkf(9, False, False), ui.tkf(14, True, True)
        for i, (cid, val, color, sub) in enumerate(items):
            cell = tk_.Frame(grid, bg=card)
            cell.grid(row=i // cols, column=i % cols, sticky="ew", padx=4, pady=4)
            ph = ui.champ_photo(cid, 34)
            ic = tk_.Label(cell, image=ph, bd=0, bg=card) if ph is not None else tk_.Frame(cell, width=34, height=34, bg=ui.hexm(PAL["card"]))
            ic.image = ph
            ic.pack(side="left", padx=(8, 8), pady=8)
            mid = tk_.Frame(cell, bg=card)
            mid.pack(side="left", fill="x", expand=True)
            tk_.Label(mid, text=f"{i + 1}.  {name(cid, ui.champs)}", font=fb, fg=fg, bg=card, anchor="w").pack(anchor="w")
            tk_.Label(mid, text=sub, font=f9, fg=dim, bg=card, anchor="w").pack(anchor="w")
            tk_.Label(cell, text=val, font=f14, fg=ui.hexm(PAL[color]) if isinstance(color, str) and color in PAL else ui.hexm(color), bg=card).pack(side="right", padx=12)

    def set_list_tab(self, v):
        self.list_tab = v
        self.render()

    def set_list_n(self, v):
        self.ui.conf["list_n"] = int(v)
        core.save_conf(self.ui.conf)
        self.render()

    def flip_owned(self):
        f = self.ui.conf["filters"]
        f["solo_mios"] = not f.get("solo_mios", False)
        core.save_conf(self.ui.conf)
        self.render()

    def hero_label(self, parent, cand, pct, w, eyebrow):
        pil = self.ui.hero_pil(cand["cid"], eyebrow, pct, w)
        im = ctk.CTkImage(light_image=pil, dark_image=pil, size=(w, 150))
        lab = ctk.CTkLabel(parent, image=im, text="")
        lab.image = im
        return lab

    def carousel(self, fade):
        ui = self.ui
        if self.tab not in self.tabs():
            self.tab = "Resumen"
        aw = 38
        self.hero_w = max(260, min(2400, self.width - 52 - 2 * (aw + 6)))
        row = ui.frame(self.dyn)
        row.pack(fill="x")
        for txt, d, side in (("‹", -1, "left"), ("›", 1, "right")):
            ctk.CTkButton(row, text=txt, width=aw, height=150, corner_radius=12, font=ui.font(24, True), fg_color=PAL["card2"],
                          hover_color=PAL["border"], text_color=PAL["fg"], command=lambda d=d: self.go(d)).pack(side=side)
        self.hero_lab = ctk.CTkLabel(row, text="")
        ui.reg("recs.hero", self.hero_lab)
        self.hero_lab.pack(side="left", padx=8)
        self.tabs_seg = None
        self.build_strip()   # las otras opciones van justo bajo la imagen: debajo del desglose quedaban fuera de la primera pantalla
        tabs_seg = self.tabs_seg = ui.seg(self.dyn, self.tabs(), self.tab, self.set_tab)
        tabs_seg.pack(fill="x", pady=(12, 8))
        ui.reg("recs.pestanas", tabs_seg)
        self.info_host = ctk.CTkFrame(self.dyn, fg_color=PAL["card2"], corner_radius=12)
        self.info_host.pack(fill="x")
        self.hero = None
        self.show_card(fade=False)

    def show_card(self, fade):
        """Muestra la tarjeta elegida: fundido de la imagen, página de información en caché y franja actualizada."""
        ui, c = self.ui, self.vis[self.sel]
        pil = ui.hero_pil(c["cid"], self.eyebrow(), self.pct(c), self.hero_w)
        old, self.hero = self.hero, pil
        self.set_hero(self.hero_lab, old if fade and ui.anim_on() and old is not None and old.size == pil.size else None, pil)
        self.show_page(c)
        self.update_strip()
        self.queue_prebuild()

    def make_page(self, c, tab):
        page = self.ui.frame(self.info_host)
        body = self.ui.frame(page)
        extra = max(0, (self.width - 52 - 800) // 2)  # en pantallas grandes la información se queda en una columna central
        body.pack(fill="x", padx=16 + extra, pady=12)
        {"Resumen": self.tab_summary, "Contra rival": self.tab_matchup, "Sinergias": self.tab_synergy,
         "Meta y build": self.tab_meta, "Build": self.tab_meta}[tab](body, c)
        self.pages[(c["cid"], tab)] = page
        return page

    def show_page(self, c):
        """Cada página (campeón y pestaña) se construye una vez; después solo se muestra u oculta."""
        if self.cur_page is not None:
            self.cur_page.pack_forget()
        page = self.pages.get((c["cid"], self.tab)) or self.make_page(c, self.tab)
        page.pack(fill="x")
        self.cur_page = page

    def queue_prebuild(self):
        """Prepara en segundo plano, poco a poco, las páginas que seguramente vas a abrir."""
        cur = self.vis[self.sel]
        order = [(cur, t) for t in TABS]
        if len(self.vis) > 1:
            order += [(self.vis[(self.sel + o) % len(self.vis)], self.tab) for o in (1, -1, 2)]
        self.pre = [(c, t) for c, t in order if (c["cid"], t) not in self.pages]
        self.pre_id = getattr(self, "pre_id", 0) + 1
        self.ui.root.after(300, lambda i=self.pre_id: self.prebuild_step(i))

    def prebuild_step(self, token):
        if token != getattr(self, "pre_id", 0) or not self.pre or not self.carousel_alive():
            return
        c, t = self.pre.pop(0)
        if (c["cid"], t) not in self.pages:
            self.make_page(c, t)
        self.ui.root.after(70, lambda: self.prebuild_step(token))

    def set_hero(self, lab, old, new, step=0, n=6):
        """Cambio de tarjeta con fundido: mezcla la imagen anterior con la nueva en unos fotogramas."""
        try:
            if not lab.winfo_exists():
                return
            t = 1.0 if old is None else (step + 1) / n
            pil = new if old is None or t >= 1 else Image.blend(old, new, t)
            im = ctk.CTkImage(light_image=pil, dark_image=pil, size=new.size)
            lab.configure(image=im)
            lab.image = im
            if old is not None and step + 1 < n:
                self.ui.root.after(28, lambda: self.set_hero(lab, old, new, step + 1, n))
        except Exception:
            pass

    def build_strip(self):
        """Previsualización inferior: un toque en cualquier campeón salta a su tarjeta."""
        ui = self.ui
        row = ui.frame(self.dyn)
        seg = getattr(self, "tabs_seg", None)
        if seg is not None and seg.winfo_exists() and seg.master is self.dyn:
            row.pack(fill="x", pady=(8, 0), before=seg)   # al cambiar de filtro se volvía a colocar al final, bajo el desglose
        else:
            row.pack(fill="x", pady=(8, 0))
        self.strip_row = row
        self.cells = []
        for i, c in enumerate(self.vis):
            row.columnconfigure(i, weight=1, uniform="thumb")
            cell = ctk.CTkFrame(row, fg_color="transparent", corner_radius=10, border_width=0, border_color=col(ui.acc))
            cell.grid(row=0, column=i, sticky="ew", padx=4)
            inner = ui.frame(cell)
            inner.pack(padx=4, pady=8)
            icon = ctk.CTkLabel(inner, text="", image=ui.icon(c["cid"], 40))
            icon.pack()
            per = (self.width - 60) / max(1, len(self.vis))   # hueco de cada miniatura
            if per >= 62:   # con sitio se pone el nombre: con 30 s de reloj, un retrato pequeño no se reconoce
                nm = name(c["cid"], ui.champs)
                cut = max(5, int(per // 8))
                ui.lbl(inner, nm if len(nm) <= cut else nm[:cut - 1] + "…", 9, "fg").pack(pady=(2, 0))
            num = ui.lbl(inner, self.pct_text(c), 13, "dim", True, True)
            num.pack(pady=(2, 0))
            ui.clickable(cell, lambda i=i: self.pick(i))
            self.cells.append((cell, icon, num, c["cid"]))

    def update_strip(self):
        ui = self.ui
        for i, (cell, icon, num, cid) in enumerate(self.cells):
            on = i == self.sel
            cell.configure(fg_color=PAL["card2"] if on else "transparent", border_width=1 if on else 0)
            img = ui.icon(cid, 40, hexc(ui.acc, True) if on else None)
            if img is not None:
                icon.configure(image=img)
            num.configure(fg=ui.hexm(ui.acc if on else "dim"))

    # ---- pestañas ----
    def tab_summary(self, body, c):
        ui = self.ui
        row = ui.frame(body)
        row.pack(fill="x", pady=(0, 8))
        g, w, m = c["games"], c["wins"], c["mastery"]
        ui.kpi(row, f"{m // 1000}k" if m else "—", "maestría")
        ui.kpi(row, f"{w} de {g}" if g else "—", "victorias")
        ui.kpi(row, f"{w / g:.0%}" if g else "—", "% de victorias")
        # (la afinidad no se repite aquí: ya está en el anillo de la imagen y en la miniatura)
        bw = 170 if self.width < 560 else 300 if self.width < 900 else 400
        col = ui.frame(body)
        col.pack()  # sin «fill»: la columna queda centrada y el desglose no se pega al borde izquierdo
        why = [w for w in c["why"] if not re.match(r"^\d+/\d+ victorias( en ARAM)?$", w)]   # ya está arriba como «2 de 3»
        ui.chips(col, why or ["encaja con tu rol"], 3 if self.width < 900 else 4)
        parts, score, scale = c["parts"], c["score"], self.r["pct_scale"]

        def fill(host):
            breakdown_rows(ui, host, parts, score, scale, bw)
            ui.lbl(host, "La afinidad (0 a 100) es la suma de estos puntos sobre un máximo realista. Los pesos y su explicación están "
                         "en «Datos» (se abre desde Ajustes).", 9, "dim", anchor="w", wraplength=bw + 150, justify="left").pack(anchor="w", pady=(8, 0))
        more = ui.frame(body)
        more.pack(fill="x", pady=(8, 0))
        ui.fold(more, "Cómo se calcula la afinidad", fill, "puntos por apartado", "rec_breakdown", False)

    def vs_row(self, parent, enemy, g, w, size=30):
        ui = self.ui
        row = ui.frame(parent)
        row.pack(fill="x", pady=4)
        ui.champ(row, enemy, size, False).pack(side="left")
        mid = ui.frame(row)
        mid.pack(side="left", fill="x", expand=True, padx=12)
        top = ui.frame(mid)
        top.pack(fill="x")
        ui.lbl(top, name(enemy, ui.champs), 12, "fg", True).pack(side="left")
        ok = w * 2 >= g
        ui.lbl(top, f"{w} de {g} victorias", 11, "good" if ok else "bad", True).pack(side="right")
        ui.bar(mid, [(w / g if g else 0, "good" if ok else "bad")], 5).pack(fill="x", pady=(4, 0))

    def tab_matchup(self, body, c):
        ui, r = self.ui, self.r
        lane, opp = c["lane"], r["lane_opp"]
        if opp:
            ui.lbl(body, f"TU RIVAL DE LÍNEA: {name(opp, ui.champs).upper()}", 10, "dim", True).pack(anchor="w", pady=(0, 4))
            if lane and lane[1]:
                self.vs_row(body, opp, lane[1], lane[2], 40)
            else:
                ui.lbl(body, f"Aún no has jugado con {name(c['cid'], ui.champs)} contra {name(opp, ui.champs)}: no hay datos tuyos de este "
                             "enfrentamiento. Los de todos los jugadores están en la pestaña «Enfrentamiento».", 11, "dim", anchor="w", wraplength=400,
                       justify="left").pack(anchor="w")
        else:
            ui.lbl(body, "Tu rival de línea todavía no ha elegido campeón.", 11, "dim").pack(anchor="w")
        others = [v for v in c["vs"] if v[0] != opp and v[1]][:4]
        if others:
            ui.lbl(body, "CONTRA OTROS RIVALES YA ELEGIDOS", 10, "dim", True).pack(anchor="w", pady=(12, 2))
            for e, g, w in others:
                self.vs_row(body, e, g, w)
        elif not opp and not (lane and lane[1]):   # con rival de línea ya se ha dicho arriba que no hay datos: no se repite
            ui.lbl(body, "Tampoco tienes partidas con este campeón contra los rivales ya elegidos.", 10, "dim").pack(anchor="w", pady=(8, 0))

    def tab_synergy(self, body, c):
        ui = self.ui
        items = c["syn"]["items"]
        if not items:
            ui.lbl(body, "Aún no hay aliados elegidos. Las sinergias aparecerán según vayan eligiendo.", 11, "dim",
                   anchor="w", wraplength=400, justify="left").pack(anchor="w")
            return
        s = c["syn"]["score"]
        level, color = ("Alta", "good") if s >= .35 else ("Media", "info") if s >= 0 else ("Baja", "bad")
        head = ui.frame(body)
        head.pack(fill="x", pady=(0, 8))
        ui.lbl(head, "SINERGIA CON TU EQUIPO", 10, "dim", True).pack(side="left")
        ui.lbl(head, level, 14, color, True, True).pack(side="right")
        for it in sorted(items, key=lambda i: -i["score"]):
            row = ui.frame(body)
            row.pack(fill="x", pady=4)
            ui.champ(row, it["ally"], 34, False).pack(side="left")
            mid = ui.frame(row)
            mid.pack(side="left", fill="x", expand=True, padx=12)
            top = ui.frame(mid)
            top.pack(fill="x")
            ui.lbl(top, name(it["ally"], ui.champs), 12, "fg", True).pack(side="left")
            if it["record"]:
                g, w = it["record"]
                ui.lbl(top, f"juntos: {w} de {g}", 10, "good" if w * 2 >= g else "bad", True).pack(side="right")
            txt = it["text"] or "Sin una sinergia destacable."
            ui.lbl(mid, txt, 10, "good" if it["score"] >= .3 else "bad" if it["score"] < 0 else "dim", anchor="w", wraplength=330,
                   justify="left").pack(anchor="w")

    def tab_meta(self, body, c):
        ui, mi, m = self.ui, self.r["meta_info"], c["meta"]
        if m and mi:
            row = ui.frame(body)
            row.pack(fill="x", pady=(0, 8))
            ui.kpi(row, f"{pct_es(m['wr'])} %", "victorias")
            ui.kpi(row, f"{pct_es(m['pr'])} %", "uso")
            ui.kpi(row, f"{pct_es(m['br'])} %", "baneos")
            ui.kpi(row, f"{m['games'] / 1000:.0f} k" if m["games"] >= 1000 else str(m["games"]), "partidas")
            d = m["wr"] - mi["avg"]
            ui.lbl(body, f"Parche {mi['patch']}{' (el ' + mi['current'] + ' aún no tiene datos suficientes)' if mi['stale'] else ''} · {mi['tier_name']} · media de la línea {pct_es(mi['avg'])} % "
                         f"({'+' if d >= 0 else '−'}{pct_es(abs(d))} puntos)", 10, "dim", anchor="w", wraplength=400,
                   justify="left").pack(anchor="w", pady=(0, 8))
        elif self.kind() == "sr":
            why = ("El meta del parche está desactivado: actívalo en «Datos» (se abre desde Ajustes)." if not ui.conf.get("meta_enabled", True)
                   else "El meta del parche aún se está descargando; aparecerá solo en unos segundos." if not core.META.get("data")
                   else "Este campeón casi no se juega en tu línea este parche: no hay datos de meta fiables.")
            ui.lbl(body, why, 10,
                   "dim", anchor="w", wraplength=400, justify="left").pack(anchor="w", pady=(0, 8))
        lane = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support"}.get(self.r.get("role"))
        if self.kind() == "sr" and lane:
            build_panel(ui, body, c["cid"], lane, self.r.get("lane_opp") or None, min(self.width - 120, 720), self.r.get("enemy_stats")).pack(fill="x", pady=(2, 8))
        ui.lbl(body, "CONSEJOS SEGÚN LA COMPOSICIÓN", 10, "dim", True).pack(anchor="w", pady=(2, 2))
        for title, text in c["build"]:
            row = ui.frame(body)
            row.pack(fill="x", pady=4)
            ui.lbl(row, title.upper(), 9, ui.acc, True, width=96, anchor="w").pack(side="left", anchor="n")
            ui.lbl(row, text, 11, "fg", anchor="w", wraplength=300, justify="left").pack(side="left", fill="x", expand=True)
        ui.lbl(body, "Consejos orientativos según la composición actual. No sustituyen a la build recomendada del parche.", 9,
               "dim", anchor="w", wraplength=max(220, min(400, self.width - 130)), justify="left").pack(anchor="w", pady=(8, 0))
        champ = ui.champs[c["cid"]]
        links = ui.frame(body)
        links.pack(anchor="w", pady=(8, 0))
        small_btn(ui, links, "Builds de especialistas (OneTricks)",
                  lambda: open_url(f"https://www.onetricks.gg/es/champions/builds/{champ['icon']}"), 220).pack(side="left", padx=(0, 8))
        lane = matchups.LANES.get(self.r["role"])
        if lane:
            small_btn(ui, links, "Meta en Lolalytics", lambda: open_url(f"https://lolalytics.com/lol/{matchups.slug(champ)}/build/?lane={lane}"),
                      130).pack(side="left")


class Lobby(Section):
    """Tu equipo: quién es cada aliado, su rango, su forma reciente y cómo le va con el campeón que ha elegido."""

    def key(self, ctx):
        r, pl = ctx["r"], ctx["players"]
        return (tuple((a["cell"], a["champ"], a["role"], a["puuid"], bool(a.get("hover"))) for a in r["ally_cells"]),
                tuple(sorted((k, v.get("name", ""), len(v.get("recent", [])), bool(v.get("error"))) for k, v in pl.items())),
                tuple(r["party"]), self.ui.conf["show_teams"], r["mode"]["kind"], json.dumps(r["mates"], sort_keys=True))

    def build(self, ctx):
        ui, r, pl = self.ui, ctx["r"], ctx["players"]
        if not ui.conf["show_teams"] or not r["ally_cells"]:
            return
        st0 = r["ally_stats"]
        summ = f"{len(r['ally_cells'])} {'aliado' if len(r['ally_cells']) == 1 else 'aliados'}" + (f" · físico {st0['ad']} / mágico {st0['ap']} · control {ctl(st0['cc'])}" if st0 and st0["ad"] + st0["ap"] else "")
        ui.fold(self.box, "Tu equipo", lambda c: self.fill(c, ctx), summ, "sel_team", False)

    def fill(self, c, ctx):
        ui, r, pl = self.ui, ctx["r"], ctx["players"]
        party = set(r["party"])
        if r["mode"]["kind"] != "sr":  # sin roles ni perfiles: solo los campeones que lleva el equipo
            row = ui.frame(c)
            row.pack(anchor="w")
            for a in r["ally_cells"]:
                ui.champ(row, a["champ"], 44, True, (ui.hexm(PAL["warn"]) if a.get("hover") else "#3ddc84") if a["champ"] else None).pack(side="left", padx=4)
            if any(a.get("hover") for a in r["ally_cells"]):
                ui.lbl(c, "Los marcados en naranja aún no han bloqueado su campeón.", 10, "dim", anchor="w").pack(anchor="w", pady=(4, 0))
        else:
            for a in r["ally_cells"]:
                p = pl.get(a["puuid"]) if a["puuid"] else None
                self.row(c, a, p, a["puuid"] in party, len(party), bool(pl) or not a["puuid"], r["mates"].get(a["puuid"]), qid=r["mode"]["id"])
            if r["ally_cells"] and not any(a["puuid"] for a in r["ally_cells"]):
                ui.lbl(c, "En esta cola Riot oculta los nombres hasta que empieza la partida, así que no hay rango ni historial de tus aliados. "
                          "Se muestran su línea y su campeón.", 10, "dim", anchor="w", justify="left", wraplength=max(260, ctx["width"] - 110)).pack(anchor="w", pady=(2, 8))
        st = r["ally_stats"]
        if st and st["ad"] + st["ap"]:
            tot = st["ad"] + st["ap"]
            ui.bar(c, [(st["ad"] / tot, "warn"), (st["ap"] / tot, "info")], 7).pack(fill="x", pady=(8, 4))
            ui.lbl(c, f"Daño físico {st['ad']} · mágico {st['ap']}   ·   Tanques {st['tanks']}   ·   Control {ctl(st['cc'])}", 10,
                   "dim", anchor="w").pack(anchor="w")

    def row(self, parent, a, p, in_party, party_n, loaded, mates=None, ring="#3ddc84", qid=0, tag=None):
        ui = self.ui
        box = ctk.CTkFrame(parent, fg_color=PAL["card2"], corner_radius=12)
        box.pack(fill="x", pady=4)
        inner = ui.frame(box)
        inner.pack(fill="x", padx=12, pady=12)
        ring = ui.hexm(PAL["warn"]) if a.get("hover") else ring   # marcado y sin bloquear: aro naranja y la etiqueta «Sin confirmar»
        ui.champ(inner, a["champ"], 44, False, ring if a["champ"] else None).pack(side="left", anchor="n")
        mid = ui.frame(inner)
        mid.pack(side="left", fill="x", expand=True, padx=12)
        head = ui.frame(mid)
        head.pack(fill="x")
        nm = (p or {}).get("name") or ("Nombre oculto" if not a["puuid"] else "Cargando…")
        ui.lbl(head, nm, 13, "fg", True).pack(side="left")
        rk = None
        if p and not p.get("error"):   # el rango se coloca antes que las etiquetas: con varias («Dúo», «Juntos…») se quedaba sin sitio y no salía
            rk = (p.get("prem") if qid == 710 else None) or p.get("solo") or p.get("flex")   # en las clasificatorias de 5 cuenta su rango de esa cola
            if rk:
                ui.lbl(head, f"{rk['tier']} {rk['div']}".strip(), 12, TIER_COLORS.get(rk["key"], "fg"), True, True).pack(side="right", padx=(8, 0))
        if ROLES_ES.get(a["role"]):
            ui.chip(head, ROLES_ES[a["role"]], "dim").pack(side="left", padx=(8, 0))
        if a.get("hover"):
            ui.chip(head, "Sin confirmar", "warn").pack(side="left", padx=(8, 0))
        if tag:
            ui.chip(head, tag, "warn").pack(side="left", padx=(8, 0))
        if in_party:
            ui.chip(head, "Dúo contigo" if party_n == 1 else "Tu grupo", "info").pack(side="left", padx=(8, 0))
        if mates and mates[0]:
            g, w = mates
            ui.chip(head, f"Juntos {w}V {g - w}D", "good" if w * 2 >= g else "bad").pack(side="left", padx=(8, 0))
        if p and not p.get("error"):
            if not rk and len(p.get("recent", [])) < 4:
                ui.chip(head, "Sin rango ni historial", "warn").pack(side="right")
            line = ui.frame(mid)
            line.pack(fill="x", pady=(4, 0))
            rec = p["recent"]
            if rec:
                ui.dots(line, [x["w"] for x in rec]).pack(side="left")
                w = sum(x["w"] for x in rec)
                ui.lbl(line, f"  {w}V {len(rec) - w}D", 10, "dim").pack(side="left")
            champ_name = name(a["champ"], ui.champs) if a["champ"] else ""
            if a["champ"]:
                pts = p["mastery"].get(a["champ"], 0)
                txt = f"Maestría {pts // 1000}k con {champ_name}" if pts >= 1000 else f"Primera vez con {champ_name}"
                ui.chip(line, txt, "good" if pts >= 50000 else "warn" if pts < 1000 else "info").pack(side="right")
            line2 = ui.frame(mid)
            line2.pack(fill="x", pady=(4, 0))
            for cid in p["top"][:3]:
                ui.champ(line2, cid, 22, False).pack(side="left", padx=(0, 4))
            extra = []
            if p["roles"]:
                extra.append("Suele jugar: " + ", ".join(ROLES_ES.get(x, x).lower() for x in p["roles"]))
            if p["wr10"] is not None and len(p["recent"]) >= 6:
                extra.append("racha negativa" if p["wr10"] < .4 else "en buena racha" if p["wr10"] >= .65 else "")
            ui.lbl(line2, "  ·  ".join(x for x in extra if x), 10, "dim").pack(side="left", padx=4)
            profile_toggle(self, box, inner, mid, a, p, qid)
        elif p and p.get("error"):
            ui.lbl(mid, "El cliente no ha entregado sus datos (perfil oculto o sin respuesta).", 10, "dim").pack(anchor="w")
        elif not loaded:
            ui.lbl(mid, "Cargando datos del jugador…", 10, "dim").pack(anchor="w", pady=(4, 0))


def profile_toggle(self, box, inner, mid, a, p, qid):
    """«Perfil completo»: despliega bajo la tarjeta todo lo que el cliente sabe del jugador (ui_player.py). Recuerda qué perfiles estaban abiertos."""
    import ui_player
    ui = self.ui
    opened = ui.__dict__.setdefault("open_prof", set())
    key = a.get("puuid") or ""
    det = ui.frame(box)
    lab = ui.lbl(mid, "", 10, "info", True)
    lab.pack(anchor="w", pady=(8, 0))

    def paint():
        if key in opened:
            lab.configure(text="▾ Ocultar perfil")
            det.pack(fill="x", padx=12, pady=(0, 12))
            if not det.winfo_children():
                ui_player.build(ui, det, p, qid, getattr(self, "width", 520))
        else:
            lab.configure(text="▸ Perfil completo")
            det.pack_forget()

    def toggle(_e=None):
        opened.symmetric_difference_update({key})
        paint()
    lab.configure(cursor="hand2")
    lab.bind("<Button-1>", toggle)
    paint()




class Enemies(Section):
    def key(self, ctx):
        r = ctx["r"]
        pl = ctx["players"]
        return (tuple(r["enemies"]), ctx["session"]["theirTeam"] and len(ctx["session"]["theirTeam"]), self.ui.conf["show_teams"],
                self.ui.conf["compact"], r["mode"]["kind"], tuple((e["cell"], e["champ"], e["puuid"]) for e in r["enemy_cells"]),
                tuple(sorted((k, v.get("name", ""), len(v.get("recent", [])), bool(v.get("error"))) for k, v in pl.items() if k in {e["puuid"] for e in r["enemy_cells"]})))

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        if ui.conf["compact"] or not ui.conf["show_teams"]:
            return
        if r["mode"]["kind"] != "sr" and not r["enemies"]:  # Arena, personalizadas, ARAM: sin rivales conocidos no hay nada que enseñar
            return
        st0 = r["enemy_stats"]
        named = any(e["puuid"] for e in r["enemy_cells"])
        summ = f"{len(r['enemies'])} de 5 elegidos" + (" · con sus nombres" if named else "") + (f" · físico {st0['ad']} / mágico {st0['ap']}" if st0 and st0["ad"] + st0["ap"] else "")
        ui.fold(self.box, "Equipo rival", lambda c: self.fill(c, ctx), summ, "sel_enemy", True)

    def fill(self, c, ctx):
        ui, r = self.ui, ctx["r"]
        row = ui.frame(c)
        row.pack(fill="x")
        icons = ui.frame(row)
        icons.pack(side="left")
        for i in range(5):
            ui.champ(icons, r["enemies"][i] if i < len(r["enemies"]) else 0, 48, True, "#ff5a5f").pack(side="left", padx=4)
        st = r["enemy_stats"]
        if st:
            narrow = ctx["width"] < 640
            info = ui.frame(c if narrow else row)
            if narrow:
                info.pack(fill="x", pady=(6, 0))
            else:
                info.pack(side="left", padx=16, fill="x", expand=True, anchor="n")
            tot = st["ad"] + st["ap"]
            if tot:
                ui.bar(info, [(st["ad"] / tot, "warn"), (st["ap"] / tot, "info")], 7).pack(fill="x", pady=(4, 4))
            ui.lbl(info, f"Daño físico {st['ad']}  ·  mágico {st['ap']}", 10, "dim", anchor="w").pack(anchor="w")
            ui.lbl(info, f"Tanques {st['tanks']}  ·  control {ctl(st['cc'])}", 10, "dim", anchor="w").pack(anchor="w")
            if st["tip"]:
                ui.lbl(info, st["tip"], 10, "warn", True, anchor="w", wraplength=230, justify="left").pack(anchor="w", pady=(2, 0))
        # con los nombres visibles se ve quién es cada rival: rango, forma reciente, campeones que más juega y maestría con el que elige
        pl = ctx["players"]
        cells = [e for e in r["enemy_cells"] if e["puuid"]]
        if cells and r["mode"]["kind"] == "sr":
            ui.lbl(c, "JUGADORES RIVALES", 10, "dim", True).pack(anchor="w", pady=(12, 2))
            import draft5
            roles = draft5.infer_roles(r["enemy_cells"], pl, ui.champs) if draft5.is_draft(r) else {}
            for e in cells:
                Lobby.row(self, c, {"champ": e["champ"], "role": roles.get(e["puuid"], ""), "puuid": e["puuid"]}, pl.get(e["puuid"]), False, 0,
                          bool(pl), None, "#ff5a5f", r["mode"]["id"])


class CounterPicks(Section):
    """«Mejores contra tus rivales»: para tu rival de línea (y, abajo, para el resto de rivales ya elegidos) los campeones que más le ganan según Lolalytics,
    con las partidas de cada cruce. Va aparte de la afinidad (que mezcla tu historial, tu equipo y el parche): aquí solo cuenta el enfrentamiento.
    Solo se fía de cruces con muestra suficiente (MIN partidas); si no hay tres, baja el listón y lo dice."""
    MIN, FALLBACK = 200, 50
    LANE_OF = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "UTILITY": "support", "SUPPORT": "support"}

    def targets(self, ctx):
        r, champs = ctx["r"], self.ui.champs
        out = []
        lane = matchups.LANES.get(r.get("role") or "")
        if r.get("lane_opp") and lane:
            out.append((r["lane_opp"], lane, True))
        md = core.META.get("data") if hasattr(core, "META") else None
        for cid in r["enemies"]:
            if cid == r.get("lane_opp") or cid not in champs:
                continue
            pos = (champs[cid].get("pos") or [])
            shares = core.metamod.lane_shares(md, cid) if md else {}
            if shares:   # la línea donde más se juega este parche
                ln = self.LANE_OF.get(max(shares, key=shares.get))
            else:   # sin meta: solo si el campeón tiene una única posición (el orden de `pos` es alfabético, no de uso)
                ln = self.LANE_OF.get(pos[0]) if len(pos) == 1 else None
            if ln and not any(t[0] == cid for t in out):
                out.append((cid, ln, False))
        return out

    def key(self, ctx):
        if ctx["r"]["mode"]["kind"] != "sr":
            return ("no",)
        t = self.targets(ctx)
        return (tuple(t), tuple(str(Recs.COUNTERS.get((c, ln)))[:14] for c, ln, _ in t), self.ui.conf["compact"], len((ctx.get("info") or {}).get("owned") or ()), ctx["width"] // 150, self.shown(ctx))

    def shown(self, ctx):
        """Qué campeones se van a enseñar en cada fila (ya sin baneados ni elegidos): la tarjeta solo se repinta si esto cambia, no con cada marca de un aliado o un ban que no la toca."""
        r = ctx["r"]
        gone = set(r["bans"]) | set(r["allies"]) | set(r["enemies"])
        owned = set((ctx.get("info") or {}).get("owned") or [])
        out = []
        for cid, lane, mine in self.targets(ctx):
            st = Recs.COUNTERS.get((cid, lane))
            if not isinstance(st, list):
                out.append(None)
                continue
            st = [x for x in st if x["cid"] not in gone]
            good = [x for x in st if x["games"] >= self.MIN]
            low = len(good) < 3
            rows = (good if not low else [x for x in st if x["games"] >= self.FALLBACK])[:5 if mine else 3]
            best = next((x for x in (good if not low else st) if x["cid"] in owned), None) if owned and mine else None
            out.append((tuple(x["cid"] for x in rows), best["cid"] if best else 0, low))
        return tuple(out)

    def fetch(self, cid, lane):
        key = (cid, lane)
        st = Recs.COUNTERS.get(key)
        if isinstance(st, tuple) and time.time() - st[2] > 90:
            st = None
        if st is None:
            Recs.COUNTERS[key] = "cargando"
            ui = self.ui

            def go():
                try:
                    rows = matchups.best_against(ui.champs, cid, lane, core.CACHE, min_games=50)
                except Exception as e:
                    rows = ("error", str(e), time.time())
                    t_ = threading.Timer(95, lambda: (Recs.COUNTERS.pop(key, None), ui.notify("recs_data")))   # reintento solo (sin tocar Tk desde otro hilo)
                    t_.daemon = True
                    t_.start()
                Recs.COUNTERS[key] = rows
                ui.notify("recs_data")
            threading.Thread(target=go, daemon=True).start()
            return "cargando"
        return st

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        if r["mode"]["kind"] != "sr" or ui.conf["compact"]:
            return
        tg = self.targets(ctx)
        if not tg:
            return
        owned = set((ctx.get("info") or {}).get("owned") or [])
        c = ui.card(self.box)
        head = ui.frame(c)
        head.pack(fill="x", pady=(0, 6))
        ctk.CTkFrame(head, width=3, height=14, corner_radius=2, fg_color=ui.acc).pack(side="left", padx=(0, 8))
        ui.lbl(head, "MEJORES CAMPEONES CONTRA TUS RIVALES", 10, "fg", True).pack(side="left")
        ui.reg("sel.contra_rivales", head)
        ui.lbl(c, "Solo cuenta el enfrentamiento (Lolalytics, todos los jugadores): no usa tu historial ni tu equipo, a diferencia de la afinidad.", 9, "dim",
               anchor="w", justify="left", wraplength=max(260, ctx["width"] - 110)).pack(anchor="w", pady=(0, 6))
        cols = 2 if ctx["width"] < 620 else 3 if ctx["width"] < 980 else 5
        for cid, lane, mine in tg:
            ln = matchups.LANE_NAMES.get(lane, lane)
            row = ui.frame(c)
            row.pack(fill="x", pady=(8, 2))
            ui.champ(row, cid, 28, False, "#ff5a5f").pack(side="left", padx=(0, 8))
            ui.lbl(row, ("Tu rival de línea: " if mine else "") + name(cid, ui.champs), 12, "fg", True).pack(side="left")
            ui.lbl(row, f"   {ln.lower()}" + ("" if mine else " · según su línea habitual"), 10, "dim").pack(side="left")
            st = self.fetch(cid, lane)
            if st == "cargando":
                ui.lbl(c, "Cargando…", 10, "dim", anchor="w").pack(anchor="w")
                continue
            if isinstance(st, tuple):
                ui.lbl(c, "Ahora mismo no hay datos de este enfrentamiento (Lolalytics no responde o aún no los tiene). Se reintenta solo.", 10, "dim", anchor="w", justify="left",
                       wraplength=max(260, ctx["width"] - 110)).pack(anchor="w")
                continue
            n = 5 if mine else 3
            gone = set(r["bans"]) | set(r["allies"]) | set(r["enemies"])   # baneados o ya elegidos: no se pueden coger
            st = [x for x in st if x["cid"] not in gone]
            good = [x for x in st if x["games"] >= self.MIN]
            low = len(good) < 3
            rows = (good if not low else [x for x in st if x["games"] >= self.FALLBACK])[:n]
            if not rows:
                ui.lbl(c, "Ningún campeón tiene partidas suficientes contra él en este parche.", 10, "dim", anchor="w").pack(anchor="w")
                continue
            grid = tk.Frame(c, bg=ui.bg(c))
            grid.pack(fill="x")
            for k in range(cols):
                grid.columnconfigure(k, weight=1, uniform="cp")
            card, fg, dim = ui.hexm(PAL["card2"]), ui.hexm(PAL["fg"]), ui.hexm(PAL["dim"])
            for i, x in enumerate(rows):
                cell = tk.Frame(grid, bg=card)
                cell.grid(row=i // cols, column=i % cols, sticky="ew", padx=3, pady=3)
                ph = ui.champ_photo(x["cid"], 34)
                ic = tk.Label(cell, image=ph, bd=0, bg=card) if ph is not None else tk.Frame(cell, width=34, height=34, bg=ui.hexm(PAL["card"]))
                ic.image = ph
                ic.pack(side="left", padx=(8, 8), pady=8)
                mid = tk.Frame(cell, bg=card)
                mid.pack(side="left", fill="x", expand=True)
                tk.Label(mid, text=f"{i + 1}. {name(x['cid'], ui.champs)}", font=ui.tkf(11, True, False), fg=fg, bg=card, anchor="w").pack(anchor="w")
                tk.Label(mid, text=f"{x['games']:,} partidas".replace(",", ".") + ("  ·  lo tienes" if x["cid"] in owned else ""), font=ui.tkf(9, False, False),
                         fg=dim, bg=card, anchor="w").pack(anchor="w")
                tk.Label(cell, text=f"{x['wr']:.1f} %".replace(".", ","), font=ui.tkf(13, True, True), fg=ui.hexm(PAL["good" if x["wr"] >= 50 else "bad"]),
                         bg=card).pack(side="right", padx=10)
            mine_best = next((x for x in (good if not low else st) if x["cid"] in owned), None) if owned and mine else None
            if mine_best and mine_best["cid"] not in [x["cid"] for x in rows]:
                wr_txt, g_txt = f"{mine_best['wr']:.1f}".replace(".", ","), f"{mine_best['games']:,}".replace(",", ".")
                ui.lbl(c, f"El mejor que tienes: {name(mine_best['cid'], ui.champs)} ({wr_txt} % en {g_txt} partidas)", 10, "info", anchor="w").pack(anchor="w", pady=(2, 0))
            if low:
                ui.lbl(c, f"Pocas partidas con cada cruce (mínimo {self.FALLBACK}): tómalo como orientativo.", 9, "warn", anchor="w").pack(anchor="w")


class BansRow(Section):
    def key(self, ctx):
        return (tuple(ctx["r"]["bans"]), self.ui.conf["show_bans"], self.ui.conf["compact"])

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        if ui.conf["compact"] or not ui.conf["show_bans"] or not r["bans"]:
            return
        ui.fold(self.box, "Campeones baneados", lambda c: self.fill(c, ctx), f"{len(r['bans'])} {'baneado' if len(r['bans']) == 1 else 'baneados'}", "sel_bans", False)

    def fill(self, c, ctx):
        ui, r = self.ui, ctx["r"]
        row = ui.frame(c)
        row.pack(anchor="w")
        for cid in r["bans"]:
            ui.champ(row, cid, 34, False, "#ff5a5f").pack(side="left", padx=4)
