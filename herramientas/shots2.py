import os, sys, time, copy
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida")
sys.path.insert(0, D)
import customtkinter as ctk
from PIL import ImageGrab
import lol_advisor as l, meta, players
import gui as g
g.save_conf = lambda c: None
l.save_conf = lambda c: None
import ui_sections
ui_sections.core.save_conf = lambda c: None

conf = l.load_conf(); champs = l.load_champions()
lcu = l.LCU(*l.find_client(conf)); l.detect_account(lcu, conf)
P = l.load_player_data(lcu, l.load_season(champs, conf))
l.META["data"] = meta.load(l.CACHE, l.DD_VERSION or "16.21.1", meta.tier_for(P["profile"]["solo"]["key"]))
# un jugador real y tres copias con otros nombres/maestrias, como si fueran los aliados
gms = lcu.get("/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=20")["games"]["games"]
gm = next(x for x in gms if x["queueId"] in l.SR_QUEUES)
ids = lcu.get(f"/lol-match-history/v1/games/{gm['gameId']}")["participantIdentities"]
pu = next(i["player"]["puuid"] for i in ids if i["player"]["puuid"] != P["profile"]["puuid"])
base = players.fetch_player(lcu, pu)
team = {}
for n, (nm, champ_pts) in enumerate((("Mikasa", 80000), ("ElDuoDeAdan", 3000), ("Zed4Life", 0), ("TankeroPro", 24000))):
    p = copy.deepcopy(base); p["puuid"] = f"fake{n}"; p["name"] = nm
    p["mastery"] = {**p["mastery"], 64: champ_pts, 103: champ_pts, 222: champ_pts, 89: champ_pts}
    if n == 2: p["recent"] = [{**x, "w": False} for x in p["recent"][:7]] + p["recent"][7:]; p["wr10"] = .3
    team[f"fake{n}"] = p

ses = {'localPlayerCellId': 0,
       'myTeam': [{'cellId': 0, 'championId': 0, 'assignedPosition': 'top'}, {'cellId': 1, 'championId': 64, 'assignedPosition': 'jungle', 'puuid': 'fake0'},
                  {'cellId': 2, 'championId': 103, 'assignedPosition': 'middle', 'puuid': 'fake1'}, {'cellId': 3, 'championId': 222, 'assignedPosition': 'bottom', 'puuid': 'fake2'},
                  {'cellId': 4, 'championId': 89, 'assignedPosition': 'utility', 'puuid': 'fake3'}],
       'theirTeam': [{'cellId': 5, 'championId': 157, 'assignedPosition': 'top'}, {'cellId': 6, 'championId': 23, 'assignedPosition': 'jungle'}],
       'bans': {'myTeamBans': [238, 60], 'theirTeamBans': [99, 777, 4]},
       'timer': {'phase': 'BAN_PICK', 'adjustedTimeLeftInPhase': 40000, 'totalTimeInPhase': 60000},
       'actions': [[{'actorCellId': 0, 'type': 'pick', 'isInProgress': True, 'completed': False}]]}
r = l.advise(ses, champs, P, conf); r["party"] = ["fake1"]
ui = g.GUI(conf, champs)
OUT = os.path.join(SP, "ui2"); os.makedirs(OUT, exist_ok=True)


def grab(name):
    ui.root.update_idletasks()
    x, y, w, h = ui.root.winfo_rootx(), ui.root.winfo_rooty(), ui.root.winfo_width(), ui.root.winfo_height()
    ImageGrab.grab(bbox=(x - 1, y - 32, x + w + 1, y + h + 1)).save(os.path.join(OUT, name + ".png"))
    print("capturada", name, w, h, flush=True)


def timed(label, fn):
    t = time.perf_counter(); fn(); ui.root.update_idletasks()
    print(f"  {label}: {(time.perf_counter() - t) * 1000:.0f} ms", flush=True)


t = lambda ms, f: ui.root.after(ms, f)
t(300, lambda: (ui.link(True), ui.idle(l.player_info(P), "Conectado al cliente. Entra en una cola cuando quieras.")))
t(6000, lambda: grab("1_idle"))
t(6500, lambda: ui.show(ses, r))
t(7500, lambda: ui.players(team))
t(12000, lambda: grab("2_select_top"))
def mid(): ui.body._parent_canvas.yview_moveto(0.42)
t(12500, mid); t(13500, lambda: grab("3_select_mid"))
def bottom(): ui.body._parent_canvas.yview_moveto(1.0)
t(14000, bottom); t(15000, lambda: grab("4_select_bottom"))
t(15500, lambda: ui.body._parent_canvas.yview_moveto(0))
t(16000, lambda: (print("tiempos:"), timed("elegir otra tarjeta (fundido incluido)", lambda: ui.recs.pick(2)), timed("cambiar de pestaña a Sinergias", lambda: ui.recs.set_tab("Sinergias"))))
t(17000, lambda: grab("5_synergy"))
t(17500, lambda: (timed("pestaña Meta y build", lambda: ui.recs.set_tab("Meta y build"))))
t(18500, lambda: grab("6_meta"))
t(19000, lambda: timed("filtro: clase Tanque", lambda: ui.recs.set_filter("clase", "Tanque")))
t(19800, lambda: grab("7_filtro_tanque"))
t(20200, lambda: timed("quitar filtros", ui.recs.reset_filters))
t(21000, lambda: timed("llega un dato de jugador (solo equipo)", lambda: ui.players(dict(team))))
t(22000, lambda: timed("abrir Ajustes (pulsar)", ui.open_dock))
t(24500, lambda: grab("8_ajustes"))
t(25000, lambda: timed("cerrar Ajustes", ui.close_dock))
t(27500, ui.close)
ui.root.mainloop()
