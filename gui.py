"""Ventana de LOL-E (CustomTkinter): armazón, eventos, panel de ajustes acoplado y volumen.

Las pantallas están formadas por secciones independientes (ui_sections.py) que solo se repintan cuando cambian
sus propios datos; las imágenes y utilidades comunes viven en ui_kit.py.
"""
import copy, os, queue, shutil, threading, time, tkinter as tk, tkinter.messagebox as messagebox
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
from PIL import Image

import lol_advisor as core
import updater
from lol_advisor import APP_NAME, APP_VERSION, CACHE, DATA_DIR, PRESET_INFO, read_json, save_conf
from ui_history import HistoryView
from ui_views import DataView, MatchupView
from ui_kit import REC_VIEWS, ACCENTS, DISPLAY, Kit, PAL, THEMES, res
from ui_game import GameView
from ui_draft import DraftCard
from ui_sections import (SummaryCard, AchievementsCard, BanIdeas, BansRow, Enemies, Lobby, ModesCard, PoolCard, ProfileCard, ProfileStrip, Recs, TurnCard, MyPick,
                         WaitCard)

DOCK_W = 360


MAX_W = 1240  # ancho máximo del contenido (se centra en pantallas más grandes)


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
        for i, nm in enumerate(("Asesor", "Partida", "Enfrentamiento", "Historial", "Datos"), 1):  # Ctrl+1…5 cambian de pestaña (en el orden de arriba)
            self.root.bind(f"<Control-Key-{i}>", lambda e, n=nm: self.set_page(n))
        self.root.bind("<Left>", lambda e: self.key_go(-1))
        self.root.bind("<Right>", lambda e: self.key_go(1))
        self.root.bind("<Configure>", self.on_resize)
        self.kit = Kit(self.root, conf, champs, lambda ev: self.q.put((ev,)))
        self.kit.goto_history, self.kit.goto_matchup = self.goto_history, self.goto_matchup
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
        self.root.after(200, self.poll)
        self.root.after(500, self.tick)
        self.root.after(1500, self.ensure_normal)
        self.root.after(2500, self.prebuild_dock)  # el panel de ajustes se prepara con la ventana en reposo
        self.root.after(5000, self.auto_check)
        if not os.environ.get("LOLE_GEOMETRY"):  # en las pruebas no se abre
            self.root.after(3500, self.show_notes_once)

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
                self.conf["win_geo"] = self.root.geometry()
                save_conf(self.conf)
        except Exception:
            pass

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
            if kind == "idle":
                self.pending_show = None
            try:
                self.handle_event(ev, kind)
            except Exception as e:  # un dato raro no debe dejar la ventana sin actualizarse
                self.status(f"Aviso: {type(e).__name__}: {e}")
        if self.pending_show is not None and time.time() - self.last_show_t >= 0.6:  # como mucho ~1,5 repintados por segundo
            ev, self.pending_show = self.pending_show, None
            self.last_show_t = time.time()
            try:
                self.handle_event(ev, "show")
            except Exception as e:
                self.status(f"Aviso: {type(e).__name__}: {e}")
        self.root.after(150, self.poll)

    pending_show, last_show_t, last_turn = None, 0.0, None
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
        plan = {"cid": r["mine"], "role": (r.get("role") or "") if sr else "", "opp": (r.get("lane_opp") or 0) if sr else 0,
                "enemies": list(r["enemies"]) if sr else [], "allies": list(r["allies"]) if sr else [], "locked": bool(r.get("mine_locked")),
                "state": "select", "kind": kind, "group": r["mode"].get("group", "")}
        if plan != {**(self.ctx.get("plan") or {}), "state": "select"}:
            self.ctx["plan"] = plan
            try:
                core.write_json(os.path.join(CACHE, "last_plan.json"), plan)
            except Exception:
                pass
        elif (self.ctx.get("plan") or {}).get("state") != "select":
            self.ctx["plan"] = plan

    def on_phase(self, flow):
        plan = self.ctx.get("plan")
        self.ctx["phase"] = flow
        if not plan:
            return
        if flow in ("InProgress", "GameStart", "Reconnect"):
            if plan["state"] != "game":
                plan["state"] = "game"
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

    def handle_event(self, ev, kind):
        if True:
            if True:
                if kind == "show":
                    _, session, r, got = ev
                    self.ctx.update(session=session, r=r, got=got)
                    first = self.advisor != "select"
                    self.advisor = "select"
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
                elif kind == "status":
                    self.status_text = ev[1]
                    self.update_footer()
                elif kind == "link":
                    self.ctx["linked"] = ev[1]
                    self.update_link()
                    if self.view == "idle":
                        self.refresh_current()
                elif kind == "assets":
                    self.kit.epoch += 1  # llegaron imágenes: lo que las usa se repinta una vez
                    self.refresh_current()
                elif kind == "splash" and self.view == "select":
                    self.recs.render()
                elif kind == "analysis":
                    self.game_view.on_data(ev[1], ev[2])
                elif kind == "game_data":
                    self.game_view.on_vs()
                elif kind == "phase":
                    self.on_phase(ev[1])
                elif kind == "recs_data" and self.view == "select":
                    self.recs.render()
                elif kind == "matchup" and self.view == "matchup":
                    self.matchup_view.update(self.make_ctx())
                elif kind == "history":
                    self.history_view.data_changed()

                elif kind == "update":
                    self.on_update(ev[1], ev[2], ev[3])
                elif kind == "update_fail":
                    self.update_btn.configure(state="normal", text=f"Actualizar a {self.update_info['version']}")
                elif kind == "update_ready":
                    updater.install(ev[1])
                    self.close()

    def tick(self):
        if not self.running:
            return
        if self.view == "select" and self.ctx["session"]:
            self.turn.tick(self.ctx)
        self.root.after(500, self.tick)

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
            used = {i for e in history.load_all(os.path.join(CACHE, "history.json"), os.path.join(CACHE, "games.json"))[:150]
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
    def auto_check(self):
        if self.conf["auto_update"] and self.conf["update_url"]:
            self.check_updates(False)

    def check_updates(self, manual):
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
        if err:
            if manual:
                self.status(f"No se ha podido comprobar si hay actualizaciones: {err}")
            return
        if info is None:
            if manual:
                self.status(f"Estás al día: la versión {APP_VERSION} es la más reciente.")
            return
        self.update_info = info
        self.update_btn.configure(text=f"Actualizar a {info['version']}")
        self.update_btn.pack(side="right", padx=(0, 10))
        self.status(f"Hay una versión nueva: {info['version']}")

    def confirm_update(self):
        info = self.update_info
        if not info:
            return
        notes = info.get("notes", "")
        if not messagebox.askyesno(APP_NAME, f"Hay una versión nueva de {APP_NAME}: {info['version']}.\n\n{notes}\n\n"
                                   "Se descargará el instalador, se comprobará su huella de seguridad y LOL-E se cerrará para "
                                   "actualizarse. Tus datos y ajustes se conservan.\n\n¿Actualizar ahora?"):
            return
        self.update_btn.configure(state="disabled", text="Descargando…")

        def go():
            try:
                path = updater.download(info, lambda f: self.status(f"Descargando la actualización… {f:.0%}"))
                self.q.put(("update_ready", path))
            except Exception as e:
                self.status(f"No se ha podido actualizar: {e}")
                self.q.put(("update_fail",))
        threading.Thread(target=go, daemon=True).start()

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
        bar.pack(fill="x", padx=18, pady=(14, 2))
        try:
            im = Image.open(res("icon.png")).convert("RGBA").resize((64, 64), Image.LANCZOS)
            self.logo = ctk.CTkImage(light_image=im, dark_image=im, size=(32, 32))
            ctk.CTkLabel(bar, image=self.logo, text="").pack(side="left", padx=(0, 10))
        except Exception:
            pass
        k.clbl(bar, APP_NAME, 22, "fg", True, True).pack(side="left")
        k.clbl(bar, f"v{APP_VERSION}", 10, "dim").pack(side="left", padx=(8, 0), pady=(8, 0))
        ajustes = ctk.CTkButton(bar, text="Ajustes", width=88, height=32, corner_radius=10, font=k.font(12), border_width=1,
                                border_color=PAL["border"], fg_color=PAL["card"], hover_color=PAL["card"], text_color=PAL["fg"],
                                command=self.toggle_dock)
        ajustes.pack(side="right")
        k.smooth_btn(ajustes, PAL["card"], PAL["card2"])
        self.link_lbl = k.clbl(bar, "", 11, "warn", True)
        self.link_lbl.pack(side="right", padx=(10, 12))
        vol = k.frame(bar)
        vol.pack(side="right")
        self.mute_btn = ctk.CTkButton(vol, text=self.vol_icon(), width=30, height=28, corner_radius=8, fg_color="transparent",
                                      hover_color=PAL["card2"], text_color=PAL["fg"], font=k.font(15), command=self.toggle_mute)
        self.mute_btn.pack(side="left")
        self.add_volume_slider(vol, 70).pack(side="left")
        self.update_btn = ctk.CTkButton(bar, text="", height=28, corner_radius=14, font=k.font(11, True), fg_color=k.acc,
                                        text_color=PAL["bg"], hover_color=k.acc, command=self.confirm_update)
        tabs = {"asesor": "Asesor", "partida": "Partida", "enfrentamiento": "Enfrentamiento", "historial": "Historial", "datos": "Datos"}
        self.tab_names = tabs
        self.tab_seg = k.seg(self.main, list(tabs.values()), tabs.get(self.page, "Asesor"), self.set_page)
        self.tab_seg.pack(fill="x", padx=18, pady=(8, 0))
        self.body = ctk.CTkScrollableFrame(self.main, fg_color="transparent", corner_radius=0)
        self.body.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        self.footer = k.clbl(self.main, "", 10, "dim", anchor="w")
        self.footer.pack(fill="x", padx=20, pady=(2, 10))
        self.update_link()

    def build_views(self):
        k = self.kit
        self.idle_view, self.select_view = k.frame(self.body), k.frame(self.body)
        self.idle_secs = [ProfileCard(k, self.idle_view), WaitCard(k, self.idle_view), SummaryCard(k, self.idle_view)]
        # (la fila de rango y racha ya no se muestra en la selección: ahí no ayuda a decidir)
        self.turn = TurnCard(k, self.select_view)
        self.draft = DraftCard(k, self.select_view)   # el orden de creación es el orden en pantalla
        mypick = MyPick(k, self.select_view)
        ideas = BanIdeas(k, self.select_view)
        self.recs = Recs(k, self.select_view)
        self.lobby = Lobby(k, self.select_view)
        self.enemies = Enemies(k, self.select_view)
        self.select_secs = [self.turn, self.draft, mypick, ideas, self.recs, self.lobby, self.enemies, BansRow(k, self.select_view)]
        self.matchup_view = MatchupView(k, self.body, self)
        self.history_view = HistoryView(k, self.body, self)
        self.data_view = DataView(k, self.body, self)
        self.game_view = GameView(k, self.body, self)

    def make_ctx(self):
        # el ancho se da en unidades lógicas (el de diseño): con la escala de Windows o el tamaño de interfaz al 125 %, 150 %…, los
        # píxeles reales son más y todo lo que se mide contra este ancho (umbrales, textos, imágenes, lienzos) se desajustaba
        self.ctx["width"] = max(self.body.winfo_width() / self.kit.scale_px(), 400)
        return self.ctx

    def show_view(self, name):
        if self.view == name:
            return
        for v in (self.idle_view, self.select_view, self.matchup_view.box, self.history_view.box, self.data_view.box, self.game_view.box):
            v.pack_forget()
        {"idle": self.idle_view, "select": self.select_view, "matchup": self.matchup_view.box,
         "history": self.history_view.box, "data": self.data_view.box, "game": self.game_view.box}[name].pack(fill="x")
        self.view = name
        try:
            self.body._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def effective_view(self):
        return {"enfrentamiento": "matchup", "historial": "history", "datos": "data", "partida": "game"}.get(self.page, self.advisor)

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
        if self.tab_seg.get() != name:
            self.tab_seg.set(name)
        self.conf["tab"] = self.page
        save_conf(self.conf)
        self.apply_page()

    def refresh_current(self, force=False):
        ctx = self.make_ctx()
        if self.view == "matchup":
            self.matchup_view.refresh(ctx, force)
        elif self.view == "history":
            self.history_view.refresh(ctx, force)
        elif self.view == "data":
            self.data_view.refresh(ctx, force)
        elif self.view == "game":
            self.game_view.refresh(ctx, force)
        elif self.view == "select" and ctx["r"]:
            self.refresh_select(ctx, force)
        elif self.view == "idle":
            for s in self.idle_secs:
                s.refresh(ctx, force)
        self.update_footer()

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
        self.root.update_idletasks()  # el ancho del cuerpo debe ser el ya colocado, no el anterior
        if self.view == "select" and self.ctx["r"]:
            self.kit.anim = False
            self.recs.resized(self.make_ctx()["width"])
        elif self.view in ("matchup", "history", "data", "idle", "game"):
            self.refresh_current()

    # ---------- enlace, pie y volumen ----------
    def update_link(self):
        ok = self.ctx["linked"]
        self.link_lbl.configure(text="●  Conectado a LoL" if ok else "●  Esperando al cliente",
                                text_color=PAL["good"] if ok else PAL["warn"])

    def update_footer(self):
        meta = read_json(core.opgg_path(self.conf), {})
        age = f"op.gg · actualizado hace {(time.time() - meta['ts']) / 3600:.0f} h" if meta.get("ts") else "op.gg: sin datos todavía"
        self.footer.configure(text=f"{self.status_text}     {age}" if self.status_text else age)

    def vol_icon(self):
        v = self.conf["volume"]
        return "🔇" if v <= 0 else "🔈" if v < .35 else "🔉" if v < .7 else "🔊"

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
        if key in ("accent", "theme", "scale"):
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
        screen_w = self.root.winfo_screenwidth() - 16
        dw = self.dock_px()
        if self.root.state() == "zoomed" or W + dw > screen_w:
            self.slide_inside(W, dw, True)  # maximizada o sin sitio: la ventana no cambia, el contenido se estrecha
            return
        X1 = min(X, max(0, screen_w - (W + dw)))
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
        head.pack(fill="x", padx=20, pady=(16, 0))
        k.clbl(head, "Ajustes", 20, "fg", True, True).pack(side="left")
        close = ctk.CTkButton(head, text="Cerrar", width=70, height=30, corner_radius=9, font=k.font(12), fg_color=PAL["card2"],
                              hover_color=PAL["card2"], text_color=PAL["fg"], command=self.close_dock)
        close.pack(side="right")
        k.smooth_btn(close, PAL["card2"], PAL["border"])
        k.clbl(d, "Los cambios se aplican al instante y se guardan solos.", 10, "dim", anchor="w", wraplength=self.note_w(),
               justify="left").pack(anchor="w", padx=22, pady=(2, 0))
        sc = ctk.CTkScrollableFrame(d, fg_color="transparent")
        sc.pack(fill="both", expand=True, padx=8, pady=(4, 10))

        def section(text):
            k.clbl(sc, text.upper(), 10, "dim", True).pack(anchor="w", padx=12, pady=(18, 4))

        def note(text):
            k.clbl(sc, text, 10, "dim", wraplength=self.note_w(), justify="left", anchor="w").pack(anchor="w", padx=14, pady=(0, 4))

        def label(text):
            k.clbl(sc, text, 11, "dim").pack(anchor="w", padx=12, pady=(8, 0))

        def seg(values, current, command):
            b = k.seg(sc, values, current, command)
            b.pack(fill="x", padx=12, pady=4)
            return b

        def switch(text, key, command=None):
            var = ctk.BooleanVar(value=bool(conf[key]))
            ctk.CTkSwitch(sc, text=text, variable=var, font=k.font(12), progress_color=k.acc,
                          command=command or (lambda: self.set(key, var.get()))).pack(anchor="w", padx=12, pady=6)

        def button(text, cmd):
            b = ctk.CTkButton(sc, text=text, font=k.font(12), fg_color=PAL["card2"], text_color=PAL["fg"], hover_color=PAL["card2"],
                              command=cmd)
            b.pack(fill="x", padx=12, pady=4)
            k.smooth_btn(b, PAL["card2"], PAL["border"])

        section("Apariencia")
        seg(list(THEMES), {v: k_ for k_, v in THEMES.items()}.get(conf["theme"], "Oscuro"),
            lambda v: self.set("theme", THEMES[v]))
        label("Color de acento")
        sw = k.frame(sc)
        sw.pack(anchor="w", padx=12, pady=(2, 0))
        for n, colr in ACCENTS.items():
            ctk.CTkButton(sw, text="", width=30, height=30, corner_radius=15, fg_color=colr, hover_color=colr, border_width=2,
                          border_color=PAL["border"], command=lambda n=n: self.set("accent", n)).pack(side="left", padx=3)
        label("Tamaño de la interfaz")
        cur = f"{round(conf['scale'] * 100)}%"
        seg(["90%", "100%", "115%", "130%"], cur if cur in ("90%", "100%", "115%", "130%") else "100%",
            lambda v: (ctk.set_widget_scaling(int(v[:-1]) / 100), self.set("scale", int(v[:-1]) / 100)))
        switch("Animaciones y transiciones", "animations")
        note("Desactívalas si prefieres cambios instantáneos o tu equipo va justo.")
        label("Ventana siempre por encima de las demás")
        tops = {"Nunca": "nunca", "En la selección": "seleccion", "Siempre": "siempre"}
        seg(list(tops), {v: k_ for k_, v in tops.items()}.get(conf.get("topmost_mode", "seleccion"), "En la selección"),
            lambda v: self.set("topmost_mode", tops[v], redraw=False))
        note("«En la selección»: solo mientras eliges campeón; el resto del tiempo se comporta como cualquier ventana (Alt+Tab).")
        switch("Modo compacto (solo turno y lo recomendado)", "compact")

        section("Al abrir")
        starts = {"Última usada": "ultima", "Asesor": "asesor", "Enfrentamiento": "enfrentamiento", "Historial": "historial", "Datos": "datos"}
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
        desc.pack(anchor="w", padx=14, pady=(2, 4))
        note("Los pesos, los umbrales y de dónde sale cada dato están en la pestaña «Datos».")
        button("Abrir la pestaña «Datos»", lambda: (self.tab_seg.set("Datos"), self.set_page("Datos")))

        section("Sonido")
        switch("Aviso sonoro cuando llega tu turno", "beep")
        label("Sonido del aviso")
        k.menu(sc, list(core.SOUNDS), conf["sound"],
               lambda v: (self.set("sound", v, redraw=False), core.play_alert(v, conf["volume"])), 300).pack(anchor="w", padx=12, pady=2)
        label("Volumen")
        self.add_volume_slider(sc, 300).pack(anchor="w", padx=12, pady=2)
        button("Probar el sonido", lambda: core.play_alert(conf["sound"], conf["volume"]))

        section("Datos")
        note("Qué fuentes se usan, y su activación, se gestiona en la pestaña «Datos».")
        button("Actualizar estadísticas de op.gg", lambda: (self.cmds.put("opgg"), self.status("Actualizando op.gg…")))
        button("Actualizar el meta del parche", lambda: (self.cmds.put("meta"), self.status("Actualizando el meta…")))
        button("Abrir la carpeta de datos", lambda: os.startfile(DATA_DIR) if os.path.isdir(DATA_DIR) else None)
        button("Borrar la caché de imágenes y enfrentamientos", self.clear_cache)

        section("Actualizaciones")
        switch("Buscar actualizaciones al abrir", "auto_update")
        label("Dirección del archivo de versión")
        entry = ctk.CTkEntry(sc, font=k.font(11), placeholder_text="https://…/latest.json", fg_color=PAL["card2"], border_color=PAL["border"],
                             text_color=PAL["fg"])
        entry.insert(0, conf["update_url"])
        entry.pack(fill="x", padx=12, pady=2)
        entry.bind("<FocusOut>", lambda e: self.set("update_url", entry.get().strip(), redraw=False))
        entry.bind("<Return>", lambda e: self.set("update_url", entry.get().strip(), redraw=False))
        button("Buscar actualizaciones ahora", lambda: (self.set("update_url", entry.get().strip(), redraw=False), self.check_updates(True)))

        section("Mantenimiento")
        button("Ver novedades", self.show_notes)
        note("Qué ha cambiado en cada versión.")
        button("Copiar informe de diagnóstico", self.copy_diagnostics)
        note("Para pedir ayuda: copia versión, sistema, estado de los datos y últimos errores (sin tu nombre ni tus partidas) y pégalo en el mensaje.")
        button("Abrir el registro de errores", lambda: self.open_log())
        button("Restablecer todos los ajustes", self.reset_settings)
        note("No borra tu historial ni tus datos; LOL-E se cierra para aplicarlo.")

        section("Acerca de")
        k.clbl(sc, f"{APP_NAME} {APP_VERSION}\nNo está respaldado por Riot Games ni refleja las opiniones de Riot Games "
                   "ni de nadie que participe oficialmente en League of Legends. Solo lee la selección de campeón "
                   "de tu cliente; nunca interviene en la partida.", 10, "dim", wraplength=self.note_w(), justify="left").pack(
            anchor="w", padx=14, pady=(0, 10))

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
                r["lane_opp"] = opp
                self.apply_page()
        except Exception:
            pass

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
                return 300
            return max(220, int(self.dock_dw / self.kit.scale_px()) - 70)
        except Exception:
            return 300

    def copy_diagnostics(self):
        extra = [f"Interfaz: escala {self.conf['scale']}, tema {self.conf['theme']}, ventana {self.root.winfo_width()}x{self.root.winfo_height()}, "
                 f"Windows {self.win_scale():.2f}x"]
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
