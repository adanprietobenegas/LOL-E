"""Panel de build: runas, hechizos, objetos y habilidades más usados (Lolalytics), con iconos y descripción al pasar el ratón."""
import tkinter as tk

import customtkinter as ctk

import builds
import lol_advisor as core
import runes as runemod
from ui_kit import PAL

SKILLS = {"q": "Q", "w": "W", "e": "E", "r": "R"}


def _ph(ui, parent, size):
    return ctk.CTkFrame(parent, width=size, height=size, corner_radius=6, fg_color=PAL["card2"], border_width=1, border_color=PAL["border"])


def build_panel(ui, parent, cid, lane, enemy=None, width=520):
    """Devuelve un contenedor que se rellena solo cuando llegan los datos (sin bloquear la ventana)."""
    box = ui.frame(parent)
    champs = ui.champs
    key = builds.request(core.CACHE, champs[cid], lane, champs[enemy] if enemy else None)
    content = ui.frame(box)
    content.pack(fill="x")
    state = {"n": 0}

    def paint():
        if not box.winfo_exists():
            return
        st = builds.peek(key)
        for w in content.winfo_children():
            w.destroy()
        if st[0] == "loading":
            ui.lbl(content, "Cargando la build…", 10, "dim").pack(anchor="w", pady=4)
            state["n"] += 1
            if state["n"] < 90:
                box.after(400, paint)
        elif st[0] == "error":
            ui.lbl(content, st[1], 10, "dim", anchor="w", justify="left", wraplength=max(200, width - 40)).pack(anchor="w", pady=4)
        else:
            render(ui, content, st[1], champs, cid, enemy, width, lane)
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
    if d.get("skills"):
        b = _row(ui, parent, "Habilidades")
        ui.lbl(b, "  ›  ".join(SKILLS[s] for s in d["skills"]), 12, ui.acc, True, True).pack(side="left")
        ui.lbl(b, "   prioridad para subirlas (la R siempre que puedas)", 9, "dim").pack(side="left")
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
