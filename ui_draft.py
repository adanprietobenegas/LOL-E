"""Tarjeta «Draft de 5» de la selección (Clasificatorias de 5 y Clash): turno, bans dirigidos, línea probable de cada rival y resumen de equipos."""
import tkinter as tk

import draft5
from ui_kit import PAL, ROLES_ES
from ui_sections import Section


def es(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


class DraftCard(Section):
    def key(self, ctx):
        r = ctx["r"]
        if not draft5.is_draft(r):
            return ("off",)
        pg = draft5.progress(ctx["session"])
        pl = ctx["players"]
        cells = {c["puuid"] for c in r["enemy_cells"]}
        return (pg["bans_done"], pg["picks_done"], pg["wait"], tuple((c["cell"], c["champ"]) for c in r["enemy_cells"]),
                tuple(sorted((k, len(v.get("recent", [])), bool(v.get("error"))) for k, v in pl.items())), tuple(r["bans"]), len(cells))

    def build(self, ctx):
        ui, r, pl = self.ui, ctx["r"], ctx["players"]
        if not draft5.is_draft(r):
            return
        pg = draft5.progress(ctx["session"])
        c = ui.card(self.box, "Draft de 5")
        self.steps(c, pg)
        cells = r["enemy_cells"]
        champs = ui.champs
        banned, picked = set(r["bans"]), set(r["enemies"]) | {a["champ"] for a in r["ally_cells"] if a["champ"]}
        loaded = [x for x in cells if x["puuid"] in pl]
        if not any(x["puuid"] for x in cells):
            ui.lbl(c, "En esta cola Riot no muestra los nombres rivales: no hay bans dirigidos.", 10, "dim", anchor="w").pack(anchor="w", pady=(8, 0))
        elif len(loaded) < len([x for x in cells if x["puuid"]]):
            ui.lbl(c, f"Leyendo perfiles rivales… {len(loaded)} de {len([x for x in cells if x['puuid']])}", 10, "dim", anchor="w").pack(anchor="w", pady=(8, 0))
        self.scout(c, r, pl, champs, banned, picked, pg)
        self.lines(c, r, pl, champs)
        self.teams(c, r, pl)
        ui.lbl(c, "Cola de grupos de 5: solo fines de semana y, según Riot, hasta el 7 de enero de 2027. Los puntajes de ban son orientativos.", 9, "dim",
               anchor="w", justify="left", wraplength=max(260, ctx["width"] - 120)).pack(anchor="w", pady=(10, 0))

    # ---- turnos ----
    def steps(self, c, pg):
        ui = self.ui
        if not pg["steps"]:
            return
        row = ui.frame(c)
        row.pack(anchor="w", pady=(0, 6))
        for s in pg["steps"]:
            col = ui.hexm(PAL["good"] if s["mine"] else PAL["bad"])
            if s["done"]:
                bg, fg = col, ui.hexm(PAL["bg"])
            elif s["now"]:
                bg, fg = ui.hexm(PAL["card2"]), col
            else:
                bg, fg = ui.hexm(PAL["card2"]), ui.hexm(PAL["dim"])
            tk.Label(row, text="B" if s["type"] == "ban" else "P", bg=bg, fg=fg, font=ui.tkf(8, True, False), width=2, bd=0,
                     highlightthickness=1 if s["now"] else 0, highlightbackground=col).pack(side="left", padx=1)
        now = pg["now"]
        if now:
            who = "tu equipo" if now["mine"] else "el rival"
            txt = f"Ahora {'banea' if now['type'] == 'ban' else 'elige'} {who}."
            if pg["wait"] == 0:
                txt = "Te toca " + ("banear." if pg.get("mine_type") == "ban" else "elegir.")
            elif pg["wait"]:
                txt += f" Tu {'ban' if pg.get('mine_type') == 'ban' else 'pick'} llega en {pg['wait']} acciones."
            ui.lbl(c, txt, 11, "fg", True, anchor="w").pack(anchor="w")
        ui.lbl(c, f"Bans {pg['bans_done']} de {pg['bans_total']}  ·  Picks {pg['picks_done']} de {pg['picks_total']}   (verde: tu equipo, rojo: rival)", 9, "dim",
               anchor="w").pack(anchor="w", pady=(2, 0))

    # ---- bans dirigidos ----
    def scout(self, c, r, pl, champs, banned, picked, pg):
        ui = self.ui
        import draft5 as d
        lst = d.scout_bans(r["enemy_cells"], pl, champs, banned, picked)
        if not lst:
            return
        title = "BANS DIRIGIDOS · lo que más puede jugar cada rival que aún no ha elegido" + (" (2.ª tanda: ya se han visto 6 picks)" if pg["second_bans"] else "")
        ui.lbl(c, title, 9, "dim", True, anchor="w", justify="left", wraplength=420).pack(anchor="w", pady=(10, 3))
        for x in lst:
            row = ui.frame(c)
            row.pack(fill="x", pady=2)
            ui.champ(row, x["cid"], 30, False, "#ff5a5f").pack(side="left")
            mid = ui.frame(row)
            mid.pack(side="left", padx=10)
            ui.lbl(mid, f"{champs[x['cid']]['name']}  ·  de {x['who']}", 11, "fg", True, anchor="w").pack(anchor="w")
            bits = []
            if x["n"]:
                bits.append(f"{x['n']} partida{'s' if x['n'] > 1 else ''} recientes, {x['w'] / x['n'] * 100:.0f} % victorias")
            if x["pts"] >= 1000:
                bits.append(f"maestría {x['pts'] // 1000}k")
            ui.lbl(mid, "  ·  ".join(bits) or "sin datos recientes", 10, "dim", anchor="w").pack(anchor="w")
            ui.lbl(row, f"{x['score'] * 100:.0f}", 13, "warn", True, True).pack(side="right")
        ui.lbl(c, "Puntaje (0-100) = 50 % maestría (tope 150k) + 30 % veces jugado (tope 5) + 20 % victorias con él.", 9, "dim", anchor="w").pack(anchor="w", pady=(4, 0))

    # ---- línea probable de cada rival ----
    def lines(self, c, r, pl, champs):
        ui = self.ui
        roles = draft5.infer_roles(r["enemy_cells"], pl, champs)
        if not roles:
            return
        ui.lbl(c, "LÍNEA PROBABLE DE CADA RIVAL (deducida de sus líneas habituales y de su campeón)", 9, "dim", True, anchor="w", justify="left",
               wraplength=420).pack(anchor="w", pady=(12, 3))
        row = ui.frame(c)
        row.pack(anchor="w")
        mine = (r.get("role") or "").upper()
        for e in sorted(r["enemy_cells"], key=lambda x: draft5.LINES.index(roles[x["puuid"]]) if x["puuid"] in roles else 9):
            if e["puuid"] not in roles:
                continue
            cell = ui.frame(row)
            cell.pack(side="left", padx=5)
            line = roles[e["puuid"]]
            ui.champ(cell, e["champ"], 38, False, "#ffd166" if line == mine else "#ff5a5f").pack()
            ui.lbl(cell, ROLES_ES.get(line, line), 9, "warn" if line == mine else "dim", line == mine).pack()
            p = pl.get(e["puuid"]) or {}
            ui.lbl(cell, (p.get("name") or e["name"] or "")[:11], 9, "dim").pack()
        opp = next((e for e in r["enemy_cells"] if roles.get(e["puuid"]) == mine and e["champ"]), None)
        if mine and opp:
            ui.lbl(c, f"Tu rival de línea probable: {champs[opp['champ']]['name']} ({(pl.get(opp['puuid']) or {}).get('name') or opp['name']})", 11, "warn", True,
                   anchor="w").pack(anchor="w", pady=(6, 0))

    # ---- resumen de equipos ----
    def teams(self, c, r, pl):
        ui = self.ui
        qid = r["mode"]["id"]
        mine = draft5.team_summary([{"puuid": a["puuid"]} for a in r["ally_cells"]], pl, qid)
        them = draft5.team_summary(r["enemy_cells"], pl, qid)
        if not mine["n"] and not them["n"]:
            return
        ui.lbl(c, "RANGO DE LOS EQUIPOS (jugadores con rango conocido)", 9, "dim", True, anchor="w").pack(anchor="w", pady=(12, 3))
        for label, t, col in (("Tu equipo (sin contarte)", mine, "good"), ("Equipo rival", them, "bad")):
            if not t["n"]:
                continue
            line = f"{label}: media {t['name']}  ·  {t['n']} jugador{'es' if t['n'] > 1 else ''}"
            if t["spread"] >= 400:
                line += f"  ·  mucha diferencia entre ellos ({int(t['spread'] // 100)} divisiones)"
            if t["unknown"]:
                line += f"  ·  {t['unknown']} sin rango"
            ui.lbl(c, line, 10, col, anchor="w", justify="left", wraplength=420).pack(anchor="w", pady=1)
        if mine["n"] and them["n"]:
            d = them["avg"] - mine["avg"]
            if abs(d) >= 100:
                ui.lbl(c, f"El equipo rival tiene de media {int(abs(d) // 100)} división{'es' if abs(d) >= 200 else ''} {'más' if d > 0 else 'menos'} que el tuyo.", 10, "dim",
                       anchor="w").pack(anchor="w", pady=(2, 0))
