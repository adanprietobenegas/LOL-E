"""ARAM: Mayhem en pantalla: tus mejoras más elegidas con el campeón (Partida > Plan), las mejoras de cada jugador (Partida > Análisis) y lo que la
partida en vivo diga de tus mejoras. Sin porcentajes de victoria por mejora (no lo permiten las normas de Riot): ver augments.py."""
import tkinter as tk

from PIL import Image, ImageTk

import augments

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
    ui.lbl(host, "ARAM: MAYHEM", 10, "dim", True, anchor="w").pack(anchor="w", pady=(14, 4))
    top, n = augments.counts(games, cid)
    name = ui.champs.get(cid, {}).get("name", "este campeón")
    if top:
        ui.lbl(host, f"Mejoras que más has elegido con {name} ({n} partida{'s' if n != 1 else ''} de Mayhem guardada{'s' if n != 1 else ''})", 11, "fg", True, anchor="w").pack(anchor="w")
        row = ui.frame(host)
        row.pack(anchor="w", pady=(6, 2))
        augments.fetch_icons([a for a, _ in top], ui.conf)
        for aid, k in top:
            cell = ui.frame(row)
            cell.pack(side="left", padx=(0, 10))
            chip(ui, cell, aid, 36).pack()
            ui.lbl(cell, f"×{k}", 9, "dim").pack()
        names = ", ".join(f"{augments.info(a)['n']} ({augments.info(a)['r'].lower() or '—'})" for a, _ in top[:5])
        ui.lbl(host, names, 10, "dim", anchor="w", justify="left", wraplength=wrap).pack(anchor="w", pady=(2, 0))
    else:
        ui.lbl(host, f"Aún no hay partidas de Mayhem guardadas con {name}: cuando juegues alguna, aquí verás las mejoras que sueles elegir con él.", 10, "dim",
               anchor="w", justify="left", wraplength=wrap).pack(anchor="w")
    live = ctx.get("live_aug")
    if live:
        ui.lbl(host, "DETECTADAS EN LA PARTIDA", 9, "dim", True, anchor="w").pack(anchor="w", pady=(10, 3))
        ui.lbl(host, "  ·  ".join(str(x) for x in live)[:500], 10, "fg", anchor="w", justify="left", wraplength=wrap).pack(anchor="w")
    ui.lbl(host, "En cada ronda todos eligen dentro de la misma categoría (Plata, Oro o Prismática); según las guías se puede relanzar una vez cada opción y, según Riot, "
                 "las mejoras se eligen estando muerto (niveles 3, 7, 11 y 15). LOL-E no muestra porcentajes de victoria de mejoras: Riot no permite que "
                 "las aplicaciones los enseñen.", 9, "dim", anchor="w", justify="left", wraplength=wrap).pack(anchor="w", pady=(10, 0))


def analysis_block(ui, parent, a, width):
    """Mejoras elegidas por cada jugador en una partida de Mayhem."""
    players = [p for p in a["players"].values() if p.get("aug")]
    if not players:
        return
    ids = [x for p in players for x in p["aug"]]
    augments.fetch_icons(ids, ui.conf)
    ui.lbl(parent, "MEJORAS ELEGIDAS", 9, "dim", True, anchor="w").pack(anchor="w", pady=(10, 3))
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
