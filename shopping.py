"""«Puedes comprar…»: con tu oro y lo que ya llevas, cuál es el siguiente objeto de tu build y cuánto te falta (teniendo en cuenta los
componentes que ya tienes). Sin red ni ventana: solo cuentas con el catálogo de objetos de Data Dragon (`items.load`).

El catálogo es {id: {"g": coste total, "t": etiquetas, "from": [componentes, con repetición]}}. El precio de montar un objeto con sus
componentes es su coste total menos lo que cuestan los componentes; lo que ya llevas de esa receta se resta una sola vez por unidad.
"""


def recipe_tree(iid, items, _seen=None):
    """Todos los objetos que forman `iid` (componentes y sub-componentes), sin él mismo."""
    out = set()
    for c in (items.get(iid) or {}).get("from") or []:
        if c not in out:
            out.add(c)
            out |= recipe_tree(c, items)
    return out


def remaining_cost(iid, items, inventory):
    """Oro que te falta para tener `iid` con lo que ya llevas. `inventory`: lista de ids (con repetición). Cada unidad que llevas cubre una
    sola vez su parte de la receta. Si `iid` no está en el catálogo devuelve None: no se inventa un precio."""
    if iid not in items:
        return None
    inv = {}
    for i in inventory:
        inv[i] = inv.get(i, 0) + 1

    def need(i):
        if inv.get(i, 0) > 0:
            inv[i] -= 1
            return 0
        it = items.get(i) or {}
        comps = it.get("from") or []
        total = int(it.get("g") or 0)
        if not comps:
            return total
        combinar = max(0, total - sum(int((items.get(c) or {}).get("g") or 0) for c in comps))
        return combinar + sum(need(c) for c in comps)
    return need(iid)


def build_order(items_build, is_boots):
    """Orden en el que se compra la build de la web: primer principal, botas, resto de principales y la primera opción de cada hueco
    siguiente. `items_build`: el diccionario «items» de builds.py ({start, core, i4, i5, i6}); `is_boots(id)` dice si es calzado."""
    core = [i for i in (items_build.get("core") or []) if not is_boots(i)]
    boots = next((i for k in ("core", "i4", "i5", "i6") for i in (items_build.get(k) or []) if is_boots(i)), None)
    later = []
    for k in ("i4", "i5", "i6"):
        first = next((i for i in (items_build.get(k) or []) if not is_boots(i)), None)
        if first and first not in core and first not in later:
            later.append(first)
    seq = core[:1] + ([boots] if boots else []) + core[1:] + later
    return list(dict.fromkeys(seq))


def next_purchase(order, inventory, gold, items):
    """Primer objeto de `order` que todavía no tienes (ni has mejorado a otro que lo contiene), con lo que te falta y si puedes pagarlo ya.
    Devuelve {id, remaining, affordable, missing, partial} o None si no hay nada que proponer (build vacía, todo comprado o precios
    desconocidos). `partial`: componentes de esa receta que ya llevas."""
    inv = [i for i in inventory if i]
    in_stock = set(inv)
    for iid in order:
        if iid not in items or iid in in_stock:
            continue
        if any(iid in recipe_tree(j, items) for j in in_stock):   # ya llevas uno mejor hecho con él
            continue
        rem = remaining_cost(iid, items, inv)
        if rem is None:
            continue
        return {"id": iid, "remaining": rem, "affordable": gold >= rem, "missing": max(0, rem - int(gold)),
                "partial": sorted(c for c in set(items[iid].get("from") or []) if c in in_stock or any(c in recipe_tree(j, items) for j in in_stock))}
    return None


def describe(res, items):
    """Frase para la pantalla a partir de `next_purchase`."""
    nombre = lambda i: (items.get(i) or {}).get("n") or f"objeto {i}"
    if res["affordable"]:
        return f"Siguiente objeto de tu build: {nombre(res['id'])}. Con tu oro ya puedes comprarlo ({res['remaining']} de oro)."
    txt = f"Siguiente objeto de tu build: {nombre(res['id'])}. Te faltan {res['missing']} de oro"
    if res["partial"]:
        txt += f" (ya llevas {', '.join(nombre(c) for c in res['partial'])})"
    return txt + "."
