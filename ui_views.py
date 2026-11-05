"""Vistas completas de LOL-E: «Enfrentamiento» (mejores picks contra un rival) y «Datos» (de dónde sale todo y qué se puede ajustar)."""
import os, threading, time, tkinter as tk, tkinter.messagebox as messagebox, webbrowser

import customtkinter as ctk

import lol_advisor as core
import matchups
import params
from ui_build import build_panel
from ui_kit import PAL, ON_FILL, ROLES_ES, col, hexc, partidas, pct_es

LANE_CHOICES = {"Automática": None, "Superior": "top", "Jungla": "jungle", "Central": "middle", "Tirador": "bottom", "Apoyo": "support"}
ROLE_TO_LANE = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support", "UTILITY": "support"}
AUTO = "Automático (tu rival de línea)"
FILTERS = ["Todos", "Solo los que tengo", "Solo los que he jugado"]


def open_url(url):
    try:
        webbrowser.open(url)
    except Exception:
        pass


def small_btn(ui, parent, text, cmd, width=10):
    b = ctk.CTkButton(parent, text=text, height=26, width=width, corner_radius=8, font=ui.font(10), fg_color=PAL["card2"],
                      text_color=PAL["fg"], hover_color=PAL["card2"], command=cmd)
    ui.smooth_btn(b, PAL["card2"], PAL["border"])
    return b


CLASSES = {"Todas": None, "Tanque": "Tank", "Luchador": "Fighter", "Asesino": "Assassin", "Mago": "Mage", "Tirador": "Marksman",
           "Soporte": "Support"}
MIN_GAMES = {"Todas": 1, "20": 20, "50": 50, "100": 100, "300": 300, "1.000": 1000, "3.000": 3000}
ORDERS = ["Mejor porcentaje", "Más fiable", "Más partidas", "Mayor ventaja"]
SMALL = 100  # por debajo de estas partidas el porcentaje es poco fiable


def wilson(wr, n, z=1.96):
    """Intervalo de confianza (95 %) del porcentaje de victorias con n partidas: (mínimo, máximo) en tanto por uno."""
    if n <= 0:
        return 0.0, 1.0
    p = wr / 100
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return max(0.0, (c - m) / d), min(1.0, (c + m) / d)
SHOWS = ["Todos", "Los que tengo", "Los que he jugado"]
LANE_SEG = ["Superior", "Jungla", "Central", "Tirador", "Apoyo"]
LANE_KEYS = {"Superior": "top", "Jungla": "jungle", "Central": "middle", "Tirador": "bottom", "Apoyo": "support"}
LANE_LABEL = {v: k for k, v in LANE_KEYS.items()}
TILE_STEP = 24
PAGE = 15


def _norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


def mini_bar(ui, parent, frac, color, width, h=7):
    sx = ui.scale_px()
    track = tk.Frame(parent, width=int(width * sx), height=int(h * sx), bg=ui.hexm(PAL["border"]))
    track.pack_propagate(False)
    tk.Frame(track, bg=ui.hexm(PAL[color]), width=max(2, int(max(0.0, min(1.0, frac)) * width * sx)), height=int(h * sx)).pack(side="left")
    return track


