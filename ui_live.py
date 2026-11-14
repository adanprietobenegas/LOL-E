"""«En vivo» de la pestaña Partida: una tira compacta arriba (reloj, balance de bajas y oro, objetivos, lo que te conviene comprar) y, plegable
debajo de tu build, los diez jugadores emparejados por línea (datos de live.summarize).

La vista se construye UNA vez y después solo se actualizan textos, barras e iconos que han cambiado (`LiveView.update`): repintarla entera cada
pocos segundos parpadeaba y hacía perder el sitio. Los datos salen de la API local del juego (los de la tabla de puntuación).
"""
import tkinter as tk

import builds
import live
import lol_advisor as core
import shopping
import ui_vs
from ui_build import _item
from ui_kit import PAL

NEUTRAL = "#8fa0b4"
LANES = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support"}
OBJECTIVES = (("towers", "Torres"), ("inhibs", "Inhib."), ("dragons", "Dragones"), ("heralds", "Heraldo"), ("grubs", "Larvas"), ("barons", "Barón"))


def _rows(snap):
    """(tuyos, rivales, ¿se sabe cuál es tu equipo?, clave de tu equipo, clave del rival)."""
    me = snap.get("me_team") or ""
    mine_t = me or "ORDER"
    other_t = "CHAOS" if mine_t == "ORDER" else "ORDER"
    return ([p for p in snap["players"] if p["team"] == mine_t], [p for p in snap["players"] if p["team"] == other_t], bool(me), mine_t, other_t)


# ---------- lo que te conviene comprar ----------
def _my_build(ui, snap, plan):
    """(tú en el resumen, build de la web de tu campeón en tu línea) o None si no se puede saber: sin plan de la Grieta, sin catálogo de objetos,
    sin saber quién eres o build aún sin cargar. Lo comparten la siguiente compra y el objeto contra los rivales."""
    if not plan or not plan.get("cid") or plan.get("kind") not in (None, "sr") or plan["cid"] not in ui.champs or not ui.items:
        return None
    lane = LANES.get(plan.get("role") or "")
    yo = next((p for p in snap["players"] if p["me"]), None)
    if not lane or not yo:
        return None
    opp = plan.get("opp") or 0
    st = builds.peek(builds.request(core.CACHE, ui.champs[plan["cid"]], lane, ui.champs[opp] if opp in ui.champs else None))
    return (yo, st[1]) if st[0] == "ok" else None


_memo = {"snap": None, "opp": None, "val": None}   # la misma lectura se consulta dos veces (aviso sonoro y pantalla): se calcula una


def buy_hint(ui, snap, plan):
    if _memo["snap"] is snap and _memo["opp"] == (plan or {}).get("opp") and _memo["val"]:
        return _memo["val"]
    val = _buy_hint(ui, snap, plan)
    if val:   # un None (build aún sin cargar) no se recuerda: se reintenta en la siguiente consulta
        _memo.update(snap=snap, opp=(plan or {}).get("opp"), val=val)
    return val


def _buy_hint(ui, snap, plan):
    """(frase, id del objeto, ¿puedes pagarlo ya?) con tu siguiente compra según tu build de la web y lo que llevas, o None si no se puede saber
    (sin plan de la Grieta, build aún sin cargar, catálogo sin recetas, nada que proponer)."""
    try:
        mine = _my_build(ui, snap, plan)
        if not mine:
            return None
        yo, st = mine
        order = shopping.build_order(st.get("items") or {}, lambda i: "Boots" in (ui.items.get(i) or {}).get("t", []))
        res = shopping.next_purchase(order, yo["items"], int(snap.get("gold") or 0), ui.items)
        return (shopping.describe(res, ui.items), res["id"], res["affordable"]) if res else None
    except Exception:
        core.log_exc("Siguiente compra")
        return None


