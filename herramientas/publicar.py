"""Prepara una publicación de LOL-E en un solo comando. NO publica: deja el comando de GitHub listo para que lo lance
quien tenga el sí del usuario.

    python herramientas/publicar.py --sin-probar "lo que NO se ha probado"      # comprueba, construye, verifica y prepara
    python herramientas/publicar.py --verificar                                  # después de publicar: espera a que GitHub sirva la versión

Antes de nada hay que haber subido la versión (APP_VERSION, entrada arriba en novedades.py y en NOTAS_DE_VERSION.txt) y
hecho commit y push. Pasos de la preparación, y se para al primer fallo:
  1. no hay partida en curso, el árbol de git está limpio y subido, y la versión no está ya publicada;
  2. la versión coincide en APP_VERSION, novedades.py y NOTAS_DE_VERSION.txt;
  3. herramientas/comprobar_todo.py (pruebas + todas las pantallas + la app entera contra el cliente falso);
  4. build_release.py;
  5. el instalador, el zip y latest.json existen y la huella SHA-256 de latest.json es la del instalador;
  6. escribe release/notas_X.Y.Z.md con las notas de novedades.py y la línea de lo que no se ha probado, y muestra el comando.
`--sin-probar` es obligatorio a propósito: las notas deben decir con honestidad qué falta por ver con el cliente real.
"""
import argparse, hashlib, json, os, re, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
REL = os.path.join(ROOT, "release")
UPDATE_URL = "https://github.com/adanprietobenegas/LOL-E/releases/latest/download/latest.json"
TIPOS = {"nuevo": "Nuevo", "mejora": "Mejora", "arreglo": "Arreglo"}
ACTUALIZAR = ("Si tienes la 1.22.5 o posterior, te llegará sola al abrir LOL-E (fuera de cola, selección y partida). "
              "Con una versión anterior, instala esta a mano una vez: tus datos y ajustes se conservan.")


def notas_markdown(entry, sin_probar):
    """Texto de la publicación a partir de la entrada de novedades.py (título y puntos) y de lo que no se ha probado."""
    lineas = [f"{entry['titulo']}.", ""]
    for tipo, texto in entry["items"]:
        lineas.append(f"- **{TIPOS.get(tipo, tipo.title())}:** {texto}")
    lineas += ["", ACTUALIZAR, "", f"Sin probar todavía: {sin_probar.strip().rstrip('.')}."]
    return "\n".join(lineas) + "\n"


def problemas_de_artefactos(rel, version):
    """Lista de fallos del contenido de release/ para esa versión (vacía si todo está en orden)."""
    malos = []
    exe, zipf, lj = (os.path.join(rel, n) for n in (f"Instalar-LOL-E-{version}.exe", f"LOL-E-{version}.zip", "latest.json"))
    for f in (exe, zipf, lj):
        if not os.path.exists(f):
            malos.append(f"falta {os.path.basename(f)}")
    if malos:
        return malos
    info = json.load(open(lj, encoding="utf-8"))
    if info.get("version") != version:
        malos.append(f"latest.json dice {info.get('version')} y la versión es {version}")
    if info.get("url", "").rsplit("/", 1)[-1] != os.path.basename(exe):
        malos.append("la dirección de latest.json no apunta al instalador de esta versión")
    if info.get("sha256", "").lower() != hashlib.sha256(open(exe, "rb").read()).hexdigest():
        malos.append("la huella SHA-256 de latest.json no es la del instalador")
    if os.path.getsize(exe) < 5_000_000:
        malos.append("el instalador es sospechosamente pequeño")
    return malos


def sh(*cmd, **kw):
    return subprocess.run(list(cmd), capture_output=True, encoding="utf-8", errors="replace", cwd=ROOT, **kw)


def parar(msg):
    print("\nNO SE PUEDE PUBLICAR:", msg)
    sys.exit(1)


