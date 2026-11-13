"""Foto del estado REAL del proyecto, para empezar una conversación nueva en un minuto.

    python herramientas/estado.py              # versión, qué está publicado y qué no, git, cliente, instalación del usuario, documentos
    python herramientas/estado.py --pruebas    # además ejecuta las pruebas unitarias y dice cuántas pasan

Solo lee: no cambia nada. Complementa a docs/CONTINUAR.md (que cuenta el porqué): esto cuenta el qué hay ahora.
"""
import json, os, re, subprocess, sys, time, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def sh(*cmd, timeout=60):
    try:
        r = subprocess.run(list(cmd), capture_output=True, encoding="utf-8", errors="replace", cwd=ROOT, timeout=timeout)
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return 1, f"({type(e).__name__})"


def linea(titulo, valor):
    print(f"  {titulo:<26} {valor}")


def main():
    import lol_advisor as core
    core.install_certs()
    ver = core.APP_VERSION
    print(f"\n=== LOL-E · estado del proyecto ({time.strftime('%d/%m/%Y %H:%M')}) ===\n")

    print("Versión")
    linea("En el código:", ver)
    rc, out = sh("gh", "release", "list", "--limit", "1", "--json", "tagName,publishedAt", "-q", ".[0] | .tagName + \" \" + .publishedAt")
    publicada = out.split()[0].lstrip("v") if rc == 0 and out else ""
    if not publicada:
        try:
            with urllib.request.urlopen(urllib.request.Request(core.DEFAULT_CONF["update_url"], headers={"User-Agent": "LOL-E"}), timeout=15) as r:
                publicada = json.loads(r.read().decode("utf8"))["version"]
        except Exception:
            publicada = ""
    linea("Publicada en GitHub:", publicada or "no se pudo comprobar")
    if publicada:
        sh("git", "fetch", "--tags", "--quiet")   # la etiqueta de una publicación se crea en GitHub, no en este repositorio
        rc, log = sh("git", "log", f"v{publicada}..HEAD", "--oneline")
        n = len(log.splitlines()) if rc == 0 and log else 0
        if rc != 0:
            linea("Sin publicar:", f"no se pudo comparar con la etiqueta v{publicada}")
        elif n:
            linea("Sin publicar:", f"{n} commits en main desde la {publicada}" + (f" (el código ya dice {ver})" if ver != publicada else " (la versión del código aún es la publicada)"))
            for l in log.splitlines()[:15]:
                print(f"      {l[:110]}")
        else:
            linea("Sin publicar:", "nada: main y lo publicado coinciden")

    print("\nGit")
    rc, st = sh("git", "status", "--porcelain")
    linea("Cambios sin commit:", f"{len(st.splitlines())}" + (" (" + ", ".join(x[3:] for x in st.splitlines()[:4]) + ("…" if len(st.splitlines()) > 4 else "") + ")" if st else ""))
    rc, pend = sh("git", "rev-list", "--count", "@{u}..HEAD")
    linea("Commits sin subir:", pend if rc == 0 else "?")
    rc, ult = sh("git", "log", "-3", "--format=%h %ad %s", "--date=format:%d/%m %H:%M")
    for l in ult.splitlines():
        print(f"      {l[:120]}")

    print("\nPruebas")
    if "--pruebas" in sys.argv:
        rc, out = sh(sys.executable, os.path.join(ROOT, "herramientas", "tests_unitarios.py"), timeout=300)
        m = re.search(r"Ran (\d+) tests", out)
        linea("Unitarias:", f"{m.group(1) if m else '?'} · {'TODAS PASAN' if rc == 0 else 'HAY FALLOS (ver python herramientas/tests_unitarios.py)'}")
    else:
        linea("Unitarias:", "no ejecutadas (usa --pruebas); la comprobación completa es herramientas/comprobar_todo.py")

    print("\nCliente de LoL")
    juego = "League of Legends.exe" in sh("tasklist")[1]
    linea("Partida en curso:", "SÍ: no construir ni subir instaladores" if juego else "no")
    try:
        found = core.find_client(core.load_conf())
        fase = core.LCU(*found).get("/lol-gameflow/v1/gameflow-phase") if found else None
        linea("Cliente / fase:", f"abierto, fase {fase}" if found else "cerrado")
    except Exception:
        linea("Cliente / fase:", "cerrado (o sin responder)")

    print("\nInstalación del usuario (diag.log de %LOCALAPPDATA%\\LOL-E; esta sesión puede ver copias antiguas de otros archivos, no de este)")
    p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "LOL-E", "cache", "diag.log")
    try:
        lineas = open(p, encoding="utf-8", errors="replace").read().splitlines()
        arr = [l for l in lineas if "arranca ---" in l]
        linea("Última versión que arrancó:", re.sub(r"^(\S+ \S+)\s+--- LOL-E (\S+) arranca ---", r"\2 (\1)", arr[-1]) if arr else "sin dato")
        linea("Última línea del registro:", lineas[-1][:90] if lineas else "(vacío)")
        if arr and publicada and not arr[-1].split("LOL-E ")[1].startswith(publicada):
            linea("¿Actualizada?", f"NO: corre una anterior a la {publicada}; basta con cerrar y abrir LOL-E fuera de cola")
    except OSError:
        linea("Registro:", "no se puede leer")

    print("\nDocumentos")
    for f in ("CONTINUAR.md", "PLAN_DE_FUTURO.md", "HISTORIAL_DE_SESIONES.md", "NOTAS_DE_VERSION.txt"):
        fp = os.path.join(ROOT, "docs", f)
        if os.path.exists(fp):
            txt = open(fp, encoding="utf-8", errors="replace").read()
            linea(f + ":", f"modificado {time.strftime('%d/%m %H:%M', time.localtime(os.path.getmtime(fp)))}" + (f" · menciona la {ver}" if ver in txt else f" · NO menciona la {ver}: ¿está al día?"))
        else:
            linea(f + ":", "NO EXISTE")
    print("\nOrden de lectura para una conversación nueva: docs/CONTINUAR.md → este informe → docs/PLAN_DE_FUTURO.md (solo si toca decidir rumbo).\n")


if __name__ == "__main__":
    main()
