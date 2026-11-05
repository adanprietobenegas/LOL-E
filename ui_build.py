"""Panel de build: runas, hechizos, objetos y habilidades más usados (Lolalytics), con iconos y descripción al pasar el ratón."""
import tkinter as tk

import customtkinter as ctk

import builds
import opgg_builds
import lol_advisor as core
import runes as runemod
from ui_kit import PAL

SKILLS = {"q": "Q", "w": "W", "e": "E", "r": "R"}


def _ph(ui, parent, size):
    return ctk.CTkFrame(parent, width=size, height=size, corner_radius=6, fg_color=PAL["card2"], border_width=1, border_color=PAL["border"])


VIEWS = ["Más usada", "Variantes", "Situaciones"]


def build_panel(ui, parent, cid, lane, enemy=None, width=520, ens=None):
    """Devuelve un contenedor que se rellena solo cuando llegan los datos (sin bloquear la ventana).
    `ens`: composición del equipo rival (comp_stats) para marcar qué situaciones aplican ahora."""
    box = ui.frame(parent)
    champs = ui.champs
    key = builds.request(core.CACHE, champs[cid], lane, champs[enemy] if enemy else None)
    content = ui.frame(box)
    content.pack(fill="x")
    state = {"n": 0, "m": 0, "view": VIEWS[0]}

    def again():
        """Vuelve a pintar mientras llega la segunda fuente (op.gg), sin bloquear la ventana."""
        if state["m"] < 40 and box.winfo_exists():
            state["m"] += 1
            box.after(900, paint)

    def setv(v):
        state["view"] = v
        paint()

    def paint():
        if not box.winfo_exists():
            return
        st = builds.peek(key)
        ui.clear(content)
        if st[0] == "loading":
            ui.lbl(content, "Cargando la build…", 10, "dim").pack(anchor="w", pady=4)
            state["n"] += 1
            if state["n"] < 90:
                box.after(400, paint)
        elif st[0] == "error":
            ui.lbl(content, st[1], 10, "dim", anchor="w", justify="left", wraplength=max(200, width - 40)).pack(anchor="w", pady=4)
        else:
            d = st[1]
            rich = bool(d.get("stats") or d.get("palette"))
            cols = 3 if width >= 1500 else 2 if width >= 960 else 1
            if rich and cols > 1:
                # cabe en el ancho: se ven todas las vistas a la vez, en columnas
                grid = ui.frame(content)
                grid.pack(fill="x")
                cw = int((width - 28 * (cols - 1)) / cols)
                slots = []
                for k in range(cols):
                    s_ = ui.frame(grid)
                    s_.grid(row=0, column=k, sticky="nw", padx=(0 if k == 0 else 14, 0))
                    grid.columnconfigure(k, weight=1, uniform="bp")
                    slots.append(s_)
                render(ui, slots[0], d, champs, cid, enemy, cw, lane)
                if d.get("stats"):
                    variants(ui, slots[1], d, champs, cid, cw, lane, again)
                situations(ui, slots[2] if cols == 3 else slots[0], d, champs, ens, cw)
                return
            width1 = min(width, 720)
            if rich:
                ui.seg(content, VIEWS, state["view"], setv, height=26).pack(fill="x", pady=(0, 8))
            if state["view"] == "Variantes" and d.get("stats"):
                variants(ui, content, d, champs, cid, width1, lane, again)
            elif state["view"] == "Situaciones":
                situations(ui, content, d, champs, ens, width1)
            else:
                render(ui, content, d, champs, cid, enemy, width1, lane)
    paint()
    return box


def _row(ui, parent, label):
    row = ui.frame(parent)
    row.pack(fill="x", pady=3)
    ui.lbl(row, label.upper(), 9, "dim", True, width=84, anchor="w").pack(side="left", anchor="n", pady=(4, 0))
    body = ui.frame(row)
    body.pack(side="left", fill="x", expand=True)
    return body


def is_boots(ui, iid):
    return "Boots" in (ui.items.get(iid) or {}).get("t", [])


