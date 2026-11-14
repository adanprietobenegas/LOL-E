"""Capturas de todas las pantallas SIN el cliente de LoL: usa la carpeta cache/ del proyecto y jugadores inventados.

    python herramientas/capturas.py [ancho] [alto] [carpeta]

Abre la ventana en el monitor secundario (-1366,209), recorre las pantallas y guarda un PNG por pantalla (y por página
de desplazamiento) en herramientas/salida/<carpeta>. No escribe la configuración y deja cache/last_plan.json como estaba.
"""
import copy, glob, json, os, random, shutil, sys, time
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida")
sys.path.insert(0, D)
W = int(sys.argv[1]) if len(sys.argv) > 1 else 560
H = int(sys.argv[2]) if len(sys.argv) > 2 else 730
OUT = os.path.join(SP, sys.argv[3] if len(sys.argv) > 3 else f"auditoria_{W}")
os.makedirs(OUT, exist_ok=True)
os.environ["LOLE_GEOMETRY"] = f"{W}x{H}+-1360+212"   # monitor secundario; además evita guardar geometría y abrir las novedades

from PIL import ImageGrab
import lol_advisor as l, meta, players
import gui as g
import ui_sections

g.save_conf = l.save_conf = ui_sections.core.save_conf = lambda c: None
if os.environ.get("LOLE_VIGILA"):   # si el recorrido pasa de estos segundos, vuelca dónde está cada hilo (un cuelgue deja así su causa)
    import faulthandler
    faulthandler.dump_traceback_later(int(os.environ["LOLE_VIGILA"]), exit=False, file=sys.stderr)
PLAN = os.path.join(l.CACHE, "last_plan.json")
PLAN_BAK = PLAN + ".captura"
if os.path.exists(PLAN):
    shutil.copy2(PLAN, PLAN_BAK)


class SinCliente:
    """Cliente apagado: toda lectura falla como si LoL estuviera cerrado, así los datos salen de cache/."""
    def get(self, *a, **k):
        raise ConnectionError("sin cliente")
    post = put = get


conf = l.load_conf()
conf.update(auto_update=False, auto_install=False, beep=False, animations=False)
conf.update(json.loads(os.environ.get("LOLE_CONF", "{}")))   # p. ej. {"theme": "light", "scale": 1.3, "compact": true, "color_theme": "Papel"}
champs = l.load_champions()
P = l.load_player_data(SinCliente(), l.load_season(champs, conf))
P["profile"] = {"name": "Jugador", "tag": "EUW", "level": 214, "icon": 29, "puuid": "yo",
                "solo": {"key": "GOLD", "tier": "Oro", "div": "II", "lp": 47, "w": 58, "l": 51, "wr": 58 / 109},
                "flex": {"key": "SILVER", "tier": "Plata", "div": "I", "lp": 12, "w": 9, "l": 7, "wr": 9 / 16}, "prem": None, "extra": {"peak": {"key": "GOLD", "tier": "Oro", "div": "I"}, "prev": {"key": "GOLD", "tier": "Oro", "div": "III"}}}
