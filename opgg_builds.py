"""Builds de op.gg como segunda opinión: objetos iniciales, botas, builds de objetos principales y orden de habilidades.

Cada web calcula con su muestra y sus filtros de rango, así que las builds no siempre coinciden con las de Lolalytics: mostrar las dos
ayuda a ver en qué hay acuerdo. La página se descarga con PowerShell (oculto) porque Python rechaza a veces la cadena de certificados
de op.gg. Se guarda un día. Si la web cambia, la función devuelve None y la aplicación sigue con Lolalytics.
"""
import json, os, re, subprocess, threading, time

import lol_advisor as core
import matchups

TTL = 24 * 3600
LANE = {"top": "top", "jungle": "jungle", "middle": "mid", "bottom": "adc", "support": "support"}
_state = {}
_lock = threading.Lock()


def url(champ, lane):
    return f"https://op.gg/lol/champions/{matchups.slug(champ)}/build/{LANE.get(lane, lane)}"


def _text(html):
    seg = re.sub(r'<img[^>]*?/item/(\d+)\.png[^>]*>', r'[I\1]', html)
    return re.sub(r"\|+", "|", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", seg)))


ROW = re.compile(r"((?:\[I\d+\]\|?)+)(\d{1,3}(?:\.\d+)?)%\|([\d,]+)\| \|Games\|(\d{1,3}(?:\.\d+)?)%")


def _rows(txt):
    out = []
    for items, pr, games, wr in ROW.findall(txt):
        out.append({"items": [int(x) for x in re.findall(r"\[I(\d+)\]", items)], "pr": float(pr), "games": int(games.replace(",", "")), "wr": float(wr)})
    return out


def parse(html):
    """{starters, boots, core, skills} o None. Cada fila: {items, pr (uso), games, wr (victorias)}."""
    t = _text(html)
    i0, i1, i2 = t.find("Starter items"), t.find("Boots Table"), t.find("Builds Table")
    if min(i0, i1, i2) < 0 or not (i0 < i1 < i2):
        return None
    starters, boots = _rows(t[i0:i1]), _rows(t[i1:i2])
    nxt = t.find("Table|", i2 + 12)
    core_rows = _rows(t[i2:nxt if nxt > i2 else i2 + 4000])
    out = {"starters": starters[:3], "boots": [{**b, "id": b["items"][0]} for b in boots[:3] if b["items"]], "core": core_rows[:4], "v": 1}
    s0 = t.find("Skill order")
    if s0 >= 0:
        m = re.search(r"((?:\|[QWER]){14,18})", t[s0:s0 + 400])
        if m:
            seq = re.findall(r"[QWER]", m.group(1))
            out["skill_seq"] = seq[:18]
            cnt = {k: seq[:15].count(k) for k in "QWE"}
            out["skills"] = sorted(cnt, key=lambda k: (-cnt[k], seq.index(k) if k in seq else 99))
    return out if out["core"] and out["boots"] else None


def _fetch(champ, lane):
    tmp = os.path.join(core.CACHE, "opgg_build.tmp")
    os.makedirs(core.CACHE, exist_ok=True)
    ps = ("Invoke-WebRequest -UseBasicParsing -TimeoutSec 40 -Headers @{'User-Agent'='Mozilla/5.0';'Accept-Language'='en'} "
          f"-Uri '{url(champ, lane)}' -OutFile '{tmp}'")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps], check=True, timeout=90,
                   capture_output=True, **{k: v for k, v in core.quiet().items() if k != "stdin"})
    with open(tmp, encoding="utf-8", errors="replace") as f:
        return f.read()


def load(cache_dir, champ, lane, force=False):
    path = os.path.join(cache_dir, "builds", f"opgg_{matchups.slug(champ)}_{lane}.json")
    old = None
    try:
        saved = json.load(open(path, encoding="utf-8"))
        old = saved["data"]
        if not force and time.time() - saved["ts"] < TTL:
            return old
    except Exception:
        pass
    try:
        data = parse(_fetch(champ, lane))
    except Exception:
        if old:   # sin red o la fuente falla: mejor lo último guardado (marcado) que nada
            return {**old, "stale": True}
        raise
    if not data:
        if old:
            return {**old, "stale": True}
        raise RuntimeError("op.gg no tiene todavía esta build.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"ts": time.time(), "data": data}, open(path, "w", encoding="utf-8"))
    return data


def request(cache_dir, champ, lane):
    key = ("opgg", matchups.slug(champ), lane)
    with _lock:
        st = _state.get(key)
        if st:
            return key
        _state[key] = ("loading",)

    def go():
        try:
            _state[key] = ("ok", load(cache_dir, champ, lane))
        except Exception as e:
            _state[key] = ("error", str(e) if isinstance(e, RuntimeError) else f"No se pudo leer op.gg ({type(e).__name__}).")
    threading.Thread(target=go, daemon=True).start()
    return key


def peek(key):
    return _state.get(key, ("loading",))
