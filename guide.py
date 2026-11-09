"""Guía de campeón y de duelo, calculada con datos oficiales de Riot (Data Dragon, en español) y las valoraciones de Meraki.

Qué hay y qué NO hay (honestidad):
- Habilidades con sus enfriamientos, costes y alcances, estadísticas base y crecimiento, y los consejos que Riot escribe para jugar con
  cada campeón y contra él: son datos oficiales.
- Las «ventajas del duelo» (alcance, velocidad, nivel 1, escalado, ventanas de trade, maná) se CALCULAN comparando ambos campeones.
  No son una guía escrita a mano de ese duelo concreto: ninguna fuente pública da algo así por parejas de campeones.
- Los picos de poder se dan por niveles de la definitiva y por el coste de los objetos de la build; el minuto exacto de cada objeto no se conoce.
"""
import json, os, re, threading, time, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)"}
_state = {}
_lock = threading.Lock()
KEYS = "QWER"


def _clean(t):
    t = re.sub(r"<br\s*/?>", " ", t or "")
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _path(cache_dir, version, icon):
    return os.path.join(cache_dir, "guide", f"{version}_{icon}.json")


def parse(raw):
    """Datos útiles de un campeón a partir del JSON de Data Dragon."""
    c = next(iter(raw["data"].values()))
    spells = []
    for i, s in enumerate(c.get("spells", [])[:4]):
        spells.append({"k": KEYS[i], "n": s["name"], "d": _clean(s.get("description")), "cd": s.get("cooldown") or [],
                       "cost": s.get("cost") or [], "range": s.get("range") or [], "max": s.get("maxrank", 5),
                       "res": s.get("costType") or "", "ammo": s.get("maxammo", "-1")})
    p = c.get("passive", {})
    return {"stats": c["stats"], "spells": spells, "passive": {"n": p.get("name", ""), "d": _clean(p.get("description"))},
            "ally": [_clean(t) for t in c.get("allytips", [])], "enemy": [_clean(t) for t in c.get("enemytips", [])],
            "res": c.get("partype", ""), "lore": _clean(c.get("blurb"))}


def load(cache_dir, version, champ):
    path = _path(cache_dir, version, champ["icon"])
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        pass
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/es_ES/champion/{champ['icon']}.json"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        data = parse(json.loads(r.read().decode("utf8")))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"))
    return data


def request(cache_dir, version, champ):
    """Pide los datos de un campeón en segundo plano; devuelve la clave para peek()."""
    key = (version, champ["icon"])
    with _lock:
        st = _state.get(key)
        if st and st[0] in ("loading", "ok"):
            return key
        _state[key] = ("loading",)

    def go():
        try:
            _state[key] = ("ok", load(cache_dir, version, champ))
        except Exception as e:
            _state[key] = ("error", f"No se pudieron bajar los datos de {champ['name']} ({type(e).__name__}).")
    threading.Thread(target=go, daemon=True).start()
    return key


def peek(key):
    return _state.get(key, ("loading",))


# ---------------------------------------------------------------- cálculo
def stat(base, growth, lvl):
    """Fórmula oficial de crecimiento por nivel."""
    return base + growth * (lvl - 1) * (0.7025 + 0.0175 * (lvl - 1))


def at(d, lvl):
    s = d["stats"]
    return {"hp": stat(s["hp"], s["hpperlevel"], lvl), "ar": stat(s["armor"], s["armorperlevel"], lvl),
            "mr": stat(s["spellblock"], s["spellblockperlevel"], lvl), "ad": stat(s["attackdamage"], s["attackdamageperlevel"], lvl),
            "as": s["attackspeed"] * (1 + stat(0, s["attackspeedperlevel"], lvl) / 100)}


def ehp(x):
    return x["hp"] * (1 + x["ar"] / 100)


def f1(v):
    return f"{v:.1f}".replace(".", ",")


def cd_text(s):
    cd = [c for c in s["cd"] if c is not None]
    if not cd or max(cd) == 0:
        return "sin enfriamiento"
    if cd[0] == cd[-1]:
        return f"{f1(cd[0]).rstrip('0').rstrip(',')} s"
    return f"{f1(cd[0]).rstrip('0').rstrip(',')} → {f1(cd[-1]).rstrip('0').rstrip(',')} s"