def verificar(version):
    """Espera hasta 5 minutos a que la dirección pública que usa el actualizador sirva esta versión."""
    for i in range(10):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{UPDATE_URL}?x={time.time()}", headers={"User-Agent": "LOL-E"}), timeout=20) as r:
                v = json.loads(r.read().decode("utf8")).get("version")
        except Exception as e:
            v = f"error {type(e).__name__}"
        print(f"  {time.strftime('%H:%M:%S')}  el actualizador ve la versión: {v}", flush=True)
        if v == version:
            print(f"\nBIEN: la {version} ya la sirve la dirección de actualizaciones.")
            return 0
        time.sleep(30)
    print("\nLa dirección de actualizaciones aún no sirve esa versión (GitHub puede tardar): vuelve a probar en un rato.")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sin-probar", help="qué NO se ha probado todavía (obligatorio al preparar)")
    ap.add_argument("--verificar", action="store_true", help="solo comprueba que GitHub ya sirve la versión actual")
    ap.add_argument("--ensayo", action="store_true", help="prueba el proceso sin exigir git limpio ni versión sin publicar (para probar esta herramienta)")
    ap.add_argument("--saltar-comprobacion", action="store_true", help="no ejecuta comprobar_todo.py (solo si se acaba de pasar)")
    a = ap.parse_args()
    import lol_advisor as core, novedades
    core.install_certs()   # los mismos certificados que usa la app: la verificación de GitHub falla en algunos Windows sin ellos
    ver = core.APP_VERSION
    if a.verificar:
        sys.exit(verificar(ver))
    if not a.sin_probar:
        ap.error("falta --sin-probar \"...\": las notas deben decir con honestidad qué no se ha visto aún con el cliente real")
    print(f"Preparando la publicación de LOL-E {ver}")

    print("1. Estado")
    if "League of Legends.exe" in sh("tasklist").stdout:
        parar("hay una partida en curso: no se construye ni se sube nada mientras juegas")
    if not a.ensayo:
        if sh("git", "status", "--porcelain").stdout.strip():
            parar("hay cambios sin hacer commit")
        pend = sh("git", "rev-list", "--count", "@{u}..HEAD").stdout.strip()
        if pend not in ("0", ""):
            parar(f"hay {pend} commits sin subir (git push)")
        gh = sh("gh", "release", "view", f"v{ver}") if sh("where", "gh").returncode == 0 else None
        if gh is not None and gh.returncode == 0:
            parar(f"la versión {ver} ya está publicada")
    print("   bien")

    print("2. Versión coherente")
    if novedades.NOTES[0]["v"] != ver:
        parar(f"la entrada de arriba de novedades.py es la {novedades.NOTES[0]['v']} y la versión es la {ver}")
    if f"VERSIÓN {ver}" not in open(os.path.join(ROOT, "docs", "NOTAS_DE_VERSION.txt"), encoding="utf-8").read():
        parar(f"falta «VERSIÓN {ver}» en docs/NOTAS_DE_VERSION.txt")
    print("   bien")

    if not a.saltar_comprobacion:
        print("3. Comprobación completa (unos 7 minutos)")
        r = subprocess.run([sys.executable, os.path.join(HERE, "comprobar_todo.py")], cwd=ROOT, encoding="utf-8", errors="replace",
                           capture_output=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if r.returncode != 0:
            print(r.stdout[-2500:])
            parar("la comprobación completa ha fallado")
        print("   bien")

    print("4. Construcción")
    if "League of Legends.exe" in sh("tasklist").stdout:   # la comprobación dura minutos: se vuelve a mirar justo antes de construir
        parar("ha empezado una partida mientras se comprobaba: no se construye nada hasta que acabe (vuelve a lanzar el comando)")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "build_release.py")], cwd=ROOT, encoding="utf-8", errors="replace",
                       capture_output=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode != 0:
        print(r.stdout[-2500:] + r.stderr[-1500:])
        parar("build_release.py ha fallado")
    print("   bien")

    print("5. Contenido de release/")
    malos = problemas_de_artefactos(REL, ver)
    if malos:
        parar("; ".join(malos))
    print(f"   bien: instalador {os.path.getsize(os.path.join(REL, f'Instalar-LOL-E-{ver}.exe')) / 1e6:.1f} MB, huella correcta")

    notas = os.path.join(REL, f"notas_{ver}.md")
    open(notas, "w", encoding="utf-8").write(notas_markdown(novedades.NOTES[0], a.sin_probar))
    print(f"6. Notas escritas en {os.path.relpath(notas, ROOT)}\n")
    print("TODO LISTO. Con el sí del usuario, publicar con:\n")
    print(f'gh release create v{ver} "release\\Instalar-LOL-E-{ver}.exe" "release\\LOL-E-{ver}.zip" "release\\latest.json" '
          f'--title "LOL-E {ver}" --target main --notes-file "release\\notas_{ver}.md"\n')
    print("Y después:  python herramientas/publicar.py --verificar")


if __name__ == "__main__":
    main()
