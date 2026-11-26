"""Ventana de LOL-E (CustomTkinter): armazón, eventos, panel de ajustes acoplado y volumen.

Las pantallas están formadas por secciones independientes (ui_sections.py) que solo se repintan cuando cambian
sus propios datos; las imágenes y utilidades comunes viven en ui_kit.py.
"""
import copy, gc, os, queue, shutil, sys, threading, time, tkinter as tk, tkinter.messagebox as messagebox
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
from PIL import Image

import lol_advisor as core
import parche
import stats
import updater
from lol_advisor import APP_NAME, APP_VERSION, CACHE, DATA_DIR, PRESET_INFO, read_json, save_conf
from ui_history import HistoryView
from ui_pool import PoolView
from ui_rail import RailNav
from ui_help import HelpWindow
from ui_views import DataView, MatchupView
from ui_kit import REC_VIEWS, ACCENTS, DISPLAY, Kit, PAL, THEMES, calm, res
from ui_game import GameView
from ui_patch import PatchView
from ui_draft import DraftCard
from ui_mayhem import AramBuild
from ui_sections import (JumpBar, CounterPicks, TourOffer,SummaryCard, AchievementsCard, BanIdeas, BansRow, Enemies, Lobby, ModesCard, PoolCard, ProfileCard, ProfileStrip, Recs, TurnCard, MyPick,
                         WaitCard)

DOCK_W = 360


MAX_W = 1240  # ancho máximo del contenido (se centra en pantallas más grandes)



def lower_priority():
    """LOL-E pasa a prioridad «por debajo de lo normal»: si Windows tiene que repartir CPU, el juego va primero. Sin efecto si falla."""
    try:
        import ctypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:
        pass

