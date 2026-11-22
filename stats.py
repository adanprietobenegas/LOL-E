"""Cuenta de instalaciones, VOLUNTARIA y ANÓNIMA (apagada de fábrica): solo para que quien mantiene LOL-E sepa cuánta gente la usa y desde qué zona aproximada.

Qué se envía (y NADA más): un identificador aleatorio de esta instalación (se crea al aceptar; no sale de tu nombre, tu cuenta ni tu PC) y la versión de LOL-E. Una vez al día
como mucho y solo si has dicho que sí. La zona (comunidad autónoma o región) la deduce el SERVIDOR de la conexión, que no guarda la dirección IP. No se envía nada de tus
partidas, tu cuenta de LoL, tus ajustes ni tu ordenador. Se puede apagar en Ajustes cuando quieras y, al apagarla, el servidor borra el registro de esa instalación.

Mientras `STATS_URL` esté vacío (no hay servidor desplegado) esta función no existe: ni se pregunta ni se envía nada. Guía del servidor: servidor/LEEME_DESPLIEGUE.md."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

STATS_URL = "https://lole-stats.aprietob04.workers.dev"   # dirección del servidor (Cloudflare Worker del mantenedor). Vacía = función desactivada.
PING_EVERY = 20 * 3600   # segundos entre avisos
MAX_ASKS = 3             # veces como mucho que se le pregunta a quien responde «Ahora no» (después no se vuelve a preguntar)
ASK_EVERY = 7 * 86400    # segundos entre una pregunta y la siguiente


def enabled(url=None):
    """¿Hay servidor configurado? Sin él no se pregunta nada ni se envía nada. Tampoco en la demostración (datos inventados: no debe contar como una instalación)."""
    try:
        import lol_advisor
        if getattr(lol_advisor, "DEMO_MODE", False):
            return False
    except Exception:
        pass
    return bool((STATS_URL if url is None else url).strip())


def should_ask(conf, now=None):
    """¿Toca enseñar la ventana de permiso? Solo si no ha decidido (None), no se ha agotado el máximo de veces y ha pasado una semana desde la anterior."""
    if not enabled() or conf.get("stats_optin") is not None:
        return False
    if int(conf.get("stats_asked") or 0) >= MAX_ASKS:
        return False
    return (now if now is not None else time.time()) - float(conf.get("stats_ask_t") or 0) >= ASK_EVERY


def more_asks(conf):
    """¿Puede llegar a preguntarse otra vez más adelante? (para decidir si se sigue esperando)"""
    return enabled() and conf.get("stats_optin") is None and int(conf.get("stats_asked") or 0) < MAX_ASKS


def new_id():
    return str(uuid.uuid4())


def payload(conf, version):
    """Exactamente lo que se envía. El servidor añade por su cuenta el país y la región (de la conexión) y no guarda la IP."""
    return {"id": conf.get("stats_id") or "", "v": str(version)}


def describe(conf, version):
    """Texto para el usuario con el contenido literal del aviso."""
    return json.dumps(payload(conf, version), ensure_ascii=False, indent=2)


def due(conf, now=None):
    """¿Toca avisar? Solo con permiso (stats_optin True), con id y pasado el intervalo."""
    if conf.get("stats_optin") is not True or not conf.get("stats_id"):
        return False
    return (now if now is not None else time.time()) - float(conf.get("stats_last") or 0) >= PING_EVERY


def _post(url, path, body, timeout=10):
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "LOL-E"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status == 200


def ping(conf, version, url=None, save=None, now=None):
    """Avisa al servidor si toca. Devuelve True si se envió. Cualquier fallo (sin red, servidor caído) se ignora: se vuelve a intentar más tarde."""
    url = STATS_URL if url is None else url
    if not enabled(url) or not due(conf, now):
        return False
    try:
        ok = _post(url, "/ping", payload(conf, version))
    except (urllib.error.URLError, OSError, ValueError):
        return False
    if ok:
        conf["stats_last"] = now if now is not None else time.time()
        if save:
            save(conf)
    return ok


def forget(conf, url=None):
    """Retirada del permiso: pide al servidor que borre el registro de esta instalación. Devuelve True si lo confirmó (si no, el id local se borra igual)."""
    url = STATS_URL if url is None else url
    ident = conf.get("stats_id") or ""
    if not enabled(url) or not ident:
        return False
    try:
        return _post(url, "/olvidar", {"id": ident})
    except (urllib.error.URLError, OSError, ValueError):
        return False


def admin_url(conf, url=None):
    """Dirección del panel privado del administrador (solo si hay servidor y un `admin_token` en config.json), o ''."""
    url = STATS_URL if url is None else url
    tok = (conf.get("admin_token") or "").strip()
    return f"{url.rstrip('/')}/panel?k={urllib.parse.quote(tok, safe='')}" if enabled(url) and tok else ""   # con símbolos en la clave (&, #…) la dirección sigue valiendo


def admin_summary(conf, url=None, timeout=10):
    """Resumen del panel (dict) o None si no se puede leer. Solo para el administrador (necesita `admin_token`)."""
    url = STATS_URL if url is None else url
    tok = (conf.get("admin_token") or "").strip()
    if not enabled(url) or not tok:
        return None
    req = urllib.request.Request(f"{url.rstrip('/')}/resumen?k={urllib.parse.quote(tok, safe='')}", headers={"User-Agent": "LOL-E"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        return None
