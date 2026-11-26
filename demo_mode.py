"""Modo demostración: la app real (la misma ventana, las mismas pantallas) con un jugador y un historial INVENTADOS, en una ventana aparte y sin tocar los datos del usuario.

Se lanza con `LOL-E --demo` (o desde la Ayuda). Usa una carpeta de datos temporal: copia lo que no es personal de la caché (campeones, iconos, builds, meta) y escribe encima el
historial, los PL y los análisis de ejemplo de demo_data.py. No arranca el bucle del cliente de LoL (no hay cliente): el estado de la app (cola, selección, partida, fin) se escenifica
con `Demo.scene(...)`, igual que hacen las capturas de prueba. Nunca guarda la configuración ni escribe fuera de la carpeta temporal.

`Demo.scene(nombre)` cambia la app a una situación y las lecciones del tour (tour.py) se apoyan en ellas. Los nombres: idle, queue, select, locked, game, end."""
import copy
import json
import os
import shutil
import sys
import tempfile
import time

import demo_data

PERSONAL = ("history*", "games*", "account*", "analysis", "last_*", "*.log", "live_samples", "lp.json", "opgg*", "*.tmp", "error*", "diag*", "archive*")
TITLE = "LOL-E · Demostración"
SCENES = ("idle", "queue", "select", "locked", "aram", "arena", "game", "end")


class SinCliente:
    """Cliente apagado: toda lectura falla como si LoL estuviera cerrado (los datos salen de la carpeta temporal)."""
    def get(self, *a, **k):
        raise ConnectionError("sin cliente")
    post = put = get