class GUI:
    def __init__(self, conf, champs):
        self.conf, self.champs = conf, champs
        self.q, self.cmds = queue.Queue(), queue.Queue()
        self.running, self.view, self.status_text, self.last_w = True, None, "", 0
        self.ctx = {"info": None, "msg": "Abre el cliente de League of Legends para empezar.", "linked": False, "r": None,
                    "session": None, "got": 0, "players": {}, "width": 520}
        start = conf.get("start_tab", "ultima")
        self.advisor, self.page, self.update_info = "idle", (conf.get("tab", "asesor") if start == "ultima" else start), None
        self.dock_inside = False
        self.dock, self.dock_open, self.docking, self.dock_dw = None, False, False, 0
        self.vol_sliders, self._rs, self._vt = [], None, None
        for f in ("ChakraPetch-Bold.ttf", "ChakraPetch-SemiBold.ttf", "ChakraPetch-Medium.ttf"):
            try:
                ctk.FontManager.load_font(res("fonts", f))
            except Exception:
                pass
        import temas
        temas.apply(conf)   # paleta y estilo guardados: antes de crear ningún widget
        ctk.set_appearance_mode(conf["theme"])
        ctk.set_widget_scaling(conf["scale"])
        self.root = ctk.CTk(fg_color=PAL["bg"])
        self.root.title(APP_NAME)
        self.initial_geometry()
        self.root.minsize(460, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.root.iconbitmap(res("icon.ico"))
        except Exception:
            pass
        self.root.bind("<Escape>", lambda e: self.close_dock())
        self.root.report_callback_exception = lambda t, v, tb: core.log_exc("Error en la ventana", (t, v, tb))
        for i, nm in enumerate([n for n in ("Asesor", "Partida", "Enfrentamiento", "Repertorio", "Historial", "Parche", "Datos") if n != "Parche" or parche.ACTIVO], 1):  # Ctrl+1…7 cambian de pestaña (en el orden de arriba)
            self.root.bind(f"<Control-Key-{i}>", lambda e, n=nm: self.set_page(n))
        self.root.bind("<F1>", lambda e: self.open_help())
        self.root.bind("<Left>", lambda e: self.key_go(-1))
        self.root.bind("<Right>", lambda e: self.key_go(1))
        self.root.bind("<Configure>", self.on_resize)
        self.root.bind("<Map>", self.on_map)
        lower_priority()
        self.kit = Kit(self.root, conf, champs, lambda ev: self.q.put((ev,)))
        self.kit.goto_history, self.kit.goto_matchup = self.goto_history, self.goto_matchup
        self.kit.launch_demo = self.launch_demo
        self.kit.set_opp, self.kit.opp_now = self.set_opp, lambda: self.opp_choice
        self.apply_window()
        self.build_shell()
        self.layout_main(self.root.winfo_width())
        self.build_views()
        self.show_view(self.effective_view())
        self.refresh_current()
        threading.Thread(target=self._prefetch, daemon=True).start()
        threading.Thread(target=self._load_items, daemon=True).start()
        plan = read_json(os.path.join(CACHE, "last_plan.json"), None)
        if plan and plan.get("cid") in champs:
            plan["state"], plan["locked"] = "done", True
            self.ctx["plan"] = plan
        gc.disable()                      # (ver gc_tick)
        self.root.after(5000, self.gc_tick)
        self.late_events = {}
        self.root.after(200, self.poll)
        self.root.after(500, self.tick)
        self.root.after(1500, self.ensure_normal)
        self.root.after(2500, self.prebuild_dock)  # el panel de ajustes se prepara con la ventana en reposo
        self.root.after(5000, self.auto_check)
        self.root.after(9000, self.patch_check)
        if not os.environ.get("LOLE_GEOMETRY"):   # la primera lectura de tus análisis (hasta 80 archivos) se hace fuera del hilo de la ventana, para que no la congele al abrir el Plan
            import patrones
            self.root.after(1200, lambda: threading.Thread(target=lambda: patrones.current(core.CACHE), daemon=True).start())
        if not os.environ.get("LOLE_GEOMETRY"):  # en las pruebas no se abre
            self.root.after(3500, self.show_notes_once)
            self.root.after(6000, self.report_failed_update)
            self.root.after(45000, self.maybe_ask_stats)
            self.root.after(90000, self.stats_tick)

    # ---------- interfaz con el motor (otro hilo: solo usa colas) ----------
    def stopped(self):
        return not self.running

    def show(self, session, r):
        self.q.put(("show", session, r, time.time()))

    def idle(self, info, msg):
        self.q.put(("idle", info, msg))

    def goto_history(self, champ_name):
        """Salta a «Historial» con el buscador puesto en un campeón."""
        h = self.history_view
        h.q, h.mode, h.res, h.line, h.limit, h.shown, h.sig = champ_name, "Todos", "Todas", "Todas", None, 20, None
        self.set_page("Historial")

    def goto_matchup(self, cid):
        """Salta a «Enfrentamiento» con ese campeón como rival."""
        self.set_page("Enfrentamiento")
        self.root.after(80, lambda: self.matchup_view.select(cid))

    def history_updated(self):
        self.q.put(("history",))

    def status(self, text):
        self.q.put(("status", text))

    def link(self, ok):
        self.q.put(("link", ok))

    def players(self, data):
        self.q.put(("players", data))

    def roster(self, ros):
        self.q.put(("roster", ros))

    def roster_players(self, data):
        self.q.put(("roster_pl", data))

    def roster_progress(self, done, total):
        self.q.put(("roster_prog", done, total))

    def poll_cmd(self):
        try:
            return self.cmds.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self.running = False
        self.root.destroy()

    # ---------- tamaño y posición, en píxeles reales (sirve con cualquier escala de Windows) ----------
    def win_scale(self):
        try:
            return ctk.ScalingTracker.get_window_scaling(self.root)
        except Exception:
            return 1.0

    def virtual_screen(self):
        """(x, y, ancho, alto) del escritorio completo, con todos los monitores (el secundario puede tener coordenadas negativas)."""
        try:
            import ctypes
            u = ctypes.windll.user32
            return u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        except Exception:
            return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def saved_geometry(self):
        """Tamaño y posición de la última vez (o de la variable LOLE_GEOMETRY de las pruebas), solo si caen dentro de algún monitor."""
        import re
        geo = os.environ.get("LOLE_GEOMETRY") or self.conf.get("win_geo") or ""
        nums = re.findall(r"-?\d+", geo)
        if len(nums) != 4:
            return None
        w, h, x, y = (int(n) for n in nums)
        vx, vy, vw, vh = self.virtual_screen()
        if w < 400 or h < 400 or not (vx - 50 < x + 150 < vx + vw) or not (vy - 10 < y + 40 < vy + vh - 60):
            return None
        return w, h, x, y

    def initial_geometry(self):
        saved = self.saved_geometry()
        if saved:
            w, h, x, y = saved
            tk.Wm.geometry(self.root, f"{w}x{h}+{x}+{y}")
            return
        s = self.win_scale()
        sh = self.root.winfo_screenheight()
        w, h = int(560 * s), min(int(900 * s), sh - int(100 * s))
        tk.Wm.geometry(self.root, f"{w}x{h}+{int(30 * s)}+{int(10 * s)}")

    def save_geometry(self):
        """Guarda dónde está la ventana para abrirla en el mismo sitio (no se guarda si es normal que esté maximizada o durante las pruebas)."""
        self._gs = None
        if os.environ.get("LOLE_GEOMETRY"):
            return
        try:
            if self.root.state() == "normal":
                self.conf["win_geo"] = tk.Wm.geometry(self.root)   # píxeles reales: `root.geometry()` de CustomTkinter los divide por la escala
                save_conf(self.conf)
        except Exception:
            pass

    PHASE_ES = {"Matchmaking": "En cola", "ReadyCheck": "Partida encontrada", "ChampSelect": "En selección", "GameStart": "Empieza la partida",
                "InProgress": "Partida en curso", "Reconnect": "Reconectando"}

    def open_help(self):
        """La ayuda de la pantalla actual y las preguntas frecuentes (F1)."""
        if not hasattr(self, "help_win"):
            self.help_win = HelpWindow(self)
        self.help_win.open(self.tab_names.get(self.page))

    def launch_demo(self, lessons=None):
        """Abre la demostración en otra ventana (otro proceso, con datos inventados). `lessons`: ids de lecciones para empezar directamente por ellas."""
        import subprocess
        cmd = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.join(os.path.dirname(os.path.abspath(core.__file__)), "app.py")]
        cmd.append("--demo")
        if lessons:
            cmd.append("--leccion=" + ",".join(lessons))
        try:
            subprocess.Popen(cmd, close_fds=True, **{k: v for k, v in core.quiet().items() if k != "stdin"})
        except Exception as e:
            core.log_exc("Abrir la demostración")
            self.status(f"No se ha podido abrir la demostración ({type(e).__name__}).")

    def help_go(self, dest):
        """«Enséñamelo»: lleva a la pantalla de una pregunta de la ayuda (o abre Ajustes)."""
        self.root.deiconify()
        if dest == "ajustes":
            if not self.dock_open:
                self.open_dock()
        else:
            self.set_page(dest)
        self.root.lift()
        if hasattr(self, "help_win") and self.help_win.alive():
            self.help_win.refresh_page(self.tab_names.get(self.page))

    def band_click(self):
        self.set_page("Asesor" if self.page == "partida" else "Partida")

    def update_band(self):
        """Estado del modo en vivo: tiñe la barra lateral y muestra (o esconde) la banda de arriba con la fase, el campeón y el botón de ir y volver."""
        phase = self.ctx.get("phase")
        live = self.advisor == "select" or phase in self.PHASE_ES
        self.tab_seg.set_live(live)
        plan = self.ctx.get("plan") or {}
        champ = core.name(plan["cid"], self.champs) if plan.get("cid") in self.champs else ""
        label = self.PHASE_ES.get(phase) or ("En selección" if self.advisor == "select" else "")
        clock = ""
        try:   # el reloj de la banda: el tiempo de tu turno en la selección, o el de la partida (de la última lectura en directo, avanzado con el reloj local)
            if self.advisor == "select" and self.ctx.get("session"):
                secs, inf = core.timer_left(self.ctx["session"], self.ctx["got"])
                clock = "" if inf else f"{int(secs) // 60}:{int(secs) % 60:02d}"
            elif phase in ("InProgress", "GameStart", "Reconnect") and self.ctx.get("live") and self.ctx.get("live_at"):
                age = time.time() - self.ctx["live_at"]
                if age <= 30:   # sin lecturas hace rato (cliente caído o juego cerrado) no se sigue contando como si estuviera vivo; y no se adelanta más de una lectura
                    t = int(self.ctx["live"]["t"] + min(age, 12))
                    clock = f"{t // 60}:{t % 60:02d}"
        except Exception:
            clock = ""
        sig = (live, label, champ, self.page == "partida", clock)
        if sig == self.band_sig:
            return
        self.band_sig = sig
        if not live:
            self.band.pack_forget()
            return
        self.band_txt.configure(text=f"●  {label}" + (f"  ·  {clock}" if clock else "") + (f"  ·  {champ}" if champ else ""))
        selecting = self.advisor == "select" and phase not in ("GameStart", "InProgress", "Reconnect")
        if self.page == "partida":
            self.band_btn.configure(text="Volver a la selección" if selecting else "Ir a Inicio")
        else:
            self.band_btn.configure(text="Ver mi plan" if selecting else "Ver mi partida")
        if not self.band.winfo_ismapped():
            self.band.pack(fill="x", padx=16, pady=(8, 0), before=self.mid)

    def hidden(self):
        """La ventana está minimizada u oculta: repintarla no la ve nadie."""
        try:
            return self.root.state() in ("iconic", "withdrawn")
        except Exception:
            return False

    def on_map(self, e):
        """La ventana vuelve a verse: si llegaron datos en vivo mientras estaba minimizada, se pintan ahora."""
        if e.widget is self.root and getattr(self, "_live_pending", False):
            self._live_pending = False
            if self.view == "game":
                self.root.after(50, lambda: self.game_view.refresh(self.make_ctx(), True))

    def ensure_normal(self):
        """Si Windows dejó la ventana maximizada sin que lo pidas, la devolvemos a su tamaño."""
        try:
            if self.root.state() == "zoomed":
                self.root.state("normal")
                self.initial_geometry()
        except Exception:
            pass

    # ---------- bucle de la ventana ----------
    def poll(self):
        if not self.running:
            return
        evs = []
        try:
            while True:
                evs.append(self.q.get_nowait())
        except queue.Empty:
            pass
        for ev in evs:
            kind = ev[0]
            if kind == "show":
                self.pending_show = ev  # de varios cambios seguidos solo cuenta el último
                continue
            if kind == "assets":
                if not self.assets_pending:
                    self.assets_since = time.time()
                self.assets_pending = True   # cada imagen descargada avisaba y repintaba TODO (1-2 s): ahora una ráfaga de imágenes cuenta como un solo repintado
                continue
            if kind in ("players", "recs_data", "splash"):   # llegan de uno en uno (un aviso por jugador o por consulta): solo cuenta el último y se aplica de vez en cuando
                self.late_events[kind] = ev
                continue
            if kind == "idle":
                self.pending_show = None
            try:
                self.handle_event(ev, kind)
            except Exception as e:  # un dato raro no debe dejar la ventana sin actualizarse
                self.event_failed(kind, e)
        if self.late_events and time.time() - self.last_late_t >= 0.6:
            pending, self.late_events = self.late_events, {}
            self.last_late_t = time.time()
            for k_, ev_ in pending.items():
                try:
                    self.handle_event(ev_, k_)
                except Exception as e:
                    self.event_failed(k_, e)
        busy_fetch = getattr(getattr(self, "kit", None), "inflight", 0) > 0 and time.time() - self.assets_since < 4   # mientras bajan imágenes se espera (hasta 4 s)
        if self.assets_pending and not busy_fetch and time.time() - self.last_assets_t >= 0.8:   # como mucho un repintado por imágenes cada 0,8 s (y tras dejar pasar la ráfaga)
            self.assets_pending = False
            self.last_assets_t = time.time()
            try:
                self.handle_event(("assets",), "assets")
            except Exception as e:
                self.event_failed("assets", e)
        if self.pending_show is not None and time.time() - self.last_show_t >= 0.6:  # como mucho ~1,5 repintados por segundo
            ev, self.pending_show = self.pending_show, None
            self.last_show_t = time.time()
            try:
                self.handle_event(ev, "show")
            except Exception as e:
                self.event_failed("show", e)
        self.root.after(150, self.poll)

    def event_failed(self, kind, e):
        """Un fallo al pintar: se guarda en el registro (antes solo pasaba por el pie y se perdía) y se dice dónde mirarlo."""
        core.log_exc(f"Evento de la ventana «{kind}»")
        self.status(f"No se pudo actualizar esta pantalla ({type(e).__name__}). Se reintenta con el siguiente cambio; "
                    "el detalle está en Ajustes › «Abrir el registro de errores».")

    pending_show, last_show_t, last_turn = None, 0.0, None
    assets_pending, last_assets_t, assets_since = False, 0.0, 0.0
    last_late_t = 0.0
    auto_game = False

    def analysis(self, gid, data):
        self.q.put(("analysis", gid, data))

    def phase(self, flow):
        self.q.put(("phase", flow))

    def update_plan(self, r):
        """Guarda el campeón que has marcado o bloqueado y su contexto: la pestaña «Partida» lo enseña después."""
        kind = r["mode"]["kind"]
        if not r.get("mine") or r["mine"] not in self.champs:
            # selección nueva sin campeón marcado: el plan de la partida anterior ya no vale (antes se quedaba y salía su build)
            if (self.ctx.get("plan") or {}).get("state") != "select":
                self.ctx["plan"] = None
                try:
                    os.remove(os.path.join(CACHE, "last_plan.json"))
                except OSError:
                    pass
            return
        sr = kind == "sr"   # ARAM, Arena, etc.: solo el campeón, sin línea ni rivales (no hay build de línea)
        plan = {"cid": r["mine"], "role": (r.get("role") or "") if sr else "", "opp": (r.get("lane_opp") or 0) if sr else 0, "opp_auto": (r.get("lane_opp_auto") or 0) if sr else 0,
                "enemies": list(r["enemies"]) if sr else [], "allies": list(r["allies"]) if sr else [], "locked": bool(r.get("mine_locked")),
                "state": "select", "kind": kind, "group": r["mode"].get("group", ""), "mayhem": r["mode"].get("id") in (2400,), "qid": r["mode"].get("id")}
        if plan != {**(self.ctx.get("plan") or {}), "state": "select"}:
            self.ctx["plan"] = plan
            try:
                core.write_json(os.path.join(CACHE, "last_plan.json"), plan)
            except Exception:
                pass
        elif (self.ctx.get("plan") or {}).get("state") != "select":
            self.ctx["plan"] = plan

    def new_cycle(self):
        """Empieza una cola nueva (buscando, partida encontrada o selección): la pestaña «Partida» olvida lo de la anterior (plan, marcador en vivo, mejoras de
        Mayhem, jugadores, pestaña Análisis). Antes cada cosa se reiniciaba en un sitio distinto y, según cómo acabara la partida, quedaba algo suelto.
        Si ya hay un plan de ESTA selección o partida en curso no se toca."""
        c = self.ctx
        MyPick.opened.clear()   # las builds abiertas a mano son de la selección anterior
        import ui_build, ui_mayhem
        ui_build.OPEN_RUNES.clear()
        ui_mayhem.OPEN_MORE.clear()
        pl = c.get("plan")
        if pl and pl.get("state") in ("select", "game"):
            return
        c["plan"] = None
        for k in ("live", "live_at", "live_aug", "roster"):
            c[k] = None
        c["roster_pl"] = {}
        self.buy_notified = set()
        self.opp_choice = 0
        gv = self.game_view
        gv.tab, gv.sig, gv.auto_try = "Plan", None, 0
        try:
            os.remove(os.path.join(CACHE, "last_plan.json"))
        except OSError:
            pass
        if self.view == "game":
            gv.refresh(self.make_ctx(), True)

    def on_phase(self, flow):
        plan = self.ctx.get("plan")
        if plan and plan.get("state") == "select" and flow in ("Lobby", "Matchmaking", "ReadyCheck", "None", None):
            plan["state"] = "done"   # la selección se abandonó (esquive, cola cancelada): ese plan ya no es de una selección en curso
        elif plan and plan.get("state") == "game" and flow in ("Matchmaking", "ReadyCheck"):
            plan["state"] = "done"   # ya se está en otra cola: la partida anterior acabó aunque no se vieran las fases de fin (cliente cerrado o reiniciado)
        if flow in ("Matchmaking", "ReadyCheck", "ChampSelect") and self.ctx.get("phase") not in ("Matchmaking", "ReadyCheck", "ChampSelect"):
            self.new_cycle()
            plan = self.ctx.get("plan")
        self.ctx["phase"] = flow
        if not plan:
            return
        if flow in ("InProgress", "GameStart", "Reconnect"):
            if plan["state"] != "game":
                plan["state"] = "game"
                self.game_view.tab = "Plan"   # al empezar la partida se ve el plan, no el análisis de la anterior
                self.game_view.sig = None
                if self.page == "asesor":  # empieza la partida: la ventana enseña tu plan en vez de volver al inicio
                    self.auto_game = True
                    self.page = "partida"
                    self.tab_seg.set("Partida")
                    self.apply_page()
                elif self.view == "game":
                    self.game_view.refresh(self.make_ctx(), True)
        elif flow in ("PreEndOfGame", "EndOfGame", "WaitingForStats", "Lobby", "None", None) and plan["state"] == "game":
            plan["state"] = "done"
            if self.view == "game":
                self.game_view.refresh(self.make_ctx(), True)

    def on_roster(self, ros):
        """Pantalla de carga: ya se sabe quién juega cada línea. Se guardan los 10 jugadores y, con ellos, el plan se afina:
        los rivales reales, su línea y tu rival directo (sin adivinar)."""
        self.ctx["roster"], self.ctx["roster_pl"] = ros, {}
        plan = self.ctx.get("plan")
        if plan and plan.get("kind") in (None, "sr"):
            enemies = [x["cid"] for x in ros if x["team"] == "enemy" and x["cid"]]
            me = next((x for x in ros if x["me"]), None)
            if not plan.get("role") and me and me["role"]:
                plan["role"] = me["role"]
            plan["enemies"] = enemies
            plan["allies"] = [x["cid"] for x in ros if x["team"] == "ally" and not x["me"] and x["cid"]]
            opp = next((x["cid"] for x in ros if x["team"] == "enemy" and x["role"] and x["role"] == plan.get("role") and x["cid"]), 0)
            if opp:
                plan["opp_auto"] = opp
            if self.opp_choice and self.opp_choice not in enemies:
                self.opp_choice = 0
            plan["opp"] = self.opp_choice or plan.get("opp_auto") or plan.get("opp") or 0
            try:
                core.write_json(os.path.join(CACHE, "last_plan.json"), plan)
            except Exception:
                pass
        if not plan and self.page == "asesor" and self.view in ("idle", None):   # sin campeón marcado: igualmente se enseña la partida
            self.auto_game = True
            self.page = "partida"
            self.tab_seg.set("Partida")
            self.game_view.tab = "Plan"
            self.apply_page()
        elif self.view == "game":
            self.game_view.sig = None
            self.game_view.refresh(self.make_ctx(), True)

    def handle_event(self, ev, kind):
        if True:
            if True:
                if kind == "show":
                    _, session, r, got = ev
                    self.ctx.update(session=session, r=r, got=got)
                    first = self.advisor != "select"
                    self.advisor = "select"
                    if first:
                        self.new_cycle()   # selección nueva: lo de la partida anterior ya no vale (rival elegido a mano, jugadores, marcador, plan…)
                        self.opp_choice = 0
                        self.ctx["roster"], self.ctx["roster_pl"] = None, {}
                    self.apply_opp(r)
                    self.update_plan(r)
                    self.infer_lane_opp()
                    if first and self.auto_game and self.page == "partida":  # nueva selección: se vuelve al Asesor
                        self.auto_game = False
                        self.page = "asesor"
                        self.tab_seg.set("Asesor")
                    self.apply_window()
                    if first and self.conf.get("topmost_mode", "seleccion") != "nunca":
                        try:
                            if self.root.state() == "iconic":
                                self.root.deiconify()  # empieza la selección: la ventana vuelve para que la veas
                        except Exception:
                            pass
                    turn = r.get("turn")
                    self.kit.anim = first or turn != self.last_turn  # solo se anima al empezar o al cambiar tu turno: no en cada gesto de otros
                    self.last_turn = turn
                    self.apply_page()
                    self.kit.anim = False
                elif kind == "idle":
                    self.ctx.update(info=ev[1], msg=ev[2], players={})
                    reconectando = (ev[2] or "").startswith("Conectado") and self.ctx.get("phase") in ("InProgress", "GameStart", "Reconnect")   # el cliente volvió en plena partida: el marcador y los avisos de compra siguen valiendo
                    if ev[2] and "Partida en curso" not in ev[2] and not reconectando:
                        self.ctx["live"] = None   # fuera de la partida el marcador en vivo ya no vale
                        self.buy_notified = set()
                    self.advisor = "idle"
                    self.apply_window()  # fuera de la selección se comporta como cualquier otra ventana (Alt+Tab)
                    self.kit.anim = True
                    self.apply_page()
                    self.kit.anim = False
                elif kind == "players":
                    self.ctx["players"] = ev[1]
                    if self.view == "select":
                        self.infer_lane_opp()
                        cx = self.make_ctx()
                        for sec in (self.lobby, self.enemies, self.draft):
                            sec.refresh(cx)
                elif kind == "call":   # una función que otro hilo pide ejecutar en el de la ventana
                    ev[1]()
                elif kind == "roster":
                    self.on_roster(ev[1])
                elif kind == "roster_prog":   # solo cambia el contador: no se redibuja el tablero
                    lab = getattr(self.game_view, "roster_lbl", None)
                    try:
                        if lab is not None and lab.winfo_exists():
                            lab.configure(text=f"Leyendo perfiles… {ev[1]} de {ev[2]}")
                    except Exception:
                        pass
                elif kind == "roster_pl":
                    self.ctx["roster_pl"] = ev[1]
                    if self.view == "game":
                        self.game_view.refresh(self.make_ctx(), True)
                elif kind == "live":
                    self.note_unknown_items(ev[1])
                    self.ctx["live"] = ev[1]
                    self.ctx["live_at"] = time.time()
                    self.buy_alert(ev[1])
                    if self.view == "game":
                        if self.hidden():   # ventana minimizada: no se repinta nada (el PC es del juego); al volver se pinta de una vez
                            self._live_pending = True
                        else:
                            self.game_view.on_live(self.make_ctx())
                elif kind == "live_aug":
                    self.ctx["live_aug"] = ev[1]
                    if self.view == "game":
                        self.game_view.refresh(self.make_ctx(), True)
                elif kind == "status":
                    self.status_text = ev[1]
                    self.update_footer()
                elif kind == "link":
                    self.ctx["linked"] = ev[1]
                    self.update_link()
                    if not ev[1] and self.advisor == "select":
                        self.leave_select()
                    if self.view == "idle":
                        self.refresh_current()
                elif kind == "assets":
                    self.kit.epoch += 1  # llegaron imágenes: lo que las usa se repinta una vez
                    self.refresh_current()
                elif kind == "splash" and self.view == "select":
                    self.recs.render()
                elif kind == "analysis":
                    pl = self.ctx.get("plan")
                    if ev[2] and pl and pl.get("state") == "done" and self.page == "partida" and self.game_view.tab != "Análisis":
                        self.game_view.tab, self.game_view.gid = "Análisis", ev[1]   # acabó la partida: se enseña su análisis solo
                    self.game_view.on_data(ev[1], ev[2])
                elif kind == "game_data":
                    self.game_view.on_vs()
                elif kind == "phase":
                    self.on_phase(ev[1])
                elif kind == "recs_data" and self.view == "select":
                    self.recs.render()
                    self.counter_picks.refresh(self.make_ctx())
                elif kind == "matchup" and self.view == "matchup":
                    self.matchup_view.update(self.make_ctx())
                elif kind == "history":
                    self.history_view.data_changed()
                    self.pool_view.data_changed()
                elif kind == "parche":
                    self.patch_view.data_changed()
                elif kind == "parche_new":
                    self.tab_seg.set_badge("Parche", True)
                elif kind == "parche_seen":
                    self.conf["parche_visto"] = ev[1]
                    save_conf(self.conf)

                elif kind == "update":
                    self.on_update(ev[1], ev[2], ev[3])
                elif kind == "update_fail":
                    self.update_btn.configure(state="normal", text=f"Actualizar a {self.update_info['version']}")
                elif kind == "update_ready":
                    self.apply_update(ev[1], ev[2] if len(ev) > 2 else False)

    def tick(self):
        if not self.running:
            return
        try:   # la barra lateral y la banda se tiñen de ámbar mientras hay cola, selección o partida
            self.update_band()
        except Exception:
            core.log_exc("Banda del modo en vivo")
        if self.view == "select" and self.ctx["session"]:
            self.turn.tick(self.ctx)
        self.root.after(500, self.tick)

    # ---- el recolector de basura, solo en el hilo de la ventana ----
    # Los objetos de Tkinter (fuentes, variables, imágenes) llaman a Tk al destruirse. Si el recolector de basura de Python los
    # destruye desde OTRO hilo mientras la ventana está esperando a ese hilo (p. ej. dentro de Thread.start(), que espera a que el hilo
    # nuevo arranque), Tk deja al hilo esperando a la ventana y la ventana al hilo: interbloqueo y ventana congelada para siempre.
    # Se vio de forma reproducible en el recorrido de pantallas al pedir una build de Mayhem (pila: Font.__del__ dentro del arranque de
    # un hilo). Por eso el recolector automático se apaga y se ejecuta aquí, en el hilo principal.
    def gc_tick(self):
        if not self.running:
            return
        self._gc_n = getattr(self, "_gc_n", 0) + 1
        try:
            gc.collect(2 if self._gc_n % 12 == 0 else 1)   # cada 5 s la generación joven; cada minuto, todo
        except Exception:
            pass
        self.root.after(5000, self.gc_tick)

    def _prefetch(self):
        d = os.path.join(CACHE, "icons")
        os.makedirs(d, exist_ok=True)
        got = []

        def get(c):
            p = os.path.join(d, f"{c.get('icon', '')}.png")
            if c.get("icon") and core.DD_VERSION and not os.path.exists(p):
                try:
                    import urllib.request
                    urllib.request.urlretrieve(
                        f"https://ddragon.leagueoflegends.com/cdn/{core.DD_VERSION}/img/champion/{c['icon']}.png", p + ".tmp")
                    os.replace(p + ".tmp", p)
                    got.append(1)
                except Exception:
                    pass
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(get, self.champs.values()))
        if got:
            self.q.put(("assets",))

    def _load_items(self):
        """Objetos del juego (Data Dragon) y los iconos que aparecen en tu historial."""
        try:
            import history, items
            if not core.DD_VERSION:
                return
            self.kit.items = items.load(CACHE, core.DD_VERSION)
            try:
                import runes
                self.kit.runedata = runes.load(CACHE, core.DD_VERSION)
            except Exception:
                pass
            used = {i for e in history.load_all(history.hpath(CACHE), history.gpath(CACHE))[:150]
                    for i in (e.get("it") or []) if i}
            d = os.path.join(CACHE, "items")
            os.makedirs(d, exist_ok=True)
            import urllib.request

            def get(i):
                p = os.path.join(d, f"{i}.png")
                if not os.path.exists(p):
                    try:
                        urllib.request.urlretrieve(items.icon_url(core.DD_VERSION, i), p + ".tmp")
                        os.replace(p + ".tmp", p)
                        return 1
                    except Exception:
                        return 0
                return 0
            with ThreadPoolExecutor(8) as ex:
                got = sum(ex.map(get, used))
            if got or self.kit.items:
                self.q.put(("assets",))
        except Exception:
            pass

    # ---------- actualizaciones ----------
    UPDATE_EVERY = 3 * 3600 * 1000     # se vuelve a mirar cada 3 horas: quien deja LOL-E abierto también se actualiza
    BUSY = ("Matchmaking", "ReadyCheck", "ChampSelect", "GameStart", "InProgress", "Reconnect", "PreEndOfGame", "EndOfGame", "WaitingForStats")   # al acabar, LOL-E aún espera el cambio de PL y analiza la partida

    def busy(self):
        """¿Hay cola, selección, partida o cierre de partida en curso? Con eso no se instala nada: el instalador cierra la app."""
        return self.advisor == "select" or self.ctx.get("phase") in self.BUSY or (self.ctx.get("plan") or {}).get("state") in ("select", "game")
    installing = False

    def patch_check(self):
        """Mira si Riot ha publicado un parche nuevo (la lista de notas, ligera) y, si es así, deja un punto de aviso en «Parche» y precarga sus notas.
        La primera vez que se ejecuta solo apunta cuál es el último: no avisa de lo que ya existía. Con una partida en marcha espera."""
        if not parche.ACTIVO:
            return
        if self.running and not self.installing:
            if self.ctx.get("phase") in self.BUSY or self.advisor == "select":
                self.root.after(30 * 60 * 1000, self.patch_check)
                return

            def go():
                try:
                    import parche
                    vs = parche.versions(CACHE, force=True)
                    if vs:
                        self.patch_view.versions = vs
                        seen = self.conf.get("parche_visto")
                        is_new = bool(seen and seen != vs[0])
                        if not seen:
                            self.q.put(("parche_seen", vs[0]))   # primera vez: solo se apunta cuál es el último, sin avisar
                        elif seen != vs[0]:
                            self.q.put(("parche_new",))
                            if self.__dict__.get("_patch_told") != vs[0]:
                                self._patch_told = vs[0]
                                self.status(f"Hay un parche nuevo: {vs[0]}. Sus notas oficiales están en «Parche».")
                        try:
                            fresh = parche.load(CACHE, vs[0], latest=vs[0])   # precarga: al abrir la pantalla ya están
                            if isinstance(fresh, dict):
                                self.patch_view.notes[vs[0]] = fresh   # y si Riot corrigió las notas del parche actual, se ven sin reiniciar
                                if is_new and self.__dict__.get("_patch_told_mine") != vs[0]:
                                    names = self.patch_view.touched_mine(fresh)
                                    if names:   # lo que más le importa a quien juega: si el parche toca a sus campeones
                                        self._patch_told_mine = vs[0]
                                        self.status(f"Parche {vs[0]}: las notas afectan a {len(names)} de tus campeones ({', '.join(names[:4])}{'…' if len(names) > 4 else ''}). Míralo en «Parche».")
                        except Exception:
                            pass
                except Exception:
                    core.log_exc("Comprobar parche nuevo")
            threading.Thread(target=go, daemon=True).start()
        self.root.after(3 * 3600 * 1000, self.patch_check)

    def patch_seen(self):
        """Se está mirando «Parche»: el aviso de parche nuevo ya está atendido."""
        vs = self.patch_view.versions
        if vs and self.conf.get("parche_visto") != vs[0]:
            self.conf["parche_visto"] = vs[0]
            save_conf(self.conf)
        self.tab_seg.set_badge("Parche", False)

    # ---------- cuenta anónima de instalaciones (voluntaria; ver stats.py) ----------
    def maybe_ask_stats(self):
        """Pregunta una sola vez si quiere contar su instalación. Solo si hay servidor, nunca durante cola, selección ni partida, y «No, gracias» es lo destacado."""
        if not self.running or not stats.more_asks(self.conf):
            return
        if not stats.should_ask(self.conf):
            self.root.after(6 * 3600 * 1000, self.maybe_ask_stats)   # aún no ha pasado la semana desde la última vez
            return
        if self.busy() or getattr(self, "notes_win", None) is not None:
            self.root.after(5 * 60 * 1000, self.maybe_ask_stats)
            return
        import ui_stats
        self.conf["stats_asked"] = int(self.conf.get("stats_asked") or 0) + 1
        self.conf["stats_ask_t"] = time.time()
        save_conf(self.conf)
        ui_stats.ConsentWindow(self, self.stats_answer, last=self.conf["stats_asked"] >= stats.MAX_ASKS)

    def stats_answer(self, res):
        """Respuesta de la ventana de permiso: «yes», «later» (ya está anotado cuándo; se vuelve a preguntar en una semana, hasta 3 veces) o «never»."""
        if res == "yes":
            self.stats_set(True)
        elif res == "never":
            self.stats_set(False)
        else:
            if stats.more_asks(self.conf):
                self.root.after(6 * 3600 * 1000, self.maybe_ask_stats)
            else:
                self.conf["stats_optin"] = False   # tercera vez sin aceptar: no se pregunta más (sigue disponible en Ajustes › Privacidad)
                save_conf(self.conf)

    def stats_set(self, on):
        """Aplica la decisión del usuario (ventana de permiso o interruptor de Ajustes)."""
        if on:
            self.conf["stats_optin"] = True
            self.conf["stats_id"] = self.conf.get("stats_id") or stats.new_id()
            self.conf["stats_last"] = 0
            save_conf(self.conf)
            threading.Thread(target=lambda: stats.ping(self.conf, APP_VERSION, save=save_conf), daemon=True).start()
            self.status("Gracias: LOL-E avisará una vez al día, de forma anónima, de que está instalada.")
        else:
            old = {"stats_id": self.conf.get("stats_id") or ""}
            self.conf["stats_optin"], self.conf["stats_id"], self.conf["stats_last"] = False, "", 0
            save_conf(self.conf)
            if old["stats_id"]:
                threading.Thread(target=lambda: stats.forget(old), daemon=True).start()   # el servidor borra el registro de esta instalación
            self.status("Hecho: no se enviará nada y se ha pedido borrar el registro de esta instalación.")

    def stats_tick(self):
        """Cada rato mira si toca avisar (una vez al día como mucho), fuera de cola, selección y partida."""
        try:
            if stats.enabled() and self.running and not self.busy() and stats.due(self.conf):
                threading.Thread(target=lambda: stats.ping(self.conf, APP_VERSION, save=save_conf), daemon=True).start()
        except Exception:
            core.log_exc("Aviso anónimo de instalación")
        self.root.after(30 * 60 * 1000, self.stats_tick)

    def report_failed_update(self):
        """Si la actualización anterior no llegó a completarse (el instalador falló con la app ya cerrada), se dice y se anota en el registro."""
        to = updater.check_pending(CACHE, APP_VERSION)
        if to:
            core.diag(f"La actualización a la {to} no se completó (se sigue en la {APP_VERSION})")
            self.status(f"La actualización a la {to} no se completó. Pulsa «Actualizar» para reintentarla; si sigue fallando, descarga LOL-E de nuevo desde GitHub.")

    def apply_update(self, path, forced=False):
        """Lanza el instalador ya descargado y comprobado. Si mientras se descargaba empezó una cola o una partida, espera (salvo si lo pidió el usuario con el botón).
        Si el instalador no se puede lanzar (antivirus, archivo borrado), la app sigue abierta y lo dice."""
        if not forced and self.busy():
            self.status("Actualización descargada: se instalará cuando acabe la partida o la cola.")
            self.root.after(120000, lambda: self.apply_update(path, forced))
            return
        try:
            updater.mark_pending(CACHE, path)
            updater.install(path)
        except Exception as e:
            try:
                os.remove(updater.pending_file(CACHE))   # no se llegó a lanzar: ya se avisa aquí, no hace falta el aviso de «no se completó» al volver a abrir
            except OSError:
                pass
            self.installing = False
            self.update_btn.configure(state="normal", text=f"Actualizar a {(self.update_info or {}).get('version', '')}".strip())
            self.status(f"No se pudo lanzar el instalador ({type(e).__name__}). Pulsa «Actualizar» para reintentarlo; si sigue fallando, descarga LOL-E de nuevo desde GitHub.")
            core.diag(f"Actualización: no se pudo lanzar {path}: {type(e).__name__} {e}")
            return
        self.root.after(800, self.close)   # el instalador reabre LOL-E al terminar
        self.close()

    def auto_check(self):
        if self.conf["auto_update"] and self.conf["update_url"] and not self.installing:
            self.check_updates(False)
        self.root.after(self.UPDATE_EVERY, self.auto_check)

    def auto_install(self, info):
        """Instala la versión nueva sin preguntar. Solo con la ventana en reposo: si hay cola, selección o partida, espera y vuelve a probar."""
        if self.installing or not self.running:
            return
        if self.busy():
            if not getattr(self, "_install_wait", None):   # un solo reintento pendiente (cada comprobación de 3 h añadía otra cadena)
                def again():
                    self._install_wait = None
                    self.auto_install(info)
                self._install_wait = self.root.after(120000, again)
            return
        self.installing = True
        self.status(f"Actualizando LOL-E a la versión {info['version']}…")

        def go():
            try:
                path = updater.download(info)
                self.q.put(("update_ready", path, False))
            except Exception as e:
                self.installing = False
                self.status(f"No se ha podido actualizar solo ({e}). Pulsa «Actualizar» cuando quieras.")
                self.update_fails = getattr(self, "update_fails", 0) + 1
                if self.update_fails <= 5:   # un fallo de red pasajero no deja la versión antigua hasta la próxima comprobación
                    self.q.put(("call", lambda: self.root.after(120000, lambda: self.auto_install(info))))   # Tk solo desde su hilo
        threading.Thread(target=go, daemon=True).start()

    def ver_note(self, text, color="dim", ms=8000):
        """Mensaje junto al número de versión (resultado de buscar actualizaciones); a los pocos segundos vuelve a ser solo «vX.Y.Z»."""
        lab = getattr(self, "ver_lbl", None)
        if lab is None:
            return
        try:
            lab.configure(text=f"v{APP_VERSION}" + (f"  ·  {text}" if text else ""), text_color=PAL[color])
            self._ver_seq = getattr(self, "_ver_seq", 0) + 1
            n = self._ver_seq
            if text and ms:
                self.root.after(ms, lambda: n == self._ver_seq and self.ver_note("", "dim"))
        except Exception:
            pass

    def check_updates(self, manual):
        if manual:
            if self.__dict__.get("_checking"):
                return
            self._checking = True
            self.ver_note("buscando…", "info", 0)
        def go():
            try:
                info = updater.check(self.conf["update_url"], APP_VERSION)
                self.q.put(("update", info, None, manual))
            except Exception as e:
                self.q.put(("update", None, str(e), manual))
        threading.Thread(target=go, daemon=True).start()
        if manual:
            self.status("Buscando actualizaciones…")

    def on_update(self, info, err, manual):
        if manual:
            self._checking = False
        if err:
            # también en la comprobación automática: antes fallaba en silencio y no se reintentaba hasta 3 horas después
            self.status(f"No se ha podido comprobar si hay actualizaciones: {err}")
            if manual:
                sin_red = any(x in str(err).lower() for x in ("urlopen", "getaddrinfo", "timed out", "connection", "winerror", "curl"))
                self.ver_note("sin conexión con el servidor de actualizaciones" if sin_red else "no se pudo comprobar (ver el pie de la ventana)", "warn")
            self.update_fails = getattr(self, "update_fails", 0) + 1
            if not manual and self.update_fails <= 5:
                self.root.after(120000, lambda: self.check_updates(False))
            return
        self.update_fails = 0
        if info is None:
            self.update_info = None   # puede que retiraran la versión nueva: el botón ya no tiene a qué llevar
            if not self.installing:
                self.update_btn.pack_forget()
            if manual:
                self.status(f"Estás al día: la versión {APP_VERSION} es la más reciente.")
                self.ver_note("al día ✓", "good")
            return
        if manual:
            self.ver_note(f"hay una nueva: {info['version']}", "info")
        self.update_info = info
        self.update_btn.configure(text=f"Actualizar a {info['version']}")
        self.update_btn.pack(side="right", padx=(0, 12))
        self.status(f"Hay una versión nueva: {info['version']}")
        if self.conf.get("auto_install", True) and not manual:
            self.auto_install(info)

    def confirm_update(self):
        info = self.update_info
        if not info or self.installing:
            return   # ya se está descargando (a mano o sola): una segunda descarga pisaría el archivo
        notes = info.get("notes", "")
        aviso = "\n\nOJO: hay una cola, una selección o una partida en curso. LOL-E se cerrará durante unos segundos: mejor espera a que acabe." if self.busy() else ""
        if not messagebox.askyesno(APP_NAME, f"Hay una versión nueva de {APP_NAME}: {info['version']}.\n\n{notes}\n\n"
                                   "Se descargará el instalador, se comprobará su huella de seguridad y LOL-E se cerrará para "
                                   f"actualizarse. Tus datos y ajustes se conservan.{aviso}\n\n¿Actualizar ahora?"):
            return
        self.installing = True
        self.update_btn.configure(state="disabled", text="Descargando…")

        def go():
            try:
                path = updater.download(info, lambda f: self.status(f"Descargando la actualización… {f:.0%}"))
                self.q.put(("update_ready", path, True))
            except Exception as e:
                self.installing = False
                self.status(f"No se ha podido actualizar: {e}")
                self.q.put(("update_fail",))
        threading.Thread(target=go, daemon=True).start()

    def leave_select(self):
        """El cliente se cerró a mitad de selección: se deja de mostrar como si siguiera."""
        self.advisor = "idle"
        plan = self.ctx.get("plan")
        if plan and plan.get("state") == "select":
            plan["state"] = "done"
        self.apply_window()
        self.apply_page()
        self.update_band()

    def apply_window(self):
        """«Siempre visible» solo cuando lo pides: nunca, durante la selección de campeón (por defecto) o siempre."""
        mode = self.conf.get("topmost_mode", "seleccion")
        top = mode == "siempre" or (mode == "seleccion" and self.advisor == "select")
        try:
            self.root.attributes("-topmost", bool(top))
        except Exception:
            pass

    # ---------- estructura fija: cabecera, cuerpo con scroll, pie ----------
    def build_shell(self):
        k = self.kit
        self.main = ctk.CTkFrame(self.root, fg_color="transparent", corner_radius=0)
        tk.Place.place_configure(self.main, x=0, y=0, relwidth=1.0, relheight=1.0)  # ancho propio: no depende de la ventana
        bar = k.frame(self.main)
        bar.pack(fill="x", padx=16, pady=(16, 2))
        try:
            im = Image.open(res("icon.png")).convert("RGBA").resize((64, 64), Image.LANCZOS)
            self.logo = ctk.CTkImage(light_image=im, dark_image=im, size=(32, 32))
            ctk.CTkLabel(bar, image=self.logo, text="").pack(side="left", padx=(0, 12))
        except Exception:
            pass
        k.clbl(bar, APP_NAME, 22, "fg", True, True).pack(side="left")
        self.ver_lbl = k.clbl(bar, f"v{APP_VERSION}", 10, "dim")
        self.ver_lbl.pack(side="left", padx=(8, 0), pady=(8, 0))
        k.clickable(self.ver_lbl, lambda: self.check_updates(True))   # pulsar la versión busca actualizaciones sin cerrar nada
        k.tip(self.ver_lbl, "Pulsa para buscar actualizaciones")
        ajustes = ctk.CTkButton(bar, text="Ajustes", width=88, height=32, corner_radius=10, font=k.font(12), border_width=1,
                                border_color=PAL["edge"], fg_color=PAL["card"], hover_color=PAL["card"], text_color=PAL["fg"],
                                command=self.toggle_dock)
        ajustes.pack(side="right")
        k.smooth_btn(ajustes, PAL["card"], PAL["card2"])
        # «Datos» (fuentes, cálculo de la afinidad, umbrales y glosario) es consulta de referencia, no una pestaña de uso diario: botón junto a Ajustes
        self.datos_btn = ctk.CTkButton(bar, text="Datos", width=74, height=32, corner_radius=10, font=k.font(12), border_width=1,
                                       border_color=k.acc if self.page == "datos" else PAL["edge"], fg_color=PAL["card"], hover_color=PAL["card"],
                                       text_color=PAL["fg"], command=lambda: self.set_page("Datos"))
        # (ya no está en la cabecera: «Datos» se abre desde el panel de Ajustes; el botón existe solo para que `set_page` pueda marcarlo)
        ayuda_btn = ctk.CTkButton(bar, text="?", width=32, height=32, corner_radius=16, font=k.font(14, True), border_width=1, border_color=PAL["edge"],
                                  fg_color=PAL["card"], hover_color=PAL["card2"], text_color=PAL["fg"], command=self.open_help)
        ayuda_btn.pack(side="right", padx=(0, 8))
        self.ayuda_btn, self.ajustes_btn = ayuda_btn, ajustes   # los usa el tour de la demostración para señalarlos
        k.tip(ayuda_btn, "Ayuda: qué es cada pantalla y preguntas frecuentes (F1)")
        self.link_lbl = k.clbl(bar, "", 11, "warn", True)
        self.link_lbl.pack(side="right", padx=(12, 12))
        vol = k.frame(bar)
        vol.pack(side="right")
        self.mute_btn = ctk.CTkButton(vol, text=self.vol_icon(), width=30, height=28, corner_radius=8, fg_color="transparent",
                                      hover_color=PAL["card2"], text_color=PAL["fg"], font=k.font(15), command=self.toggle_mute)
        self.mute_btn.pack(side="left")
        self.add_volume_slider(vol, 70).pack(side="left")
        self.update_btn = ctk.CTkButton(bar, text="", height=28, corner_radius=14, font=k.font(11, True), fg_color=k.acc,
                                        text_color=PAL["bg"], hover_color=k.acc, command=self.confirm_update)
        tabs = {"asesor": "Asesor", "partida": "Partida", "enfrentamiento": "Enfrentamiento", "repertorio": "Repertorio", "historial": "Historial"}
        if parche.ACTIVO:
            tabs["parche"] = "Parche"
        self.tab_names = {**tabs, "datos": "Datos"}   # «Datos» es una página más, pero se abre desde su botón de la cabecera
        # banda del modo en vivo: solo con cola, selección o partida (el prototipo v3); lleva el estado y un botón para ir y volver entre la partida y la consulta
        self.band = ctk.CTkFrame(self.main, fg_color=("#fbead0", "#2e2210"), corner_radius=10, border_width=1, border_color=PAL["warn"])
        self.band_txt = k.clbl(self.band, "", 12, "warn", True)
        self.band_txt.pack(side="left", padx=(12, 8), pady=6)
        self.band_btn = ctk.CTkButton(self.band, text="", width=150, height=26, corner_radius=8, font=k.font(11, True), fg_color="transparent", border_width=1,
                                      border_color=PAL["warn"], text_color=PAL["warn"], hover_color=PAL["card2"], command=self.band_click)
        self.band_btn.pack(side="right", padx=10, pady=5)
        self.band_sig = None
        self.mid = k.frame(self.main)   # la barra lateral a la izquierda y el cuerpo a su lado
        self.mid.pack(fill="both", expand=True)
        self.tab_seg = RailNav(k, self.mid, self.set_page, tabs.get(self.page, ""))
        self.tab_seg.frame.pack(side="left", fill="y", padx=(12, 0), pady=(10, 0))
        self.right = k.frame(self.mid)   # a la derecha del carril: la barra «Ir a» (fija, solo en la selección) y debajo el cuerpo con desplazamiento
        self.right.pack(side="left", fill="both", expand=True)
        self.jump_host = k.frame(self.right)
        self.body = ctk.CTkScrollableFrame(self.right, fg_color="transparent", corner_radius=0, scrollbar_button_color=PAL["edge"],
                                           scrollbar_button_hover_color=PAL["border"])
        self.body.pack(side="top", fill="both", expand=True, padx=(6, 12), pady=(8, 0))
        calm(getattr(self.body, "_scrollbar", None))   # la barra recalculaba toda la ventana en cada cambio de alto del contenido
        self.footer = k.clbl(self.main, "", 10, "dim", anchor="w")
        self.footer.pack(fill="x", padx=24, pady=(2, 12))
        self.update_link()

    def build_views(self):
        k = self.kit
        self.idle_view, self.select_view = k.frame(self.body), k.frame(self.body)
        self.idle_secs = [TourOffer(k, self.idle_view), ProfileCard(k, self.idle_view), WaitCard(k, self.idle_view), SummaryCard(k, self.idle_view)]
        # (la fila de rango y racha ya no se muestra en la selección: ahí no ayuda a decidir)
        self.turn = TurnCard(k, self.select_view)
        self.draft = DraftCard(k, self.select_view)   # el orden de creación es el orden en pantalla
        self._order_kind = None   # secciones nuevas (al cambiar tema o tamaño): hay que volver a colocarlas
        self.jump = JumpBar(k, self.jump_host, self)
        self.game_jump = k.frame(self.jump_host)   # la barra «Ir a» de «Tu partida» durante la partida (la pinta GameView)
        mypick = MyPick(k, self.select_view)
        ideas = BanIdeas(k, self.select_view)
        self.aram_build = AramBuild(k, self.select_view)   # la build de tu campeón va antes que la lista del banquillo
        self.recs = Recs(k, self.select_view)
        self.lobby = Lobby(k, self.select_view)
        self.enemies = Enemies(k, self.select_view)
        self.counter_picks = CounterPicks(k, self.select_view)   # los mejores campeones contra cada rival, aparte de la afinidad
        self.jump.targets = [("Tu build", self.aram_build), ("Tu campeón", mypick), ("Recomendaciones", self.recs), ("Contrarrestos", self.counter_picks), ("Tu equipo", self.lobby), ("Rivales", self.enemies)]
        bans = BansRow(k, self.select_view)
        self.sec = {"turn": self.turn, "draft": self.draft, "mypick": mypick, "ideas": ideas, "aram": self.aram_build, "recs": self.recs,
                    "counter": self.counter_picks, "lobby": self.lobby, "enemies": self.enemies, "bans": bans}
        self.select_secs = [self.turn, self.draft, mypick, ideas, self.aram_build, self.recs, self.counter_picks, self.lobby, self.enemies, bans, self.jump]   # la barra «Ir a» se repinta la última
        self.matchup_view = MatchupView(k, self.body, self)
        self.history_view = HistoryView(k, self.body, self)
        self.pool_view = PoolView(k, self.body, self)
        self.data_view = DataView(k, self.body, self)
        self.game_view = GameView(k, self.body, self)
        self.patch_view = PatchView(k, self.body, self)

    def make_ctx(self):
        # el ancho se da en unidades lógicas (el de diseño): con la escala de Windows o el tamaño de interfaz al 125 %, 150 %…, los
        # píxeles reales son más y todo lo que se mide contra este ancho (umbrales, textos, imágenes, lienzos) se desajustaba
        self.ctx["width"] = max(self.body.winfo_width() / self.kit.scale_px(), 400)
        return self.ctx

    def show_view(self, name):
        if self.view == name:
            return
        for v in (self.idle_view, self.select_view, self.matchup_view.box, self.history_view.box, self.pool_view.box, self.data_view.box, self.game_view.box, self.patch_view.box):
            v.pack_forget()
        {"idle": self.idle_view, "select": self.select_view, "matchup": self.matchup_view.box,
         "history": self.history_view.box, "pool": self.pool_view.box, "data": self.data_view.box, "game": self.game_view.box, "patch": self.patch_view.box}[name].pack(fill="x")
        self.view = name
        try:   # la barra «Ir a» solo existe en la selección
            if name in ("select", "game"):
                self.jump.box.pack_forget()
                self.game_jump.pack_forget()
                (self.jump.box if name == "select" else self.game_jump).pack(fill="x")
                self.jump_host.pack(side="top", fill="x", padx=(6, 12), pady=(8, 0), before=self.body._parent_frame)   # el marco que de verdad se coloca (CTkScrollableFrame lo oculta tras .pack)
            else:
                self.jump_host.pack_forget()
        except Exception:
            core.log_exc("Barra Ir a")
        try:
            self.body._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def effective_view(self):
        return {"enfrentamiento": "matchup", "historial": "history", "repertorio": "pool", "datos": "data", "partida": "game", "parche": "patch"}.get(self.page, self.advisor)

    def apply_page(self):
        prev = self.view
        self.show_view(self.effective_view())
        self.refresh_current()
        if prev is not None and prev != self.view and self.kit.anim_on():
            self.wipe()

    def wipe(self, n=8):
        """Transición entre pantallas: una cortina del color del fondo se retira de arriba abajo y descubre el contenido."""
        try:
            cur = tk.Frame(self.body, bg=self.kit.bg(self.body))
            tk.Place.place_configure(cur, relx=0, rely=1.0, relwidth=1.0, relheight=1.0, anchor="sw")
            cur.lift()

            def step(i=0):
                if not cur.winfo_exists():
                    return
                h = 1 - (i + 1) / n
                if h <= 0.02:
                    cur.destroy()
                    return
                tk.Place.place_configure(cur, relheight=h)
                self.root.after(16, lambda: step(i + 1))
            self.root.after(10, step)
        except Exception:
            pass

    def set_page(self, name):
        self.page = {v: k for k, v in self.tab_names.items()}[name]
        want = name if self.page != "datos" else ""   # en «Datos» ninguna pestaña queda marcada
        if self.tab_seg.get() != want:
            self.tab_seg.set(want)
        try:
            self.datos_btn.configure(border_color=self.kit.acc if self.page == "datos" else PAL["edge"])
        except Exception:
            pass
        self.conf["tab"] = self.page
        save_conf(self.conf)
        self.apply_page()

    def refresh_current(self, force=False):
        ctx = self.make_ctx()
        if self.view == "matchup":
            self.matchup_view.refresh(ctx, force)
        elif self.view == "history":
            self.history_view.refresh(ctx, force)
        elif self.view == "pool":
            self.pool_view.refresh(ctx, force)
        elif self.view == "data":
            self.data_view.refresh(ctx, force)
        elif self.view == "game":
            self.game_view.refresh(ctx, force)
        elif self.view == "patch":
            self.patch_view.refresh(ctx, force)
            self.patch_seen()
        elif self.view == "select" and ctx["r"]:
            self.refresh_select(ctx, force)
        elif self.view == "idle":
            for s in self.idle_secs:
                s.refresh(ctx, force)
        self.update_footer()

    ORDERS = {   # orden de los bloques de la selección según lo que hay que hacer ahora
        "ban": ["turn", "draft", "ideas", "aram", "recs", "counter", "mypick", "lobby", "enemies", "bans"],
        "pick": ["turn", "draft", "aram", "recs", "counter", "mypick", "ideas", "lobby", "enemies", "bans"],
        "locked": ["turn", "draft", "mypick", "aram", "recs", "counter", "lobby", "enemies", "bans", "ideas"],
    }

    def order_select(self, ctx):
        """En la fase de bans primero las ideas de baneo; eligiendo (sin bloquear), las recomendaciones; con el campeón bloqueado, su build. Solo recoloca al cambiar de fase."""
        try:
            r, ses = ctx["r"], ctx["session"]
            ban = r.get("turn") == "ban" or (ses or {}).get("timer", {}).get("phase") == "PLANNING"
            kind = "ban" if ban else ("locked" if r.get("mine_locked") else "pick")
            if kind == getattr(self, "_order_kind", None):
                return False
            self._order_kind = kind
            names = self.ORDERS[kind]
            for n in names:
                self.sec[n].box.pack_forget()
            for n in names:
                self.sec[n].box.pack(fill="x")
            return True
        except Exception:
            core.log_exc("Orden de la selección")
        return False

    def refresh_select(self, ctx, force=False):
        """Repinta la selección sección a sección, dejando respirar a la ventana entre una y otra: con LoL en marcha el ordenador va
        justo y hacerlo todo de golpe bloqueaba la ventana ~1,5 s. Si llega un cambio nuevo a mitad, se abandona el anterior."""
        self._sel_tok = getattr(self, "_sel_tok", 0) + 1
        tok = self._sel_tok
        cv = self.body._parent_canvas
        try:  # el desplazamiento se conserva en píxeles: al añadirse tarjetas arriba, lo que mirabas no se va de sitio
            total = max(1, (cv.bbox("all") or (0, 0, 0, 1))[3])
            off = cv.yview()[0] * total
        except Exception:
            off = 0
        if self.order_select(ctx):
            off = 0   # los bloques han cambiado de sitio: se mira desde arriba, no a un sitio sin relación
        secs = list(self.select_secs)
        anim = self.kit.anim

        def step(i=0):
            if tok != self._sel_tok or not self.running:
                return
            self.kit.anim = anim
            if i < len(secs):
                try:
                    secs[i].refresh(ctx, force)
                except Exception:
                    core.log_exc(f"Sección {type(secs[i]).__name__}")
                self.kit.anim = False
                self.root.after(1, lambda: step(i + 1))
                return
            self.kit.anim = False
            try:
                self.root.update_idletasks()
                new_total = max(1, (cv.bbox("all") or (0, 0, 0, 1))[3])
                cv.yview_moveto(min(1.0, off / new_total))
            except Exception:
                pass
        step()

    def paint_game_jump(self, anchors, width):
        """Atajos «Ir a» de «Tu partida» (solo durante la partida): `anchors` es [(nombre, marca)] en el orden en que están en pantalla."""
        box = self.game_jump
        self.kit.clear(box)
        if len(anchors) < 2:
            box.configure(height=1)   # un contenedor vacío conserva su tamaño: se colapsa a mano
            return
        per = 3 if width < 660 else len(anchors)
        row = None
        for i, (n, mark) in enumerate(anchors):
            if i % per == 0:
                row = self.kit.frame(box)
                row.pack(fill="x", pady=(0, 6))
                self.kit.lbl(row, "IR A" if i == 0 else "", 9, "dim", True, width=34, anchor="w").pack(side="left", padx=(2, 8))
            ctk.CTkButton(row, text=n, width=0, height=26, corner_radius=13, font=self.kit.font(11), fg_color=PAL["card2"], text_color=PAL["fg"],
                          hover_color=PAL["border"], command=lambda m=mark: self.go_to(m)).pack(side="left", padx=(0, 6))

    def go_to(self, widget):
        """Desplaza el cuerpo hasta dejar `widget` en lo alto de la ventana."""
        try:
            cv = self.body._parent_canvas
            self.root.update_idletasks()
            total = max(1, (cv.bbox("all") or (0, 0, 0, 1))[3])
            y = widget.winfo_rooty() - cv.winfo_rooty() + cv.canvasy(0)
            cv.yview_moveto(max(0.0, min(1.0, (y - 8) / total)))
        except Exception:
            core.log_exc("Ir a un bloque de la partida")

    def key_go(self, d):
        if self.view == "select" and self.conf["rec_view"] == "carrusel" and not self.conf["compact"]:
            self.recs.go(d)

    # ---------- cambios de tamaño: solo se rehace lo que depende del ancho ----------
    def layout_main(self, W=None):
        """El contenido se centra y no pasa de un ancho máximo: en pantallas grandes la información queda junta, no en los extremos."""
        try:
            W = W or self.root.winfo_width()
            dw = self.dock_dw if self.dock_open else 0
            avail = max(300, W - dw)
            mw = int(self.main._apply_widget_scaling(MAX_W))
            w = min(avail, mw)
            tk.Place.place_configure(self.main, x=(avail - w) // 2, y=0, relwidth=0, width=w, relheight=1.0)
            mode = self.conf.get("rail_mode", "auto")   # «auto»: con la ventana ancha la barra lateral enseña también los nombres
            self.tab_seg.set_expanded(mode == "nombres" or (mode == "auto" and w / self.kit.scale_px() >= 900))
        except Exception:
            pass

    def on_resize(self, e):
        if e.widget is self.root and not self.docking:
            self.layout_main(e.width)
            if getattr(self, "_gs", None):
                self.root.after_cancel(self._gs)
            self._gs = self.root.after(1500, self.save_geometry)  # al dejar de moverla o cambiarle el tamaño
        if e.widget is self.root and not self.docking and abs(e.width - self.last_w) > 24:
            self.last_w = e.width
            if self._rs:
                self.root.after_cancel(self._rs)
            self._rs = self.root.after(180, self.after_resize)

    def after_resize(self):
        self._rs = None
        self.layout_main()
        self.update_link()
        self.root.update_idletasks()  # el ancho del cuerpo debe ser el ya colocado, no el anterior
        if self.view == "select" and self.ctx["r"]:
            self.kit.anim = False
            self.recs.resized(self.make_ctx()["width"])
            try:
                self.jump.refresh(self.ctx)   # al estrechar o ensanchar la ventana la barra «Ir a» pasa a una o dos filas
            except Exception:
                core.log_exc("Barra Ir a")
        elif self.view in ("matchup", "history", "pool", "data", "idle", "game"):
            self.refresh_current()

    # ---------- enlace, pie y volumen ----------
    def update_link(self):
        ok = self.ctx["linked"]
        try:   # ventana estrecha o interfaz al 115–130 %: el texto largo no cabía en la cabecera y salía cortado
            lw = self.root.winfo_width() / self.kit.scale_px()
        except Exception:
            lw = 999
        small = lw < 540
        txt = ("●  Conectado" if small else "●  Conectado a LoL") if ok else ("●  Sin cliente" if small else "●  Esperando al cliente")
        self.link_lbl.configure(text="●" if lw < 460 else txt,   # muy estrecho: solo el punto de color (verde conectado, ámbar sin cliente)
                                text_color=PAL["good"] if ok else PAL["warn"])

    def update_footer(self):
        meta = read_json(core.opgg_path(self.conf), {})
        age = f"op.gg · actualizado hace {(time.time() - meta['ts']) / 3600:.0f} h" if meta.get("ts") else ""
        self.footer.configure(text="     ".join(x for x in (self.status_text, age) if x))

    def vol_icon(self):
        v = self.conf["volume"]
        return "🔇" if v <= 0 else "🔈" if v < .35 else "🔉" if v < .7 else "🔊"

    def _phase_sound_row(self, sc, k, ph, ph_name, ph_desc):
        """Una fila de Ajustes: el sonido de una fase, con su selector, su archivo propio y el botón de probar."""
        conf = self.conf
        choices = list(core.SOUNDS) + [core.NONE, core.FILE]

        def current():
            return core.phase_cfg(conf, ph)

        def store(snd, file=None):
            cfg = dict((conf.get("phase_sounds") or {}).get(ph) or {})
            cfg["sound"] = snd
            if file is not None:
                cfg["file"] = file
            conf["phase_sounds"] = {**(conf.get("phase_sounds") or {}), ph: cfg}
            save_conf(conf)

        info = k.clbl(sc, "", 10, "dim", anchor="w")

        def show_file():
            snd, f = current()
            info.configure(text=("Archivo: " + os.path.basename(f)) if snd == core.FILE and f else "")

        def chosen(v):
            if v == core.FILE:
                from tkinter import filedialog
                path = filedialog.askopenfilename(title="Elige un sonido (.wav)", filetypes=[("Sonido WAV", "*.wav")])
                if not path:
                    menu.set(current()[0])  # cancelado: se queda como estaba
                    return
                store(v, path)
            else:
                store(v)
            show_file()
            test()

        def test():
            snd, f = current()
            if snd == core.FILE:
                if not core.play_file(f, conf["volume"]):
                    messagebox.showinfo(APP_NAME, "No se pudo reproducir ese archivo. Usa un .wav de 16 bits (se usará el sonido general mientras tanto).")
            else:
                core.play_alert(snd, conf["volume"])

        k.clbl(sc, ph_name, 11, "fg", True).pack(anchor="w", padx=12, pady=(12, 0))
        k.clbl(sc, ph_desc, 10, "dim", anchor="w").pack(anchor="w", padx=12)
        row = k.frame(sc)
        row.pack(anchor="w", padx=12, pady=2)
        menu = k.menu(row, choices, current()[0], chosen, 220)
        menu.pack(side="left")
        b = ctk.CTkButton(row, text="Probar", width=70, font=k.font(11), fg_color=PAL["card2"], text_color=PAL["fg"], hover_color=PAL["card2"],
                          border_width=1, border_color=PAL["edge"], command=test)
        b.pack(side="left", padx=(8, 0))
        k.smooth_btn(b, PAL["card2"], PAL["border"])
        info.pack(anchor="w", padx=12)
        show_file()
    def add_volume_slider(self, parent, width):
        a = self.kit.acc
        s = ctk.CTkSlider(parent, from_=0, to=1, number_of_steps=20, width=width, height=14, progress_color=a, button_color=a,
                          button_hover_color=a, command=self.on_volume)
        s.set(self.conf["volume"])
        self.vol_sliders.append(s)
        return s

    def on_volume(self, v):
        v = round(float(v), 2)
        self.conf["volume"] = v
        for s in self.vol_sliders:
            try:
                if abs(s.get() - v) > 0.001:
                    s.set(v)
            except Exception:
                pass
        self.mute_btn.configure(text=self.vol_icon())
        if self._vt:
            self.root.after_cancel(self._vt)
        self._vt = self.root.after(300, self.volume_settled)  # al soltar: guarda y suena una muestra

    def volume_settled(self):
        save_conf(self.conf)
        core.play_alert(self.conf["sound"], self.conf["volume"])

    def toggle_mute(self):
        if self.conf["volume"] > 0:
            self.prev_vol = self.conf["volume"]
            self.on_volume(0)
        else:
            self.on_volume(getattr(self, "prev_vol", 0.7))

    # ---------- ajustes acoplados: la ventana se ensancha y ves el resultado en vivo ----------
    def set(self, key, value, recalc=False, redraw=True):
        self.conf[key] = value
        save_conf(self.conf)
        self.apply_window()
        if key in ("accent", "theme", "scale", "color_theme", "style"):
            if key in ("color_theme", "style"):
                import temas
                if key == "color_theme":
                    self.conf["accent"] = temas.accent_for(value)   # cada tema trae su acento; luego se puede cambiar a mano
                    save_conf(self.conf)
                temas.apply(self.conf)
            if key in ("color_theme", "style"):
                self.kit.fonts.clear()   # la tipografía puede cambiar con el tema (los looks traen la suya)
            if key == "scale":
                self.kit.fonts = {k_: v for k_, v in self.kit.fonts.items() if k_[0] != "tk"}
            self.kit.epoch += 1  # las secciones se reconstruyen con los colores y tamaños nuevos
            self.rebuild_ui(value if key == "theme" else None)
            return
        if recalc:
            self.cmds.put("recalc")
        if redraw:
            self.kit.anim = False
            self.refresh_current()

    def vol_slider_colors(self):
        a = self.kit.acc
        for s in self.vol_sliders:
            try:
                s.configure(progress_color=a, button_color=a, button_hover_color=a)
            except Exception:
                pass

    def toggle_dock(self):
        self.close_dock() if self.dock_open else self.open_dock()

    def dock_px(self):
        try:
            return int(self.dock._apply_widget_scaling(DOCK_W))
        except Exception:
            return int(DOCK_W * self.conf["scale"] * self.win_scale())

    def prebuild_dock(self):
        if self.dock is None and self.running:
            self.build_dock()

    def open_dock(self):
        if self.docking or self.dock_open:
            return
        if self.dock is None:
            self.build_dock()
        self.root.update_idletasks()
        W, H, X, Y = self.root.winfo_width(), self.root.winfo_height(), self.root.winfo_x(), self.root.winfo_y()
        vx, _vy, vw, _vh = self.virtual_screen()
        screen_w = vx + vw - 16   # el borde derecho de TODOS los monitores (el principal solo medía el primero)
        dw = self.dock_px()
        if self.root.state() == "zoomed" or W + dw > screen_w:
            self.slide_inside(W, dw, True)  # maximizada o sin sitio: la ventana no cambia, el contenido se estrecha
            return
        X1 = min(X, max(vx, screen_w - (W + dw)))
        self.dock_inside = False
        tk.Place.place_configure(self.main, x=0, y=0, relwidth=0, width=W, relheight=1.0)  # el contenido no se recoloca
        tk.Place.place_configure(self.dock, x=W, y=0, width=dw, relheight=1.0)
        self.dock.lift()
        self.dock_open, self.docking, self.dock_dw = True, True, dw

        def done():
            tk.Place.place_configure(self.dock, relx=1.0, x=-dw, y=0, width=dw, relheight=1.0)
            self.layout_main(W + dw)
        self.animate_window(W, W + dw, H, X, X1, Y, 0, done)

    def slide_inside(self, W, dw, opening):
        """Panel dentro de la ventana actual (por ejemplo maximizada): entra deslizando y el contenido se estrecha una sola vez."""
        n = 9 if self.kit.anim_on() else 1
        if opening:
            dw = min(dw, max(300, W // 2))
            self.dock_dw, self.dock_inside, self.dock_open = dw, True, True
            tk.Place.place_configure(self.dock, relx=1.0, x=0, y=0, width=dw, relheight=1.0)
            self.dock.lift()
        else:
            dw = self.dock_dw
            self.dock_open = False
            self.layout_main()  # el contenido recupera su ancho
        self.docking = True

        def step(i=0):
            t = 1 - (1 - (i + 1) / n) ** 3
            tk.Place.place_configure(self.dock, relx=1.0, x=-int(dw * (t if opening else 1 - t)), y=0, width=dw, relheight=1.0)
            if i + 1 < n:
                self.root.after(14, lambda: step(i + 1))
                return
            if opening:
                self.layout_main()
            else:
                tk.Place.place_forget(self.dock)
                self.dock_inside = False
            self.docking = False
            self.root.after(60, self.after_resize)
        step()

    def close_dock(self):
        if self.docking or not self.dock_open:
            return
        if self.dock_inside:
            self.slide_inside(self.root.winfo_width(), self.dock_dw, False)
            return
        W, H, X, Y = self.root.winfo_width(), self.root.winfo_height(), self.root.winfo_x(), self.root.winfo_y()
        dw = self.dock_dw
        tk.Place.place_configure(self.main, x=0, y=0, relwidth=0, width=W - dw, relheight=1.0)
        tk.Place.place_configure(self.dock, relx=0, x=W - dw, y=0, width=dw, relheight=1.0)
        self.dock_open, self.docking = False, True

        def done():
            tk.Place.place_forget(self.dock)
            self.layout_main(W - dw)
        self.animate_window(W, W - dw, H, X, X, Y, 0, done)

    def animate_window(self, a, b, h, x0, x1, y, step, done, n=9):
        n = n if self.kit.anim_on() else 1
        t = 1 - (1 - (step + 1) / n) ** 3
        tk.Wm.geometry(self.root, f"{int(a + (b - a) * t)}x{h}+{int(x0 + (x1 - x0) * t)}+{y}")
        if step + 1 < n:
            self.root.after(14, lambda: self.animate_window(a, b, h, x0, x1, y, step + 1, done, n))
        else:
            done()
            self.docking = False
            self.last_w = self.root.winfo_width()

    def rebuild_ui(self, theme=None):
        """Tema, acento o tamaño nuevos: se rehace toda la interfaz (los widgets ligeros fijan su color al crearse)."""
        was_open = self.dock_open
        yview = 0.0
        try:
            yview = self.body._parent_canvas.yview()[0]
        except Exception:
            pass
        for w in (self.main, self.dock):
            if w is not None:
                w.destroy()
        self.dock, self.dock_open, self.docking, self.dock_inside, self.vol_sliders = None, False, False, False, []
        if theme:
            ctk.set_appearance_mode(theme)  # con la interfaz vieja ya destruida: no hay que recolorear miles de widgets
        self.kit.photos.clear()  # por si cambió la escala de la ventana
        self.root.configure(fg_color=PAL["bg"])
        self.view = None
        self.kit.anim = False
        self.build_shell()
        self.layout_main()
        self.build_views()
        self.show_view(self.effective_view())
        self.refresh_current()
        if was_open:
            self.build_dock()
        else:
            self.root.after(1500, self.prebuild_dock)  # los ajustes se preparan después, sin bloquear el cambio
        if was_open:
            self.root.update_idletasks()
            dw = self.dock_px()
            self.dock_dw, self.dock_open = dw, True
            tk.Place.place_configure(self.dock, relx=1.0, x=-dw, y=0, width=dw, relheight=1.0)
            self.dock.lift()
            self.layout_main()
            self.dock_inside = self.root.state() == "zoomed" or self.root.winfo_width() < dw * 2
        self.root.after(80, lambda: self.body._parent_canvas.yview_moveto(yview))
        self.root.after(200, self.after_resize)  # el ancho real solo se conoce una vez colocada la interfaz

    def refresh_dock(self):
        """Reconstruye el panel con el acento nuevo (sus controles se colorean al crearse)."""
        if self.dock is None:
            return
        old, was_open, dw = self.dock, self.dock_open, self.dock_dw
        self.build_dock()
        if was_open:
            tk.Place.place_configure(self.dock, relx=1.0, x=-dw, y=0, width=dw, relheight=1.0)
            self.dock.lift()
        old.destroy()
        self.vol_sliders = [s for s in self.vol_sliders if s.winfo_exists()]

    def build_dock(self):
        k, conf = self.kit, self.conf
        d = self.dock = ctk.CTkFrame(self.root, width=DOCK_W, corner_radius=0, fg_color=PAL["card"], border_width=1,
                                     border_color=PAL["border"])
        d.pack_propagate(False)
        head = k.frame(d)
        head.pack(fill="x", padx=24, pady=(16, 0))
        k.clbl(head, "Ajustes y datos", 20, "fg", True, True).pack(side="left")
        close = ctk.CTkButton(head, text="Cerrar", width=70, height=30, corner_radius=9, font=k.font(12), fg_color=PAL["card2"],
                              hover_color=PAL["card2"], text_color=PAL["fg"], command=self.close_dock)
        close.pack(side="right")
        k.smooth_btn(close, PAL["card2"], PAL["border"])
        k.clbl(d, "Los cambios se aplican al instante y se guardan solos.", 10, "dim", anchor="w", wraplength=self.note_w(),
               justify="left").pack(anchor="w", padx=24, pady=(2, 0))
        datos = ctk.CTkButton(d, text="Datos y fuentes de información  ›", height=34, corner_radius=10, font=k.font(12, True),
                              fg_color=PAL["card2"], hover_color=PAL["border"], text_color=PAL["fg"], anchor="w",
                              command=lambda: (self.close_dock(), self.set_page("Datos")))
        datos.pack(fill="x", padx=24, pady=(10, 0))
        sc = ctk.CTkScrollableFrame(d, fg_color="transparent")
        self.dock_scroll = sc   # lo usan las capturas de prueba para paginar el panel
        calm(getattr(sc, "_scrollbar", None))
        sc.pack(fill="both", expand=True, padx=8, pady=(4, 12))

        def section(text):
            ctk.CTkFrame(sc, height=1, corner_radius=0, fg_color=PAL["border"]).pack(fill="x", padx=12, pady=(16, 0))
            k.clbl(sc, text.upper(), 10, k.acc, True).pack(anchor="w", padx=12, pady=(8, 4))

        def note(text):
            k.clbl(sc, text, 10, "dim", wraplength=self.note_w(), justify="left", anchor="w").pack(anchor="w", padx=16, pady=(0, 4))

        def label(text):
            k.clbl(sc, text, 11, "dim").pack(anchor="w", padx=12, pady=(8, 0))

        def seg(values, current, command):
            b = k.seg(sc, values, current, command)
            b.pack(fill="x", padx=12, pady=4)
            return b

        def switch(text, key, command=None):
            var = ctk.BooleanVar(value=bool(conf[key]))
            ctk.CTkSwitch(sc, text=text, variable=var, font=k.font(12), progress_color=k.acc,
                          command=command or (lambda: self.set(key, var.get()))).pack(anchor="w", padx=12, pady=8)

        def button(text, cmd):
            b = ctk.CTkButton(sc, text=text, font=k.font(12), fg_color=PAL["card2"], text_color=PAL["fg"], hover_color=PAL["card2"],
                              command=cmd)
            b.pack(fill="x", padx=12, pady=4)
            k.smooth_btn(b, PAL["card2"], PAL["border"])

        section("Apariencia")
        seg(list(THEMES), {v: k_ for k_, v in THEMES.items()}.get(conf["theme"], "Oscuro"),
            lambda v: self.set("theme", THEMES[v]))
        import temas
        label("Tema de color")
        k.menu(sc, temas.NOMBRES, conf.get("color_theme", temas.DEFAULT_THEME), lambda v: self.set("color_theme", v), width=220).pack(anchor="w", padx=12, pady=2)
        cur_theme = conf.get("color_theme", temas.DEFAULT_THEME)
        if temas.is_look(cur_theme):
            note(f"«{cur_theme}»: " + temas.FORMA_LOOKS[cur_theme]["nota"] + " Es un look completo: trae su propia tipografía y estilo de tarjetas.")
        else:
            note("Paletas revisadas por contraste y daltonismo. Los looks (Terminal, Papel, Blueprint, Hextech, Arcade, Neón Tokio y Océano) cambian además la tipografía y la forma.")
            label("Estilo de las tarjetas")
            seg(temas.ESTILOS_NOMBRES, conf.get("style", temas.DEFAULT_STYLE), lambda v: self.set("style", v))
            note(temas.ESTILOS[conf.get("style", temas.DEFAULT_STYLE)]["nota"] + " Se combina con cualquier tema de color.")
        label("Color de acento")
        sw = k.frame(sc)
        sw.pack(anchor="w", padx=12, pady=(2, 0))
        for n, colr in ACCENTS.items():
            ctk.CTkButton(sw, text="", width=30, height=30, corner_radius=15, fg_color=colr, hover_color=colr, border_width=2,
                          border_color=PAL["border"], command=lambda n=n: self.set("accent", n)).pack(side="left", padx=4)
        label("Tamaño de la interfaz")
        cur = f"{round(conf['scale'] * 100)}%"
        seg(["90%", "100%", "115%", "130%"], cur if cur in ("90%", "100%", "115%", "130%") else "100%",
            lambda v: (ctk.set_widget_scaling(int(v[:-1]) / 100), self.set("scale", int(v[:-1]) / 100)))
        label("Barra lateral")
        rails = {"Automática": "auto", "Con nombres": "nombres", "Solo iconos": "iconos"}
        seg(list(rails), {v: k_ for k_, v in rails.items()}.get(conf.get("rail_mode", "auto"), "Automática"),
            lambda v: (self.set("rail_mode", rails[v], redraw=False), self.layout_main()))
        note("«Automática»: muestra los nombres si la ventana es ancha y solo iconos si es estrecha.")
        switch("Animaciones y transiciones", "animations")
        note("Desactívalas si prefieres cambios instantáneos o tu equipo va justo.")
        label("Ventana siempre por encima de las demás")
        tops = {"Nunca": "nunca", "En la selección": "seleccion", "Siempre": "siempre"}
        seg(list(tops), {v: k_ for k_, v in tops.items()}.get(conf.get("topmost_mode", "seleccion"), "En la selección"),
            lambda v: self.set("topmost_mode", tops[v], redraw=False))
        note("«En la selección»: solo mientras eliges campeón; el resto del tiempo se comporta como cualquier ventana (Alt+Tab).")
        switch("Modo compacto (solo turno y lo recomendado)", "compact")
        switch("Datos en vivo durante la partida", "live_enabled")
        note("En «Partida», marcador, objetos y estado de los 10 jugadores. Lee la API local del propio juego (la de la tabla de puntuación); no toca la partida.")
        switch("Aviso al poder comprar el siguiente objeto", "buy_alert")
        note("Un sonido suave, una vez por objeto, cuando tu oro ya llega para el siguiente de tu build. Necesita los avisos sonoros y los datos en vivo.")

        section("Al abrir")
        starts = {"Última usada": "ultima", "Inicio": "asesor", "Enfrentamiento": "enfrentamiento", "Campeones": "repertorio", "Historial": "historial", "Datos": "datos"}   # los nombres de la barra lateral
        if parche.ACTIVO:
            starts["Parche"] = "parche"
        label("Pestaña inicial")
        k.menu(sc, list(starts), {v: k_ for k_, v in starts.items()}.get(conf["start_tab"], "Última usada"),
               lambda v: self.set("start_tab", starts[v], redraw=False), 300).pack(anchor="w", padx=12, pady=2)

        section("Qué mostrar")
        switch("Tu equipo y el equipo rival", "show_teams")
        switch("Campeones baneados", "show_bans")

        section("Recomendaciones")
        label("Forma de verlas")
        seg(list(REC_VIEWS.values()), REC_VIEWS.get(conf["rec_view"], "Carrusel"),
            lambda v: self.set("rec_view", next((k for k, t in REC_VIEWS.items() if t == v), v.lower())))
        label("Cuántas mostrar")
        seg(["3", "4", "5", "6", "8"], str(conf["top_n"]), lambda v: self.set("top_n", int(v)))
        names = {v[0]: key for key, v in PRESET_INFO.items()}
        label("Estilo")
        desc = k.clbl(sc, PRESET_INFO[conf["preset"]][1], 11, "dim", wraplength=self.note_w(), justify="left")

        def pick(v):
            key = names[v]
            conf["weights"] = ({**core.PRESETS["equilibrado"], **conf.get("custom_weights", {})} if key == "personalizado"
                               else dict(core.PRESETS[key]))
            desc.configure(text=PRESET_INFO[key][1])
            self.set("preset", key, True, redraw=False)
            self.data_view.sig = None  # la pestaña «Datos» recoge los pesos nuevos la próxima vez
        seg(list(names), PRESET_INFO[conf["preset"]][0], pick)
        desc.pack(anchor="w", padx=16, pady=(2, 4))
        note("Los pesos, los umbrales y de dónde sale cada dato están en «Datos» (Ajustes › «Datos y fuentes de información»).")
        button("Abrir «Datos»", lambda: self.set_page("Datos"))

        section("Sonido")
        switch("Avisos sonoros", "beep")
        label("Volumen")
        self.add_volume_slider(sc, 300).pack(anchor="w", padx=12, pady=2)
        label("Sonido general")
        k.menu(sc, list(core.SOUNDS), conf["sound"],
               lambda v: (self.set("sound", v, redraw=False), core.play_alert(v, conf["volume"])), 300).pack(anchor="w", padx=12, pady=2)
        note("Lo usan las fases que no tengan sonido propio (baneo y elegir, mientras no los cambies).")
        section("Sonido de cada fase")
        note("Elige un sonido para cada momento, «Sin sonido» para silenciarlo, o «Mi archivo…» para usar un .wav tuyo.")
        for ph, ph_name, ph_desc in core.PHASES:
            self._phase_sound_row(sc, k, ph, ph_name, ph_desc)
        section("Datos")
        note("Las fuentes se activan o desactivan en «Datos» (Ajustes › «Datos y fuentes de información»).")
        button("Actualizar estadísticas de op.gg", lambda: (self.cmds.put("opgg"), self.status("Actualizando op.gg…")))
        button("Actualizar el meta del parche", lambda: (self.cmds.put("meta"), self.status("Actualizando el meta…")))
        button("Abrir la carpeta de datos", lambda: os.startfile(DATA_DIR) if os.path.isdir(DATA_DIR) else None)
        button("Borrar la caché de imágenes y enfrentamientos", self.clear_cache)

        section("Actualizaciones")
        switch("Buscar actualizaciones al abrir y cada pocas horas", "auto_update")
        switch("Instalar las actualizaciones solas", "auto_install")
        note("Con esto activo no hay que hacer nada: al salir una versión nueva LOL-E la descarga, comprueba su huella y se reinicia solo. "
             "Nunca lo hace durante la cola, la selección ni la partida.")
        label("Dirección del archivo de versión")
        entry = ctk.CTkEntry(sc, font=k.font(11), placeholder_text="https://…/latest.json", fg_color=PAL["well"], border_color=PAL["edge"],
                             text_color=PAL["fg"])
        entry.insert(0, conf["update_url"])
        entry.pack(fill="x", padx=12, pady=2)
        entry.bind("<FocusOut>", lambda e: self.set("update_url", entry.get().strip(), redraw=False))
        entry.bind("<Return>", lambda e: self.set("update_url", entry.get().strip(), redraw=False))
        button("Buscar actualizaciones ahora", lambda: (self.set("update_url", entry.get().strip(), redraw=False), self.check_updates(True)))

        if stats.enabled():
            section("Privacidad")
            var_s = ctk.BooleanVar(value=conf.get("stats_optin") is True)
            ctk.CTkSwitch(sc, text="Contar mi instalación (anónimo)", variable=var_s, font=k.font(12), progress_color=k.acc,
                          command=lambda: self.stats_set(var_s.get())).pack(anchor="w", padx=12, pady=8)
            note("Voluntario y apagado de fábrica. Si lo activas, LOL-E envía una vez al día un número aleatorio y su versión, para que quien la mantiene sepa cuánta gente la usa "
                 "y desde qué zona aproximada. No se envían tu nombre, tu cuenta de LoL, tus partidas ni tus ajustes, y la dirección IP no se guarda. Al apagarlo se borra el registro.")
            button("Ver exactamente qué se envía", lambda: messagebox.showinfo(APP_NAME, "Esto es todo lo que se envía (una vez al día):\n\n"
                                                                                  + stats.describe({"stats_id": conf.get("stats_id") or "(un número aleatorio)"}, APP_VERSION)
                                                                                  + "\n\nEl servidor añade el país y la región de la conexión y descarta la dirección IP."))
            if (conf.get("admin_token") or "").strip():
                section("Administrador")
                adm = k.clbl(sc, "Leyendo el resumen…", 11, "dim", wraplength=self.note_w(), justify="left", anchor="w")
                adm.pack(anchor="w", padx=16, pady=(0, 4))

                def got(res):
                    try:
                        if adm.winfo_exists():
                            adm.configure(text=(f"Instalaciones: {res['total']} · activas hoy {res['activas']['1']}, en 7 días {res['activas']['7']}, en 30 días {res['activas']['30']}"
                                                if res else "No se pudo leer el panel (¿sin conexión o clave incorrecta?)."))
                    except Exception:
                        pass
                def fetch():
                    res = stats.admin_summary(conf)
                    self.q.put(("call", lambda: got(res)))   # la ventana se toca solo desde su hilo
                threading.Thread(target=fetch, daemon=True).start()
                button("Abrir el panel de uso (mapa)", lambda: __import__("webbrowser").open(stats.admin_url(conf)))

        section("Mantenimiento")
        button("Ver novedades", self.show_notes)
        note("Qué ha cambiado en cada versión.")
        button("Copiar informe de diagnóstico", self.copy_diagnostics)
        note("Para pedir ayuda: pulsa el botón, pega el texto en tu mensaje y cuenta en una frase qué esperabas ver y qué viste. Incluye versión, sistema, estado de los datos y últimos errores (sin tu nombre ni tus partidas).")
        button("Abrir el registro de errores", lambda: self.open_log())
        button("Restablecer todos los ajustes", self.reset_settings)
        note("No borra tu historial ni tus datos; LOL-E se cierra para aplicarlo.")

        section("Acerca de")
        k.clbl(sc, f"{APP_NAME} {APP_VERSION}\nNo está respaldado por Riot Games ni refleja las opiniones de Riot Games "
                   "ni de nadie que participe oficialmente en League of Legends. Solo lee datos "
                   "de tu cliente y de la API local de la partida; nunca interviene en el juego.", 10, "dim", wraplength=self.note_w(), justify="left").pack(
            anchor="w", padx=16, pady=(0, 12))

    _opp_choice = 0  # rival de línea elegido a mano (0 = el que se deduce solo)

    @property
    def opp_choice(self):
        return self._opp_choice

    @opp_choice.setter
    def opp_choice(self, v):
        """También se lo cuenta al motor (conf["_opp"], que no se guarda): las puntuaciones de la selección se calculan contra él."""
        self._opp_choice = v or 0
        self.conf["_opp"] = self._opp_choice


    def apply_opp(self, r):
        """Aplica a la selección actual el rival de línea elegido a mano; si ya no está entre los rivales, se descarta."""
        r.setdefault("lane_opp_auto", r.get("lane_opp") or 0)
        if self.opp_choice and r["mode"]["kind"] == "sr" and self.opp_choice in (r.get("enemies") or []):
            r["lane_opp"] = self.opp_choice
        else:
            if self.opp_choice and r["mode"]["kind"] == "sr" and r.get("enemies") is not None and self.opp_choice not in r["enemies"]:
                self.opp_choice = 0
            r["lane_opp"] = r["lane_opp_auto"]

    def set_opp(self, cid):
        """El jugador elige (o suelta, con 0) a mano su rival de línea: build, runas y guía se rehacen contra él, en la selección y en la partida."""
        self.opp_choice = cid or 0
        r, plan = self.ctx.get("r"), self.ctx.get("plan")
        if self.advisor == "select" and r:
            self.apply_opp(r)
            self.update_plan(r)
            self.cmds.put("recalc")   # el motor vuelve a puntuar contra este rival; lo nuevo llega en ~1 s y repinta la selección
        elif plan:
            plan["opp"] = self.opp_choice or plan.get("opp_auto") or 0
            try:
                core.write_json(os.path.join(CACHE, "last_plan.json"), plan)
            except Exception:
                pass
        self.kit.anim = False
        if self.view == "game":
            self.game_view.sig = None
            self.game_view.refresh(self.make_ctx(), True)
        else:
            self.apply_page()
    def infer_lane_opp(self):
        """En las colas de grupos de 5 los rivales no traen línea: con sus perfiles se deduce cuál es tu rival directo (si aún no se sabía)."""
        r = self.ctx.get("r")
        try:
            import draft5
            if not r or not draft5.is_draft(r) or r.get("lane_opp") or not r.get("role"):
                return
            roles = draft5.infer_roles(r["enemy_cells"], self.ctx["players"], self.champs)
            opp = next((e["champ"] for e in r["enemy_cells"] if roles.get(e["puuid"]) == r["role"] and e["champ"]), 0)
            if opp:
                r["lane_opp_auto"] = opp
                r["lane_opp"] = self.opp_choice or opp
                self.apply_page()
        except Exception:
            pass

    def live_augments(self, found):
        self.q.put(("live_aug", found))

    def note_unknown_items(self, snap):
        """Objetos de la partida que el catálogo no conoce (parche más nuevo que el guardado, mejoras de Ornn u otra variante): se anotan una vez en el registro
        para poder enseñar a la app a reconocerlos. Mientras tanto no cuentan para «siguiente objeto» ni para lo que llevan los rivales."""
        try:
            cat = self.kit.items
            if not cat:
                return
            seen = self.__dict__.setdefault("_unknown_seen", {*()})
            new = {i for p in snap.get("players", []) for i in p.get("items", []) if i and i not in cat and i not in seen}
            if new:
                seen |= new
                core.diag("Objetos en la partida que no están en el catálogo: " + ", ".join(str(i) for i in sorted(new)) + f" (catálogo {len(cat)} objetos)")
        except Exception:
            core.log_exc("Objetos desconocidos")

    def buy_alert(self, snap):
        """Suena un aviso suave UNA vez por objeto cuando ya puedes pagar el siguiente de tu build (solo con los avisos sonoros y este aviso activados)."""
        if not self.conf.get("beep", True) or not self.conf.get("buy_alert", True):
            return
        try:
            import sounds, ui_live
            hint = ui_live.buy_hint(self, snap, self.ctx.get("plan"))
            done = getattr(self, "buy_notified", None)
            if done is None:
                done = self.buy_notified = set()
            if hint and hint[2] and hint[1] not in done:
                done.add(hint[1])
                sounds.play_alert("Cristal", self.conf.get("volume", 0.7))
        except Exception:
            core.log_exc("Aviso de compra")

    def live(self, summary):
        """Resumen de la partida en vivo (live.summarize), leído por el motor cada ~10 s durante la partida."""
        self.q.put(("live", summary))

    def show_notes(self):
        """Ventana de novedades (la misma que sale al abrir una versión nueva)."""
        import novedades
        if getattr(self, "notes_win", None) is not None:
            try:
                if self.notes_win.w.winfo_exists():
                    self.notes_win.w.lift()
                    return
            except Exception:
                pass
        def done():
            self.notes_win = None
            self.conf["notes_seen"] = novedades.NOTES[0]["v"]
            save_conf(self.conf)
        self.notes_win = novedades.NotesWindow(self, done)

    def show_notes_once(self):
        import novedades
        if novedades.unseen(self.conf):
            self.show_notes()

    def note_w(self):
        """Ancho para las notas del panel de ajustes: el del panel menos sus márgenes (antes era fijo y cortaba textos)."""
        try:
            if self.dock_dw <= 0:
                return 270
            return max(220, int(self.dock_dw / self.kit.scale_px()) - 90)
        except Exception:
            return 270

    def copy_diagnostics(self):
        extra = [f"Interfaz: escala {self.conf['scale']}, tema {self.conf['theme']}, ventana {self.root.winfo_width()}x{self.root.winfo_height()}, "
                 f"Windows {self.win_scale():.2f}x",
                 "Ajustes: " + ", ".join(f"{k}={'sí' if self.conf.get(k, d) else 'no'}" for k, d in
                                          (("live_enabled", True), ("buy_alert", True), ("meta_enabled", True), ("auto_update", True), ("auto_install", True), ("animations", True), ("beep", True)))]
        txt = core.diagnostics(extra)
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.status("Informe copiado: pégalo donde pidas ayuda.")

    def open_log(self):
        p = os.path.join(CACHE, "error.log")
        if os.path.exists(p):
            os.startfile(p)
        else:
            self.status("No hay errores registrados.")

    def clear_cache(self):
        if not messagebox.askyesno(APP_NAME, "Se borrarán las imágenes descargadas (arte, emblemas, iconos de invocador), los "
                                   "enfrentamientos guardados y el meta. Se volverán a descargar cuando hagan falta. "
                                   "Tu historial no se toca.\n\n¿Borrar?"):
            return
        for sub in ("splash", "matchups", "emblems", "profileicons", "sounds"):
            shutil.rmtree(os.path.join(CACHE, sub), ignore_errors=True)
        try:
            os.remove(os.path.join(CACHE, "meta.json"))
        except OSError:
            pass
        self.kit.icons.clear()
        self.kit.heroes.clear()
        self.status("Caché borrada. Se descargará de nuevo al hacer falta.")

    def reset_settings(self):
        if not messagebox.askyesno(APP_NAME, "Se restablecerán la apariencia, la vista, los filtros, el sonido y el estilo de "
                                   "recomendación. No se borra tu historial. LOL-E se cerrará para aplicar los cambios: "
                                   "vuelve a abrirlo.\n\n¿Restablecer?"):
            return
        keep = ("lol_path", "update_url", "opgg_region", "opgg_name", "opgg_tag")
        for key, val in core.DEFAULT_CONF.items():
            if key not in keep:
                self.conf[key] = copy.deepcopy(val)
        self.conf["weights"] = dict(core.PRESETS["equilibrado"])
        save_conf(self.conf)
        self.close()
