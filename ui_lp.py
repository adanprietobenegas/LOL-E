"""Gráfica «Tu rango en el tiempo»: eje de fechas, rango real con las divisiones marcadas, filtros por tramo y por cola, y un cuadro con el
campeón, el resultado y los PL de la partida al pasar el ratón por un punto. Con historiales largos no se dibuja un icono por partida (no
cabrían): solo el del punto que miras. Los datos y las cuentas están en lpseries.py."""
import datetime
import time
import tkinter as tk

import lol_advisor as core
import lpseries
from ui_kit import PAL

_STATE = {"queue": "solo", "range": "30", "est": True}   # lo elegido se recuerda mientras la app está abierta
H = 176
LEFT, RIGHT, TOP, BOTTOM = 84, 16, 14, 24
MAX_DOTS = 90


def fecha(ms, hora=False):
    d = datetime.datetime.fromtimestamp(ms / 1000)
    return d.strftime("%d/%m/%Y %H:%M" if hora else "%d/%m/%Y")


class LpChart:
    def __init__(self, ui, parent, width, hist, lp, snaps, now=None, marks=()):
        """`marks`: [(valor de la escala, nombre)] de referencias oficiales del cliente (el pico de la temporada, cómo acabó la anterior)."""
        self.ui, self.width, self.now, self.marks = ui, width, now or int(time.time() * 1000), list(marks)
        self.hist, self.lp, self.snaps = hist, lp, snaps
        self.imgs = []
        self.pts = []
        self.box = ui.frame(parent)
        self.box.pack(fill="x")
        self.series = {q: lpseries.series(lp, hist, snaps, q, with_estimate=True) for q in ("solo", "flex")}
        if len(self.real("solo")) < 3 and len(self.real("flex")) >= 3:
            _STATE["queue"] = "flex"
        self.build()

    # ---- estructura ----
    def build(self):
        ui = self.ui
        ui.clear(self.box)
        head = ui.frame(self.box)
        head.pack(fill="x")
        ui.lbl(head, "TU RANGO EN EL TIEMPO", 9, "dim", True).pack(side="left")
        if len(self.series["flex"]) >= 3 and len(self.series["solo"]) >= 3:
            ui.seg(head, ["Solo/Dúo", "Flexible"], "Solo/Dúo" if _STATE["queue"] == "solo" else "Flexible", self.set_queue, height=24).pack(side="right")
        if any(p["src"] == "est" for p in self.series[_STATE["queue"]]):
            ui.seg(head, ["Con estimación", "Solo reales"], "Con estimación" if _STATE["est"] else "Solo reales", self.set_est, height=24).pack(side="right", padx=(0, 8))
        names = [n for n, _ in lpseries.RANGES]
        cur = next((n for n, k in lpseries.RANGES if k == _STATE["range"]), names[1])
        ui.seg(self.box, names, cur, self.set_range, height=24).pack(fill="x", pady=(8, 8))
        self.line = ui.lbl(self.box, "", 11, "fg", anchor="w", justify="left", wraplength=max(240, self.width - 40))
        self.line.pack(anchor="w", pady=(0, 4))
        sx = ui.scale_px()
        self.W = max(280, min(self.width - 40, 960))
        self.sx = sx
        self.cv = tk.Canvas(self.box, width=int(self.W * sx), height=int(H * sx), bg=ui.bg(self.box), highlightthickness=0, bd=0)
        self.cv.pack(anchor="w")
        self.cv.bind("<Motion>", self.hover)
        self.cv.bind("<Leave>", lambda e: self.cv.delete("hov"))
        self.note = ui.lbl(self.box, "", 9, "dim", anchor="w", justify="left", wraplength=max(240, self.width - 40))
        self.note.pack(anchor="w", pady=(4, 0))
        self.draw()

    def real(self, queue):
        """Puntos de una cola sin los estimados."""
        return [p for p in self.series[queue] if p["src"] != "est"]

    def set_est(self, v):
        _STATE["est"] = v == "Con estimación"
        self.build()

    def set_queue(self, v):
        _STATE["queue"] = "flex" if v == "Flexible" else "solo"
        self.build()

    def set_range(self, name):
        _STATE["range"] = next(k for n, k in lpseries.RANGES if n == name)
        self.build()

    # ---- dibujo ----
    def draw(self):
        ui, cv, S = self.ui, self.cv, (lambda v: int(v * self.sx))
        cv.delete("all")
        allp = self.series[_STATE["queue"]] if _STATE["est"] else self.real(_STATE["queue"])
        self.pts = lpseries.select(allp, _STATE["range"], self.now)
        pts = self.pts
        good, bad, dim, fg = ui.hexm(PAL["good"]), ui.hexm(PAL["bad"]), ui.hexm(PAL["dim"]), ui.hexm(PAL["fg"])
        edge = ui.hexm(PAL["edge"])
        if len(pts) < 2:
            msg = "No hay puntos en este tramo: prueba con uno más largo." if allp else "Todavía no hay rango guardado."
            cv.create_text(S(self.W / 2), S(H / 2), text=msg, fill=dim, font=ui.tkf(11, False, False))
            self.line.configure(text="")
            self.note.configure(text="")
            return
        d, n, w, l = lpseries.summary(pts)
        last = pts[-1]
        txt = f"Ahora: {last['tier']} · {last['lp']} PL"
        if n:
            approx = "≈" if any(p["src"] == "est" for p in pts) else ""
            txt = f"{approx}{d:+d} PL en {n} partida{'s' if n != 1 else ''} ({w}V {l}D)   ·   ".replace("-", "−") + txt
        self.line.configure(text=txt)
        vs = [p["v"] for p in pts]
        vmin, vmax = min(vs), max(vs)
        pad = max(40, (vmax - vmin) * 0.12)
        vmin, vmax = vmin - pad, vmax + pad
        t0, t1 = pts[0]["t"], pts[-1]["t"]
        # el eje es el TRAMO elegido (7, 30, 90 días, este año), aunque el historial guardado sea más corto: así se nota el cambio de tramo
        if _STATE["range"] in ("7", "30", "90"):
            t0, t1 = self.now - int(_STATE["range"]) * lpseries.DAY_MS, self.now
        elif _STATE["range"] == "year":
            t0, t1 = int(datetime.datetime(datetime.datetime.fromtimestamp(self.now / 1000).year, 1, 1).timestamp() * 1000), self.now
        if t1 <= t0:
            t1 = t0 + 1
        px = lambda t: S(LEFT + (self.W - LEFT - RIGHT) * (t - t0) / (t1 - t0))
        py = lambda v: S(TOP + (H - TOP - BOTTOM) * (1 - (v - vmin) / (vmax - vmin)))
        self.px, self.py = px, py
        # divisiones: como mucho 6 etiquetas; las líneas son tenues
        bl = lpseries.bands(vmin, vmax)
        step = max(1, -(-len(bl) // 6))
        for i, (v, name) in enumerate(bl):
            y = py(v)
            cv.create_line(S(LEFT), y, S(self.W - RIGHT), y, fill=edge, dash=(2, 4))
            if i % step == 0:
                cv.create_text(S(LEFT - 8), y, text=name, anchor="e", fill=dim, font=ui.tkf(9, False, False))
        # referencias del cliente: solo si caen dentro de lo que se ve (no se estira la gráfica para llegar a ellas)
        acc = ui.hexm(ui.acc)
        for v, name in self.marks:
            if vmin <= v <= vmax:
                y = py(v)
                cv.create_line(S(LEFT), y, S(self.W - RIGHT), y, fill=acc, dash=(6, 3))
                cv.create_text(S(self.W - RIGHT), y - S(8), text=name, anchor="e", fill=acc, font=ui.tkf(9, False, False))
        # fechas
        for k in range(5):
            t = t0 + (t1 - t0) * k / 4
            x = px(t)
            cv.create_text(min(max(x, S(LEFT)), S(self.W - RIGHT)), S(H - 10), text=datetime.datetime.fromtimestamp(t / 1000).strftime("%d/%m" if t1 - t0 < 330 * 86_400_000 else "%m/%y"),
                           anchor="center", fill=dim, font=ui.tkf(9, False, False))
        # línea: verde si el tramo sube, roja si baja, tenue entre fotos del día
        for a, b in zip(pts, pts[1:]):
            if b["src"] in ("game", "est") and b["d"]:
                col = good if b["d"] > 0 else bad
            else:
                col = good if b["v"] > a["v"] else bad if b["v"] < a["v"] else dim
            if "est" in (a["src"], b["src"]):   # lo estimado va a trazos y más fino: se nota que no es un dato guardado
                cv.create_line(px(a["t"]), py(a["v"]), px(b["t"]), py(b["v"]), fill=col, width=S(1), dash=(3, 3))
            else:
                cv.create_line(px(a["t"]), py(a["v"]), px(b["t"]), py(b["v"]), fill=col, width=S(2), capstyle="round")
        if len(pts) <= MAX_DOTS:
            for p in pts:
                r = S(3)
                x, y = px(p["t"]), py(p["v"])
                if p["src"] == "game":
                    cv.create_oval(x - r, y - r, x + r, y + r, fill=good if p["w"] else bad, outline="")
                elif p["src"] == "est":
                    cv.create_oval(x - r, y - r, x + r, y + r, outline=good if p["w"] else bad, fill=ui.bg(self.box))
                else:
                    cv.create_oval(x - r, y - r, x + r, y + r, outline=dim, fill=ui.bg(self.box))
        x, y = px(last["t"]), py(last["v"])
        cv.create_oval(x - S(4), y - S(4), x + S(4), y + S(4), fill=fg, outline="")
        has_day = any(p["src"] == "day" for p in pts)
        has_est = any(p["src"] == "est" for p in pts)
        real = [p for p in allp if p["src"] != "est"]
        first = real[0]["t"] if real else allp[0]["t"]
        txt = "Los puntos rellenos son partidas que LOL-E vio con la app abierta; " + ("los huecos son fotos diarias de tu rango que da op.gg; " if has_day else "") +               ("los puntos huecos y a trazos son ESTIMADOS: salen de tus victorias y derrotas con los PL típicos, así que pueden desviarse unos PL por partida. " if has_est else "") +               "Pasa el ratón por un punto para ver la partida."
        if t0 < first - lpseries.DAY_MS:   # el tramo empieza antes de lo que hay guardado: se dice, en vez de dejar un hueco sin explicar
            txt += f"  Tu rango guardado de verdad empieza el {fecha(first)}; antes de esa fecha LOL-E no tenía tus PL" + (" y lo que ves es estimado." if has_est else ".")
        self.note.configure(text=txt)

    # ---- al pasar el ratón ----
    def hover(self, e):
        cv, ui, S = self.cv, self.ui, (lambda v: int(v * self.sx))
        cv.delete("hov")
        if len(self.pts) < 2:
            return
        x = e.x
        i = min(range(len(self.pts)), key=lambda k: abs(self.px(self.pts[k]["t"]) - x))
        p = self.pts[i]
        cx, cy = self.px(p["t"]), self.py(p["v"])
        if abs(cx - x) > S(40):
            return
        fg, dim = ui.hexm(PAL["fg"]), ui.hexm(PAL["dim"])
        cv.create_line(cx, S(TOP), cx, S(H - BOTTOM), fill=dim, dash=(2, 3), tags="hov")
        cv.create_oval(cx - S(5), cy - S(5), cx + S(5), cy + S(5), outline=fg, width=S(2), tags="hov")
        lines = [(fecha(p["t"], p["src"] != "day"), dim, 9, False), (f"{p['tier']} · {p['lp']} PL", fg, 10, True)]
        icon = None
        if p["src"] == "game":
            d = p["d"]
            lines.append((("Victoria" if p["w"] else "Derrota") + f" · {d:+d} PL".replace("-", "−"), ui.hexm(PAL["good"] if p["w"] else PAL["bad"]), 10, True))
            name = core.name(p["cid"], ui.champs) if p.get("cid") in ui.champs else ""
            if name:
                lines.insert(1, (name, fg, 10, True))
            icon = ui.champ_photo(p["cid"], 34, None) if p.get("cid") in ui.champs else None
        elif p["src"] == "est":
            d = p["d"]
            lines.append((("Victoria" if p["w"] else "Derrota") + f" · ≈{d:+d} PL (estimado)".replace("-", "−"), ui.hexm(PAL["good"] if p["w"] else PAL["bad"]), 10, True))
            name = core.name(p["cid"], ui.champs) if p.get("cid") in ui.champs else ""
            if name:
                lines.insert(1, (name, fg, 10, True))
            icon = ui.champ_photo(p["cid"], 34, None) if p.get("cid") in ui.champs else None
        else:
            lines.append(("Foto del día (op.gg)", dim, 9, False))
        pad, iw = S(8), (S(34) + S(8) if icon is not None else 0)
        tw = max(ui.tkf(sz, b, False).measure(t) for t, _c, sz, b in lines)
        bw, bh = pad * 2 + iw + tw, pad * 2 + sum(ui.tkf(sz, b, False).metrics("linespace") + S(2) for _t, _c, sz, b in lines)
        bx = cx + S(12) if cx + S(12) + bw < S(self.W) else cx - S(12) - bw
        by = min(max(cy - bh // 2, S(2)), S(H) - bh - S(2))
        cv.create_rectangle(bx, by, bx + bw, by + bh, fill=ui.hexm(PAL["card"]), outline=ui.hexm(PAL["edge"]), tags="hov")
        if icon is not None:
            self.imgs = [icon]
            cv.create_image(bx + pad, by + pad, image=icon, anchor="nw", tags="hov")
        y = by + pad
        for t, c, sz, b in lines:
            f = ui.tkf(sz, b, False)
            cv.create_text(bx + pad + iw, y, text=t, anchor="nw", fill=c, font=f, tags="hov")
            y += f.metrics("linespace") + S(2)
