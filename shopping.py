"""«Puedes comprar…»: con tu oro y lo que ya llevas, cuál es el siguiente objeto de tu build y cuánto te falta (teniendo en cuenta los
componentes que ya tienes). Sin red ni ventana: solo cuentas con el catálogo de objetos de Data Dragon (`items.load`).

El catálogo es {id: {"g": coste total, "t": etiquetas, "from": [componentes, con repetición]}}. El precio de montar un objeto con sus
componentes es su coste total menos lo que cuestan los componentes; lo que ya llevas de esa receta se resta una sola vez por unidad.
"""


# Objetos que NO se compran: aparecen cuando el que ya llevas se transforma (acumulando cargas o por la misión). Data Dragon no les da receta, así que sin esto
# la app proponía «comprar» Muramana teniendo Manamune (y, al revés, comprar Manamune teniendo ya Muramana). base -> forma evolucionada
EVOLVES = {3004: 3042,    # Manamune -> Muramana
           3003: 3040,    # Bastón del arcángel -> Abrazo del serafín
           3119: 3121,    # Llegada del invierno -> El gran invierno
           2526: 2530,    # Diadema susurrante -> Diadema melodiosa
           3865: 3866, 3866: 3867}   # Atlas mundial -> Brújula rúnica -> Botín universal (misión del apoyo)
_BASE = {v: k for k, v in EVOLVES.items()}


def base(iid):
    """La forma comprable de un objeto: Muramana -> Manamune, Abrazo del serafín -> Bastón del arcángel…; los demás, ellos mismos."""
    while iid in _BASE:
        iid = _BASE[iid]
    return iid


def norm(iid, items):
    """`base` más las variantes de modo (Arena, Enjambre, ARAM Caos…: mismo objeto con el id prefijado, p. ej. 323003 = 3003 con otro precio): si el id con prefijo
    no es el comprable, se usa el del mismo nombre sin prefijo. Un id que no está en el catálogo se deja tal cual."""
    it = (items or {}).get(iid)
    if it and iid >= 10000:
        b = iid % 10000
        if b in items and items[b].get("n") == it.get("n"):
            iid = b
    return base(iid)


def is_quest(iid, items):
    """Objetos de la misión del apoyo y de la jungla (400 de oro nominales, se mejoran con oro de misión, no en la tienda)."""
    t = (items.get(iid) or {}).get("t") or []
    return "Lane" in t and "GoldPer" in t


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
    inv = [norm(i, items) for i in inventory if i]   # lo que llevas, en su forma comprable (Muramana cuenta como Manamune)
    in_stock = set(inv)
    # con unas botas de segundo nivel o más ya puestas, no se propone otro par (la build puede traer unas distintas de las que elegiste)
    boots_made = any("Boots" in (items.get(j) or {}).get("t", []) and (items.get(j) or {}).get("depth") not in (None, 1) for j in in_stock)
    for iid in order:
        iid = norm(iid, items)
        if iid not in items or iid in in_stock or is_quest(iid, items):
            continue
        if boots_made and "Boots" in items[iid].get("t", []):
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


def candidate_pool(items, build):
    """Objetos completos (sin botas ni consumibles, de 1000+ de oro) entre los que más se compran con este campeón: la paleta de la página
    y las opciones de los huecos 4 a 6. `build`: los datos de builds.py. Es la cantera de las «situaciones»."""
    pool = []
    for i in list(build.get("palette") or []) + [o["id"] for k in ("i4", "i5", "i6") for o in (build.get("stats") or {}).get(k, [])]:
        info = items.get(i)
        if i not in pool and info and not info.get("into") and info["g"] >= 1000 and "Boots" not in info["t"] and "Consumable" not in info["t"]:
            pool.append(i)
    return pool


def counter_item(enemy, pool, items, inventory, minimum=2500):
    """UN objeto concreto contra lo que llevan los rivales, o None. `enemy`: resultado de live.itemization (oro en daño físico/mágico y en
    armadura/resistencia mágica). Primero la penetración si acumulan una defensa; si no, la defensa contra su tipo de daño dominante.
    Solo habla con oro suficiente (`minimum`) y entre los objetos de `pool` que aún no llevas. Devuelve {id, why}."""
    have = {norm(i, items) for i in inventory}
    libres = list(dict.fromkeys(norm(i, items) for i in pool if norm(i, items) not in have and not is_quest(norm(i, items), items)))
    defensa, ataque = enemy["armor"] + enemy["mr"], enemy["ad"] + enemy["ap"]
    if defensa >= minimum:
        for dom, otro, efecto, texto in (("armor", "mr", "penarm", "acumulan armadura"), ("mr", "armor", "penmag", "acumulan resistencia mágica")):
            if enemy[dom] >= 1.8 * enemy[otro]:
                it = next((i for i in libres if efecto in items[i].get("x", [])), None)
                if it:
                    return {"id": it, "why": f"Los rivales {texto}: penetración."}
    if ataque >= minimum:
        for dom, tag, texto in (("ad", "Armor", "físico"), ("ap", "SpellBlock", "mágico")):
            if enemy[dom] >= 0.7 * ataque:
                it = next((i for i in libres if tag in items[i]["t"]), None)
                if it:
                    return {"id": it, "why": f"El daño rival es sobre todo {texto} ({round(100 * enemy[dom] / ataque)} %): {'armadura' if tag == 'Armor' else 'resistencia mágica'}."}
    return None
