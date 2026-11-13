"""Comprobación completa antes de publicar una versión. No necesita el cliente de LoL.

    python herramientas/comprobar_todo.py

Ejecuta, en este orden, y se para al primer fallo:
  1. las pruebas unitarias,
  2. un recorrido por TODAS las pantallas con la ventana real (a 560 y a 1340 px de ancho), sin guardar imágenes:
     cualquier error al pintar, de la ventana o registrado, cuenta como fallo,
  3. la app entera (ventana + bucle principal) contra el cliente falso: cola, selección, partida y fin; en la Grieta y en ARAM (con datos en vivo).
Tarda unos 10 minutos y abre la ventana en el monitor secundario. Con una partida en curso se niega a empezar.
"""
import os, subprocess, subprocess as sp, sys, time
D = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

if "League of Legends.exe" in sp.run(["tasklist"], capture_output=True, text=True, errors="replace").stdout:
    print("Hay una partida en curso: no se lanza una comprobación pesada. Espera a que acabe.")
    sys.exit(3)


def paso(nombre, cmd, extra_env=None, bien=lambda salida: True):
    t = time.time()
    print(f"\n=== {nombre} ===", flush=True)
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", env={**ENV, **(extra_env or {})}, timeout=900)   # los hijos escriben UTF-8
    salida = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and bien(salida)
    malos = [l for l in salida.splitlines() if any(k in l for k in ("ERROR", "FALLA", "Traceback", "errores de ventana: 1", "FAIL"))]
    print(f"  {'bien' if ok else 'MAL '}  ({time.time() - t:.0f} s)", flush=True)
    if not ok:
        print("\n".join(("  " + l)[:200] for l in (malos or salida.splitlines()[-15:])[:25]))
        print("\nLA COMPROBACIÓN HA FALLADO en:", nombre)
        sys.exit(1)
    return salida


paso("Pruebas unitarias", [PY, os.path.join(D, "tests_unitarios.py")], bien=lambda s: "\nOK" in s)
for ancho in (560, 1340):
    paso(f"Todas las pantallas a {ancho} px", [PY, os.path.join(D, "capturas.py"), str(ancho), "730", f"comprobacion_{ancho}"],
         {"LOLE_SINFOTO": "1", "LOLE_PAGINAS": "2"}, bien=lambda s: "errores: 0" in s)
paso("La app entera contra el cliente falso", [PY, os.path.join(D, "demo_falso.py"), "5", "comprobacion_demo"],
     bien=lambda s: "errores de ventana: 0 | registro de errores: vacío" in s and "Partida terminada" in s)
paso("La app entera contra el cliente falso, en ARAM", [PY, os.path.join(D, "demo_falso.py"), "5", "comprobacion_demo_aram"], {"LOLE_MODO": "aram"},
     bien=lambda s: "errores de ventana: 0 | registro de errores: vacío" in s and "Partida terminada" in s)
print("\nTODO BIEN: se puede publicar (si el usuario lo confirma).")
