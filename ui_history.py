"""Pestaña «Historial»: resumen con estadísticas, buscador, filtros y la lista de partidas por días (cada una se despliega)."""
import datetime, os, tkinter as tk, unicodedata
from collections import Counter

import customtkinter as ctk

import history
import lol_advisor as core
from ui_kit import PAL, ROLES_ES, ON_FILL
from ui_views import small_btn, mini_bar

STEP = 20
RANGES = [("Últimas 50", 50), ("Últimas 100", 100), ("Últimas 200", 200), ("Últimas 500", 500)]
MODES = ["Todos"] + [g for g in core.MODE_ORDER if g != "Otros"] + ["Personalizada", "Otros"]
RESULTS = ["Todas", "Victorias", "Derrotas"]
LINES = {"Todas": None, "Superior": "TOP", "Jungla": "JUNGLE", "Central": "MIDDLE", "Tirador": "BOTTOM", "Apoyo": "SUPPORT"}
SORTS = ["Más recientes", "Más antiguas", "Mejor KDA", "Más largas", "Más daño"]
WD = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MON = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
# anchos de columna (se usan igual en la cabecera y en las filas para que todo quede alineado)
W_NAME, W_KDA, W_CS, W_DMG, W_TIME, W_ITEMS, W_RES = 190, 110, 100, 100, 120, 180, 84


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


def mode_of(e):
    """Tipo de partida: se mira primero el modo y el tipo que da el cliente (Arena, personalizadas) y después la cola."""
    if e.get("gt") == "CUSTOM_GAME":
        return "Personalizada"
    if e.get("gm") == "CHERRY":
        return "Arena"
    return core.queue_group(e["q"])