def tier3(ui, iid):
    """Botas de nivel 3 a las que mejoran unas botas de nivel 2 (Data Dragon), o None."""
    for nxt in (ui.items.get(iid) or {}).get("into", []):
        if "Boots" in (ui.items.get(nxt) or {}).get("t", []):
            return nxt
    return None


def item_tip(ui, iid):
    info = ui.items.get(iid)
    if not info:
        return ""
    extra = ""
    t = info.get("t", [])
    if "Boots" in t:
        n3 = tier3(ui, iid)
        extra = "\nBotas de nivel 2" + (f": mejoran a {ui.items[n3]['n']} ({ui.items[n3]['g']} de oro)" if n3 else "")
    elif "Jungle" in t and info.get("depth") is None:
        extra = "\nObjeto de jungla: evoluciona al completar su misión"
    elif "GoldPer" in t and "Lane" in t:
        extra = "\nObjeto de apoyo: evoluciona al completar su misión"
    return f"{info['n']}  ·  {info['g']} de oro" + (f"\n{info['d']}" if info["d"] else "") + extra


# Misión de rol (parche 26.1, fuentes públicas secundarias: conviene confirmarlo en las notas oficiales del parche)
ROLE_QUEST = {
    "bottom": "Misión de rol: las botas pasan a la ranura de la misión y no ocupan uno de los objetos (7.ª ranura).",
    "middle": "Misión de rol: al completarla, tus botas de nivel 2 se mejoran gratis a nivel 3 (y si no las tienes, al comprarlas).",
    "top": "Misión de rol: la recompensa de la línea superior se describe como nivel máximo 20 y, según algunas fuentes, un Teletransporte "
           "si no lo llevas. Sin confirmar oficialmente.",
    "jungle": "Misión de rol: al completarla, más oro y experiencia y más velocidad de movimiento en la jungla.",
    "support": "Misión de rol: tras completarla, las Balizas de control cuestan menos y se guardan en la ranura de la misión (hasta 2).",
}


def _item(ui, parent, iid, size=30):
    ph = ui.item_photo(iid, size) if iid else None
    if ph is not None:
        lab = tk.Label(parent, image=ph, bd=0, highlightthickness=0, bg=ui.bg(parent))
        lab.image = ph
        if ui.items.get(iid):
            ui.tip(lab, item_tip(ui, iid))
    else:
        lab = tk.Frame(parent, width=int(size * ui.scale_px()), height=int(size * ui.scale_px()), bg=ui.hexm(PAL["card2"]))
    lab.pack(side="left", padx=2)
    return lab


def pct_txt(o):
    return f"{o['wr']:.1f} %".replace(".", ",") + f" · {o['games']:,}".replace(",", ".") + " partidas"


def _chain(ui, parent, ids, notes=None):
    """Una fila de objetos unidos con «›»; el globo de cada uno dice su porcentaje si se conoce."""
    for n, i in enumerate(ids):
        if n:
            ui.lbl(parent, "›", 13, "dim").pack(side="left")
        lab = _item(ui, parent, i)
        if notes and notes.get(i) and hasattr(lab, "winfo_exists"):
            try:
                ui.tip(lab, item_tip(ui, i) + "\n" + notes[i])
            except Exception:
                pass


