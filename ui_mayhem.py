"""ARAM: Mayhem en pantalla: tus mejoras más elegidas con el campeón (Partida > Plan), las mejoras de cada jugador (Partida > Análisis) y lo que la
partida en vivo diga de tus mejoras. Sin porcentajes de victoria por mejora (no lo permiten las normas de Riot): ver augments.py."""
import tkinter as tk

from PIL import Image, ImageTk

import augments
from ui_sections import Section

TIER_COLOR = {"Plata": "dim", "Oro": "warn", "Prismática": "info"}


def icon(ui, aid, size):
    """Icono de una mejora (cuadrado con esquinas suaves) o None si aún no se ha bajado."""
    cache = ui.__dict__.setdefault("aug_img", {})
    px = max(12, int(size * ui.scale_px()))
    key = (aid, px, bool(augments.icon_path(aid)))
    if key in cache:
        return cache[key]
    p = augments.icon_path(aid)
    ph = None
    if p:
        try:
            im = Image.open(p).convert("RGBA").resize((px, px), Image.LANCZOS)
            ph = ImageTk.PhotoImage(im)
        except Exception:
            ph = None
    cache[key] = ph
    return ph


def chip(ui, parent, aid, size=30):
    """Icono (o cuadro con la inicial si falta) con su nombre y nivel en el cuadro de ayuda."""
    inf = augments.info(aid)
    ph = icon(ui, aid, size)
    if ph is not None:
        w = tk.Label(parent, image=ph, bd=0, highlightthickness=0, bg=ui.bg(parent))
        w.image = ph
    else:
        px = int(size * ui.scale_px())
        w = tk.Label(parent, text=(inf["n"] or "?")[:1], width=2, bg="#141e2a", fg="#8fa3b8", bd=0)
        w.configure(font=ui.tkf(10, True, False), height=max(1, px // 22))
    ui.tip(w, f"{inf['n']}" + (f"  ·  {inf['r']}" if inf["r"] else ""))
    return w


def plan_block(ui, host, plan, ctx, games, width):
    """Bloque de Mayhem de la pestaña Plan."""
    cid = plan["cid"]
    wrap = max(260, width - 110)
    ui.lbl(host, "ARAM: MAYHEM", 10, "dim", True, anchor="w").pack(anchor="w", pady=(16, 4))
    top, n = augments.counts(games, cid)
    name = ui.champs.get(cid, {}).get("name", "este campeón")
    if top:
        ui.lbl(host, f"Mejoras que más has elegido con {name} ({n} partida{'s' if n != 1 else ''} de Mayhem guardada{'s' if n != 1 else ''})", 11, "fg", True, anchor="w").pack(anchor="w")
        row = ui.frame(host)
        row.pack(anchor="w", pady=(8, 2))
        augments.fetch_icons([a for a, _ in top], ui.conf, lambda: ui.notify("game_data"))
        for aid, k in top:
            cell = ui.frame(row)
            cell.pack(side="left", padx=(0, 12))
            chip(ui, cell, aid, 36).pack()
            ui.lbl(cell, f"×{k}", 9, "dim").pack()
        names = ", ".join(f"{augments.info(a)['n']} ({augments.info(a)['r'].lower() or '—'})" for a, _ in top[:5])
        ui.lbl(host, names, 10, "dim", anchor="w", justify="left", wraplength=wrap).pack(anchor="w", pady=(2, 0))
    else:
        ui.lbl(host, f"Aún no hay partidas de Mayhem guardadas con {name}: cuando juegues alguna, aquí verás las mejoras que sueles elegir con él.", 10, "dim",
               anchor="w", justify="left", wraplength=wrap).pack(anchor="w")
    live = ctx.get("live_aug")
    if live:
        ui.lbl(host, "DETECTADAS EN LA PARTIDA", 9, "dim", True, anchor="w").pack(anchor="w", pady=(12, 4))
        ui.lbl(host, "  ·  ".join(str(x) for x in live)[:500], 10, "fg", anchor="w", justify="left", wraplength=wrap).pack(anchor="w")
    ui.lbl(host, "En cada ronda todos eligen dentro de la misma categoría (Plata, Oro o Prismática); según las guías se puede relanzar una vez cada opción y, según Riot, "
                 "las mejoras se eligen estando muerto (niveles 3, 7, 11 y 15). LOL-E no muestra porcentajes de victoria de mejoras: Riot no permite que "
                 "las aplicaciones los enseñen.", 9, "dim", anchor="w", justify="left", wraplength=wrap).pack(anchor="w", pady=(12, 0))


def analysis_block(ui, parent, a, width):
    """Mejoras elegidas por cada jugador en una partida de Mayhem."""
    players = [p for p in a["players"].values() if p.get("aug")]
    if not players:
        return
    ids = [x for p in players for x in p["aug"]]
    augments.fetch_icons(ids, ui.conf, lambda: ui.notify("game_data"))
    ui.lbl(parent, "MEJORAS ELEGIDAS", 9, "dim", True, anchor="w").pack(anchor="w", pady=(12, 4))
    for team_mine in (True, False):
        for p in sorted((p for p in players if (p["team"] == a["team"]) == team_mine), key=lambda p: p["pid"]):
            row = ui.frame(parent)
            row.pack(fill="x", pady=2)
            ui.champ(row, p["champ"], 26, False, "#3ddc84" if team_mine else "#ff5a5f").pack(side="left")
            nm = ui.champs.get(p["champ"], {}).get("name", "?")
            ui.lbl(row, nm + (" (tú)" if p["pid"] == a["me"] else ""), 10, "fg", p["pid"] == a["me"], width=110, anchor="w").pack(side="left", padx=8)
            for aid in p["aug"]:
                chip(ui, row, aid, 26).pack(side="left", padx=2)
    ui.lbl(parent, "Pasa el ratón sobre un icono para ver su nombre y categoría.", 9, "dim", anchor="w").pack(anchor="w", pady=(4, 0))


# ---------------------------------------------------------------- build sugerida de ARAM / Mayhem
def _items(ui, parent, ids, size=30):
    row = ui.frame(parent)
    for iid in ids:
        ph = ui.item_photo(iid, size) if iid else None
        if ph is None:
            continue
        lab = tk.Label(row, image=ph, bd=0, highlightthickness=0, bg=ui.bg(parent))
        lab.image = ph
        info = ui.items.get(iid)
        if info:
            ui.tip(lab, f"{info['n']}  ·  {info['g']} de oro" + (f"\n{info['d']}" if info.get("d") else ""))
        lab.pack(side="left", padx=2)
    return row


def build_block(ui, host, cid, mode_id, width):
    """Build sugerida (op.gg) y, en Mayhem, mejoras sugeridas. Se rellena sola cuando llegan los datos."""
    import aram_builds
    import lol_advisor as core
    mode = aram_builds.MODES.get(mode_id)
    if not mode or cid not in ui.champs:
        return
    mayhem = mode_id in augments.MAYHEM_QUEUES
    key = aram_builds.request(core.CACHE, ui.champs[cid], mode)
    box = ui.frame(host)
    box.pack(fill="x", pady=(12, 0))
    wrap = max(260, width - 110)
    state = {"n": 0}

    def paint():
        if not box.winfo_exists():
            return
        st = aram_builds.peek(key)
        ui.clear(box)
        title = "BUILD SUGERIDA PARA " + ("ARAM: MAYHEM" if mayhem else "ARAM") + " · op.gg"
        ui.lbl(box, title, 10, "dim", True, anchor="w").pack(anchor="w", pady=(0, 4))
        if st[0] == "ok" and st[1].get("stale"):
            ui.lbl(box, "No se pudo actualizar ahora: son los últimos datos guardados.", 9, "warn", anchor="w").pack(anchor="w", pady=(0, 4))
        if st[0] == "loading":
            ui.lbl(box, "Cargando la build…", 10, "dim").pack(anchor="w")
            state["n"] += 1
            if state["n"] < 90:
                box.after(500, paint)
            return
        if st[0] == "error":
            ui.lbl(box, st[1], 10, "dim", anchor="w", justify="left", wraplength=wrap).pack(anchor="w")
            return
        d = st[1]
        for label, ids in (("INICIO", d["starters"]), ("BOTAS", d["boots"])):
            if ids:
                r = ui.frame(box)
                r.pack(fill="x", pady=4)
                ui.lbl(r, label, 9, "dim", True, width=84, anchor="w").pack(side="left")
                _items(ui, r, ids).pack(side="left")
        for i, b in enumerate(d["builds"], 1):
            r = ui.frame(box)
            r.pack(fill="x", pady=4)
            ui.lbl(r, f"BUILD {i}", 9, "dim", True, width=84, anchor="w").pack(side="left")
            _items(ui, r, b, 34).pack(side="left")
        if d.get("skills"):
            r = ui.frame(box)
            r.pack(fill="x", pady=4)
            ui.lbl(r, "HABILIDADES", 9, "dim", True, width=84, anchor="w").pack(side="left")
            ui.lbl(r, " > ".join(d["skills"][:9]), 11, "warn", True).pack(side="left")
        if mayhem and d.get("augments"):
            if augments.ensure_catalog(ui.conf, lambda: ui.notify("game_data")):
                ui.lbl(box, "Cargando las mejoras del cliente…", 10, "dim").pack(anchor="w", pady=(12, 0))
                return
            ids = aram_builds.augment_ids(d["augments"], augments.catalog())
            known = {n for _, n in ids}
            ui.lbl(box, "MEJORAS QUE SUGIERE OP.GG PARA ESTE CAMPEÓN (sin porcentajes)", 10, "dim", True, anchor="w").pack(anchor="w", pady=(12, 4))
            augments.fetch_icons([a for a, _ in ids], ui.conf, lambda: ui.notify("game_data"))
            for tier in ("Prismática", "Oro", "Plata"):
                mine = [(a, n) for a, n in ids if augments.info(a)["r"] == tier]
                if not mine:
                    continue
                r = ui.frame(box)
                r.pack(fill="x", pady=4)
                ui.lbl(r, tier.upper(), 9, TIER_COLOR.get(tier, "dim"), True, width=84, anchor="w").pack(side="left")
                for a, n in mine:
                    chip(ui, r, a, 30).pack(side="left", padx=2)
                ui.lbl(r, ", ".join(augments.info(a)["n"] for a, _ in mine), 10, "dim", anchor="w", justify="left",
                       wraplength=max(200, wrap - 200)).pack(side="left", padx=8)
            rest = [n for n in d["augments"] if n not in known]
            if rest:
                ui.lbl(box, "Mejoras de op.gg que no encuentro en tu cliente (sin icono): " + ", ".join(rest), 9, "dim", anchor="w", justify="left", wraplength=wrap).pack(anchor="w", pady=(2, 0))
        ui.lbl(box, "Orden y listas de op.gg; en Mayhem no publica porcentajes. LOL-E tampoco muestra victorias por mejora (norma de Riot). "
                    "Como cada ronda es de una sola categoría, mira la fila de esa categoría; si no hay ninguna de tu lista, elige por lo que haga tu build.",
               9, "dim", anchor="w", justify="left", wraplength=wrap).pack(anchor="w", pady=(8, 0))
    paint()

class AramBuild(Section):
    """Selección de ARAM / Mayhem: build sugerida (y mejoras sugeridas en Mayhem) para el campeón que llevas."""

    def key(self, ctx):
        r = ctx["r"]
        return (r["mode"]["kind"], r["mode"]["id"], r.get("mine"), r.get("mine_locked"))

    def build(self, ctx):
        ui, r = self.ui, ctx["r"]
        import aram_builds
        if r["mode"]["kind"] != "aram" or not r.get("mine") or r["mode"]["id"] not in aram_builds.MODES:
            return
        c = ui.card(self.box, f"Tu campeón: {ui.champs[r['mine']]['name']}" if r["mine"] in ui.champs else "Tu campeón")
        build_block(ui, c, r["mine"], r["mode"]["id"], ctx["width"])