"""Pestaña «Historial»: resumen con estadísticas, buscador, filtros y la lista de partidas por días (cada una se despliega)."""
import datetime, os, subprocess, time, tkinter as tk, unicodedata
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
        self.list_host = self.summary_host = self.entry = self.filter_fold = None
        self.day_state, self.days, self.day_games = {}, {}, {}   # días plegados o desplegados, y sus partidas
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
        self.ui.clear(self.box)
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
        desde = fecha(self.all[-1]["t"], False) if n else ""
        self.filter_fold = ui.fold(self.box, "Buscar y filtrar", lambda c: self.filters(c, n, wl, desde), self.filter_summary(), "hist_filters", False,
                                   action=("Restablecer filtros", self.clear_filters))
        self.filter_fold.show_action(self.filters_active())
        self.list_card = ui.card(self.box)
        self.list_host = ui.frame(self.list_card)
        self.list_host.pack(fill="x")

    def filters_active(self):
        return bool(self.q or self.mode != "Todos" or self.res != "Todas" or self.line != "Todas" or self.limit or self.sort != "Más recientes")

    def filter_summary(self):
        act = [x for x in (self.mode if self.mode != "Todos" else "", self.res if self.res != "Todas" else "", self.line if self.line != "Todas" else "",
                           f"«{self.q}»" if self.q else "") if x]
        return (" · ".join(act) if act else "sin filtros") + f" · {len(self.all)} partidas"

    def filters(self, c, n, wl, desde):
        ui = self.ui
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
        small_btn(ui, bar, "Restablecer filtros", self.clear_filters, 140).pack(side="left")
        small_btn(ui, bar, "Actualizar", self.update_now, 90).pack(side="right")
        small_btn(ui, bar, "Exportar CSV", self.export_csv, 110).pack(side="right", padx=(0, 6))

    def export_csv(self):
        """Guarda las partidas que ves (con los filtros puestos) en Documentos, listas para abrir con Excel."""
        import csv
        games = self.filtered()
        folder = os.path.join(os.path.expanduser("~"), "Documents")
        path = os.path.join(folder if os.path.isdir(folder) else os.path.expanduser("~"), "LOL-E_historial.csv")
        champs = self.ui.champs
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Fecha", "Modo", "Campeón", "Línea", "Resultado", "Muertes", "Asesinatos", "Asistencias", "Farmeo",
                            "Daño", "Duración (s)", "Nivel", "Puesto (Arena)"])
                for e in games:
                    w.writerow([time.strftime("%Y-%m-%d %H:%M", time.localtime(e["t"] / 1000)), mode_of(e),
                                champs.get(e["c"], {}).get("name", e["c"]), ROLES_ES.get(e["r"], ""),
                                "Remake" if e.get("rm") else "Victoria" if e["w"] else "Derrota",
                                e.get("de"), e.get("k"), e.get("a"), e.get("cs"), e.get("dm"), e.get("d"), e.get("lv"), e.get("pl")])
            self.gui.status(f"Exportadas {len(games)} partidas a {path}")
            subprocess.Popen(["explorer", "/select,", path])
        except Exception as ex:
            self.gui.status(f"No se pudo exportar: {ex}")

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
        try:
            self.filter_fold.set_summary(self.filter_summary())
            self.filter_fold.show_action(self.filters_active())
        except Exception:
            pass
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
        self.ui.clear(self.summary_host)
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
        self.ui.clear(self.list_host)
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
        self.day_stats, self.day_games, self.days = {}, {}, {}
        for x in games:
            d = day_label(x["t"])
            st = self.day_stats.setdefault(d, [0, 0])
            st[0] += 1
            st[1] += x["w"]
            self.day_games.setdefault(d, []).append(x)
        if self.by_day and len(self.day_stats) > 1:
            bar = ui.frame(self.wrap)
            bar.pack(fill="x", padx=8, pady=(0, 2))
            small_btn(ui, bar, "Plegar todos los días", lambda: self.fold_days(False), 150).pack(side="left")
            small_btn(ui, bar, "Desplegar todos", lambda: self.fold_days(True), 130).pack(side="left", padx=(6, 0))
        self.append_rows()

    def append_rows(self):
        """Añade solo las filas que faltan (y el botón de «Mostrar más»): pedir más partidas no repinta las anteriores."""
        ui, games = self.ui, self.cur_games
        shown = games[:self.shown]
        for e in shown[self.built:]:
            d = day_label(e["t"])
            if self.by_day:
                dd = self.days.get(d) or self.new_day(d)
                dd["games"].append(e)
                if dd["open"]:
                    self.row(dd["body"], e)
                else:
                    dd["pending"].append(e)  # el día está plegado: sus filas se pintan al desplegarlo
            else:
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

    def row_width(self):
        """Ancho de una fila (el mismo cálculo que en row()), para que la cabecera del día case con ellas."""
        lv = self.level
        widths = [150 if lv == 0 else W_NAME, 92 if lv == 0 else W_KDA] + ([W_CS] if lv >= 1 else []) + ([W_DMG] if lv >= 2 else []) + \
                 ([W_TIME] if lv >= 1 else []) + ([W_ITEMS] if lv >= 3 else [])
        chip_w = 28 if lv == 0 else W_RES
        total = 8 + 38 + 10 + sum(w + 10 for w in widths) + chip_w + 8 - (10 if lv == 0 else 0)
        return max(300, self.width - 100) if lv == 0 else total

    def new_day(self, d):
        """Cabecera del día (resumen y burbujas) y contenedor de sus filas; por defecto solo están desplegados los dos días más recientes."""
        ui = self.ui
        box = ui.frame(self.wrap)
        box.pack(fill="x", pady=(8, 2), padx=4)
        head = ui.frame(box)
        head.pack(fill="x")
        body = ui.frame(box)
        default = len(self.days) < 2
        st = {"open": self.day_state.get(d, default), "games": [], "pending": [], "body": body, "head": head, "label": d}
        self.days[d] = st
        self.paint_day(st)
        if st["open"]:
            body.pack(fill="x")
        return st

    def paint_day(self, st):
        """Cabecera del día en un solo lienzo: flecha, nombre, resumen, barra de balance y una burbuja por partida (verde ganada, roja perdida)."""
        ui = self.ui
        d, items = st["label"], self.day_games[st["label"]]
        ui.clear(st["head"])
        sx = ui.scale_px()
        S = lambda v: int(v * sx)
        W, H = self.row_width(), 60
        cv = tk.Canvas(st["head"], width=S(W), height=S(H), bg=ui.bg(st["head"]), highlightthickness=0, bd=0, cursor="hand2")
        cv.pack(anchor="w")
        ui.rrect(cv, 0, 0, S(W) - 1, S(H) - 1, S(10), fill=ui.hexm(PAL["card2"]), outline="")
        n = len(items)
        wins = sum(1 for g in items if g["w"] and not g.get("rm"))
        losses = sum(1 for g in items if not g["w"] and not g.get("rm"))
        played = max(1, wins + losses)
        pct = round(wins / played * 100)
        good, bad, dim, fg = ui.hexm(PAL["good"]), ui.hexm(PAL["bad"]), ui.hexm(PAL["dim"]), ui.hexm(PAL["fg"])
        cv.create_text(S(14), S(20), text="▾" if st["open"] else "▸", fill=dim, font=ui.tkf(12, False, False), anchor="w")
        cv.create_text(S(34), S(19), text=d.upper(), fill=fg, font=ui.tkf(11, True, False), anchor="w")
        cv.create_text(S(34), S(37), text=f"{n} partida{'s' if n != 1 else ''}  ·  {wins}V {losses}D  ·  {pct} %", fill=good if pct >= 50 else bad,
                       font=ui.tkf(9, True, False), anchor="w")
        # barra de balance: la parte verde es la proporción de victorias
        bx0, bx1, by = S(14), S(W - 14), S(H - 9)
        cv.create_rectangle(bx0, by, bx1, by + S(3), fill=bad, outline="")
        cv.create_rectangle(bx0, by, bx0 + int((bx1 - bx0) * wins / played), by + S(3), fill=good, outline="")
        # burbujas: las más recientes del día; si hay más de las que caben, una burbuja «+N» abre la lista
        size, step = 28, 31                      # burbujas separadas por un hueco de 3 px
        text_w = 34 + max(len(f"{n} partidas  ·  {wins}V {losses}D  ·  {pct} %"), len(d)) * 6.2   # lo que ocupa el texto de la izquierda
        room = int((W - 20 - text_w) // step) - 1                    # sitio para burbujas, dejando una de reserva para el «+N»
        show = items[:max(1, min(room, 10))]
        if n - len(show) == 1 and len(show) < 10:  # una sola oculta: mejor enseñarla que una burbuja «+1»
            show = items[:len(show) + 1]
        hidden = n - len(show)
        x = W - 14 - size
        for g in show:  # de la más reciente (a la derecha) hacia atrás
            ring = good if g["w"] and not g.get("rm") else bad if not g.get("rm") else dim
            ph = ui.bubble(g["c"], size, ring, 2)
            it = cv.create_image(S(x), S(16), image=ph, anchor="nw")
            cv.image = getattr(cv, "image", []) + [ph]
            ui.canvas_tip(cv, it, f"{ui.champs.get(g['c'], {}).get('name', '?')} · {'Remake' if g.get('rm') else 'Victoria' if g['w'] else 'Derrota'} · {fecha(g['t'])}")
            x -= step
        if hidden > 0:
            ph = ui.bubble(None, size, dim, 2, fill=ui.hexm(PAL["card"]))   # mismo dibujo y borde suave que las demás
            cv.create_image(S(x), S(16), image=ph, anchor="nw")
            cv.image = getattr(cv, "image", []) + [ph]
            cv.create_text(S(x + size / 2), S(16 + size / 2), text=f"+{hidden}", fill=fg, font=ui.tkf(9, True, False))
        cv.bind("<Button-1>", lambda e, s=st: self.toggle_day(s))

    def toggle_day(self, st, to=None):
        st["open"] = (not st["open"]) if to is None else to
        self.day_state[st["label"]] = st["open"]
        if st["open"]:
            for e in st["pending"]:
                self.row(st["body"], e)
            st["pending"] = []
            st["body"].pack(fill="x")
        else:
            st["body"].pack_forget()
        self.paint_day(st)

    def fold_days(self, open_):
        for st in self.days.values():
            if st["open"] != open_:
                self.toggle_day(st, open_)

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
