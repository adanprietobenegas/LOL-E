"""LOL-E: asesor de selección de campeón. Sin claves ni cuentas: solo necesita el cliente de LoL abierto."""
import base64, json, os, queue, re, shutil, ssl, subprocess, sys, threading, time
import urllib.parse, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

import analysis
import history
import live
import matchups
import meta as metamod
import params
import players
import sounds
import synergy
import trends
from sounds import SOUNDS, PHASES, NONE, FILE, phase_cfg, play_file, synth_wav, play_alert, play_phase, beep  # noqa: F401  (los usa la ventana)

APP_NAME, APP_VERSION = "LOL-E", "1.22.11"
FROZEN = getattr(sys, "frozen", False)
HERE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
# instalado: los datos de cada usuario van a su perfil; en desarrollo, junto al script
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", HERE), "LOL-E") if FROZEN else HERE
CACHE = os.path.join(DATA_DIR, "cache")
CONF_FILE = os.path.join(DATA_DIR, "config.json")
sounds.CACHE_DIR = CACHE

# estilos de recomendacion: cuanto pesa cada factor
PRESETS = {
    "equilibrado": {"mastery": 3.0, "winrate": 4.0, "role": 3.0, "comp": 2.5, "counter": 3.0, "synergy": 1.8, "meta": 2.2},
    "comodo": {"mastery": 4.5, "winrate": 5.0, "role": 3.0, "comp": 1.2, "counter": 1.5, "synergy": 0.8, "meta": 1.0},
    "adaptativo": {"mastery": 2.0, "winrate": 3.0, "role": 3.0, "comp": 4.0, "counter": 4.5, "synergy": 2.6, "meta": 2.6},
}
PRESET_INFO = {
    "equilibrado": ("Equilibrado", "Mezcla lo que dominas con lo que necesita tu equipo."),
    "comodo": ("Cómodo", "Prioriza tus campeones con más maestría y victorias."),
    "adaptativo": ("Adaptativo", "Prioriza lo que necesita la composición y los counters."),
    "personalizado": ("Personalizado", "Tus propios pesos, ajustados en «Datos»."),
}
DEFAULT_CONF = {
    "lol_path": "",          # carpeta de LoL si no esta en la ruta normal
    "top_n": 5,
    "ban_n": 3,
    "poll_seconds": 1.0,
    "beep": True,            # aviso sonoro cuando es tu turno
    "sound": "Doble tono",
    "volume": 0.7,           # 0 a 1
    "phase_sounds": {},      # sonido de cada fase de la selección: {fase: {"sound": ..., "file": ...}}
    "preset": "equilibrado",
    "folds": {},             # qué secciones plegables están abiertas
    "notes_seen": "",        # última versión cuyas novedades ya se mostraron al abrir
    "auto_itemset": False,   # enviar sola la build al cliente (conjunto de objetos) al elegir campeón
    "win_geo": "",           # tamaño y posición de la ventana la última vez (para abrirla en el mismo monitor)
    "rec_view": "carrusel",  # carrusel | lista | listas
    "list_n": 20,            # cuántos campeones por lista en la vista «Listas»
    "meta_enabled": True,    # meta del parche (Lolalytics)
    "matchups_enabled": True,  # enfrentamientos globales (Lolalytics)
    "custom_weights": {},    # pesos propios (estilo «personalizado»)
    "params": {},            # umbrales propios (ver params.py)
    "auto_update": True,     # buscar actualizaciones al abrir y cada pocas horas (si hay update_url)
    "color_theme": "Predeterminado",   # tema de color (ver temas.py)
    "style": "Plano",                  # estilo de las tarjetas: Plano, Brutal o Cristal
    "auto_install": True,   # instalar solas las versiones nuevas (sin pulsar nada), nunca durante una cola, selección o partida
    "update_url": "https://github.com/adanprietobenegas/LOL-E/releases/latest/download/latest.json",        # direccion del archivo latest.json
    "tab": "asesor",
    "start_tab": "ultima",   # ultima | asesor | enfrentamiento | repertorio | historial | datos
    "animations": True,
    "live_enabled": True,    # durante la partida: marcador, objetos y estado de los 10 jugadores (API local del juego)
    "filters": {"orden": "Afinidad", "clase": "Todas", "mi_rol": True, "mios": False, "meta": False},
    "opgg_enabled": True,    # actualiza tus stats de temporada y matchups desde op.gg
    "opgg_auto": True,       # toma tu Riot ID y region del cliente de LoL
    "topmost_mode": "seleccion",
    "opgg_region": "",
    "opgg_name": "",
    "opgg_tag": "",
    "opgg_update_hours": 24,  # se actualiza si han pasado estas horas...
    "opgg_update_games": 5,   # ...o si has jugado estas partidas nuevas (lo que ocurra antes)
    "theme": "dark",         # dark | light | system
    "accent": "Dorado",
    "scale": 1.0,
    "topmost": True,
    "compact": False,
    "show_teams": True,
    "show_bans": True,
}
TIERS_ES = {"IRON": "Hierro", "BRONZE": "Bronce", "SILVER": "Plata", "GOLD": "Oro", "PLATINUM": "Platino",
            "EMERALD": "Esmeralda", "DIAMOND": "Diamante", "MASTER": "Maestro", "GRANDMASTER": "Gran Maestro",
            "CHALLENGER": "Aspirante"}
SR_QUEUES = {400, 420, 430, 440, 480, 490, 700, 710}  # partidas de Grieta (para winrate y matchups)
ROLE_TAGS = {  # plan B si no hay datos de posicion
    "TOP": {"Fighter": 1.0, "Tank": 0.8},
    "JUNGLE": {"Fighter": 0.7, "Assassin": 0.8, "Tank": 0.7},
    "MIDDLE": {"Mage": 1.0, "Assassin": 0.9},
    "BOTTOM": {"Marksman": 1.0},
    "SUPPORT": {"Support": 1.0, "Tank": 0.3, "Mage": 0.3},
}
CTX = ssl.create_default_context()
CTX.check_hostname, CTX.verify_mode = False, ssl.CERT_NONE


def install_certs():
    """Todas las peticiones de LOL-E a internet verifican con el almacén de Windows MÁS los certificados raíz de `certifi`.
    Windows rellena sus raíces bajo demanda y Python no puede forzarlo: en un PC al que aún no le había llegado la de un servidor
    (visto con op.gg) la petición fallaba con CERTIFICATE_VERIFY_FAILED sin que el usuario pudiera hacer nada. Si `certifi` no
    está, no pasa nada: sigue valiendo el almacén de Windows. Devuelve True si se aplicó. (El cliente de LoL tiene su propio
    contexto, CTX, sin verificar y solo para 127.0.0.1; esto no lo toca.)"""
    try:
        import certifi
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cafile=certifi.where())
        ssl._create_default_https_context = lambda *a, **k: ctx
        return True
    except Exception as e:
        diag(f"Certificados raíz adicionales no disponibles ({type(e).__name__}): se usa solo el almacén de Windows")
        return False


def load_conf():
    conf = dict(DEFAULT_CONF)
    conf.update(read_json(CONF_FILE, {}))
    if not str(conf.get("update_url") or "").strip():
        # Las primeras versiones guardaban esta dirección vacía (aún no había dónde actualizarse) y ese vacío tapaba para
        # siempre la dirección de fábrica: la app no volvía a buscar versiones. Para no actualizarse está el interruptor.
        conf["update_url"] = DEFAULT_CONF["update_url"]
    conf["filters"] = {**DEFAULT_CONF["filters"], **(conf.get("filters") or {})}
    conf["params"] = {**params.DEFAULT_PARAMS, **(conf.get("params") or {})}
    base = PRESETS["equilibrado"]
    conf["weights"] = {**base, **(conf.get("custom_weights") or {})} if conf["preset"] == "personalizado" \
        else dict(PRESETS.get(conf["preset"], base))
    if not os.path.exists(CONF_FILE):
        save_conf(conf)
    return conf


def save_conf(conf):
    os.makedirs(DATA_DIR, exist_ok=True)
    data = {k: v for k, v in conf.items() if k != "weights" and not k.startswith("_")}
    with open(CONF_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, data):
    """Escribe en un archivo temporal y lo cambia de sitio al terminar: un corte de luz no deja el archivo a medias."""
    os.makedirs(os.path.dirname(path) or CACHE, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def norm_role(r):
    r = (r or "").upper()
    return "SUPPORT" if r == "UTILITY" else r


# ---------- Datos de campeones (Data Dragon + Meraki, cacheados) ----------
def http_json(url, timeout=15):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def load_meraki():
    """Posiciones reales y tipo de dano por campeon. Descarga 13MB, guarda solo lo util y refresca cada 7 dias."""
    path = os.path.join(CACHE, "meraki.json")
    saved = read_json(path, None)
    if saved and time.time() - saved["ts"] < 7 * 86400:
        return saved["data"]
    try:
        raw = http_json("https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json", 120)
        data = {str(c["id"]): {"pos": c.get("positions", []), "dmg": c.get("adaptiveType", ""),
                               "attr": c.get("attributeRatings", {})} for c in raw.values()}
        write_json(path, {"ts": time.time(), "data": data})
        return data
    except Exception:
        return saved["data"] if saved else {}


DD_VERSION = ""  # version de Data Dragon, para bajar los iconos


def load_champions():
    global DD_VERSION
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "champions.json")
    saved = read_json(path, None)
    champs = None
    try:
        ver = http_json("https://ddragon.leagueoflegends.com/api/versions.json")[0]
        DD_VERSION = ver
        if saved and saved["version"] == ver and "icon" in next(iter(saved["champs"].values())):
            champs = {int(k): v for k, v in saved["champs"].items()}
        else:
            data = http_json(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/champion.json")["data"]
            champs = {int(c["key"]): {"name": c["name"], "icon": c["id"], "tags": c["tags"], "info": c["info"]}
                      for c in data.values()}
            write_json(path, {"version": ver, "champs": champs})
    except Exception as e:
        if saved:  # sin internet: usar cache vieja
            DD_VERSION = saved["version"]
            champs = {int(k): v for k, v in saved["champs"].items()}
        else:
            raise SystemExit(f"No he podido descargar los datos de los campeones: {e}")
    meraki = load_meraki()
    for cid, c in champs.items():
        c.update(meraki.get(str(cid), {}))
    return champs


# ---------- Cliente (LCU) ----------
def quiet():
    """Opciones para lanzar PowerShell sin que Windows enseñe una ventana azul (parpadeaba cada pocos segundos sin el cliente abierto)."""
    if os.name != "nt":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return {"creationflags": 0x08000000, "startupinfo": si, "stdin": subprocess.DEVNULL}  # CREATE_NO_WINDOW


_PS_NEXT = 0.0  # el plan B (PowerShell) es lento: no se repite más de una vez cada 20 s


def find_client(conf):
    global _PS_NEXT
    paths = [os.path.join(conf["lol_path"], "lockfile")] if conf["lol_path"] else []
    paths += [rf"{d}:\Riot Games\League of Legends\lockfile" for d in "CDEFG"]
    for p in paths:
        if os.path.exists(p):
            try:
                _, _, port, pw, _ = open(p).read().split(":")
                return int(port), pw
            except Exception:
                diag("Leer el archivo de conexión del cliente: " + type(sys.exc_info()[1]).__name__)
    if time.time() < _PS_NEXT:
        return None
    _PS_NEXT = time.time() + 20
    try:  # plan B: leer los argumentos del proceso (por si LoL está instalado en otra carpeta)
        cmd = subprocess.check_output(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"name='LeagueClientUx.exe'\").CommandLine"],
            text=True, timeout=10, **quiet())
        port = re.search(r"--app-port=(\d+)", cmd)
        pw = re.search(r"--remoting-auth-token=([\w-]+)", cmd)
        if port and pw:
            return int(port.group(1)), pw.group(1)
    except Exception:
        diag("Buscar el cliente por su proceso: " + type(sys.exc_info()[1]).__name__)
    return None


