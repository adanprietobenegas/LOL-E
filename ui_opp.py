"""Selector de rival de línea: cuando no sabes contra quién vas (o quieres ver cómo te iría contra cada uno), eliges entre los campeones
rivales ya visibles y la build, las runas y la guía de juego se recalculan contra ese. «Auto» vuelve a lo que la app deduce de la selección.

Cada rival muestra el % de victorias de tu campeón contra él en tu línea (Lolalytics, página de tu campeón: una sola consulta para todos).
El rival de línea de los rivales NO lo da el cliente en todas las colas: por eso se puede corregir a mano, también durante la partida."""
import threading

import lol_advisor as core
import matchups

_ROWS = {}  # (campeón, línea) -> filas | "cargando" | ("error", texto)


def _rows(ui, cid, lane):
    key = (cid, lane)
    got = _ROWS.get(key)
    if got is None:
        _ROWS[key] = "cargando"

        def go():
            try:
                _ROWS[key] = matchups.load(core.CACHE, ui.champs[cid], lane)
            except Exception as e:
                _ROWS[key] = ("error", str(e))
        threading.Thread(target=go, daemon=True).start()
        return "cargando"
    return got


def wr_vs(ui, rows, opp):
    """% de victorias de tu campeón contra `opp` y partidas, o None si no hay datos."""
    if not isinstance(rows, list) or opp not in ui.champs:
        return None
    n = matchups.norm(ui.champs[opp]["name"])
    for r in rows:
        if matchups.norm(r["name"]) == n and r.get("games", 0) >= 20:
            return r["wr"], r["games"]
    return None


def picker(ui, parent, cid, lane, enemies, auto, chosen, on_pick, width=520):
    """Fila con una ficha por rival. `auto`: el rival que se deduce solo (0 si no se sabe); `chosen`: el elegido a mano (0 si ninguno);
    `on_pick(cid)`: se llama con el rival elegido, o con 0 para volver a «Auto»."""
    enemies = [e for e in dict.fromkeys(enemies) if e in ui.champs]
    if not enemies:
        return None
    box = ui.frame(parent)
    ui.lbl(box, "RIVAL DE LÍNEA", 9, "dim", True, anchor="w").pack(anchor="w")
    if chosen:
        state = f"Elegido por ti: {core.name(chosen, ui.champs)}. Pulsa «Auto» para volver a la detección."
    elif auto:
        state = f"Detectado: {core.name(auto, ui.champs)}. Si no es tu rival, elige otro."
    else:
        state = "Aún no se sabe contra quién vas. Elige uno para ver tu build, runas y guía contra él, y cámbialo cuando lo sepas."
    ui.lbl(box, state, 10, "dim", anchor="w", justify="left", wraplength=max(240, width - 40)).pack(anchor="w", pady=(2, 6))
    row = ui.frame(box)
    row.pack(anchor="w")
    tiles = []

    def tile(label_cid, title, selected, cb):
        import customtkinter as ctk
        t = ctk.CTkFrame(row, corner_radius=10, fg_color=core_color("well"), border_width=2,
                         border_color=core_color("acc", ui) if selected else core_color("edge"))
        t.pack(side="left", padx=(0, 6), pady=2)
        inner = ui.frame(t, fg_color="transparent")
        inner.pack(padx=7, pady=5)
        if label_cid:
            ui.champ(inner, label_cid, 34, False).pack()
        else:
            ui.lbl(inner, "AUTO", 11, ui.acc, True).pack(pady=(9, 9), padx=3)
        ui.lbl(inner, title, 10, "fg", selected).pack(pady=(2, 0))
        sub = ui.lbl(inner, "", 9, "dim")
        sub.pack()
        ui.clickable(t, cb)
        tiles.append((label_cid, sub))

    tile(0, "Auto", not chosen, lambda: on_pick(0))
    for e in enemies:
        tile(e, core.name(e, ui.champs)[:10], chosen == e, (lambda e=e: on_pick(e)))
    state_ = {"n": 0}

    def paint():
        if not box.winfo_exists():
            return
        rows = _rows(ui, cid, lane) if lane else ("error", "")
        for e, sub in tiles:
            if not e:
                sub.configure(text=core.name(auto, ui.champs)[:10] if auto else "sin datos")
                continue
            w = wr_vs(ui, rows, e)
            if w:
                sub.configure(text=f"{w[0]:.0f} %".replace(".", ",") if abs(w[0] - round(w[0])) < .05 else f"{w[0]:.1f} %".replace(".", ","),
                              fg=ui.hexm("good" if w[0] >= 52 else "bad" if w[0] <= 48 else "dim"))
            elif rows == "cargando":
                sub.configure(text="…")
            else:
                sub.configure(text="s/d")
        if rows == "cargando" and state_["n"] < 60:
            state_["n"] += 1
            box.after(500, paint)
    paint()
    ui.lbl(box, "El % es la tasa de victorias de tu campeón contra ese rival en tu línea (Lolalytics, todas las partidas). «s/d»: sin datos suficientes.",
           9, "dim", anchor="w", justify="left", wraplength=max(240, width - 40)).pack(anchor="w", pady=(2, 0))
    return box


def core_color(name, ui=None):
    from ui_kit import PAL
    if name == "acc":
        return ui.acc
    return PAL[name]