def counter_hint(ui, snap, plan, other):
    """(frase, id) con UN objeto contra lo que llevan los rivales (de los que más se compran con tu campeón), o None. Ver shopping.counter_item."""
    try:
        mine = _my_build(ui, snap, plan)
        if not mine:
            return None
        yo, st = mine
        res = shopping.counter_item(live.itemization(other, ui.items), shopping.candidate_pool(ui.items, st), ui.items, yo["items"])
        return (f"{res['why']} Opción de tu build: {ui.items[res['id']]['n']}.", res["id"]) if res else None
    except Exception:
        core.log_exc("Objeto contra los rivales")
        return None


# ---------- piezas que se actualizan en sitio ----------
class BarRow:
    """Un reparto visual entre tu equipo y el rival: tus cifras a la izquierda, las suyas a la derecha y una barra partida en proporción."""
    H = 30

    def __init__(self, ui, parent, title, width):
        self.ui, self.W, self.sx = ui, width, ui.scale_px()
        self.title = title
        self.cv = tk.Canvas(parent, width=int(width * self.sx), height=int(self.H * self.sx), bg=ui.bg(parent), highlightthickness=0, bd=0)
        S = lambda v: int(v * self.sx)
        dim = ui.hexm(PAL["dim"])
        self.left_bar = self.cv.create_rectangle(0, S(20), 0, S(27), fill=NEUTRAL, outline="")
        self.right_bar = self.cv.create_rectangle(0, S(20), S(width), S(27), fill=NEUTRAL, outline="")
        self.t_left = self.cv.create_text(0, S(8), text="", anchor="w", fill=ui.hexm(PAL["fg"]), font=ui.tkf(12, True, False))
        self.t_right = self.cv.create_text(S(width), S(8), text="", anchor="e", fill=ui.hexm(PAL["fg"]), font=ui.tkf(12, True, False))
        self.cv.create_text(S(width / 2), S(8), text=title, anchor="center", fill=dim, font=ui.tkf(10, False, False))
        self.last = None

    def update(self, a, b, fmt, ca, cb):
        key = (a, b, fmt(a), fmt(b), ca, cb)
        if key == self.last:
            return
        self.last = key
        S = lambda v: int(v * self.sx)
        total = a + b
        frac = a / total if total else 0.5
        if total:
            frac = min(0.96, max(0.04, frac))
        x = S(self.W * frac)
        mine_on, other_on = a >= b, b >= a
        self.cv.coords(self.left_bar, 0, S(20), x, S(27))
        self.cv.coords(self.right_bar, x, S(20), S(self.W), S(27))
        self.cv.itemconfigure(self.left_bar, fill=ca)
        self.cv.itemconfigure(self.right_bar, fill=cb)
        fg, dim = self.ui.hexm(PAL["fg"]), self.ui.hexm(PAL["dim"])
        self.cv.itemconfigure(self.t_left, text=fmt(a), fill=fg if mine_on else dim)
        self.cv.itemconfigure(self.t_right, text=fmt(b), fill=fg if other_on else dim)


class Hint:
    """Una fila «icono + frase» que se muestra solo cuando hay algo que decir y cambia de icono solo si cambia el objeto."""

    def __init__(self, ui, parent, wrap):
        self.ui, self.wrap = ui, wrap
        self.row = ui.frame(parent)
        self.icon_host = ui.frame(self.row)
        self.icon_host.pack(side="left")
        self.text = ui.lbl(self.row, "", 11, "fg", True, anchor="w", justify="left", wraplength=wrap)
        self.text.pack(side="left", padx=6)
        self.iid, self.shown, self.last = None, False, None

    def set(self, value, bold=True):
        """value: (frase, id de objeto) o None."""
        if value == self.last:
            return
        self.last = value
        if not value:
            if self.shown:
                self.row.pack_forget()
                self.shown = False
            return
        if value[1] != self.iid:
            for w in self.icon_host.winfo_children():
                w.destroy()
            _item(self.ui, self.icon_host, value[1], 26)
            self.iid = value[1]
        self.text.configure(text=value[0])
        if not self.shown:
            self.row.pack(fill="x", pady=(6, 0))
            self.shown = True


