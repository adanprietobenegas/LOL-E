"""Repertorio: tus campeones, ordenables, con un panel de detalle (resumen, partidas y build).

La pantalla responde primero a su pregunta («¿con qué campeones me va bien?»): un titular con el hallazgo, cuatro cifras, la tabla de
campeones y, al lado, el campeón elegido. En ventanas estrechas el detalle va encima de la tabla.
"""
import tkinter as tk
from collections import Counter

import customtkinter as ctk

import history
import lol_advisor as core
from ui_build import build_panel
from ui_history import fecha, mode_of
from ui_kit import PAL, ROLES_ES
from ui_views import mini_bar, small_btn

SORTS = ["Más jugados", "Mejor porcentaje", "Maestría", "Reciente"]
SCOPES = ["Grieta (temporada)", "Todos los modos"]
LANE_SEG = ["Superior", "Jungla", "Central", "Tirador", "Apoyo"]
LANE_KEY = {"Superior": "top", "Jungla": "jungle", "Central": "middle", "Tirador": "bottom", "Apoyo": "support"}
ROLE_LANE = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support", "UTILITY": "support"}
LANE_NAME = {v: k for k, v in LANE_KEY.items()}
NO_LANE_MODES = ("ARAM", "Arena", "Personalizada", "Otros")
PAGE = 10