class LCU:
    def __init__(self, port, pw):
        self.base = f"https://127.0.0.1:{port}"
        self.auth = "Basic " + base64.b64encode(f"riot:{pw}".encode()).decode()

    def get(self, path, timeout=5):
        req = urllib.request.Request(self.base + path, headers={"Authorization": self.auth})
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError:
            return None

    def get_bytes(self, path, timeout=10):
        """Archivo binario del cliente (por ejemplo un icono de mejora)."""
        req = urllib.request.Request(self.base + path, headers={"Authorization": self.auth})
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError:
            return None


def find_opponent(me, detail):
    """Campeon rival en tu misma linea, a partir del detalle de la partida."""
    if not detail:
        return 0
    parts = detail.get("participants", [])
    mias = history.team_roles([q for q in parts if q.get("teamId") == me.get("teamId")])
    mine = mias.get(me.get("participantId")) or history.role_of(me)
    if not mine:
        return 0
    rival = [q for q in parts if q.get("teamId") != me.get("teamId")]
    rr = history.team_roles(rival)
    cand = [q for q in rival if rr.get(q.get("participantId")) == mine]
    return cand[0]["championId"] if len(cand) == 1 else 0   # con dos candidatos no se adivina cuál es


def load_season_seed(champs):
    """Resultados de tu temporada (sacados de op.gg) por campeon: mas muestra que lo que guarda el cliente."""
    key = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    ids = {key(c["name"]): cid for cid, c in champs.items()}
    out = {}
    for n, v in read_json(os.path.join(DATA_DIR, "season_seed.json"), {}).items():
        if key(n) in ids and isinstance(v, list):
            out[ids[key(n)]] = [v[0] + v[1], v[0]]  # [partidas, victorias]
    return out


def opgg_path(conf):
    who = re.sub(r"\W+", "_", f"{conf.get('opgg_region')}_{conf.get('opgg_name')}_{conf.get('opgg_tag')}")
    return os.path.join(CACHE, f"opgg_{who}.json")


def detect_account(lcu, conf):
    """Lee del cliente tu Riot ID y tu region, para que op.gg funcione sin configurar nada."""
    if not conf.get("opgg_auto", True):
        return
    try:
        acct = lcu.get("/lol-summoner/v1/current-summoner") or {}
        reg = lcu.get("/riotclient/region-locale") or {}
        if acct.get("gameName") and acct.get("tagLine"):
            conf["opgg_name"], conf["opgg_tag"] = acct["gameName"], acct["tagLine"]
        if reg.get("webRegion") or reg.get("region"):
            conf["opgg_region"] = (reg.get("webRegion") or reg["region"]).lower()
    except Exception:
        soft_fail("Detectar tu cuenta para op.gg")


def load_season(champs, conf=None):
    """Stats de temporada y matchups: cache de op.gg si existe, si no el volcado manual season_seed.json."""
    saved = read_json(opgg_path(conf), None) if conf and conf.get("opgg_name") else None
    if saved:
        return {"champs": {int(k): v for k, v in saved["champs"].items()},
                "matchups": {tuple(map(int, k.split(":"))): v for k, v in saved["matchups"].items()}, "ladder": saved.get("ladder")}
    return {"champs": load_season_seed(champs), "matchups": {}}


def fetch_opgg(conf):
    """Descarga la pagina de campeones. Va por PowerShell porque Python rechaza la cadena de certificados de op.gg
    y no quiero desactivar la verificacion SSL."""
    who = urllib.parse.quote(f"{conf['opgg_name']}-{conf['opgg_tag']}")
    url = f"https://op.gg/lol/summoners/{conf['opgg_region']}/{who}/champions"
    out = os.path.join(CACHE, "opgg.html")
    os.makedirs(CACHE, exist_ok=True)
    ps = ("Invoke-WebRequest -UseBasicParsing -TimeoutSec 40 -Headers @{'User-Agent'='Mozilla/5.0';"
          f"'Accept-Language'='en'}} -Uri '{url}' -OutFile '{out}'").replace("}}", "}")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps], check=True, timeout=90,
                   capture_output=True, **{k: v for k, v in quiet().items() if k != "stdin"})
    with open(out, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_ladder(html):
    """Puesto en la clasificación clasificatoria de tu servidor: {rank, top} (op.gg: «Ladder Rank 1,136,003 (30.9% of top)»)."""
    m = re.search(r'Ladder Rank <span[^>]*>([\d,]+)</span> \(([\d.]+)% of top\)', html)
    if not m:
        return None
    return {"rank": int(m.group(1).replace(",", "")), "top": float(m.group(2))}


def parse_opgg(html):
    """Saca de los datos embebidos en la pagina: [partidas, victorias] por campeon y por (campeon, rival)."""
    text = html.replace('\\"', '"')
    dec = json.JSONDecoder()
    champs, matchups = {}, {}
    for m in re.finditer(r'\{"id":(\d+),"play":\d+,"win":\d+,"lose":\d+,', text):
        cid = int(m.group(1))
        try:
            obj, _ = dec.raw_decode(text, m.start())
        except ValueError:
            continue
        if "match_up_stats" not in obj:
            continue
        if str(cid) in champs:  # un campeon repetido = empieza otro conjunto de datos (otro modo/temporada): parar
            break
        champs[str(cid)] = [obj["play"], obj["win"]]
        for mu in obj["match_up_stats"]:
            matchups[f"{cid}:{mu['id']}"] = [mu["play"], mu["win"]]
    return champs, matchups


_opgg_last_try = 0.0


OPGG_MSG = ""  # ultimo resultado, para mostrarlo en pantalla


def maybe_update_opgg(conf, champs, P, force=False):
    """Devuelve datos de temporada nuevos si tocaba actualizar (por horas o por partidas nuevas)."""
    global _opgg_last_try, OPGG_MSG
    if not conf["opgg_name"] or not (conf["opgg_enabled"] or force):
        return None
    if not force and time.time() - _opgg_last_try < 3600:
        return None
    path = opgg_path(conf)
    meta = read_json(path, {})
    age_h = (time.time() - meta.get("ts", 0)) / 3600
    new_games = P["games"] - meta.get("games", P["games"])
    if not force and meta and age_h < conf["opgg_update_hours"] and new_games < conf["opgg_update_games"]:
        return None
    _opgg_last_try = time.time()
    try:
        try:
            html = fetch_opgg(conf)
        except Exception:  # un corte momentáneo: se reintenta una vez antes de rendirse
            time.sleep(4)
            html = fetch_opgg(conf)
        c, m = parse_opgg(html)
        if len(c) < 5:
            raise ValueError("la pagina no trajo datos (perfil no encontrado o web cambiada)")
        write_json(path, {"ts": time.time(), "games": P["games"], "champs": c, "matchups": m, "ladder": parse_ladder(html)})
        OPGG_MSG = f"op.gg actualizado: {len(c)} campeones y {len(m)} enfrentamientos"
        return load_season(champs, conf)
    except Exception as e:
        OPGG_MSG = "op.gg no disponible ahora; sigo con los datos guardados."
        try:
            with open(os.path.join(CACHE, "error.log"), "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%d/%m/%Y %H:%M')} op.gg: {str(e)[:400]}\n")
        except Exception:
            pass
        return None


QUEUE_GROUPS = [("Solo/Dúo", {420}), ("Flexible", {440}), ("Normales", {400, 430, 490}), ("Modo rápido", {480}),
                ("ARAM", {450, 720, 2400}), ("Arena", {1700, 1710, 1740, 1750}), ("Clash", {700}), ("Clasificatorias de 5", {710})]
MODE_ORDER = [g for g, _ in QUEUE_GROUPS] + ["Otros"]


def queue_group(q):
    return next((n for n, qs in QUEUE_GROUPS if q in qs), "Otros")


# ---------- Registro de diagnóstico ----------
_DIAG = {"queues": set(), "last": ""}


def diag(msg):
    """Una línea con fecha en cache/diag.log: qué fue pasando (conexión, cuenta, fases, lecturas). Sin nombres de jugador;
    las cuentas, solo por los 8 primeros caracteres de su identificador. Se parte al llegar a ~400 KB (queda diag.log.1)."""
    try:
        if msg == _DIAG["last"]:
            return
        _DIAG["last"] = msg
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, "diag.log")
        if os.path.exists(path) and os.path.getsize(path) > 400_000:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "  " + str(msg) + chr(10))
    except OSError:
        pass


def soft_fail(where):
    """Para llamar dentro de un `except`: una lectura opcional ha fallado y la app sigue, pero deja rastro (antes eran
    `except: pass`). Si el cliente no respondió, una línea en el registro de diagnóstico; si es un fallo del programa, la
    traza completa en el registro de errores."""
    e = sys.exc_info()[1]
    if isinstance(e, (urllib.error.URLError, ConnectionError, OSError)):
        diag(f"{where}: el cliente no respondió ({type(e).__name__})")
    else:
        log_exc(where)


players.on_fail = soft_fail

# ---------- Versión de los datos guardados ----------
# Claves con las que el cliente de LoL (y su API en vivo) identifican a una persona. Lo que se guarda solo para depurar
# no las necesita: se vacían antes de escribir (ver scrub).
IDENTITY_KEYS = {"puuid", "gameName", "tagLine", "summonerName", "summonerInternalName", "summonerId", "accountId",
                 "obfuscatedPuuid", "obfuscatedSummonerId", "riotId", "riotIdGameName", "riotIdTagLine", "displayName"}