def other_source(ui, parent, d, champs, cid, width, lane, again):
    """Builds de op.gg junto a las de Lolalytics: cada web calcula con su muestra, y ver las dos enseña en qué hay acuerdo."""
    ui.lbl(parent, "SEGUNDA OPINIÓN · OP.GG", 10, "dim", True, anchor="w").pack(anchor="w", pady=(14, 4))
    key = opgg_builds.request(core.CACHE, champs[cid], lane)
    st = opgg_builds.peek(key)
    if st[0] == "loading":
        ui.lbl(parent, "Consultando op.gg…", 10, "dim").pack(anchor="w")
        again()
        return
    if st[0] == "error":
        ui.lbl(parent, st[1], 10, "dim", anchor="w", justify="left", wraplength=max(240, width - 60)).pack(anchor="w")
        return
    o = st[1]
    txt = lambda r: f"{r['pr']:.1f} % de uso".replace(".", ",") + f" · {r['wr']:.1f} % victorias".replace(".", ",") + f" · {r['games']:,}".replace(",", ".") + " partidas"
    mine = set((d.get("items") or {}).get("core") or [])
    for n, r in enumerate(o["core"][:3], 1):
        row = _row(ui, parent, f"Núcleo {n}")
        line = ui.frame(row)
        line.pack(anchor="w")
        _chain(ui, line, r["items"])
        ui.lbl(row, txt(r), 9, "dim", anchor="w").pack(anchor="w")
    top = set(o["core"][0]["items"])
    same = len(top & mine)
    nboots = sum(1 for i in mine if is_boots(ui, i))
    ui.lbl(parent, f"Su núcleo más usado comparte {same} de {len(top)} objetos con el de Lolalytics" + ("." if same < len(top) else ": coinciden."),
           9, "good" if same == len(top) else "dim", anchor="w").pack(anchor="w", pady=(2, 4))
    if o.get("boots"):
        b = _row(ui, parent, "Botas")
        for n, r in enumerate(o["boots"][:3]):
            cell = ui.frame(b)
            cell.pack(side="left", padx=(0, 14))
            _item(ui, cell, r["id"])
            ui.lbl(cell, f"{r['pr']:.0f} % · {r['wr']:.1f} %".replace(".", ","), 9, "dim").pack(side="left")
    if o.get("starters"):
        b = _row(ui, parent, "Inicio")
        for r in o["starters"][:2]:
            cell = ui.frame(b)
            cell.pack(side="left", padx=(0, 14))
            for i in r["items"]:
                _item(ui, cell, i)
            ui.lbl(cell, f"{r['pr']:.0f} % · {r['wr']:.1f} %".replace(".", ","), 9, "dim").pack(side="left")
    if o.get("skills"):
        b = _row(ui, parent, "Habilidades")
        ui.lbl(b, " > ".join(o["skills"]) + "  (orden de subida más jugado según op.gg; la R siempre que puedas)", 10, "fg", anchor="w").pack(anchor="w")
    ui.lbl(parent, "Los porcentajes de uso y victorias de cada web salen de su propia muestra y su filtro de rango; compara el orden, no las cifras. "
                   "LeagueOfGraphs no se consulta: bloquea las lecturas automáticas.", 9, "dim", anchor="w", justify="left",
           wraplength=max(240, width - 60)).pack(anchor="w", pady=(6, 0))


