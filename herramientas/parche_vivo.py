"""Comprueba, contra la web real de Riot, que las últimas notas del parche en español se siguen reconociendo.

    python herramientas/parche_vivo.py

Descarga la lista de versiones y las notas de la última (a una carpeta temporal, sin tocar la caché de la app) y comprueba que salen secciones, fichas de
campeón con cambios «antes ⇒ después» y errores corregidos. Si Riot cambia su web, falla aquí y no el día que el usuario abra la pantalla «Parche».
Sin conexión no es un fallo: lo dice y termina bien (la comprobación no puede saber nada). Termina con «parche en vivo: bien» o «parche en vivo: MAL …»."""
import os
import sys
import tempfile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)
import parche

tmp = tempfile.mkdtemp(prefix="lole-parche-")
try:
    vs = parche.versions(tmp, force=True)
except Exception as e:
    vs = []
if not vs:
    print("parche en vivo: sin conexión o sin lista de versiones; no se puede comprobar (no es un fallo)")
    sys.exit(0)
try:
    d = parche.load(tmp, vs[0], latest=vs[0], force=True)
except Exception as e:
    print(f"parche en vivo: MAL: no se pudieron leer las notas de {vs[0]}: {e!r}")
    sys.exit(1)
kinds = {s["kind"]: s for s in d["sections"]}
champs = [e for s in d["sections"] if s["kind"] == "champions" for g in s["groups"] for e in g["entries"] if e["kind"] == "champion"]
lines = sum(len(b["lines"]) for e in champs for b in e["blocks"])
changes = sum(1 for e in champs for b in e["blocks"] for ln in b["lines"] if ln["before"])
problemas = []
if d["v"] != vs[0]:
    problemas.append(f"la versión leída ({d['v']}) no es la pedida ({vs[0]})")
if len(d["sections"]) < 3:
    problemas.append(f"solo {len(d['sections'])} secciones")
if "champions" not in kinds or len(champs) < 3:
    problemas.append(f"solo {len(champs)} campeones en la sección Campeones")
if changes < 3:
    problemas.append(f"solo {changes} cambios «antes ⇒ después» (de {lines} líneas)")
if not d["summary"] or not d["date"]:
    problemas.append("sin resumen o sin fecha")
print(f"parche {d['v']}: {len(d['sections'])} secciones, {len(champs)} campeones, {changes} cambios numéricos")
print("parche en vivo: " + ("bien" if not problemas else "MAL: " + "; ".join(problemas)))
sys.exit(0 if not problemas else 1)