def scrub(obj):
    """Copia de `obj` (diccionarios y listas anidados) con vacíos los valores de las claves que identifican a alguien."""
    if isinstance(obj, dict):
        return {k: ("" if k in IDENTITY_KEYS else scrub(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


def _scrub_3(cache):
    """Esquema 2 -> 3: la última selección (last_session.json) y las muestras de la partida en vivo guardaban los nombres e
    identificadores de tus compañeros y rivales. Solo sirven para depurar: se limpian los que ya hay."""
    files = [os.path.join(cache, "last_session.json")] + [os.path.join(cache, "live_samples", f)
                                                          for f in (os.listdir(os.path.join(cache, "live_samples")) if os.path.isdir(os.path.join(cache, "live_samples")) else [])]
    n = 0
    for p in files:
        d = read_json(p, None) if p.endswith(".json") else None
        if d is not None:
            write_json(p, scrub(d))
            n += 1
    diag(f"Migración de privacidad: {n} archivos de depuración sin nombres ni identificadores")


def _roles_1(cache):
    """Esquema 1 -> 2: las partidas guardadas como «JUNGLE» con la regla antigua (la etiqueta cruda del cliente) no son de fiar:
    solo 5 de 16 lo eran en los datos reales. Se dejan sin línea ni rival, y las que el cliente aún entrega (sus últimas 200)
    se recalculan solas al conectar. Las más antiguas se quedan sin línea: mejor ninguna que una equivocada."""
    n = 0
    for f in os.listdir(cache):
        if not (f.startswith(("history", "games")) and f.endswith(".json")):
            continue
        path = os.path.join(cache, f)
        data = read_json(path, None)
        if not isinstance(data, dict):
            continue
        changed = False
        for e in data.values():
            if isinstance(e, dict) and e.get("r") == "JUNGLE" and e.get("rv") != history.ROLE_V:
                e["r"] = ""
                if "o" in e:
                    e["o"] = 0
                changed, n = True, n + 1
        if changed:
            write_json(path, data)
    diag(f"Migración de líneas: {n} partidas marcadas como jungla sin comprobar quedan sin línea hasta recalcularse")


SCHEMA = 3   # sube cuando cambie la forma de algún archivo de cache/; MIGRATIONS[n] lleva los datos de la versión n a la n+1
MIGRATIONS = {1: _roles_1, 2: _scrub_3}


def check_schema():
    """cache/schema.json dice con qué versión de datos se escribió la carpeta. Si es anterior, se aplican las migraciones
    pendientes, una a una; si es posterior (se instaló una versión más antigua encima), se avisa en el registro y no se toca."""
    path = os.path.join(CACHE, "schema.json")
    cur = read_json(path, None)
    v = cur.get("v") if isinstance(cur, dict) and isinstance(cur.get("v"), int) else 0
    if v > SCHEMA:
        diag(f"Datos de una versión más nueva (esquema {v}, esta app usa el {SCHEMA}): no se modifican")
        return v
    try:
        for n in range(max(v, 1), SCHEMA):
            MIGRATIONS[n](CACHE)
            diag(f"Datos migrados del esquema {n} al {n + 1}")
        if v != SCHEMA:
            write_json(path, {"v": SCHEMA, "app": APP_VERSION, "t": int(time.time())})
    except Exception:
        log_exc("Migrar los datos guardados")
    return SCHEMA


def note_queue(q):
    """Una cola que LOL-E no conoce cae en «Otros»: se apunta una vez para poder añadirla (la 1740 pasó desapercibida)."""
    if q and q not in _DIAG["queues"] and queue_group(q) == "Otros":
        _DIAG["queues"].add(q)
        diag(f"Cola desconocida: {q} (se agrupa en «Otros»)")


def ally_champs(me, detail):
    """Campeones y puuids de tus compañeros en una partida, a partir del detalle."""
    if not detail:
        return [], []
    ids = {i["participantId"]: (i.get("player") or {}).get("puuid", "") for i in detail.get("participantIdentities", [])}
    mates = [p for p in detail.get("participants", [])
             if p.get("teamId") == me.get("teamId") and p.get("participantId") != me.get("participantId")]
    return [p["championId"] for p in mates], [ids.get(p["participantId"], "") for p in mates if ids.get(p["participantId"])]


def _refresh_old_games(lcu, puuid, gc, limit=60):
    """Recalcula con la regla de líneas actual las partidas de Grieta guardadas que el cliente YA NO lista (a veces solo entrega las
    últimas 20, aunque se le pidan 200): su detalle sí se puede pedir por identificador. Las más recientes primero y, como mucho,
    `limit` por lectura; el resto, en la siguiente. Una partida que ya no existe o en la que no se te reconoce se marca como
    revisada y se deja como está. Devuelve True si cambió algo de `gc`."""
    pend = sorted((k for k, e in gc.items() if isinstance(e, dict) and e.get("q") in SR_QUEUES and e.get("rv") != history.ROLE_V),
                  key=lambda k: -(gc[k].get("t") or 0))
    if not pend or not puuid:
        return False
    hechas, cambian, recs = 0, 0, []
    for gid in pend[:limit]:
        try:
            detail = lcu.get(f"/lol-match-history/v1/games/{gid}")
        except (urllib.error.URLError, ConnectionError, OSError):
            break                                   # el cliente se ha cerrado: se sigue en la próxima lectura
        except Exception:
            log_exc("Releer una partida antigua")
            continue
        e = gc[gid]
        me = history.my_part(detail, puuid) if isinstance(detail, dict) else None
        if me is None:
            gc[gid] = {**e, "rv": history.ROLE_V}
        else:
            role = history.role_of(me)
            allies, mates = ally_champs(me, detail)
            cambian += role != e.get("r")
            gc[gid] = {**e, "r": role, "o": find_opponent(me, detail), "a": allies, "p": mates, "rv": history.ROLE_V}
            rec = history.from_game(detail, puuid)
            if rec:
                recs.append(rec)
        hechas += 1
    if recs:
        history.save(history.hpath(CACHE), recs)
    diag(f"Partidas antiguas recalculadas con su detalle: {hechas} de {len(pend)} pendientes, {cambian} con otra línea")
    return hechas > 0


def load_player_data(lcu, season=None):
    """Maestría, historial, enfrentamientos, parejas de campeones, modos y perfil. Todo desde el cliente, sin claves."""
    P = {"mastery": {}, "stats": {}, "rstats": {}, "matchups": {}, "opp": {}, "pairs": {}, "modes": {}, "mates": {}, "aram": {}, "owned": set(),
         "season": (season or {}).get("champs", {}), "ladder": (season or {}).get("ladder"), "form": [], "games": 0, "rank": "", "record": "", "profile": {}}
    try:
        for m in lcu.get("/lol-champion-mastery/v1/local-player/champion-mastery") or []:
            P["mastery"][m["championId"]] = m["championPoints"]
    except Exception:
        soft_fail("Leer tus maestrías")
    try:
        P["owned"] = {c["id"] for c in lcu.get("/lol-champions/v1/owned-champions-minimal") or []}
        if not P["owned"]:   # recién abierto, el cliente contesta vacío un rato (visto en una prueba real): se reintenta
            diag("Campeones en propiedad: el cliente aún no los da; hasta que lleguen se cuentan todos como tuyos")
    except Exception:
        soft_fail("Leer tus campeones")
    # El cliente solo devuelve las ultimas partidas: las guardamos en disco para acumular historial.
    gc = None  # gameId -> {c: campeon, w: victoria, r: rol, o: rival de linea, q: cola, t: fecha, a: aliados}
    dirty = False
    try:  # tu puuid: con él se localiza tu jugador en cada partida (nunca «el primero de la lista»)
        P["puuid"] = (lcu.get("/lol-summoner/v1/current-summoner") or {}).get("puuid", "")
    except Exception:
        P["puuid"] = ""
    P["hist_ok"] = False   # si el cliente no entregó las partidas se reintenta (antes un fallo aquí pasaba en silencio)
    try:
        if not P["puuid"]:
            # sin saber qué cuenta es no se guarda nada: las partidas irían al archivo de la última cuenta vista (se reintenta)
            raise ConnectionError("cuenta aún desconocida")
        games = lcu.get("/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=200", timeout=40)
        glist = games["games"]["games"]
        how = history.set_account(CACHE, P["puuid"], [g.get("gameId") for g in glist])   # cada cuenta, su archivo
        if how:
            diag(f"Cuenta {P['puuid'][:8]}: " + ("hereda el historial anterior" if how == "migrated" else "historial propio nuevo"))
        gc = read_json(history.gpath(CACHE), {})
        try:
            recs = [history.from_game(g, P["puuid"]) for g in glist]
            history.save(history.hpath(CACHE), [r for r in recs if r])
            diag(f"Historial: el cliente entregó {len(glist)} partidas, {sum(1 for r in recs if r)} reconocidas como tuyas")
        except Exception:
            log_exc("Guardar el historial")
        P["hist_ok"] = True
        for g in glist:
            gid, q = str(g["gameId"]), g.get("queueId")
            e = gc.get(gid)
            # las partidas de Grieta guardadas con otra versión de la regla de líneas se recalculan una vez (el cliente aún
            # las entrega mientras estén entre sus últimas 200); fuera de esa ventana se quedan como las dejó la migración
            stale = q in SR_QUEUES and isinstance(e, dict) and e.get("rv") != history.ROLE_V
            if isinstance(e, dict) and ("p" in e or q not in SR_QUEUES) and not stale:
                continue
            me = history.my_part(g, P["puuid"])
            if me is None:
                continue
            role = history.role_of(me)
            opp, allies, mates = 0, [], []
            if q in SR_QUEUES:  # el detalle (rival de linea y aliados) solo importa en la Grieta
                try:
                    detail = lcu.get(f"/lol-match-history/v1/games/{gid}")
                    opp = find_opponent(me, detail)
                    allies, mates = ally_champs(me, detail)
                except Exception:
                    continue
            if stale and role != e.get("r"):
                diag(f"Partida {gid}: la línea pasa de «{e.get('r') or '?'}» a «{role or '?'}» (regla de líneas v{history.ROLE_V})")
            gc[gid] = {"c": me["championId"], "w": bool(me["stats"]["win"]), "r": role, "o": opp, "q": q,
                       "t": g.get("gameCreation", 0), "a": allies, "p": mates, "rv": history.ROLE_V}
            dirty = True
        if _refresh_old_games(lcu, P["puuid"], gc):
            dirty = True
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        diag(f"Historial sin leer: {type(e).__name__} {e}")   # cliente cerrado o aún arrancando: se reintenta
    except Exception:
        log_exc("Leer las partidas del cliente")
    if gc is None:   # no se llegó a leer el cliente: se enseña lo guardado de la cuenta (la de ahora o la última vista)
        history.set_account(CACHE, P["puuid"])
        gc = read_json(history.gpath(CACHE), {})
    if dirty:
        write_json(history.gpath(CACHE), gc)
    hist = sorted((v for v in gc.values() if isinstance(v, dict)), key=lambda v: v["t"])
    sr = []
    for e in hist:
        note_queue(e["q"])
        grp = queue_group(e["q"])
        m = P["modes"].setdefault(grp, [0, 0, []])
        m[0] += 1; m[1] += e["w"]; m[2].append(e["w"])
        if grp == "ARAM":
            ar = P["aram"].setdefault(e["c"], [0, 0]); ar[0] += 1; ar[1] += e["w"]
        if e["q"] not in SR_QUEUES:
            continue
        sr.append(e)
        champ, win, role, opp = e["c"], e["w"], e["r"], e["o"]
        for d, k in ((P["stats"], champ), (P["rstats"], (champ, role))):
            s_ = d.setdefault(k, [0, 0]); s_[0] += 1; s_[1] += win
        for al in e.get("a", []):
            pr = P["pairs"].setdefault((champ, al), [0, 0]); pr[0] += 1; pr[1] += win
        for pu in e.get("p", []):  # con quien has jugado (companeros de equipo)
            mt = P["mates"].setdefault(pu, [0, 0]); mt[0] += 1; mt[1] += win
        if opp:
            m_ = P["matchups"].setdefault((champ, opp), [0, 0]); m_[0] += 1; m_[1] += win
            o = P["opp"].setdefault(opp, [0, 0]); o[0] += 1; o[1] += not win  # partidas y derrotas contra este rival
    # temporada (op.gg): nos quedamos con lo que tenga mas partidas, el local o el de op.gg
    agg = {}
    for (c, o), (g, w) in (season or {}).get("matchups", {}).items():
        if g > P["matchups"].get((c, o), [0, 0])[0]:
            P["matchups"][(c, o)] = [g, w]
        a = agg.setdefault(o, [0, 0]); a[0] += g; a[1] += g - w
    for o, a in agg.items():
        if a[0] > P["opp"].get(o, [0, 0])[0]:
            P["opp"][o] = a
    P["form"] = [e["w"] for e in sr[-5:]]
    P["games"] = len(sr)
    try:
        P["profile"] = players.load_profile(lcu)
        solo = P["profile"].get("solo")
        if solo:
            P["rank"] = f"{solo['tier']}{' ' + solo['div'] if solo['div'] else ''} · {solo['lp']} PL"
            P["record"] = f"{solo['w']}V · {solo['l']}D" + (f" · {solo['wr']:.0%}" if solo["w"] + solo["l"] else "")
    except Exception:
        soft_fail("Leer tu perfil y tu rango")
    return P


# ---------- Motor de puntuacion ----------
def lean(c):
    """+1 = dano fisico, -1 = dano magico."""
    d = c.get("dmg")
    if d == "PHYSICAL_DAMAGE": return 1.0
    if d == "MAGIC_DAMAGE": return -1.0
    a, m = c["info"]["attack"], c["info"]["magic"]
    return (a - m) / max(a + m, 1)


def lane_share(cid, role):
    """Parte de las partidas de un campeón que se juegan en esa línea según el meta (0 si no hay datos)."""
    try:
        return metamod.lane_shares(META["data"], cid).get(role, 0.0)
    except Exception:
        return 0.0


def role_fit(c, role, cid=None, conf=None):
    if not role:
        return 0.5
    if c.get("pos") and role in c["pos"]:
        return 1.0
    sh = lane_share(cid, role) if cid else 0.0
    if conf is not None and sh * 100 >= getp(conf, "lane_share_min"):
        return 0.6 + min(0.35, sh)  # línea alternativa pero jugada de verdad: casi tan buena como la habitual
    if c.get("pos"):
        return 0.1
    return max((ROLE_TAGS.get(role, {}).get(t, 0) for t in c["tags"]), default=0)


def getp(conf, key):
    """Valor de un umbral: el que hayas fijado o el de por defecto (ver params.py)."""
    return (conf.get("params") or {}).get(key, params.DEFAULT_PARAMS[key])


def score(cid, champs, role, allies, enemies, lane_opp, pend, P, conf, mmax):
    """Puntos de un campeón y su desglose: {factor: puntos}. Todo sale de conf['weights'] y conf['params']."""
    w, c, why = conf["weights"], champs[cid], []
    prior = getp(conf, "winrate_prior")
    parts = {}
    m = P["mastery"].get(cid, 0)
    parts["mastery"] = w["mastery"] * min(m / max(mmax, 1), 1.0)
    if m:
        why.append(f"maestría {m // 1000}k")
    # primero tu historial en este rol; si no hay, lo que tenga mas muestra entre el historial local y la temporada
    g, wins = P["rstats"].get((cid, role)) or max(P["stats"].get(cid, [0, 0]), P["season"].get(cid, [0, 0]))
    parts["winrate"] = w["winrate"] * ((wins + prior / 2) / (g + prior) - 0.5) * 2 if g + prior else 0.0  # suavizado
    if g:
        why.append(f"{wins}/{g} victorias")
    fit = role_fit(c, role, cid, conf)
    if g >= getp(conf, "off_role_games") and fit < 0.5:
        fit = 0.5  # lo has jugado bastante, asumimos que sabes usarlo
    parts["role"] = w["role"] * fit
    if role and fit < 0.5:
        why.append("fuera de tu rol")
    ids = [a for a in allies if a in champs]
    tanks = sum(1 for a in ids if "Tank" in champs[a]["tags"])
    bal = sum(lean(champs[a]) for a in ids)
    comp = 0.0
    if tanks == 0 and "Tank" in c["tags"]:
        comp += 0.6; why.append("te falta un tanque")
    if abs(bal) > 1.0:  # equipo muy cargado a un tipo de dano
        if bal > 0 and lean(c) < -0.2: comp += 0.7; why.append("aporta daño mágico")
        if bal < 0 and lean(c) > 0.2: comp += 0.7; why.append("aporta daño físico")
        if bal > 0 and lean(c) > 0.2: comp -= 0.5
        if bal < 0 and lean(c) < -0.2: comp -= 0.5
    ctrl = [champs[a].get("attr", {}).get("control", 2) for a in ids]
    if ctrl and sum(ctrl) / len(ctrl) < 1.5 and c.get("attr", {}).get("control", 0) >= 3:
        comp += 0.5; why.append("aporta control")
    parts["comp"] = w["comp"] * comp
    if pend >= 2 and len(c.get("pos", [])) >= 2:  # quedan picks rivales: un campeon flexible no revela tu linea
        parts["comp"] += 0.3; why.append("pick flexible")
    ebal = sum(lean(champs[e]) for e in enemies if e in champs)
    if ebal > 1.0 and c["info"]["defense"] >= 7:
        parts["comp"] += 0.5; why.append("resiste su daño físico")
    parts["counter"] = 0.0
    if lane_opp:  # tu historial contra el rival de tu linea
        mg, mw = P["matchups"].get((cid, lane_opp), [0, 0])
        if mg:
            parts["counter"] = w["counter"] * ((mw + 1) / (mg + 2) - 0.5) * 2
            why.append(f"contra {champs[lane_opp]['name']}: {mw}/{mg}")
    return sum(parts.values()), why, parts


def ban_suggestions(champs, P, taken, n, conf=None):
    """Rivales de linea contra los que mas has perdido (umbrales en params.py)."""
    mg, ml = (getp(conf, "ban_games"), getp(conf, "ban_loss") / 100) if conf else (2, 0.6)
    cand = [(l, g, o) for o, (g, l) in P["opp"].items()
            if g >= mg and l / g >= ml and o in champs and o not in taken]
    cand.sort(reverse=True)
    return [(champs[o]["name"], g - l, g, o) for l, g, o in cand[:n]]


def my_turn(session):
    me = session["localPlayerCellId"]
    for group in session.get("actions", []):
        for a in group:
            if a.get("actorCellId") == me and a.get("isInProgress") and not a.get("completed"):
                return a.get("type")  # "ban" o "pick"
    return None


def comp_stats(ids, champs, tips=False):
    ids = [i for i in ids if i in champs]
    if not ids:
        return None
    ad = sum(1 for i in ids if lean(champs[i]) > 0.2)
    ap = sum(1 for i in ids if lean(champs[i]) < -0.2)
    tip = ""
    if tips and ad >= 3 and ap == 0: tip = "Solo daño físico: compra armadura"
    elif tips and ap >= 3 and ad == 0: tip = "Solo daño mágico: compra resistencia mágica"
    return {"ad": ad, "ap": ap, "tanks": sum(1 for i in ids if "Tank" in champs[i]["tags"]),
            "cc": sum(champs[i].get("attr", {}).get("control", 2) for i in ids) / len(ids), "tip": tip}


def champ_record(P, cid, role):
    """[partidas, victorias] de un campeon: primero tu historial en este rol, si no, lo que tenga mas muestra."""
    return P["rstats"].get((cid, role)) or max(P["stats"].get(cid, [0, 0]), P["season"].get(cid, [0, 0]))


def build_tips(c, ens, als):
    """Consejos de construccion segun la composicion. Son orientativos: no sustituyen a la build del parche."""
    tips = []
    lean_ = lean(c)
    if lean_ > 0.2:
        tips.append(("Tu daño", "Es sobre todo físico: prioriza el daño de ataque y, si el rival lleva tanques, la penetración de armadura."))
    elif lean_ < -0.2:
        tips.append(("Tu daño", "Es sobre todo mágico: prioriza el poder de habilidad y la penetración mágica."))
    else:
        tips.append(("Tu daño", "Es mixto o depende de la construcción: elige según lo que más te funcione en la partida."))
    if ens:
        if ens["ad"] >= 3 and ens["ap"] <= 1:
            tips.append(("Defensa", "El rival hace mucho daño físico: añade armadura, empezando por las botas."))
        elif ens["ap"] >= 3 and ens["ad"] <= 1:
            tips.append(("Defensa", "El rival hace mucho daño mágico: añade resistencia mágica."))
        elif ens["ad"] + ens["ap"] >= 3:
            tips.append(("Defensa", "El rival tiene daño mixto: combina vida con una defensa equilibrada."))
        if ens["cc"] >= 2.3:
            tips.append(("Control", "Hay mucho control en el rival: valora la tenacidad o algo que te limpie los controles."))
        if ens["tanks"] >= 2:
            tips.append(("Tanques rivales", "Hay varios tanques: la penetración y el daño porcentual rinden más."))
    else:
        tips.append(("Rivales", "Cuando los rivales elijan, aquí verás consejos adaptados a su composición."))
    if als and als["tanks"] == 0 and "Tank" in c["tags"]:
        tips.append(("Tu equipo", "No tiene tanque: serás la primera línea, así que prioriza vida y resistencias."))
    return tips


TRENDS = {"data": None}  # picks en auge (parche anterior y Corea), en segundo plano
META = {"data": None, "error": ""}  # meta del parche, se rellena en segundo plano


def is_off_role(champs, cid, role, P, conf):
    """Fuera de rol: la línea no es de ese campeón y tú tampoco lo has jugado ahí las veces necesarias."""
    if not role:
        return False
    c = champs[cid]
    ok = (role in c["pos"]) if c.get("pos") else role_fit(c, role) >= 0.5
    ok = ok or lane_share(cid, role) * 100 >= getp(conf, "lane_share_min")  # se juega ahí de verdad, aunque no sea su línea habitual
    return (not ok) and P["rstats"].get((cid, role), [0, 0])[0] < getp(conf, "off_role_games")


def detect_mode(lcu):
    """Tipo de partida: la Grieta (con roles y bans), ARAM u otro modo (Arena, personalizadas...). Sin dato, se asume la Grieta."""
    qid, gm, custom = 0, "", False
    try:
        gf = lcu.get("/lol-gameflow/v1/session") or {}
        gd = gf.get("gameData") or {}
        q = gd.get("queue") or {}
        qid = q.get("id", 0) or 0
        gm = str(q.get("gameMode") or (gf.get("map") or {}).get("gameMode") or "").upper()
        custom = bool(gd.get("isCustomGame"))
    except Exception:
        soft_fail("Detectar el modo de la partida")
    if custom:  # personalizadas: sin roles asignados; solo las de ARAM tienen banquillo
        return {"id": qid, "group": "Personalizada", "kind": "aram" if gm in ("ARAM", "KIWI") else "other"}
    if gm == "CHERRY":
        return {"id": qid, "group": "Arena", "kind": "other"}
    grp = queue_group(qid) if qid else ""
    return {"id": qid, "group": grp, "kind": "sr" if (not qid or qid in SR_QUEUES) else "aram" if grp == "ARAM" else "other"}


def sanitize_session(s):
    """Rellena lo que falte en la sesión del cliente (cada modo trae campos distintos) para que nada falle más adelante."""
    s = dict(s or {})

    def team(t):
        out = []
        for i, p in enumerate(t or []):
            if isinstance(p, dict):
                out.append({**p, "cellId": p.get("cellId", i), "championId": p.get("championId") or 0})
        return out
    s["myTeam"], s["theirTeam"] = team(s.get("myTeam")), team(s.get("theirTeam"))
    b = s.get("bans") if isinstance(s.get("bans"), dict) else {}
    s["bans"] = {"myTeamBans": list(b.get("myTeamBans") or []), "theirTeamBans": list(b.get("theirTeamBans") or [])}
    t = s.get("timer") if isinstance(s.get("timer"), dict) else {}
    s["timer"] = {**t, "phase": t.get("phase") or "", "adjustedTimeLeftInPhase": t.get("adjustedTimeLeftInPhase") or 0,
                  "totalTimeInPhase": t.get("totalTimeInPhase") or 0}
    s["actions"] = [[a for a in g if isinstance(a, dict)] for g in (s.get("actions") or []) if isinstance(g, list)]
    # en varias colas (clasificatorias de 5, Clash) el cliente deja los bans en las acciones y no en "bans": se pasan a su sitio
    for grp in s["actions"]:
        for a in grp:
            cid = a.get("championId") or 0
            if a.get("type") == "ban" and a.get("completed") and cid > 0:
                lst = s["bans"]["myTeamBans" if a.get("isAllyAction") else "theirTeamBans"]
                if cid not in lst:
                    lst.append(cid)
    s["benchChampions"] = [b_ for b_ in (s.get("benchChampions") or []) if isinstance(b_, dict)]
    lp = s.get("localPlayerCellId")
    s["localPlayerCellId"] = lp if isinstance(lp, int) else -1
    return s


def my_champion(session):
    """(campeón, confirmado): el que has marcado o bloqueado. Su build se muestra aunque no esté entre las recomendaciones."""
    me_cell = session.get("localPlayerCellId")
    for grp in session.get("actions") or []:
        for a in grp or []:
            if a.get("type") == "pick" and a.get("actorCellId") == me_cell and a.get("championId"):
                return a["championId"], bool(a.get("completed"))
    me = next((p for p in session.get("myTeam") or [] if p.get("cellId") == me_cell), {})
    cid = me.get("championId") or 0
    return (cid, True) if cid else (me.get("championPickIntent") or 0, False)


def _result(session, champs, P, conf, mode, role, allies, enemies, lane_opp, bans, taken, cands, ens, als):
    w = conf["weights"]
    top = [(c["score"], c["cid"], c["why"]) for c in cands if not c["off_role"]][: conf["top_n"]]
    md = META["data"] if (conf.get("meta_enabled", True) and mode["kind"] == "sr") else None
    me_cell = session["localPlayerCellId"]
    mine, locked = my_champion(session)
    return {"mine": mine, "mine_locked": locked, "role": role, "allies": allies, "enemies": enemies, "bans": bans, "cands": cands, "top": top, "mode": mode,
            "lane_opp": lane_opp, "ban_ideas": ban_suggestions(champs, P, taken, conf["ban_n"], conf) if mode["kind"] == "sr" else [],
            "turn": my_turn(session), "ally_stats": als, "enemy_stats": ens,
            "pct_scale": 0.8 * (w["mastery"] + w["winrate"]) if mode["kind"] == "aram" else 0.6 * sum(w.values()),
            "enemy_cells": [{"cell": p["cellId"], "champ": p["championId"] or 0, "puuid": p.get("puuid", ""), "name": p.get("gameName", "")}
                            for p in session["theirTeam"]],
            "ally_cells": [{"cell": p["cellId"], "champ": p["championId"] or p.get("championPickIntent", 0),
                            "role": norm_role(p.get("assignedPosition")), "puuid": p.get("puuid", "")}
                           for p in session["myTeam"] if p["cellId"] != me_cell],
            "meta_info": ({"patch": metamod.public_patch(md["patch"]), "current": metamod.public_patch(md.get("current", md["patch"])),
                           "stale": md.get("current", md["patch"]) != md["patch"], "tier": md["tier"], "tier_name": metamod.TIER_NAMES.get(md["tier"], md["tier"]),
                           "avg": md["avg"].get(metamod.LANES.get(role, ""), 50)} if md else None),
            "mates": {p.get("puuid"): P["mates"].get(p.get("puuid")) for p in session["myTeam"] if P["mates"].get(p.get("puuid"))},
            "party": [], "profile": P["profile"], "weights": dict(w),
            "rank": P["rank"], "record": P["record"], "form": P["form"], "games": P["games"]}


def advise_aram(session, champs, P, conf, mode):
    """ARAM: no hay roles ni bans. Se compara tu campeón con los del banquillo según tus resultados en ARAM."""
    me_cell = session["localPlayerCellId"]
    me = next((p for p in session["myTeam"] if p["cellId"] == me_cell), {})
    mine = me.get("championId") or me.get("championPickIntent", 0)
    bench = [b["championId"] for b in session.get("benchChampions", []) if b.get("championId")]
    allies = [a for a in (p["championId"] or p.get("championPickIntent", 0) for p in session["myTeam"] if p["cellId"] != me_cell) if a]
    enemies = [p["championId"] for p in session["theirTeam"] if p["championId"]]
    ens, als = comp_stats(enemies, champs, True), comp_stats(allies, champs)
    w, prior = conf["weights"], getp(conf, "winrate_prior")
    mmax = max(P["mastery"].values(), default=1)
    cands = []
    for cid in dict.fromkeys(([mine] if mine else []) + bench):
        if cid not in champs:
            continue
        g, wins = P["aram"].get(cid, [0, 0])
        m = P["mastery"].get(cid, 0)
        parts = {"mastery": w["mastery"] * min(m / max(mmax, 1), 1.0),
                 "winrate": w["winrate"] * ((wins + prior / 2) / (g + prior) - 0.5) * 2 if g + prior else 0.0}
        why = ([f"maestría {m // 1000}k"] if m else []) + ([f"{wins}/{g} victorias en ARAM"] if g else ["sin partidas tuyas en ARAM"])
        if cid == mine:
            why.insert(0, "tu campeón actual")
        cands.append({"cid": cid, "score": sum(parts.values()), "why": why, "off_role": False, "meta": None, "parts": parts,
                      "syn": {"score": 0.0, "items": [], "why": []}, "mastery": m, "games": g, "wins": wins,
                      "tags": champs[cid]["tags"], "lane": None, "vs": [], "build": build_tips(champs[cid], ens, als)})
    cands.sort(key=lambda c: -c["score"])
    return _result(session, champs, P, conf, mode, "", allies, enemies, 0, [], set(allies) | set(enemies), cands, ens, als)


def advise(session, champs, P, conf, mode=None):
    """Recomendaciones para la selección actual. Si algo falla en un modo raro, se devuelve un resultado sencillo en vez de fallar."""
    mode = mode or {"id": 0, "group": "", "kind": "sr"}
    session = sanitize_session(session)
    try:
        return _advise(session, champs, P, conf, mode)
    except Exception as e:
        try:
            write_json(os.path.join(CACHE, "error_advise.json"), {"error": f"{type(e).__name__}: {e}", "mode": mode})
        except Exception:
            pass
        if mode["kind"] == "other":
            raise
        mode = {**mode, "kind": "other"}
        return _advise(session, champs, P, conf, mode)


def _advise(session, champs, P, conf, mode):
    if mode["kind"] == "aram":
        return advise_aram(session, champs, P, conf, mode)
    me_cell = session["localPlayerCellId"]
    me = next((p for p in session["myTeam"] if p["cellId"] == me_cell), {})
    role = norm_role(me.get("assignedPosition"))
    allies = [p["championId"] or p.get("championPickIntent", 0) for p in session["myTeam"] if p["cellId"] != me_cell]
    allies = [a for a in allies if a]
    enemies = [p["championId"] for p in session["theirTeam"] if p["championId"]]
    lane_opp = next((p["championId"] for p in session["theirTeam"]
                     if p["championId"] and role and norm_role(p.get("assignedPosition")) == role), 0)
    auto_opp = lane_opp   # el que se deduce solo, por la posición asignada
    forced = conf.get("_opp") or 0   # rival elegido a mano en la ventana (clave con «_»: no se guarda en config.json)
    if forced and forced in enemies:
        lane_opp = forced   # las puntuaciones («contra tu rival», afinidad, orden) se calculan contra ese
    bans = [b for b in session["bans"]["myTeamBans"] + session["bans"]["theirTeamBans"] if b]
    taken = set(allies) | set(enemies) | set(bans)
    if mode["kind"] == "other":  # Arena, Swiftplay...: no tiene sentido recomendar nada
        return _result(session, champs, P, conf, mode, "", allies, enemies, 0, bans, taken, [],
                       comp_stats(enemies, champs, True), comp_stats(allies, champs))
    pool = [c for c in champs if c not in taken and (not P["owned"] or c in P["owned"])]
    mmax = max(P["mastery"].values(), default=1)
    enemy_cells = {p["cellId"] for p in session["theirTeam"]}
    pend = sum(1 for grp in session.get("actions", []) for a in grp
               if a.get("type") == "pick" and not a.get("completed") and a.get("actorCellId") in enemy_cells)
    w = conf["weights"]
    use_meta = conf.get("meta_enabled", True) and META["data"]
    strong, weak = getp(conf, "meta_strong"), getp(conf, "meta_weak")
    lane_key = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "middle", "BOTTOM": "bottom", "SUPPORT": "support"}.get(role)
    ens, als = comp_stats(enemies, champs, True), comp_stats(allies, champs)
    ranked = []
    for cid in pool:
        sc, why, parts = score(cid, champs, role, allies, enemies, lane_opp, pend, P, conf, mmax)
        off = is_off_role(champs, cid, role, P, conf)
        syn = synergy.synergy_for(champs, cid, allies, P["pairs"], lean, role, getp(conf, "pair_games"))
        m = metamod.get(META["data"], role, cid) if use_meta else None
        parts["meta"] = 0.0
        if m:
            parts["meta"] = w.get("meta", 0) * max(-1.0, min(1.0, (m["wr"] - 50) / 4))
            if m["wr"] >= strong:
                why.append(f"meta fuerte ({m['wr']:.1f} %)".replace(".", ","))
            elif m["wr"] <= weak:
                why.append("meta débil")
        if lane_key:
            fl = trends.short_flag(TRENDS["data"], lane_key, cid)
            if fl:
                why.append(fl)
        parts["synergy"] = w.get("synergy", 0) * syn["score"]
        why = why + syn["why"]
        parts["off_role"] = -8.0 if off else 0.0
        if off and "fuera de tu rol" not in why:
            why.append("fuera de tu rol")
        ranked.append((sum(parts.values()), cid, why, off, m, syn, parts))
    ranked.sort(key=lambda x: -x[0])
    inrole = [x for x in ranked if not x[3]][:36]  # los de tu rol, y unos pocos fuera de rol por si quitas ese filtro
    cands = []
    for sc, cid, why, off, m, syn, parts in sorted(inrole + [x for x in ranked if x[3]][:8], key=lambda x: -x[0]):
        g, wv = champ_record(P, cid, role)
        cands.append({"cid": cid, "score": sc, "why": why, "off_role": off, "meta": m, "syn": syn, "parts": parts,
                      "mastery": P["mastery"].get(cid, 0), "games": g, "wins": wv, "tags": champs[cid]["tags"],
                      "lane": (lane_opp, *P["matchups"].get((cid, lane_opp), [0, 0])) if lane_opp else None,
                      "vs": [(e, *P["matchups"][(cid, e)]) for e in enemies if (cid, e) in P["matchups"]],
                      "build": build_tips(champs[cid], ens, als)})
    res = _result(session, champs, P, conf, mode, role, allies, enemies, lane_opp, bans, taken, cands, ens, als)
    res["lane_opp_auto"] = auto_opp   # la ventana lo necesita para ofrecer «Auto» aunque estés viendo otro rival
    return res


def name(cid, champs):
    return champs[cid]["name"] if cid in champs else "-"


def timer_left(session, got_at):
    """Segundos que quedan en la fase, contados desde que recibimos el dato."""
    t = session.get("timer", {})
    left = t.get("adjustedTimeLeftInPhase", 0) / 1000 - (time.time() - got_at)
    return max(0, int(left)), bool(t.get("isInfinite"))


def why_kind(w):
    """Clasifica un motivo para colorearlo: good (verde), bad (rojo), info (azul)."""
    m = re.search(r"(\d+)/(\d+)", w)
    if m and ("victorias" in w or w.startswith("contra ")):
        return "good" if int(m.group(1)) * 2 >= int(m.group(2)) else "bad"
    if w in ("fuera de tu rol", "meta débil"):
        return "bad"
    return "info" if w.startswith("maestría") else "good"


def champ_vs(P):
    """Contra qué rivales has jugado cada campeón: {campeón: [(rival, partidas, victorias)]} (los más jugados primero)."""
    out = {}
    for (c, o), (g, w) in P["matchups"].items():
        out.setdefault(c, []).append((o, g, w))
    return {c: sorted(v, key=lambda x: -x[1])[:8] for c, v in out.items()}


def vs_enemy(P):
    """Con qué campeones tuyos has jugado contra cada rival: {rival: [(tu campeón, partidas, victorias)]}."""
    out = {}
    for (c, o), (g, w) in P["matchups"].items():
        out.setdefault(o, []).append((c, g, w))
    return {o: sorted(v, key=lambda x: -x[1])[:5] for o, v in out.items()}


def player_info(P):
    pool = sorted(((cid, g, w) for cid, (g, w) in P["season"].items() if g >= 5), key=lambda x: -x[1])[:6]
    modes = [{"name": n, "games": P["modes"][n][0], "wins": P["modes"][n][1], "last": P["modes"][n][2][-10:]}
             for n in MODE_ORDER if P["modes"].get(n)]
    return {"rank": P["rank"], "record": P["record"], "form": P["form"], "games": P["games"], "pool": pool,
            "profile": P["profile"], "modes": modes, "owned": sorted(P["owned"]), "ladder": P.get("ladder"), "region": "",
            "opp": {k: list(v) for k, v in P["opp"].items()}, "champ_vs": champ_vs(P), "vs_enemy": vs_enemy(P), "mastery_top": sorted(P["mastery"].items(), key=lambda x: -x[1])[:8], "mastery_all": dict(P["mastery"]), "season": {k: list(v) for k, v in P["season"].items()}, "stats": {k: list(v) for k, v in P["stats"].items()}}


# ---------- Motor: lee el cliente y avisa a la pantalla (ventana o consola) ----------
def start_meta(conf, P, ui, force=False):
    """Carga el meta del parche en un hilo aparte: si tarda o falla, la aplicación sigue igual."""
    if not conf.get("meta_enabled", True) or P is None:
        return

    def go():
        try:
            tier = metamod.tier_for(((P.get("profile") or {}).get("solo") or {}).get("key"))
            META["data"] = metamod.load(CACHE, DD_VERSION or "16.21.1", tier, force)
            META["dirty"] = True
            d = META["data"]
            stale = d.get("current", d["patch"]) != d["patch"]
            ui.status(f"Meta del parche {metamod.public_patch(d['patch'])} cargado ({metamod.TIER_NAMES.get(d['tier'], d['tier'])})"
                      + (f"; el {metamod.public_patch(d['current'])} aún no tiene datos" if stale else ""))
            try:
                TRENDS["data"] = trends.load(CACHE, d["patch"], force, (conf.get("opgg_region") or "").lower())
                META["dirty"] = True
            except Exception:
                soft_fail("Cargar las tendencias del parche")
        except Exception as e:
            META["error"] = str(e)
            ui.status(f"Sin datos de meta: {e}")
    threading.Thread(target=go, daemon=True).start()


def run(conf, champs, ui):
    season = load_season(champs)
    lcu = P = None
    last = None
    next_check, next_lobby = 0.0, 0.0
    prev_turn = None
    prev_locked = False
    force_opgg = False
    reload_pending = False
    played = False   # ¿ha empezado de verdad una partida desde la última selección? (si no, se esquivó o se canceló: no hay nada que cerrar)
    rank_before, cur_gid, end_tries = None, None, 0
    import augments   # (aquí dentro: augments importa este módulo)
    mayhem_live, next_probe = False, 0.0
    last_flow = "_"
    next_roster, roster_gid = 0.0, None
    next_hist, hist_tries = 0.0, 0
    party, my_puuid = set(), ""
    mode = None
    ui.status("Abre el cliente de League of Legends…")
    while not ui.stopped():
        try:
            cmd = ui.poll_cmd()
            if cmd == "recalc" and last is not None:
                last = "_force"  # fuerza recalcular con los ajustes nuevos
            elif cmd == "opgg":
                force_opgg = True
            elif cmd == "history" and lcu is not None and P is not None:
                P = load_player_data(lcu, season)  # vuelve a leer las partidas del cliente y las guarda
                getattr(ui, "history_updated", lambda: None)()
            elif cmd == "meta":
                start_meta(conf, P, ui, force=True)
            elif isinstance(cmd, tuple) and cmd[0] == "analysis" and lcu is not None:
                try:
                    getattr(ui, "analysis", lambda *a: None)(str(cmd[1]), analysis.load(lcu, cmd[1], my_puuid, CACHE))
                except (urllib.error.URLError, ConnectionError, OSError):
                    getattr(ui, "analysis", lambda *a: None)(str(cmd[1]), None)
                except Exception:
                    log_exc("Análisis de la partida")
                    getattr(ui, "analysis", lambda *a: None)(str(cmd[1]), None)
            if P is not None:  # tu puuid se refresca tras cada lectura (si el cliente aún no lo daba al conectar, llega después)
                my_puuid = (P.get("profile") or {}).get("puuid") or P.get("puuid") or my_puuid
            if META.pop("dirty", False) and last is not None:
                last = "_force"  # llego el meta: recalcular
            if lcu is None:
                found = find_client(conf)
                if not found:
                    time.sleep(3); continue
                lcu = LCU(*found)
                diag("Cliente de LoL encontrado")
                ui.status("Conectado. Cargando tus datos…")
                detect_account(lcu, conf)
                season = load_season(champs, conf)
                ui.link(True)
                P = load_player_data(lcu, season)  # precarga (la primera vez descarga el historial)
                my_puuid = (P.get("profile") or {}).get("puuid", "")
                diag(f"Conectado: cuenta {(my_puuid or P.get('puuid') or '?')[:8]}, historial {'leído' if P.get('hist_ok') else 'pendiente'}, "
                     f"{P.get('games', 0)} partidas de Grieta guardadas")
                ui.idle(player_info(P), "Conectado al cliente. Entra en una cola cuando quieras.")
                ui.status("" if P.get("hist_ok") else "Conectado. El historial aún no ha llegado; se vuelve a pedir solo.")   # «Cargando tus datos…» ya no es verdad
                getattr(ui, "history_updated", lambda: None)()   # puede ser otra cuenta: el historial en pantalla se relee
                start_meta(conf, P, ui)
            if time.time() >= next_lobby:  # quien va contigo en la sala (duo o grupo)
                next_lobby = time.time() + 3
                pp = players.lobby_party(lcu, my_puuid)
                if pp is not None:
                    party = pp
            session = lcu.get("/lol-champ-select/v1/session")
            session = sanitize_session(session) if session else session
            if not session:
                try:
                    flow = lcu.get("/lol-gameflow/v1/gameflow-phase")
                except (urllib.error.URLError, ConnectionError, OSError):
                    raise
                except Exception:
                    flow = None
                in_game = flow in ("InProgress", "GameStart", "Reconnect")  # con la partida en marcha no se toca nada: el PC es del juego
                if in_game:
                    played = True
                if flow != last_flow:
                    if last_flow != "_":  # sonidos por fase (no al conectar con el cliente a medias)
                        if flow == "ReadyCheck":
                            play_phase(conf, "found")
                        elif flow in ("GameStart", "InProgress") and last_flow not in ("GameStart", "InProgress", "Reconnect"):
                            play_phase(conf, "start")
                    diag(f"Fase: {last_flow} -> {flow}")
                    last_flow = flow
                    getattr(ui, "phase", lambda f: None)(flow)
                if last is not None:
                    last = prev_turn = mode = None
                    prev_locked = False
                    reload_pending = True
                    diag("Selección terminada" + (": empieza la partida" if in_game else ""))
                    ui.idle(player_info(P), "Partida en curso. LOL-E espera a que acabe." if in_game else "Selección terminada. Esperando la siguiente…")
                if reload_pending and not in_game and flow != "ChampSelect" and not played:
                    # la selección acabó y NO empezó ninguna partida (esquivada o cancelada). Antes se daba por terminada la partida ANTERIOR:
                    # «Partida terminada», se reanalizaba y, si el rango no se había movido, se esperaba hasta 8 veces y se guardaba «0 PL» para ella
                    reload_pending = False
                    diag("La selección acabó sin empezar partida (esquivada o cancelada): no se analiza nada")
                if reload_pending and not in_game and flow != "ChampSelect" and played:
                    reload_pending = False
                    if rank_before is None:
                        rank_before = {k: (P.get("profile") or {}).get(k) for k in ("solo", "flex", "prem")}
                    P = load_player_data(lcu, season)  # actualiza con la partida que acaba de pasar
                    ui.idle(player_info(P), "Partida terminada. Historial actualizado. Esperando la siguiente…")
                    getattr(ui, "history_updated", lambda: None)()
                    try:  # análisis de la partida que acaba de terminar, listo en la pestaña «Partida»
                        g = (lcu.get("/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=1") or {})["games"]["games"][0]
                        if cur_gid and str(g["gameId"]) != str(cur_gid) and end_tries < 8:
                            # el cliente aún no lista la partida recién terminada: sin esto se analizaba la anterior
                            end_tries += 1
                            reload_pending = True
                            time.sleep(8)
                            continue
                        qkey = {420: "solo", 440: "flex", 710: "prem"}.get(g.get("queueId"))
                        if qkey and rank_before and rank_before.get(qkey):
                            dl = analysis.lp_delta(rank_before[qkey], (P.get("profile") or {}).get(qkey))
                            if dl and dl["d"] == 0 and end_tries < 8:  # el rango tarda un poco más en actualizarse
                                end_tries += 1
                                reload_pending = True
                                time.sleep(8)
                                continue
                            if dl:
                                analysis.save_lp(CACHE, g["gameId"], dl)
                        diag(f"Partida terminada: {g['gameId']} (cola {g.get('queueId')}), esperas {end_tries}")
                        rank_before, cur_gid, end_tries, played = None, None, 0, False
                        getattr(ui, "analysis", lambda *a: None)(str(g["gameId"]), analysis.load(lcu, g["gameId"], my_puuid, CACHE))
                    except (urllib.error.URLError, ConnectionError, OSError):
                        raise
                    except Exception:
                        log_exc("Análisis al terminar la partida")
                if in_game and time.time() >= next_roster:
                    next_roster = time.time() + 3
                    try:  # pantalla de carga: quién juega la partida (los 10), con su rango y su forma; se lee una vez por partida
                        gfr = lcu.get("/lol-gameflow/v1/session") or {}
                        gid_r = (gfr.get("gameData") or {}).get("gameId")
                        ros = players.game_roster(gfr, my_puuid) if gid_r and gid_r != roster_gid else None
                        if gid_r and gid_r != roster_gid and not ros:
                            diag(f"Jugadores de la partida {gid_r}: aún sin datos del cliente o sin saber cuál es tu equipo (cuenta {'conocida' if my_puuid else 'DESCONOCIDA'})")
                        if ros:
                            roster_gid = gid_r
                            diag(f"Jugadores de la partida {gid_r}: {len(ros)} leídos, {sum(1 for x in ros if not x['puuid'])} con perfil oculto, "
                                 f"{sum(1 for x in ros if not x['cid'])} sin campeón, {sum(1 for x in ros if not x['role'])} sin línea")
                            getattr(ui, "roster", lambda *a: None)(ros)
                            threading.Thread(target=players.fetch_roster, args=(lcu, ros, getattr(ui, "roster_players", lambda d: None), getattr(ui, "roster_progress", None)), daemon=True).start()
                    except (urllib.error.URLError, ConnectionError, OSError):
                        raise
                    except Exception:
                        log_exc("Jugadores de la partida")
                if in_game:
                    try:  # API de partida en vivo del juego: marcador, objetos y estado de los 10 jugadores (y, en Mayhem, tus mejoras)
                        if time.time() >= next_probe:
                            live_on = conf.get("live_enabled", True)
                            snap = augments.fetch_live() if (live_on or mayhem_live) else None
                            next_probe = time.time() + (10 if live_on else 20)
                            if snap:
                                if live_on:
                                    summary = live.summarize(snap, champs)
                                    if summary:
                                        getattr(ui, "live", lambda d: None)(summary)
                                if mayhem_live:   # se guarda lo que traiga para poder mejorarlo
                                    got = augments.live_probe(conf, snap)
                                    if got:
                                        getattr(ui, "live_augments", lambda f: None)(augments.flat_live([v for _, v in got]))
                    except Exception:
                        soft_fail("Leer los datos de la partida en vivo")
                    try:  # id de la partida en curso: luego se espera a que el cliente la liste en el historial
                        gfs = (lcu.get("/lol-gameflow/v1/session") or {}).get("gameData", {})
                        cur_gid = gfs.get("gameId") or cur_gid
                        mayhem_live = (gfs.get("queue") or {}).get("id") in augments.MAYHEM_QUEUES
                    except (urllib.error.URLError, ConnectionError, OSError):
                        raise
                    except Exception:
                        soft_fail("Leer la partida en curso")
                    time.sleep(5); continue
                if (not P.get("hist_ok") or not my_puuid or not P.get("owned")) and hist_tries < 12 and time.time() >= next_hist:
                    # el historial, tu cuenta o tus campeones no llegaron (cliente aún iniciando sesión): reintentar
                    next_hist, hist_tries = time.time() + 30, hist_tries + 1
                    P = load_player_data(lcu, season)
                    if P.get("hist_ok") and P.get("owned"):
                        hist_tries = 0
                        ui.idle(player_info(P), "Historial cargado.")
                        getattr(ui, "history_updated", lambda: None)()
                if time.time() >= next_check or force_opgg:  # fuera de seleccion: toca revisar op.gg
                    next_check = time.time() + 300
                    new = maybe_update_opgg(conf, champs, P, force_opgg)
                    force_opgg = False
                    if OPGG_MSG:
                        ui.status(OPGG_MSG)
                    if new:
                        season = new
                        P = load_player_data(lcu, season)
                        ui.idle(player_info(P), "Estadísticas de op.gg actualizadas.")
                time.sleep(2); continue
            key = json.dumps([session["myTeam"], session["theirTeam"], session["bans"],
                              session["timer"]["phase"], session.get("actions")], sort_keys=True)
            if key != last:
                if last is None:
                    played = False   # selección nueva
                    P = load_player_data(lcu, season)
                    mode = detect_mode(lcu)  # la Grieta, ARAM u otro modo: cambia lo que tiene sentido mostrar
                    diag(f"Selección de campeón: cola {mode['id']}, tipo {mode['kind']}")
                    note_queue(mode["id"])
                    if mode["kind"] == "sr":
                        threading.Thread(target=players.fetch_team, args=(lcu, session, ui.players), daemon=True).start()
                last = key
                write_json(os.path.join(CACHE, "last_session.json"), scrub(session))  # para depurar, sin nombres ni identificadores de nadie
                r = advise(session, champs, P, conf, mode)
                r["party"] = list(party)
                ui.show(session, r)
                if r["turn"] and r["turn"] != prev_turn:
                    play_phase(conf, "ban" if r["turn"] == "ban" else "pick")
                if r.get("mine_locked") and not prev_locked:
                    play_phase(conf, "locked")
                prev_turn, prev_locked = r["turn"], bool(r.get("mine_locked"))
            time.sleep(conf["poll_seconds"])
        except KeyboardInterrupt:
            break
        except (urllib.error.URLError, ConnectionError, OSError):
            if lcu is not None:
                diag("Cliente de LoL perdido (cerrado o reiniciando)")
            lcu = None  # el cliente se cerro o reinicio
            ui.link(False)
            ui.status("No encuentro el cliente de LoL. Reintentando…")
            time.sleep(3)
        except Exception as e:  # un fallo puntual no debe tumbar el programa
            log_exc("Bucle principal")
            diag(f"Fallo en el bucle: {type(e).__name__} {e}")
            ui.status(f"Algo ha fallado al leer el cliente ({type(e).__name__}); se reintenta. El detalle está en Ajustes › «Abrir el registro de errores».")
            time.sleep(2)


# ---------- Pantalla 1: consola con colores ----------
ANSI = {"r": "\033[91m", "g": "\033[92m", "y": "\033[93m", "b": "\033[94m", "m": "\033[95m", "c": "\033[96m",
        "d": "\033[90m", "B": "\033[1m", "0": "\033[0m"}
KIND_ANSI = {"good": "g", "bad": "r", "info": "b"}


def paint(txt, *codes):
    return "".join(ANSI[c] for c in codes) + str(txt) + ANSI["0"]


def cbar(frac, width=14, color="g"):
    n = int(round(max(0.0, min(1.0, frac)) * width))
    return paint("█" * n, color) + paint("░" * (width - n), "d")


class ConsoleUI:
    def __init__(self, champs):
        self.champs = champs
        os.system("")  # activa los colores ANSI en la consola de Windows 10

    def stopped(self):
        return False

    def link(self, ok):
        pass

    def players(self, data):
        pass

    def poll_cmd(self):
        return None

    def status(self, text):
        if text:
            print(paint(text, "d"))

    def _clear(self):
        os.system("cls" if os.name == "nt" else "clear")

    def _head(self, rank, form, games):
        racha = " ".join(paint("V", "g", "B") if w else paint("D", "r", "B") for w in form) or "-"
        tilt = paint("  !! 3 derrotas seguidas: cuidado con el tilt", "y", "B") if form[-3:] == [False] * 3 else ""
        return f"{paint(rank or 'Sin rango', 'y', 'B')}  | racha {racha}  | {games} partidas guardadas{tilt}"

    def idle(self, info, msg):
        self._clear()
        print(self._head(info["rank"], info["form"], info["games"]))
        print("\n" + paint(msg, "B"))
        if info["pool"]:
            print("\n" + paint("Tu repertorio de la temporada:", "d"))
            for cid, g, w in info["pool"]:
                wr = w / g
                print(f"  {name(cid, self.champs):<14} {cbar(wr, 10, 'g' if wr >= .5 else 'r')} {w}/{g} ({wr:.0%})")

    def _comp(self, st):
        if not st:
            return ""
        tot = st["ad"] + st["ap"] or 1
        line = f"   AD {paint('█' * st['ad'], 'y')}{paint('█' * st['ap'], 'b')} AP   {st['ad']}/{st['ap']}  tanques {st['tanks']}  CC {st['cc']:.1f}"
        return line + (paint(f"  -> {st['tip']}", "y", "B") if st["tip"] else "")

    def show(self, session, r):
        ch = self.champs
        self._clear()
        secs = int(session["timer"].get("adjustedTimeLeftInPhase", 0) / 1000)
        print(self._head(r["rank"], r["form"], r["games"]))
        print(paint(f"\n SELECCIÓN · {session['timer']['phase']} · rol {r['role'] or '?'} · {secs}s al refrescar ", "B", "c"))
        if r["turn"]:
            col = "r" if r["turn"] == "ban" else "g"
            print(paint(f"\n >>> ES TU TURNO DE {'BAN' if r['turn'] == 'ban' else 'PICK'} <<< ", "B", col))
        print("\n" + paint("Aliados ", "g", "B") + (", ".join(name(c, ch) for c in r["allies"]) or "-"))
        print(self._comp(r["ally_stats"]))
        print(paint("Rivales ", "r", "B") + (", ".join(name(c, ch) for c in r["enemies"]) or "-"))
        print(self._comp(r["enemy_stats"]))
        print(paint("Bans    ", "d", "B") + (", ".join(name(c, ch) for c in r["bans"]) or "-"))
        if r["turn"] == "ban" or session["timer"]["phase"] == "PLANNING":
            ideas = ", ".join(f"{n} ({w}/{g})" for n, w, g, _ in r["ban_ideas"])
            print("\n" + paint("Ban sugerido ", "r", "B") + (ideas or paint("sin datos suficientes todavía", "d")))
        print("\n" + paint("RECOMENDADO", "y", "B"))
        best = max((t[0] for t in r["top"]), default=1) or 1
        for i, (sc, cid, why) in enumerate(r["top"], 1):
            tags = "  ".join(paint(w[:1].upper() + w[1:], KIND_ANSI[why_kind(w)]) for w in why) or paint("encaja con el rol", "d")
            print(f" {paint(i, 'y', 'B')} {paint(f'{name(cid, ch):<13}', 'B')} {cbar(sc / best, 14, 'y' if i == 1 else 'b')} {sc:5.1f}  {tags}")


_LOGGED = {}


def log_error(text):
    """Añade una línea al registro de errores (cache/error.log). Se recorta solo cuando pasa de ~400 KB."""
    try:
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, "error.log")
        if os.path.exists(path) and os.path.getsize(path) > 400_000:
            with open(path, encoding="utf-8", errors="replace") as f:
                tail = f.read()[-100_000:]
            with open(path, "w", encoding="utf-8") as f:
                f.write(tail)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {text}\n")
    except Exception:
        pass


def log_exc(where, exc_info=None):
    """Registra una excepción con su traza; el mismo fallo no se repite más de una vez por minuto."""
    import traceback
    try:
        t, v, tb = exc_info or sys.exc_info()
        body = "".join(traceback.format_exception(t, v, tb, limit=8)).strip()
        key = f"{where}|{type(v).__name__}|{v}"
        if time.time() - _LOGGED.get(key, 0) < 60:
            return
        _LOGGED[key] = time.time()
        log_error(f"{where}\n{body}")
    except Exception:
        pass


def install_error_hooks():
    """Cualquier error no controlado (en la ventana o en un hilo) queda en el registro en vez de perderse."""
    sys.excepthook = lambda t, v, tb: log_exc("Error no controlado", (t, v, tb))
    try:
        threading.excepthook = lambda a: log_exc(f"Error en un hilo ({getattr(a.thread, 'name', '?')})", (a.exc_type, a.exc_value, a.exc_traceback))
    except Exception:
        pass


_MUTEX = None


def single_instance():
    """Solo una copia de LOL-E a la vez: si ya hay una abierta, se trae al frente y esta se cierra."""
    global _MUTEX
    try:
        import ctypes
        k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
        _MUTEX = k32.CreateMutexW(None, False, "Local\\LOL-E-instancia-unica")
        if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            hwnd = u32.FindWindowW(None, APP_NAME)
            if hwnd:
                u32.ShowWindow(hwnd, 9)  # SW_RESTORE
                u32.SetForegroundWindow(hwnd)
            return False
    except Exception:
        pass
    return True


def prune_cache(days=21):
    """Borra de la caché lo que lleva semanas sin usarse (builds y enfrentamientos de parches viejos)."""
    for sub, dias in (("builds", days), ("matchups", days), ("live_samples", 14)):   # las muestras en vivo, solo dos semanas
        limit = time.time() - dias * 86400
        d = os.path.join(CACHE, sub)
        try:
            for f in os.listdir(d):
                p = os.path.join(d, f)
                if os.path.isfile(p) and os.path.getmtime(p) < limit:
                    os.remove(p)
        except OSError:
            pass


def diagnostics(extra=None):
    """Informe corto para pedir ayuda: versión, sistema, estado de los datos y últimos errores. Sin nombres ni partidas."""
    import platform
    home = os.path.expanduser("~")
    md = META.get("data") or {}
    try:
        n_games = len(history.load_all(history.hpath(CACHE), history.gpath(CACHE)))
    except Exception:
        n_games = "?"
    try:
        size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(CACHE) for f in fs) / 1e6
    except Exception:
        size = 0
    lines = [f"{APP_NAME} {APP_VERSION} ({'instalada' if FROZEN else 'desde el código'})",
             f"Windows: {platform.platform()}  ·  Python {platform.python_version()}",
             f"Datos: parche de datos {DD_VERSION or '?'}, meta {md.get('patch', 'sin cargar')} ({md.get('tier', '-')}), "
             f"{n_games} partidas guardadas, caché {size:.1f} MB"]
    if extra:
        lines += extra
    try:
        with open(os.path.join(CACHE, "error.log"), encoding="utf-8", errors="replace") as f:
            tail = f.read().splitlines()[-25:]
        lines += ["", "Últimos errores:"] + [x.replace(home, "~") for x in tail]
    except OSError:
        lines += ["", "Sin errores registrados."]
    try:
        with open(os.path.join(CACHE, "diag.log"), encoding="utf-8", errors="replace") as f:
            lines += ["", "Últimos pasos:"] + f.read().splitlines()[-30:]
    except OSError:
        pass
    return "\n".join(lines)


