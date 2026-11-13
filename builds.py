"""Build más usada de un campeón en una línea: runas, hechizos, objetos y orden de habilidades.

Fuente: la página pública de «build» de Lolalytics (las runas elegidas se distinguen de las demás por su estilo). También sirve la
página «contra un rival» para ver la build en un enfrentamiento concreto. Se guarda un día. Si la web cambia, la función devuelve
None y la aplicación sigue sin la build.
"""
import json, os, re, threading, time, urllib.request

import matchups

TTL = 24 * 3600
MIN_VS = 100  # partidas mínimas de los objetos principales para fiarse de la build «contra un rival»
UA = matchups.UA
_state = {}   # clave -> ("loading",) | ("ok", datos) | ("error", texto)
_lock = threading.Lock()
LANES_OK = set(matchups.LANE_NAMES)


def url(champ, lane, enemy=None, tier=None):
    t = f"&tier={tier}" if tier else ""
    if enemy:
        return f"https://lolalytics.com/lol/{matchups.slug(champ)}/vs/{matchups.slug(enemy)}/build/?lane={lane}&vslane={lane}{t}"
    return f"https://lolalytics.com/lol/{matchups.slug(champ)}/build/?lane={lane}{t}"


def _imgs(seg):
    return re.findall(r"<img[^>]*>", seg)


def _sel(tag):
    return "grayscale" not in tag


def patch_of(html):
    """Parche del que son los datos de la página («Patch 16.22» en su texto), con la numeración pública (26.22); «» si no aparece."""
    m = re.search(r"Patch (\d{1,2})\.(\d{1,2})\b", re.sub(r"<!--.*?-->", "", html, flags=re.S))
    return f"{int(m.group(1)) + 10}.{m.group(2)}" if m else ""


