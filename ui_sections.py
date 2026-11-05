"""Secciones independientes de la ventana de LOL-E.

Cada sección calcula una clave con los datos que usa; si la clave no cambia, no se toca. Así, cuando llega
un dato nuevo (un aliado que elige, un jugador que carga…) solo se repinta su parte y no toda la pantalla.
"""
import json, os, tkinter as tk
from collections import Counter

import customtkinter as ctk
from PIL import Image

import history
import lol_advisor as core
from players import TIERS_ES
from ui_build import build_panel
from ui_pool import PoolPanel
from lol_advisor import name
import matchups
from ui_kit import PAL, TIER_COLORS, ROLES_ES, PHASES, ON_FILL, col, hexc, partidas, pct_es
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
        for w in self.box.winfo_children():
            w.destroy()
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
    inner.pack(fill="x", padx=12, pady=10)
    ui.lbl(inner, title.upper(), 9, "dim", True).pack(anchor="w")
    row = ui.frame(inner)
    row.pack(anchor="w", pady=(4, 0))
    if rk:
        em = ui.emblem(rk["key"], 44)
        if em:
            ctk.CTkLabel(row, image=em, text="").pack(side="left", padx=(0, 10))
        txt = ui.frame(row)
        txt.pack(side="left")
        ui.lbl(txt, f"{rk['tier']} {rk['div']}".strip(), 15, TIER_COLORS.get(rk["key"], "fg"), True, True).pack(anchor="w")
        ui.lbl(txt, f"{rk['lp']} PL  ·  {rk['w']}V {rk['l']}D  ·  {rk['wr'] * 100:.0f} %", 10, "dim", anchor="w", wraplength=170,
               justify="left").pack(anchor="w")
    else:
        ui.lbl(row, "Sin clasificar", 13, "dim", True).pack(anchor="w", pady=10)
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
        top = ui.frame(c)
        top.pack(fill="x")
        img = ui.profile_icon(pr["icon"], 56) if pr.get("icon") else None
        if img:
            ctk.CTkLabel(top, image=img, text="").pack(side="left", padx=(0, 14))
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