def variants(ui, parent, d, champs, cid, width, lane=None, again=None):
    """Builds completas para elegir según cómo vaya la partida, y las opciones de cada hueco con su porcentaje."""
    it, st = d.get("items") or {}, d.get("stats") or {}
    core = [i for i in (it.get("core") or []) if not is_boots(ui, i)]
    boots = next((i for k in ("core", "i4", "i5", "i6") for i in (it.get(k) or []) if is_boots(ui, i)), None)
    opts = {k: [o for o in (st.get(k) or []) if not is_boots(ui, o["id"])] for k in ("i4", "i5", "i6")}
    notes = {o["id"]: pct_txt(o) for k in opts for o in opts[k]}

    def pick(key):
        """Un objeto por hueco: el mejor según `key`, sin repetir los ya elegidos."""
        used, out = set(core), []
        for k in ("i4", "i5", "i6"):
            cand = [o for o in opts[k] if o["id"] not in used]
            if not cand:
                continue
            o = max(cand, key=key)
            used.add(o["id"])
            out.append(o["id"])
        return out
    a = core + pick(lambda o: o["games"])
    b = core + pick(lambda o: (o["games"] >= 30, o["wr"]))
    ui.lbl(parent, "BUILDS COMPLETAS", 10, "dim", True, anchor="w").pack(anchor="w", pady=(0, 4))
    shown = [("Más jugada", a)] + ([("Mayor % de victorias", b)] if b != a else [])
    for label, ids in shown:
        row = ui.frame(parent)
        row.pack(fill="x", pady=3)
        ui.lbl(row, label.upper(), 9, "dim", True, width=110, anchor="w").pack(side="left", anchor="n", pady=(6, 0))
        body = ui.frame(row)
        body.pack(side="left", fill="x", expand=True)
        line = ui.frame(body)
        line.pack(anchor="w")
        _chain(ui, line, ids, notes)
        gold = sum((ui.items.get(i) or {}).get("g", 0) for i in ids)
        ui.lbl(body, f"{gold:,}".replace(",", ".") + " de oro en total" + (f"  ·  botas: {ui.items[boots]['n']}" if boots and boots in ui.items else ""),
               9, "dim", anchor="w").pack(anchor="w")
    if len(shown) == 1:
        ui.lbl(parent, "La build más jugada es también la de mayor porcentaje de victorias.", 9, "dim", anchor="w").pack(anchor="w")
    ui.lbl(parent, "OPCIONES EN CADA HUECO", 10, "dim", True, anchor="w").pack(anchor="w", pady=(12, 4))
    if st.get("start"):
        b0 = _row(ui, parent, "Inicio")
        for i in it.get("start") or []:
            _item(ui, b0, i)
        ui.lbl(b0, "  " + pct_txt(st["start"]), 9, "dim").pack(side="left")
    if st.get("core"):
        b0 = _row(ui, parent, "Núcleo")
        _chain(ui, b0, core)
        ui.lbl(b0, "  " + pct_txt(st["core"]), 9, "dim").pack(side="left")
    for k, label in (("i4", "4.º objeto"), ("i5", "5.º objeto"), ("i6", "6.º objeto")):
        if not opts[k]:
            continue
        b0 = _row(ui, parent, label)
        for n, o in enumerate(sorted(opts[k], key=lambda o: -o["games"])[:3]):
            cell = ui.frame(b0)
            cell.pack(side="left", padx=(0, 14))
            _item(ui, cell, o["id"])
            ui.lbl(cell, pct_txt(o), 9, "dim").pack(side="left")
    ui.lbl(parent, "Los porcentajes de los objetos tardíos salen algo inflados: solo los compran las partidas que duran lo suficiente, y esas "
                   "se ganan más. Úsalos para comparar opciones entre sí, no como probabilidad de ganar. Fuente: Lolalytics.",
           9, "dim", anchor="w", justify="left", wraplength=max(240, width - 60)).pack(anchor="w", pady=(8, 0))
    if lane and again:
        other_source(ui, parent, d, champs, cid, width, lane, again)


SITUATIONS = [
    ("Mucho daño físico rival", "armadura", lambda i: "Armor" in i["t"], lambda e: e and e["ad"] >= 3 and e["ap"] <= 1),
    ("Mucho daño mágico rival", "resistencia mágica", lambda i: "SpellBlock" in i["t"], lambda e: e and e["ap"] >= 3 and e["ad"] <= 1),
    ("Rivales con curación o regeneración", "heridas graves", lambda i: "antiheal" in i.get("x", []), lambda e: None),
    ("Mucho control rival", "tenacidad o resistencia", lambda i: "tenacidad" in i.get("x", []) or "Tenacity" in i["t"], lambda e: e and e["cc"] >= 2.3),
    ("Rivales con mucha vida (tanques)", "daño porcentual o penetración", lambda i: "vidamax" in i.get("x", []) or "penarm" in i.get("x", []) or "penmag" in i.get("x", []),
     lambda e: e and e["tanks"] >= 2),
    ("Si vas por delante", "más daño", lambda i: "Damage" in i["t"] or "SpellDamage" in i["t"] or "CriticalStrike" in i["t"], lambda e: None),
    ("Si vas por detrás", "aguantar más", lambda i: "Health" in i["t"] and ("Armor" in i["t"] or "SpellBlock" in i["t"]), lambda e: None),
]