class PlayerCell:
    """Un jugador: icono, KDA, farmeo, oro en objetos (con una barra) y sus objetos. `side`: «L» el icono a la izquierda, «R» a la derecha."""

    def __init__(self, ui, parent, side, width, max_ref):
        self.ui, self.side, self.max_ref = ui, side, max_ref
        self.frame = ui.frame(parent)
        left = side == "L"
        self.icon_host = ui.frame(self.frame)
        self.icon_host.pack(side="left" if left else "right", padx=(0, 8) if left else (8, 0))
        self.body = ui.frame(self.frame)
        self.body.pack(side="left" if left else "right", fill="x", expand=True)
        al = "w" if left else "e"
        self.name = ui.lbl(self.body, "", 11, "fg", True, anchor=al)
        self.name.pack(anchor=al, fill="x")
        self.stats = ui.lbl(self.body, "", 10, "dim", anchor=al)
        self.stats.pack(anchor=al, fill="x")
        self.items_host = ui.frame(self.body)
        self.items_host.pack(anchor=al, pady=(2, 0))
        sx = ui.scale_px()
        self.bar_w = int(max(60, width) * sx)
        self.bar = tk.Canvas(self.body, width=self.bar_w, height=int(4 * sx), bg=ui.bg(self.body), highlightthickness=0, bd=0)
        self.bar.pack(anchor=al, pady=(3, 0))
        self.bar_rect = self.bar.create_rectangle(0, 0, 0, int(4 * sx), fill=NEUTRAL, outline="")
        self.cid, self.items, self.sig = None, None, None

    def update(self, p, color, me, rival):
        ui = self.ui
        sig = (p["cid"], p["level"], p["k"], p["d"], p["a"], p["cs"], p["dead"], int(p["respawn"]), tuple(p["items"]), p["value"], color, me, rival)
        if sig == self.sig:
            return
        self.sig = sig
        if p["cid"] != self.cid:
            for w in self.icon_host.winfo_children():
                w.destroy()
            if p["cid"] in ui.champs:
                ui.champ(self.icon_host, p["cid"], 34, False, NEUTRAL if p["dead"] else color).pack()
            else:
                ui.lbl(self.icon_host, "?", 12, "dim").pack()
            self.cid = p["cid"]
        name = ui.champs.get(p["cid"], {}).get("name") or p["name"]
        tag = "  (tú)" if me else "  · tu rival" if rival else ""
        self.name.configure(text=name + tag, fg=ui.hexm(PAL["dim"] if p["dead"] else PAL["fg"]))
        resp = f"   ↻ {int(p['respawn'])} s" if p["dead"] else ""
        self.stats.configure(text=f"Nv {p['level']} · {p['k']}/{p['d']}/{p['a']} · {p['cs']} cs{resp}",
                             fg=ui.hexm(PAL["warn"] if p["dead"] else PAL["dim"]))
        if tuple(p["items"]) != self.items:
            for w in self.items_host.winfo_children():
                w.destroy()
            for iid in p["items"][:7]:
                _item(ui, self.items_host, iid, 20)
            self.items = tuple(p["items"])
        ref = max(1, self.max_ref())
        self.bar.coords(self.bar_rect, 0, 0, int(self.bar_w * min(1.0, p["value"] / ref)), int(4 * ui.scale_px()))
        self.bar.itemconfigure(self.bar_rect, fill=color)


