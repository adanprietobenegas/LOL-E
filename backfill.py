"""Analizar en segundo plano las últimas partidas de la Grieta que aún no tienen análisis, para que el objetivo y los patrones no dependan de haber
jugado con LOL-E abierto. Solo LEE el cliente (detalle y línea de tiempo de tus partidas), una partida cada pocos segundos y únicamente fuera de
cola, selección y partida: en cuanto entras en una, se para y sigue otro rato."""
import os
import threading
import urllib.error

import analysis
import history
import patrones

LIMIT = 20       # las más recientes: de más atrás el cliente apenas guarda líneas de tiempo y el patrón mira lo reciente
PAUSE = 4.0      # segundos entre partidas

_idle = threading.Event()   # puesto = fuera de cola, selección y partida
_lock = threading.Lock()
_running = False
_gone = set()               # partidas sin línea de tiempo en el cliente: no se vuelven a pedir hasta reconectar
_fails = {}                 # fallos de red por partida: a la segunda se aparta, para que no tape a las anteriores


def reset():
    """Al reconectar con el cliente: lo que antes falló puede funcionar ahora."""
    _gone.clear()
    _fails.clear()


def set_idle(on):
    (_idle.set if on else _idle.clear)()


def pending(cache_dir, limit=LIMIT):
    """Ids (texto) de las `limit` últimas partidas de la Grieta sin remake que no tienen análisis guardado, de la más reciente a la más antigua."""
    games = history.load_all(history.hpath(cache_dir), history.gpath(cache_dir))
    recent = [g for g in games if g.get("q") in patrones.QUEUES and not g.get("rm") and g.get("t")][:limit]
    return [str(g["id"]) for g in recent
            if str(g["id"]) not in _gone and not os.path.exists(os.path.join(cache_dir, "analysis", f"{g['id']}.json"))]


def run(lcu, puuid, cache_dir, say=lambda t: None, wait=None):
    """Analiza lo pendiente mientras se pueda. Devuelve cuántas partidas nuevas quedaron analizadas."""
    wait = wait or _idle_wait
    done, todo = 0, pending(cache_dir)
    for gid in todo:
        if not _idle.is_set():
            break
        try:
            result = analysis.load(lcu, int(gid), puuid, cache_dir)
        except (urllib.error.URLError, ConnectionError, OSError):
            _fails[gid] = _fails.get(gid, 0) + 1
            if _fails[gid] >= 2:
                _gone.add(gid)
            break   # el cliente se ha cerrado o va muy justo: otro rato
        except Exception as e:
            result = None
            say(f"Análisis en segundo plano: la partida {gid} no se pudo analizar ({type(e).__name__})")
        if result is None:
            _gone.add(gid)
        else:
            done += 1
        if not wait(PAUSE):
            break
    if done:
        patrones._NOW.pop(cache_dir, None)   # el patrón se recalcula ya con lo nuevo
        say(f"Análisis en segundo plano: {done} {'partida nueva' if done == 1 else 'partidas nuevas'} (quedan {len(pending(cache_dir))})")
    return done


def _idle_wait(seconds):
    """Espera entre partidas; False si en ese rato se ha dejado de estar en reposo."""
    end = threading.Event()
    end.wait(seconds)
    return _idle.is_set()


def start(lcu, puuid, cache_dir, say=lambda t: None, finished=lambda n: None):
    """Lanza `run` en un hilo (solo uno a la vez). Devuelve True si lo ha lanzado."""
    global _running
    with _lock:
        if _running or not puuid or not _idle.is_set():
            return False
        _running = True

    def go():
        global _running
        try:
            n = run(lcu, puuid, cache_dir, say)
            if n:
                finished(n)
        except Exception as e:
            say(f"Análisis en segundo plano: fallo ({type(e).__name__} {e})")
        finally:
            _running = False
    threading.Thread(target=go, daemon=True).start()
    return True
