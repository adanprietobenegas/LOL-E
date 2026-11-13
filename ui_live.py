"""Bloque «En vivo» de la pestaña Partida: marcador, objetivos y los jugadores con sus objetos (datos de live.summarize).

Se repinta solo este bloque cada pocos segundos (GameView.on_live): repintar toda la pestaña cuesta más de un segundo.
Los datos salen de la API local del juego y son los mismos que ves en la tabla de puntuación dentro de la partida.
"""
import customtkinter as ctk

import live
from ui_build import _item
from ui_kit import PAL

NEUTRAL = "#8fa0b4"


def _rows(snap):
    """(tuyos, rivales, títulos, ¿se sabe cuál es tu equipo?) a partir del resumen."""
    me = snap.get("me_team") or ""
    mine_t = me or "ORDER"
    other_t = "CHAOS" if mine_t == "ORDER" else "ORDER"
    mine = [p for p in snap["players"] if p["team"] == mine_t]
    other = [p for p in snap["players"] if p["team"] == other_t]
    titles = ("TU EQUIPO", "RIVALES") if me else ("EQUIPO AZUL", "EQUIPO ROJO")
    return mine, other, titles, mine_t, other_t, bool(me)


def paint(ui, host, snap, width, opp_cid=0):
    ui.clear(host)
    mine, other, (t_mine, t_other), k_mine, k_other, known = _rows(snap)
    c_mine = ui.hexm(PAL["good"]) if known else NEUTRAL
    c_other = ui.hexm(PAL["bad"]) if known else NEUTRAL
    card = ctk.CTkFrame(host, fg_color=PAL["card2"], corner_radius=12)
    card.pack(fill="x")
    box = ui.frame(card)
    box.pack(fill="x", padx=12, pady=10)
    head = ui.frame(box)
    head.pack(fill="x")
    ui.lbl(head, f"EN VIVO  ·  {live.clock(snap['t'])}", 10, "fg", True).pack(side="left")
    if snap.get("gold"):
        ui.lbl(head, f"Tu oro: {snap['gold']}", 10, "dim").pack(side="right")
    teams = snap["teams"]
    a, b = teams.get(k_mine, {}), teams.get(k_other, {})
    grid = ui.frame(box)
    grid.pack(fill="x", pady=(8, 2))
    for c, w in ((0, 1), (1, 0), (2, 1)):
        grid.grid_columnconfigure(c, weight=w, uniform="live" if w else "")
    grid.grid_columnconfigure(1, minsize=130)
    ui.lbl(grid, t_mine, 9, "dim", True).grid(row=0, column=0, sticky="e", padx=8)
    ui.lbl(grid, t_other, 9, "dim", True).grid(row=0, column=2, sticky="w", padx=8)
    lines = [("Bajas", a.get("kills", 0), b.get("kills", 0), str), ("Oro en objetos", a.get("value", 0), b.get("value", 0), live.money)]
    for title, key in (("Torres", "towers"), ("Inhibidores", "inhibs"), ("Dragones", "dragons"), ("Heraldos", "heralds"), ("Barones", "barons")):
        if a.get(key) or b.get(key):
            lines.append((title, a.get(key, 0), b.get(key, 0), str))
    for i, (title, va, vb, fmt) in enumerate(lines, 1):
        ui.lbl(grid, fmt(va), 12, c_mine if va >= vb else "dim", True).grid(row=i, column=0, sticky="e", padx=8, pady=1)
        ui.lbl(grid, title, 10, "dim").grid(row=i, column=1, pady=1)
        ui.lbl(grid, fmt(vb), 12, c_other if vb >= va else "dim", True).grid(row=i, column=2, sticky="w", padx=8, pady=1)

    def players(parent, rows, color):
        for p in rows:
            _player(ui, parent, p, color, width, bool(opp_cid) and p["cid"] == opp_cid and p["team"] != next((q["team"] for q in snap["players"] if q["me"]), ""))

    pareja = live.duel(snap, opp_cid)
    if pareja:   # tu rival directo (el de tu línea, o el que elegiste a mano): cómo vas frente a él
        ui.lbl(box, live.duel_line(*pareja, ui.champs.get(opp_cid, {}).get("name", "")), 11, "fg", anchor="w", justify="left",
               wraplength=max(240, width - 110)).pack(anchor="w", pady=(6, 0))
    frases = live.reading(live.itemization(other, ui.items or {}))
    if frases:
        ui.lbl(box, " ".join(frases) + "  (orientativo)", 10, "dim", anchor="w", justify="left",
               wraplength=max(240, width - 110)).pack(anchor="w", pady=(6, 0))
    ui.lbl(box, t_other, 9, "dim", True, anchor="w").pack(anchor="w", pady=(8, 2))
    players(box, other, c_other)
    summary = f"{sum(p['k'] for p in mine)} bajas · {live.money(sum(p['value'] for p in mine))} en objetos"
    ui.fold(box, t_mine.capitalize(), lambda c: players(c, mine, c_mine), summary, "live_mine", False)


def _player(ui, parent, p, color, width, rival=False):
    row = ui.frame(parent)
    row.pack(fill="x", pady=2)
    if p["cid"] in ui.champs:
        ui.champ(row, p["cid"], 32, False, NEUTRAL if p["dead"] else color).pack(side="left")
    else:
        ui.lbl(row, "?", 12, "dim", width=32).pack(side="left")
    right = ui.frame(row)
    right.pack(side="right", padx=(6, 0))
    if p["dead"]:
        ui.lbl(right, f"↻ {int(p['respawn'])} s", 10, "warn", True).pack(anchor="e")
    ui.lbl(right, live.money(p["value"]), 10, "fg", True).pack(anchor="e")
    mid = ui.frame(row)
    mid.pack(side="left", fill="x", expand=True, padx=8)
    name = ui.champs.get(p["cid"], {}).get("name") or p["name"]
    ui.lbl(mid, name + ("  (tú)" if p["me"] else "  · tu rival" if rival else ""), 11, "dim" if p["dead"] else "fg", True, anchor="w").pack(anchor="w")
    ui.lbl(mid, f"Nv {p['level']}  ·  {p['k']}/{p['d']}/{p['a']}  ·  {p['cs']} cs", 10, "dim", anchor="w").pack(anchor="w")
    items = ui.frame(row if width >= 760 else parent)
    if width >= 760:
        items.pack(side="right", padx=8)
    else:
        items.pack(fill="x", padx=(40, 0), pady=(0, 2))
    for iid in p["items"][:7]:
        _item(ui, items, iid, 22)
