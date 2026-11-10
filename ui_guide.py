"""Guía de juego en pantalla: cómo jugar con tu campeón y, si hay rival de línea, el duelo concreto (ventajas, ventanas de trade, picos de poder).
Todo se calcula con datos oficiales; ver guide.py para lo que es dato y lo que es cálculo."""
import guide
import builds
import lol_advisor as core

CACHE_DIR = core.CACHE


def _rows(ui, parent, rows, width, lw=104):
    for title, text, *tone in rows:
        row = ui.frame(parent)
        row.pack(fill="x", pady=2)
        ui.lbl(row, title.upper(), 9, tone[0] if tone and tone[0] in ("good", "bad") else "dim", True, width=lw, anchor="w").pack(side="left", anchor="n", pady=(3, 0))
        ui.lbl(row, text, 11, "fg", anchor="w", justify="left", wraplength=max(220, width - lw - 150)).pack(side="left", fill="x", expand=True)


def _spells(ui, parent, d, width):
    """Tabla de habilidades: tecla, nombre, enfriamiento, coste, alcance y descripción corta."""
    p = d["passive"]
    if p["n"]:
        row = ui.frame(parent)
        row.pack(fill="x", pady=(0, 3))
        ui.lbl(row, "PASIVA", 9, "dim", True, width=44, anchor="w").pack(side="left", anchor="n", pady=(2, 0))
        ui.lbl(row, p["n"], 11, "warn", True, width=150, anchor="w").pack(side="left", anchor="n")
    for s in d["spells"]:
        box = ui.frame(parent)
        box.pack(fill="x", pady=3)
        head = ui.frame(box)
        head.pack(fill="x")
        ui.lbl(head, s["k"], 12, "warn", True, width=20, anchor="w").pack(side="left")
        ui.lbl(head, s["n"], 11, "fg", True, anchor="w").pack(side="left")
        meta = [guide.cd_text(s)]
        c = guide.cost_text(s, d["res"])
        if c:
            meta.append(c)
        r = guide.range_text(s)
        if r:
            meta.append(f"alcance {r}")
        ui.lbl(head, "  ·  ".join(meta), 10, "dim", anchor="e").pack(side="right")
        if s["d"]:
            txt = s["d"] if len(s["d"]) <= 170 else s["d"][:167].rsplit(" ", 1)[0] + "…"
            ui.lbl(box, txt, 10, "dim", anchor="w", justify="left", wraplength=max(220, width - 120)).pack(anchor="w", padx=(20, 0))


def _own(ui, parent, d, name, width, b):
    sp = guide.spikes(d, name, (b or {}).get("skills") or [], [i for i in (((b or {}).get("items") or {}).get("core") or []) if "Boots" not in (ui.items.get(i) or {}).get("t", [])], ui.items)
    if d["ally"]:
        ui.lbl(parent, "CONSEJOS DE RIOT PARA JUGAR CON " + name.upper(), 9, "dim", True, anchor="w").pack(anchor="w", pady=(0, 3))
        for t in d["ally"]:
            ui.lbl(parent, "•  " + t, 11, "fg", anchor="w", justify="left", wraplength=max(240, width - 120)).pack(anchor="w", pady=1)
    ui.lbl(parent, "HABILIDADES (enfriamiento de rango 1 al máximo)", 9, "dim", True, anchor="w").pack(anchor="w", pady=(10, 3))
    _spells(ui, parent, d, width)
    if sp:
        ui.lbl(parent, "PICOS DE PODER", 9, "dim", True, anchor="w").pack(anchor="w", pady=(10, 3))
        _rows(ui, parent, sp, width)
        ui.lbl(parent, "Los niveles y el coste son exactos; el minuto en que llegas a cada objeto depende de tu partida.", 9, "dim", anchor="w").pack(anchor="w", pady=(4, 0))


def _vs(ui, parent, dm, do, cid, opp, width):
    nm, no = ui.champs[cid]["name"], ui.champs[opp]["name"]
    am = ui.champs[cid].get("attr") or {}
    ao = ui.champs[opp].get("attr") or {}
    rows = guide.duel(dm, do, nm, no, am, ao, ui.champs[opp].get("dmg", ""))
    if rows:
        _rows(ui, parent, rows, width)
    if do["enemy"]:
        ui.lbl(parent, f"CONSEJOS DE RIOT CONTRA {no.upper()}", 9, "dim", True, anchor="w").pack(anchor="w", pady=(10, 3))
        for t in do["enemy"]:
            ui.lbl(parent, "•  " + t, 11, "fg", anchor="w", justify="left", wraplength=max(240, width - 120)).pack(anchor="w", pady=1)
    ui.lbl(parent, f"HABILIDADES DE {no.upper()}", 9, "dim", True, anchor="w").pack(anchor="w", pady=(10, 3))
    _spells(ui, parent, do, width)
    ui.lbl(parent, "Lo de arriba sale de comparar las estadísticas y habilidades oficiales de ambos; no es una guía escrita de este duelo.", 9, "dim",
           anchor="w", justify="left", wraplength=max(240, width - 120)).pack(anchor="w", pady=(6, 0))


def guide_block(ui, host, cid, opp, lane, width):
    """Bloque «Guía de juego». Se rellena solo cuando llegan los datos de Data Dragon."""
    if cid not in ui.champs or not core.DD_VERSION:
        return
    box = ui.frame(host)
    box.pack(fill="x", pady=(12, 0))
    kc = guide.request(CACHE_DIR, core.DD_VERSION, ui.champs[cid])
    ko = guide.request(CACHE_DIR, core.DD_VERSION, ui.champs[opp]) if opp and opp in ui.champs else None
    bkey = builds.request(CACHE_DIR, ui.champs[cid], lane, ui.champs[opp] if opp and opp in ui.champs else None) if lane else None
    st = {"n": 0}

    def paint():
        if not box.winfo_exists():
            return
        ui.clear(box)
        ui.lbl(box, "GUÍA DE JUEGO", 10, "dim", True, anchor="w").pack(anchor="w", pady=(0, 4))
        a = guide.peek(kc)
        o = guide.peek(ko) if ko else None
        if a[0] == "loading" or (o and o[0] == "loading"):
            ui.lbl(box, "Cargando la guía…", 10, "dim").pack(anchor="w")
            st["n"] += 1
            if st["n"] < 60:
                box.after(600, paint)
            return
        if a[0] == "error":
            ui.lbl(box, a[1], 10, "dim", anchor="w").pack(anchor="w")
            return
        b = None
        if bkey:
            bs = builds.peek(bkey)
            b = bs[1] if bs[0] == "ok" else None
            if bs[0] == "loading" and st["n"] < 60:
                st["n"] += 1
                box.after(600, paint)
        nm = ui.champs[cid]["name"]
        ui.fold(box, f"Cómo jugar con {nm}", lambda p: _own(ui, p, a[1], nm, width, b), "habilidades · picos de poder", "gd_own", False)
        if o and o[0] == "ok":
            no = ui.champs[opp]["name"]
            ui.fold(box, f"Tu duelo contra {no}", lambda p: _vs(ui, p, a[1], o[1], cid, opp, width), "ventajas · ventanas de trade", "gd_vs", True)
    paint()
