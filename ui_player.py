"""Perfil completo de un jugador (aliado o rival): rangos, forma reciente, rendimiento, campeones, maestría, líneas y señales.

Todo sale del cliente de LoL (players.fetch_player); no se inventa nada: cada cifra es un cálculo sobre sus últimas partidas de Grieta.
"""
import time

from ui_kit import TIER_COLORS, ROLES_ES

QUEUE_NAMES = (("solo", "Solo/Dúo"), ("flex", "Flexible"), ("prem", "Clasificatorias de 5"))


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def ago(ms):
    """«hace 3 días», «hace 2 meses»… a partir de una fecha en milisegundos."""
    if not ms:
        return "sin fecha"
    days = max(0, (time.time() * 1000 - ms) / 86400000)
    if days < 1:
        return "hoy"
    if days < 2:
        return "ayer"
    if days < 60:
        return f"hace {int(days)} días"
    if days < 700:
        return f"hace {int(days // 30)} meses"
    return f"hace {int(days // 365)} años"


def signals(p):
    """[(texto, color)] con lo más llamativo del jugador."""
    out = []
    st = p.get("stats") or {}
    top = p.get("mastery_top") or []
    s = st.get("streak", 0)
    if s >= 3:
        out.append((f"Racha de {s} victorias", "good"))
    elif s <= -3:
        out.append((f"Racha de {-s} derrotas", "bad"))
    if st.get("otp"):
        out.append(("Juega casi siempre el mismo campeón", "info"))
    if st.get("last_days") is not None and st["last_days"] > 14:
        out.append((f"Inactivo desde hace {int(st['last_days'])} días", "warn"))
    if st.get("sr_n", 0) < 5:
        out.append(("Pocas partidas de Grieta recientes", "warn"))
    if p.get("level", 99) < 60 and (p.get("wr10") or 0) >= .65 and st.get("n", 0) >= 6:
        out.append(("Nivel bajo y muchas victorias: posible cuenta secundaria", "warn"))
    if top and top[0]["pts"] >= 300000:
        out.append(("Maestría muy alta en un campeón", "info"))
    return out


def rank_line(rk):
    if not rk:
        return None
    n = rk["w"] + rk["l"]
    base = f"{rk['tier']} {rk['div']}".strip() + f" · {rk['lp']} PL"
    if rk["l"] == 0 and rk["w"] >= 20:   # el cliente no da las derrotas de otros jugadores (saldría «0D, 100 %»): no se inventa el récord
        return base
    return base + f" · {rk['w']}V {rk['l']}D" + (f" ({rk['wr'] * 100:.0f} %)" if n else "")


