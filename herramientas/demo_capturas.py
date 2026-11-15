"""Recorre las escenas de la demostración (demo_mode.py) y guarda una captura de cada una: comprueba que la app arranca con los datos de ejemplo y que las pantallas se pintan.

    python herramientas/demo_capturas.py [ancho] [alto] [carpeta]

Abre la ventana en el monitor secundario como capturas.py y la captura con PrintWindow (sale bien aunque otra ventana la tape). Termina con «errores: N»."""
import os
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)
W = int(sys.argv[1]) if len(sys.argv) > 1 else 960
H = int(sys.argv[2]) if len(sys.argv) > 2 else 730
OUT = os.path.join(D, "herramientas", "salida", sys.argv[3] if len(sys.argv) > 3 else "demo")
os.makedirs(OUT, exist_ok=True)
os.environ["LOLE_GEOMETRY"] = f"{W}x{H}+-1360+212"

import lol_advisor as core
import demo_mode

errs = []
d = demo_mode.Demo(menu=False)
ui = d.ui
ui.root.report_callback_exception = lambda *a: (errs.append(a[1]), print("ERROR en callback:", repr(a[1]), flush=True))
_log = core.log_exc
core.log_exc = lambda where, exc_info=None: (print("ERROR registrado:", where, repr(sys.exc_info()[1]), flush=True), errs.append(where))


def grab(name):
    ui.root.update_idletasks()
    if os.environ.get("LOLE_PANTALLA"):   # foto de la pantalla real en vez de PrintWindow (para distinguir fallos de captura de fallos de pintado)
        from PIL import ImageGrab
        x, y, w, h = ui.root.winfo_rootx(), ui.root.winfo_rooty(), ui.root.winfo_width(), ui.root.winfo_height()
        ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(os.path.join(OUT, name + ".png"))
        print("capturada (pantalla)", name, flush=True)
        return
    try:
        import ctypes
        from ctypes import wintypes as wt
        from PIL import Image
        u, g = ctypes.windll.user32, ctypes.windll.gdi32
        u.GetAncestor.restype = wt.HWND
        hwnd = u.GetAncestor(wt.HWND(ui.root.winfo_id()), 2)
        r = wt.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        dc = u.GetWindowDC(hwnd)
        mdc = g.CreateCompatibleDC(dc)
        bm = g.CreateCompatibleBitmap(dc, w, h)
        g.SelectObject(mdc, bm)
        u.PrintWindow(hwnd, mdc, 2)

        class BI(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                        ("biSizeImage", wt.DWORD), ("a", wt.LONG), ("b", wt.LONG), ("c", wt.DWORD), ("d", wt.DWORD)]
        bi = BI(ctypes.sizeof(BI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        g.GetDIBits(mdc, bm, 0, h, buf, ctypes.byref(bi), 0)
        Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(os.path.join(OUT, name + ".png"))
        print("capturada", name, "| página:", ui.page, flush=True)
    except Exception as e:
        errs.append(e)
        print("no se pudo capturar", name, repr(e), flush=True)


# (nombre, acción, espera en ms)
PASOS = [
    ("01_inicio", lambda: d.scene("idle"), 3500),
    ("02_cola", lambda: d.scene("queue"), 2500),
    ("03_seleccion", lambda: d.scene("select"), 6000),
    ("04_eleccion", lambda: d.scene("locked"), 5000),
    ("05_partida", lambda: d.scene("game"), 6000),
    ("06_fin", lambda: d.scene("end"), 5000),
    ("07_historial", lambda: (d.scene("idle"), d.go("Historial")), 4000),
    ("08_campeones", lambda: d.go("Repertorio"), 4000),
    ("09_enfrentamiento", lambda: d.go("Enfrentamiento"), 3000),
    ("10_datos", lambda: d.go("Datos"), 3000),
]
import tour as _tour
if os.environ.get("LOLE_TOUR"):   # el recorrido completo: una captura por paso (y comprueba que cada paso se pinta)
    ids = list(_tour.LESSONS) if os.environ.get("LOLE_TOUR") == "todo" else [os.environ["LOLE_TOUR"]] if os.environ["LOLE_TOUR"] in _tour.LESSONS else _tour.RECORRIDO
    PASOS = [("00_menu", lambda: d.tour.menu(), 1200)]
    PASOS.append(("00b_inicio_recorrido", lambda: d.tour.start(ids), 2200))
    k = 0
    for li, lid in enumerate(ids):
        for si in range(len(_tour.LESSONS[lid]["steps"])):
            if li or si:
                PASOS.append((f"{k:02d}_{lid}_{si + 1}", lambda: d.tour.next(), 3600))
            else:
                PASOS.append((f"{k:02d}_{lid}_{si + 1}", lambda: None, 100))
            k += 1
    PASOS.append(("99_fin", lambda: d.tour.exit(), 800))
t = 600
for nombre, accion, espera in PASOS:
    ui.root.after(t, accion)
    ui.root.after(t + espera, lambda n=nombre: grab(n))
    t += espera + 400
ui.root.after(t + 300, ui.close)
ui.root.mainloop()
print("errores:", len(errs), flush=True)
