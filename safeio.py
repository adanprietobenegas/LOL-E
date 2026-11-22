"""Lectura y escritura segura de los datos del USUARIO (historial, PL, partidas con rival, configuración, fotos de rango).

Esos datos no se pueden volver a pedir al cliente (solo entrega las últimas partidas y el rango de ahora), así que perderlos es definitivo. Reglas:
  · Escribir: archivo temporal ÚNICO junto al destino, `flush` + `fsync` y `os.replace`, con un cerrojo por ruta: un corte de luz o dos hilos a la vez no dejan el archivo
    vacío ni entrelazado.
  · Leer: si el archivo existe pero está dañado, NO se sigue como si estuviera vacío (el siguiente guardado lo pisaría): se aparta como `nombre.corrupt-FECHA` y se
    avisa en el resultado. Si no se puede leer por otra causa (antivirus o OneDrive lo tienen bloqueado un instante) se dice «no leído» y quien guarda debe esperar.
Sin dependencias del resto de la app para poder probarlo solo."""
import json, os, threading, time

_locks = {}
_guard = threading.Lock()
KEEP_CORRUPT = 3   # copias apartadas que se conservan por archivo


def _lock(path):
    with _guard:
        return _locks.setdefault(os.path.abspath(path), threading.Lock())


def write(path, data, indent=None):
    """Escribe `data` como JSON de forma atómica y duradera."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with _lock(path):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass


def quarantine(path):
    """Aparta un archivo dañado como `path.corrupt-AAAAMMDD-HHMMSS` (y deja solo las últimas copias). Devuelve la ruta nueva o None."""
    dest = f"{path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
    try:
        os.replace(path, dest)
    except OSError:
        return None
    try:
        d, base = os.path.split(os.path.abspath(path))
        old = sorted(n for n in os.listdir(d) if n.startswith(base + ".corrupt-"))
        for n in old[:-KEEP_CORRUPT]:
            os.remove(os.path.join(d, n))
    except OSError:
        pass
    return dest


def read(path, default=None, kind=dict):
    """(datos, estado): estado «ok», «missing» (no existe: vacío legítimo), «corrupt» (dañado: ya apartado; se devuelve `default`) o «unreadable» (no se pudo leer ahora)."""
    default = {} if default is None else default
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return default, "missing"
    except (ValueError, UnicodeDecodeError):
        quarantine(path)
        return default, "corrupt"
    except OSError:
        return default, "unreadable"
    if kind is not None and not isinstance(d, kind):
        quarantine(path)
        return default, "corrupt"
    return d, "ok"
