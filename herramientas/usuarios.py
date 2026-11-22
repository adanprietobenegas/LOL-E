"""Cuánta gente usa LOL-E, de forma privada y sin rastrear a nadie: solo lo que GitHub ya cuenta de tus publicaciones (necesita la CLI `gh` con tu sesión).

    python herramientas/usuarios.py            # resumen y guarda una foto de hoy en cache/usuarios_historial.json (solo en tu PC, fuera de git)
    python herramientas/usuarios.py --sin-guardar

Qué mide y qué NO:
  · Descargas del instalador por versión: instalaciones nuevas + actualizaciones (la actualización automática descarga el instalador). Incluyen las tuyas.
  · Descargas de `latest.json`: cada LOL-E abierta lo pide al arrancar y cada 3 horas para ver si hay versión nueva; sirve de pulso de «cuántas están abiertas».
  · Tráfico del repositorio (14 días): clones y visitas. Los clones suelen ser robots y réplicas, no usuarios.
  · NO hay países ni nombres: GitHub no los da, y LOL-E no envía nada a nadie (no hay telemetría). Para saber de dónde son habría que añadir un aviso anónimo y voluntario,
    decisión que no está tomada (ver docs/PLAN_DE_FUTURO.md).
Cada ejecución con guardado añade una foto (fecha, descargas totales, comprobaciones totales): con el tiempo sale el histórico y la diferencia entre dos fotos son las comprobaciones
y descargas de ese tramo."""
import datetime
import json
import os
import subprocess
import sys

REPO = "adanprietobenegas/LOL-E"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "cache", "usuarios_historial.json")


def gh(path):
    r = subprocess.run(["gh", "api", path, "--paginate"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "gh falló").strip()[:300])
    txt = r.stdout.strip()
    try:
        return json.loads(txt)
    except ValueError:   # --paginate con varias páginas concatena listas JSON: se unen
        out = []
        dec = json.JSONDecoder()
        i = 0
        while i < len(txt):
            obj, j = dec.raw_decode(txt, i)
            out.extend(obj if isinstance(obj, list) else [obj])
            i = j
            while i < len(txt) and txt[i] in " \r\n":
                i += 1
        return out


def main():
    guardar = "--sin-guardar" not in sys.argv
    rel = gh(f"repos/{REPO}/releases")
    filas = []
    for r in rel:
        a = {x["name"]: x["download_count"] for x in r.get("assets", [])}
        inst = sum(v for k, v in a.items() if k.startswith("Instalar-"))
        pulso = a.get("latest.json", 0)
        filas.append((r["tag_name"], r["published_at"][:10], inst, a.get("LOL-E-" + r["tag_name"].lstrip("v") + ".zip", 0), pulso))
    tot_inst, tot_zip, tot_pulso = sum(f[2] for f in filas), sum(f[3] for f in filas), sum(f[4] for f in filas)
    print(f"LOL-E en GitHub ({REPO}): {len(filas)} versiones publicadas\n")
    print(f"{'versión':<10}{'fecha':<12}{'instalador':>11}{'zip':>6}{'comprobac.':>12}")
    for tag, fecha, inst, z, pulso in filas[:12]:
        print(f"{tag:<10}{fecha:<12}{inst:>11}{z:>6}{pulso:>12}")
    if len(filas) > 12:
        print(f"  … y {len(filas) - 12} versiones más antiguas")
    print(f"\nTotal: {tot_inst} descargas del instalador (instalaciones + actualizaciones, incluidas las tuyas), {tot_zip} del zip, {tot_pulso} comprobaciones de versión.")
    # pulso reciente: comprobaciones de la versión anterior y el tiempo que estuvo vigente (entre publicaciones)
    if len(rel) >= 2:
        f = lambda r: datetime.datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
        horas = (f(rel[0]) - f(rel[1])).total_seconds() / 3600
        ant = filas[1]
        if horas >= 24:
            print(f"La anterior ({ant[0]}) fue la vigente {horas / 24:.1f} días y recibió {ant[4]} comprobaciones: unas {ant[4] / (horas / 24):.1f} al día "
                  "(una LOL-E abierta todo el día pregunta ~8 veces: 1-2 usuarios con la app abierta solo parte del día salen así).")
        else:
            print(f"La anterior ({ant[0]}) fue la vigente solo {horas:.1f} horas: aún no sirve para estimar el pulso diario.")
    try:
        cl = gh(f"repos/{REPO}/traffic/clones")
        vi = gh(f"repos/{REPO}/traffic/views")
        ref = gh(f"repos/{REPO}/traffic/popular/referrers")
        info = gh(f"repos/{REPO}")
        print(f"\nRepositorio (14 días): {cl.get('count', 0)} clones ({cl.get('uniques', 0)} únicos; suelen ser robots), {vi.get('count', 0)} visitas ({vi.get('uniques', 0)} únicas), "
              f"{info.get('stargazers_count', 0)} estrellas, {info.get('forks_count', 0)} forks.")
        if ref:
            print("Desde dónde llegan a la página: " + ", ".join(f"{x['referrer']} ({x['count']})" for x in ref))
    except Exception as e:
        print("\n(El tráfico del repositorio no se pudo leer:", e, ")")
    if guardar:
        os.makedirs(os.path.dirname(HIST), exist_ok=True)
        try:
            hist = json.load(open(HIST, encoding="utf-8"))
        except (OSError, ValueError):
            hist = []
        hoy = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        hist.append({"fecha": hoy, "instalador": tot_inst, "zip": tot_zip, "comprobaciones": tot_pulso, "version": filas[0][0] if filas else ""})
        with open(HIST, "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=1)
        print(f"\nFoto guardada en {os.path.relpath(HIST, ROOT)} ({len(hist)} en total).")
        if len(hist) >= 2:
            a, b = hist[-2], hist[-1]
            print(f"Desde la foto anterior ({a['fecha']}): +{b['instalador'] - a['instalador']} descargas del instalador, +{b['comprobaciones'] - a['comprobaciones']} comprobaciones de versión.")


if __name__ == "__main__":
    main()