def situations(ui, parent, d, champs, ens, width):
    """Objetos sueltos para cada situación, elegidos entre los que más se compran con este campeón (cantera de Lolalytics)."""
    pool = []
    for i in list(d.get("palette") or []) + [o["id"] for k in ("i4", "i5", "i6") for o in (d.get("stats") or {}).get(k, [])]:
        info = ui.items.get(i)
        if i not in pool and info and not info.get("into") and info["g"] >= 1000 and "Boots" not in info["t"] and "Consumable" not in info["t"]:
            pool.append(i)
    ui.lbl(parent, "SEGÚN LA SITUACIÓN", 10, "dim", True, anchor="w").pack(anchor="w", pady=(16, 2))
    if ens:
        ui.lbl(parent, f"Equipo rival ahora: {ens['ad']} de daño físico, {ens['ap']} de mágico, {ens['tanks']} tanques, control {ens['cc']:.1f}/3.",
               9, "dim", anchor="w").pack(anchor="w", pady=(0, 6))
    n = 0
    for title, what, test, now in SITUATIONS:
        found = [i for i in pool if test(ui.items[i])][:5]
        if not found:
            continue
        n += 1
        row = ui.frame(parent)
        row.pack(fill="x", pady=4)
        head = ui.frame(row)
        head.pack(fill="x")
        ui.lbl(head, title, 12, "fg", True, anchor="w").pack(side="left")
        ui.lbl(head, f"  ·  {what}", 10, "dim").pack(side="left")
        if now(ens):
            ui.chip(head, "aplica ahora", "good").pack(side="left", padx=(8, 0))
        line = ui.frame(row)
        line.pack(anchor="w", pady=(3, 0))
        for i in found:
            _item(ui, line, i, 32)
    if not n:
        ui.lbl(parent, "Aún no hay datos para sugerir objetos por situación.", 10, "dim").pack(anchor="w")
    ui.lbl(parent, "Elegidos entre los objetos que más se compran con este campeón, según sus etiquetas y su descripción oficial. Orientativo: "
                   "no sustituyen a leer la partida.", 9, "dim", anchor="w", justify="left", wraplength=max(240, width - 60)).pack(anchor="w", pady=(8, 0))


