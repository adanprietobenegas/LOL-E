"""Claves del campeón: lo que cambia cómo se compra o se juega y no sale en las builds estadísticas (evoluciones de Kai'Sa y Kha'Zix, acumulaciones
permanentes de Nasus o Veigar, formas de Jayce o Kayn, restricciones y mecánicas de objetos…).

Los datos están en assets/claves.json, generado por herramientas/generar_claves.py desde docs/rediseno/claves_campeones.json (verificado en dos
pasadas con notas de parche de Riot, Data Dragon, CommunityDragon y Lolalytics). Caducan con los parches: el archivo guarda el parche en el que se
verificó y la pantalla avisa cuando el actual es otro.
"""
import json
import os
import sys

TIPOS = {  # tipo -> (etiqueta, color de la etiqueta)
    "evolucion": ("EVOLUCIÓN", "info"),
    "forma": ("FORMA", "good"),
    "acumulacion": ("ACUMULA", "good"),
    "objetos": ("OBJETOS", "warn"),
    "aviso": ("AVISO", "dim"),
    "orden_habilidades": ("ORDEN", "info"),
}
_cache = {}


def _path():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", "claves.json")


def load():
    """El archivo completo ({patch, verificado, champs}); vacío si falta o está roto (la app sigue igual, sin este bloque)."""
    if "d" not in _cache:
        try:
            with open(_path(), encoding="utf-8") as f:
                _cache["d"] = json.load(f)
        except (OSError, ValueError):
            _cache["d"] = {"patch": "", "verificado": "", "champs": {}}
    return _cache["d"]


def for_champ(key):
    """[(tipo, texto)] del campeón (key = id de Data Dragon, p. ej. «MonkeyKing»); lista vacía si no tiene claves."""
    c = load().get("champs", {}).get(key or "")
    return [tuple(x) for x in c["c"]] if c else []


def patch_of(dd_version):
    """Versión de Data Dragon («16.22.1») -> parche del juego («26.22»); cadena vacía si no se entiende."""
    try:
        a, b = str(dd_version).split(".")[:2]
        return f"{int(a) + 10}.{int(b)}"
    except (ValueError, TypeError):
        return ""


def stale(dd_version):
    """El parche actual si es distinto del verificado (los datos pueden haber cambiado); cadena vacía si coincide o no se sabe."""
    cur, ver = patch_of(dd_version), load().get("patch", "")
    return cur if cur and ver and cur != ver else ""