def parse(html):
    """{runes:{keystone, primary[3], secondary[2], shards[]}, spells[2], skills[], items:{start, core, i4, i5, i6}} o None."""
    h = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    try:
        ip, isec, istat = h.index("Primary Runes"), h.index("Secondary", h.index("Primary Runes")), h.index("Stat Mods")
    except ValueError:
        return None
    out = {"runes": {}, "spells": [], "skills": [], "items": {}}
    key, prim = None, []
    for tag in _imgs(h[ip:isec]):
        m = re.search(r"rune68/(\d+)", tag)
        if not m or not _sel(tag):
            continue
        if 'width="34"' in tag:
            key = int(m.group(1))
        else:
            prim.append(int(m.group(1)))
    out["runes"]["keystone"], out["runes"]["primary"] = key, prim[:3]
    out["runes"]["secondary"] = [int(re.search(r"rune68/(\d+)", t).group(1)) for t in _imgs(h[isec:istat])
                                 if re.search(r"rune68/(\d+)", t) and _sel(t)][:2]
    mods = [t for t in _imgs(h[istat:istat + 9000]) if "statmod32/" in t][:9]  # 3 filas de 3 opciones; la elegida no está en gris
    out["runes"]["shards"] = [int(re.search(r"statmod32/(\d+)", t).group(1)) for t in mods if _sel(t)][:3]
    isp = h.find("Summoner Spells")
    if isp >= 0:
        out["spells"] = list(dict.fromkeys(int(x) for x in re.findall(r"spell64/(\d+)", h[isp:isp + 3000])))[:2]
        iwr = h.find("Win Rate")
        seen = []
        for x in re.findall(r"skill68/[a-z0-9_]+?_([qwer])\.webp", h[iwr:isp] if 0 <= iwr < isp else h[max(0, isp - 6000):isp]):
            if x not in seen and x != "r":
                seen.append(x)
        out["skills"] = seen[:3]
    heads = ["Starting Items", "Core Build", "Item 4", "Item 5", "Item 6"]
    pos = []
    base = h.find("Starting Items", istat)
    for t in heads:
        p = h.find(t, base)
        if p < 0:
            return out if out["runes"].get("keystone") else None
        pos.append(p)
    pos.append(pos[-1] + 4000)
    names = ["start", "core", "i4", "i5", "i6"]
    stats = {}
    for n, a, b in zip(names, pos, pos[1:]):
        ids = []
        for x in re.findall(r"item64/(\d+)", h[a:b]):
            if int(x) not in ids:
                ids.append(int(x))
        out["items"][n] = ids
        seg = re.sub(r"<img[^>]*item64/(\d+)[^>]*>", r"[I\1]", h[a:b])
        txt = re.sub(r"\|+", "|", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", seg)))
        if n in ("i4", "i5", "i6"):  # cada opción trae su porcentaje de victorias y sus partidas
            opts = [{"id": int(i), "wr": float(w), "games": int(g.replace(",", ""))}
                    for i, w, g in re.findall(r"\[I(\d+)\](?:\|Loading\.\.\.)?\|(\d{1,2}(?:\.\d+)?)%\|([\d,]+)", txt)]
            if opts:
                stats[n] = opts
        else:
            m = re.search(r"(\d{1,2}(?:\.\d+)?)%(?: Win Rate)?\|\s*([\d,]+)(?: Games)?", txt)
            if m:
                stats[n] = {"wr": float(m.group(1)), "games": int(m.group(2).replace(",", ""))}
    out["stats"] = stats
    # objetos que más se compran con este campeón (la paleta de la página): sirven de cantera para las situaciones
    i0, i1 = h.find("Combined Sets"), h.find("Click Items Below to Filter")
    if 0 <= i0 < i1:
        out["palette"] = list(dict.fromkeys(int(x) for x in re.findall(r"item64/(\d+)", h[i0:i1])))[:40]
    out["v"] = 3
    return out if out["runes"].get("keystone") and out["items"].get("core") else None


def _path(cache_dir, champ, lane, enemy):
    tag = f"{matchups.slug(champ)}_{lane}" + (f"_vs_{matchups.slug(enemy)}" if enemy else "")
    return os.path.join(cache_dir, "builds", tag + ".json")


def load(cache_dir, champ, lane, enemy=None, force=False):
    path = _path(cache_dir, champ, lane, enemy)
    try:
        saved = json.load(open(path, encoding="utf-8"))
        if not force and time.time() - saved["ts"] < TTL and saved["data"].get("v") == 3:
            return saved["data"]
    except Exception:
        pass
    last = None
    for tier in (None, "all"):  # primero tu rango; si no hay datos suficientes, todos los rangos
        try:
            req = urllib.request.Request(url(champ, lane, enemy, tier), headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                page = r.read().decode("utf8", "replace")
                data = parse(page)
                if data:
                    data["patch"], data["read"] = patch_of(page), time.time()   # de qué parche son los datos y cuándo se leyeron
            if data and enemy and ((data.get("stats") or {}).get("core") or {}).get("games", 10 ** 6) < MIN_VS:
                data = None  # muy pocas partidas contra ese rival: es mejor la build general que una cifra sin respaldo
            if data:
                data["tier"] = tier or "default"
                data["vs"] = bool(enemy)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                json.dump({"ts": time.time(), "data": data}, open(path, "w", encoding="utf-8"))
                return data
        except Exception as e:
            last = e
    if enemy:  # sin datos del enfrentamiento concreto: la build general de la línea
        d = load(cache_dir, champ, lane, None, force)
        if d:
            return {**d, "vs": False, "vs_missing": True}
    raise RuntimeError("Lolalytics no tiene todavía una build de este campeón en esa línea." if last is None else f"No se pudo leer la build ({type(last).__name__}).")


def request(cache_dir, champ, lane, enemy=None):
    """Pide la build en segundo plano. Devuelve la clave para consultar con peek()."""
    key = (matchups.slug(champ), lane, matchups.slug(enemy) if enemy else "")
    with _lock:
        st = _state.get(key)
        if st and (st[0] == "loading" or (st[0] == "ok")):
            return key
        _state[key] = ("loading",)

    def go():
        try:
            d = load(cache_dir, champ, lane, enemy)
            _state[key] = ("ok", d)
        except Exception as e:
            _state[key] = ("error", str(e) if isinstance(e, RuntimeError) else f"No se pudo leer la build ({type(e).__name__}).")
    threading.Thread(target=go, daemon=True).start()
    return key


def peek(key):
    return _state.get(key, ("loading",))
