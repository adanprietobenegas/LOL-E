"""La app entera (ventana real + bucle real) contra el cliente falso: cola -> selección -> partida -> fin, con capturas.

    python herramientas/demo_falso.py [segundos_por_paso] [carpeta]

Usa una carpeta de datos temporal (no toca cache/ del proyecto, salvo para copiar campeones e imágenes ya descargadas) y
abre la ventana en el monitor secundario. Sirve para ver que la pestaña «Asesor» se pinta de verdad cuando el bucle
recibe una selección, no solo con datos inyectados (herramientas/capturas.py).
"""
import os, shutil, sys, tempfile, threading, time
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D); sys.path.insert(0, HERE)
PASO = float(sys.argv[1]) if len(sys.argv) > 1 else 7
OUT = os.path.join(HERE, "salida", sys.argv[2] if len(sys.argv) > 2 else "demo_falso")
os.makedirs(OUT, exist_ok=True)
os.environ["LOLE_GEOMETRY"] = "560x730+-1360+212"

from PIL import ImageGrab
import lol_advisor as core, history, players, analysis, meta
from cliente_falso import ClienteFalso, GUION

REAL = core.CACHE
TMP = os.path.join(tempfile.mkdtemp(), "cache")
shutil.copytree(REAL, TMP, ignore=shutil.ignore_patterns("history*", "games*", "account.json", "analysis", "last_*", "*.log", "live_samples"))
champs = core.load_champions()
core.CACHE = TMP
import gui as g
g.CACHE = TMP
g.save_conf = core.save_conf = lambda c: None
history.ACCOUNT = ""
conf = core.load_conf()
conf.update(auto_update=False, auto_install=False, beep=False, animations=False, topmost_mode="nunca")
try:
    core.META["data"] = meta.load(TMP, core.DD_VERSION or "16.21.1", "gold_plus")
except Exception as e:
    print("sin meta:", e, flush=True)

fake = ClienteFalso()
t0 = time.time()
guion = ["None"] + GUION   # un paso de reposo al principio para ver el inicio
fake.guion = guion
fake.dormir = lambda _s=0: time.sleep(0.25)                       # el bucle va a su ritmo real…
type(fake).paso = property(lambda self: int((time.time() - t0) / PASO), lambda self, v: None)   # …y el guion avanza por reloj
core.find_client, core.LCU = (lambda conf: ("x",)), (lambda *a: fake)
core.start_meta = core.play_phase = core.detect_account = lambda *a, **k: None
core.maybe_update_opgg = lambda *a, **k: None
players.fetch_team = lambda lcu, session, emit: emit({})
players.fetch_roster = lambda *a, **k: None
players.lobby_party = lambda *a, **k: None
analysis.load = lambda *a, **k: None

ui = g.GUI(conf, champs)
errs = []
ui.root.report_callback_exception = lambda *a: (errs.append(a[1]), print("ERROR en callback:", repr(a[1]), flush=True))
_st = ui.status
ui.status = lambda text: (print("pie:", text, flush=True), _st(text))


def grab(name):
    ui.root.update_idletasks()
    x, y, w, h = ui.root.winfo_rootx(), ui.root.winfo_rooty(), ui.root.winfo_width(), ui.root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(os.path.join(OUT, name + ".png"))
    print("capturada", name, "| vista:", ui.view, "| página:", ui.page, flush=True)


for i, fase in enumerate(guion):
    ui.root.after(int((i + 0.8) * PASO * 1000), lambda i=i, fase=fase: grab(f"{i:02d}_{fase}"))
ui.root.after(int((len(guion) + 0.3) * PASO * 1000), ui.close)
threading.Thread(target=core.run, args=(conf, champs, ui), daemon=True).start()
ui.root.mainloop()
log = os.path.join(TMP, "error.log")
print("errores de ventana:", len(errs), "| registro de errores:", open(log, encoding="utf-8").read()[:1500] if os.path.exists(log) else "vacío", flush=True)
print(open(os.path.join(TMP, "diag.log"), encoding="utf-8").read(), flush=True)