class LiveView:
    """Lo que ve el jugador durante la partida. `strip` es la tira compacta (va arriba); los diez jugadores van en un pliegue (`detail`).
    Se llama a `update(snap, opp_cid, plan)` con cada lectura nueva; solo cambia lo que ha cambiado."""

    def __init__(self, ui, strip, detail, width):
        self.ui, self.width = ui, width
        self.snap, self.opp, self.plan = None, 0, None
        self.cells = {}
        self.board_built = False
        W = max(240, min(width - 100, 980))
        card = tk.Frame(strip, bg=ui.hexm(PAL["card2"]))
        card.pack(fill="x")
        box = tk.Frame(card, bg=ui.hexm(PAL["card2"]))
        box.pack(fill="x", padx=12, pady=10)
        head = ui.frame(box)
        head.pack(fill="x")
        self.clock = ui.lbl(head, "EN VIVO", 10, "fg", True)
        self.clock.pack(side="left")
        self.gold = ui.lbl(head, "", 10, "dim")
        self.gold.pack(side="right")
        self.bar_kills = BarRow(ui, box, "Bajas", W)
        self.bar_kills.cv.pack(anchor="w", pady=(6, 0))
        self.bar_gold = BarRow(ui, box, "Oro en objetos", W)
        self.bar_gold.cv.pack(anchor="w", pady=(2, 0))
        objs = ui.frame(box)
        objs.pack(fill="x", pady=(6, 0))
        self.obj = {}
        for key, title in OBJECTIVES:
            cell = ui.frame(objs)
            cell.pack(side="left", expand=True, fill="x")
            ui.lbl(cell, title, 9, "dim").pack()
            self.obj[key] = ui.lbl(cell, "0 · 0", 12, "dim", True)
            self.obj[key].pack()
        wrap = max(220, width - 150)
        slots = [ui.frame(box) for _ in range(5)]   # huecos fijos y en orden: lo que aparece o desaparece no cambia el lugar de lo demás
        for s in slots:
            s.pack(fill="x")
        self.buy = Hint(ui, slots[0], wrap)
        self.counter = Hint(ui, slots[1], wrap)
        self.duel = ui.lbl(slots[2], "", 11, "fg", anchor="w", justify="left", wraplength=max(240, width - 110))
        self.reading = ui.lbl(slots[3], "", 10, "dim", anchor="w", justify="left", wraplength=max(240, width - 110))
        self.alert = ui.lbl(slots[4], "", 11, "warn", True, anchor="w", justify="left", wraplength=max(240, width - 110))
        self.duel_on = self.reading_on = self.alert_on = False
        self.prev_snap, self.alerts = None, []   # [(hora de partida, frase)] de picos del rival, que se quedan unos segundos
        self.summary = ""
        self.fold = ui_vs.collapsible(ui, detail, "Los 10 jugadores en directo", "nivel, objetos y oro de cada uno", "live_board", self._fill_board, open_=False)

    # ---- tablero de los diez ----
    def _fill_board(self, c):
        ui = self.ui
        self.board_built = True
        self.cells = {}
        pair = self.width >= 900
        mine_n = len(_rows(self.snap)[0]) if self.snap else 5
        other_n = len(_rows(self.snap)[1]) if self.snap else 5
        maxref = lambda: max([p["value"] for p in (self.snap or {"players": []})["players"]] + [1])
        cw = max(180, (self.width - 150) // 2 - 20) if pair else max(240, self.width - 150)
        self.board = ui.frame(c)
        self.board.pack(fill="x")
        if pair:
            for i in range(max(mine_n, other_n)):
                row = ui.frame(self.board)
                row.pack(fill="x", pady=3)
                row.grid_columnconfigure(0, weight=1, uniform="lv")
                row.grid_columnconfigure(1, weight=1, uniform="lv")
                for col, (key, side) in enumerate((("mine", "L"), ("other", "R"))):
                    cell = PlayerCell(ui, row, side, cw, maxref)
                    cell.frame.grid(row=0, column=col, sticky="ew", padx=6)
                    self.cells[(key, i)] = cell
        else:
            for key, n, title in (("other", other_n, "RIVALES"), ("mine", mine_n, "TU EQUIPO")):
                ui.lbl(self.board, title, 9, "dim", True, anchor="w").pack(anchor="w", pady=(6, 2))
                for i in range(n):
                    cell = PlayerCell(ui, self.board, "L", cw, maxref)
                    cell.frame.pack(fill="x", pady=3)
                    self.cells[(key, i)] = cell
        if self.snap:
            self._update_board(self.snap)

    def _update_board(self, snap):
        mine, other, known, kmine, kother = _rows(snap)
        c_mine = self.ui.hexm(PAL["good"]) if known else NEUTRAL
        c_other = self.ui.hexm(PAL["bad"]) if known else NEUTRAL
        opp = self.opp
        for key, lst, color in (("mine", mine, c_mine), ("other", other, c_other)):
            for i, p in enumerate(lst):
                cell = self.cells.get((key, i))
                if cell is not None:
                    cell.update(p, color, p["me"], bool(opp) and key == "other" and p["cid"] == opp)

    # ---- actualización ----
    def update(self, snap, opp_cid=0, plan=None):
        ui = self.ui
        self.snap, self.opp, self.plan = snap, opp_cid, plan
        mine, other, known, kmine, kother = _rows(snap)
        c_mine = ui.hexm(PAL["good"]) if known else NEUTRAL
        c_other = ui.hexm(PAL["bad"]) if known else NEUTRAL
        self.clock.configure(text=f"EN VIVO  ·  {live.clock(snap['t'])}")
        self.gold.configure(text=f"Tu oro: {snap['gold']}" if snap.get("gold") else "")
        teams = snap["teams"]
        a, b = teams.get(kmine, {}), teams.get(kother, {})
        self.bar_kills.update(a.get("kills", 0), b.get("kills", 0), str, c_mine, c_other)
        self.bar_gold.update(a.get("value", 0), b.get("value", 0), live.money, c_mine, c_other)
        good, bad, dim = ui.hexm(PAL["good"]), ui.hexm(PAL["bad"]), ui.hexm(PAL["dim"])
        for key, _title in OBJECTIVES:
            va, vb = a.get(key, 0), b.get(key, 0)
            self.obj[key].configure(text=f"{va} · {vb}", fg=(good if known else ui.hexm(PAL["fg"])) if va > vb else (bad if known else ui.hexm(PAL["fg"])) if vb > va else dim)
        buy = buy_hint(ui, snap, plan)
        self.buy.set((buy[0], buy[1]) if buy else None)
        self.counter.set(counter_hint(ui, snap, plan, other))
        pareja = live.duel(snap, opp_cid)
        if self.prev_snap is not snap:   # una lectura nueva: ¿ha pasado algo con tu rival?
            for txt in live.spikes(self.prev_snap, snap, opp_cid):
                self.alerts.append((snap["t"], txt))
            self.prev_snap = snap
        self.alerts = [(t, x) for t, x in self.alerts if 0 <= snap["t"] - t <= live.SPIKE_SHOW]
        self._text(self.alert, "alert_on", " ".join(x for _t, x in self.alerts), 6)
        self._text(self.duel, "duel_on", live.duel_line(*pareja, ui.champs.get(opp_cid, {}).get("name", "")) if pareja else "", 6)
        frases = live.reading(live.itemization(other, ui.items or {}))
        if self.counter.last:   # la sugerencia ya dice qué acumulan o qué daño hacen: no se repite
            frases = [f for f in frases if not f.startswith("Acumulan")]
        self._text(self.reading, "reading_on", " ".join(frases) + "  (orientativo)" if frases else "", 6)
        if self.board_built:
            self._update_board(snap)

    def _text(self, lab, flag, text, pady):
        """Etiqueta que se muestra solo si tiene texto; no se vuelve a empaquetar si ya estaba puesta."""
        on = bool(text)
        if text and lab.cget("text") != text:
            lab.configure(text=text)
        if on and not getattr(self, flag):
            lab.pack(anchor="w", pady=(pady, 0))
        elif not on and getattr(self, flag):
            lab.pack_forget()
        setattr(self, flag, on)

    def alive(self):
        try:
            return bool(self.clock.winfo_exists())
        except Exception:
            return False
