"""Tablero «5 contra 5» de la pantalla de carga: los diez jugadores a la vez, cada línea frente a su rival, con etiquetas de lo más llamativo
(maestría, racha, fuera de rol…), la comparativa de los dos equipos y, al pasar el ratón por una tarjeta, el resumen de sus últimas 10 partidas.

Todo sale del cliente de LoL (players.fetch_player): rango, partidas recientes y maestrías de cada jugador. Un clic abre el perfil completo.
"""
import tkinter as tk

import customtkinter as ctk

import lol_advisor as core
from ui_kit import PAL, ROLES_ES, TIER_COLORS, ctl
from ui_player import ago, num, rank_line, signals
from ui_player import build as profile_build

TIERS = list(("IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"))
DIVS = ["IV", "III", "II", "I"]
TIERS_ES = {"IRON": "Hierro", "BRONZE": "Bronce", "SILVER": "Plata", "GOLD": "Oro", "PLATINUM": "Platino", "EMERALD": "Esmeralda",
            "DIAMOND": "Diamante", "MASTER": "Maestro", "GRANDMASTER": "Gran Maestro", "CHALLENGER": "Aspirante"}
QUEUES = {420: "Solo/Dúo", 440: "Flexible", 710: "Clasif. de 5", 400: "Normal", 430: "Normal", 480: "Normal", 490: "Normal", 700: "Clash"}
LANE_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT"]
MIN_WIDTH = 640     # por debajo no caben dos columnas: se usa la lista de siempre


def best_rank(p):
    return (p.get("solo") or p.get("flex") or p.get("prem")) if p else None


def rank_score(rk):
    """Rango como número para poder promediar: 4 puntos por liga y 0-3 por división (las ligas altas no tienen división)."""
    if not rk or rk.get("key") not in TIERS:
        return None
    t = TIERS.index(rk["key"])
    return t * 4 + (DIVS.index(rk["div"]) if rk.get("div") in DIVS else 0)


