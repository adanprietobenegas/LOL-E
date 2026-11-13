"""Build sugerida para ARAM y ARAM: Mayhem (objetos iniciales, botas, builds de 3 objetos, orden de habilidades) y las mejoras que op.gg sugiere en Mayhem.

Fuente: las páginas de op.gg para esos modos (op.gg/lol/modes/aram/<campeón>/build y .../aram-mayhem/...). Se bajan con PowerShell oculto, como el resto de op.gg, y se
guardan un día. Las páginas de Mayhem NO traen porcentajes de objetos ni de mejoras: solo las listas. Y aunque los trajeran, Riot no permite mostrar victorias por
mejora, así que aquí solo se enseña el orden/lista de nombres y nunca un porcentaje.
"""
import html as htmlmod
import json, os, re, subprocess, threading, time

import lol_advisor as core
import matchups
import opgg_builds as og

TTL = 24 * 3600
MODES = {450: "aram", 2400: "aram-mayhem"}
_state = {}
_lock = threading.Lock()


def url(champ, mode):
    return f"https://op.gg/lol/modes/{mode}/{matchups.slug(champ)}/build"


def _ids(txt):
    return [int(x) for x in re.findall(r"\[I(\d+)\]", txt)]


def parse(page):
    """{starters, boots, builds, skills, augments} o None si la página no tiene build."""
    t = og._text(page)
    i0, i1, i2 = t.find("Starter items|"), t.find("Boots Table"), t.find("Builds Table")
    if min(i0, i1, i2) < 0 or not (i0 < i1 < i2):
        return None
    end = t.find("ADVERTISEMENT", i2)
    starters = _ids(t[i0:i1])
    boots = _ids(t[i1:i2])
    core_ids = _ids(t[i2:end if end > i2 else i2 + 400])
    builds = [core_ids[k:k + 3] for k in range(0, len(core_ids) - 2, 3)][:5]
    out = {"v": 1, "starters": starters[:4], "boots": boots[:3], "builds": builds}
    s0 = t.find("Skill order|")
    if s0 >= 0:
        m = re.search(r"((?:\|[QWER]){12,18})", t[s0:s0 + 300])
        if m:
            out["skills"] = re.findall(r"[QWER]", m.group(1))[:18]
    a = re.search(r"\|Augments\|(.*?)\|[A-Za-z' .&;#0-9-]+\| \|Summoner spells", t, re.S)
    if a:
        chunk = a.group(1)
        chunk = chunk[chunk.rfind("Augments|") + 9:] if "Augments|" in chunk else chunk   # solo lo que va tras el último «Augments»
        names = [htmlmod.unescape(x).strip() for x in chunk.split("|") if x.strip()]
        out["augments"] = [n for n in names if len(n) < 40][:16]
    return out if (out["builds"] or out["boots"]) else None


def _fetch(champ, mode):
    tmp = os.path.join(core.CACHE, "aram_build.tmp")
    os.makedirs(core.CACHE, exist_ok=True)
    ps = ("Invoke-WebRequest -UseBasicParsing -TimeoutSec 40 -Headers @{'User-Agent'='Mozilla/5.0';'Accept-Language'='en'} "
          f"-Uri '{url(champ, mode)}' -OutFile '{tmp}'")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps], check=True, timeout=90,
                   capture_output=True, **{k: v for k, v in core.quiet().items() if k != "stdin"})
    with open(tmp, encoding="utf-8", errors="replace") as f:
        return f.read()


def load(cache_dir, champ, mode, force=False):
    path = os.path.join(cache_dir, "builds", f"mode_{mode}_{matchups.slug(champ)}.json")
    old = None
    try:
        saved = json.load(open(path, encoding="utf-8"))
        old = saved["data"]
        if not force and time.time() - saved["ts"] < TTL:
            return old
    except Exception:
        pass
    try:
        data = parse(_fetch(champ, mode))
    except Exception:
        if old:   # sin red o la fuente falla: mejor lo último guardado (marcado) que nada
            return {**old, "stale": True}
        raise
    if not data:
        if old:
            return {**old, "stale": True}
        raise RuntimeError("op.gg no tiene todavía build para este campeón en este modo.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"ts": time.time(), "data": data}, open(path, "w", encoding="utf-8"))
    return data


def request(cache_dir, champ, mode):
    key = ("mode", mode, matchups.slug(champ))
    with _lock:
        if key in _state:
            return key
        _state[key] = ("loading",)

    def go():
        try:
            _state[key] = ("ok", load(cache_dir, champ, mode))
        except Exception as e:
            _state[key] = ("error", str(e) if isinstance(e, RuntimeError) else f"No se pudo leer op.gg ({type(e).__name__}).")
    threading.Thread(target=go, daemon=True).start()
    return key


def peek(key):
    return _state.get(key, ("loading",))


def augment_ids(names, catalog):
    """Casa los nombres en inglés de op.gg con las mejoras del cliente (id interno ARAM_Nombre). Devuelve [(id, nombre_op.gg)] de las que se reconocen."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    by = {}
    for aid, v in catalog.items():
        if v.get("k"):
            k = norm(re.sub(r"^ARAM_", "", v["k"]))
            if k not in by or v.get("a"):   # si hay dos con el mismo nombre, gana la de ARAM
                by[k] = aid
    return [(by[norm(n)], n) for n in names if norm(n) in by]