def build(ui, parent, p, qid, width):
    """Rellena `parent` con el perfil completo de `p`."""
    wrap = max(240, width - 60)

    def head(text):
        ui.lbl(parent, text, 9, "dim", True).pack(anchor="w", pady=(12, 4))

    # ---- rangos ----
    head("RANGOS")
    shown = 0
    first = {710: "prem", 440: "flex"}.get(qid, "solo")   # primero el rango de la cola que se está jugando
    order = sorted(QUEUE_NAMES, key=lambda q: 0 if q[0] == first else 1)
    for key, label in order:
        rk = p.get(key)
        line = ui.frame(parent)
        line.pack(fill="x", pady=2)
        ui.lbl(line, label, 10, "dim", width=150, anchor="w").pack(side="left")
        if rk:
            shown += 1
            ui.lbl(line, rank_line(rk), 10, "fg", True, anchor="w").pack(side="left")
        else:
            ui.lbl(line, "sin clasificar", 10, "dim", anchor="w").pack(side="left")
    mk = p.get("marks") or {}
    extra = [t for t in (f"Máximo de esta temporada: {mk['peak']}" if mk.get("peak") else "",
                         f"Terminó la anterior en {mk['prev']}" if mk.get("prev") else "") if t]
    if extra:
        ui.lbl(parent, "  ·  ".join(extra), 10, "dim", anchor="w", justify="left", wraplength=wrap).pack(anchor="w", pady=(4, 0))

    st = p.get("stats") or {}
    rec = p.get("recent") or []
    # ---- forma reciente ----
    if rec:
        w = sum(x["w"] for x in rec)
        head(f"ÚLTIMAS {len(rec)} PARTIDAS DE GRIETA  ·  {w}V {len(rec) - w}D")
        row = ui.frame(parent)
        row.pack(anchor="w")
        for x in rec:
            ui.champ(row, x["c"], 28, False, "#3ddc84" if x["w"] else "#ff5a5f").pack(side="left", padx=2)
        if st.get("streak"):
            s = st["streak"]
            ui.lbl(parent, f"Racha actual: {abs(s)} {'victoria' if s > 0 else 'derrota'}{'s' if abs(s) > 1 else ''}", 10,
                   "good" if s > 0 else "bad", anchor="w").pack(anchor="w", pady=(4, 0))
    # ---- rendimiento ----
    if st.get("n"):
        head("RENDIMIENTO EN ESAS PARTIDAS")
        grid = ui.frame(parent)
        grid.pack(fill="x")
        cells = [(f"{num(st['k'])} / {num(st['d'])} / {num(st['a'])}", "K / D / A"), (num(st["kda"], 2), "KDA"),
                 (num(st["cspm"]), "súbditos por minuto"), (f"{int(st['dpm'])}", "daño por minuto"),
                 (num(st["vpm"], 2), "visión por minuto"), (f"{int(st['dur'] // 60)} min", "duración media")]
        for i, (v, lab) in enumerate(cells):
            c = ui.frame(grid)
            c.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 16), pady=2)
            ui.lbl(c, v, 12, "fg", True).pack(anchor="w")
            ui.lbl(c, lab, 9, "dim").pack(anchor="w")
    # ---- campeones recientes ----
    if st.get("champs"):
        head(f"CAMPEONES MÁS JUGADOS (últimas {st['sr_n']} de Grieta)")
        for c in st["champs"]:
            row = ui.frame(parent)
            row.pack(fill="x", pady=2)
            ui.champ(row, c["c"], 26, False).pack(side="left")
            nm = (ui.champs.get(c["c"]) or {}).get("name", "?")
            ui.lbl(row, nm, 11, "fg", True, width=110, anchor="w").pack(side="left", padx=8)
            wr = c["w"] / c["n"]
            ui.lbl(row, f"{c['n']} partida{'s' if c['n'] > 1 else ''}", 10, "dim", width=80, anchor="w").pack(side="left")
            ui.lbl(row, f"{wr * 100:.0f} % victorias", 10, "good" if wr >= .55 else "bad" if wr <= .4 else "dim", width=100, anchor="w").pack(side="left")
            ui.lbl(row, f"KDA {num(c['kda'], 1)}", 10, "dim", anchor="w").pack(side="left")
    # ---- maestría ----
    if p.get("mastery_top"):
        head("MAYOR MAESTRÍA")
        for m in p["mastery_top"][:5]:
            row = ui.frame(parent)
            row.pack(fill="x", pady=2)
            ui.champ(row, m["c"], 26, False).pack(side="left")
            nm = (ui.champs.get(m["c"]) or {}).get("name", "?")
            ui.lbl(row, nm, 11, "fg", True, width=110, anchor="w").pack(side="left", padx=8)
            ui.lbl(row, f"nivel {m['lvl']}", 10, "dim", width=70, anchor="w").pack(side="left")
            ui.lbl(row, f"{m['pts']:,} puntos".replace(",", "."), 10, "fg", width=120, anchor="w").pack(side="left")
            ui.lbl(row, "última vez " + ago(m["last"]), 10, "dim", anchor="w").pack(side="left")
    # ---- líneas ----
    if st.get("roles"):
        head("LÍNEAS QUE JUEGA")
        ui.lbl(parent, "  ·  ".join(f"{ROLES_ES.get(r, r)} {pct * 100:.0f} %" for r, pct in st["roles"]), 11, "fg", anchor="w").pack(anchor="w")
    # ---- señales ----
    sg = signals(p)
    if sg:
        head("A TENER EN CUENTA")
        for text, color in sg:
            ui.lbl(parent, "• " + text, 10, color, anchor="w", justify="left", wraplength=wrap).pack(anchor="w", pady=2)
    ui.lbl(parent, f"Nivel de cuenta {p.get('level', '?')}  ·  datos del cliente de LoL, actualizados cada 10 minutos", 9, "dim",
           anchor="w", justify="left", wraplength=wrap).pack(anchor="w", pady=(12, 0))
