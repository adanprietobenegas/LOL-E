import os, sys, time, copy
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida")
src = open(SP + r"\shots2.py", encoding="utf-8").read()
head = src.split("t = lambda ms, f: ui.root.after(ms, f)")[0].replace('"ui2"', '"modes"')
exec(compile(head, "modes_head", "exec"))
OUT = os.path.join(SP, "modes"); os.makedirs(OUT, exist_ok=True)
errs = []
ui.root.report_callback_exception = lambda *a: (errs.append(a[1]), print("ERROR en callback:", repr(a[1]), flush=True))
t = lambda ms, f: ui.root.after(ms, f)
tm = {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 25000, "totalTimeInPhase": 30000}

SC = {
 "A_arena": ({"localPlayerCellId": 2, "myTeam": [{"cellId": 2, "championId": 0, "playerSubteamId": 1}, {"cellId": 3, "championId": 103, "playerSubteamId": 1}],
              "theirTeam": [], "timer": {"phase": "BAN_PICK"}, "actions": [[None]]},
             {"id": 1750, "group": "Arena", "kind": "other"}),
 "B_custom_rift": ({"localPlayerCellId": 0, "myTeam": [{"cellId": i, "championId": c} for i, c in enumerate((0, 64, 103, 222, 89))],
                    "theirTeam": [{"cellId": 5 + i, "championId": c} for i, c in enumerate((157, 23, 0, 0, 0))], "bans": {}, "timer": tm, "actions": []},
                   {"id": 0, "group": "Personalizada", "kind": "other"}),
 "C_custom_aram": ({"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championId": 103}, {"cellId": 1, "championId": 64}],
                    "theirTeam": [], "benchChampions": [{"championId": 1}, {"championId": 51}], "timer": tm, "actions": []},
                   {"id": 0, "group": "Personalizada", "kind": "aram"}),
 "D_aram_vacio": ({"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championId": None}], "theirTeam": None,
                   "benchChampions": [{"championId": None}, {}], "timer": None, "actions": None, "bans": None},
                  {"id": 450, "group": "ARAM", "kind": "aram"}),
 "E_vacia": ({}, {"id": 0, "group": "", "kind": "sr"}),
 "F_sr_sin_posiciones": ({"localPlayerCellId": 0, "myTeam": [{"cellId": i, "championId": c} for i, c in enumerate((0, 64, 103, 222, 89))],
                          "theirTeam": [{"cellId": 5, "championId": 157}], "bans": {"myTeamBans": [1], "theirTeamBans": [2]}, "timer": tm, "actions": []},
                         {"id": 0, "group": "", "kind": "sr"}),
}


def grab(name):
    ui.root.update_idletasks()
    x, y, w, h = ui.root.winfo_rootx(), ui.root.winfo_rooty(), ui.root.winfo_width(), ui.root.winfo_height()
    ImageGrab.grab(bbox=(x - 1, y - 32, x + w + 1, y + h + 1)).save(os.path.join(OUT, name + ".png"))


def run_case(name):
    ses_, mode = SC[name]
    try:
        r_ = l.advise(copy.deepcopy(ses_), champs, P, conf, mode)
        r_["party"] = []
        print(f"{name}: motor OK, modo={r_['mode']['kind']} cands={len(r_['cands'])}", flush=True)
        ui.show(l.sanitize_session(ses_), r_)
    except Exception as e:
        print(f"{name}: FALLA el motor -> {type(e).__name__}: {e}", flush=True)
        errs.append(e)


ui.root.state("normal")
t(300, lambda: (ui.link(True), ui.idle(l.player_info(P), "ok")))
at = 4000
for name in SC:
    t(at, lambda n=name: run_case(n)); t(at + 2200, lambda n=name: grab(n)); at += 3200
t(at, lambda: print("errores:", len(errs), flush=True)); t(at + 300, ui.close)
ui.root.mainloop()