class MatchupView:
    """Qué campeón le gana a tu rival: se elige al rival con un buscador y se ven los mejores contra él (Lolalytics, todos los jugadores).

    Dos pasos en pantalla: «1 · Elige a tu rival» y «2 · Qué campeón le gana». Los datos del rival se precargan al buscarlo.
    """

    DEFAULT_FILT = {"show": "Todos", "clase": "Todas", "order": ORDERS[0], "min": "100", "adv": False}

    def __init__(self, ui, parent, gui):
        self.ui, self.gui = ui, gui
        self.box = ui.frame(parent)
        self.sig = None
        self.enemy, self.lane = 0, None
        self.query, self.all_tiles = "", False
        self.filt = dict(self.DEFAULT_FILT)
        self.f_show = self.f_adv = self.f_adv_var = None
        self.f_menus = {}
        self._bkey = None
        self.shown = PAGE
        self.data, self.errors, self.loading = {}, {}, set()
        self.opened, self.pod_open, self.pod_slot = set(), None, None
        self.rival_slot, self.rival_open = None, False
        self.banner = self.sugg = self.host = self.entry = self.lane_seg = self.res_title = None
        self.width, self.level = 520, 0
        self._t = self._hover = self._ukey = None

    # ---- ciclo de vida ----
    def refresh(self, ctx, force=False):
        ui = self.ui
        self.width = ctx["width"]
        self.level = 2 if self.width >= 1000 else 1 if self.width >= 700 else 0
        sig = (ui.epoch, ui.conf["matchups_enabled"], self.level)
        if sig != self.sig or force:
            self.sig = sig
            self.ui.clear(self.box)
            self._ukey = None
            self._bkey = None
            self.skeleton(ctx)
        self.update(ctx)

    def step_title(self, parent, n, text):
        ui = self.ui
        row = ui.frame(parent)
        row.pack(fill="x", pady=(0, 8))
        badge = ctk.CTkLabel(row, text=str(n), width=24, height=24, corner_radius=12, font=ui.font(11, True, True), fg_color=ui.acc,
                             text_color=ON_FILL)
        badge.pack(side="left", padx=(0, 10))
        lab = ui.lbl(row, text, 13, "fg", True, True)
        lab.pack(side="left")
        return lab

    def skeleton(self, ctx):
        ui = self.ui
        wl = min(self.width - 90, 760)
        c = ui.card(self.box)
        self.step_title(c, 1, "Elige a tu rival")
        ui.lbl(c, "Escribe el campeón al que te enfrentas y verás qué campeones le ganan más, con datos de todos los jugadores (Lolalytics). "
                  "En una selección de campeón se rellena solo con tu rival de línea.", 10, "dim", anchor="w", justify="left",
               wraplength=wl).pack(anchor="w", pady=(0, 8))
        self.banner = ui.frame(c)
        self.banner.pack(fill="x", pady=(0, 8))
        self.rival_slot = ui.frame(c)
        self.rival_slot.pack(fill="x")
        self.entry = ctk.CTkEntry(c, placeholder_text="Buscar campeón por nombre…", height=34, font=ui.font(12), fg_color=PAL["card2"],
                                  border_color=PAL["border"], text_color=PAL["fg"])
        if self.query:
            self.entry.insert(0, self.query)
        self.entry.pack(fill="x")
        self.entry.bind("<KeyRelease>", self.on_type)
        self.entry.bind("<Return>", lambda e: self.pick_first())
        self.sugg = ui.frame(c)
        self.sugg.pack(fill="x", pady=(6, 0))
        self.render_sugg()
        ui.lbl(c, "Línea en la que juega el rival", 10, "dim", anchor="w").pack(anchor="w", pady=(10, 2))
        self.lane_seg = ui.seg(c, LANE_SEG, LANE_LABEL.get(self.lane, ""), self.set_lane, height=28)
        self.lane_seg.pack(fill="x")
        self.lane_hint = ui.lbl(c, "", 10, "dim", anchor="w", justify="left", wraplength=wl)
        self.lane_hint.pack(anchor="w", pady=(4, 0))
        self.rise_host = ui.frame(c)
        self.rise_host.pack(fill="x")

        r = ui.card(self.box)
        self.res_title = self.step_title(r, 2, "Qué campeón le gana")
        self.f_show = ui.seg(r, SHOWS, self.filt["show"], lambda v: self.set_filt("show", v), height=28)
        self.f_show.pack(fill="x", pady=(0, 6))
        self.f_menus = {}
        groups = [(("Clase", list(CLASSES), "clase", 110), ("Orden", ORDERS, "order", 150), ("Partidas ≥", list(MIN_GAMES), "min", 90))]
        if self.level == 0:
            groups = [(g,) for pair in groups for g in pair]
        for pair in groups:
            line = ui.frame(r)
            line.pack(fill="x", pady=2)
            for label, values, key, wd in pair:
                ui.lbl(line, label, 10, "dim", width=60, anchor="w").pack(side="left")
                m = ui.menu(line, values, self.filt[key], lambda v, k=key: self.set_filt(k, v), wd)
                m.pack(side="left", padx=(0, 12))
                self.f_menus[key] = m
        bar = ui.frame(r)
        bar.pack(fill="x", pady=(6, 8))
        self.f_adv_var = ctk.BooleanVar(value=self.filt["adv"])
        ctk.CTkSwitch(bar, text="Solo los que ganan más del 50 %", variable=self.f_adv_var, font=ui.font(11), progress_color=ui.acc,
                      command=lambda: self.set_filt("adv", self.f_adv_var.get())).pack(side="left")
        small_btn(ui, bar, "Restablecer filtros", self.reset_filters, 140).pack(side="right")
        self.host = ui.frame(r)
        self.host.pack(fill="x")

    # ---- paso 1: buscar y elegir al rival ----
    def on_type(self, _e=None):
        if self._t:
            self.ui.root.after_cancel(self._t)
        self._t = self.ui.root.after(150, self.typed)

    def typed(self):
        self._t = None
        self.query = self.entry.get().strip()
        self.all_tiles = False
        self.render_sugg()
        m = self.matches()
        if self.query and 0 < len(m) <= 3:
            self.prefetch(m[0])  # precarga: el primero de la lista ya empieza a descargarse

    def pick_first(self):
        m = self.matches()
        if self.query and m:
            self.select(m[0])

    def matches(self):
        q = _norm(self.query)
        ids = [cid for cid, v in self.ui.champs.items() if not q or q in _norm(v["name"])]
        return sorted(ids, key=lambda c: (not _norm(self.ui.champs[c]["name"]).startswith(q), self.ui.champs[c]["name"]))

    def lane_shares(self, cid):
        """{nombre de línea: parte de sus partidas} según el meta (Lolalytics): dónde se juega de verdad, no solo la línea habitual."""
        try:
            sh = core.metamod.lane_shares(core.META["data"], cid)
        except Exception:
            return {}
        return {LANE_LABEL[ROLE_TO_LANE[r]]: v for r, v in sh.items() if r in ROLE_TO_LANE and ROLE_TO_LANE[r] in LANE_LABEL}

    def lanes_of(self, cid):
        sh = self.lane_shares(cid)
        by_meta = [ln for ln, v in sorted(sh.items(), key=lambda x: -x[1]) if v >= 0.02]
        pos = self.ui.champs.get(cid, {}).get("pos") or []
        by_pos = [LANE_LABEL[ROLE_TO_LANE[p]] for p in pos if p in ROLE_TO_LANE and ROLE_TO_LANE[p] in LANE_LABEL]
        return by_meta + [ln for ln in by_pos if ln not in by_meta]

    def lane_text(self, cid, n=3):
        sh = self.lane_shares(cid)
        return " · ".join(f"{ln} {round(sh[ln] * 100)} %" if sh.get(ln, 0) >= 0.01 else ln for ln in self.lanes_of(cid)[:n])

    def render_sugg(self):
        ui = self.ui
        if self.sugg is None or not self.sugg.winfo_exists():
            return
        self.ui.clear(self.sugg)
        ids = self.matches()
        if self.query:
            if not ids:
                ui.lbl(self.sugg, "Ningún campeón se llama así.", 11, "dim").pack(anchor="w", pady=4)
                return
            for cid in ids[:6]:
                self.sugg_row(cid)
            if len(ids) > 6:
                ui.lbl(self.sugg, f"y {len(ids) - 6} más: sigue escribiendo para afinar.", 10, "dim").pack(anchor="w", pady=(4, 0))
            return
        recent = [c for c in ui.conf.get("recent_rivals", []) if c in ui.champs][:8]
        if recent:
            ui.lbl(self.sugg, "RECIENTES", 9, "dim", True).pack(anchor="w", pady=(2, 4))
            row = ui.frame(self.sugg)
            row.pack(anchor="w")
            for cid in recent:
                cell = ui.frame(row)
                cell.pack(side="left", padx=(0, 8))
                ui.champ(cell, cid, 36, True).pack()
                ui.clickable(cell, lambda c=cid: self.select(c))
                cell.bind("<Enter>", lambda e, c=cid: self.hover(c), add="+")
        if self.all_tiles:
            self.render_grid(ids)
        elif not self.enemy:
            small_btn(ui, self.sugg, f"Ver todos los campeones ({len(ids)})", self.show_all, 220).pack(anchor="w", pady=(8, 0))

    def sugg_row(self, cid):
        ui = self.ui
        row = ctk.CTkFrame(self.sugg, fg_color=PAL["card2"], corner_radius=10)
        row.pack(fill="x", pady=2)
        inner = ui.frame(row)
        inner.pack(fill="x", padx=10, pady=5)
        ui.champ(inner, cid, 30, False).pack(side="left")
        ui.lbl(inner, ui.champs[cid]["name"], 12, "fg", True, anchor="w", width=150).pack(side="left", padx=10)
        ui.lbl(inner, self.lane_text(cid), 10, "dim").pack(side="left")
        ui.lbl(inner, "Elegir  ›", 10, ui.acc, True).pack(side="right")
        ui.clickable(row, lambda c=cid: self.select(c))
        row.bind("<Enter>", lambda e, c=cid: self.hover(c), add="+")

    def render_grid(self, ids):
        ui = self.ui
        cols = max(3, (self.width - 110) // 84)
        grid = ui.frame(self.sugg)
        grid.pack(pady=(8, 0))
        for i, cid in enumerate(ids):
            cell = ui.frame(grid)
            cell.grid(row=i // cols, column=i % cols, padx=3, pady=3)
            ui.champ(cell, cid, 38, True).pack()
            ui.clickable(cell, lambda c=cid: self.select(c))
            cell.bind("<Enter>", lambda e, c=cid: self.hover(c), add="+")

    def show_all(self):
        self.all_tiles = True
        self.render_sugg()

    def hover(self, cid):
        if self._hover:
            self.ui.root.after_cancel(self._hover)
        self._hover = self.ui.root.after(300, lambda: self.prefetch(cid))

    def select(self, cid):
        ui = self.ui
        self.enemy, self.shown = cid, PAGE
        self.opened.clear()
        self.pod_open = None
        self.rival_open = False
        ctx = self.gui.make_ctx()
        r = ctx.get("r")
        lanes = self.lanes_of(cid)
        mine = LANE_LABEL.get(ROLE_TO_LANE.get(r.get("role"))) if (r and r["mode"]["kind"] == "sr") else None
        # el rival juega en su línea habitual; si también juega en la tuya, se usa la tuya
        self.lane = LANE_KEYS[mine] if mine in lanes else (LANE_KEYS[lanes[0]] if lanes else None)
        rec = [c for c in ui.conf.get("recent_rivals", []) if c != cid]
        ui.conf["recent_rivals"] = ([cid] + rec)[:8]
        core.save_conf(ui.conf)
        self.query = ""
        try:
            self.entry.delete(0, "end")
        except Exception:
            pass
        self.render_sugg()
        self.update(ctx)
        try:
            self.gui.body._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass

    def clear_enemy(self):
        self.enemy, self.lane = 0, None
        self.update(self.gui.make_ctx())

    def set_lane(self, v):
        self.lane = LANE_KEYS[v]
        self.opened.clear()
        self.pod_open = None
        self.rival_open = False
        self.shown = PAGE
        self.update(self.gui.make_ctx())

    def reset_filters(self):
        """Todos los filtros a su valor inicial, sin reconstruir la pantalla: solo se cambian los controles y se repinta la lista."""
        self.filt = dict(self.DEFAULT_FILT)
        self.shown = PAGE
        try:
            self.f_show.set(self.filt["show"])
            for k, m in self.f_menus.items():
                m.set(self.filt[k])
            self.f_adv_var.set(False)
        except Exception:
            pass
        self.update(self.gui.make_ctx())

    def set_filt(self, k, v):
        self.filt[k] = v
        self.shown = PAGE
        self.update(self.gui.make_ctx())

    # ---- datos ----
    def lane_of(self, enemy, ctx):
        if self.lane:
            return self.lane
        r = ctx.get("r")
        if not self.enemy and r and r.get("role") in ROLE_TO_LANE and r["mode"]["kind"] == "sr":
            return ROLE_TO_LANE[r["role"]]
        lanes = self.lanes_of(enemy)
        return LANE_KEYS[lanes[0]] if lanes else None

    def target(self, ctx):
        r = ctx.get("r")
        enemy = self.enemy or (r["lane_opp"] if r else 0)
        return enemy, (self.lane_of(enemy, ctx) if enemy else None)

    def prefetch(self, cid):
        lanes = self.lanes_of(cid)
        lane = self.lane if (self.enemy == cid and self.lane) else (LANE_KEYS[lanes[0]] if lanes else None)
        if lane:
            self.start((cid, lane))

    def start(self, key):
        if key in self.data or key in self.loading or not self.ui.conf["matchups_enabled"]:
            return
        self.loading.add(key)
        champs = self.ui.champs

        def go():
            try:
                self.data[key] = matchups.best_against(champs, key[0], key[1], core.CACHE, min_games=1)
                self.errors.pop(key, None)
            except Exception as e:
                self.errors[key] = str(e) if isinstance(e, RuntimeError) else f"No se han podido cargar los enfrentamientos ({type(e).__name__}). Comprueba tu conexión."
            self.loading.discard(key)
            self.ui.notify("matchup")
        threading.Thread(target=go, daemon=True).start()

    # ---- pintado ----
    def update(self, ctx):
        ui = self.ui
        if self.host is None or not self.host.winfo_exists():
            return
        enemy, lane = self.target(ctx)
        k = (enemy, lane, self.rival_open, tuple(sorted(self.filt.items())), self.shown, (enemy, lane) in self.data, (enemy, lane) in self.errors,
             self.level, ui.epoch, ui.conf["matchups_enabled"], bool((ctx.get("info") or {}).get("owned")), bool(self.enemy))
        if k == self._ukey:
            return  # nada ha cambiado: no se repinta (cambiar de pestaña y volver es instantáneo)
        self._ukey = k
        kb = self.head_key(ctx, enemy, lane)
        head_changed = kb != self._bkey
        self._bkey = kb
        if head_changed:
            self.paint_banner(enemy, lane)
        if head_changed and self.lane_seg is not None and self.lane_seg.winfo_exists():
            try:
                self.lane_seg.set(LANE_LABEL.get(lane, ""))
            except Exception:
                pass
            hint = ""
            if enemy:
                sh = self.lane_shares(enemy)
                name = ui.champs[enemy]["name"]
                hint = f"Dónde juega {name} según el meta: {self.lane_text(enemy, 5) or 'sin datos'}."
                if lane and LANE_LABEL.get(lane) and sh.get(LANE_LABEL[lane], 0) < 0.02 and sh:
                    hint += f" En {matchups.LANE_NAMES[lane].lower()} casi no hay partidas: se intentará con todos los rangos."
                if lane and core.TRENDS["data"]:
                    hint += "\n" + core.trends.describe(core.TRENDS["data"], lane, enemy)
            self.lane_hint.configure(text=hint)
            self.paint_rising(lane)
        self.ui.clear(self.host)
        if self.res_title is not None and self.res_title.winfo_exists():
            self.res_title.configure(text=f"Qué campeón le gana a {ui.champs[enemy]['name']}" if enemy else "Qué campeón le gana")
        wl = min(self.width - 90, 700)
        if not ui.conf["matchups_enabled"]:
            ui.lbl(self.host, "Esta fuente está desactivada. Actívala en la pestaña «Datos».", 11, "dim").pack(anchor="w")
            return
        if not enemy:
            ui.lbl(self.host, "Todavía no has elegido rival. Escribe su nombre arriba, o elige uno de los recientes.", 11, "dim", anchor="w",
                   justify="left", wraplength=wl).pack(anchor="w", pady=6)
            return
        if not lane:
            ui.lbl(self.host, "Elige la línea en la que juega el rival (arriba).", 11, "dim").pack(anchor="w", pady=6)
            return
        key = (enemy, lane)
        self.start(key)
        if key in self.errors:
            ui.lbl(self.host, self.errors[key], 11, "bad", anchor="w", justify="left", wraplength=wl).pack(anchor="w", pady=6)
            alts = [ln for ln in self.lanes_of(enemy) if LANE_KEYS[ln] != lane][:3]
            if alts:
                ui.lbl(self.host, f"Líneas de {ui.champs[enemy]['name']} con más partidas:", 10, "dim").pack(anchor="w", pady=(2, 4))
                row = ui.frame(self.host)
                row.pack(anchor="w")
                for ln in alts:
                    small_btn(ui, row, f"Ver en {ln.lower()}", lambda v=ln: self.set_lane(v), 120).pack(side="left", padx=(0, 6))
            ui.lbl(self.host, "Con datos propios: si ya te has enfrentado a este campeón, tus partidas aparecen en «Tu rival» (arriba).", 9, "dim",
                   anchor="w", justify="left", wraplength=wl).pack(anchor="w", pady=(8, 0))
            return
        if key not in self.data:
            ui.lbl(self.host, f"Cargando los datos de {ui.champs[enemy]['name']}…", 11, "dim").pack(anchor="w", pady=6)
            return
        self.render(ctx, enemy, lane, self.data[key])

    def paint_banner(self, enemy, lane):
        ui = self.ui
        if self.banner is None or not self.banner.winfo_exists():
            return
        self.ui.clear(self.banner)
        if not enemy:
            return
        box = ctk.CTkFrame(self.banner, fg_color=PAL["card2"], corner_radius=12, border_width=1, border_color=ui.hexm(ui.acc))
        box.pack(fill="x")
        inner = ui.frame(box)
        inner.pack(fill="x", padx=12, pady=8)
        ui.champ(inner, enemy, 48, False, ui.hexm(ui.acc)).pack(side="left")
        mid = ui.frame(inner)
        mid.pack(side="left", padx=12)
        ui.lbl(mid, "TU RIVAL" + ("  ·  el de tu línea" if not self.enemy else ""), 9, "dim", True, anchor="w").pack(anchor="w")
        ui.lbl(mid, ui.champs[enemy]["name"], 16, "fg", True, True, anchor="w").pack(anchor="w")
        ui.lbl(mid, matchups.LANE_NAMES[lane] if lane else "línea sin elegir", 10, "dim", anchor="w").pack(anchor="w")
        opp = ((self.gui.ctx.get("info") or {}).get("opp") or {})
        mine = opp.get(enemy) or opp.get(str(enemy))
        if mine and mine[0]:
            g, lost = mine[0], mine[1]
            wins = max(0, g - lost)
            wr = round(wins / g * 100)
            row = ui.frame(mid)
            row.pack(anchor="w")
            ui.lbl(row, f"Tus partidas contra {ui.champs[enemy]['name']}: {g}  ·  ", 10, "dim", anchor="w").pack(side="left")
            ui.lbl(row, f"{wins}V {lost}D  ({wr} %)", 10, "good" if wins * 2 >= g else "bad", True, anchor="w").pack(side="left")
            vs = ((self.gui.ctx.get("info") or {}).get("vs_enemy") or {})
            det = vs.get(enemy) or vs.get(str(enemy)) or []
            if det:
                txt = "  ·  ".join(f"{ui.champs[c]['name']} {w}V {gg - w}D" for c, gg, w in det[:3] if c in ui.champs)
                if txt:
                    ui.lbl(mid, "Con " + txt, 9, "dim", anchor="w").pack(anchor="w")
            if g < 5:
                ui.lbl(mid, "Pocas partidas: tómalo como una pista, no como una regla.", 9, "dim", anchor="w").pack(anchor="w")
        if self.enemy:
            small_btn(ui, inner, "Quitar", self.clear_enemy, 64).pack(side="right")
        if lane:
            small_btn(ui, inner, "Su build" if not self.rival_open else "Ocultar su build",
                      lambda: self.toggle_rival(enemy, lane), 110).pack(side="right", padx=(0, 6))
        self.paint_rival(enemy, lane)

    def paint_rising(self, lane):
        """Campeones que suben de uso en esa línea (o que se juegan mucho más en Corea): lo que puede llegar al meta."""
        ui = self.ui
        host = getattr(self, "rise_host", None)
        if host is None or not host.winfo_exists():
            return
        self.ui.clear(host)
        data = core.TRENDS["data"]
        if not data or not lane:
            return
        lst = core.trends.rising(data, lane, 6)
        if not lst:
            return
        ui.lbl(host, f"EN AUGE EN {matchups.LANE_NAMES[lane].upper()}  ·  suben de uso frente al parche anterior, aquí o en las regiones que suelen ir por delante",
               9, "dim", True, anchor="w").pack(anchor="w", pady=(10, 4))
        row = ui.frame(host)
        row.pack(anchor="w")
        for cid, tag in lst:
            cell = ui.frame(row)
            cell.pack(side="left", padx=(0, 10))
            ui.champ(cell, cid, 34, True).pack()
            ui.lbl(cell, "▲ sube" if tag == "sube" else "▲ fuera", 8, "good", True).pack()
            ui.clickable(cell, lambda c=cid: self.select(c))
            e = core.trends.entry(data, lane, cid)
            ui.tip(cell, core.trends.describe(data, lane, cid))

    def head_key(self, ctx, enemy, lane):
        """Lo que decide cómo se ve el cartel del rival: si no cambia, no se repinta."""
        return (enemy, lane, self.rival_open, self.ui.epoch, bool((ctx.get("info") or {}).get("owned")), bool(self.enemy), self.level)

    def toggle_rival(self, enemy, lane):
        self.rival_open = not self.rival_open
        self.paint_banner(enemy, lane)
        self._bkey = self.head_key(self.gui.make_ctx(), enemy, lane)

    def paint_rival(self, enemy, lane):
        """Cómo juega el propio rival en esa línea (runas, objetos…), para saber a qué te enfrentas."""
        ui = self.ui
        if self.rival_slot is None or not self.rival_slot.winfo_exists():
            return
        self.ui.clear(self.rival_slot)
        if not (self.rival_open and enemy and lane):
            return
        panel = ctk.CTkFrame(self.rival_slot, fg_color=PAL["card2"], corner_radius=12)
        panel.pack(fill="x", pady=(0, 8))
        inner = ui.frame(panel)
        inner.pack(fill="x", padx=14, pady=12)
        ui.lbl(inner, f"Así juega {ui.champs[enemy]['name']} en {matchups.LANE_NAMES[lane].lower()}", 12, "fg", True, True, anchor="w").pack(anchor="w", pady=(0, 6))
        build_panel(ui, inner, enemy, lane, None, min(self.width - 150, 760)).pack(fill="x")

    def filtered(self, rows, ctx):
        info = ctx.get("info") or {}
        owned, stats = set(info.get("owned") or []), info.get("stats") or {}
        f, out = self.filt, []
        for r in rows:
            g = (stats.get(r["cid"]) or stats.get(str(r["cid"])) or [0, 0])[0]
            if r["games"] < MIN_GAMES[f["min"]]:
                continue
            if f["show"] == "Los que tengo" and owned and r["cid"] not in owned:
                continue
            if f["show"] == "Los que he jugado" and g < 1:
                continue
            if CLASSES[f["clase"]] and CLASSES[f["clase"]] not in self.ui.champs[r["cid"]]["tags"]:
                continue
            if f["adv"] and r["wr"] < 50:
                continue
            out.append((r, g))
        key = {"Más partidas": lambda x: -x[0]["games"], "Mayor ventaja": lambda x: -x[0]["delta"],
               "Más fiable": lambda x: -wilson(x[0]["wr"], x[0]["games"])[0]}.get(f["order"], lambda x: -x[0]["wr"])
        return sorted(out, key=key), owned

    def small_chip(self, parent, r, pack):
        """Aviso de muestra pequeña: con pocas partidas el porcentaje es poco fiable; el globo da el intervalo real."""
        if r["games"] >= SMALL:
            return
        lo, hi = wilson(r["wr"], r["games"])
        chip = self.ui.chip(parent, "Pocas partidas", "warn")
        chip.pack(**pack)
        self.ui.tip(chip, f"Con {r['games']} partidas, el porcentaje real podría estar entre el {round(lo * 100)} % y el {round(hi * 100)} %.\n"
                          "Se muestra porque hay datos, pero no te fíes tanto como de uno con muchas partidas.")

    def tag_of(self, r, g, owned):
        info = getattr(self, "_info", None) or {}
        enemy = getattr(self, "_enemy", None)
        if enemy:  # tu resultado con este campeón contra este rival, si lo hay
            for o, gg, ww in (info.get("champ_vs") or {}).get(r["cid"], []) or (info.get("champ_vs") or {}).get(str(r["cid"]), []):
                if o == enemy and gg:
                    return f"Contra él: {ww}V {gg - ww}D", ("good" if ww * 2 >= gg else "bad")
        if g:
            w = ((info.get("stats") or {}).get(r["cid"]) or (info.get("stats") or {}).get(str(r["cid"])) or [0, 0])[1]
            return f"Lo has jugado: {partidas(g)} · {round(w / g * 100)} %", "info"
        return ("No lo tienes", "warn") if owned and r["cid"] not in owned else ("No lo has jugado", "dim")

    def render(self, ctx, enemy, lane, rows):
        ui = self.ui
        self._info, self._enemy = ctx.get("info") or {}, enemy
        rows, owned = self.filtered(rows, ctx)
        wl = min(self.width - 90, 800)
        if not rows:
            ui.lbl(self.host, "Ningún campeón cumple los filtros. Prueba a bajar las «partidas mínimas» o a quitar filtros.", 11, "dim", anchor="w",
                   justify="left", wraplength=wl).pack(anchor="w", pady=6)
            return
        allr = bool(self.data.get((enemy, lane))) and self.data[(enemy, lane)][0].get("tier") == "all"
        ui.lbl(self.host, f"{len(rows)} campeones con datos contra {ui.champs[enemy]['name']} en {matchups.LANE_NAMES[lane].lower()}. "
                          "El porcentaje son las victorias del campeón frente al rival. Pulsa «Build» para ver runas, objetos y habilidades. "
                          "«Partidas ≥» sirve para ver también los que tienen pocas partidas (el orden «Más fiable» los pone en su sitio)."
                          + (" Hay pocos datos en tu rango: se usan los de todos los rangos." if allr else ""), 10, "dim", anchor="w",
               justify="left", wraplength=wl).pack(anchor="w", pady=(0, 8))
        if self.level == 0:
            for i, (r, g) in enumerate(rows[:self.shown]):
                cell = ctk.CTkFrame(self.host, fg_color=PAL["card2"], corner_radius=12)
                cell.pack(fill="x", pady=3)
                self.result_card(cell, i + 1, r, g, owned, enemy, lane)
        else:
            self.podium(rows[:3], owned, enemy, lane)
            rest = rows[3:self.shown]
            if rest:
                self.table(rest, 4, owned, enemy, lane)
        left = len(rows) - self.shown
        if left > 0:
            b = ctk.CTkButton(self.host, text=f"Mostrar {min(PAGE, left)} más  ({left} restantes)", height=34, corner_radius=10,
                              font=ui.font(12), fg_color=PAL["card2"], hover_color=PAL["card2"], text_color=PAL["fg"], command=self.more)
            b.pack(pady=(10, 0))
            ui.smooth_btn(b, PAL["card2"], PAL["border"])

    def more(self):
        self.shown += PAGE
        self.update(self.gui.make_ctx())

    def podium(self, top, owned, enemy, lane):
        ui = self.ui
        grid = ui.frame(self.host)
        grid.pack(fill="x", pady=(0, 10))
        for i in range(len(top)):
            grid.columnconfigure(i, weight=1, uniform="pd")
        medals = ("1º", "2º", "3º")
        for i, (r, g) in enumerate(top):
            cell = ctk.CTkFrame(grid, fg_color=PAL["card2"], corner_radius=14, border_width=1 if i == 0 else 0, border_color=ui.hexm(ui.acc))
            cell.grid(row=0, column=i, sticky="nsew", padx=4)
            inner = ui.frame(cell)
            inner.pack(padx=12, pady=12)
            head = ui.frame(inner)
            head.pack()
            ui.lbl(head, medals[i], 12, ui.acc if i == 0 else "dim", True, True).pack(side="left", padx=(0, 8))
            ui.champ(head, r["cid"], 44, False).pack(side="left")
            ui.lbl(inner, ui.champs[r["cid"]]["name"], 14, "fg", True, True).pack(pady=(6, 0))
            ok = r["wr"] >= 50
            ui.lbl(inner, f"{pct_es(r['wr'])} %", 22, "good" if ok else "bad", True, True).pack()
            ui.lbl(inner, f"{'+' if r['delta'] >= 0 else '−'}{pct_es(abs(r['delta']))} sobre su media · {r['games']} partidas", 9, "dim").pack()
            tag, color = self.tag_of(r, g, owned)
            ui.chip(inner, tag, col(color) if color != "dim" else "dim").pack(pady=(6, 0))
            self.small_chip(inner, r, dict(pady=(4, 0)))
            btns = ui.frame(inner)
            btns.pack(pady=(6, 0))
            small_btn(ui, btns, "Build", lambda c=r["cid"]: self.toggle_pod(c, enemy, lane), 54).pack(side="left", padx=(0, 6))
            small_btn(ui, btns, "Lolalytics", lambda c=r["cid"]: open_url(matchups.vs_url(ui.champs[c], ui.champs[enemy], lane)), 72).pack(side="left")
        self.pod_slot = ui.frame(self.host)
        self.pod_slot.pack(fill="x", pady=(0, 8))
        if self.pod_open in [r["cid"] for r, _ in top]:
            c0 = self.pod_open
            self.pod_open = None
            self.toggle_pod(c0, enemy, lane)

    def table(self, rows, start, owned, enemy, lane):
        ui, lv = self.ui, self.level
        wrap = ui.frame(self.host)
        wrap.pack()  # sin «fill»: la tabla queda centrada y cada fila se lee de una vez
        head = ui.frame(wrap)
        head.pack(fill="x", padx=10, pady=(0, 2))
        cols = [("", 26), ("", 34), ("Campeón", 130)] + ([("Victorias", 156), ("", 64), ("Ventaja", 78)] if lv >= 2 else [("Victorias", 64)])
        cols += [("Partidas", 74), ("Tú", 170)]
        for t, w in cols:
            ui.lbl(head, t.upper(), 8, "dim", True, width=w, anchor="w").pack(side="left")
        for i, (r, g) in enumerate(rows):
            box = ui.frame(wrap)
            box.pack(fill="x")
            row = ctk.CTkFrame(box, fg_color=PAL["card2"], corner_radius=10)
            row.pack(fill="x", pady=2)
            slot = ui.frame(box)
            slot.pack(fill="x")
            inner = ui.frame(row)
            inner.pack(fill="x", padx=10, pady=5)
            ok = r["wr"] >= 50
            ui.lbl(inner, str(start + i), 11, "dim", True, True, width=26, anchor="w").pack(side="left")
            ui.champ(inner, r["cid"], 28, False).pack(side="left", padx=(0, 6))
            ui.lbl(inner, ui.champs[r["cid"]]["name"], 12, "fg", True, width=130 - 0, anchor="w").pack(side="left")
            if lv >= 2:
                mini_bar(ui, inner, (r["wr"] - 40) / 25, "good" if ok else "bad", 140).pack(side="left", padx=(0, 16))
            ui.lbl(inner, f"{pct_es(r['wr'])} %", 12, "good" if ok else "bad", True, True, width=64, anchor="w").pack(side="left")
            if lv >= 2:
                ui.lbl(inner, f"{'+' if r['delta'] >= 0 else '−'}{pct_es(abs(r['delta']))}", 11, "good" if r["delta"] >= 0 else "bad",
                       width=78, anchor="w").pack(side="left")
            ui.lbl(inner, f"{r['games']}", 11, "dim", width=74, anchor="w").pack(side="left")
            tag, color = self.tag_of(r, g, owned)
            ui.chip(inner, tag, col(color) if color != "dim" else "dim").pack(side="left")
            self.small_chip(inner, r, dict(side="left", padx=(6, 0)))
            small_btn(ui, inner, "Lolalytics", lambda c=r["cid"]: open_url(matchups.vs_url(ui.champs[c], ui.champs[enemy], lane)), 72).pack(side="right")
            small_btn(ui, inner, "Build", lambda s=slot, c=r["cid"]: self.toggle_panel(s, c, enemy, lane), 54).pack(side="right", padx=(0, 6))
            if (r["cid"], enemy, lane) in self.opened:
                self.opened.discard((r["cid"], enemy, lane))
                self.toggle_panel(slot, r["cid"], enemy, lane)

    def toggle_panel(self, slot, cid, enemy, lane):
        """Abre o cierra la build debajo de una fila."""
        key = (cid, enemy, lane)
        if slot.winfo_children():
            self.ui.clear(slot)
            self.opened.discard(key)
            return
        self.opened.add(key)
        panel = ctk.CTkFrame(slot, fg_color=PAL["card"], corner_radius=10, border_width=1, border_color=PAL["border"])
        panel.pack(fill="x", padx=10, pady=(0, 6))
        inner = self.ui.frame(panel)
        inner.pack(fill="x", padx=12, pady=10)
        build_panel(self.ui, inner, cid, lane, enemy, min(self.width - 140, 720)).pack(fill="x")

    def toggle_pod(self, cid, enemy, lane):
        if self.pod_slot is None or not self.pod_slot.winfo_exists():
            return
        self.ui.clear(self.pod_slot)
        if self.pod_open == cid:
            self.pod_open = None
            return
        self.pod_open = cid
        panel = ctk.CTkFrame(self.pod_slot, fg_color=PAL["card2"], corner_radius=12)
        panel.pack(fill="x", padx=4, pady=(0, 6))
        inner = self.ui.frame(panel)
        inner.pack(fill="x", padx=14, pady=12)
        build_panel(self.ui, inner, cid, lane, enemy, min(self.width - 150, 760)).pack(fill="x")

    def result_card(self, cell, n, r, g, owned, enemy, lane):
        ui = self.ui
        inner = ui.frame(cell)
        inner.pack(fill="x", padx=10, pady=8)
        top = ui.frame(inner)
        top.pack(fill="x")
        ui.lbl(top, str(n), 11, "dim", True, True, width=24, anchor="w").pack(side="left")
        ui.champ(top, r["cid"], 36, False).pack(side="left")
        ok = r["wr"] >= 50
        mid = ui.frame(top)
        mid.pack(side="left", padx=10)
        ui.lbl(mid, ui.champs[r["cid"]]["name"], 13, "fg", True, anchor="w").pack(anchor="w")
        ui.lbl(mid, f"{'+' if r['delta'] >= 0 else '−'}{pct_es(abs(r['delta']))} sobre su media · {r['games']} partidas", 9, "dim",
               anchor="w").pack(anchor="w")
        ui.lbl(top, f"{pct_es(r['wr'])} %", 15, "good" if ok else "bad", True, True).pack(side="right")
        ui.bar(inner, [(min(max(r["wr"], 0), 100) / 100, "good" if ok else "bad")], 5).pack(fill="x", pady=(6, 6))
        foot = ui.frame(inner)
        foot.pack(fill="x")
        tag, color = self.tag_of(r, g, owned)
        ui.chip(foot, tag, col(color) if color != "dim" else "dim").pack(side="left")
        self.small_chip(foot, r, dict(side="left", padx=(6, 0)))
        small_btn(ui, foot, "Lolalytics", lambda c=r["cid"]: open_url(matchups.vs_url(ui.champs[c], ui.champs[enemy], lane)), 72).pack(side="right")
        slot = ui.frame(inner)
        slot.pack(fill="x")
        small_btn(ui, foot, "Build", lambda s=slot, c=r["cid"]: self.toggle_panel(s, c, enemy, lane), 54).pack(side="right", padx=(0, 6))
        if (r["cid"], enemy, lane) in self.opened:
            self.opened.discard((r["cid"], enemy, lane))
            self.toggle_panel(slot, r["cid"], enemy, lane)


def padlock(parent, ui, locked, size=38):
    """Candado dibujado: cerrado (ámbar) cuando los ajustes avanzados están protegidos, abierto (verde) cuando se pueden editar."""
    sx = ui.scale_px()
    px = int(size * sx)
    cv = tk.Canvas(parent, width=px, height=px, bg=ui.bg(parent), highlightthickness=0, bd=0)
    colr = ui.hexm(PAL["warn"] if locked else PAL["good"])
    w = max(2, int(3 * sx))
    cv.create_rectangle(.20 * px, .46 * px, .80 * px, .90 * px, fill=colr, outline=colr)
    if locked:
        cv.create_arc(.30 * px, .10 * px, .70 * px, .62 * px, start=0, extent=180, style="arc", outline=colr, width=w)
        cv.create_line(.30 * px, .36 * px, .30 * px, .47 * px, fill=colr, width=w)
        cv.create_line(.70 * px, .36 * px, .70 * px, .47 * px, fill=colr, width=w)
    else:
        cv.create_arc(.30 * px, .02 * px, .70 * px, .54 * px, start=0, extent=180, style="arc", outline=colr, width=w)
        cv.create_line(.30 * px, .28 * px, .30 * px, .47 * px, fill=colr, width=w)
    key = ui.bg(parent)
    cv.create_oval(.45 * px, .60 * px, .55 * px, .70 * px, fill=key, outline=key)
    cv.create_rectangle(.485 * px, .66 * px, .515 * px, .80 * px, fill=key, outline=key)
    return cv


class DataView:
    """Transparencia: de dónde sale cada dato, cómo se calcula la afinidad y qué se puede cambiar (con lo que implica)."""

    def __init__(self, ui, parent, gui):
        self.ui, self.gui = ui, gui
        self.box = ui.frame(parent)
        self.sig = None
        self.sliders, self.labels, self.preset_seg, self._t = {}, {}, None, {}
        self.locked, self.lock_hosts = True, []   # los números avanzados empiezan siempre bloqueados

    def refresh(self, ctx, force=False):
        width = ctx["width"]
        sig = (self.ui.epoch, bool(ctx.get("r")), min(width, 1000) // 120)
        if sig == self.sig and not force:
            return
        self.sig = sig
        self.ui.clear(self.box)
        self.wl = max(240, min(760, width - 110))  # los textos se ajustan al ancho disponible
        self.col = self.ui.frame(self.box)
        self.col.pack(fill="x", padx=max(0, (width - 52 - 900) // 2))  # en pantallas grandes, una columna central
        self.sliders, self.labels, self.lock_hosts = {}, {}, []
        self.sources_card()
        self.formula_card(ctx)
        self.params_card()
        self.glossary_card()

    # ---- fuentes ----
    def status_of(self, sid):
        cf, ui = self.ui.conf, self.ui
        d = core.META["data"]
        if sid == "opgg":
            meta = core.read_json(core.opgg_path(cf), {})
            return (cf["opgg_enabled"], f"actualizado hace {(time.time() - meta['ts']) / 3600:.0f} h" if meta.get("ts") else "sin datos todavía")
        if sid == "meta":
            return (cf["meta_enabled"], f"parche {core.metamod.public_patch(d['patch'])}{' (el ' + core.metamod.public_patch(d['current']) + ' aún sin datos)' if d.get('current', d['patch']) != d['patch'] else ''}"
                    f" · {core.metamod.TIER_NAMES.get(d['tier'], d['tier'])}" if d else
                    (core.META["error"] or "sin cargar todavía"))
        if sid == "matchups":
            n = len(os.listdir(os.path.join(core.CACHE, "matchups"))) if os.path.isdir(os.path.join(core.CACHE, "matchups")) else 0
            return (cf["matchups_enabled"], f"{n} rivales guardados")
        if sid == "ddragon":
            return (True, f"parche {core.metamod.public_patch(core.DD_VERSION)}" if core.DD_VERSION else "")
        return (True, "")

    def sources_card(self):
        ui = self.ui
        act = sum(1 for src in params.SOURCES if self.status_of(src[0])[0])
        ui.fold(self.col, "De dónde sale la información", self.sources_fill, f"{act} de {len(params.SOURCES)} fuentes activas", "dat_src", False)

    def sources_fill(self, c):
        ui = self.ui
        ui.lbl(c, "Todo lo personal se lee de tu cliente y se queda en tu ordenador. Las fuentes de internet son públicas y solo se "
                  "descargan datos generales o tu perfil público de op.gg.", 10, "dim", anchor="w", justify="left", wraplength=self.wl).pack(
            anchor="w", pady=(0, 8))
        toggles = {"opgg": "opgg_enabled", "meta": "meta_enabled", "matchups": "matchups_enabled"}
        for sid, name, gives, uses, optional in params.SOURCES:
            on, state = self.status_of(sid)
            row = ctk.CTkFrame(c, fg_color=PAL["card2"], corner_radius=10)
            row.pack(fill="x", pady=3)
            inner = ui.frame(row)
            inner.pack(fill="x", padx=12, pady=9)
            head = ui.frame(inner)
            head.pack(fill="x")
            ui.lbl(head, name, 13, "fg", True, True).pack(side="left")
            ui.chip(head, "Activa" if on else "Desactivada", "good" if on else "dim").pack(side="right")
            if state:
                ui.lbl(head, state + "   ", 10, "dim").pack(side="right")
            ui.lbl(inner, "Qué da: " + gives, 10, "dim", anchor="w", justify="left", wraplength=self.wl).pack(anchor="w", pady=(3, 0))
            ui.lbl(inner, "Para qué se usa: " + uses, 10, "fg", anchor="w", justify="left", wraplength=self.wl).pack(anchor="w")
            if optional:
                key = toggles[sid]
                var = ctk.BooleanVar(value=bool(ui.conf[key]))
                ctk.CTkSwitch(inner, text="Usar esta fuente", variable=var, font=ui.font(11), progress_color=ui.acc,
                              command=lambda key=key, var=var, sid=sid: self.toggle_source(key, var.get(), sid)).pack(anchor="w", pady=(6, 0))

    def toggle_source(self, key, on, sid):
        self.gui.set(key, on, recalc=True)
        if on and sid == "meta":
            self.gui.cmds.put("meta")
        if on and sid == "opgg":
            self.gui.cmds.put("opgg")
        self.sig = None
        self.refresh(self.gui.make_ctx())

    # ---- bloqueo de los números avanzados ----
    def style_slider(self, s):
        ui = self.ui
        if self.locked:
            s.configure(state="disabled", progress_color=ui.hexm(PAL["border"]), button_color=ui.hexm(PAL["border"]),
                        button_hover_color=ui.hexm(PAL["border"]))
        else:
            s.configure(state="normal", progress_color=ui.acc, button_color=ui.acc, button_hover_color=ui.acc)

    def lock_strip(self, parent):
        host = ctk.CTkFrame(parent, fg_color=PAL["card2"], corner_radius=12)
        host.pack(fill="x", pady=(0, 10))
        self.lock_hosts.append(host)
        self.paint_lock(host)

    def paint_lock(self, host):
        ui = self.ui
        self.ui.clear(host)
        narrow = self.wl < 420
        inner = ui.frame(host)
        inner.pack(fill="x", padx=12, pady=10)
        padlock(inner, ui, self.locked).pack(side="left", padx=(0, 12))
        txt = ui.frame(inner)
        txt.pack(side="left", fill="x", expand=True)
        ui.lbl(txt, "Ajustes avanzados bloqueados" if self.locked else "Edición desbloqueada", 12, "warn" if self.locked else "good",
               True, anchor="w").pack(anchor="w")
        msg = ("Estos números cambian cómo se ordenan tus recomendaciones. Si no tienes experiencia o no sabes qué estás haciendo, lo "
               "recomendable es dejarlos como están. Así evitas moverlos sin querer al hacer scroll."
               if self.locked else
               "Cualquier cambio altera tus recomendaciones. Puedes volver a los valores por defecto cuando quieras.")
        ui.lbl(txt, msg, 10, "dim", anchor="w", justify="left", wraplength=max(200, self.wl - (110 if narrow else 230))).pack(anchor="w")
        btns = ui.frame(host if narrow else inner)
        if narrow:
            btns.pack(fill="x", padx=12, pady=(0, 10))
        else:
            btns.pack(side="right", padx=(10, 0))
        for text, cmd, pad in (("Desbloquear" if self.locked else "Bloquear", self.toggle_lock, (0, 4)), ("Restablecer todo", self.reset_all, 0)):
            b = ctk.CTkButton(btns, text=text, height=26, width=110, corner_radius=8, font=ui.font(10), fg_color=PAL["border"],
                              text_color=PAL["fg"], hover_color=PAL["border"], command=cmd)
            ui.smooth_btn(b, PAL["border"], PAL["card"])
            b.pack(side="left" if narrow else "top", padx=(0, 6) if narrow else 0, pady=0 if narrow else pad)

    def toggle_lock(self):
        if self.locked and not messagebox.askyesno(
                "LOL-E", "Vas a poder cambiar los pesos y umbrales con los que se calculan las recomendaciones.\n\n"
                         "Si no sabes bien qué haces, lo mejor es dejarlos como están. Siempre podrás restablecerlos.\n\n"
                         "¿Desbloquear la edición?"):
            return
        self.locked = not self.locked
        for s in self.sliders.values():
            self.style_slider(s)
        self.lock_hosts = [h for h in self.lock_hosts if h.winfo_exists()]
        for h in self.lock_hosts:
            self.paint_lock(h)

    def reset_all(self):
        if not messagebox.askyesno("LOL-E", "Se restablecerán el estilo «Equilibrado», sus pesos y todos los umbrales a los valores por "
                                            "defecto.\n\n¿Restablecer?"):
            return
        self.pick_preset(core.PRESET_INFO["equilibrado"][0])
        self.reset_params(confirm=False)

    # ---- formula ----
    def formula_card(self, ctx):
        ui = self.ui
        ui.fold(self.col, "Cómo se calcula la afinidad", lambda c: self.formula_fill(c, ctx), "estilo: " + core.PRESET_INFO[ui.conf["preset"]][0], "dat_formula", False)

    def formula_fill(self, c, ctx):
        ui = self.ui
        self.lock_strip(c)
        ui.lbl(c, "Cada recomendación suma puntos de varios factores. Cada factor se multiplica por su peso; la afinidad (0 a 100) es la suma "
                  "dividida por un máximo realista. Mueve un peso y verás al instante cómo cambia el orden.", 10, "dim", anchor="w",
               justify="left", wraplength=self.wl).pack(anchor="w", pady=(0, 8))
        top = ui.frame(c)
        top.pack(fill="x", pady=(0, 6))
        ui.lbl(top, "Estilo", 11, "dim").pack(side="left", padx=(0, 8))
        names = {v[0]: k for k, v in core.PRESET_INFO.items()}
        self.names = names
        self.preset_seg = ui.seg(top, list(names), core.PRESET_INFO[ui.conf["preset"]][0], self.pick_preset, height=26)
        self.preset_seg.pack(side="left", fill="x", expand=True)
        self.preset_desc = ui.lbl(c, core.PRESET_INFO[ui.conf["preset"]][1], 10, "dim", anchor="w", wraplength=self.wl, justify="left")
        self.preset_desc.pack(anchor="w", pady=(0, 6))
        for key, (label, what, up, down) in params.WEIGHT_INFO.items():
            self.slider_row(c, key, label, what, up, down, ui.conf["weights"].get(key, 0.0), 0.0, 6.0, 0.1, True)
        small_btn(ui, c, "Volver al estilo «Equilibrado»", lambda: self.pick_preset("Equilibrado"), 200).pack(anchor="w", pady=(8, 0))
        r = ctx.get("r")
        if r and r.get("cands"):
            self.breakdown(c, r)

    def slider_row(self, parent, key, label, what, up, down, value, lo, hi, step, is_weight, fmt="{:.1f}"):
        ui = self.ui
        row = ui.frame(parent)
        row.pack(fill="x", pady=(8, 0))
        head = ui.frame(row)
        head.pack(fill="x")
        ui.lbl(head, label, 12, "fg", True).pack(side="left")
        val = ui.lbl(head, fmt.format(value), 12, ui.acc, True, True)
        val.pack(side="right")
        n = max(1, int(round((hi - lo) / step)))
        s = ctk.CTkSlider(row, from_=lo, to=hi, number_of_steps=n, height=14, progress_color=ui.acc, button_color=ui.acc,
                          button_hover_color=ui.acc, command=lambda v, key=key: self.on_slide(key, v, is_weight, fmt))
        s.set(value)
        self.style_slider(s)
        s.pack(fill="x", pady=(3, 2))
        ui.lbl(row, what, 10, "dim", anchor="w", justify="left", wraplength=self.wl).pack(anchor="w")
        ui.lbl(row, f"Subirlo: {up}", 10, "good", anchor="w", justify="left", wraplength=self.wl).pack(anchor="w")
        ui.lbl(row, f"Bajarlo: {down}", 10, "info", anchor="w", justify="left", wraplength=self.wl).pack(anchor="w")
        self.sliders[(is_weight, key)], self.labels[(is_weight, key)] = s, (val, fmt)

    def on_slide(self, key, v, is_weight, fmt):
        val, f = self.labels[(is_weight, key)]
        v = round(float(v), 2)
        val.configure(text=f.format(v))
        if (is_weight, key) in self._t:
            self.ui.root.after_cancel(self._t[(is_weight, key)])
        self._t[(is_weight, key)] = self.ui.root.after(450, lambda: self.apply(key, v, is_weight))

    def apply(self, key, v, is_weight):
        cf = self.ui.conf
        if is_weight:
            cf["custom_weights"] = {**cf["weights"], key: v}
            cf["preset"] = "personalizado"
            cf["weights"] = {**core.PRESETS["equilibrado"], **cf["custom_weights"]}
            if self.preset_seg is not None:
                self.preset_seg.set(core.PRESET_INFO["personalizado"][0])
                self.preset_desc.configure(text=core.PRESET_INFO["personalizado"][1])
        else:
            cf["params"] = {**cf["params"], key: v}
        core.save_conf(cf)
        self.gui.cmds.put("recalc")

    def pick_preset(self, name):
        cf = self.ui.conf
        key = self.names[name]
        cf["preset"] = key
        cf["weights"] = {**core.PRESETS["equilibrado"], **cf.get("custom_weights", {})} if key == "personalizado" else dict(core.PRESETS[key])
        core.save_conf(cf)
        self.preset_seg.set(name)
        self.preset_desc.configure(text=core.PRESET_INFO[key][1])
        for (is_w, k), s in self.sliders.items():
            if is_w:
                s.set(cf["weights"].get(k, 0.0))
                self.labels[(is_w, k)][0].configure(text=self.labels[(is_w, k)][1].format(cf["weights"].get(k, 0.0)))
        self.gui.cmds.put("recalc")

    def breakdown(self, parent, r):
        ui = self.ui
        c = r["cands"][0]
        ui.lbl(parent, f"EJEMPLO EN VIVO: {ui.champs[c['cid']]['name'].upper()} (la primera recomendación ahora mismo)", 10, "dim", True).pack(
            anchor="w", pady=(14, 4))
        breakdown_rows(ui, parent, c["parts"], c["score"], r["pct_scale"])

    # ---- umbrales ----
    def params_card(self):
        ui = self.ui
        ui.fold(self.col, "Umbrales y reglas", self.params_fill, "números avanzados (con candado)", "dat_params", False)

    def params_fill(self, c):
        ui = self.ui
        self.lock_strip(c)
        ui.lbl(c, "Números que deciden cuándo una regla se activa. Cada uno explica qué cambia si lo mueves.", 10, "dim", anchor="w",
               justify="left", wraplength=self.wl).pack(anchor="w")
        for key, (label, default, lo, hi, step, what, up, down) in params.PARAM_INFO.items():
            fmt = "{:.1f}" if isinstance(step, float) and step < 1 else "{:.0f}"
            self.slider_row(c, key, label, what, up, down, ui.conf["params"].get(key, default), lo, hi, step, False, fmt)
        small_btn(ui, c, "Restablecer umbrales", self.reset_params, 150).pack(anchor="w", pady=(8, 0))

    def reset_params(self, confirm=True):
        self.ui.conf["params"] = dict(params.DEFAULT_PARAMS)
        core.save_conf(self.ui.conf)
        for (is_w, k), s in self.sliders.items():
            if not is_w:
                s.set(params.DEFAULT_PARAMS[k])
                self.labels[(is_w, k)][0].configure(text=self.labels[(is_w, k)][1].format(params.DEFAULT_PARAMS[k]))
        self.gui.cmds.put("recalc")

    def glossary_card(self):
        ui = self.ui
        ui.fold(self.col, "Glosario", self.glossary_fill, "qué significa cada término", "dat_gloss", False)

    def glossary_fill(self, c):
        ui = self.ui
        for term, text in (
                ("Afinidad", "Número de 0 a 100: cuánto encaja un campeón contigo ahora mismo. No es una probabilidad de ganar."),
                ("Maestría", "Puntos de maestría de tu cuenta con ese campeón (el cliente de LoL)."),
                ("Meta", "Rendimiento del campeón en el parche, de todos los jugadores de tu rango o superior (Lolalytics)."),
                ("Sinergia", "Cómo encaja con los campeones ya elegidos por tus compañeros, según reglas de composición y vuestro historial."),
                ("Fuera de rol", "Campeón que no se suele jugar en tu línea y que tú no has jugado ahí las veces necesarias."),
                ("Enfrentamiento", "Resultado de un campeón contra otro concreto en la misma línea."),
                ("Estos datos no son oficiales", "LOL-E no es de Riot Games. Las estadísticas de terceros pueden cambiar o fallar.")):
            ui.lbl(c, term, 11, "fg", True, anchor="w").pack(anchor="w", pady=(6, 0))
            ui.lbl(c, text, 10, "dim", anchor="w", justify="left", wraplength=self.wl).pack(anchor="w")


LABELS = {"mastery": "Maestría", "winrate": "Tus victorias", "role": "Rol", "comp": "Equipo", "counter": "Contra rival",
          "meta": "Meta", "synergy": "Sinergia", "off_role": "Fuera de rol"}


def breakdown_rows(ui, parent, parts, total, scale, width=170):
    """Puntos que suma cada factor, con barra (verde suma, rojo resta). Sirve en la tarjeta y en la pestaña Datos."""
    big = max([abs(v) for v in parts.values()] + [1.0])
    sx = ui.scale_px()
    for k in ("mastery", "winrate", "role", "comp", "counter", "meta", "synergy", "off_role"):
        if k not in parts or (k == "off_role" and not parts[k]):
            continue
        v = parts[k]
        row = ui.frame(parent)
        row.pack(fill="x", pady=1)
        ui.lbl(row, LABELS[k], 10, "fg", width=92, anchor="w").pack(side="left")
        track = tk.Frame(row, width=int(width * sx), height=int(7 * sx), bg=ui.hexm(PAL["card2"] if ui.bg(parent) != ui.hexm(PAL["card2"]) else PAL["border"]))
        track.pack(side="left", padx=(0, 8))
        track.pack_propagate(False)
        tk.Frame(track, bg=ui.hexm(PAL["good" if v >= 0 else "bad"]), width=max(2, int(abs(v) / big * width * sx)), height=int(7 * sx)).pack(
            side="left")
        ui.lbl(row, f"{'+' if v >= 0 else '−'}{abs(v):.1f}".replace(".", ","), 10, "good" if v >= 0 else "bad", True).pack(side="left")
    pct = round(min(max(total, 0) / max(scale, 1), 1) * 100)
    tot = ui.frame(parent)
    tot.pack(fill="x", pady=(4, 0))
    ui.lbl(tot, f"Total {total:.1f} puntos → afinidad {pct}".replace(".", ","), 10, ui.acc, True, anchor="w").pack(anchor="w")
