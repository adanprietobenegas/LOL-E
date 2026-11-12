"""Actualizaciones automáticas: comprueba un archivo de versión (latest.json), descarga el instalador, verifica su huella y lo lanza.

El archivo de versión lo publica quien reparte el programa (por ejemplo, en las «Releases» de un repositorio de GitHub).
Si `update_url` está vacío, no se comprueba nada. Por defecto la app se actualiza sola (al abrir y cada pocas horas, solo fuera de cola, selección y partida); con el ajuste
«Instalar las actualizaciones solas» desactivado, queda el botón «Actualizar».

latest.json:  {"version": "1.2.0", "url": "https://…/Instalar-LOL-E-1.2.0.exe", "sha256": "…", "notes": "…"}
"""
import hashlib, json, os, subprocess, tempfile, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)"}


def vtuple(v):
    return tuple(int(x) for x in v.strip().lstrip("v").split(".") if x.isdigit())


HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")


def safe_url(url):
    """Solo HTTPS y solo GitHub: el instalador se ejecuta sin preguntar, así que no vale cualquier dirección."""
    from urllib.parse import urlparse
    u = urlparse(url or "")
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in HOSTS)


def _open(url, timeout):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)


def _cert_error(e):
    return "CERTIFICATE_VERIFY_FAILED" in str(e)


def _curl(url, out=None, timeout=120):
    """Plan B cuando Python no puede validar el certificado (le falta un emisor que Windows aún no ha descargado a su almacén):
    curl.exe de Windows valida con el sistema, que sí lo consigue. Sigue siendo HTTPS verificado, y el instalador se comprueba por su huella."""
    exe = os.path.join(os.environ.get("SystemRoot", r"C:Windows"), "System32", "curl.exe")
    cmd = [exe, "-fsSL", "--proto", "=https", "--proto-redir", "=https", "--max-time", str(timeout), "-A", UA["User-Agent"], url]
    if out:
        cmd += ["-o", out]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout + 10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError(f"no se pudo descargar (curl {r.returncode})")
    return r.stdout


def check(url, current):
    """Devuelve el manifiesto si hay una versión más nueva que `current`; None si no. Lanza excepción si no se puede comprobar."""
    if not url:
        raise RuntimeError("no hay una dirección de actualizaciones configurada")
    if not safe_url(url):
        raise RuntimeError("la dirección de actualizaciones no es de GitHub por HTTPS")
    try:
        with _open(url, 20) as r:
            raw = r.read()
    except Exception as e:
        if not _cert_error(e):
            raise
        raw = _curl(url, timeout=30)
    info = json.loads(raw.decode("utf8"))
    for k in ("version", "url", "sha256"):
        if k not in info:
            raise RuntimeError(f"el archivo de versión no tiene «{k}»")
    if not vtuple(str(info["version"])) or ".".join(map(str, vtuple(str(info["version"])))) != str(info["version"]).strip().lstrip("v"):
        raise RuntimeError("la versión del archivo de versión no es válida")   # va en el nombre del archivo: solo números y puntos
    if not safe_url(info["url"]):
        raise RuntimeError("el instalador no está en GitHub por HTTPS: se descarta por seguridad")
    return info if vtuple(info["version"]) > vtuple(current) else None


def download(info, progress=None):
    """Descarga el instalador a una carpeta temporal y comprueba su SHA-256. Devuelve la ruta."""
    folder = os.path.join(tempfile.gettempdir(), "LOL-E-update")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"Instalar-LOL-E-{info['version']}.exe")
    h = hashlib.sha256()
    try:
        _open(info["url"], 60).close()
    except Exception as e:
        if not _cert_error(e):
            raise
        _curl(info["url"], path, 300)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest().lower() != info["sha256"].lower():
            os.remove(path)
            raise RuntimeError("la huella del archivo descargado no coincide: se descarta por seguridad")
        return path
    with _open(info["url"], 60) as r, open(path, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)
    if h.hexdigest().lower() != info["sha256"].lower():
        os.remove(path)
        raise RuntimeError("la huella del archivo descargado no coincide: se descarta por seguridad")
    return path


def install(path):
    """Lanza el instalador sin ventanas; al terminar vuelve a abrir LOL-E (UPDATE=1). El programa debe cerrarse después."""
    subprocess.Popen([path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/UPDATE=1", "/NORESTART"], close_fds=True)