def es(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


class PoolPanel:
    def __init__(self, ui, ctx, hist):
        self.ui, self.ctx, self.hist = ui, ctx, hist
        self.sort, self.scope, self.sel, self.dtab, self.shown = SORTS[0], SCOPES[0], None, "Resumen", PAGE
        self.lane_pick = {}   # campeón -> línea elegida para la build
        self.root, self.cards, self.dparent = None, {}, None

    # ---- datos ----
    def rows(self):
        info = self.ctx["info"] or {}
        mast = {int(k): v for k, v in (info.get("mastery_all") or {}).items()}
        by_champ = {}
        for e in self.hist:
            by_champ.setdefault(e["c"], []).append(e)
        out = []
        if self.scope == SCOPES[0]:
            season = {int(k): v for k, v in (info.get("season") or {}).items() if v[0] >= 3}  # temporada (op.gg): más muestra que lo local
            src = season or {int(k): v for k, v in (info.get("stats") or {}).items() if v[0] >= 2}
        else:
            src = {c: [len(g), sum(1 for e in g if e["w"])] for c, g in by_champ.items()}
        for cid, (g, w) in src.items():
            if cid not in self.ui.champs or g <= 0:
                continue
            games = [e for e in by_champ.get(cid, []) if self.scope == SCOPES[1] or mode_of(e) not in NO_LANE_MODES]
            sm = history.summary(games) if games else None
            out.append({"cid": cid, "g": g, "w": w, "wr": w / g, "kda": sm["kda"] if sm else None, "games": games,
                        "mast": mast.get(cid, 0), "last": max((e["t"] for e in games), default=0),
                        "form": [e["w"] for e in games[:5]][::-1]})
        key = {"Mejor porcentaje": lambda r: (-r["wr"], -r["g"]), "Maestría": lambda r: -r["mast"], "Reciente": lambda r: -r["last"]}.get(
            self.sort, lambda r: (-r["g"], -r["wr"]))
        return sorted(out, key=key)

    # ---- montaje ----
    def mount(self, parent):
        self.parent = parent
        self.render()

    def render(self):
        ui = self.ui
        if self.root is not None and self.root.winfo_exists():
            self.root.destroy()
        self.root = ui.frame(self.parent)
        self.root.pack(fill="x")
        rows = self.rows()
        self.data = rows
        if self.sel not in [r["cid"] for r in rows]:
            self.sel = rows[0]["cid"] if rows else None
        width = self.ctx["width"]
        self.wide = width >= 1000
        self.narrow = width < 640
        self.cards = {}
        self.header(rows)
        if not rows:
            ui.lbl(self.root, "Aún no hay campeones con partidas aquí. Prueba «Todos los modos», o juega con LOL-E abierto para que las guarde.", 11, "dim", anchor="w").pack(anchor="w", pady=8)
            return
        body = ui.frame(self.root)
        body.pack(fill="x", pady=(10, 0))
        if self.wide:
            body.columnconfigure(0, weight=3, uniform="pl")
            body.columnconfigure(1, weight=2, uniform="pl")
            left, right = ui.frame(body), ui.frame(body)
            left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
            right.grid(row=0, column=1, sticky="nsew")
            self.dw = int((width - 120) * 0.38)
            self.dparent = right
            self.table_host = left
            self.table(left, rows)
            self.detail(right, next(r for r in rows if r["cid"] == self.sel))
        else:
            self.dw = max(280, width - 110)
            top, bottom = ui.frame(body), ui.frame(body)
            top.pack(fill="x")
            bottom.pack(fill="x", pady=(10, 0))
            self.dparent = top
            self.detail(top, next(r for r in rows if r["cid"] == self.sel))
            self.table_host = bottom
            self.table(bottom, rows)

    # ---- titular y cifras ----
    def header(self, rows):
        ui = self.ui
        top = ui.frame(self.root)
        top.pack(fill="x")
        ui.lbl(top, "Tu repertorio", 16, "fg", True, True, anchor="w").pack(side="left")
        ui.seg(top, SCOPES, self.scope, self.set_scope, height=26).pack(side="right")
        if not rows:
            return
        tot = sum(r["g"] for r in rows)
        wins = sum(r["w"] for r in rows)
        sure = [r for r in rows if r["g"] >= 5]
        best = max(sure, key=lambda r: (r["wr"], r["g"]), default=None)
        worst = min((r for r in sure if r["wr"] < 0.45), key=lambda r: (r["wr"], -r["g"]), default=None)
        nm = lambda r: core.name(r["cid"], ui.champs)
        if best:
            line = f"Tu mejor campeón es {nm(best)}: {round(best['wr'] * 100)} % en {best['g']} partidas."
            if worst and worst["cid"] != best["cid"]:
                line += f" Con {nm(worst)} pierdes más de lo que ganas ({round(worst['wr'] * 100)} % en {worst['g']})."
        else:
            line = "Aún hay pocas partidas por campeón (se necesitan 5 para sacar conclusiones)."
        ui.lbl(self.root, line, 11, "dim", anchor="w", justify="left", wraplength=min(self.ctx["width"] - 90, 760)).pack(anchor="w", pady=(3, 8))
        # cifras: un solo contenedor partido por líneas, sin fichas ni iconos
        box = ctk.CTkFrame(self.root, fg_color=PAL["card2"], corner_radius=12)
        box.pack(fill="x")
        inner = ui.frame(box)
        inner.pack(fill="x", padx=4, pady=10)
        figs = [("Campeones", str(len(rows)), "con partidas"), ("Partidas", str(tot), f"{wins}V {tot - wins}D"),
                ("Victorias", f"{round(wins / tot * 100)} %", "de todas ellas"),
                ("Más jugado", nm(max(rows, key=lambda r: r["g"])), f"{max(r['g'] for r in rows)} partidas")]
        if self.narrow:
            figs = figs[:3]
        for i, (lb, v, sub) in enumerate(figs):
            if i:
                tk.Frame(inner, width=1, bg=ui.hexm(PAL["border"])).pack(side="left", fill="y", pady=2)
            cell = ui.frame(inner)
            cell.pack(side="left", expand=True, fill="x", padx=12)
            ui.lbl(cell, lb, 10, "dim", anchor="w").pack(anchor="w")
            ui.lbl(cell, v, 17, "good" if lb == "Victorias" and wins / tot >= .5 else "bad" if lb == "Victorias" else "fg", True, True, anchor="w").pack(anchor="w")
            ui.lbl(cell, sub, 9, "dim", anchor="w").pack(anchor="w")

    def set_scope(self, v):
        self.scope, self.sel, self.shown = v, None, PAGE
        self.render()

    def set_sort(self, v):
        self.sort, self.shown = v, PAGE
        self.rerender_table()

    def rerender_table(self):
        """Cambiar el orden o pedir más filas solo repinta la tabla: el titular, las cifras y el detalle se quedan como están."""
        host = getattr(self, "table_host", None)
        if host is None or not host.winfo_exists():
            return self.render()
        rows = self.rows()
        if self.sel not in [r["cid"] for r in rows]:
            return self.render()
        self.data = rows
        self.cards = {}
        self.ui.clear(host)
        self.table(host, rows)

    # ---- tabla de campeones ----
    def table(self, parent, rows):
        ui, nar = self.ui, self.narrow
        ui.seg(parent, SORTS, self.sort, self.set_sort, height=26).pack(fill="x", pady=(0, 8))
        wrap = ui.frame(parent)
        wrap.pack(fill="x")
        head = ui.frame(wrap)
        head.pack(fill="x", padx=10, pady=(0, 2))
        cols = [("", 34), ("Campeón", 130 if nar else 150), ("Partidas", 56), ("Victorias", 64 if nar else 120)]
        if not nar:
            cols += [("KDA", 50), ("Maestría", 64)]
            if self.wide is False or True:
                cols += [("Forma", 60)]
        for t, w in cols:
            ui.lbl(head, t, 9, "dim", True, width=w, anchor="w" if t in ("", "Campeón", "Forma") else "e").pack(side="left", padx=(0, 8))
        for r in rows[:self.shown]:
            self.row(wrap, r, nar)
        left = len(rows) - self.shown
        if left > 0:
            b = ctk.CTkButton(parent, text=f"Mostrar {min(PAGE, left)} más  ({left} restantes)", height=32, corner_radius=10, font=ui.font(11),
                              fg_color=PAL["card2"], hover_color=PAL["card2"], text_color=PAL["fg"], command=self.more)
            b.pack(pady=(8, 0))
            ui.smooth_btn(b, PAL["card2"], PAL["border"])

    def more(self):
        self.shown += PAGE
        self.rerender_table()

    def row(self, parent, r, nar):
        """Fila de la tabla: un solo lienzo (antes ~15 widgets por fila)."""
        ui = self.ui
        sx = ui.scale_px()
        on = r["cid"] == self.sel
        wcol = 130 if nar else 150
        wwin = 64 if nar else 120
        W = 10 + 34 + 8 + wcol + 8 + 56 + 8 + wwin + 8 + (0 if nar else 50 + 8 + 64 + 8 + 60) + 10
        H = 46
        S = lambda v: int(v * sx)
        cv = tk.Canvas(parent, width=S(W), height=S(H), bg=ui.bg(parent), highlightthickness=0, bd=0, cursor="hand2")
        cv.pack(fill="x", pady=2, anchor="w")
        border = ui.rrect(cv, 1, 1, S(W) - 1, S(H) - 1, S(10), fill=ui.hexm(PAL["card2"]), outline=ui.hexm(ui.acc) if on else ui.hexm(PAL["card2"]), width=1)
        self.cards[r["cid"]] = (cv, border)
        fg, dim = ui.hexm(PAL["fg"]), ui.hexm(PAL["dim"])
        f12b, f12, f11, f9 = ui.tkf(12, True, False), ui.tkf(12, False, False), ui.tkf(11, False, False), ui.tkf(9, False, False)
        ph = ui.champ_photo(r["cid"], 30)
        cv.image = []
        if ph is not None:
            cv.create_image(S(10), S(8), image=ph, anchor="nw")
            cv.image.append(ph)
        x = 10 + 34 + 8
        cv.create_text(S(x), S(15), text=ui.fit(core.name(r["cid"], ui.champs), f12b, S(wcol)), font=f12b, fill=fg, anchor="w")
        roles = Counter(ROLES_ES.get(e["r"], "") for e in r["games"] if e["r"] and mode_of(e) not in NO_LANE_MODES)
        sub = roles.most_common(1)[0][0] if roles and roles.most_common(1)[0][0] else ""
        cv.create_text(S(x), S(32), text=sub or "—", font=f9, fill=dim, anchor="w")
        x += wcol + 8 + 56
        cv.create_text(S(x), S(23), text=str(r["g"]), font=f12, fill=fg, anchor="e")
        x += 8 + wwin
        col = ui.hexm(PAL["good" if r["wr"] >= .5 else "bad"])
        cv.create_text(S(x), S(17 if not nar else 23), text=f"{round(r['wr'] * 100)} %", font=f12b, fill=col, anchor="e")
        if not nar:
            bx0 = x - 120
            ui.rrect(cv, S(bx0), S(30), S(x), S(33), S(1), fill=ui.hexm(PAL["card"]), outline="")
            ui.rrect(cv, S(bx0), S(30), S(bx0 + max(3, 120 * r["wr"])), S(33), S(1), fill=col, outline="")
            x += 8 + 50
            cv.create_text(S(x), S(23), text=es(r["kda"], 2) if r["kda"] is not None else "—", font=f11, fill=fg if r["kda"] is not None else dim, anchor="e")
            x += 8 + 64
            cv.create_text(S(x), S(23), text=f"{r['mast'] // 1000} k" if r["mast"] >= 1000 else (str(r["mast"]) if r["mast"] else "—"), font=f11,
                           fill=fg if r["mast"] else dim, anchor="e")
            x += 8
            for q, w in enumerate(r["form"] or []):
                cv.create_rectangle(S(x + q * 10), S(19), S(x + q * 10 + 8), S(27), fill=ui.hexm(PAL["good" if w else "bad"]), outline="")
        cv.bind("<Button-1>", lambda e, c=r["cid"]: self.select(c))

    def select(self, cid):
        """Cambia de campeón sin repintar la tabla: solo el borde de la fila y el panel de detalle."""
        self.sel, self.dtab = cid, "Resumen"
        hi, lo = self.ui.hexm(self.ui.acc), self.ui.hexm(PAL["card2"])
        for c, (cv, border) in self.cards.items():
            try:
                cv.itemconfigure(border, outline=hi if c == cid else lo)
            except Exception:
                pass
        self.render_detail()

    def render_detail(self):
        if self.dparent is None or not self.dparent.winfo_exists():
            return self.render()
        self.ui.clear(self.dparent)
        self.detail(self.dparent, next(r for r in self.data if r["cid"] == self.sel))

    # ---- detalle ----
    def detail(self, parent, r):
        ui = self.ui
        cid = r["cid"]
        card = ctk.CTkFrame(parent, fg_color=PAL["card2"], corner_radius=14)
        card.pack(fill="x")
        inner = ui.frame(card)
        inner.pack(fill="x", padx=12, pady=12)
        try:
            pil = ui.hero_pil(cid, "Tu repertorio", round(r["wr"] * 100), self.dw - 24, "VICTORIAS")
            im = ctk.CTkImage(light_image=pil, dark_image=pil, size=(self.dw - 24, 150))
            lab = ctk.CTkLabel(inner, image=im, text="")
            lab.image = im
            lab.pack()
        except Exception:
            ui.lbl(inner, core.name(cid, ui.champs), 18, "fg", True, True, anchor="w").pack(anchor="w")
        ui.lbl(inner, f"{r['w']} victorias y {r['g'] - r['w']} derrotas · {round(r['wr'] * 100)} %" + (f" · maestría {r['mast'] // 1000} k" if r["mast"] >= 1000 else ""),
               10, "dim", anchor="w").pack(anchor="w", pady=(8, 8))
        ui.seg(inner, ["Resumen", "Partidas", "Build"], self.dtab, self.set_dtab, height=26).pack(fill="x", pady=(0, 10))
        body = ui.frame(inner)
        body.pack(fill="x")
        {"Resumen": self.d_summary, "Partidas": self.d_games, "Build": self.d_build}[self.dtab](body, r)

    def set_dtab(self, v):
        self.dtab = v
        self.render_detail()

    def section(self, p, text):
        self.ui.lbl(p, text, 9, "dim", True, anchor="w").pack(anchor="w", pady=(12, 4))

    def d_summary(self, p, r):
        ui = self.ui
        games = r["games"]
        if not games:
            ui.lbl(p, "No hay partidas de este campeón en tu archivo local (LOL-E guarda las que ve).", 10, "dim", anchor="w", justify="left",
                   wraplength=self.dw - 40).pack(anchor="w")
            return
        s = history.summary(games)
        durs = [e["d"] for e in games if e.get("d")]
        mins = sum(durs) / 60 if durs else 0
        dmg = sum(e["dm"] for e in games if e.get("dm") and e.get("d"))
        cs = sum(e["cs"] for e in games if e.get("cs") is not None and e.get("d"))
        figs = []
        if s["kda"] is not None:
            figs.append(("KDA", es(s["kda"], 2), f"{es(s['avg'][0])} / {es(s['avg'][1])} / {es(s['avg'][2])}"))
        if mins and dmg:
            figs.append(("Daño/min", str(int(dmg / mins)), ""))
        if mins and cs:
            figs.append(("CS/min", es(cs / mins), ""))
        if durs:
            m = sum(durs) / len(durs)
            figs.append(("Duración", f"{int(m // 60)}:{int(m % 60):02d}", ""))
        if figs:
            box = ctk.CTkFrame(p, fg_color=PAL["card"], corner_radius=10)
            box.pack(fill="x")
            row = ui.frame(box)
            row.pack(fill="x", padx=2, pady=8)
            for i, (lb, v, sub) in enumerate(figs):
                if i:
                    tk.Frame(row, width=1, bg=ui.hexm(PAL["border"])).pack(side="left", fill="y", pady=2)
                c = ui.frame(row)
                c.pack(side="left", expand=True, fill="x", padx=8)
                ui.lbl(c, lb, 9, "dim", anchor="w").pack(anchor="w")
                ui.lbl(c, v, 14, "fg", True, True, anchor="w").pack(anchor="w")
                if sub:
                    ui.lbl(c, sub, 8, "dim", anchor="w").pack(anchor="w")
        roles = {}
        for e in games:
            if e["r"] and mode_of(e) not in NO_LANE_MODES:
                x = roles.setdefault(e["r"], [0, 0])
                x[0] += 1
                x[1] += e["w"]
        if roles:
            self.section(p, "LÍNEAS")
            row = ui.frame(p)
            row.pack(anchor="w")
            for rl, (n_, w_) in sorted(roles.items(), key=lambda x: -x[1][0])[:3]:
                ui.chip(row, f"{ROLES_ES.get(rl, rl)} · {n_} · {round(w_ / n_ * 100)} %", "good" if w_ * 2 >= n_ else "bad").pack(side="left", padx=(0, 6))
        cnt = Counter(i for e in games if e.get("it") for i in e["it"] if i)
        if cnt and ui.items:
            self.section(p, "OBJETOS QUE MÁS LLEVAS")
            row = ui.frame(p)
            row.pack(anchor="w")
            for iid, n_ in cnt.most_common(6):
                cell = ui.frame(row)
                cell.pack(side="left", padx=(0, 8))
                img = ui.item_photo(iid, 28)
                lab = tk.Label(cell, image=img, bd=0, highlightthickness=0, bg=ui.bg(cell)) if img is not None else tk.Frame(
                    cell, width=int(28 * ui.scale_px()), height=int(28 * ui.scale_px()), bg=ui.hexm(PAL["card"]))
                if img is not None:
                    lab.image = img
                lab.pack()
                inf = ui.items.get(iid)
                if inf:
                    ui.tip(lab, f"{inf['n']}  ·  {inf['g']} de oro" + (f"\n{inf['d']}" if inf["d"] else ""))
                ui.lbl(cell, f"{n_}×", 8, "dim").pack()
        vs = ((self.ctx["info"] or {}).get("champ_vs") or {})
        vs = vs.get(r["cid"]) or vs.get(str(r["cid"])) or []
        best = sorted((v for v in vs if v[1] >= 2), key=lambda v: (-v[2] / v[1], -v[1]))[:3]
        worst = sorted((v for v in vs if v[1] >= 2 and v[2] < v[1]), key=lambda v: (v[2] / v[1], -v[1]))[:3]
        if best or worst:
            self.section(p, "CONTRA QUIÉN")
            for title, lst, color in (("Mejor", best, "good"), ("Peor", worst, "bad")):
                if not lst:
                    continue
                row = ui.frame(p)
                row.pack(anchor="w", pady=2)
                ui.lbl(row, title, 10, color, True, width=40, anchor="w").pack(side="left")
                for opp, gg, ww in lst:
                    cell = ui.frame(row)
                    cell.pack(side="left", padx=(0, 10))
                    ui.champ(cell, opp, 24, False).pack(side="left")
                    ui.lbl(cell, f" {ww} de {gg}", 10, color, True).pack(side="left")
        nm = core.name(r["cid"], ui.champs)
        acts = ui.frame(p)
        acts.pack(anchor="w", pady=(12, 0))
        small_btn(ui, acts, "Verlo como rival", lambda: ui.goto_matchup(r["cid"]), 120).pack(side="left", padx=(0, 6))
        small_btn(ui, acts, "Ver en Historial", lambda: ui.goto_history(nm), 120).pack(side="left")

    def d_games(self, p, r):
        ui = self.ui
        games = r["games"]
        if not games:
            ui.lbl(p, "No hay partidas de este campeón en tu archivo local.", 10, "dim", anchor="w").pack(anchor="w")
            return
        head = ui.frame(p)
        head.pack(fill="x")
        for t, w in (("Fecha", 62), ("Modo", 84), ("K / D / A", 84), ("Duración", 52)):
            ui.lbl(head, t, 9, "dim", True, width=w, anchor="w").pack(side="left")
        for e in games[:10]:
            row = ui.frame(p)
            row.pack(fill="x", pady=2)
            ui.lbl(row, fecha(e["t"], False)[:5], 10, "dim", width=62, anchor="w").pack(side="left")
            ui.lbl(row, mode_of(e), 10, "fg", width=84, anchor="w").pack(side="left")
            ui.lbl(row, f"{e['k']} / {e['de']} / {e['a']}" if e.get("k") is not None else "—", 10, "fg", True, width=84, anchor="w").pack(side="left")
            ui.lbl(row, f"{e['d'] // 60}:{e['d'] % 60:02d}" if e.get("d") else "—", 10, "dim", width=52, anchor="w").pack(side="left")
            ui.lbl(row, "Victoria" if e["w"] else "Derrota", 10, "good" if e["w"] else "bad", True).pack(side="left")
        nm = core.name(r["cid"], ui.champs)
        small_btn(ui, p, f"Ver las {len(games)} en el Historial", lambda: ui.goto_history(nm), 190).pack(anchor="w", pady=(10, 0))

    def best_lane(self, r):
        """Línea más jugada con él (solo modos con líneas); si no hay, la que más se juega según el meta o su posición habitual."""
        rl = Counter(e["r"] for e in r["games"] if e["r"] and mode_of(e) not in NO_LANE_MODES)
        if rl:
            return ROLE_LANE.get(rl.most_common(1)[0][0], "middle")
        try:
            sh = core.metamod.lane_shares(core.META["data"], r["cid"])
            if sh:
                return ROLE_LANE.get(max(sh, key=sh.get), "middle")
        except Exception:
            pass
        pos = self.ui.champs.get(r["cid"], {}).get("pos") or []
        return ROLE_LANE.get(pos[0], "middle") if pos else "middle"

    def d_build(self, p, r):
        ui = self.ui
        lane = self.lane_pick.get(r["cid"]) or self.best_lane(r)
        ui.lbl(p, "Línea de la build", 10, "dim", anchor="w").pack(anchor="w", pady=(0, 2))
        ui.seg(p, LANE_SEG, LANE_NAME[lane], lambda v, c=r["cid"]: self.set_lane(c, LANE_KEY[v]), height=26).pack(fill="x", pady=(0, 10))
        build_panel(ui, p, r["cid"], lane, None, self.dw - 40).pack(fill="x")

    def set_lane(self, cid, lane):
        self.lane_pick[cid] = lane
        self.render_detail()