P["rank"], P["record"], P["puuid"] = "Oro II · 47 PL", "58V · 51D · 53%", "yo"
l.META["data"] = meta.load(l.CACHE, l.DD_VERSION or "16.21.1", meta.tier_for("GOLD"))
import lpseries, time as _t   # una serie de rango de ejemplo (el cache del proyecto no tiene lp.json): la gráfica sale en el inicio
_pts, _v = [], 1000 + 3 * 100 + 35   # Oro II
_now = int(_t.time() * 1000)
for _i, _d in enumerate([18, -17, 19, 20, -16, -19, 17, 21, -18, 16, 19, -15, 20, 18, -17, 19, 17, -16, 21, 18, -19, 20, 17, 16, -15, 19]):
    _v += _d
    _pts.append({"t": _now - (26 - _i) * 86400000 * 2 // 1 + _i * 1000, "v": _v, "d": _d, "w": _d > 0, "cid": [86, 122, 875, 54][_i % 4],
                 "tier": lpseries.label_of(_v // 100 * 100).replace("Maestro+", "Maestro"), "lp": _v % 100, "src": "game"})
_pts.insert(5, {"t": _pts[4]["t"] + 86400000, "v": _pts[4]["v"] + 5, "d": None, "cid": None, "w": None, "tier": "Oro II", "lp": 70, "src": "day"})
lpseries.series = lambda lp, hist, snaps, queue="solo": _pts if queue == "solo" else []
lpseries.load_all = lambda cache_dir: ({"a": 1, "b": 2, "c": 3}, {})
import learn   # «Qué aprender» de ejemplo (el cache del proyecto no tiene partidas con línea)
learn.advice = lambda *a, **k: [{"role": "TOP", "n": 14, "main": 86, "main_g": 12, "main_wr": .58, "cands": [(122, 53.4), (875, 52.9), (54, 52.1)]}]



def jugador(n, nombre, tier, cids, wr, rol):
    rnd = random.Random(n)
    rec = [{"c": rnd.choice(cids), "w": rnd.random() < wr, "q": 420, "role": rol, "k": rnd.randint(1, 12), "d": rnd.randint(1, 9),
            "a": rnd.randint(2, 15), "cs": rnd.randint(30, 240), "dmg": rnd.randint(6000, 32000), "vis": rnd.randint(10, 60),
            "dur": rnd.randint(1300, 2300), "t": int((time.time() - 86400 * (i + 1)) * 1000)} for i in range(14)]
    w = sum(x["w"] for x in rec)
    return {"puuid": f"fake{n}", "name": nombre, "level": 80 + 37 * n, "icon": 1 + n,
            "solo": {"key": tier[0], "tier": tier[1], "div": tier[2], "lp": 20 + 9 * n, "w": 40 + w, "l": 44 - w + n, "wr": .5},
            "flex": None, "prem": None, "marks": {"peak": tier[1]}, "recent": rec[:10], "wr10": sum(x["w"] for x in rec[:10]) / 10,
            "top": cids[:3], "roles": [rol], "mastery": {c: 9000 * (i + 1) * (n + 1) for i, c in enumerate(cids)},
            "mastery_top": [{"c": c, "pts": 9000 * (i + 1) * (n + 1), "lvl": 5 + i, "last": 0} for i, c in enumerate(cids)],
            "stats": players.recent_stats(rec[:10], rec, rec)}


team = {p["puuid"]: p for p in (
    jugador(0, "Mikasa", ("GOLD", "Oro", "I"), [64, 121, 254], .6, "JUNGLE"),
    jugador(1, "ElDuoDeAdan", ("PLATINUM", "Platino", "IV"), [103, 134, 61], .5, "MIDDLE"),
    jugador(2, "Zed4Life", ("SILVER", "Plata", "II"), [222, 51, 81], .25, "BOTTOM"),
    jugador(3, "TankeroPro", ("GOLD", "Oro", "III"), [89, 412, 111], .55, "SUPPORT"))}
rivales = {p["puuid"]: p for p in (
    jugador(5, "Yasuo Main", ("GOLD", "Oro", "II"), [157, 777, 92], .5, "TOP"),
    jugador(6, "KhaJungla", ("GOLD", "Oro", "IV"), [23, 121, 64], .45, "JUNGLE"),
    jugador(7, "Syndra77", ("PLATINUM", "Platino", "III"), [134, 103, 99], .7, "MIDDLE"),
    jugador(8, "CaitADC", ("SILVER", "Plata", "I"), [51, 222, 81], .5, "BOTTOM"),
    jugador(9, "Thresh Hooks", ("GOLD", "Oro", "II"), [412, 89, 111], .5, "SUPPORT"))}

ses = {'localPlayerCellId': 0,
       'myTeam': [{'cellId': 0, 'championId': 0, 'assignedPosition': 'top'}, {'cellId': 1, 'championId': 64, 'assignedPosition': 'jungle', 'puuid': 'fake0'},
                  {'cellId': 2, 'championId': 103, 'assignedPosition': 'middle', 'puuid': 'fake1'}, {'cellId': 3, 'championId': 222, 'assignedPosition': 'bottom', 'puuid': 'fake2'},
                  {'cellId': 4, 'championId': 89, 'assignedPosition': 'utility', 'puuid': 'fake3'}],
       'theirTeam': [{'cellId': 5, 'championId': 157, 'assignedPosition': 'top'}, {'cellId': 6, 'championId': 23, 'assignedPosition': 'jungle'}],
       'bans': {'myTeamBans': [238, 60], 'theirTeamBans': [99, 777, 4]},
       'timer': {'phase': 'BAN_PICK', 'adjustedTimeLeftInPhase': 40000, 'totalTimeInPhase': 60000},
       'actions': [[{'actorCellId': 0, 'type': 'pick', 'isInProgress': True, 'completed': False}]]}
aram = {"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championId": 103}, {"cellId": 1, "championId": 64}, {"cellId": 2, "championId": 222}],
        "theirTeam": [], "benchChampions": [{"championId": 1}, {"championId": 51}, {"championId": 69}, {"championId": 99}],
        "bans": {"myTeamBans": [], "theirTeamBans": []}, "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 40000, "totalTimeInPhase": 60000}, "actions": []}
roster = ([{"team": "ally", "cid": 86, "puuid": "yo", "role": "TOP", "spells": [4, 12], "me": True, "icon": 29}]
          + [{"team": "ally", "cid": c, "puuid": f"fake{n}", "role": r, "spells": [4, 14], "me": False, "icon": 1 + n}
             for n, (c, r) in enumerate(((64, "JUNGLE"), (103, "MIDDLE"), (222, "BOTTOM"), (89, "SUPPORT")))]
          + [{"team": "enemy", "cid": c, "puuid": f"fake{n}", "role": r, "spells": [4, 14], "me": False, "icon": 1 + n}
             for n, (c, r) in ((5, (157, "TOP")), (6, (23, "JUNGLE")), (7, (134, "MIDDLE")), (8, (51, "BOTTOM")), (9, (412, "SUPPORT")))])

if os.environ.get("LOLE_PERFIL"):   # «Tu equipo» desplegado y el perfil completo de un aliado abierto
    conf["folds"] = {**(conf.get("folds") or {}), "sel_team": True}
ui = g.GUI(conf, champs)
if os.environ.get("LOLE_PERFIL"):
    ui.kit.open_prof = {"fake0"}
errs = []
ui.root.report_callback_exception = lambda *a: (errs.append(a[1]), print("ERROR en callback:", repr(a[1]), flush=True))
_log = l.log_exc
l.log_exc = g.core.log_exc = lambda where, exc_info=None: (print("ERROR registrado:", where, repr(sys.exc_info()[1]), flush=True), errs.append(where))


def push(s, mode=None, mine=0):
    s = copy.deepcopy(s)
    if mine:
        s["myTeam"][0]["championId"] = mine
        s["actions"] = [[{"actorCellId": 0, "type": "pick", "isInProgress": False, "completed": True, "championId": mine}]]
    r = l.advise(s, champs, P, conf, mode) if mode else l.advise(s, champs, P, conf)
    r["party"], r["mates"] = ["fake1"], {"fake0": [5, 3], "fake1": [2, 0]}
    ui.show(s, r)


def en_partida():
    ui.ctx["plan"] = {"cid": 86, "role": "TOP", "opp": 157, "opp_auto": 157, "enemies": [157, 23, 134, 51, 412], "allies": [64, 103, 222, 89],
                      "locked": True, "state": "game", "kind": "sr", "group": "", "mayhem": False, "qid": 420}
    ui.game_view.tab, ui.game_view.sig = "Plan", None
    ui.phase("InProgress"); ui.roster(roster); ui.roster_players({**team, **rivales})
    ui.set_page("Partida")


def tab_partida(v):
    ui.game_view.set_tab(v)


def vivo2():
    """Una segunda lectura en vivo con cambios (30 s después, tres bajas más tuyas, un objeto menos): la vista debe actualizarse sin repintarse."""
    s = __import__("live").summarize(__import__("cliente_falso").live_sample(), champs)
    s["t"] += 30
    me = next(p for p in s["players"] if p["me"])
    me["k"] += 3
    me["items"] = me["items"][:-1]
    s["teams"][s["me_team"] or "ORDER"]["kills"] += 3
    return s


def fin_partida():
    ui.phase("EndOfGame")


def analisis_guardado():
    """Enseña el análisis de la partida guardada más reciente en cache/analysis (no hace falta el cliente)."""
    fs = sorted(glob.glob(os.path.join(l.CACHE, "analysis", "*.json")))
    if not fs:
        return
    data = l.read_json(fs[-1], None)
    gid = os.path.basename(fs[-1])[:-5]
    ui.game_view.load_games()
    gid = next((x["id"] for x in ui.game_view.games if str(x["id"]) == gid), gid)   # mismo tipo que usa la lista de partidas
    ui.game_view.gid, ui.game_view.auto_try = gid, 99
    ui.analysis(gid, data)


def abrir_pliegues(v=True):
    conf.setdefault("folds", {}).update({k: v for k in ("dat_src", "dat_formula", "dat_f", "dat_params", "dat_gloss", "hist_filters", "game_roster")})


def pulsar(valor):
    """Pulsa de verdad el botón «valor» del primer selector segmentado visible que lo tenga (pestañas internas sin API propia)."""
    import customtkinter as ctk
    def walk(w):
        for ch in w.winfo_children():
            if isinstance(ch, ctk.CTkSegmentedButton) and valor in getattr(ch, "_buttons_dict", {}) and ch.winfo_ismapped():
                return ch
            r = walk(ch)
            if r is not None:
                return r
    seg = walk(ui.body)
    if seg is None and os.environ.get("LOLE_DEBUG"):
        def dump(w):
            for ch in w.winfo_children():
                if isinstance(ch, ctk.CTkSegmentedButton):
                    print("seg:", list(getattr(ch, "_buttons_dict", {})), ch.winfo_ismapped(), flush=True)
                dump(ch)
        dump(ui.root)
    if seg is None:
        if W >= 960:   # con ventana ancha la build se ve en columnas, sin pestañas «Variantes» / «Situaciones»: no es un fallo
            print("(sin pestañas a este ancho:", valor + ")", flush=True)
            return
        print("no encuentro el botón", valor, flush=True); errs.append(valor); return
    seg._buttons_dict[valor].invoke()


def vista(v):
    ui.set("rec_view", v, redraw=True)


# (nombre, acción, espera en ms antes de capturar)
PASOS = [
    ("01_espera_sin_cliente", lambda: (ui.link(False), ui.idle(l.player_info(P), "Abre el cliente de League of Legends para empezar.")), 3500),
    ("02_inicio_conectado", lambda: (ui.link(True), ui.idle(l.player_info(P), "Conectado al cliente. Entra en una cola cuando quieras.")), 3500),
    ("03_seleccion_turno", lambda: (push(ses), ui.players(team)), 6000),
    ("04_seleccion_sinergias", lambda: ui.recs.set_tab("Sinergias"), 2000),
    ("05_seleccion_meta", lambda: ui.recs.set_tab("Meta y build"), 2500),
    ("06_seleccion_lista", lambda: vista("lista"), 3000),
    ("07_seleccion_listas", lambda: vista("listas"), 3000),
    ("08_seleccion_bloqueado", lambda: (vista("carrusel"), push(ses, mine=86)), 5000),
    ("09_aram", lambda: push(aram, {"id": 450, "group": "ARAM", "kind": "aram"}), 5000),
    ("10_partida_plan", en_partida, 6000),
    ("10b_salto_a_jugadores", lambda: getattr(ui.game_view, "jump_roster", lambda: print("sin enlace (ventana ancha)", flush=True))(), 1500),
    ("10c_partida_en_vivo", lambda: (ui.ctx["plan"].__setitem__("opp", next(c for c, v in champs.items() if v["name"] == "Darius")),   # tu rival de línea: el de la muestra
                                     ui.live(__import__("live").summarize(__import__("cliente_falso").live_sample(), champs))), 3000),
    ("10d_vivo_compra", lambda: ui.live(__import__("live").summarize(__import__("cliente_falso").live_sample(), champs)), 3500),   # 2.ª lectura: ya con la build cargada
    ("10f_vivo_detalle", lambda: (ui.conf.setdefault("folds", {}).__setitem__("live_board", True), ui.game_view.refresh(ui.make_ctx(), True),
                                  ui.root.after(1200, lambda: ui.live(vivo2()))), 4500),   # el pliegue de los diez abierto y una segunda lectura con cambios: se actualiza en sitio
    ("10e_fin_con_scroll", lambda: (ui.body._parent_canvas.yview_moveto(1.0), ui.root.after(300, lambda: (ui.idle(l.player_info(P), "Partida terminada. Historial actualizado. Esperando la siguiente…"), ui.phase("None"), analisis_guardado()))), 3500),   # el usuario miraba la parte baja del bloque en vivo cuando acabó la partida: no debe quedar la pantalla en blanco
    ("11_partida_analisis", lambda: (fin_partida(), tab_partida("Análisis")), 5000),
    ("11b_analisis_guardado", analisis_guardado, 5000),
    ("12_enfrentamiento", lambda: ui.set_page("Enfrentamiento"), 4000),
    ("13_enfrentamiento_rival", lambda: ui.matchup_view.select(157), 4000),
    ("14_historial", lambda: ui.set_page("Historial"), 4000),
    ("15_datos", lambda: ui.set_page("Datos"), 4000),
    ("17_inicio_modos", lambda: (ui.set_page("Asesor"), ui.idle(l.player_info(P), "Conectado al cliente. Entra en una cola cuando quieras."),
                                 ui.root.after(900, lambda: ui.idle_secs[2].switch("Modos"))), 3500),
    ("17b_inicio_pl", lambda: (ui.set_page("Asesor"), ui.idle(l.player_info(P), "Conectado al cliente. Entra en una cola cuando quieras."),
                               ui.root.after(900, lambda: (ui.idle_secs[2].switch("Rango y logros"), ui.root.after(400, lambda: ui.idle_secs[2].toggle("lp"))))), 3500),   # la ficha «Tus PL guardados» abierta (gráfico)
    ("17c_pl_hover", lambda: (ui.set_page("Asesor"), ui.idle(l.player_info(P), "Conectado al cliente. Entra en una cola cuando quieras."),
                              ui.root.after(900, lambda: (ui.idle_secs[2].switch("Rango y logros"), ui.root.after(500, lambda: (lambda ch: ch.hover(type("E", (), {"x": int(ch.px(ch.pts[-7]["t"]))})()))(ui.idle_secs[2].lp_chart))))), 3500),   # el cuadro con el campeón, el resultado y los PL de una partida
    ("17d_pl_7_dias", lambda: (ui.set_page("Asesor"), ui.idle(l.player_info(P), "Conectado al cliente. Entra en una cola cuando quieras."),
                        ui.root.after(900, lambda: (ui.idle_secs[2].switch("Rango y logros"), ui.root.after(500, lambda: ui.idle_secs[2].lp_chart.set_range("7 días"))))), 3500),   # el tramo cambia el eje
    ("17e_pl_90_dias", lambda: (ui.set_page("Asesor"), ui.idle(l.player_info(P), "Conectado al cliente. Entra en una cola cuando quieras."),
                        ui.root.after(900, lambda: (ui.idle_secs[2].switch("Rango y logros"), ui.root.after(500, lambda: ui.idle_secs[2].lp_chart.set_range("90 días"))))), 3500),   # el tramo cambia el eje
    ("18_repertorio", lambda: ui.set_page("Repertorio"), 4500),
    ("18b_repertorio_detalle", lambda: (ui.pool_view.panel.__setattr__("dtab", "Partidas"), ui.pool_view.panel.render()), 3000),
    ("19_seleccion_contra_rival", lambda: (push(ses), ui.players(team), ui.root.after(2500, lambda: ui.recs.set_tab("Contra rival"))), 6000),
    ("20_datos_abierto", lambda: (abrir_pliegues(), ui.set_page("Datos"), ui.refresh_current(True)), 5000),
    ("21_historial_filtros", lambda: (ui.set_page("Historial"), ui.refresh_current(True)), 5000),
    ("22_build_variantes", lambda: (en_partida(), ui.root.after(3500, lambda: pulsar("Variantes"))), 7000),
    ("23_build_situaciones", lambda: pulsar("Situaciones"), 3500),
    ("24_perfil_completo", lambda: (ui.kit.__dict__.update(open_prof={"fake0"}), conf["folds"].update(lobby=True, sel_team=True, team=True),
                                    ui.set_page("Asesor"), push(ses), ui.players(team)), 7000),
    ("25_arena", lambda: push(ses, {"id": 1700, "group": "Arena", "kind": "other"}), 5000),
    ("26_mayhem", lambda: push(aram, {"id": 2400, "group": "ARAM: Mayhem", "kind": "aram"}, mine=103), 6000),
    ("27_filtros_abiertos", lambda: (ui.set_page("Asesor"), push(ses), ui.players(team),
                                     ui.root.after(2500, lambda: (ui.recs.toggle_filters(), ui.recs.set_filter("clase", "Tanque")))), 6000),
    ("16_ajustes", lambda: (ui.set_page("Asesor"), ui.open_dock()), 4500),
]
SOLO = [x for x in os.environ.get("LOLE_SOLO", "").split(",") if x]
MAXP = int(os.environ.get("LOLE_PAGINAS", "4"))


def grab(name):
    if os.environ.get("LOLE_SINFOTO"):   # solo recorrer las pantallas (lo usa comprobar_todo.py): sin guardar imágenes
        ui.root.update_idletasks()
        return
    ui.root.update_idletasks()
    x, y, w, h = ui.root.winfo_rootx(), ui.root.winfo_rooty(), ui.root.winfo_width(), ui.root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(os.path.join(OUT, name + ".png"))
    print("capturada", name, w, h, flush=True)


def paginas(name, seguir, n=0):
    """Captura la página visible y baja una pantalla (con algo de solape) hasta el final."""
    cv = ui.body._parent_canvas
    grab(name + ("" if n == 0 else f"_p{n + 1}"))
    a, b = cv.yview()
    if name.startswith("16") and n < 6:   # Ajustes: se pagina el panel, no el cuerpo
        try:
            sc = ui.dock_scroll._parent_canvas
            a, b = sc.yview()
            if b < 0.999:
                sc.yview_moveto(a + (b - a) * 0.9)
                ui.root.after(900, lambda: paginas(name, seguir, n + 1))
                return
        except Exception as e:
            print("ajustes sin paginar:", repr(e), flush=True)
    if b >= 0.999 or n + 1 >= MAXP or name.startswith(("16", "10b")):
        cv.yview_moveto(0)
        ui.root.after(200, seguir)
        return
    cv.yview_moveto(a + (b - a) * 0.9)
    ui.root.after(900, lambda: paginas(name, seguir, n + 1))


def correr(i=0):
    if i >= len(PASOS):
        print("errores:", len(errs), flush=True)
        ui.root.after(300, ui.close)
        return
    name, fn, wait = PASOS[i]
    print(">> paso", name, flush=True)
    try:
        fn()
    except Exception as e:
        errs.append(e); print(f"{name}: FALLA -> {type(e).__name__}: {e}", flush=True)
    if SOLO and not any(name.startswith(s) for s in SOLO):
        ui.root.after(700 if i < 3 else 300, lambda: correr(i + 1))
        return
    ui.root.after(wait, lambda: paginas(name, lambda: correr(i + 1)))


ui.root.after(800, correr)
try:
    ui.root.mainloop()
finally:
    if os.path.exists(PLAN_BAK):
        shutil.move(PLAN_BAK, PLAN)
if errs:
    sys.exit(1)   # el código de salida distingue «recorrido limpio» de «hubo errores»
