"""Mide cuánta CPU gasta la ventana por cada tipo de cambio de la selección (marcar un campeón, que un aliado marque uno, un rival elija, un ban…) y qué secciones se repintan."""
import copy, os, sys, time, collections
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["LOLE_TIEMPOS"] = "1"
sys.argv = [sys.argv[0], "1340", "730", "hover"]
src = open(os.path.join(HERE, "capturas.py"), encoding="utf-8").read()
head = src.split("# (nombre, acción, espera en ms antes de capturar)")[0]
exec(compile(head, "capturas_head", "exec"))

import ui_sections

rebuilt = collections.Counter()
orig = ui_sections.Section.refresh


def spy(self, ctx, force=False):
    did = orig(self, ctx, force)
    if did:
        rebuilt[type(self).__name__] += 1
    return did


ui_sections.Section.refresh = spy


def pump(ms=900):
    end = time.time() + ms / 1000
    while time.time() < end:
        ui.root.update()
        time.sleep(0.005)


def evento(nombre, fn):
    rebuilt.clear()
    c0, t0 = time.process_time(), time.perf_counter()
    fn()
    pump(1200)
    cpu, wall = time.process_time() - c0, time.perf_counter() - t0
    print(f"{nombre:<44} CPU {cpu:5.2f} s   repintado: {dict(rebuilt)}", flush=True)


def sesion(mine=0, intent=0, ally_intent=None, enemy=None, bans=None):
    s = copy.deepcopy(ses)
    if mine:
        s["myTeam"][0]["championId"] = mine
    if intent:
        s["myTeam"][0]["championPickIntent"] = intent
    if ally_intent:
        s["myTeam"][1]["championId"] = 0
        s["myTeam"][1]["championPickIntent"] = ally_intent
    if enemy:
        s["theirTeam"].append({"cellId": 7, "championId": enemy, "assignedPosition": "middle"})
    if bans:
        s["bans"]["myTeamBans"] = list(s["bans"]["myTeamBans"]) + bans
    return s


def push2(s):
    r = l.advise(s, champs, P, conf)
    r["party"], r["mates"] = ["fake1"], {"fake0": [5, 3], "fake1": [2, 0]}
    ui.show(s, r)


def main():
    ui.link(True)
    ui.idle(l.player_info(P), "Conectado")
    pump(2500)
    push2(ses)
    ui.players(team)
    pump(4000)
    evento("sin cambios (misma sesión otra vez)", lambda: push2(ses))
    evento("marco un campeón (intención)", lambda: push2(sesion(intent=103)))
    if os.environ.get("PERFIL"):
        import cProfile, pstats
        push2(sesion(intent=86)); pump(2500)       # el campeón y su build ya cargados: lo que cuesta de verdad cambiar a otro
        pr = cProfile.Profile(); pr.enable(); push2(sesion(intent=11)); pump(1500); pr.disable()
        pstats.Stats(pr).strip_dirs().sort_stats("cumulative").print_stats(28)
        evento("marco otro", lambda: push2(sesion(intent=157)))
    evento("un aliado marca un campeón", lambda: push2(sesion(ally_intent=11)))
    evento("otro aliado marca (cambia)", lambda: push2(sesion(ally_intent=64)))
    evento("un rival elige", lambda: push2(sesion(enemy=134)))
    evento("alguien banea", lambda: push2(sesion(bans=[777])))
    evento("bloqueo mi campeón", lambda: push2(sesion(mine=86)))
    def rafaga():
        for _ in range(10):
            ui.q.put(("assets",))
    evento("llegan 10 imágenes seguidas", rafaga)
    print("errores:", len(errs), flush=True)
    ui.close()


ui.root.after(600, main)
try:
    ui.root.mainloop()
finally:
    if os.path.exists(PLAN_BAK):
        shutil.move(PLAN_BAK, PLAN)