def score_rank(s):
    """Número medio -> (texto, color)."""
    t = min(len(TIERS) - 1, int(s // 4))
    key = TIERS[t]
    div = "" if t >= TIERS.index("MASTER") else " " + DIVS[min(3, int(round(s - t * 4)))]
    return TIERS_ES[key] + div, TIER_COLORS.get(key, "fg")


def badges(p, x, party, mates):
    """[(texto, color)] con lo más destacado de un jugador, por orden de importancia."""
    out = []
    if x["puuid"] in party:
        out.append(("Dúo contigo", "info"))
    if mates and mates[0]:
        g, w = mates
        out.append((f"Juntos {g}p · {w}V", "good" if w * 2 >= g else "bad"))
    if not p or p.get("error"):
        return out
    st = p.get("stats") or {}
    pts = (p.get("mastery") or {}).get(x["cid"], 0)
    if x["cid"]:
        if pts >= 200000:
            out.append((f"Maestría {pts // 1000}k", "good"))
        elif pts >= 50000:
            out.append((f"Maestría {pts // 1000}k", "info"))
        elif pts < 1000:
            out.append(("Primera vez", "warn"))
        elif pts < 10000:
            out.append((f"Poca maestría ({pts // 1000}k)", "warn"))
    s = st.get("streak", 0)
    if s >= 3:
        out.append((f"Racha +{s}", "good"))
    elif s <= -3:
        out.append((f"Racha {s}", "bad"))
    if st.get("otp") == x["cid"]:
        out.append(("Especialista", "info"))
    roles = p.get("roles") or []
    if x["role"] and roles and x["role"] not in roles and st.get("sr_n", 0) >= 6:
        out.append(("Fuera de su línea", "warn"))
    if p.get("level", 99) < 60 and (p.get("wr10") or 0) >= .65 and st.get("n", 0) >= 6:
        out.append(("Posible cuenta secundaria", "warn"))
    if not best_rank(p) and st.get("n", 0) >= 1:
        out.append(("Sin rango", "dim"))
    if st.get("last_days") is not None and st["last_days"] > 14:
        out.append(("Inactivo", "warn"))
    return out


def team_stats(members, info, ui):
    """Cifras del equipo a partir de los datos leídos: rango medio, victorias recientes y maestría con el campeón que lleva."""
    ranks, wrs, pts, n = [], [], [], 0
    for x, p in members:
        if x["me"] and (not p or p.get("error")):   # tu perfil aún no ha llegado: se usan tus datos ya cargados
            prof = (info or {}).get("profile") or {}
            rk = prof.get("solo") or prof.get("flex")
            if rank_score(rk) is not None:
                ranks.append(rank_score(rk))
            if x["cid"] and info:
                pts.append((info.get("mastery_all") or {}).get(x["cid"], 0))
            n += 1
            continue
        if not p or p.get("error"):
            continue
        n += 1
        sc = rank_score(best_rank(p))
        if sc is not None:
            ranks.append(sc)
        if p.get("wr10") is not None and len(p.get("recent") or []) >= 4:
            wrs.append(p["wr10"])
        if x["cid"]:
            pts.append((p.get("mastery") or {}).get(x["cid"], 0))
    comp = core.comp_stats([x["cid"] for x, _ in members if x["cid"]], ui.champs)
    return {"n": n, "rank": sum(ranks) / len(ranks) if ranks else None, "wr": sum(wrs) / len(wrs) if wrs else None,
            "pts": sum(pts) / len(pts) if pts else None, "comp": comp}


def collapsible(ui, parent, title, summary, key, build, open_=True):
    """Cabecera plegable (flecha, título y resumen) con el cuerpo debajo. Recuerda si estaba abierta. Sin animación: el cuerpo es grande y con
    la animación de ui.fold se medía antes de tiempo y se quedaba cortado."""
    folds = ui.conf.setdefault("folds", {})
    st = {"open": folds.get(key, open_), "built": False}
    bgp = ui.bg(parent)
    card, fg, dim = ui.hexm(PAL["card2"]), ui.hexm(PAL["fg"]), ui.hexm(PAL["dim"])
    box = tk.Frame(parent, bg=bgp)
    box.pack(fill="x", pady=(0, 8))
    import temas
    head = tk.Frame(box, bg=card, cursor="hand2", highlightthickness=1, highlightbackground=ui.hexm(ui.edge_color()))
    head.pack(fill="x")
    stripe = tk.Frame(head, width=3, bg=ui.hexm(ui.acc))
    stripe.pack(side="left", fill="y")
    arrow = tk.Label(head, text="", bg=card, fg=dim, font=ui.tkf(12, False, False), width=2)
    arrow.pack(side="left", padx=(10, 2), pady=7)
    ttl = tk.Label(head, text=title, bg=card, fg=fg, font=ui.tkf(12, True, False), anchor="w")
    ttl.pack(side="left")
    sm = tk.Label(head, text=summary, bg=card, fg=dim, font=ui.tkf(10, False, False), anchor="e")
    sm.pack(side="right", padx=12)
    body = tk.Frame(box, bg=bgp)

    def paint():
        arrow.configure(text="▾" if st["open"] else "▸")
        stripe.configure(bg=ui.hexm(ui.acc) if st["open"] else ui.hexm(PAL["edge"]))
        if st["open"]:
            if not st["built"]:
                st["built"] = True
                build(body)
            body.pack(fill="x", pady=(8, 0))
        else:
            body.pack_forget()

    def toggle(_e=None):
        st["open"] = not st["open"]
        folds[key] = st["open"]
        try:
            core.save_conf(ui.conf)
        except Exception:
            pass
        paint()
    for w in (head, arrow, ttl, sm):
        w.bind("<Button-1>", toggle)
    paint()
    return box


class Board:
    def __init__(self, view):
        self.v, self.ui = view, view.ui

    # ---------- entrada ----------
    def render(self, host, ctx, plan):
        ui, v = self.ui, self.v
        ros = ctx["roster"]
        pl, r = ctx.get("roster_pl") or {}, ctx.get("r") or {}
        info = ctx.get("info")
        self.party, self.mates = set(r.get("party") or ()), r.get("mates") or {}
        self.qid = (plan or {}).get("qid") or 0
        self.my_role = (plan or {}).get("role") or next((x["role"] for x in ros if x["me"]), "")
        self.opp = (plan or {}).get("opp") or 0
        self.pl, self.info = pl, info
        # colores de estado del tema y del modo actuales (antes eran fijos de modo oscuro y con 1,4:1 de contraste en claro)
        self.c_ally, self.c_enemy, self.c_rival = ui.hexm(PAL["good"]), ui.hexm(PAL["bad"]), ui.hexm(PAL["warn"])
        n_load = len([x for x in ros if x["puuid"]])
        v.roster_lbl = None
        if n_load and len(pl) < n_load:
            v.roster_lbl = ui.lbl(host, f"Leyendo perfiles… {len(pl)} de {n_load}", 10, "dim", anchor="w")
            v.roster_lbl.pack(anchor="w", pady=(0, 4))
        mine = [(x, pl.get(x["puuid"])) for x in ros if x["team"] == "ally"]
        theirs = [(x, pl.get(x["puuid"])) for x in ros if x["team"] == "enemy"]
        self.compare(host, mine, theirs)
        self.lanes(host, mine, theirs)
        ui.lbl(host, "Pasa el ratón por una tarjeta para ver sus últimas 10 partidas; haz clic para abrir su perfil completo. "
                     "Todo sale del cliente de cada jugador: un rango oculto o sin partidas se marca como tal.", 9, "dim", anchor="w",
               justify="left", wraplength=max(260, v.width - 110)).pack(anchor="w", pady=(6, 10))

    # ---------- comparativa de equipos ----------
    def compare(self, host, mine, theirs):
        ui = self.ui
        a, b = team_stats(mine, self.info, ui), team_stats(theirs, self.info, ui)
        box = ctk.CTkFrame(host, fg_color=PAL["card2"], corner_radius=12)
        box.pack(fill="x", pady=(0, 8))
        g = ui.frame(box)
        g.pack(fill="x", padx=12, pady=10)
        for c, w in ((0, 1), (1, 0), (2, 1)):
            g.grid_columnconfigure(c, weight=w, uniform="cmp" if w else "")
        g.grid_columnconfigure(1, minsize=150)
        ui.lbl(g, "TU EQUIPO", 9, "good", True).grid(row=0, column=0, sticky="e", padx=8)
        ui.lbl(g, "EQUIPO RIVAL", 9, "bad", True).grid(row=0, column=2, sticky="w", padx=8)
        rows = []
        if a["rank"] is not None or b["rank"] is not None:
            rows.append(("Rango medio", a["rank"], b["rank"], lambda s: score_rank(s)[0], lambda s: score_rank(s)[1], 0.5))
        if a["wr"] is not None or b["wr"] is not None:
            rows.append(("Victorias recientes", a["wr"], b["wr"], lambda s: f"{s * 100:.0f} %", None, 0.02))
        if a["pts"] is not None or b["pts"] is not None:
            rows.append(("Maestría con su campeón", a["pts"], b["pts"], lambda s: f"{s / 1000:.0f}k".replace(".", ","), None, 8000))
        i = 1
        for title, va, vb, fmt, colr, eps in rows:
            better = None
            if va is not None and vb is not None and abs(va - vb) > eps:
                better = "a" if va > vb else "b"
            for side, val, column, anchor in (("a", va, 0, "e"), ("b", vb, 2, "w")):
                txt = fmt(val) if val is not None else "s/d"
                color = colr(val) if (colr and val is not None) else ("good" if better == side else "fg")
                ui.lbl(g, txt, 12, color, True).grid(row=i, column=column, sticky=anchor, padx=8, pady=1)
            ui.lbl(g, title, 10, "dim").grid(row=i, column=1, pady=1)
            i += 1
        for title, key in (("Daño físico · mágico", "dmg"), ("Tanques · control", "tank")):
            for column, t, anchor in ((0, a, "e"), (2, b, "w")):
                c = t["comp"]
                if not c:
                    txt = "s/d"
                elif key == "dmg":
                    txt = f"{c['ad']} · {c['ap']}"
                else:
                    txt = f"{c['tanks']} · {ctl(c['cc'])}"
                ui.lbl(g, txt, 12, "fg", True).grid(row=i, column=column, sticky=anchor, padx=8, pady=1)
            ui.lbl(g, title, 10, "dim").grid(row=i, column=1, pady=1)
            i += 1
        if a["n"] < len(mine) or b["n"] < len(theirs):
            ui.lbl(box, "Las medias solo cuentan a quien ya se ha leído y tiene datos.", 9, "dim").pack(pady=(0, 8))

    # ---------- las cinco líneas ----------
    def lanes(self, host, mine, theirs):
        ui = self.ui
        left = {x["role"] or f"?{i}": (x, p) for i, (x, p) in enumerate(mine)}
        right = {x["role"] or f"?{i}": (x, p) for i, (x, p) in enumerate(theirs)}
        keys = [k for k in LANE_ORDER if k in left or k in right] + [k for k in list(left) + list(right) if k not in LANE_ORDER]
        keys = list(dict.fromkeys(keys))
        width = max(self.v.width - 100, MIN_WIDTH - 100)
        cw = (width - 84) // 2
        for k in keys:
            box = ui.frame(host)
            box.pack(fill="x", pady=3)
            g = ui.frame(box)
            g.pack(fill="x")
            g.grid_columnconfigure(0, weight=1, uniform="lane")
            g.grid_columnconfigure(2, weight=1, uniform="lane")
            g.grid_columnconfigure(1, minsize=84)
            det = ui.frame(box)
            for col_, side, ring in ((0, left.get(k), self.c_ally), (2, right.get(k), self.c_enemy)):
                if side:
                    self.card(g, side[0], side[1], ring, cw, box, det).grid(row=0, column=col_, sticky="nsew", padx=2)
            mid = ui.frame(g)
            mid.grid(row=0, column=1)
            rname = ROLES_ES.get(k, "")
            if rname:
                ui.chip(mid, rname, "dim").pack()
            if k == self.my_role and right.get(k):
                ui.lbl(mid, "tu línea", 9, "warn", True).pack(pady=(3, 0))

    # ---------- una tarjeta ----------
    def card(self, parent, x, p, ring, cw, row, det):
        ui = self.ui
        lane_rival = ring == self.c_enemy and self.my_role and x["role"] == self.my_role and (not self.opp or x["cid"] == self.opp)
        card = ctk.CTkFrame(parent, fg_color=PAL["card2"], corner_radius=12, border_width=2 if (x["me"] or lane_rival) else 0,
                            border_color=self.c_ally if x["me"] else self.c_rival)
        inner = ui.frame(card)
        inner.pack(fill="both", expand=True, padx=10, pady=8)
        ui.champ(inner, x["cid"], 46, False, ring if x["cid"] else None).pack(side="left", anchor="n")
        col_ = ui.frame(inner)
        col_.pack(side="left", fill="x", expand=True, padx=(10, 0))
        head = ui.frame(col_)
        head.pack(fill="x")
        prof = (self.info or {}).get("profile") or {}
        name = (p or {}).get("name") or (prof.get("name") if x["me"] else "")
        name = name or ("Nombre oculto" if not x["puuid"] else "Cargando…")
        rk = best_rank(p) or (best_rank(prof) if x["me"] else None)
        rank_w = 0
        if rk:
            txt = f"{rk['tier']} {rk['div']}".strip()
            rank_w = ui.tkf(10, True, False).measure(txt) + 6
            ui.lbl(head, txt, 10, TIER_COLORS.get(rk["key"], "fg"), True).pack(side="right")
        shown = ("Tú · " if x["me"] else "") + name
        ui.lbl(head, ui.fit(shown, ui.tkf(11, True, False), max(60, cw - 46 - 36 - rank_w)), 11, "fg", True).pack(side="left")
        line = ui.frame(col_)
        line.pack(fill="x", pady=(4, 0))
        if p and not p.get("error"):
            rec = p.get("recent") or []
            if rec:
                ui.dots(line, [g["w"] for g in rec], 7).pack(side="left")
                w = sum(g["w"] for g in rec)
                ui.lbl(line, f"  {w}V {len(rec) - w}D", 9, "dim").pack(side="left")
            else:
                ui.lbl(line, "Sin partidas recientes", 9, "dim").pack(side="left")
        elif p and p.get("error"):
            ui.lbl(line, "No se pudieron leer sus datos", 9, "dim").pack(side="left")
        elif x["puuid"]:
            ui.lbl(line, "Leyendo tu perfil…" if x["me"] else "Leyendo su perfil…", 9, "dim").pack(side="left")
        bw = ui.frame(col_)
        bw.pack(fill="x", pady=(5, 0))
        used = 0
        for txt, colr in badges(p, x, self.party, self.mates.get(x["puuid"]))[:3]:
            f = ui.tkf(10, False, False)
            w = f.measure(txt) + 30
            if used + w > cw - 46 - 24 and used:
                break
            ui.chip(bw, txt, colr).pack(side="left", padx=(0, 4))
            used += w + 4
        if p and not p.get("error"):
            self.hover(card, p, x)
            self.click(card, p, x, row, det)
        return card

    # ---------- clic: perfil completo debajo de la línea ----------
    def click(self, card, p, x, row, det):
        ui = self.ui
        opened = ui.__dict__.setdefault("open_prof", set())
        key = "vs:" + x["puuid"]

        def paint():
            if key in opened:
                det.pack(fill="x", pady=(3, 0))
                if not det.winfo_children():
                    profile_build(ui, det, p, self.qid, self.v.width)
            else:
                det.pack_forget()

        def toggle(_e=None):
            opened.symmetric_difference_update({key})
            paint()
        self.bind_tree(card, "<Button-1>", toggle)
        try:
            card.configure(cursor="hand2")
        except Exception:
            pass
        paint()

    @staticmethod
    def bind_tree(w, ev, cb):
        try:
            w.bind(ev, cb, add="+")
        except Exception:
            pass
        for c in w.winfo_children():
            Board.bind_tree(c, ev, cb)

    # ---------- al pasar el ratón: últimas 10 partidas ----------
    def hover(self, card, p, x):
        ui = self.ui
        st = {"t": None, "job": None}

        def kill():
            st["job"] = None
            if st["t"] is not None:
                try:
                    st["t"].destroy()
                except Exception:
                    pass
                st["t"] = None

        def enter(e):
            if st["job"] is not None:
                card.after_cancel(st["job"])
                st["job"] = None
            if st["t"] is not None:
                return
            t = tk.Toplevel(card)
            t.wm_overrideredirect(True)
            t.attributes("-topmost", True)
            self.popup(t, p, x)
            t.update_idletasks()
            sw, sh = t.winfo_screenwidth(), t.winfo_screenheight()
            px, py = e.x_root + 18, e.y_root + 14
            if 0 <= e.x_root < sw and px + t.winfo_reqwidth() > sw - 8:   # en la pantalla principal no se sale por la derecha (con otros monitores, coordenadas negativas: se respetan)
                px = e.x_root - t.winfo_reqwidth() - 14
            if 0 <= e.y_root < sh and py + t.winfo_reqheight() > sh - 48:
                py = max(0, sh - t.winfo_reqheight() - 48)
            t.geometry(f"+{px}+{py}")
            st["t"] = t

        def leave(_e):
            if st["job"] is None:
                st["job"] = card.after(140, kill)
        self.bind_tree(card, "<Enter>", enter)
        self.bind_tree(card, "<Leave>", leave)
        card.bind("<Destroy>", lambda e: kill(), add="+")

    def popup(self, t, p, x):
        ui = self.ui
        bg, fg, dim = ui.hexm(PAL["card2"]), ui.hexm(PAL["fg"]), ui.hexm(PAL["dim"])
        good, bad = ui.hexm(PAL["good"]), ui.hexm(PAL["bad"])
        frame = tk.Frame(t, bg=bg, bd=1, relief="solid", padx=12, pady=10)
        frame.pack()

        def label(parent, text, size=10, bold=False, color=fg, **kw):
            return tk.Label(parent, text=text, font=ui.tkf(size, bold, False), fg=color, bg=bg, bd=0, **kw)
        label(frame, p.get("name") or "Jugador", 12, True).pack(anchor="w")
        sub = [f"Nivel {p['level']}"] if p.get("level") else []
        rl = rank_line(best_rank(p))
        sub.append(rl or "Sin rango esta temporada")
        label(frame, "  ·  ".join(sub), 10, False, dim).pack(anchor="w")
        if x.get("cid") in ui.champs:   # lo que importa de este jugador ahora: cómo le va con el campeón que lleva y qué línea hace normalmente
            cn = core.name(x["cid"], ui.champs)
            pts = (p.get("mastery") or {}).get(x["cid"], 0)
            rc = next((c for c in (p.get("stats") or {}).get("champs") or [] if c["c"] == x["cid"]), None)
            txt = f"Con {cn}: " + (f"{rc['n']} partidas recientes, {round(100 * rc['w'] / rc['n'])} % de victorias" if rc else "ninguna partida reciente")
            txt += f" · maestría {pts:,}".replace(",", ".") if pts else " · sin maestría"
            label(frame, txt, 10, True, ui.hexm(PAL["info"]) if pts >= 50000 else fg).pack(anchor="w", pady=(4, 0))
        if p.get("roles"):
            label(frame, "Suele jugar: " + ", ".join(ROLES_ES.get(r, r).lower() for r in p["roles"]), 9, False, dim).pack(anchor="w")
        pk = (p.get("marks") or {}).get("peak")
        if pk:
            label(frame, f"Máximo de la temporada: {pk}", 9, False, dim).pack(anchor="w")
        rec = p.get("recent") or []
        stt = p.get("stats") or {}
        tk.Frame(frame, bg=ui.hexm(PAL["border"]), height=1).pack(fill="x", pady=6)
        if not rec:
            label(frame, "Sin partidas de Grieta recientes.", 10, False, dim).pack(anchor="w")
        else:
            ranked = any(g.get("q") in (420, 440, 710) for g in rec)
            w = sum(g["w"] for g in rec)
            label(frame, f"Últimas {len(rec)} {'clasificatorias' if ranked else 'de Grieta'}: {w}V {len(rec) - w}D", 10, True).pack(anchor="w")
            grid = tk.Frame(frame, bg=bg)
            grid.pack(anchor="w", pady=(4, 0))
            for i, g in enumerate(rec):
                ph = ui.champ_photo(g["c"], 22) if g.get("c") else None
                ic = tk.Label(grid, image=ph, bg=bg, bd=0) if ph is not None else tk.Label(grid, text="?", bg=bg, fg=dim)
                ic.image = ph
                ic.grid(row=i, column=0, padx=(0, 6), pady=1)
                tk.Label(grid, text="Victoria" if g["w"] else "Derrota", font=ui.tkf(10, True, False), fg=good if g["w"] else bad, bg=bg, width=8,
                         anchor="w").grid(row=i, column=1)
                kda = (g["k"] + g["a"]) / max(1, g["d"])
                tk.Label(grid, text=f"{g['k']}/{g['d']}/{g['a']}", font=ui.tkf(10, False, False), fg=fg, bg=bg, width=8, anchor="w").grid(row=i, column=2)
                tk.Label(grid, text=f"{num(kda)} KDA", font=ui.tkf(9, False, False), fg=dim, bg=bg, width=8, anchor="w").grid(row=i, column=3)
                mins = max(1, g.get("dur", 0)) / 60
                tk.Label(grid, text=f"{num(g.get('cs', 0) / mins)} súb./min", font=ui.tkf(9, False, False), fg=dim, bg=bg, width=10, anchor="w").grid(row=i, column=4)
                tk.Label(grid, text=f"{g.get('dmg', 0) / 1000:.0f}k daño".replace(".", ","), font=ui.tkf(9, False, False), fg=dim, bg=bg, width=8, anchor="w").grid(row=i, column=5)
                tk.Label(grid, text=QUEUES.get(g.get("q"), "Grieta"), font=ui.tkf(9, False, False), fg=dim, bg=bg, width=10, anchor="w").grid(row=i, column=6)
                tk.Label(grid, text=f"{ago(g.get('t'))} · {int(g.get('dur', 0) // 60)} min", font=ui.tkf(9, False, False), fg=dim, bg=bg, width=16, anchor="w").grid(row=i, column=7)
            if stt.get("n"):
                label(frame, f"Media: {num(stt['k'])}/{num(stt['d'])}/{num(stt['a'])} · {num(stt['kda'])} KDA · {num(stt['cspm'])} súbditos por minuto",
                      9, False, dim).pack(anchor="w", pady=(6, 0))
        champs = stt.get("champs") or []
        if champs:
            tk.Frame(frame, bg=ui.hexm(PAL["border"]), height=1).pack(fill="x", pady=6)
            label(frame, "Lo que más juega", 10, True).pack(anchor="w")
            line = tk.Frame(frame, bg=bg)
            line.pack(anchor="w", pady=(3, 0))
            for c in champs[:4]:
                ph = ui.champ_photo(c["c"], 22)
                if ph is not None:
                    lb = tk.Label(line, image=ph, bg=bg, bd=0)
                    lb.image = ph
                    lb.pack(side="left")
                label(line, f" {c['n']}p · {round(100 * c['w'] / c['n'])} %   ", 9, False, dim).pack(side="left")
        sig = signals(p)
        if sig:
            tk.Frame(frame, bg=ui.hexm(PAL["border"]), height=1).pack(fill="x", pady=6)
            for txt, colr in sig[:4]:
                label(frame, "• " + txt, 9, False, ui.hexm(PAL.get(colr, PAL["fg"]))).pack(anchor="w")