def es(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def fecha(ms, hora=True):
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%d/%m/%Y %H:%M" if hora else "%d/%m/%Y")


def day_label(ms):
    d = datetime.datetime.fromtimestamp(ms / 1000).date()
    today = datetime.date.today()
    if d == today:
        return "Hoy"
    if d == today - datetime.timedelta(days=1):
        return "Ayer"
    return f"{WD[d.weekday()]} {d.day} {MON[d.month - 1]}" + (f" {d.year}" if d.year != today.year else "")


class HistoryView:
    def __init__(self, ui, parent, gui):
        self.ui, self.gui = ui, gui
        self.box = ui.frame(parent)
        self.sig = None
        self.all, self.loaded = [], False
        self.limit, self.q, self.mode, self.res, self.line, self.sort = None, "", "Todos", "Todas", "Todas", "Más recientes"
        self.shown, self._t, self.width, self.level = STEP, None, 520, 0
        self.list_host = self.summary_host = self.entry = None
        self.open = set()

    # ---- datos ----
    def reload(self):
        self.all = history.load_all(os.path.join(core.CACHE, "history.json"), os.path.join(core.CACHE, "games.json"))
        self.loaded = True

    def data_changed(self):
        """Llegó una partida nueva: se relee el archivo y se repinta."""
        self.reload()
        if self.list_host is not None and self.list_host.winfo_exists():
            self.sig = None
            self.refresh(self.gui.make_ctx(), True)

    def refresh(self, ctx, force=False):
        ui = self.ui
        width = ctx["width"]
        level = 3 if width >= 1120 else 2 if width >= 900 else 1 if width >= 640 else 0
        sig = (ui.epoch, level, width // 40 if level == 0 else 0)
        if not self.loaded:
            self.reload()
        if sig == self.sig and not force:
            return
        self.sig, self.width, self.level = sig, width, level
        for w in self.box.winfo_children():
            w.destroy()
        self.skeleton()
        self.render_all()

    # ---- estructura: resumen, filtros y lista ----
    def skeleton(self):
        ui = self.ui
        n = len(self.all)
        wl = min(self.width - 90, 780)
        self.sum_card = ui.card(self.box, "Resumen")
        self.summary_host = ui.frame(self.sum_card)
        self.summary_host.pack(fill="x")
        c = ui.card(self.box, "Buscar y filtrar")
        desde = fecha(self.all[-1]["t"], False) if n else ""
        ui.lbl(c, (f"{n} partidas guardadas desde el {desde}. " if n else "Todavía no hay partidas guardadas. ") +
               "El cliente de LoL solo entrega las últimas ~20, así que LOL-E guarda cada partida que ve: el historial crece mientras lo usas.",
               10, "dim", anchor="w", justify="left", wraplength=wl).pack(anchor="w", pady=(0, 8))
        narrow = self.level == 0
        todas = "Todas" if narrow or not n else f"Todas · hasta {desde}"
        self.range_names = [str(r[1]) if narrow else r[0] for r in RANGES] + [todas]
        cur = next((self.range_names[i] for i, r in enumerate(RANGES) if r[1] == self.limit), todas)
        ui.lbl(c, "Cuántas partidas mirar" if not narrow else "Últimas partidas a mostrar", 10, "dim", anchor="w").pack(anchor="w", pady=(0, 2))
        ui.seg(c, self.range_names, cur, self.set_range, height=28).pack(fill="x", pady=(0, 8))
        self.entry = ctk.CTkEntry(c, placeholder_text="Buscar por campeón…", height=32, font=ui.font(12), fg_color=PAL["card2"],
                                  border_color=PAL["border"], text_color=PAL["fg"])
        if self.q:
            self.entry.insert(0, self.q)
        self.entry.pack(fill="x", pady=(0, 8))
        self.entry.bind("<KeyRelease>", self.on_type)
        groups = [(("Modo", MODES, self.mode, "mode"), ("Resultado", RESULTS, self.res, "res"),
                   ("Línea", list(LINES), self.line, "line"), ("Orden", SORTS, self.sort, "sort"))]
        if self.level < 2:
            groups = [(("Modo", MODES, self.mode, "mode"), ("Resultado", RESULTS, self.res, "res")),
                      (("Línea", list(LINES), self.line, "line"), ("Orden", SORTS, self.sort, "sort"))]
        for pair in groups:
            row = ui.frame(c)
            row.pack(fill="x", pady=2)
            for label, values, cur_v, key in pair:
                ui.lbl(row, label, 10, "dim", width=58 if not narrow else 52, anchor="w").pack(side="left")
                ui.menu(row, values, cur_v, lambda v, k=key: self.set_filter(k, v), 128 if not narrow else 116).pack(
                    side="left", padx=(0, 14 if not narrow else 8))
        bar = ui.frame(c)
        bar.pack(fill="x", pady=(8, 0))
        small_btn(ui, bar, "Quitar filtros", self.clear_filters, 110).pack(side="left")
        small_btn(ui, bar, "Actualizar", self.update_now, 90).pack(side="right")
        self.list_card = ui.card(self.box)
        self.list_host = ui.frame(self.list_card)
        self.list_host.pack(fill="x")

    def update_now(self):
        self.gui.cmds.put("history")
        self.gui.status("Leyendo las partidas del cliente…")

    def clear_filters(self):
        self.q, self.mode, self.res, self.line, self.sort, self.limit = "", "Todos", "Todas", "Todas", "Más recientes", None
        self.shown = STEP
        self.sig = None
        self.refresh(self.gui.make_ctx(), True)

    def set_range(self, name):
        self.limit = dict(RANGES).get(name) or (int(name) if name.isdigit() else None)
        self.shown = STEP
        self.render_all()

    def set_filter(self, key, v):
        setattr(self, key, v)
        self.shown = STEP
        self.render_all()

    def on_type(self, _e=None):
        if self._t:
            self.ui.root.after_cancel(self._t)
        self._t = self.ui.root.after(220, self.typed)

    def typed(self):
        self._t = None
        self.q = self.entry.get().strip()
        self.shown = STEP
        self.render_all()

    # ---- filtrado ----
    def filtered(self):
        games = self.all[:self.limit] if self.limit else list(self.all)
        champs = self.ui.champs
        q = norm(self.q)
        if q:
            games = [e for e in games if q in norm(champs.get(e["c"], {}).get("name", ""))]
        if self.mode != "Todos":
            games = [e for e in games if mode_of(e) == self.mode]
        if self.res != "Todas":
            games = [e for e in games if e["w"] == (self.res == "Victorias")]
        if LINES[self.line]:
            games = [e for e in games if e["r"] == LINES[self.line]]
        key = {"Más antiguas": lambda e: e["t"], "Mejor KDA": lambda e: -(history.kda(e) if history.kda(e) is not None else -1),
               "Más largas": lambda e: -e["d"], "Más daño": lambda e: -(e["dm"] or 0)}.get(self.sort)
        return sorted(games, key=key) if key else games

    def render_all(self):
        if self.list_host is None or not self.list_host.winfo_exists():
            return
        games = self.filtered()
        self.render_summary(games)
        self.render_list(games)

    # ---- resumen de lo que estás viendo ----
    def tile(self, grid, i, cols, label, value, sub="", color="fg"):
        ui = self.ui
        cell = ctk.CTkFrame(grid, fg_color=PAL["card2"], corner_radius=12)
        cell.grid(row=i // cols, column=i % cols, sticky="nsew", padx=4, pady=4)
        inner = ui.frame(cell)
        inner.pack(fill="x", padx=12, pady=9)
        ui.lbl(inner, label.upper(), 9, "dim", True, anchor="w").pack(anchor="w")
        ui.lbl(inner, value, 17, color, True, True, anchor="w").pack(anchor="w", pady=(2, 0))
        if sub:
            ui.lbl(inner, sub, 9, "dim", anchor="w", wraplength=170, justify="left").pack(anchor="w")

    def render_summary(self, games):
        ui = self.ui
        for w in self.summary_host.winfo_children():
            w.destroy()
        if not games:
            ui.lbl(self.summary_host, "Sin partidas con estos filtros." if self.all else
                   "Cuando juegues, aquí verás tus estadísticas: victorias, KDA, rachas y tus campeones más jugados.", 11, "dim",
                   anchor="w", justify="left", wraplength=min(self.width - 90, 700)).pack(anchor="w")
            return
        s = history.summary(games)
        cols = 2 if self.level == 0 else 5
        grid = ui.frame(self.summary_host)
        grid.pack(fill="x")
        for k in range(cols):
            grid.columnconfigure(k, weight=1, uniform="hs")
        ordered = sorted((e for e in games if not e.get("rm")), key=lambda e: -e["t"])
        cur_win, n = (ordered[0]["w"], 0) if ordered else (True, 0)
        for e in ordered:
            if e["w"] != cur_win:
                break
            n += 1
        tiles = [("Partidas", str(s["n"]), f"{s['wins']} victorias · {s['n'] - s['wins']} derrotas", "fg"),
                 ("Victorias", f"{round(s['wr'] * 100)} %", "de las partidas mostradas", "good" if s["wr"] >= .5 else "bad")]
        if s["kda"] is not None:
            a = s["avg"]
            tiles.append(("KDA medio", es(s["kda"], 2), f"{es(a[0])} / {es(a[1])} / {es(a[2])} por partida", "good" if s["kda"] >= 3 else "fg"))
        durs = [e["d"] for e in games if e.get("d")]
        if durs:
            m = sum(durs) / len(durs)
            tiles.append(("Duración media", f"{int(m // 60)}:{int(m % 60):02d}", "minutos por partida", "fg"))
        if n:
            tiles.append(("Racha", f"{n} {'victoria' if cur_win else 'derrota'}{'s' if n != 1 else ''}", "las más recientes seguidas",
                          "good" if cur_win else "bad"))
        for i, t in enumerate(tiles):
            self.tile(grid, i, cols, *t)
        strip = ui.frame(self.summary_host)
        strip.pack(fill="x", pady=(8, 0))
        ui.lbl(strip, "ÚLTIMAS 20", 9, "dim", True).pack(side="left", padx=(4, 10))
        ui.dots(strip, [e["w"] for e in ordered[:20][::-1]]).pack(side="left")
        # campeones más jugados y reparto por modo
        two = ui.frame(self.summary_host)
        two.pack(fill="x", pady=(12, 0))
        two.columnconfigure(0, weight=1, uniform="two")
        if self.level >= 1:
            two.columnconfigure(1, weight=1, uniform="two")
        left = ui.frame(two)
        left.grid(row=0, column=0, sticky="nsew", padx=(4, 10))
        ui.lbl(left, "CAMPEONES MÁS JUGADOS", 9, "dim", True, anchor="w").pack(anchor="w", pady=(0, 4))
        cnt, win = Counter(e["c"] for e in games), Counter(e["c"] for e in games if e["w"])
        for cid, g in cnt.most_common(5):
            row = ui.frame(left)
            row.pack(fill="x", pady=2)
            ui.champ(row, cid, 26, False).pack(side="left")
            ui.lbl(row, ui.champs.get(cid, {}).get("name", "—"), 11, "fg", True, width=110, anchor="w").pack(side="left", padx=8)
            ui.lbl(row, f"{g} partida{'s' if g != 1 else ''}", 10, "dim", width=70, anchor="w").pack(side="left")
            wr = win[cid] / g
            ui.lbl(row, f"{round(wr * 100)} %", 11, "good" if wr >= .5 else "bad", True, width=44, anchor="w").pack(side="left")
        right = ui.frame(two)
        if self.level >= 1:
            right.grid(row=0, column=1, sticky="nsew", padx=(10, 4))
        else:
            right.grid(row=1, column=0, sticky="nsew", padx=4, pady=(12, 0))
        ui.lbl(right, "POR MODO", 9, "dim", True, anchor="w").pack(anchor="w", pady=(0, 4))
        modes = Counter(mode_of(e) for e in games)
        mw = Counter(mode_of(e) for e in games if e["w"])
        for name, g in modes.most_common(6):
            row = ui.frame(right)
            row.pack(fill="x", pady=2)
            wr = mw[name] / g
            ui.lbl(row, name, 11, "fg", True, width=96, anchor="w").pack(side="left")
            mini_bar(ui, row, g / modes.most_common(1)[0][1], "good" if wr >= .5 else "bad", 90 if self.level else 60).pack(side="left", padx=(0, 8))
            ui.lbl(row, f"{g}", 10, "dim", width=34, anchor="w").pack(side="left")
            ui.lbl(row, f"{round(wr * 100)} %", 11, "good" if wr >= .5 else "bad", True, width=44, anchor="w").pack(side="left")

    # ---- lista por días ----
    def col_header(self, wrap):
        ui, lv = self.ui, self.level
        head = ui.frame(wrap)
        head.pack(fill="x", padx=8, pady=(0, 2))
        ui.lbl(head, "", 8, "dim", width=38).pack(side="left")
        cols = [("Campeón", W_NAME), ("KDA", W_KDA)]
        if lv >= 1:
            cols.append(("Farmeo", W_CS))
        if lv >= 2:
            cols.append(("Daño", W_DMG))
        if lv >= 1:
            cols.append(("Duración y fecha", W_TIME))
        if lv >= 3:
            cols.append(("Objetos", W_ITEMS))
        cols.append(("Resultado", W_RES))
        for t, w in cols:
            ui.lbl(head, t.upper(), 8, "dim", True, width=w, anchor="w").pack(side="left", padx=(10, 0))

    def render_list(self, games):
        ui = self.ui
        for w in self.list_host.winfo_children():
            w.destroy()
        if not games:
            ui.lbl(self.list_host, "Ninguna partida cumple los filtros." if self.all else "Cuando juegues, tus partidas aparecerán aquí.",
                   11, "dim").pack(anchor="w", pady=6)
            return
        self.wrap = ui.frame(self.list_host)
        self.wrap.pack(fill="x" if self.level == 0 else None)  # sin «fill» queda centrada: la información de cada fila va junta
        if self.level >= 1:
            self.col_header(self.wrap)
        self.cur_games, self.built, self.last_day, self.more_b = games, 0, None, None
        self.by_day = self.sort in ("Más recientes", "Más antiguas")
        self.day_stats = {}
        for x in games:
            st = self.day_stats.setdefault(day_label(x["t"]), [0, 0])
            st[0] += 1
            st[1] += x["w"]
        self.append_rows()

    def append_rows(self):
        """Añade solo las filas que faltan (y el botón de «Mostrar más»): pedir más partidas no repinta las anteriores."""
        ui, games = self.ui, self.cur_games
        shown = games[:self.shown]
        for e in shown[self.built:]:
            d = day_label(e["t"])
            if self.by_day and d != self.last_day:
                self.last_day = d
                n, w = self.day_stats[d]
                h = ui.frame(self.wrap)
                h.pack(fill="x", pady=(10, 2), padx=4)
                ui.lbl(h, d.upper(), 10, "fg", True).pack(side="left")
                ui.lbl(h, f"  ·  {n} partida{'s' if n != 1 else ''}  ·  {w}V {n - w}D", 10, "dim").pack(side="left")
            self.row(self.wrap, e)
        self.built = len(shown)
        if self.more_b is not None:
            self.more_b.destroy()
            self.more_b = None
        left = len(games) - self.shown
        if left > 0:
            b = ctk.CTkButton(self.list_host, text=f"Mostrar {min(STEP, left)} más  ({left} restantes)", height=34, corner_radius=10,
                              font=ui.font(12), fg_color=PAL["card2"], hover_color=PAL["card2"], text_color=PAL["fg"], command=self.more)
            b.pack(pady=(10, 0))
            ui.smooth_btn(b, PAL["card2"], PAL["border"])
            self.more_b = b

    def more(self):
        self.shown += STEP
        self.append_rows()

    def row(self, parent, e):
        """Una partida: un solo lienzo con todo dibujado (texto, iconos, objetos y resultado). Antes eran ~40 widgets por fila y
        Tk tardaba más en colocarlos que Python en crearlos."""
        ui, lv = self.ui, self.level
        sx = ui.scale_px()
        champs = ui.champs
        box = ui.frame(parent)
        box.pack(fill="x", pady=3)
        arena = mode_of(e) == "Arena"
        grp = mode_of(e)
        role = ROLES_ES.get(e["r"], "") if e["r"] and not arena else ""
        sub = " · ".join(x for x in (grp, role) if x)
        if lv == 0:
            sub += f" · {fecha(e['t'], False)[:5]}"
        widths = [150 if lv == 0 else W_NAME, 92 if lv == 0 else W_KDA]
        if lv >= 1:
            widths += [W_CS]
        if lv >= 2:
            widths += [W_DMG]
        if lv >= 1:
            widths += [W_TIME]
        if lv >= 3:
            widths += [W_ITEMS]
        chip_w = 28 if lv == 0 else W_RES
        left = 8 + 38 + 10
        total = left + sum(w + 10 for w in widths) + chip_w + 8 - (10 if lv == 0 else 0)
        H = 52
        cw = int((max(300, self.width - 100) if lv == 0 else total) * sx)
        cv = tk.Canvas(box, width=cw, height=int(H * sx), bg=ui.bg(parent), highlightthickness=0, bd=0, cursor="hand2")
        cv.pack(fill="x" if lv == 0 else None)
        ui.rrect(cv, 0, 0, cw - 1, int(H * sx) - 1, int(10 * sx), fill=ui.hexm(PAL["card2"]), outline="")
        color = "dim" if e.get("rm") else "good" if e["w"] else "bad"
        f12b, f10, f12 = ui.tkf(12, True, False), ui.tkf(10, False, False), ui.tkf(12, False, False)
        fg, dim = ui.hexm(PAL["fg"]), ui.hexm(PAL["dim"])
        ph = ui.champ_photo(e["c"], 38) if e["c"] else None
        if ph is not None:
            cv.create_image(int(8 * sx), int(7 * sx), image=ph, anchor="nw")
            cv.image = getattr(cv, "image", [])
            cv.image.append(ph)
        else:
            cv.create_rectangle(int(8 * sx), int(7 * sx), int(46 * sx), int(45 * sx), fill=ui.hexm(PAL["card"]), outline="")
        x = left

        def two(x, top, bottom, w, top_color=fg, bottom_color=dim, bold=True):
            cv.create_text(int(x * sx), int(17 * sx), text=ui.fit(top, f12b if bold else f12, int(w * sx)), font=f12b if bold else f12, fill=top_color, anchor="w")
            cv.create_text(int(x * sx), int(35 * sx), text=ui.fit(bottom, f10, int(w * sx)), font=f10, fill=bottom_color, anchor="w")
        two(x, champs.get(e["c"], {}).get("name", f"Campeón {e['c']}"), sub, widths[0])
        x += widths[0] + 10
        k = history.kda(e)
        if k is None:
            two(x, "—", "sin detalle", widths[1], dim)
        else:
            two(x, f"{e['k']} / {e['de']} / {e['a']}", f"KDA {es(k, 2)}", widths[1], fg, ui.hexm(PAL["good"]) if k >= 3 else dim)
        x += widths[1] + 10
        n = 2
        if lv >= 1:
            mins = max(1, e["d"] / 60)
            has_cs = e["cs"] is not None and not arena
            two(x, f"{e['cs']} CS" if has_cs else "—", f"{es(e['cs'] / mins)} por min" if has_cs and e["d"] else "", widths[n], fg if has_cs else dim)
            x += widths[n] + 10
            n += 1
        if lv >= 2:
            two(x, f"{es(e['dm'] / 1000)}k daño" if e["dm"] else "—", f"Nivel {e['lv']}" if e["lv"] else "", widths[n], fg if e["dm"] else dim)
            x += widths[n] + 10
            n += 1
        if lv >= 1:
            dur = f"{e['d'] // 60}:{e['d'] % 60:02d}" if e["d"] else "—"
            two(x, dur, fecha(e["t"]), widths[n], fg if e["d"] else dim)
            x += widths[n] + 10
            n += 1
        if lv >= 3:
            if e.get("it") is None:
                cv.create_text(int(x * sx), int(26 * sx), text="—", font=f12b, fill=dim, anchor="w")
            else:
                for q, iid in enumerate(e["it"]):
                    ix, iy = int((x + q * 26) * sx), int(14 * sx)
                    iph = ui.item_photo(iid, 24) if iid else None
                    if iph is not None:
                        it = cv.create_image(ix, iy, image=iph, anchor="nw")
                        cv.image.append(iph)
                        info = ui.items.get(iid)
                        if info:
                            ui.canvas_tip(cv, it, f"{info['n']}  ·  {info['g']} de oro" + (f"\n{info['d']}" if info["d"] else ""))
                    else:
                        cv.create_rectangle(ix, iy, ix + int(24 * sx), iy + int(24 * sx), fill=ui.hexm(PAL["card"]), outline="")
            x += widths[n] + 10
        txt = "Remake" if e.get("rm") else ("Victoria" if e["w"] else "Derrota")
        if arena and e.get("pl"):
            txt = f"Puesto {e['pl']}º"  # Arena se puntúa por puesto: del 1º al 3º cuenta como victoria
        if lv == 0:
            txt = (f"{e['pl']}º" if arena and e.get("pl") else "V" if e["w"] and not e.get("rm") else "D" if not e.get("rm") else "R")
            cx1 = cw - int((8 + chip_w) * sx)
        else:
            cx1 = int(x * sx)
        cy = int((H - 24) / 2 * sx)
        ui.rrect(cv, cx1, cy, cx1 + int(chip_w * sx), cy + int(24 * sx), int(8 * sx), fill=ui.hexm(PAL[color]), outline="")
        cv.create_text(cx1 + int(chip_w * sx / 2), cy + int(12 * sx), text=txt, font=ui.tkf(10, True, True), fill=ui.hexm(PAL["bg"]))
        detail = {"w": None}

        def toggle(_e=None):
            if detail["w"] is not None:
                detail["w"].destroy()
                detail["w"] = None
                self.open.discard(e["id"])
            else:
                detail["w"] = self.detail(box, e)
                self.open.add(e["id"])
        cv.bind("<Button-1>", toggle)
        if e["id"] in self.open:
            toggle()

    def items_row(self, parent, e, size):
        ui = self.ui
        if e.get("it") is None:
            ui.lbl(parent, "—", 12, "dim", width=W_ITEMS, anchor="w").pack(anchor="w")
            return
        for iid in e["it"]:
            ph = ui.item_photo(iid, size) if iid else None
            if ph is not None:
                lab = tk.Label(parent, image=ph, bd=0, highlightthickness=0, bg=ui.bg(parent))
                lab.image = ph
                info = ui.items.get(iid)
                if info:
                    ui.tip(lab, f"{info['n']}  ·  {info['g']} de oro" + (f"\n{info['d']}" if info["d"] else ""))
            else:
                px = int(size * ui.scale_px())
                lab = tk.Frame(parent, width=px, height=px, bg=ui.hexm(PAL["card"]))
            lab.pack(side="left", padx=1)

    def detail(self, box, e):
        """Datos extra de la partida, justo debajo de su fila."""
        ui = self.ui
        d = ctk.CTkFrame(box, fg_color=PAL["card"], corner_radius=10, border_width=1, border_color=PAL["border"])
        d.pack(fill="x", pady=(0, 6), padx=10)
        inner = ui.frame(d)
        inner.pack(fill="x", padx=12, pady=10)
        mins = max(1, e["d"] / 60) if e.get("d") else 0
        arena = mode_of(e) == "Arena"
        parts = []
        if e.get("pl") and arena:
            parts.append(f"Puesto {e['pl']}º de 6")
        if e.get("lv"):
            parts.append(f"Nivel {e['lv']}")
        if e.get("g"):
            parts.append(f"{es(e['g'] / 1000)}k de oro")
        if e.get("dm") and mins:
            parts.append(f"{int(e['dm'] / mins)} de daño por minuto")
        if e.get("cs") and mins and not arena:
            parts.append(f"{es(e['cs'] / mins)} CS por minuto")
        if e.get("v") is not None and not arena:
            parts.append(f"visión {e['v']}")
        ui.lbl(inner, "  ·  ".join(parts) if parts else "Esta partida se guardó sin detalle (de una versión anterior).", 11, "fg", anchor="w",
               justify="left", wraplength=min(self.width - 130, 760)).pack(anchor="w")
        if e.get("it") and any(e["it"]):
            row = ui.frame(inner)
            row.pack(anchor="w", pady=(8, 0))
            self.items_row(row, e, 32)
            names = [ui.items[i]["n"] for i in e["it"] if i and i in ui.items]
            if names:
                ui.lbl(inner, "Objetos: " + ", ".join(names), 10, "dim", anchor="w", justify="left",
                       wraplength=min(self.width - 130, 760)).pack(anchor="w", pady=(6, 0))
        ui.lbl(inner, f"Partida del {fecha(e['t'])} · número {e['id']}", 9, "dim", anchor="w").pack(anchor="w", pady=(6, 0))
        return d
