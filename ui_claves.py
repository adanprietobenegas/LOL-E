"""Bloque «Claves de <campeón>» (plegable): evoluciones, acumulaciones, formas y avisos de objetos. Datos y avisos de parche en claves.py."""
import claves
import lol_advisor as core


def block(ui, parent, cid, width):
    """Dibuja el bloque en `parent`; no hace nada si el campeón no tiene claves."""
    key = (ui.champs.get(cid) or {}).get("icon")
    items = claves.for_champ(key)
    if not items:
        return
    from ui_vs import collapsible
    nm = core.name(cid, ui.champs)
    kinds = [claves.TIPOS[t][0].capitalize() for t in dict.fromkeys(t for t, _ in items) if t in claves.TIPOS]
    summ = f"{len(items)} claves · " + ", ".join(kinds[:3]).lower()

    def fill(c):
        for tipo, texto in items:
            lab, color = claves.TIPOS.get(tipo, ("CLAVE", "dim"))
            row = ui.frame(c)
            row.pack(fill="x", pady=2)
            ui.lbl(row, lab, 9, color, True, width=88, anchor="w").pack(side="left", anchor="n", pady=(4, 0))
            ui.lbl(row, texto, 11, "fg", anchor="w", justify="left", wraplength=max(220, width - 88 - 40)).pack(side="left", fill="x", expand=True)
        cur = claves.stale(core.DD_VERSION)
        ver = claves.load().get("patch", "")
        if cur:
            note, tone = f"Verificado en el parche {ver}; el actual es el {cur}: puede haber cambiado, compruébalo.", "warn"
        else:
            note, tone = f"Verificado en el parche {ver} con notas de Riot, Data Dragon y Lolalytics.", "dim"
        ui.lbl(c, note, 9, tone, anchor="w").pack(anchor="w", pady=(4, 0))
    collapsible(ui, parent, f"Claves de {nm}", summ, "claves_campeon", fill)