def cost_text(s, res):
    c = [x for x in s["cost"] if x is not None]
    if not c or max(c) == 0:
        return ""
    unit = {"Maná": "maná", "Energía": "energía"}.get(res, "")
    return f"{c[0]:g} {unit}".strip() if c[0] == c[-1] else f"{c[0]:g} → {c[-1]:g} {unit}".strip()


def range_text(s):
    r = [x for x in s["range"] if x]
    if not r or r[0] >= 3000 or r[0] <= 0:
        return ""
    return f"{r[0]:g}" if r[0] == r[-1] else f"{r[0]:g}"


def mana_rounds(d):
    """Cuántas rondas de Q+W+E se pueden lanzar con el maná de nivel 1 (None si el recurso no es maná)."""
    if d["res"] not in ("Maná", "Mana"):
        return None
    mp = d["stats"]["mp"]
    tot = sum((s["cost"][0] if s["cost"] else 0) or 0 for s in d["spells"][:3])
    return int(mp // tot) if tot > 0 and mp > 0 else None


def duel(mine, opp, nm, no, attr_m=None, attr_o=None, dmg_o=""):
    """Lista de (título, texto, tono) con lo que se desprende de comparar a ambos. tono: good | bad | fg."""
    out = []
    sm, so = mine["stats"], opp["stats"]
    # alcance
    dr = sm["attackrange"] - so["attackrange"]
    if abs(dr) >= 100:
        if dr > 0:
            out.append(("Alcance", f"{nm} ataca desde {sm['attackrange']:g} y {no} desde {so['attackrange']:g}: tienes alcance para castigarle "
                                   f"sin que te responda; si se acerca, retrocede.", "good"))
        else:
            out.append(("Alcance", f"{no} ataca desde {so['attackrange']:g} y {nm} desde {sm['attackrange']:g}: él te golpea primero. "
                                   f"No te quedes a distancia de sus ataques; busca entrar con una habilidad o con los súbditos de por medio.", "bad"))
    dv = sm["movespeed"] - so["movespeed"]
    if abs(dv) >= 10:
        out.append(("Velocidad", f"Velocidad de movimiento {sm['movespeed']:g} frente a {so['movespeed']:g}: " +
                    ("puedes elegir cuándo pelear y cuándo irte." if dv > 0 else "él decide más fácilmente si pelea; no te alejes de tu torre sin visión."),
                    "good" if dv > 0 else "bad"))
    # nivel 1 y escalado
    a1, b1, a16, b16 = at(mine, 1), at(opp, 1), at(mine, 16), at(opp, 16)
    r1, r16 = ehp(a1) / ehp(b1), ehp(a16) / ehp(b16)
    ad1 = a1["ad"] - b1["ad"]
    if abs(ad1) >= 3 or abs(r1 - 1) >= 0.08:
        win = ad1 + 20 * (r1 - 1)
        out.append(("Nivel 1", f"{nm}: {a1['hp']:.0f} de vida, {a1['ar']:.0f} de armadura y {a1['ad']:.0f} de ataque. {no}: {b1['hp']:.0f}, {b1['ar']:.0f} y "
                               f"{b1['ad']:.0f}. " + ("Llegas con ventaja física al primer cruce de súbditos." if win > 0 else
                                                       "Empieza ligeramente por delante: cede los primeros intercambios."), "good" if win > 0 else "bad"))
    gain = (r16 / r1) - 1
    if abs(gain) >= 0.08:
        out.append(("Escalado", f"Tu aguante base (vida y armadura) frente al suyo pasa de {r1:.2f}× en el nivel 1 a {r16:.2f}× en el 16 (sin objetos): " +
                    (f"{nm} mejora con los niveles; no fuerces antes de tiempo." if gain > 0 else f"{nm} pierde terreno con los niveles; la ventaja hay que "
                                                                                                f"convertirla pronto."),
                    "good" if gain > 0 else "bad"))
    # ventanas de trade
    for who, d, n, mineflag in (("rival", opp, no, False), ("tuyo", mine, nm, True)):
        sp = [s for s in d["spells"][:3] if s["cd"] and s["cd"][0]]
        if not sp:
            continue
        short = min(sp, key=lambda s: s["cd"][0])
        long_ = max(sp, key=lambda s: s["cd"][0])
        if mineflag:
            out.append(("Tu ritmo", f"Tu {short['k']} ({short['n']}) vuelve en {cd_text(short)} y tu {long_['k']} ({long_['n']}) tarda {cd_text(long_)}: "
                                    f"plantea el intercambio con la corta y reserva la larga para rematar o escapar.", "fg"))
        else:
            lst = ", ".join(f"{s['k']} {cd_text(s)}" for s in d["spells"][:3] if s["cd"] and s["cd"][0])
            out.append(("Ventana de trade", f"Enfriamientos de {n} (rango 1 → máx.): {lst}. Cuenta esos segundos desde que gaste o falle una habilidad: "
                                            f"es el hueco para entrar. Las de enfriamiento largo ({long_['k']}, {cd_text(long_)}) te dan el hueco más grande.", "good"))
    ru = opp["spells"][3] if len(opp["spells"]) > 3 else None
    if ru and ru["cd"]:
        out.append(("Su definitiva", f"{ru['n']}: {cd_text(ru)}. La tiene desde el nivel 6; el rango 2 llega al 11 y el 3 al 16 (en la mayoría de campeones).", "fg"))
    # maná
    rm, ro = mana_rounds(mine), mana_rounds(opp)
    if rm is not None and ro is not None and abs(rm - ro) >= 1:
        out.append(("Maná", f"Con el maná de nivel 1 aguantas {rm} rondas de Q+W+E y {no} {ro}. " +
                    ("Él se quedará sin recursos antes: presiona sin miedo." if rm < ro else "Tú tienes más margen: puedes insistir más."), "good" if rm > ro else "bad"))
    # valoraciones Meraki
    am, ao = attr_m or {}, attr_o or {}
    for key, label in (("mobility", "Movilidad"), ("control", "Control de masas"), ("toughness", "Aguante"), ("damage", "Daño")):
        x, y = am.get(key), ao.get(key)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and abs(x - y) >= 1:
            hint = {"mobility": (" Decides tú el ritmo de la línea.", " Él decide el ritmo: no te alejes de tu torre sin visión."),
                    "control": (" Tienes más control: úsalo para iniciar o salvarte.", " Respeta sus controles: sin visión de sus habilidades no avances."),
                    "toughness": (" Aguantas más los intercambios largos.", " Aguanta más que tú: evita intercambios largos."),
                    "damage": (" Ganas los intercambios cortos si aciertas.", " Te supera en daño: no aceptes un cruce directo sin ventaja.")}[key]
            out.append((label, f"Valoración de Meraki: {nm} {x:g} frente a {no} {y:g} (de 1 a 3)." + hint[0 if x > y else 1], "good" if x > y else "bad"))
    kind = {"PHYSICAL_DAMAGE": "físico", "MAGIC_DAMAGE": "mágico", "MIXED_DAMAGE": "mixto"}.get(dmg_o)
    if kind:
        out.append(("Su daño", f"El daño de {no} es {kind}" + (": la armadura le recorta mucho." if kind == "físico" else ": la resistencia mágica le recorta mucho."
                                                                if kind == "mágico" else ": ni solo armadura ni solo resistencia mágica bastan."), "fg"))
    return out


def spikes(d, name, skills, items, info):
    """Picos de poder: niveles de la definitiva, habilidad principal y coste acumulado de los primeros objetos (sin minutos exactos)."""
    out = []
    ru = d["spells"][3] if len(d["spells"]) > 3 else None
    if ru:
        out.append(("Nivel 6", f"Consigues {ru['n']} ({cd_text(ru)}). Es el primer salto de poder: el intercambio de nivel 6 suele decidir la línea."))
        out.append(("Niveles 11 y 16", "La definitiva sube de rango (11 y 16): ir un nivel por delante del rival en esos momentos da ventaja en el cruce."))
    if skills:
        first = skills[0].upper()
        sp = next((s for s in d["spells"] if s["k"] == first), None)
        if sp:
            out.append(("Habilidad principal", f"{first} ({sp['n']}) al máximo hacia el nivel 9 según el orden más jugado ({' > '.join(x.upper() for x in skills)}): "
                                               f"su enfriamiento baja a {cd_text(sp).split('→')[-1].strip()}."))
    tot = 0
    for i, iid in enumerate(items[:3], 1):
        g = (info.get(iid) or {}).get("g")
        if g:
            tot += g
            out.append((f"{i}.º objeto" if i < 3 else "3.º objeto", f"{info[iid]['n']} (acumulado ≈ {tot:,} de oro)".replace(",", ".")))
    return out