def fatal(text):
    log_error(text)
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk(); root.withdraw()
        messagebox.showerror(APP_NAME, text)
    except Exception:
        print(text)


def migrate_data():
    """La 1.0 guardaba los datos en LoLAdvisor; ahora la carpeta se llama LOL-E."""
    old = os.path.join(os.environ.get("LOCALAPPDATA", ""), "LoLAdvisor")
    if FROZEN and os.path.isdir(old) and not os.path.exists(DATA_DIR):
        try:
            shutil.move(old, DATA_DIR)
        except Exception:
            soft_fail("Mover los datos de la versión antigua")


def seed_cache():
    """Primer arranque: copia los datos que vienen en el instalador (campeones e iconos) para no depender de internet."""
    src = os.path.join(HERE, "seed_cache")
    if not os.path.isdir(src):
        return
    for root, _, files in os.walk(src):
        dst = os.path.join(CACHE, os.path.relpath(root, src))
        os.makedirs(dst, exist_ok=True)
        for f in files:
            if not os.path.exists(os.path.join(dst, f)):
                shutil.copy2(os.path.join(root, f), os.path.join(dst, f))


def main():
    sys.modules.setdefault("lol_advisor", sys.modules[__name__])  # si se lanza como script, que gui.py comparta este modulo
    if "--consola" not in sys.argv and not single_instance():
        return
    install_error_hooks()
    install_certs()
    migrate_data()
    seed_cache()
    check_schema()
    history.load_account(CACHE)   # sin cliente se enseña el historial de la última cuenta vista
    diag(f"--- {APP_NAME} {APP_VERSION} arranca ---")
    threading.Thread(target=prune_cache, daemon=True).start()
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    conf = load_conf()
    try:
        champs = load_champions()
    except SystemExit as e:
        fatal(f"{e}\n\nComprueba tu conexión a internet la primera vez que abras la aplicación.")
        return
    ui = None
    if "--consola" not in sys.argv:
        try:
            from gui import GUI
            ui = GUI(conf, champs)
        except Exception as e:
            log_error(f"No se pudo abrir la ventana: {type(e).__name__}: {e}")
            print(f"No he podido abrir la ventana ({e}); uso la consola.")
    if ui is None:
        print(f"{len(champs)} campeones cargados. Esperando al cliente de LoL…")
        run(conf, champs, ConsoleUI(champs))
        return
    threading.Thread(target=run, args=(conf, champs, ui), daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
