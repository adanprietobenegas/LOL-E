"""Mide cuánto tarda en pintarse cada pantalla (sin cliente de LoL, con los datos de herramientas/capturas.py).

    python herramientas/tiempos.py [ancho] [perfil]

Cada acción se repite y se da su mediana en milisegundos: es el tiempo que la ventana queda sin responder.
Con «perfil» (p. ej. `python herramientas/tiempos.py 560 seleccion`) saca además las funciones que más pesan en esa acción.
"""
import cProfile, os, pstats, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
W = sys.argv[1] if len(sys.argv) > 1 else "560"
PERFIL = sys.argv[2] if len(sys.argv) > 2 else ""
os.environ["LOLE_TIEMPOS"] = "1"
sys.argv = [sys.argv[0], W, "730", "tiempos"]
src = open(os.path.join(HERE, "capturas.py"), encoding="utf-8").read()
head = src.split("# (nombre, acción, espera en ms antes de capturar)")[0]
exec(compile(head, "capturas_head", "exec"))   # misma ventana, datos y ayudantes que las capturas

res = []


def pump(ms=400):
    """Deja a la ventana terminar lo pendiente (repintados por pasos, imágenes) antes de la siguiente medida."""
    end = time.time() + ms / 1000
    while time.time() < end:
        ui.root.update()
        time.sleep(0.005)


def medir(nombre, fn, veces=5, antes=None):
    ts = []
    for _ in range(veces):
        if antes:
            antes(); pump()
        t = time.perf_counter()
        fn()
        ui.root.update()             # incluye el dibujo que la acción deja encolado
        ts.append((time.perf_counter() - t) * 1000)
        pump(250)
    res.append((nombre, statistics.median(ts), max(ts)))
    print(f"{nombre:<46} mediana {statistics.median(ts):6.0f} ms   peor {max(ts):6.0f} ms", flush=True)
    if PERFIL and PERFIL in nombre:
        if antes:
            antes(); pump()
        pr = cProfile.Profile(); pr.enable(); fn(); ui.root.update(); pr.disable()
        pstats.Stats(pr).strip_dirs().sort_stats("cumulative").print_stats(34)


def seleccion_entera():
    """Lo que pasa al llegar un cambio de la selección: todas las secciones, de golpe (en la app van una a una)."""
    ctx = ui.make_ctx()
    for s in ui.select_secs:
        s.refresh(ctx, True)


def main():
    ui.link(True); ui.idle(l.player_info(P), "Conectado al cliente. Entra en una cola cuando quieras."); pump(2500)
    medir("inicio: repintar entero", lambda: [s.refresh(ui.make_ctx(), True) for s in ui.idle_secs])
    push(ses); ui.players(team); pump(4000)
    medir("seleccion: repintar entera", seleccion_entera)
    for sec in ui.select_secs:   # qué sección pesa: en la app se repintan una a una, solo las que cambian
        medir("seleccion: solo " + type(sec).__name__, lambda sec=sec: sec.refresh(ui.make_ctx(), True), veces=3)
    medir("seleccion: llega un cambio sin novedad", lambda: [s.refresh(ui.make_ctx()) for s in ui.select_secs])
    medir("seleccion: otra tarjeta del carrusel", lambda: ui.recs.pick((ui.recs.sel + 1) % max(1, len(ui.recs.vis))))
    medir("seleccion: cambiar de pestaña", lambda: ui.recs.set_tab("Meta y build" if ui.recs.tab != "Meta y build" else "Resumen"))
    medir("seleccion: vista Lista", lambda: vista("lista"), antes=lambda: vista("carrusel"))
    medir("seleccion: vista Por categorías", lambda: vista("listas"), antes=lambda: vista("carrusel"))
    vista("carrusel"); pump()
    en_partida(); pump(4000)
    medir("partida: repintar el plan", lambda: ui.game_view.refresh(ui.make_ctx(), True))
    analisis_guardado(); tab_partida("Análisis"); pump(3000)
    medir("partida: repintar el análisis", lambda: ui.game_view.refresh(ui.make_ctx(), True))
    medir("ir a Enfrentamiento", lambda: ui.set_page("Enfrentamiento"), antes=lambda: ui.set_page("Asesor"))
    ui.set_page("Enfrentamiento"); pump(); ui.matchup_view.select(157); pump(2500)
    medir("enfrentamiento: repintar con rival", lambda: ui.matchup_view.refresh(ui.make_ctx(), True))
    medir("ir a Historial", lambda: ui.set_page("Historial"), antes=lambda: ui.set_page("Asesor"))
    medir("historial: repintar entero", lambda: ui.history_view.refresh(ui.make_ctx(), True))
    medir("ir a Datos", lambda: ui.set_page("Datos"), antes=lambda: ui.set_page("Asesor"))
    medir("abrir Ajustes", ui.open_dock, veces=3, antes=lambda: (ui.close_dock(), pump(900)))
    print("errores:", len(errs), flush=True)
    ui.close()


ui.root.after(600, main)
try:
    ui.root.mainloop()
finally:
    if os.path.exists(PLAN_BAK):
        shutil.move(PLAN_BAK, PLAN)