def render(ui, parent, d, champs, cid, enemy, width, lane=None):
    rd = ui.runedata or {}
    title = f"BUILD MÁS USADA DE {champs[cid]['name'].upper()}" + (f" CONTRA {champs[enemy]['name'].upper()}" if d.get("vs") and enemy else "")
    ui.lbl(parent, title, 10, "dim", True, anchor="w").pack(anchor="w", pady=(0, 4))
    # hechizos
    sp = d.get("spells") or []
    if sp:
        b = _row(ui, parent, "Hechizos")
        for sid in sp:
            img = ui.spell_icon(sid, 28)
            lab = ctk.CTkLabel(b, image=img, text="", width=28, height=28) if img is not None else _ph(ui, b, 28)
            info = (rd.get("spells") or {}).get(sid)
            if info:
                ui.tip(lab, info["n"])
            lab.pack(side="left", padx=2)
        names = [(rd.get("spells") or {}).get(s, {}).get("n") for s in sp]
        if all(names):
            ui.lbl(b, "  " + " + ".join(names), 11, "fg").pack(side="left")
    # runas
    rn = d["runes"]
    b = _row(ui, parent, "Runas")
    line = ui.frame(b)
    line.pack(anchor="w")
    groups = [([rn["keystone"]], 38), (rn.get("primary") or [], 26), (rn.get("secondary") or [], 26)]
    for gi, (ids, size) in enumerate(groups):
        if gi:
            ui.lbl(line, "│", 12, "dim").pack(side="left", padx=4)
        for rid in ids:
            img = ui.rune_icon(rid, size)
            lab = ctk.CTkLabel(line, image=img, text="", width=size, height=size) if img is not None else _ph(ui, line, size)
            info = (rd.get("runes") or {}).get(rid)
            if info:
                ui.tip(lab, f"{info['n']}\n{info['d']}" if info["d"] else info["n"])
            lab.pack(side="left", padx=2)
    if rn.get("shards"):
        ui.lbl(line, "│", 12, "dim").pack(side="left", padx=4)
        for sid in rn["shards"]:
            img = ui.shard_icon(sid, 22)
            lab = ctk.CTkLabel(line, image=img, text="", width=22, height=22) if img is not None else _ph(ui, line, 22)
            nm = runemod.SHARDS.get(sid)
            if nm:
                ui.tip(lab, f"{nm[0]}\n{nm[1]}")
            lab.pack(side="left", padx=2)
    kn = (rd.get("runes") or {}).get(rn["keystone"], {}).get("n")
    sec_tree = (rd.get("runes") or {}).get((rn.get("secondary") or [0])[0], {}).get("t")
    tree = (rd.get("trees") or {}).get((rd.get("runes") or {}).get(rn["keystone"], {}).get("t"))
    if kn:
        txt = f"{kn}" + (f" ({tree})" if tree else "") + (f"  +  {(rd.get('trees') or {}).get(sec_tree)}" if sec_tree else "")
        ui.lbl(b, txt, 10, "dim", anchor="w", wraplength=max(200, width - 140), justify="left").pack(anchor="w", pady=(3, 0))
    if d.get("skills"):
        b = _row(ui, parent, "Habilidades")
        ui.lbl(b, "  ›  ".join(SKILLS[s] for s in d["skills"]), 12, ui.acc, True, True).pack(side="left")
        ui.lbl(b, "   prioridad para subirlas (la R siempre que puedas)", 9, "dim").pack(side="left")
    # objetos: las botas van aparte (en la Grieta tienen su propia mejora y, en tirador, su propia ranura)
    it = d.get("items") or {}
    boots = [i for k in ("core", "i4", "i5", "i6") for i in (it.get(k) or []) if is_boots(ui, i)]
    boots = list(dict.fromkeys(boots))
    if it.get("start"):
        b = _row(ui, parent, "Inicio")
        for i in it["start"]:
            _item(ui, b, i)
    if boots:
        b = _row(ui, parent, "Botas")
        for n, i in enumerate(boots[:2]):
            if n:
                ui.lbl(b, "o", 10, "dim").pack(side="left", padx=2)
            _item(ui, b, i)
            n3 = tier3(ui, i)
            if n3:
                ui.lbl(b, "→", 12, "dim").pack(side="left", padx=(2, 0))
                _item(ui, b, n3)
        ui.lbl(b, "  nivel 2 → nivel 3", 9, "dim").pack(side="left")
    core = [i for i in (it.get("core") or []) if not is_boots(ui, i)]
    if core:
        b = _row(ui, parent, "Núcleo")
        for n, i in enumerate(core):
            if n:
                ui.lbl(b, "›", 13, "dim").pack(side="left")
            _item(ui, b, i)
    for k, label in (("i4", "Siguiente"), ("i5", "Después"), ("i6", "Al final")):
        opts = [i for i in (it.get(k) or []) if not is_boots(ui, i)]
        if opts:
            b = _row(ui, parent, label)
            for n, i in enumerate(opts[:3]):
                if n:
                    ui.lbl(b, "o", 10, "dim").pack(side="left", padx=2)
                _item(ui, b, i)
    notes = []
    quest = ROLE_QUEST.get(lane)
    if quest:
        ui.lbl(parent, quest, 9, "dim", anchor="w", justify="left", wraplength=max(200, width - 20)).pack(anchor="w", pady=(8, 0))
    if d.get("vs_missing"):
        notes.append("Sin datos suficientes de este enfrentamiento: se muestra la build general de la línea.")
    if d.get("tier") == "all":
        notes.append("Pocos datos en tu rango: se usan los de todos los rangos.")
    notes.append("Fuente: Lolalytics (build más jugada). Pasa el ratón por un icono para ver su descripción.")
    ui.lbl(parent, " ".join(notes), 9, "dim", anchor="w", justify="left", wraplength=max(200, width - 20)).pack(anchor="w", pady=(6, 0))
