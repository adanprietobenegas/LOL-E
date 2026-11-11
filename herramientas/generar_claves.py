"""Genera assets/claves.json (el archivo que usa la app) a partir de docs/rediseno/claves_campeones.json (verificado en dos pasadas).

Uso:  python herramientas/generar_claves.py
Solo pasa lo mostrable (confirmadas, corregidas y nuevas), ordenado por importancia, con un tope por campeón. El orden de habilidades
no se copia: la app ya lo trae de Lolalytics en la build.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDEN = ["evolucion", "forma", "acumulacion", "objetos", "aviso", "orden_habilidades"]
TOPE = 6


def main():
    src = json.load(open(os.path.join(ROOT, "docs", "rediseno", "claves_campeones.json"), encoding="utf-8"))
    out = {}
    for k, v in src["campeones"].items():
        cl = [c for c in v.get("claves", []) if (c.get("texto") or "").strip() and c.get("tipo") in ORDEN]
        cl.sort(key=lambda c: ORDEN.index(c["tipo"]))
        if cl:
            out[k] = {"n": v["nombre"], "c": [[c["tipo"], c["texto"].strip()] for c in cl[:TOPE]]}
    data = {"patch": "26.22", "verificado": "2026-11-11", "champs": out}
    path = os.path.join(ROOT, "assets", "claves.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(out)} campeones, {sum(len(x['c']) for x in out.values())} claves, {os.path.getsize(path) // 1024} KB -> {path}")


if __name__ == "__main__":
    main()
