"""Lógica del draft de las Clasificatorias de 5 (y Clash): turnos, bans dirigidos a cada rival, línea probable de cada rival y resumen de equipos.

Sin dibujo ni red: recibe la sesión de selección y los perfiles que ya leyó players.py. Todas las fórmulas están a la vista (docs/ESTADO_Y_PENDIENTES.md).
"""
from itertools import permutations

import analysis

LINES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT"]
DRAFT_QUEUES = {700, 710}
# pesos del puntaje de ban dirigido: maestría, veces jugado en sus últimas partidas y % de victorias con él
W_MASTERY, W_GAMES, W_WR = 0.50, 0.30, 0.20
MASTERY_FULL = 150000   # a partir de estos puntos la maestría ya cuenta al máximo
GAMES_FULL = 5          # a partir de 5 partidas recientes con el campeón cuenta al máximo


def is_draft(r):
    return (r.get("mode") or {}).get("id") in DRAFT_QUEUES


def progress(session):
    """Pasos del draft: [{type, mine, cell, done, now, champ}], más el resumen para mostrar."""
    me = session.get("localPlayerCellId", -1)
    mine = {p["cellId"] for p in session.get("myTeam", [])}
    steps = []
    for grp in session.get("actions", []):
        for a in grp:
            if a.get("type") in ("ban", "pick"):
                steps.append({"type": a["type"], "mine": a.get("actorCellId") in mine, "cell": a.get("actorCellId"), "done": bool(a.get("completed")),
                              "now": bool(a.get("isInProgress")), "champ": a.get("championId") or 0})
    nb = sum(1 for s in steps if s["type"] == "ban")
    out = {"steps": steps, "bans_total": nb, "picks_total": len(steps) - nb,
           "bans_done": sum(1 for s in steps if s["type"] == "ban" and s["done"]),
           "picks_done": sum(1 for s in steps if s["type"] == "pick" and s["done"]), "now": None, "wait": None}
    now = next((s for s in steps if s["now"]), None) or next((s for s in steps if not s["done"]), None)
    out["now"] = now
    if now is not None:
        i = steps.index(now)
        for k in range(i, len(steps)):
            if steps[k]["cell"] == me and not steps[k]["done"]:
                out["wait"] = k - i   # acciones de otros antes de la tuya (0 = te toca)
                out["mine_type"] = steps[k]["type"]
                break
    # fase 1 o 2: hay una segunda tanda de bans cuando ya se bloquearon picks
    out["second_bans"] = out["bans_done"] >= 6 and out["picks_done"] >= 1
    return out


def rank_of(p, qid):
    return (p.get("prem") if qid == 710 else None) or p.get("solo") or p.get("flex")


def infer_roles(cells, players, champs):
    """{puuid: línea} la más probable de cada rival: sus líneas habituales (60 %) y, si ya eligió, las del campeón (40 %). Reparto óptimo entre las 5 líneas."""
    people = [c for c in cells if c.get("puuid")]
    if len(people) < 2:
        return {}

    def score(c, line):
        p = players.get(c["puuid"]) or {}
        pct = dict(((p.get("stats") or {}).get("roles")) or [])
        s = 0.6 * pct.get(line, 0.0)
        pos = (champs.get(c.get("champ")) or {}).get("pos") or []
        if c.get("champ") and pos:
            s += 0.4 * (1.0 if line in pos or ("UTILITY" if line == "SUPPORT" else line) in pos else 0.0)
        return s
    best, best_s = None, -1
    n = len(people)
    for perm in permutations(LINES, n):
        s = sum(score(people[i], perm[i]) for i in range(n))
        if s > best_s:
            best, best_s = perm, s
    return {people[i]["puuid"]: best[i] for i in range(n)}


def scout_bans(cells, players, champs, banned, picked, limit=6):
    """Bans dirigidos: los campeones que más pesa cada rival que aún no ha elegido.
    puntaje = 0,50 · maestría (tope 150.000) + 0,30 · veces jugado (tope 5) + 0,20 · % de victorias. Devuelve lista ordenada."""
    out = []
    for c in cells:
        if c.get("champ") or not c.get("puuid"):
            continue
        p = players.get(c["puuid"]) or {}
        if not p or p.get("error"):
            continue
        st = p.get("stats") or {}
        rec = {x["c"]: x for x in st.get("champs", [])}
        mas = {m["c"]: m["pts"] for m in p.get("mastery_top", [])}
        for cid in set(rec) | set(mas):
            if cid in banned or cid in picked or cid not in champs:
                continue
            n, w = (rec[cid]["n"], rec[cid]["w"]) if cid in rec else (0, 0)
            pts = mas.get(cid, (p.get("mastery") or {}).get(cid, 0))
            sc = W_MASTERY * min(1.0, pts / MASTERY_FULL) + W_GAMES * min(1.0, n / GAMES_FULL) + W_WR * ((w / n) if n else 0.0)
            out.append({"cid": cid, "who": p.get("name") or c.get("name") or "?", "puuid": c["puuid"], "score": sc, "n": n, "w": w, "pts": pts})
    out.sort(key=lambda x: -x["score"])
    seen, res = set(), []
    for x in out:   # un campeón una sola vez (el del rival que más lo domina)
        if x["cid"] not in seen:
            seen.add(x["cid"])
            res.append(x)
    return res[:limit]


def team_summary(cells, players, qid):
    """Rango medio y dispersión de un equipo (con los jugadores cuyo rango se conoce) y cuántos no tienen rango ni historial."""
    vals, unknown = [], 0
    for c in cells:
        p = players.get(c.get("puuid")) if c.get("puuid") else None
        if not p or p.get("error"):
            continue
        v = analysis.ladder_value(rank_of(p, qid))
        if v is None:
            unknown += 1
        else:
            vals.append(v)
    if not vals:
        return {"n": 0, "unknown": unknown}
    avg = sum(vals) / len(vals)
    return {"n": len(vals), "unknown": unknown, "avg": avg, "spread": max(vals) - min(vals), "name": rank_name(avg)}


def rank_name(v):
    """Nombre del rango a partir del valor numérico de analysis.ladder_value (100 por división)."""
    t = int(v // 400)
    tiers = ["Hierro", "Bronce", "Plata", "Oro", "Platino", "Esmeralda", "Diamante", "Maestro"]
    t = max(0, min(t, len(tiers) - 1))
    if t >= 7:
        return "Maestro o más"
    div = ["IV", "III", "II", "I"][int((v % 400) // 100)]
    return f"{tiers[t]} {div}"