class WaitCard(Section):
    def key(self, ctx):
        return (ctx["msg"], ctx["linked"])

    def build(self, ctx):
        ui = self.ui
        c = ui.card(self.box, pad=4)
        row = ui.frame(c)
        row.pack(fill="x")
        ui.lbl(row, "●", 12, "good" if ctx["linked"] else "warn").pack(side="left", padx=(0, 8))
        ui.lbl(row, "Esperando la selección de campeón", 13, "fg", True, True).pack(side="left")
        hint = ("Se activa sola al entrar en la selección." if ctx["linked"]
                else "1. Abre League of Legends   2. Entra en una cola   3. Esta ventana se activa sola")
        ui.lbl(row, hint, 10, "dim").pack(side="right")
        if ctx["msg"] and "Conectado al cliente" not in ctx["msg"]:
            ui.lbl(c, ctx["msg"], 10, "dim", anchor="w").pack(anchor="w", pady=(4, 0))


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
            games = [e for e in history.load_all(os.path.join(core.CACHE, "history.json"), os.path.join(core.CACHE, "games.json"))
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

    def tile(self, grid, i, cols, label, value, sub="", color="fg"):
        ui = self.ui
        cell = ctk.CTkFrame(grid, fg_color=PAL["card2"], corner_radius=12)
        cell.grid(row=i // cols, column=i % cols, sticky="nsew", padx=4, pady=4)
        inner = ui.frame(cell)
        inner.pack(fill="x", padx=12, pady=10)
        wl = getattr(self, "tile_wl", 200)
        ui.lbl(inner, label.upper(), 9, "dim", True, anchor="w", wraplength=wl, justify="left").pack(anchor="w")
        ui.lbl(inner, value, 15, color, True, True, anchor="w", wraplength=wl, justify="left").pack(anchor="w", pady=(3, 0))
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
        cols = 2 if ctx["width"] < 600 else 3 if ctx["width"] < 960 else 4
        self.tile_wl = max(100, min(220, (ctx["width"] - 110) // cols - 34))  # el texto se ajusta al ancho de cada ficha
        grid = ui.frame(c)
        grid.pack(fill="x")
        for k in range(cols):
            grid.columnconfigure(k, weight=1, uniform="lg")
        for i, (label, value, sub, color) in enumerate(tiles):
            self.tile(grid, i, cols, label, value, sub, color)
        ui.lbl(c, "Datos de tu cliente de LoL. La posición exacta en el ranking de tu servidor no la da el cliente; el porcentaje de los "
                  "retos sí es de tu servidor.", 9, "dim", anchor="w", wraplength=min(ctx["width"] - 90, 760), justify="left").pack(
            anchor="w", pady=(6, 0))


def history_fecha(ms):
    return history_fecha_full(ms, False)[:5]


class SummaryCard(Section):
    """Resumen interactivo de la pantalla principal: rango y logros, modos y repertorio en una sola tarjeta con pestañas.

    Cada ficha enseña una previsualización al pasar el ratón y, al pulsarla, un detalle que se despliega con animación.
    """
    TABS = ["Rango y logros", "Modos", "Repertorio"]
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
            self.hist = [e for e in history.load_all(os.path.join(core.CACHE, "history.json"), os.path.join(core.CACHE, "games.json"))
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
                json.dumps(info.get("pool"), default=str), json.dumps(self.streaks()), ctx["width"] // 300)

    # ---- estructura ----
    def build(self, ctx):
        ui = self.ui
        self.ctx, self.sel, self.tiles = ctx, None, {}
        c = ui.card(self.box)
        ui.seg(c, self.TABS, self.tab, self.switch, height=30).pack(fill="x")
        self.body = ui.frame(c)
        self.body.pack(fill="x", pady=(10, 0))
        self.paint_tab(False)

    def switch(self, name):
        if name == self.tab:
            return
        self.tab, self.sel, self.tiles = name, None, {}
        self.paint_tab(True)

    def paint_tab(self, animate):
        ui = self.ui
        for w in self.body.winfo_children():
            w.destroy()
        fn = {"Rango y logros": self.tab_logros, "Modos": self.tab_modos, "Repertorio": self.tab_pool}[self.tab]
        if animate and ui.anim_on():
            ui.reveal(self.body, fn)
        else:
            fn(self.body)

    def cols(self, small=2, mid=3, big=4):
        w = self.ctx["width"]
        return small if w < 600 else mid if w < 960 else big

    # ---- ficha con previsualización y pulsación ----
    def tile(self, grid, i, cols, key, label, value, sub="", color="fg", preview=""):
        ui = self.ui
        cell = ctk.CTkFrame(grid, fg_color=PAL["card2"], corner_radius=12, border_width=1, border_color=PAL["card2"])
        cell.grid(row=i // cols, column=i % cols, sticky="nsew", padx=4, pady=4)
        inner = ui.frame(cell)
        inner.pack(fill="x", padx=12, pady=10)
        wl = max(100, min(220, (self.ctx["width"] - 110) // cols - 40))
        head = ui.frame(inner)
        head.pack(fill="x")
        ui.lbl(head, label.upper(), 9, "dim", True, anchor="w", wraplength=wl, justify="left").pack(side="left")
        ui.lbl(head, "▸", 9, "dim").pack(side="right")
        ui.lbl(inner, value, 15, color, True, True, anchor="w", wraplength=wl, justify="left").pack(anchor="w", pady=(3, 0))
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
        for w in self.slot.winfo_children():
            w.destroy()
        if same:
            return
        fn = self.details.get(key)
        if fn is None:
            return
        wrap = ctk.CTkFrame(self.slot, fg_color=PAL["card2"], corner_radius=12)
        wrap.pack(fill="x", padx=4, pady=(4, 2))
        holder = ui.frame(wrap)
        holder.pack(fill="x", padx=14, pady=12)
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
        if ex.get("peak"):
            p = ex["peak"]
            tiles.append(("peak", "Mejor rango de la temporada", f"{p['tier']} {p['div']}".strip(), "tu punto más alto este año",
                          TIER_COLORS.get(p["key"], "fg"), "Pulsa para ver tus rangos y cuánto te falta para subir"))
            self.details["peak"] = self.d_rank
        if ex.get("prev"):
            p = ex["prev"]
            tiles.append(("prev", "Temporada anterior", f"{p['tier']} {p['div']}".strip(), "rango con el que acabaste",
                          TIER_COLORS.get(p["key"], "fg"), "Pulsa para ver tus rangos"))
            self.details["prev"] = self.d_rank
        ch = ex.get("challenges")
        if ch:
            lv = TIERS_ES.get(ch["level"], ch["level"].title())
            sub = (f"Entre el {es(ch['pct'])} % mejor · " if ch.get("pct") is not None else "") + f"{miles(ch['points'])} puntos"
            tiles.append(("ch", "Retos", lv, sub, TIER_COLORS.get(ch["level"], "fg"), "Pulsa para ver tus 5 categorías de Retos"))
            self.details["ch"] = self.d_challenges
            cats = [c for c in ch.get("cats", []) if c.get("pct") is not None]
            if cats:
                b = min(cats, key=lambda c: c["pct"])
                tiles.append(("cat", "Tu mejor categoría de retos", self.CATS.get(b["cat"], b["cat"].title()),
                              f"{TIERS_ES.get(b['level'], b['level'].title())} · entre el {es(b['pct'])} % mejor",
                              TIER_COLORS.get(b["level"], "fg"), "Pulsa para ver todas las categorías"))
                self.details["cat"] = self.d_challenges
        if ex.get("mastery_score"):
            tiles.append(("mast", "Maestría total", miles(ex["mastery_score"]), "suma de los niveles de tus campeones", "fg",
                          "Pulsa para ver tus campeones con más maestría"))
            self.details["mast"] = self.d_mastery
        if ex.get("honor") is not None:
            tiles.append(("honor", "Nivel de honor", str(ex["honor"]), "cómo te valoran tus compañeros", "fg", "Pulsa para ver tu nivel de honor"))
            self.details["honor"] = self.d_honor
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
            self.tile(grid, i, cols, key, label, value, sub, color, prev)
        self.slot = ui.frame(parent)
        self.slot.pack(fill="x")
        ui.lbl(parent, "Datos de tu cliente de LoL. Pulsa cualquier ficha para ver el detalle. La posición exacta en el ranking de tu servidor "
                       "no la da el cliente; el porcentaje de los retos sí es de tu servidor.", 9, "dim", anchor="w",
               wraplength=min(self.ctx["width"] - 90, 760), justify="left").pack(anchor="w", pady=(6, 0))

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

    def d_rank(self, parent):
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
                mini_bar(ui, box, min(rk["lp"], 100) / 100, "good", 200, 6).pack(anchor="w", pady=(3, 2))
                ui.lbl(box, f"Te faltan {max(0, 100 - rk['lp'])} PL para {nxt}", 10, "dim", anchor="w").pack(anchor="w")
            else:
                ui.lbl(box, f"{rk['w']}V {rk['l']}D · {round(rk['wr'] * 100)} %", 10, "dim", anchor="w").pack(anchor="w")
        lines = []
        if ex.get("peak"):
            lines.append(f"Tu mejor rango de esta temporada: {ex['peak']['tier']} {ex['peak']['div']}".strip())
        if ex.get("prev"):
            lines.append(f"Acabaste la temporada anterior en {ex['prev']['tier']} {ex['prev']['div']}".strip())
        if lines:
            ui.lbl(parent, "  ·  ".join(lines), 10, "dim", anchor="w", wraplength=min(self.ctx["width"] - 130, 700), justify="left").pack(anchor="w", pady=(6, 0))

    def d_challenges(self, parent):
        ui = self.ui
        ch = (self.ex or {}).get("challenges") or {}
        es = lambda x: f"{x:.1f}".replace(".", ",")
        for c in sorted(ch.get("cats", []), key=lambda c: (c.get("pct") is None, c.get("pct") or 0)):
            row = ui.frame(parent)
            row.pack(fill="x", pady=3)
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
                anchor="w", pady=(6, 0))

    def d_mastery(self, parent):
        ui = self.ui
        top = (self.ctx["info"] or {}).get("mastery_top") or []
        if not top:
            ui.lbl(parent, "Sin datos de maestría por campeón.", 11, "dim").pack(anchor="w")
            return
        mx = max(p for _, p in top) or 1
        for cid, pts in top[:6]:
            row = ui.frame(parent)
            row.pack(fill="x", pady=3)
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
        ui.dots(parent, [e["w"] for e in games[::-1]], 12).pack(anchor="w", pady=(4, 6))
        w = sum(1 for e in games if e["w"])
        ui.lbl(parent, f"{w} victorias y {len(games) - w} derrotas ({round(w / max(1, len(games)) * 100)} %). Mejor racha de victorias guardada: "
                       f"{st.get('best', 0)}. Partidas guardadas: {st.get('n', 0)}.", 10, "dim", anchor="w", justify="left",
               wraplength=min(self.ctx["width"] - 130, 640)).pack(anchor="w")

    # ---- pestaña: modos ----
    def tab_modos(self, parent):
        ui = self.ui
        modes = (self.ctx["info"] or {}).get("modes") or []
        self.slot = None
        if not modes:
            ui.lbl(parent, "Aún no hay partidas guardadas por modo.", 11, "dim").pack(anchor="w")
            return
        self.mode_slots = {}
        for m in modes:
            box = ui.frame(parent)
            box.pack(fill="x")
            row = ctk.CTkFrame(box, fg_color=PAL["card2"], corner_radius=10, border_width=1, border_color=PAL["card2"])
            row.pack(fill="x", pady=3)
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
        wrap.pack(fill="x", padx=8, pady=(0, 6))
        holder = ui.frame(wrap)
        holder.pack(fill="x", padx=12, pady=10)

        def fill(p):
            s = history.summary(games)
            if not games:
                ui.lbl(p, "No hay partidas guardadas con detalle en este modo.", 10, "dim").pack(anchor="w")
                return
            line = f"{s['n']} partidas guardadas · {s['wins']}V {s['n'] - s['wins']}D"
            if s["kda"] is not None:
                line += f" · KDA {s['kda']:.2f}".replace(".", ",")
            durs = [e["d"] for e in games if e.get("d")]
            if durs:
                m_ = sum(durs) / len(durs)
                line += f" · {int(m_ // 60)}:{int(m_ % 60):02d} de media"
            ui.lbl(p, line, 11, "fg", anchor="w", wraplength=min(self.ctx["width"] - 140, 640), justify="left").pack(anchor="w")
            ui.dots(p, [e["w"] for e in games[:20][::-1]], 11).pack(anchor="w", pady=(6, 6))
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

    # ---- pestaña: repertorio ----
    def tab_pool(self, parent):
        """Tus campeones: titular con el hallazgo, cifras, tabla ordenable y panel de detalle (resumen, partidas y build)."""
        self.slot = None
        if getattr(self, "pool_panel", None) is None:
            self.pool_panel = PoolPanel(self.ui, self.ctx, self.hist)
        else:
            self.pool_panel.ctx, self.pool_panel.hist = self.ctx, self.hist
        self.pool_panel.mount(parent)


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
            inner.pack(padx=8, pady=10)
            ui.champ(inner, cid, 48, True).pack()
            wr = w / g
            ui.lbl(inner, f"{wr:.0%}", 20, "good" if wr >= .5 else "bad", True, True).pack(pady=(4, 0))
            ui.lbl(inner, f"{w} de {g} partidas", 9, "dim").pack(pady=(0, 4))
            ui.bar(inner, [(wr, "good" if wr >= .5 else "bad")], 5, True).pack(fill="x", padx=6)


# ------------------------------------------------------------------ selección de campeón
class ProfileStrip(Section):
    """Resumen en una línea mientras se elige: lo importante ocupa el sitio de lo recomendado."""

    def key(self, ctx):
        r = ctx["r"]
        return (json.dumps(r["profile"], sort_keys=True, default=str), tuple(r["form"]), ctx["width"] < 560)

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        pr = r["profile"] or {}
        c = ui.card(self.box, pad=4)
        row = ui.frame(c)
        row.pack(fill="x")
        img = ui.profile_icon(pr["icon"], 30) if pr.get("icon") else None
        if img:
            ctk.CTkLabel(row, image=img, text="").pack(side="left", padx=(0, 10))
        solo = pr.get("solo")
        ui.lbl(row, r["rank"] or "Sin clasificar", 15, TIER_COLORS.get(solo["key"], "fg") if solo else "dim", True, True).pack(side="left")
        if r["record"]:
            ui.lbl(row, f"   {r['record']}", 11, "dim").pack(side="left")
        right = ui.frame(row)
        right.pack(side="right")
        if r["form"][-3:] == [False] * 3 and ctx["width"] >= 560:  # en ventanas estrechas solo caben los resultados
            ui.lbl(right, "Cuidado con el tilt  ", 10, "warn", True).pack(side="left")
        for w in r["form"]:
            ctk.CTkLabel(right, text="V" if w else "D", width=22, height=20, corner_radius=6, font=ui.font(10, True, True),
                         fg_color=PAL["good" if w else "bad"], text_color=ON_FILL).pack(side="left", padx=1)


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
        return (r["turn"], s["timer"]["phase"], r["role"], self.step(s), r["mode"]["kind"])

    def build(self, ctx):
        ui, r, session = self.ui, ctx["r"], ctx["session"]
        sr = r["mode"]["kind"] == "sr"
        c = ui.card(self.box)
        row = ui.frame(c)
        row.pack(fill="x")
        if sr and r["role"] in ROLES_ES:
            ctk.CTkLabel(row, image=ui.role_icon(r["role"], 56), text="").pack(side="left", padx=(0, 14))
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

    def key(self, ctx):
        r = ctx["r"]
        return (r.get("mine"), r.get("mine_locked"), r["role"], r["lane_opp"], r["mode"]["kind"])

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
        ui.lbl(txt, "TU CAMPEÓN ELEGIDO" if r.get("mine_locked") else "LO ESTÁS ELIGIENDO", 10, "dim", True).pack(anchor="w")
        ui.lbl(txt, name(cid, ui.champs), 18, "fg", True, True).pack(anchor="w")
        build_panel(ui, c, cid, lane, r["lane_opp"] or None, min(ctx["width"] - 120, 720)).pack(fill="x")


class BanIdeas(Section):
    def key(self, ctx):
        r = ctx["r"]
        return (r["turn"] == "ban" or ctx["session"]["timer"]["phase"] == "PLANNING", tuple(x[3] for x in r["ban_ideas"]),
                r["mode"]["kind"])

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        if r["mode"]["kind"] != "sr" or not (r["turn"] == "ban" or ctx["session"]["timer"]["phase"] == "PLANNING"):
            return
        c = ui.card(self.box, "Banea a quien te gana en tu línea")
        if not r["ban_ideas"]:
            ui.lbl(c, "Todavía no hay datos suficientes.", 11, "dim").pack(anchor="w")
            return
        row = ui.frame(c)
        row.pack(anchor="w")
        for n, w, g, cid in r["ban_ideas"]:
            cell = ui.frame(row)
            cell.pack(side="left", padx=(0, 16))
            ui.champ(cell, cid, 40, False, "#ff5a5f").pack(side="left")
            ui.lbl(cell, f"{n}\n{g - w} derrotas de {g}", 10, "bad").pack(side="left", padx=8)


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

    def key(self, ctx):
        r, cf = ctx["r"], self.ui.conf
        return (tuple((c["cid"], round(c["score"], 1), c["off_role"]) for c in r["cands"]), tuple(r["allies"]),
                tuple(r["enemies"]), r["lane_opp"], cf["rec_view"], cf["compact"], cf["top_n"],
                bool(r["meta_info"]), r["mode"]["kind"])

    def build(self, ctx):
        ui = self.ui
        self.r, self.width = ctx["r"], ctx["width"]
        compact = ui.conf["compact"]
        self.keep_cid = self.vis[self.sel]["cid"] if self.vis and 0 < self.sel < len(self.vis) else None
        if self.kind() == "other":
            self.dyn = None
            c = ui.card(self.box, "Recomendado para ti")
            ui.lbl(c, f"Este modo ({self.r['mode']['group'] or 'sin identificar'}) no tiene recomendaciones.\nLOL-E está pensado para la "
                      "Grieta del Invocador y, con menos datos, para ARAM.", 11, "dim", anchor="w", justify="left").pack(anchor="w")
            return
        c = ui.card(self.box)
        head = ui.frame(c)
        head.pack(fill="x", pady=(0, 8))
        ui.lbl(head, "CAMBIO DE CAMPEÓN (BANQUILLO)" if self.kind() == "aram" else "RECOMENDADO PARA TI", 10, "dim", True).pack(side="left")
        if not compact:
            ui.seg(head, ["Carrusel", "Lista"], "Carrusel" if ui.conf["rec_view"] == "carrusel" else "Lista",
                   self.set_view, width=150, height=26).pack(side="right")
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
        bar = ui.frame(parent)
        bar.pack(fill="x", pady=(0, 10))
        r1 = ui.frame(bar)
        r1.pack(fill="x")
        ui.lbl(r1, "Ordenar", 10, "dim").pack(side="left", padx=(0, 6))
        self.menu_order = ui.menu(r1, ORDENES, f["orden"], lambda v: self.set_filter("orden", v), 112)
        self.menu_order.pack(side="left")
        ui.lbl(r1, "Clase", 10, "dim").pack(side="left", padx=(14, 6))
        self.menu_class = ui.menu(r1, list(CLASES), f["clase"], lambda v: self.set_filter("clase", v), 112)
        self.menu_class.pack(side="left")
        r2 = ui.frame(bar)
        r2.pack(fill="x", pady=(8, 0))
        for text, key in (("Mi rol", "mi_rol"), ("Mis campeones", "mios"), ("Meta fuerte", "meta")):
            self.toggle(r2, text, key)

    def toggle(self, parent, text, key):
        ui = self.ui
        on = ui.conf["filters"][key]
        b = ctk.CTkButton(parent, text=text, height=26, width=10, corner_radius=13, font=ui.font(11), border_width=1,
                          border_color=PAL["border"], fg_color=ui.acc if on else PAL["card2"],
                          text_color=ON_FILL if on else PAL["fg"], hover_color=PAL["border"])
        b.configure(command=lambda: self.flip(b, key))
        b.pack(side="left", padx=(0, 6))
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
        self.sel = 0
        self.render()

    def visible(self):
        ui, f = self.ui, self.ui.conf["filters"]
        if self.kind() != "sr":
            return sorted(self.r["cands"], key=lambda c: -c["score"])[: 3 if ui.conf["compact"] else ui.conf["top_n"]]
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
        order = {"Afinidad": lambda c: -c["score"], "Meta": lambda c: -(c["meta"]["wr"] if c["meta"] else 0),
                 "Sinergia": lambda c: -c["syn"]["score"], "Maestría": lambda c: -c["mastery"]}[f["orden"]]
        out.sort(key=order)
        return out[: 3 if ui.conf["compact"] else ui.conf["top_n"]]

    def pct(self, c):
        return self.ui.pct(c["score"], self.r["pct_scale"])

    # ---- navegación ----
    def set_view(self, v):
        self.ui.conf["rec_view"] = v.lower()
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
        for w in self.dyn.winfo_children():
            w.destroy()
        self.pages, self.cur_page, self.hero_lab, self.cells = {}, None, None, []
        if not self.vis and not self.r["cands"]:  # nada que comparar todavía (por ejemplo, un banquillo de ARAM aún vacío)
            ui.lbl(self.dyn, "Todavía no hay campeones para comparar. Aparecerán cuando el cliente los muestre.", 11, "dim").pack(anchor="w", pady=(4, 6))
            return
        if not self.vis:
            ui.lbl(self.dyn, "Ningún campeón cumple los filtros.", 11, "dim").pack(anchor="w", pady=(4, 6))
            ctk.CTkButton(self.dyn, text="Quitar filtros", height=28, font=ui.font(11), fg_color=PAL["card2"], text_color=PAL["fg"],
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
        self.pages = {}  # el ancho cambió: las páginas de información se rehacen con la columna nueva
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
        self.sel = 0
        self.render()

    def list_view(self):
        ui, compact = self.ui, self.ui.conf["compact"]
        for i, c in enumerate(self.vis, 1):
            pct = self.pct(c)
            if i == 1:
                w = max(340, min(2400, self.width - 52))
                lab = self.hero_label(self.dyn, c, pct, w, "Mejor opción para ti")
                lab.pack(pady=(0, 6))
                if not compact:
                    ui.chips(self.dyn, c["why"] or ["encaja con tu rol"], 4)
                continue
            row = ctk.CTkFrame(self.dyn, fg_color=PAL["card2"], corner_radius=12)
            row.pack(fill="x", pady=4)
            inner = ui.frame(row)
            inner.pack(fill="x", padx=12, pady=10)
            ui.champ(inner, c["cid"], 40, False).pack(side="left")
            mid = ui.frame(inner)
            mid.pack(side="left", fill="x", expand=True, padx=12)
            ui.lbl(mid, f"{i}.  {name(c['cid'], ui.champs)}", 14, "fg", True, True).pack(anchor="w")
            if not compact:
                ui.chips(mid, c["why"] or ["encaja con tu rol"])
            right = ui.frame(inner)
            right.pack(side="right", anchor="n")
            ui.lbl(right, str(pct), 22, ui.acc, True, True).pack(anchor="e")
            ui.lbl(right, "afinidad", 9, "dim").pack(anchor="e")
            if not compact:
                ui.clickable(row, lambda i=i: (self.set_view("carrusel"), self.pick(i - 1)))

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
        self.hero_lab.pack(side="left", padx=6)
        ui.seg(self.dyn, self.tabs(), self.tab, self.set_tab).pack(fill="x", pady=(10, 8))
        self.info_host = ctk.CTkFrame(self.dyn, fg_color=PAL["card2"], corner_radius=12)
        self.info_host.pack(fill="x")
        self.build_strip()
        self.hero = None
        self.show_card(fade=False)

    def show_card(self, fade):
        """Muestra la tarjeta elegida: fundido de la imagen, página de información en caché y franja actualizada."""
        ui, c = self.ui, self.vis[self.sel]
        eyebrow = "Mejor opción para ti" if self.sel == 0 else f"Opción {self.sel + 1} de {len(self.vis)}"
        pil = ui.hero_pil(c["cid"], eyebrow, self.pct(c), self.hero_w)
        old, self.hero = self.hero, pil
        self.set_hero(self.hero_lab, old if fade and ui.anim_on() and old is not None and old.size == pil.size else None, pil)
        self.show_page(c)
        self.update_strip()
        self.queue_prebuild()

    def make_page(self, c, tab):
        page = self.ui.frame(self.info_host)
        body = self.ui.frame(page)
        extra = max(0, (self.width - 52 - 800) // 2)  # en pantallas grandes la información se queda en una columna central
        body.pack(fill="x", padx=14 + extra, pady=12)
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
        row.pack(fill="x", pady=(10, 0))
        self.strip_row = row
        self.cells = []
        for i, c in enumerate(self.vis):
            row.columnconfigure(i, weight=1, uniform="thumb")
            cell = ctk.CTkFrame(row, fg_color="transparent", corner_radius=10, border_width=0, border_color=col(ui.acc))
            cell.grid(row=0, column=i, sticky="ew", padx=3)
            inner = ui.frame(cell)
            inner.pack(padx=4, pady=6)
            icon = ctk.CTkLabel(inner, text="", image=ui.icon(c["cid"], 40))
            icon.pack()
            num = ui.lbl(inner, str(self.pct(c)), 13, "dim", True, True)
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
        ui.kpi(row, f"{w / g:.0%}" if g else "—", "porcentaje")
        ui.kpi(row, str(self.pct(c)), "afinidad")
        bw = 170 if self.width < 560 else 300 if self.width < 900 else 400
        col = ui.frame(body)
        col.pack()  # sin «fill»: la columna queda centrada y el desglose no se pega al borde izquierdo
        ui.chips(col, c["why"] or ["encaja con tu rol"], 3 if self.width < 900 else 4)
        ui.lbl(col, "DESGLOSE DE LA AFINIDAD", 10, "dim", True).pack(anchor="w", pady=(10, 3))
        breakdown_rows(ui, col, c["parts"], c["score"], self.r["pct_scale"], bw)
        ui.lbl(col, "La afinidad (0 a 100) es la suma de estos puntos sobre un máximo realista. Los pesos y su explicación están en la "
                    "pestaña «Datos».", 9, "dim", anchor="w", wraplength=bw + 150, justify="left").pack(anchor="w", pady=(6, 0))

    def vs_row(self, parent, enemy, g, w, size=30):
        ui = self.ui
        row = ui.frame(parent)
        row.pack(fill="x", pady=3)
        ui.champ(row, enemy, size, False).pack(side="left")
        mid = ui.frame(row)
        mid.pack(side="left", fill="x", expand=True, padx=10)
        top = ui.frame(mid)
        top.pack(fill="x")
        ui.lbl(top, name(enemy, ui.champs), 12, "fg", True).pack(side="left")
        ok = w * 2 >= g
        ui.lbl(top, f"{w} de {g} victorias", 11, "good" if ok else "bad", True).pack(side="right")
        ui.bar(mid, [(w / g if g else 0, "good" if ok else "bad")], 5).pack(fill="x", pady=(3, 0))

    def tab_matchup(self, body, c):
        ui, r = self.ui, self.r
        lane, opp = c["lane"], r["lane_opp"]
        if opp:
            ui.lbl(body, f"TU RIVAL DE LÍNEA: {name(opp, ui.champs).upper()}", 10, "dim", True).pack(anchor="w", pady=(0, 4))
            if lane and lane[1]:
                self.vs_row(body, opp, lane[1], lane[2], 40)
            else:
                ui.lbl(body, f"Aún no has jugado con {name(c['cid'], ui.champs)} contra {name(opp, ui.champs)}, "
                             "así que no hay datos de este enfrentamiento.", 11, "dim", anchor="w", wraplength=400,
                       justify="left").pack(anchor="w")
        else:
            ui.lbl(body, "Tu rival de línea todavía no ha elegido campeón.", 11, "dim").pack(anchor="w")
        others = [v for v in c["vs"] if v[0] != opp and v[1]][:4]
        if others:
            ui.lbl(body, "CONTRA OTROS RIVALES YA ELEGIDOS", 10, "dim", True).pack(anchor="w", pady=(12, 2))
            for e, g, w in others:
                self.vs_row(body, e, g, w)
        elif not (lane and lane[1]):
            ui.lbl(body, "Sin datos de enfrentamientos con los rivales actuales.", 10, "dim").pack(anchor="w", pady=(8, 0))

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
        head.pack(fill="x", pady=(0, 6))
        ui.lbl(head, "SINERGIA CON TU EQUIPO", 10, "dim", True).pack(side="left")
        ui.lbl(head, level, 14, color, True, True).pack(side="right")
        for it in sorted(items, key=lambda i: -i["score"]):
            row = ui.frame(body)
            row.pack(fill="x", pady=4)
            ui.champ(row, it["ally"], 34, False).pack(side="left")
            mid = ui.frame(row)
            mid.pack(side="left", fill="x", expand=True, padx=10)
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
            row.pack(fill="x", pady=(0, 6))
            ui.kpi(row, f"{pct_es(m['wr'])} %", "victorias")
            ui.kpi(row, f"{pct_es(m['pr'])} %", "uso")
            ui.kpi(row, f"{pct_es(m['br'])} %", "baneos")
            ui.kpi(row, f"{m['games'] / 1000:.0f} k" if m["games"] >= 1000 else str(m["games"]), "partidas")
            d = m["wr"] - mi["avg"]
            ui.lbl(body, f"Parche {mi['patch']}{' (el ' + mi['current'] + ' aún no tiene datos suficientes)' if mi['stale'] else ''} · {mi['tier_name']} · media de la línea {pct_es(mi['avg'])} % "
                         f"({'+' if d >= 0 else '−'}{pct_es(abs(d))} puntos)", 10, "dim", anchor="w", wraplength=400,
                   justify="left").pack(anchor="w", pady=(0, 8))
        elif self.kind() == "sr":
            ui.lbl(body, "Sin datos de meta para este campeón en tu línea (o el meta está desactivado o aún cargando).", 10,
                   "dim", anchor="w", wraplength=400, justify="left").pack(anchor="w", pady=(0, 8))
        lane = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support"}.get(self.r.get("role"))
        if self.kind() == "sr" and lane:
            build_panel(ui, body, c["cid"], lane, self.r.get("lane_opp") or None, min(self.width - 120, 720)).pack(fill="x", pady=(2, 8))
        ui.lbl(body, "CONSEJOS SEGÚN LA COMPOSICIÓN", 10, "dim", True).pack(anchor="w", pady=(2, 2))
        for title, text in c["build"]:
            row = ui.frame(body)
            row.pack(fill="x", pady=3)
            ui.lbl(row, title.upper(), 9, ui.acc, True, width=96, anchor="w").pack(side="left", anchor="n")
            ui.lbl(row, text, 11, "fg", anchor="w", wraplength=300, justify="left").pack(side="left", fill="x", expand=True)
        ui.lbl(body, "Consejos orientativos según la composición actual. No sustituyen a la build recomendada del parche.", 9,
               "dim", anchor="w", wraplength=400, justify="left").pack(anchor="w", pady=(8, 0))
        champ = ui.champs[c["cid"]]
        links = ui.frame(body)
        links.pack(anchor="w", pady=(8, 0))
        small_btn(ui, links, "Builds de especialistas (OneTricks)",
                  lambda: open_url(f"https://www.onetricks.gg/es/champions/builds/{champ['icon']}"), 220).pack(side="left", padx=(0, 6))
        lane = matchups.LANES.get(self.r["role"])
        if lane:
            small_btn(ui, links, "Meta en Lolalytics", lambda: open_url(f"https://lolalytics.com/lol/{matchups.slug(champ)}/build/?lane={lane}"),
                      130).pack(side="left")


class Lobby(Section):
    """Tu equipo: quién es cada aliado, su rango, su forma reciente y cómo le va con el campeón que ha elegido."""

    def key(self, ctx):
        r, pl = ctx["r"], ctx["players"]
        return (tuple((a["cell"], a["champ"], a["role"], a["puuid"]) for a in r["ally_cells"]),
                tuple(sorted((k, v.get("name", ""), len(v.get("recent", [])), bool(v.get("error"))) for k, v in pl.items())),
                tuple(r["party"]), self.ui.conf["show_teams"], r["mode"]["kind"], json.dumps(r["mates"], sort_keys=True))

    def build(self, ctx):
        ui, r, pl = self.ui, ctx["r"], ctx["players"]
        if not ui.conf["show_teams"] or not r["ally_cells"]:
            return
        c = ui.card(self.box, "Tu equipo")
        party = set(r["party"])
        if r["mode"]["kind"] != "sr":  # sin roles ni perfiles: solo los campeones que lleva el equipo
            row = ui.frame(c)
            row.pack(anchor="w")
            for a in r["ally_cells"]:
                ui.champ(row, a["champ"], 44, True, "#3ddc84" if a["champ"] else None).pack(side="left", padx=3)
        else:
            for a in r["ally_cells"]:
                p = pl.get(a["puuid"]) if a["puuid"] else None
                self.row(c, a, p, a["puuid"] in party, len(party), bool(pl) or not a["puuid"], r["mates"].get(a["puuid"]))
        st = r["ally_stats"]
        if st and st["ad"] + st["ap"]:
            tot = st["ad"] + st["ap"]
            ui.bar(c, [(st["ad"] / tot, "warn"), (st["ap"] / tot, "info")], 7).pack(fill="x", pady=(8, 4))
            ui.lbl(c, f"Daño físico {st['ad']} · mágico {st['ap']}   ·   Tanques {st['tanks']}   ·   Control {st['cc']:.1f}/3", 10,
                   "dim", anchor="w").pack(anchor="w")

    def row(self, parent, a, p, in_party, party_n, loaded, mates=None):
        ui = self.ui
        box = ctk.CTkFrame(parent, fg_color=PAL["card2"], corner_radius=12)
        box.pack(fill="x", pady=4)
        inner = ui.frame(box)
        inner.pack(fill="x", padx=12, pady=10)
        ui.champ(inner, a["champ"], 44, False, "#3ddc84" if a["champ"] else None).pack(side="left", anchor="n")
        mid = ui.frame(inner)
        mid.pack(side="left", fill="x", expand=True, padx=12)
        head = ui.frame(mid)
        head.pack(fill="x")
        nm = (p or {}).get("name") or ("Perfil oculto" if not a["puuid"] else "Cargando…")
        ui.lbl(head, nm, 13, "fg", True).pack(side="left")
        if ROLES_ES.get(a["role"]):
            ui.chip(head, ROLES_ES[a["role"]], "dim").pack(side="left", padx=(8, 0))
        if in_party:
            ui.chip(head, "Dúo contigo" if party_n == 1 else "Tu grupo", "info").pack(side="left", padx=(6, 0))
        if mates and mates[0]:
            g, w = mates
            ui.chip(head, f"Juntos: {partidas(g)} · {w}V {g - w}D", "good" if w * 2 >= g else "bad").pack(side="left", padx=(6, 0))
        if p and not p.get("error"):
            rk = p.get("solo") or p.get("flex")
            if rk:
                ui.lbl(head, f"{rk['tier']} {rk['div']}".strip(), 12, TIER_COLORS.get(rk["key"], "fg"), True, True).pack(side="right")
            line = ui.frame(mid)
            line.pack(fill="x", pady=(5, 0))
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
            line2.pack(fill="x", pady=(5, 0))
            for cid in p["top"][:3]:
                ui.champ(line2, cid, 22, False).pack(side="left", padx=(0, 4))
            extra = []
            if p["roles"]:
                extra.append("Suele jugar: " + ", ".join(ROLES_ES.get(x, x).lower() for x in p["roles"]))
            if p["wr10"] is not None and len(p["recent"]) >= 6:
                extra.append("racha negativa" if p["wr10"] < .4 else "en buena racha" if p["wr10"] >= .65 else "")
            ui.lbl(line2, "  ·  ".join(x for x in extra if x), 10, "dim").pack(side="left", padx=4)
        elif p and p.get("error"):
            ui.lbl(mid, "No se pudieron leer sus datos.", 10, "dim").pack(anchor="w")
        elif not loaded:
            ui.lbl(mid, "Cargando datos del jugador…", 10, "dim").pack(anchor="w", pady=(4, 0))


class Enemies(Section):
    def key(self, ctx):
        r = ctx["r"]
        return (tuple(r["enemies"]), ctx["session"]["theirTeam"] and len(ctx["session"]["theirTeam"]), self.ui.conf["show_teams"],
                self.ui.conf["compact"], r["mode"]["kind"])

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        if ui.conf["compact"] or not ui.conf["show_teams"]:
            return
        if r["mode"]["kind"] != "sr" and not r["enemies"]:  # Arena, personalizadas, ARAM: sin rivales conocidos no hay nada que enseñar
            return
        c = ui.card(self.box, "Equipo rival")
        row = ui.frame(c)
        row.pack(fill="x")
        icons = ui.frame(row)
        icons.pack(side="left")
        for i in range(5):
            ui.champ(icons, r["enemies"][i] if i < len(r["enemies"]) else 0, 48, True, "#ff5a5f").pack(side="left", padx=3)
        st = r["enemy_stats"]
        if st:
            info = ui.frame(row)
            info.pack(side="left", padx=16, fill="x", expand=True, anchor="n")
            tot = st["ad"] + st["ap"]
            if tot:
                ui.bar(info, [(st["ad"] / tot, "warn"), (st["ap"] / tot, "info")], 7).pack(fill="x", pady=(4, 4))
            ui.lbl(info, f"Daño físico {st['ad']}  ·  mágico {st['ap']}", 10, "dim", anchor="w").pack(anchor="w")
            ui.lbl(info, f"Tanques {st['tanks']}  ·  control {st['cc']:.1f}/3", 10, "dim", anchor="w").pack(anchor="w")
            if st["tip"]:
                ui.lbl(info, st["tip"], 10, "warn", True, anchor="w", wraplength=230, justify="left").pack(anchor="w", pady=(2, 0))


class BansRow(Section):
    def key(self, ctx):
        return (tuple(ctx["r"]["bans"]), self.ui.conf["show_bans"], self.ui.conf["compact"])

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        if ui.conf["compact"] or not ui.conf["show_bans"] or not r["bans"]:
            return
        c = ui.card(self.box, "Campeones baneados")
        row = ui.frame(c)
        row.pack(anchor="w")
        for cid in r["bans"]:
            ui.champ(row, cid, 34, False, "#ff5a5f").pack(side="left", padx=3)
