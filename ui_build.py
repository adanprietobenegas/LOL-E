"""Panel de build: runas, hechizos, objetos y habilidades más usados (Lolalytics), con iconos y descripción al pasar el ratón."""
import tkinter as tk

import customtkinter as ctk

import builds
import opgg_builds
import lol_advisor as core
import runes as runemod
import shopping
from ui_kit import PAL, ctl, ON_FILL

CACHE_DIR = core.CACHE   # (en render() «core» es una lista de objetos)

SKILLS = {"q": "Q", "w": "W", "e": "E", "r": "R"}


def current_patch():
    """Parche del juego instalado, con la numeración pública (26.22). A nivel de módulo porque en render() «core» es otra cosa."""
    return core.metamod.public_patch(core.DD_VERSION) if core.DD_VERSION else ""


def source_note(d, current="", now=None):
    """Nota de procedencia de una build: la fuente, el parche de sus datos y cuándo se leyeron. Si el parche es anterior al
    que tiene el juego, lo dice (cuando cambia el parche, la web tarda en tener datos nuevos). Sin parche no inventa ninguno."""
    import time as _t
    now = now or _t.time()
    partes = []
    if d.get("patch"):
        partes.append(f"parche {d['patch']}")
    if d.get("read"):
        dias = int((now - d["read"]) // 86400)
        partes.append("leída hoy" if dias <= 0 else "leída ayer" if dias == 1 else f"leída hace {dias} días")
    txt = "Fuente: Lolalytics (build más jugada" + (", " + ", ".join(partes) if partes else "") + ")."
    if d.get("stale"):
        txt += " No se pudo actualizar ahora: son los últimos datos guardados."
    if d.get("patch") and current and d["patch"] != current:
        txt += f" Es de un parche anterior al actual ({current}): puede haber cambiado."
    return txt


def _ph(ui, parent, size):
    return ctk.CTkFrame(parent, width=size, height=size, corner_radius=6, fg_color=PAL["card2"], border_width=1, border_color=PAL["border"])


VIEWS = ["Más usada", "Variantes", "Situaciones"]


_VIEW = {}


def build_panel(ui, parent, cid, lane, enemy=None, width=520, ens=None):
    """Devuelve un contenedor que se rellena solo cuando llegan los datos (sin bloquear la ventana).
    `ens`: composición del equipo rival (comp_stats) para marcar qué situaciones aplican ahora."""
    box = ui.frame(parent)
    champs = ui.champs
    key = builds.request(core.CACHE, champs[cid], lane, champs[enemy] if enemy else None)
    content = ui.frame(box)
    content.pack(fill="x")
    # la vista elegida se recuerda por campeón y línea: en la selección el panel se reconstruye con cada pick y volvía a "Más usada"
    state = {"n": 0, "m": 0, "view": _VIEW.get((cid, lane), VIEWS[0])}

    def again():
        """Vuelve a pintar mientras llega la segunda fuente (op.gg), sin bloquear la ventana."""
        if state["m"] < 40 and box.winfo_exists():
            state["m"] += 1
            box.after(900, paint)

    def setv(v):
        state["view"] = _VIEW[(cid, lane)] = v
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
                render(ui, slots[0], d, champs, cid, enemy, cw, lane, again)
                if d.get("stats"):
                    variants(ui, slots[1], d, champs, cid, cw, lane, again)
                situations(ui, slots[2] if cols == 3 else slots[0], d, champs, ens, cw)
                export_row(ui, content, d, champs, cid, enemy, lane, build_blocks(ui, d, cid, lane, ens))
                return
            width1 = min(width, 720)
            if rich:
                ui.seg(content, VIEWS, state["view"], setv, height=26).pack(fill="x", pady=(0, 8))
            if state["view"] == "Variantes" and d.get("stats"):
                variants(ui, content, d, champs, cid, width1, lane, again)
            elif state["view"] == "Situaciones":
                situations(ui, content, d, champs, ens, width1)
            else:
                render(ui, content, d, champs, cid, enemy, width1, lane, again)
            export_row(ui, content, d, champs, cid, enemy, lane, build_blocks(ui, d, cid, lane, ens))
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


def slot_labels(ui, it):
    """Rótulos de los huecos 4/5/6 de Lolalytics contando solo objetos completos: allí las botas ocupan un hueco,
    así que si van entre los principales (o en un hueco anterior) el «4.º» de la web es en realidad el 3.º objeto."""
    boots_seen = any(is_boots(ui, i) for i in (it.get("core") or []))
    out = {}
    for raw, k in ((4, "i4"), (5, "i5"), (6, "i6")):
        opts = it.get(k) or []
        if not boots_seen and opts and is_boots(ui, opts[0]):
            out[k] = "Con las botas"  # este hueco suele ser las botas: lo que no son botas se compra a la vez
            boots_seen = True
            continue
        out[k] = f"{raw - (1 if boots_seen else 0)}.º objeto"
    return out


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
    ui.lbl(parent, "SEGÚN OP.GG", 10, "dim", True, anchor="w").pack(anchor="w", pady=(14, 4))
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
        row = _row(ui, parent, f"Principal {n}")
        line = ui.frame(row)
        line.pack(anchor="w")
        _chain(ui, line, r["items"])
        ui.lbl(row, txt(r), 9, "dim", anchor="w").pack(anchor="w")
    top = set(o["core"][0]["items"])
    same = len(top & mine)
    nboots = sum(1 for i in mine if is_boots(ui, i))
    ui.lbl(parent, f"Sus objetos principales más usados comparten {same} de {len(top)} con los de Lolalytics" + ("." if same < len(top) else ": coinciden."),
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
    shown = [("Más jugada", a)] + ([("Más victorias", b)] if b != a else [])
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
    ui.lbl(parent, "ALTERNATIVAS POR OBJETO", 10, "dim", True, anchor="w").pack(anchor="w", pady=(12, 4))
    if st.get("start"):
        b0 = _row(ui, parent, "Inicio")
        for i in it.get("start") or []:
            _item(ui, b0, i)
        ui.lbl(b0, "  " + pct_txt(st["start"]), 9, "dim").pack(side="left")
    if st.get("core"):
        b0 = _row(ui, parent, "Principales")
        _chain(ui, b0, core)
        ui.lbl(b0, "  " + pct_txt(st["core"]), 9, "dim").pack(side="left")
    for k, label in slot_labels(ui, it).items():
        if not opts[k]:
            continue
        b0 = _row(ui, parent, label)
        for n, o in enumerate(sorted(opts[k], key=lambda o: -o["games"])[:3 if width >= 520 else 2]):   # en estrecho la tercera opción salía cortada
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
    pool = shopping.candidate_pool(ui.items, d)
    ui.lbl(parent, "SEGÚN LA SITUACIÓN", 10, "dim", True, anchor="w").pack(anchor="w", pady=(16, 2))
    if ens:
        ui.lbl(parent, f"Equipo rival ahora: {ens['ad']} de daño físico, {ens['ap']} de mágico, {ens['tanks']} {'tanque' if ens['tanks'] == 1 else 'tanques'}, control {ctl(ens['cc'])}.",
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
            ui.chip(head, "recomendado ahora", "good").pack(side="left", padx=(8, 0))
        line = ui.frame(row)
        line.pack(anchor="w", pady=(3, 0))
        for i in found:
            _item(ui, line, i, 32)
    if not n:
        ui.lbl(parent, "Aún no hay datos para sugerir objetos por situación.", 10, "dim").pack(anchor="w")
    ui.lbl(parent, "Elegidos entre los objetos que más se compran con este campeón, según sus etiquetas y su descripción oficial. Orientativo: "
                   "no sustituyen a leer la partida.", 9, "dim", anchor="w", justify="left", wraplength=max(240, width - 60)).pack(anchor="w", pady=(8, 0))


def build_blocks(ui, d, cid, lane, ens):
    """Bloques del conjunto de objetos: lo principal y, debajo, variantes y objetos por situación (los de «recomendado ahora» primero)."""
    it, st = d.get("items") or {}, d.get("stats") or {}
    nb = lambda ids: [i for i in ids if not is_boots(ui, i)]
    blocks = []
    if it.get("start"):
        blocks.append(("Inicio", list(it["start"])))
    boots = list(dict.fromkeys(i for k in ("core", "i4", "i5", "i6") for i in (it.get(k) or []) if is_boots(ui, i)))
    if boots:
        blocks.append(("Botas", [x for i in boots[:2] for x in (i, tier3(ui, i)) if x]))
    elif lane:
        ost = opgg_builds.peek(opgg_builds.request(CACHE_DIR, ui.champs[cid], lane))
        if ost[0] == "ok" and ost[1].get("boots"):
            blocks.append(("Botas", [x for r in ost[1]["boots"][:2] for x in (r["id"], tier3(ui, r["id"])) if x]))
    mainl = nb(it.get("core") or [])
    if mainl:
        blocks.append(("Principales (en este orden)", mainl))
    used = set(mainl)
    for k, label in slot_labels(ui, it).items():
        opts = nb(it.get(k) or [])[:3]
        if opts:
            blocks.append((label + " (a elegir)", opts))
            used.update(opts)
    # variante: lo más ganador de cada hueco, si añade algo distinto
    win = []
    for k in ("i4", "i5", "i6"):
        cand = [o for o in st.get(k, []) if not is_boots(ui, o["id"]) and o["id"] not in used and o["games"] >= 30]
        if cand:
            win.append(max(cand, key=lambda o: o["wr"])["id"])
    if win:
        blocks.append(("Variante: más victorias", win))
        used.update(win)
    # situaciones
    pool = shopping.candidate_pool(ui.items, d)
    sit = []
    for title, what, test, now in SITUATIONS:
        found = [i for i in pool if test(ui.items[i])][:4]
        if found:
            hot = bool(now(ens))
            sit.append((not hot, (("★ " if hot else "") + (title if title.startswith("Si ") else f"Si: {title.lower()}") + f" ({what})"), found))
    for _, name, found in sorted(sit, key=lambda x: x[0]):
        blocks.append((name, found))
    return blocks


_SENT = {}  # (uid, contenido) -> True: lo que ya se envió solo, para no repetirlo en cada repintado


def export_row(ui, parent, d, champs, cid, enemy, lane, blocks):
    """Botón «Enviar al cliente» (y envío automático opcional): crea en League un conjunto de objetos propio con esta build."""
    import itemset
    import matchups
    if not blocks:
        return
    name = champs[cid]["name"]
    vs = d.get("vs") and enemy and enemy in champs
    uid = f"{itemset.PREFIX}{cid}-{lane or 'x'}"
    title = f"LOL-E · {name}" + (f" · {matchups.LANE_NAMES.get(lane, '')}" if lane else "") + (f" vs {champs[enemy]['name']}" if vs else "")
    row = ui.frame(parent)
    row.pack(fill="x", pady=(10, 0))
    res = {}
    msg = ui.lbl(row, "", 10, "dim", anchor="w", justify="left", wraplength=360)

    def poll():
        if not row.winfo_exists():
            return
        if res.get("state") == "sending":
            row.after(300, poll)
            return
        if res.get("state") == "done":
            msg.configure(text=res["msg"])
            btn.configure(state="normal")

    def go():
        btn.configure(state="disabled")
        msg.configure(text="Enviando al cliente…")
        itemset.send_async(ui.conf, uid, title, cid, blocks, res, champs[cid].get("icon"))
        row.after(300, poll)

    btn = ctk.CTkButton(row, text="Enviar al cliente", height=28, width=140, corner_radius=8, font=ui.font(11, True), fg_color=ui.acc,
                        text_color=ON_FILL, command=go)
    btn.pack(side="left", padx=(0, 10))
    msg.pack(side="left", fill="x", expand=True)
    var = ctk.BooleanVar(value=bool(ui.conf.get("auto_itemset")))

    def toggle():
        ui.conf["auto_itemset"] = bool(var.get())
        core.save_conf(ui.conf)
        if var.get():
            go_auto()
    sw = ctk.CTkSwitch(parent, text="Enviar siempre al elegir campeón", variable=var, font=ui.font(10), progress_color=ui.acc, command=toggle)
    sw.pack(anchor="w", pady=(6, 0))
    ui.autowrap(ui.lbl(parent, "Crea un conjunto de objetos propio en tu cliente de League («LOL-E · campeón · línea»), y lo copia a la carpeta del juego. "
                   "El juego lo lee al EMPEZAR la partida: envíalo durante la selección de campeón (o activa el envío automático); si lo envías "
                   "con la partida ya cargada, aparecerá en la siguiente. "
                   "Solo se tocan los conjuntos de LOL-E; los tuyos no.", 9, "dim", anchor="w", justify="left", wraplength=400), parent).pack(anchor="w", pady=(4, 0))

    def go_auto():
        key = (uid, title, tuple((n, tuple(i)) for n, i in blocks))
        if not _SENT.get(key):
            _SENT[key] = True
            go()
    if ui.conf.get("auto_itemset"):
        row.after(400, go_auto)


def render(ui, parent, d, champs, cid, enemy, width, lane=None, again=None):
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
    elif lane and again is not None:
        # Lolalytics no puso botas entre los objetos de esta build (pasa en algunos campeones de jungla): se toman las más usadas de op.gg
        okey = opgg_builds.request(CACHE_DIR, champs[cid], lane)
        ost = opgg_builds.peek(okey)
        b = _row(ui, parent, "Botas")
        if ost[0] == "loading":
            ui.lbl(b, "Consultando op.gg…", 10, "dim").pack(side="left")
            again()
        elif ost[0] == "ok" and ost[1].get("boots"):
            for n, r in enumerate(ost[1]["boots"][:2]):
                if n:
                    ui.lbl(b, "o", 10, "dim").pack(side="left", padx=2)
                _item(ui, b, r["id"])
                n3 = tier3(ui, r["id"])
                if n3:
                    ui.lbl(b, "→", 12, "dim").pack(side="left", padx=(2, 0))
                    _item(ui, b, n3)
            ui.lbl(b, "  según op.gg (Lolalytics no las incluye en esta build)", 9, "dim").pack(side="left")
        else:
            ui.lbl(b, "Sin datos de botas para esta build.", 10, "dim").pack(side="left")
    core = [i for i in (it.get("core") or []) if not is_boots(ui, i)]
    if core:
        b = _row(ui, parent, "Principales")
        for n, i in enumerate(core):
            if n:
                ui.lbl(b, "›", 13, "dim").pack(side="left")
            _item(ui, b, i)
    for k, label in slot_labels(ui, it).items():
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
    notes.append(source_note(d, current_patch()) + " Pasa el ratón por un icono para ver su descripción.")
    ui.lbl(parent, " ".join(notes), 9, "dim", anchor="w", justify="left", wraplength=max(200, width - 20)).pack(anchor="w", pady=(6, 0))
