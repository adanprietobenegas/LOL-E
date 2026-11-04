"""Demo en vivo de LOL-E: la app real con una partida simulada. Se maneja escribiendo órdenes en cmd.txt."""
import os, sys, time, copy, json
SP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida")
src = open(SP + r"\shots2.py", encoding="utf-8").read()
head = src.split("t = lambda ms, f: ui.root.after(ms, f)")[0].replace('"ui2"', '"demo"')
exec(compile(head, "demo_head", "exec"))
CMD = os.path.join(SP, "cmd.txt"); LOG = os.path.join(SP, "demo_log.txt")
open(CMD, "w").close()
OUT = os.path.join(SP, "demo"); os.makedirs(OUT, exist_ok=True)
g.save_conf = lambda c: None
ui.root.state("normal")
tk_geo = lambda s: g.tk.Wm.geometry(ui.root, s)
sw, sh = ui.root.winfo_screenwidth(), ui.root.winfo_screenheight()
tk_geo(f"{sw // 2}x{sh - 80}+{sw // 2}+10")
mates = {"fake0": [5, 3], "fake1": [2, 0]}
r["mates"] = mates
state = {"s": copy.deepcopy(ses), "mode": None, "tick": None}


def log(*a):
    open(LOG, "a", encoding="utf-8").write(" ".join(map(str, a)) + "\n")


def push(s=None, mode=None):
    s = s or state["s"]
    res = l.advise(s, champs, P, conf, mode) if mode else l.advise(s, champs, P, conf)
    res["party"] = ["fake1"]
    res["mates"] = mates
    ui.show(s, res)


def stop_tick():
    if state["tick"]:
        ui.root.after_cancel(state["tick"]); state["tick"] = None


def countdown(total=30, speed=1):
    stop_tick()
    t0 = time.time()

    def step():
        left = max(0, total - (time.time() - t0) * speed)
        state["s"]["timer"] = {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": int(left * 1000), "totalTimeInPhase": total * 1000}
        push()
        state["tick"] = ui.root.after(1000, step) if left > 0 else None
    step()


S = state["s"]
for c in S["myTeam"]:
    if c["cellId"] != 0: c["_real"] = c["championId"]; c["championId"] = 0
S["theirTeam"] = [{"cellId": 5 + i, "championId": 0, "assignedPosition": p} for i, p in enumerate(("top", "jungle", "middle", "bottom", "utility"))]
S["bans"] = {"myTeamBans": [], "theirTeamBans": []}
S["timer"] = {"phase": "PLANNING", "adjustedTimeLeftInPhase": 20000, "totalTimeInPhase": 20000}
S["actions"] = []


def c_idle(*a): stop_tick(); ui.link(True); ui.idle(l.player_info(P), "Conectado al cliente. Entra en una cola cuando quieras.")
def c_waiting(*a): stop_tick(); ui.link(False); ui.idle(l.player_info(P), "Esperando al cliente de League of Legends…")
def c_start(*a):
    ui.link(True); push(); ui.players({k: v for k, v in team.items() if False})
def c_players(*a): ui.players(team)
def c_bans(*a):
    S["bans"] = {"myTeamBans": [238, 60, 777], "theirTeamBans": [99, 7, 4]}; S["timer"]["phase"] = "BAN_PICK"; push()
def c_ally(*a):
    n = int(a[0])
    for c in S["myTeam"]:
        if c["cellId"] == n: c["championId"] = c.get("_real", 0)
    push()
def c_enemy(*a):
    ids = {5: 157, 6: 23, 7: 134, 8: 51, 9: 412}
    n = int(a[0]); S["theirTeam"][n - 5]["championId"] = ids[n]; push()
def c_myturn(*a):
    S["actions"] = [[{"actorCellId": 0, "type": "pick", "isInProgress": True, "completed": False}]]; countdown(int(a[0]) if a else 30, 1.5)
def c_lock(*a):
    stop_tick(); S["myTeam"][0]["championId"] = int(a[0]) if a else 103; S["actions"] = []
    S["timer"] = {"phase": "FINALIZATION", "adjustedTimeLeftInPhase": 8000, "totalTimeInPhase": 8000}; push()
def c_tab(*a): ui.recs.set_tab(" ".join(a))
def c_page(*a): ui.set_page(" ".join(a))
def c_card(*a): ui.recs.pick(int(a[0]))
def c_filter(*a): ui.recs.set_filter(a[0], " ".join(a[1:]))
def c_nofilter(*a): ui.recs.reset_filters()
def c_dock(*a): ui.toggle_dock()
def c_scroll(*a): ui.body._parent_canvas.yview_moveto(float(a[0]))
def c_aram(*a):
    stop_tick()
    aram = {"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championId": 103}, {"cellId": 1, "championId": 64}, {"cellId": 2, "championId": 222}],
            "theirTeam": [], "benchChampions": [{"championId": 1}, {"championId": 51}, {"championId": 69}, {"championId": 99}],
            "bans": {"myTeamBans": [], "theirTeamBans": []}, "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 40000, "totalTimeInPhase": 60000}, "actions": []}
    push(aram, {"id": 450, "group": "ARAM", "kind": "aram"})
def c_other(*a):
    stop_tick(); push(copy.deepcopy(S), {"id": 1700, "group": "Arena", "kind": "other"})
def c_theme(*a): ctk.set_appearance_mode(a[0]); ui.set("theme", a[0])
def c_accent(*a): ui.set("accent", " ".join(a))
def c_size(*a): tk_geo(f"{a[0]}x{a[1]}+{a[2] if len(a) > 2 else 0}+10")
def c_max(*a): ui.root.state("zoomed")
def c_normal(*a): ui.root.state("normal"); tk_geo(f"{sw // 2}x{sh - 80}+{sw // 2}+10")
def c_anim(*a): ui.set("animations", a[0] == "on")
def c_shot(*a):
    ui.root.update_idletasks()
    x, y, w, h = ui.root.winfo_rootx(), ui.root.winfo_rooty(), ui.root.winfo_width(), ui.root.winfo_height()
    ImageGrab.grab(bbox=(x - 1, y - 32, x + w + 1, y + h + 1)).save(os.path.join(OUT, a[0] + ".png")); log("shot", a[0], w, h)
def c_time(*a):
    t = time.perf_counter(); getattr(ui, a[0])(*[int(x) if x.isdigit() else " ".join([x]) for x in a[1:]]); ui.root.update_idletasks(); log("tiempo", a, f"{(time.perf_counter() - t) * 1000:.0f} ms")
def c_eval(*a): exec(' '.join(a), globals())
def c_quit(*a): ui.close()


def poll():
    try:
        lines = open(CMD, encoding="utf-8").read().splitlines()
        if lines:
            open(CMD, "w").close()
            for ln in lines:
                p = ln.strip().split()
                if not p: continue
                try:
                    globals()["c_" + p[0]](*p[1:]); log("ok", ln)
                except Exception as e:
                    log("ERROR", ln, repr(e))
    except Exception as e:
        log("poll", repr(e))
    ui.root.after(150, poll)


ui.root.report_callback_exception = lambda *a: log("CALLBACK ERROR", repr(a[1]))
ui.root.after(300, lambda: c_idle())
ui.root.after(500, poll)
log("listo")
ui.root.mainloop()