def prepare_cache(core, now_ms):
    """Carpeta temporal con la caché no personal de la app y los datos de ejemplo. Devuelve su ruta."""
    tmp = os.path.join(tempfile.mkdtemp(prefix="lole-demo-"), "cache")
    if os.path.isdir(core.CACHE):
        shutil.copytree(core.CACHE, tmp, ignore=shutil.ignore_patterns(*PERSONAL))
    os.makedirs(os.path.join(tmp, "analysis"), exist_ok=True)
    import lpseries
    hist = demo_data.history_entries(now_ms)
    with open(os.path.join(tmp, "history.json"), "w", encoding="utf-8") as f:
        json.dump(hist, f)
    with open(os.path.join(tmp, "lp.json"), "w", encoding="utf-8") as f:
        json.dump(demo_data.lp_entries(hist, lpseries.label_of), f)
    solo = [e for e in sorted(hist.values(), key=lambda e: -e["t"]) if e["q"] == 420][:14]
    wins = [e for e in solo if e["w"]]
    for e in solo:   # las partidas con análisis son de Garen arriba: el análisis y la lista del historial cuentan lo mismo
        e["c"], e["r"] = 86, "TOP"
    with open(os.path.join(tmp, "history.json"), "w", encoding="utf-8") as f:
        json.dump(hist, f)
    for e in solo:   # con las derrotas peor: más muertes antes del minuto 15, y de ahí sale el patrón y el objetivo
        with open(os.path.join(tmp, "analysis", f"{e['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(demo_data.analysis_sample(e["id"], e["t"], 86, win=e["w"], early_deaths=0 if e["w"] else 3), f)
    return tmp, hist, wins


class Demo:
    """La app en modo demostración. `ui` es la ventana (gui.GUI)."""

    def __init__(self, menu=True):
        import lol_advisor as core
        self.core = core
        core.DEMO_MODE = True   # los demás módulos lo consultan (p. ej. para no ofrecer la demostración dentro de la demostración)
        now = int(time.time() * 1000)
        self.tmp, self.hist, self.wins = prepare_cache(core, now)
        import history, meta, players
        self.history = history
        core.CACHE = self.tmp
        history.ACCOUNT = ""
        import gui as g
        import ui_kit, ui_build, ui_guide
        g.CACHE = ui_kit.CACHE = self.tmp
        ui_build.CACHE_DIR = ui_guide.CACHE_DIR = self.tmp
        g.save_conf = core.save_conf = lambda c: None          # la demo no guarda nada de configuración
        self.champs = core.load_champions()
        conf = core.load_conf()
        conf.update(auto_update=False, auto_install=False, beep=False, tab="asesor", start_tab="asesor", live_enabled=True)
        self.conf = conf
        P = core.load_player_data(SinCliente(), core.load_season(self.champs, conf))
        P["profile"] = copy.deepcopy(demo_data.PROFILE)
        P["rank"], P["record"], P["puuid"] = "Oro II · 47 PL", "58V · 51D · 53%", "yo"
        P["form"] = [True, True, False, True, True]   # las últimas 5 partidas, la más reciente primero
        self.P = P
        try:
            core.META["data"] = meta.load(self.tmp, core.DD_VERSION or "16.21.1", meta.tier_for("GOLD"))
        except Exception:
            pass
        self.team, self.rivals = self.make_players(players)
        self.ui = g.GUI(conf, self.champs)
        self.ui.root.title(TITLE)
        self.banner()
        self.scene("idle")
        import tour
        self.tour = tour.Tour(self)
        if menu:
            self.ui.root.after(900, self.tour.menu)   # al abrir: ¿recorrido completo, una lección o explorar?

    # ---- jugadores de ejemplo (aliados y rivales de la selección) ----
    def make_players(self, players):
        import random

        def one(n, name, tier, cids, wr, role):
            rnd = random.Random(n)
            rec = [{"c": rnd.choice(cids), "w": rnd.random() < wr, "q": 420, "role": role, "k": rnd.randint(1, 12), "d": rnd.randint(1, 9), "a": rnd.randint(2, 15),
                    "cs": rnd.randint(30, 240), "dmg": rnd.randint(6000, 32000), "vis": rnd.randint(10, 60), "dur": rnd.randint(1300, 2300),
                    "t": int((time.time() - 86400 * (i + 1)) * 1000)} for i in range(14)]
            w = sum(x["w"] for x in rec)
            return {"puuid": f"fake{n}", "name": name, "level": 80 + 37 * n, "icon": 1 + n,
                    "solo": {"key": tier[0], "tier": tier[1], "div": tier[2], "lp": 20 + 9 * n, "w": 40 + w, "l": 44 - w + n, "wr": .5},
                    "flex": None, "prem": None, "marks": {"peak": tier[1]}, "recent": rec[:10], "wr10": sum(x["w"] for x in rec[:10]) / 10, "top": cids[:3],
                    "roles": [role], "mastery": {c: 9000 * (i + 1) * (n + 1) for i, c in enumerate(cids)},
                    "mastery_top": [{"c": c, "pts": 9000 * (i + 1) * (n + 1), "lvl": 5 + i, "last": 0} for i, c in enumerate(cids)],
                    "stats": players.recent_stats(rec[:10], rec, rec)}
        team = {p["puuid"]: p for p in (one(0, "Mikasa", ("GOLD", "Oro", "I"), [64, 121, 254], .6, "JUNGLE"), one(1, "ElDuoDeAdan", ("PLATINUM", "Platino", "IV"), [103, 134, 61], .5, "MIDDLE"),
                                        one(2, "Zed4Life", ("SILVER", "Plata", "II"), [222, 51, 81], .25, "BOTTOM"), one(3, "TankeroPro", ("GOLD", "Oro", "III"), [89, 412, 111], .55, "SUPPORT"))}
        rivals = {p["puuid"]: p for p in (one(5, "Yasuo Main", ("GOLD", "Oro", "II"), [157, 777, 92], .5, "TOP"), one(6, "KhaJungla", ("GOLD", "Oro", "IV"), [23, 121, 64], .45, "JUNGLE"),
                                          one(7, "Syndra77", ("PLATINUM", "Platino", "III"), [134, 103, 99], .7, "MIDDLE"), one(8, "CaitADC", ("SILVER", "Plata", "I"), [51, 222, 81], .5, "BOTTOM"),
                                          one(9, "Thresh Hooks", ("GOLD", "Oro", "II"), [412, 89, 111], .5, "SUPPORT"))}
        return team, rivals

    # ---- aviso fijo de que esto es una demostración ----
    def banner(self):
        import customtkinter as ctk
        from ui_kit import PAL
        ui = self.ui
        self.band = ctk.CTkFrame(ui.main, fg_color=("#fbead0", "#2e2210"), corner_radius=8, border_width=1, border_color=PAL["warn"])
        ui.kit.clbl(self.band, "DEMOSTRACIÓN · datos de ejemplo inventados: nada de esto es tuyo y no se guarda nada", 10, "warn", True).pack(padx=12, pady=3)
        self.band.pack(fill="x", padx=16, pady=(6, 0), before=ui.mid)

    # ---- escenas ----
    def info(self):
        return self.core.player_info(self.P)

    def push(self, session, mode=None, mine=0):
        s = copy.deepcopy(session)
        if mine:
            s["myTeam"][0]["championId"] = mine
            s["actions"] = [[{"actorCellId": 0, "type": "pick", "isInProgress": False, "completed": True, "championId": mine}]]
        r = self.core.advise(s, self.champs, self.P, self.conf, mode) if mode else self.core.advise(s, self.champs, self.P, self.conf)
        r["party"], r["mates"] = ["fake1"], {"fake0": [5, 3], "fake1": [2, 0]}
        self.ui.show(s, r)

    def live(self, second=False):
        import live
        from demo_cliente import live_sample
        snap = live.summarize(live_sample(), self.champs)
        if second:
            snap["t"] += 30
        self.ui.live(snap)

    def scene(self, name):
        """Lleva la app a una situación: idle (antes de jugar), queue, select (eligiendo), locked (campeón elegido), game (jugando) o end (partida terminada)."""
        ui = self.ui
        if name == "idle":
            ui.phase("None")
            ui.link(True)
            ui.idle(self.info(), "Conectado al cliente. Entra en una cola cuando quieras.")
        elif name == "queue":
            ui.link(True)
            ui.idle(self.info(), "En cola…")
            ui.phase("Matchmaking")
        elif name in ("aram", "arena"):
            ui.link(True)
            ui.phase("ChampSelect")
            if name == "aram":
                self.push(demo_data.ARAM_SESSION, {"id": 450, "group": "ARAM", "kind": "aram"})
            else:
                self.push(demo_data.SESSION, {"id": 1700, "group": "Arena", "kind": "other"})
        elif name in ("select", "locked"):
            ui.link(True)
            ui.phase("ChampSelect")
            self.push(demo_data.SESSION, mine=86 if name == "locked" else 0)
            ui.players(self.team)
        elif name == "game":
            ui.link(True)
            ui.ctx["plan"] = {"cid": 86, "role": "TOP", "opp": 157, "opp_auto": 157, "enemies": [157, 23, 134, 51, 412], "allies": [64, 103, 222, 89],
                              "locked": True, "state": "game", "kind": "sr", "group": "", "mayhem": False, "qid": 420}
            ui.game_view.tab, ui.game_view.sig = "Plan", None
            ui.phase("InProgress")
            ui.roster(demo_data.ROSTER)
            ui.roster_players({**self.team, **self.rivals})
            ui.set_page("Partida")
            self.live()
        elif name == "end":
            ui.link(True)
            ui.phase("EndOfGame")
            ui.idle(self.info(), "Partida terminada. Historial actualizado. Esperando la siguiente…")
            e = self.wins[0]
            ui.game_view.load_games()
            gid = next((x["id"] for x in ui.game_view.games if str(x["id"]) == str(e["id"])), e["id"])
            ui.game_view.gid, ui.game_view.auto_try = gid, 99
            ui.ctx["plan"] = {**(ui.ctx.get("plan") or {}), "state": "done"}
            ui.analysis(gid, self.core.read_json(os.path.join(self.tmp, "analysis", f"{e['id']}.json"), None))
            ui.set_page("Partida")
            ui.game_view.set_tab("Análisis")

    def go(self, page):
        self.ui.set_page(page)

    def act(self, name):
        """Acciones sueltas que piden algunos pasos del tour."""
        ui = self.ui
        if name == "rival":
            ui.matchup_view.select(157)
        elif name == "ajustes":
            if not ui.dock_open:
                ui.open_dock()
        elif name == "cerrar_ajustes":
            if ui.dock_open:
                ui.close_dock()
        elif name == "abrir_jugadores":
            folds = ui.conf.setdefault("folds", {})
            folds["game_roster"] = folds["game_roster_live"] = folds["game_opp"] = True   # en partida salen cerrados: la lección los abre
            ui.game_view.refresh(ui.make_ctx(), True)
        elif name == "parche_notas":
            ui.patch_view.set_tab("Notas")
        elif name == "parche_estadisticas":
            ui.patch_view.set_tab("Estadísticas")
        elif name == "abrir_anio":
            ui.conf.setdefault("folds", {})["hist_wrapped"] = True
            ui.refresh_current(True)


def run(scene=None, lessons=None):
    """Abre la demostración y la deja funcionando hasta que se cierre la ventana. `lessons`: ids de lecciones (tour.LESSONS) que empiezan solas; sin ellas sale el menú de bienvenida."""
    import tour
    lessons = [x for x in (lessons or []) if x in tour.LESSONS]
    d = Demo(menu=not lessons)
    if scene:
        d.scene(scene)
    if lessons:
        d.ui.root.after(900, lambda: d.tour.start(lessons))
    d.ui.root.mainloop()
    shutil.rmtree(os.path.dirname(d.tmp), ignore_errors=True)
