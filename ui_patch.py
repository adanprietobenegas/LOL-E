"""Pantalla «Parche»: las notas oficiales de Riot (en español, tal cual) y cómo se está moviendo el juego con ese parche.

Es una pantalla de LECTURA: nada que configurar, solo elegir parche, una pestaña (Notas / Estadísticas) y unos filtros de búsqueda sobre los datos DE ESE PARCHE.
Los datos salen de parche.py (notas) y parche_stats.py (estadísticas); aquí solo se dibujan. Todo se descarga en segundo plano y avisa con el evento «parche».

Diseño: una cabecera con el banner oficial del parche, fichas con una franja de color según el veredicto (mejora / debilitación / mixto / novedad), cambios «antes → después»
con el número nuevo resaltado, y tarjetas de estadísticas con la muestra siempre a la vista. Sin degradados ni adornos: lo que importa es el contenido.
"""
import datetime
import os
import re
import threading
import time
import tkinter as tk
import unicodedata
from collections import Counter

import customtkinter as ctk
from PIL import Image, ImageTk

import history
import lol_advisor as core
import meta as metamod
import parche
import parche_stats
from ui_kit import PAL, ON_FILL

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
VERDICT = {"buff": ("▲  Mejora", "good"), "nerf": ("▼  Debilitación", "bad"), "mixed": ("◆  Mixto", "warn"), "adjust": ("●  Ajuste", "dim"), "new": ("★  Novedad", "info")}
VERDICT_FILTERS = [("all", "Todos"), ("buff", "Mejoras"), ("nerf", "Debilitaciones"), ("mixed", "Mixtos"), ("new", "Novedades")]
SECTION_LABEL = {"champions": "Campeones", "items": "Objetos", "aram": "ARAM", "arena": "Arena", "classic": "Classic", "bugs": "Errores", "other": "Otros cambios"}
KIND_LABEL = {"champion": "Campeón", "item": "Objeto", "augment": "Aumento", "rune": "Runa", "other": ""}
CHUNK = 10
LIMIT = 14


def norm(s):
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn"))


def es_num(x, d=1, sign=False):
    if x is None:
        return "—"
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    return s.replace(".", ",").replace("-", "−")


def es_int(n):
    return f"{int(n):,}".replace(",", ".")


def es_date(iso):
    try:
        d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().date()
    except Exception:
        return ""
    ago = (datetime.date.today() - d).days
    when = "hoy" if ago == 0 else "ayer" if ago == 1 else f"hace {ago} días" if ago < 60 else ""
    return f"{d.day} de {MONTHS[d.month - 1]} de {d.year}" + (f" · {when}" if when else "")


class PatchView:
    def __init__(self, ui, parent, gui):
        self.ui, self.gui = ui, gui
        self.box = ui.frame(parent)
        self.sig = None
        self.versions, self.sel, self.tab = [], None, "Notas"
        self.notes, self.stats = {}, {}            # versión -> datos | "cargando" | ("error", texto, momento)
        self.sec, self.verdict, self.query, self.only_mine = "all", "all", "", False
        self.lane = "all"
        self.limits = {}
        self.content = None
        self.width = 900
        self.banner = {}
        self._tok = 0
        self._qjob = None
        self._mine = None
        self._hist = []
        self._mine_src = ""
        self.focus = ""
        self._list_try = 0
        self._retry_job = None
        self.entries_host = self.stats_host = None
        self._item_idx = None
        self._aug_idx = None
        self._wraps = []
        self.pills = {}

    # ------------------------------------------------------------ datos en segundo plano
    def start(self):
        """Pide la lista de versiones (una vez por visita) y, con ella, las notas de la última."""
        if getattr(self, "_listing", False):
            return
        self._listing = True
        self._list_try = time.time()

        def go():
            try:
                vs = parche.versions(core.CACHE)
                if vs:
                    self.versions = vs
            except Exception:
                core.log_exc("Lista de parches")
            finally:
                self._listing = False
                self.ui.notify("parche")
        threading.Thread(target=go, daemon=True).start()

    def want_notes(self, v):
        st = self.notes.get(v)
        if isinstance(st, tuple) and time.time() - st[2] > 60:
            st = None
        if st is not None:
            return st
        self.notes[v] = "cargando"
        latest = self.versions[0] if self.versions else None

        def go():
            try:
                self.notes[v] = parche.load(core.CACHE, v, latest=latest)
            except Exception as e:
                self.notes[v] = ("error", str(e), time.time())
            self.ui.notify("parche")
        threading.Thread(target=go, daemon=True).start()
        return "cargando"

    def tier(self):
        info = (self.gui.ctx.get("info") or {})
        return metamod.tier_for((((info.get("profile") or {}).get("solo") or {}).get("key")))

    def want_stats(self, v):
        key = (v, self.tier())
        st = self.stats.get(key)
        if isinstance(st, tuple) and len(st) == 3 and time.time() - st[2] > 120:
            st = None
        if isinstance(st, dict) and time.time() - st.get("at", 0) > (600 if not st["cur"] else 4 * 3600):   # sin datos: se mira de nuevo a los 10 min; con datos, a las 4 h
            st = None
        if st is not None:
            return st
        self.stats[key] = "cargando"
        latest = self.versions[0] if self.versions else None
        tier = key[1]
        vs = list(self.versions)

        def go():
            try:
                cur = parche_stats.snapshot(core.CACHE, v, tier, current=(v == latest))
                pv = vs[vs.index(v) + 1] if v in vs and vs.index(v) + 1 < len(vs) else parche_stats.prev_version(v)   # el anterior real (27.1 -> 26.24)
                prev = parche_stats.snapshot(core.CACHE, pv, tier) if pv else None
                self.stats[key] = {"cur": cur, "prev": prev, "pv": pv, "at": time.time()}
            except Exception as e:
                core.log_exc("Estadísticas del parche")
                self.stats[key] = ("error", str(e), time.time())
            self.ui.notify("parche")
        threading.Thread(target=go, daemon=True).start()
        return "cargando"

    def retry_later(self, ms):
        """Vuelve a pintar la pantalla pasado un rato (para reintentar lo que falló); un solo aviso pendiente a la vez."""
        if self._retry_job is None:
            def go():
                self._retry_job = None
                self.data_changed()
            self._retry_job = self.ui.root.after(ms, go)

    def data_changed(self):
        self.sig = None
        if self.gui.view == "patch":
            self.refresh(self.gui.make_ctx(), True)

    # ------------------------------------------------------------ utilidades de dibujo
    def hexm(self, k):
        return self.ui.hexm(PAL[k]) if isinstance(k, str) and k in PAL else self.ui.hexm(k)

    def pill(self, parent, text, active, cb, color=None, key=None):
        ui = self.ui
        fg_on, fg_off = self.hexm(ON_FILL) if isinstance(ON_FILL, (str, tuple, list)) else "#101010", self.hexm("fg")
        lab = tk.Label(parent, text=f"  {text}  ", font=ui.tkf(10, active, False), cursor="hand2", bd=0, padx=2, pady=3,
                       bg=self.hexm(color or ui.acc) if active else self.hexm("well"), fg=fg_on if active else fg_off)
        hover = self.hexm("border")
        base = lambda: self.hexm(color or ui.acc) if lab._on else self.hexm("well")
        lab._on = active
        lab.bind("<Enter>", lambda e: lab.configure(bg=hover) if not lab._on else None)
        lab.bind("<Leave>", lambda e: lab.configure(bg=base()))
        lab.bind("<Button-1>", lambda e: cb())
        return lab

    def pill_row(self, parent, items, current, cb, name):
        """Fila de pastillas; al elegir una se repintan en sitio (sin reconstruir la pantalla)."""
        row = self.ui.frame(parent)
        labs = {}

        def paint(cur):
            for k, lab in labs.items():
                on = k == cur
                lab._on = on
                lab.configure(bg=self.hexm(self.ui.acc) if on else self.hexm("well"), fg=self.hexm(ON_FILL) if on else self.hexm("fg"), font=self.ui.tkf(10, on, False))

        def pick(k):
            paint(k)
            cb(k)
        per = max(2, int((self.width - 150) // 112)) if self.width < 760 else 99   # en ventanas estrechas las pastillas pasan a la fila de debajo
        for i, (k, text) in enumerate(items):
            lab = self.pill(row, text, k == current, lambda k=k: pick(k))
            if per == 99:
                lab.pack(side="left", padx=(0, 5), pady=2)
            else:
                lab.grid(row=i // per, column=i % per, padx=(0, 5), pady=2, sticky="w")
            labs[k] = lab
        self.pills[name] = paint
        return row

    def label(self, parent, text, size=11, color="fg", bold=False, wrap=0, **kw):
        return self.ui.lbl(parent, text, size, color, bold, anchor=kw.pop("anchor", "w"), justify=kw.pop("justify", "left"), wraplength=wrap, **kw)

    def mine(self):
        """Campeones del jugador: los que ha jugado al menos 2 veces en el historial guardado y, si no hay historial, los que tiene."""
        if self._mine:
            return self._mine
        s = set()
        try:
            hist = [e for e in history.load_all(history.hpath(core.CACHE), history.gpath(core.CACHE)) if not e.get("rm")]
            self._hist = hist
            n = Counter(e.get("c") for e in hist)
            s = {c for c, k in n.items() if c and k >= 2}
        except Exception:
            pass
        self._mine_src = "hist" if s else ""
        if not s:
            s = set((self.gui.ctx.get("info") or {}).get("owned") or [])
            self._mine_src = "owned" if s else ""
        if s:   # un conjunto vacío no se recuerda: la información del cliente puede llegar después
            self._mine = s
        return s

    def before_after(self, cid, iso):
        """Tus partidas con `cid` antes y desde la fecha del parche: (victorias, partidas) de cada tramo. Muestra pequeña: la pantalla lo dice."""
        try:
            cut = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000
        except Exception:
            return None
        a = [e for e in self._hist if e.get("c") == cid and e.get("t", 0) < cut]
        b = [e for e in self._hist if e.get("c") == cid and e.get("t", 0) >= cut]
        if not a and not b:
            return None
        return (sum(1 for e in a if e.get("w")), len(a)), (sum(1 for e in b if e.get("w")), len(b))

    def played(self):
        """Los campeones que de verdad has jugado (del historial). Vacío si solo se sabe cuáles tienes: entonces no se marca nada como «tuyo»."""
        s = self.mine()
        return s if self._mine_src == "hist" else set()

    def touched_mine(self, d):
        """Nombres de los campeones que de verdad has jugado y que tocan las notas `d` (solo la sección Campeones, sin novedades de Classic). Para el aviso de parche nuevo."""
        mine = self.played()
        out = []
        for s in (d or {}).get("sections", []):
            if s.get("kind") != "champions":
                continue
            for g in s.get("groups", []):
                for e in g.get("entries", []):
                    if e.get("kind") == "champion" and self.champ_id(e) in mine and e["name"] not in out:
                        out.append(e["name"])
        return out

    def champ_id(self, entry):
        idx = getattr(self, "_cidx", None)
        if idx is None or len(idx) < 5:
            idx = self._cidx = parche_stats.champion_index(self.ui.champs)
        return idx.get(norm(parche.champion_slug(entry))) or idx.get(norm(entry.get("name")))

    def item_id(self, name):
        if self._item_idx is None or len(self._item_idx) < 5:
            idx = {}
            for iid, it in sorted((self.ui.items or {}).items()):
                if iid < 10000:
                    idx.setdefault(norm(it.get("n")), iid)
            self._item_idx = idx
        return self._item_idx.get(norm(name))

    def augment_photo(self, name, size):
        """Icono de un aumento de ARAM: Caos si ya está en la caché (los baja el propio cliente de LoL al abrir su pantalla); si no, la insignia."""
        try:
            import augments
            if not self._aug_idx:
                self._aug_idx = {norm(v.get("n")): k for k, v in augments.catalog().items()}
            aid = self._aug_idx.get(norm(name))
            pth = augments.icon_path(aid) if aid else None
            if not pth:
                return None
            return self.ui._photo(("aug", aid), Image.open(pth).convert("RGBA"), size)
        except Exception:
            return None

    def icon_for(self, parent, entry, size=40):
        """Retrato del campeón, icono del objeto, o una insignia con la inicial; todo en un cuadrado del mismo tamaño."""
        ui = self.ui
        ph = None
        if entry["kind"] == "champion":
            cid = self.champ_id(entry)
            ph = ui.champ_photo(cid, size) if cid else None
        elif entry["kind"] == "item":
            iid = self.item_id(entry["name"])
            ph = ui.item_photo(iid, size) if iid else None
        elif entry["kind"] == "augment":
            ph = self.augment_photo(entry["name"], size)
        if ph is not None:
            lab = tk.Label(parent, image=ph, bd=0, bg=ui.bg(parent))
            lab.image = ph
            return lab
        glyph = {"augment": "✦", "item": "◈", "rune": "◉", "champion": (entry["name"] or "?")[:1].upper()}.get(entry["kind"], (entry["name"] or "?")[:1].upper())
        px = int(size * ui.scale_px())
        f = tk.Frame(parent, width=px, height=px, bg=self.hexm("well"))
        f.pack_propagate(False)
        tk.Label(f, text=glyph, font=ui.tkf(int(max(12, size // 2.4)), True, False), fg=self.hexm("dim"), bg=self.hexm("well")).pack(expand=True)
        return f

    # ------------------------------------------------------------ pantalla
    def refresh(self, ctx, force=False):
        ui = self.ui
        self.width = ctx["width"]
        if not self.versions and not getattr(self, "_listing", False) and time.time() - self._list_try > 60:   # sin red: se reintenta como mucho una vez por minuto
            self.start()
        sig = (ui.epoch, int(self.width // 90), self.sel, self.tab, tuple(self.versions[:3]), len(self.notes), len(self.stats))
        if sig == self.sig and not force:
            return
        self.sig = sig
        self._tok += 1
        self.cancel_query()
        self.pills = {}
        ui.clear(self.box)
        outer = ui.frame(self.box)
        outer.pack(fill="x", padx=8)
        self.header(outer)
        self.content = ui.frame(outer)
        self.content.pack(fill="x")
        self.fill_content()

    def current(self):
        if self.sel and (not self.versions or self.sel in self.versions):
            return self.sel
        return self.versions[0] if self.versions else None

    def header(self, host):
        ui = self.ui
        v = self.current()
        card = ui.card(host)
        data = self.notes.get(v) if v else None
        data = data if isinstance(data, dict) else None
        top = ui.frame(card)
        top.pack(fill="x")
        if data and data.get("banner") and self.tab == "Notas":
            lab = tk.Label(top, bd=0, bg=ui.bg(top))
            lab.pack(fill="x", pady=(0, 12))
            lab._bw = 0

            def fit(e, lab=lab, url=data["banner"], v=v):
                if abs(e.width - lab._bw) > 6 and e.width > 100:   # el banner ocupa justo el ancho de la tarjeta, sea cual sea la ventana
                    lab._bw = e.width
                    bn = self.banner_image(url, v, e.width / ui.scale_px())
                    if bn is not None:
                        lab.configure(image=bn)
                        lab.image = bn
            lab.bind("<Configure>", fit)
        row = ui.frame(top)
        row.pack(fill="x")
        left = ui.frame(row)
        left.pack(side="left", fill="x", expand=True)
        ctk.CTkFrame(left, width=3, height=1, fg_color="transparent").pack()
        self.label(left, "NOTAS OFICIALES DE RIOT · EN ESPAÑOL", 9, "dim", True).pack(anchor="w")
        self.label(left, f"Parche {v}" if v else "Parche", 26, "fg", True).pack(anchor="w", pady=(0, 2))
        sub = es_date(data["date"]) if data else ("Buscando el último parche…" if not self.versions else "")
        if data and data["authors"]:
            sub += ("  ·  " if sub else "") + "Diseño: " + ", ".join(data["authors"][:3])
        if sub:
            self.label(left, sub, 10, "dim").pack(anchor="w")
        right = ui.frame(row)
        right.pack(side="right", anchor="n")
        if v and self.versions:
            vals = [f"{x}" for x in self.versions[:12]]
            m = ui.menu(right, vals, v, self.pick_version, width=96)
            m.pack(side="left", padx=(0, 8))
            ui.tip(m, "Otro parche")
        if data and data.get("url"):
            host_link = right if self.width >= 800 else left   # en ventanas estrechas el enlace pasa bajo el título para no quedar cortado
            b = tk.Label(host_link, text="Abrir en la web de Riot ↗", font=ui.tkf(10, True, False), fg=self.hexm(ui.acc), bg=ui.bg(host_link), cursor="hand2")
            if host_link is right:
                b.pack(side="left")
            else:
                b.pack(anchor="w", pady=(4, 0))
            b.bind("<Button-1>", lambda e, u=data["url"]: __import__("webbrowser").open(u))
        if data and data["summary"] and self.tab == "Notas":
            self.label(card, data["summary"], 12, "fg", wrap=max(260, self.width - 130)).pack(anchor="w", pady=(10, 0))
        bar = ui.frame(card)
        bar.pack(fill="x", pady=(12, 0))
        seg = ui.seg(bar, ["Notas", "Estadísticas"], self.tab, self.set_tab, width=230, height=30)
        seg.pack(side="left")
        ui.reg("parche.pestanas", seg)

    def banner_image(self, url, v, w):
        """El banner oficial recortado a un panorama bajo (un tercio del alto); se descarga una vez y se guarda en la caché."""
        w = int(w // 8 * 8)
        key = (v, w)
        if key in self.banner:
            return self.banner[key]
        path = os.path.join(core.CACHE, "parche", f"banner_{v}.jpg")
        if not os.path.exists(path):
            self.ui.fetch(url, path, "parche")
            return None
        try:
            im = Image.open(path).convert("RGB")
            px = int(w * self.ui.scale_px())
            h = int(px * 0.26)
            r = im.width / px
            ch = int(h * r)
            top = max(0, int((im.height - ch) * 0.38))
            im = im.crop((0, top, im.width, min(im.height, top + ch))).resize((px, h), Image.LANCZOS)
            ph = ImageTk.PhotoImage(im)
            for k in [k for k in self.banner if k[0] == v]:
                del self.banner[k]   # solo se guarda el último ancho de cada parche
            self.banner[key] = ph
            return ph
        except Exception:
            return None

    def cancel_query(self):
        if self._qjob is not None:
            try:
                self.ui.root.after_cancel(self._qjob)
            except Exception:
                pass
            self._qjob = None

    def pick_version(self, v):
        self.cancel_query()
        self.sel = v
        self.sec, self.verdict, self.lane, self.focus = "all", "all", "all", ""
        self.limits = {}
        self.sig = None
        self.refresh(self.gui.make_ctx(), True)

    def set_tab(self, t):
        self.cancel_query()
        self.tab = t
        self.limits = {}
        self.sig = None
        self.refresh(self.gui.make_ctx(), True)   # la cabecera cambia con la pestaña (el banner solo va en Notas)

    def fill_content_clear(self):
        self.cancel_query()
        self._tok += 1
        self.pills = {}
        self.ui.clear(self.content)
        self.fill_content()

    def fill_content(self):
        v = self.current()
        if not v:
            self.msg("Buscando las notas del último parche…" if not self.versions else "No se ha podido leer la lista de parches.")
            if self.versions == [] and not getattr(self, "_listing", False):
                self.label(self.content, "Comprueba tu conexión. Las notas oficiales están en leagueoflegends.com/es-es.", 10, "dim").pack(anchor="w", padx=12)
            return
        if self.tab == "Notas":
            self.notes_tab(v)
        else:
            self.stats_tab(v)

    def msg(self, text, color="dim"):
        c = self.ui.card(self.content)
        self.label(c, text, 12, color, wrap=max(260, self.width - 130)).pack(anchor="w")

    # ------------------------------------------------------------ pestaña Notas
    def notes_tab(self, v):
        ui = self.ui
        d = self.want_notes(v)
        if d == "cargando":
            self.msg("Descargando las notas oficiales…")
            return
        if isinstance(d, tuple):
            self.msg(f"No se han podido leer las notas del parche {v}: {d[1]}", "warn")
            return
        secs = [s for s in d["sections"] if s["kind"] not in ("tft", "skins", "highlights", "pass") and (s["groups"] or s["intro"])]
        if not secs:
            self.msg("Las notas de este parche no se han podido interpretar (la web de Riot puede haber cambiado). Ábrelas en la página oficial con el enlace de arriba.", "warn")
            return
        self.cur_notes, self.cur_secs = d, secs
        # resumen del diseñador (plegado) y fichas de recuento
        if d["intro"]:
            c = ui.card(self.content)
            self.label(c, "NOTA DE LOS DISEÑADORES", 9, "dim", True).pack(anchor="w")
            full = "\n\n".join(d["intro"])
            short = d["intro"][0]
            state = {"open": False}
            lab = self.label(c, short if len(short) < 420 else short[:400].rsplit(" ", 1)[0] + "…", 11, "fg", wrap=max(260, self.width - 130))
            lab.pack(anchor="w", pady=(4, 0))
            if len(full) > len(short) or len(short) >= 420:
                tog = tk.Label(c, text="Leerla entera ▾", font=ui.tkf(10, True, False), fg=self.hexm(ui.acc), bg=ui.bg(c), cursor="hand2")
                tog.pack(anchor="w", pady=(6, 0))

                def flip():
                    state["open"] = not state["open"]
                    lab.configure(text=full if state["open"] else (short if len(short) < 420 else short[:400].rsplit(" ", 1)[0] + "…"))
                    tog.configure(text="Plegar ▴" if state["open"] else "Leerla entera ▾")
                tog.bind("<Button-1>", lambda e: flip())
            if d["designers"]:
                self.label(c, "  ·  ".join(d["designers"]), 9, "dim").pack(anchor="w", pady=(8, 0))
        self.tiles(secs)
        self.yours(secs)
        self.glance(secs)
        # barra de filtros
        card = ui.card(self.content)
        counts = self.counts(secs)
        items = [("all", f"Todo · {sum(counts.values())}")] + [(k, f"{SECTION_LABEL.get(k, k)} · {n}") for k, n in counts.items() if n]
        if self.sec not in dict(items):
            self.sec = "all"
        r1 = self.pill_row(card, items, self.sec, self.set_section, "sec")
        r1.pack(anchor="w")
        r2 = ui.frame(card)
        r2.pack(fill="x", pady=(6, 0))
        vrow = self.pill_row(r2, VERDICT_FILTERS, self.verdict, self.set_verdict, "verdict")
        vrow.pack(side="left")
        ui.reg("parche.filtros", r1)
        tail = ui.frame(r2) if self.width >= 900 else ui.frame(card)
        if self.width >= 900:
            tail.pack(side="right")
        else:
            tail.pack(anchor="w", pady=(6, 0))
        if self.mine():
            tg = self.pill(tail, "Solo mis campeones", self.only_mine, lambda: None)
            tg.pack(side="left", padx=(0, 8))
            tg.bind("<Button-1>", lambda e, t=tg: self.flip_mine(t))
            ui.tip(tg, "Muestra solo a los campeones que has jugado (o, si aún no hay historial, los que tienes).")
        if self.focus:
            fc = tk.Label(tail, text=f"  Ficha: {self.focus}  ✕  ", font=ui.tkf(10, True, False), fg=self.hexm(ON_FILL), bg=self.hexm(ui.acc), cursor="hand2", pady=3)
            fc.pack(side="left", padx=(0, 8))
            fc.bind("<Button-1>", lambda e: (setattr(self, "focus", ""), self.fill_content_clear()))
        ent = ctk.CTkEntry(tail, width=190, height=28, placeholder_text="Buscar en el parche…", font=ui.font(11), fg_color=PAL["well"], border_width=0, text_color=PAL["fg"])
        ent.pack(side="left")
        if self.query:
            ent.insert(0, self.query)
        ent.bind("<KeyRelease>", lambda e, w=ent: self.type_query(w.get()))
        self.entries_host = ui.frame(self.content)
        self.entries_host.pack(fill="x")
        self.render_entries()

    def yours(self, secs):
        """«Tus campeones en este parche»: los que has jugado y han tocado las notas, con su veredicto y el primer cambio; es la respuesta a «¿qué cambió en lo que juego?»."""
        ui = self.ui
        pl = self.played()
        if not pl:
            return
        rows = []
        for s in secs:
            if s["kind"] != "champions":
                continue
            for g in s["groups"]:
                for e in g["entries"]:
                    if e["kind"] == "champion" and self.champ_id(e) in pl:
                        rows.append(e)
        if not rows:
            return
        bg = self.hexm("card2")
        outer = tk.Frame(self.content, bg=ui.bg(self.content))
        outer.pack(fill="x", padx=8, pady=(0, 8))
        card = tk.Frame(outer, bg=bg, highlightthickness=1, highlightbackground=self.hexm(ui.edge_color()))
        card.pack(fill="x")
        tk.Frame(card, width=4, bg=self.hexm(ui.acc)).pack(side="left", fill="y")
        inner = tk.Frame(card, bg=bg)
        inner.pack(side="left", fill="x", expand=True, padx=14, pady=10)
        tk.Label(inner, text="TUS CAMPEONES EN ESTE PARCHE", font=ui.tkf(9, True, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w", pady=(0, 4))
        ui.reg("parche.tuyos", card)
        for e in rows[:6]:
            vk, vcol = VERDICT.get(e["verdict"], VERDICT["adjust"])
            first = next((ln for b in e["blocks"] for ln in b["lines"]), None)
            blk = next((b["title"] for b in e["blocks"] if b["lines"]), "")
            txt = ""
            if first:
                txt = (blk + ": " if blk else "") + ((first["label"] + " " + first["before"] + " → " + first["after"]) if first["before"] else first["text"])
                txt = txt if len(txt) <= 70 else txt[:67].rsplit(" ", 1)[0] + "…"
            ba = self.before_after(self.champ_id(e), self.cur_notes.get("date", ""))
            if ba:
                (w0, n0), (w1, n1) = ba
                txt += ("   ·   " if txt else "") + f"tus partidas: antes {w0}V {n0 - w0}D" + (f", desde el parche {w1}V {n1 - w1}D" if n1 else ", aún ninguna desde el parche")
            row = tk.Frame(inner, bg=bg, cursor="hand2")
            row.pack(fill="x", pady=3)
            ph = ui.champ_photo(self.champ_id(e), 30)
            if ph is not None:
                ic = tk.Label(row, image=ph, bd=0, bg=bg)
                ic.image = ph
                ic.pack(side="left", padx=(0, 10))
            tk.Label(row, text=e["name"], font=ui.tkf(11, True, False), fg=self.hexm("fg"), bg=bg, width=13, anchor="w").pack(side="left")
            tk.Label(row, text=vk, font=ui.tkf(10, True, False), fg=self.hexm(vcol), bg=bg, width=15, anchor="w").pack(side="left")
            tk.Label(row, text=txt, font=ui.tkf(10, False, False), fg=self.hexm("dim"), bg=bg, anchor="w").pack(side="left", fill="x", expand=True)
            ui.clickable(row, lambda n=e["name"]: self.jump_to(n))
        if len(rows) > 6:
            tk.Label(inner, text=f"… y {len(rows) - 6} más (filtra con «Solo mis campeones»)", font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w", pady=(2, 0))
        tk.Label(inner, text="Pocas partidas por campeón: es una referencia, no una conclusión.", font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w", pady=(4, 0))

    def glance(self, secs):
        """«De un vistazo»: los retratos de los campeones que mejoran y los que bajan; pulsar uno busca su ficha. Es lo que primero se quiere saber de un parche."""
        ui = self.ui
        champs = [e for s in secs if s["kind"] == "champions" for g in s["groups"] for e in g["entries"] if e["kind"] == "champion"]
        groups = [("▲  MEJORAN", "good", [e for e in champs if e["verdict"] == "buff"]), ("▼  BAJAN", "bad", [e for e in champs if e["verdict"] == "nerf"]),
                  ("◆  MIXTOS", "warn", [e for e in champs if e["verdict"] == "mixed"])]
        groups = [g for g in groups if g[2]]
        if not groups:
            return
        bg = self.hexm("card2")
        outer = tk.Frame(self.content, bg=ui.bg(self.content))
        outer.pack(fill="x", padx=8, pady=(0, 8))
        card = tk.Frame(outer, bg=bg, highlightthickness=1, highlightbackground=self.hexm(ui.edge_color()))
        card.pack(fill="x")
        inner = tk.Frame(card, bg=bg)
        inner.pack(fill="x", padx=14, pady=10)
        tk.Label(inner, text="DE UN VISTAZO · CAMPEONES DE LA GRIETA", font=ui.tkf(9, True, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w", pady=(0, 6))
        mine = self.played()
        for title, color, es in groups:
            row = tk.Frame(inner, bg=bg)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=title, font=ui.tkf(10, True, False), fg=self.hexm(color), bg=bg, width=11, anchor="w").pack(side="left", anchor="n", pady=6)
            icons = tk.Frame(row, bg=bg)
            icons.pack(side="left", fill="x", expand=True)
            per_row = max(6, int((self.width - 260) // 46))
            for j, e in enumerate(es):
                cid = self.champ_id(e)
                ph = ui.champ_photo(cid, 38) if cid else None
                cell = tk.Frame(icons, bg=bg)
                cell.grid(row=j // per_row, column=j % per_row, padx=2, pady=2)
                if ph is not None:
                    lab = tk.Label(cell, image=ph, bd=0, bg=bg, cursor="hand2")
                    lab.image = ph
                else:
                    lab = tk.Label(cell, text=e["name"][:2], font=ui.tkf(10, True, False), fg=self.hexm("fg"), bg=self.hexm("well"), width=4, height=2, cursor="hand2")
                lab.pack()
                if cid in mine:
                    tk.Frame(cell, height=3, bg=self.hexm(ui.acc)).pack(fill="x")   # una raya del acento: es uno de los tuyos
                ui.tip(lab, e["name"] + ("  ·  lo juegas" if cid in mine else ""))
                lab.bind("<Button-1>", lambda ev, n=e["name"]: self.jump_to(n))

    def jump_to(self, name):
        """Filtra la lista por el nombre pulsado (y vuelve arriba de la lista)."""
        self.focus, self.query = name, ""
        self.sec = "champions"
        self.limits = {}
        self.fill_content_clear()
        try:   # que se vea la ficha: la pantalla baja hasta la lista
            self.ui.root.after(150, lambda: self.gui.body._parent_canvas.yview_moveto(0.28))
        except Exception:
            pass

    def counts(self, secs):
        out = {}
        for s in secs:
            n = sum(len(g["entries"]) + (1 if g["bullets"] else 0) for g in s["groups"])
            out[s["kind"]] = out.get(s["kind"], 0) + (n or (1 if s["intro"] else 0))
        return out

    def tiles(self, secs):
        """Fichas de recuento: cuántos campeones y objetos se tocan y cuántas son mejoras o debilitaciones. Pulsar una filtra la lista."""
        ui = self.ui
        champs = [e for s in secs if s["kind"] in ("champions",) for g in s["groups"] for e in g["entries"] if e["kind"] == "champion"]
        ch = Counter(e["verdict"] for e in champs)
        items = [e for s in secs if s["kind"] == "items" for g in s["groups"] for e in g["entries"]]
        augs = [e for s in secs if s["kind"] == "aram" for g in s["groups"] for e in g["entries"] if e["kind"] == "augment"]
        bugs = sum(len(g["bullets"]) for s in secs if s["kind"] == "bugs" for g in s["groups"])
        tiles = []
        if champs:
            sub = f"{ch['buff']} " + ("mejora" if ch["buff"] == 1 else "mejoran") + f" · {ch['nerf']} " + ("baja" if ch["nerf"] == 1 else "bajan")
            if ch["mixed"]:
                sub += f" · {ch['mixed']} " + ("mixto" if ch["mixed"] == 1 else "mixtos")
            tiles.append((str(len(champs)), "campeón tocado" if len(champs) == 1 else "campeones tocados", sub, "champions"))
        if items:
            tiles.append((str(len(items)), "objeto" if len(items) == 1 else "objetos", "", "items"))
        if augs:
            tiles.append((str(len(augs)), "aumento" if len(augs) == 1 else "aumentos", "ARAM: Caos", "aram"))
        if bugs:
            tiles.append((str(bugs), "error corregido" if bugs == 1 else "errores corregidos", "", "bugs"))
        if not tiles:
            return
        row = tk.Frame(self.content, bg=ui.bg(self.content))
        row.pack(fill="x", padx=8, pady=(0, 6))
        per = len(tiles) if self.width >= 720 else 2
        for i, (n, label, sub, key) in enumerate(tiles):
            row.columnconfigure(i % per, weight=1, uniform="tiles")
            t = tk.Frame(row, bg=self.hexm("card2"), highlightthickness=1, highlightbackground=self.hexm(ui.edge_color()), cursor="hand2")
            t.grid(row=i // per, column=i % per, sticky="nsew", padx=(0, 8) if i % per < per - 1 else 0, pady=(0, 8) if per < len(tiles) else 0)
            inner = tk.Frame(t, bg=self.hexm("card2"))
            inner.pack(fill="both", expand=True, padx=14, pady=10)
            tk.Label(inner, text=n, font=ui.tkf(22, True, True), fg=self.hexm(ui.acc), bg=self.hexm("card2")).pack(anchor="w")
            tk.Label(inner, text=label, font=ui.tkf(10, True, False), fg=self.hexm("fg"), bg=self.hexm("card2")).pack(anchor="w")
            tk.Label(inner, text=sub or " ", font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=self.hexm("card2")).pack(anchor="w")
            ui.clickable(t, lambda k=key: self.set_section(k, True))

    def set_section(self, k, repaint=False):
        self.sec = k
        self.limits = {}
        if repaint and "sec" in self.pills:
            self.pills["sec"](k)
        self.render_entries()

    def set_verdict(self, k):
        self.verdict = k
        self.limits = {}
        self.render_entries()

    def flip_mine(self, lab):
        self.only_mine = not self.only_mine
        lab._on = self.only_mine
        lab.configure(bg=self.hexm(self.ui.acc) if self.only_mine else self.hexm("well"), fg=self.hexm(ON_FILL) if self.only_mine else self.hexm("fg"))
        self.limits = {}
        self.render_entries()

    def type_query(self, text):
        if self._qjob is not None:
            try:
                self.ui.root.after_cancel(self._qjob)
            except Exception:
                pass

        def go():
            self._qjob = None
            try:
                if self.entries_host is None or not self.entries_host.winfo_exists():
                    return
            except Exception:
                return
            self.query = text.strip()
            self.focus = ""
            self.limits = {}
            self.render_entries()
        self._qjob = self.ui.root.after(260, go)

    def match(self, e):
        if self.verdict != "all" and e.get("verdict") != self.verdict:
            return False
        if self.focus and norm(e["name"]) != norm(self.focus):
            return False
        if self.only_mine:
            cid = self.champ_id(e) if e["kind"] == "champion" else None
            if cid not in self.mine():
                return False
        q = norm(self.query)
        if q:
            hay = norm(e["name"] + " " + " ".join(e["note"]) + " " + " ".join(b["title"] + " " + " ".join(l["text"] for l in b["lines"]) for b in e["blocks"]))
            if q not in hay:
                return False
        return True

    def render_entries(self):
        """Repinta la lista según los filtros. Las fichas se dibujan de diez en diez para no congelar la ventana."""
        ui = self.ui
        self._tok += 1
        tok = self._tok
        host = self.entries_host
        ui.clear(host)
        secs = [s for s in self.cur_secs if self.sec in ("all", s["kind"]) or (self.sec == "aram" and s["kind"] == "arena" and False)]
        anything = False
        jobs = []
        for s in secs:
            gs = []
            for g in s["groups"]:
                es = [e for e in g["entries"] if self.match(e)]
                bl = g["bullets"] if (self.verdict == "all" and not self.only_mine and (not self.query or any(norm(self.query) in norm(b["text"]) for b in g["bullets"]))) else []
                if self.query:
                    bl = [b for b in bl if norm(self.query) in norm(b["text"])]
                if es or bl:
                    gs.append((g, es, bl))
            intro_ok = s["intro"] and not gs and self.verdict == "all" and not self.only_mine and (not self.query or any(norm(self.query) in norm(p) for p in s["intro"]))
            if gs or intro_ok:
                anything = True
                jobs.append((s, gs, intro_ok))
        if not anything:
            c = ui.frame(host)
            c.pack(fill="x", padx=8, pady=12)
            self.label(c, "Nada coincide con esos filtros." if (self.query or self.verdict != "all" or self.only_mine) else "No hay cambios en esta categoría.", 11, "dim").pack(anchor="w")
            return
        steps = []
        for s, gs, intro_ok in jobs:
            steps.append(("title", s))
            if intro_ok:
                steps.append(("prose", s))
            for g, es, bl in gs:
                steps.append(("group", (s, g, es, bl)))
        self.run_steps(host, steps, tok)

    def run_steps(self, host, steps, tok, i=0):
        if tok != self._tok or not host.winfo_exists() or i >= len(steps):
            return
        kind, x = steps[i]
        try:
            if kind == "title":
                self.section_title(host, x)
            elif kind == "prose":
                self.prose(host, x)
            else:
                self.group(host, *x, tok)
        except Exception:
            core.log_exc("Notas del parche: dibujar sección")
        self.ui.root.after(1, lambda: self.run_steps(host, steps, tok, i + 1))

    def section_title(self, host, s):
        ui = self.ui
        row = ui.frame(host)
        row.pack(fill="x", padx=12, pady=(18, 4))
        ctk.CTkFrame(row, width=3, height=16, corner_radius=2, fg_color=ui.acc).pack(side="left", padx=(0, 8))
        self.label(row, s["title"].upper(), 11, "fg", True).pack(side="left")
        kind_note = {"aram": "ARAM: Caos y ARAM", "classic": "Modo Classic", "arena": "Arena"}.get(s["kind"])

    def prose(self, host, s):
        c = self.ui.frame(host)
        c.pack(fill="x", padx=12, pady=(0, 6))
        for p in s["intro"]:
            self.label(c, p, 11, "fg", wrap=max(260, self.width - 120)).pack(anchor="w", pady=(0, 6))

    def group(self, host, s, g, entries, bullets, tok):
        ui = self.ui
        wrap = ui.frame(host)
        wrap.pack(fill="x", padx=8)
        if g["title"] and (len(s["groups"]) > 1 or s["kind"] in ("aram", "classic", "arena")):
            self.label(wrap, f"{g['title']}  ·  {len(entries) or len(bullets)}", 10, "dim", True).pack(anchor="w", padx=6, pady=(10, 4))
        if entries:
            key = (s["id"], g["title"])
            lim = self.limits.get(key, LIMIT)
            pl = self.played()
            if pl and g.get("kind") == "champion":   # tus campeones primero (el orden entre ellos y entre el resto no cambia)
                entries = sorted(entries, key=lambda e: self.champ_id(e) not in pl)
            shown = entries[:lim]
            cols = 2 if self.width >= 940 else 1
            cframe = ui.frame(wrap)
            cframe.pack(fill="x")
            colw = (self.width - 150) / cols
            heights = [0] * cols
            columns = []
            for ci in range(cols):
                f = ui.frame(cframe)
                f.pack(side="left", fill="both", expand=True, anchor="n", padx=(0, 8) if ci < cols - 1 else 0)
                columns.append(f)
            for e in shown:
                ci = heights.index(min(heights))
                self.entry_card(columns[ci], e, colw)
                heights[ci] += 3 + sum(len(b["lines"]) + 1 for b in e["blocks"])
            if len(entries) > lim:
                more = tk.Label(wrap, text=f"Mostrar {min(LIMIT, len(entries) - lim)} más  ({len(entries) - lim} sin ver) ▾", font=ui.tkf(10, True, False),
                                fg=self.hexm(ui.acc), bg=ui.bg(wrap), cursor="hand2")
                more.pack(anchor="w", padx=8, pady=(4, 6))
                more.bind("<Button-1>", lambda e, k=key, n=lim: self.show_more(k, n))
        ui.root.after(40, lambda: self.settle(False))
        ui.root.after(400, self.settle)
        if bullets:
            card = tk.Frame(wrap, bg=self.hexm("card2"), highlightthickness=1, highlightbackground=self.hexm(ui.edge_color()))
            card.pack(fill="x", padx=6, pady=(2, 6))
            inner = tk.Frame(card, bg=self.hexm("card2"))
            inner.pack(fill="x", padx=14, pady=10)
            for b in bullets:
                row = tk.Frame(inner, bg=self.hexm("card2"))
                row.pack(fill="x", pady=2)
                tk.Label(row, text="•", font=ui.tkf(11, True, False), fg=self.hexm("dim"), bg=self.hexm("card2")).pack(side="left", anchor="n", padx=(0, 8))
                self.line_in(row, b, max(240, self.width - 190), card_bg="card2")
            ui.root.after(40, lambda: self.settle(False))
            ui.root.after(400, self.settle)

    def show_more(self, key, n):
        """Enseña diez fichas más sin que la pantalla salte: se recuerda cuántos píxeles había por encima y se vuelve a ellos al repintar."""
        cv = None
        try:
            cv = self.gui.body._parent_canvas
            total = max(1, (cv.bbox("all") or (0, 0, 0, 1))[3])
            off = cv.yview()[0] * total
        except Exception:
            off = None
        self.limits[key] = n + LIMIT
        self.render_entries()

        def back():
            try:
                tot = max(1, (cv.bbox("all") or (0, 0, 0, 1))[3])
                cv.yview_moveto(min(1.0, off / tot))
            except Exception:
                pass
        if off is not None:
            for ms in (60, 250, 700):
                self.ui.root.after(ms, back)

    # ------------------------------------------------------------ una ficha
    def entry_card(self, parent, e, colw):
        ui = self.ui
        vk, vcol = VERDICT.get(e["verdict"], VERDICT["adjust"])
        bg = self.hexm("card2")
        outer = tk.Frame(parent, bg=self.hexm("bg") if False else ui.bg(parent))
        outer.pack(fill="x", pady=(0, 8))
        card = tk.Frame(outer, bg=bg, highlightthickness=1, highlightbackground=self.hexm(ui.edge_color()))
        card.pack(fill="x")
        tk.Frame(card, width=4, bg=self.hexm(vcol)).pack(side="left", fill="y")
        inner = tk.Frame(card, bg=bg)
        inner.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        head = tk.Frame(inner, bg=bg)
        head.pack(fill="x")
        self.icon_for(head, e, 40).pack(side="left", padx=(0, 10))
        txt = tk.Frame(head, bg=bg)
        txt.pack(side="left", fill="x", expand=True)
        nm = tk.Frame(txt, bg=bg)
        nm.pack(anchor="w")
        tk.Label(nm, text=e["name"], font=ui.tkf(13, True, False), fg=self.hexm("fg"), bg=bg, anchor="w").pack(side="left")
        if e["kind"] == "champion" and self.champ_id(e) in self.played():
            mk = tk.Label(nm, text="  ★ lo juegas", font=ui.tkf(9, True, False), fg=self.hexm(ui.acc), bg=bg)
            mk.pack(side="left")
            ui.tip(mk, "Es uno de tus campeones (los que has jugado en tu historial).")
        subtxt = KIND_LABEL.get(e["kind"], "")
        if e.get("tag") and e["tag"] != "NOVEDAD":
            subtxt = (subtxt + " · " if subtxt else "") + e["tag"].capitalize()
        if subtxt:
            tk.Label(txt, text=subtxt, font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg, anchor="w").pack(anchor="w")
        if e["verdict"] == "mixed":
            vk = f"{vk}  {e.get('up', 0)}▲ {e.get('down', 0)}▼"
        pill = tk.Label(head, text=f" {vk} ", font=ui.tkf(9, True, False), fg=self.hexm(vcol), bg=self.hexm("well"), padx=4, pady=2)
        pill.pack(side="right", anchor="n")
        if e.get("up") or e.get("down"):
            ui.tip(pill, "Estimación automática a partir de los números de cada cambio" + f": {e.get('up', 0)} a favor, {e.get('down', 0)} en contra. No es la opinión de Riot.")
        wrap = max(200, colw - 50)
        if e["note"]:
            note = " ".join(e["note"])
            short = note if len(note) <= 190 else note[:185].rsplit(" ", 1)[0] + "…"
            nl = tk.Label(inner, text=short, font=ui.tkf(10, False, False), fg=self.hexm("fg"), bg=bg, anchor="w", justify="left", wraplength=int(wrap * ui.scale_px()))
            nl.pack(anchor="w", pady=(8, 0), fill="x")
            self.reg_wrap(nl, inner)
            if len(note) > 190:
                st = {"open": False}
                tg = tk.Label(inner, text="Leer la nota ▾", font=ui.tkf(9, True, False), fg=self.hexm(ui.acc), bg=bg, cursor="hand2")
                tg.pack(anchor="w", pady=(2, 0))

                def flip(nl=nl, tg=tg, st=st, note=note, short=short):
                    st["open"] = not st["open"]
                    nl.configure(text=note if st["open"] else short)
                    tg.configure(text="Plegar ▴" if st["open"] else "Leer la nota ▾")
                tg.bind("<Button-1>", lambda ev, f=flip: f())
        for b in e["blocks"]:
            tk.Frame(inner, height=1, bg=self.hexm("border")).pack(fill="x", pady=(9, 5))
            if b["title"]:
                self.block_title(inner, b["title"], bg)
            for ln in b["lines"]:
                row = tk.Frame(inner, bg=bg)
                row.pack(fill="x", pady=1)
                self.line_in(row, ln, wrap, card_bg="card2")

    def reg_wrap(self, lab, host, frac=1.0):
        """Anota una etiqueta para ajustar sus saltos de línea al ancho real de su contenedor, UNA vez, cuando ya está colocado (`settle`).
        No se engancha a «Configure»: con columnas que se reparten el ancho, eso oscilaba sin fin."""
        self._wraps.append((lab, host, frac))

    def settle(self, last=True):
        pend = self._wraps
        if last:
            self._wraps = []
        try:
            self.ui.root.update_idletasks()   # que el ancho que se lea ya sea el definitivo
        except Exception:
            pass
        for lab, host, frac in pend:
            try:
                if lab.winfo_exists() and host.winfo_exists():
                    w = host.winfo_width()
                    if w > 60:
                        lab.configure(wraplength=max(80, int(w * frac - (30 if frac < 1 else 6))))
            except Exception:
                pass

    def block_title(self, parent, title, bg):
        ui = self.ui
        m = re.match(r"^(Pasiva|P|Q|W|E|R)\s*[-–—]\s*(.+)$", title)
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=(0, 3))
        if m:
            key = "P" if m.group(1).lower().startswith("p") else m.group(1)
            tk.Label(row, text=key, font=ui.tkf(10, True, False), fg=self.hexm(ON_FILL), bg=self.hexm(ui.acc), width=2).pack(side="left", padx=(0, 8))
            name = m.group(2)
        else:
            tk.Label(row, text="≡", font=ui.tkf(10, True, False), fg=self.hexm("dim"), bg=self.hexm("well"), width=2).pack(side="left", padx=(0, 8))
            name = title
        tk.Label(row, text=name, font=ui.tkf(11, True, False), fg=self.hexm("fg"), bg=bg, anchor="w").pack(side="left")

    def line_in(self, row, ln, wrap, card_bg="card2"):
        """Una línea de cambio: «Etiqueta   antes → después» con el número nuevo en el color del veredicto; si no es numérica, el texto tal cual."""
        ui = self.ui
        bg = self.hexm(card_bg)
        w = int(wrap * ui.scale_px())
        if ln["before"] and ln["after"] and ARROW_OK(ln):
            col = {1: "good", -1: "bad", 0: "fg"}[ln["trend"]]
            if ln["label"]:
                lb = tk.Label(row, text=ln["label"], font=ui.tkf(10, False, False), fg=self.hexm("dim"), bg=bg, anchor="w", justify="left", wraplength=w)
                lb.pack(anchor="w", fill="x")
                self.reg_wrap(lb, row)
            if len(ln["before"]) + len(ln["after"]) > 38:   # largas: antes (atenuado) y debajo el nuevo valor, sin flecha lateral
                b1 = tk.Label(row, text=ln["before"], font=ui.tkf(10, False, False), fg=self.hexm("dim"), bg=bg, anchor="w", justify="left", wraplength=w)
                b1.pack(anchor="w", fill="x")
                b2 = tk.Label(row, text="→  " + ln["after"], font=ui.tkf(11, True, False), fg=self.hexm(col), bg=bg, anchor="w", justify="left", wraplength=w)
                b2.pack(anchor="w", fill="x")
                self.reg_wrap(b1, row)
                self.reg_wrap(b2, row)
                return
            line = tk.Frame(row, bg=bg)
            line.pack(anchor="w", fill="x")
            b1 = tk.Label(line, text=ln["before"], font=ui.tkf(11, False, False), fg=self.hexm("dim"), bg=bg, anchor="w", justify="left", wraplength=int(w * 0.44))
            b1.pack(side="left", anchor="n")
            tk.Label(line, text="  →  ", font=ui.tkf(11, True, False), fg=self.hexm("dim"), bg=bg).pack(side="left", anchor="n")
            b2 = tk.Label(line, text=ln["after"], font=ui.tkf(11, True, False), fg=self.hexm(col), bg=bg, anchor="w", justify="left", wraplength=int(w * 0.44))
            b2.pack(side="left", anchor="n")

            self.reg_wrap(b1, line, 0.45)
            self.reg_wrap(b2, line, 0.45)
            return
        tx = tk.Label(row, text=ln["text"], font=ui.tkf(11, False, False), fg=self.hexm("fg"), bg=bg, anchor="w", justify="left", wraplength=w)
        tx.pack(anchor="w", fill="x")
        self.reg_wrap(tx, row)

    # ------------------------------------------------------------ pestaña Estadísticas
    def stats_tab(self, v):
        ui = self.ui
        st = self.want_stats(v)
        if st == "cargando":
            self.msg("Descargando las estadísticas del parche (Lolalytics)…")
            return
        if isinstance(st, tuple):
            self.msg("No se han podido leer las estadísticas ahora mismo. Se reintenta solo en un par de minutos.", "warn")
            self.retry_later(125000)
            return
        cur, prev = st["cur"], st["prev"]
        if not cur:
            self.msg(f"Lolalytics aún no tiene partidas del parche {v}. Suelen aparecer a las pocas horas de salir el parche; se vuelve a mirar solo cada 10 minutos.")
            self.retry_later(610000)
            return
        rel, warn = parche_stats.reliability(cur, prev)
        self.st_data = (cur, prev, rel)
        tier_name = metamod.TIER_NAMES.get(self.tier(), self.tier())
        c = ui.card(self.content)
        row = ui.frame(c)
        row.pack(fill="x")
        left = ui.frame(row)
        left.pack(side="left", fill="x", expand=True)
        self.label(left, f"{parche_stats.summary_line(cur, prev)}", 12, "fg", True).pack(anchor="w")
        self.label(left, f"Partidas clasificatorias en solitario · {tier_name}, según tu rango · fuente: Lolalytics · se compara con el parche {st.get('pv') or '—'}",
                   9, "dim", wrap=max(260, self.width - 200)).pack(anchor="w", pady=(2, 0))
        if warn:
            w = tk.Frame(c, bg=self.hexm("well"))
            w.pack(fill="x", pady=(10, 0))
            tk.Frame(w, width=4, bg=self.hexm("warn")).pack(side="left", fill="y")
            tk.Label(w, text=warn, font=ui.tkf(10, False, False), fg=self.hexm("warn"), bg=self.hexm("well"), justify="left", anchor="w",
                     wraplength=int((self.width - 170) * ui.scale_px())).pack(side="left", padx=10, pady=8, fill="x")
        if not prev:
            self.label(c, f"Sin datos del parche anterior: se enseña el estado actual pero no se pueden calcular cambios.", 10, "dim").pack(anchor="w", pady=(8, 0))
        # filtros
        card = ui.card(self.content)
        lanes = [("all", "Todas las líneas")] + [(k, parche_stats.LANE_ES[k]) for k in parche_stats.LANES]
        r1 = self.pill_row(card, lanes, self.lane, self.set_lane, "lane")
        r1.pack(side="left", anchor="w")
        ui.reg("parche.lineas", r1)
        tail = ui.frame(card)
        tail.pack(side="right")
        if self.mine():
            tg = self.pill(tail, "Solo mis campeones", self.only_mine, lambda: None)
            tg.pack(side="left", padx=(0, 8))
            tg.bind("<Button-1>", lambda e, t=tg: (self.flip_mine_stats(t)))
        self.stats_host = ui.frame(self.content)
        self.stats_host.pack(fill="x")
        self.render_stats()

    def flip_mine_stats(self, lab):
        self.only_mine = not self.only_mine
        lab._on = self.only_mine
        lab.configure(bg=self.hexm(self.ui.acc) if self.only_mine else self.hexm("well"), fg=self.hexm(ON_FILL) if self.only_mine else self.hexm("fg"))
        self.render_stats()

    def set_lane(self, k):
        self.lane = k
        self.render_stats()

    def render_stats(self):
        ui = self.ui
        self._tok += 1
        host = self.stats_host
        ui.clear(host)
        cur, prev, rel = self.st_data
        rows = parche_stats.compare(cur, prev)
        only = self.mine() if self.only_mine else None
        lane = None if self.lane == "all" else self.lane
        rk = parche_stats.rankings(rows, lane=lane, only=only, n=6, scale=rel)
        wid = max(280, (self.width - 150) / (2 if self.width >= 900 else 1))
        grid = ui.frame(host)
        grid.pack(fill="x", padx=8)
        cards = [
            ("SUBEN EN VICTORIAS", rk["wr_up"], "wr", "good", "Solo cambios que superan el margen de error"),
            ("BAJAN EN VICTORIAS", rk["wr_dn"], "wr", "bad", "Solo cambios que superan el margen de error"),
            ("SUBEN EN USO", rk["pr_up"], "pr", "info", "Puntos de uso en su línea"),
            ("BAJAN EN USO", rk["pr_dn"], "pr", "warn", "Puntos de uso en su línea"),
            ("LOS MÁS BANEADOS", rk["bans"], "br", "fg", "Porcentaje de partidas en que se banea"),
            ("MÁS BANEADOS QUE ANTES", rk["ban_up"], "bru", "warn", "Subida del baneo frente al parche anterior"),
        ]
        cols = 2 if self.width >= 900 else 1
        colf = []
        for i in range(cols):
            f = ui.frame(grid)
            f.pack(side="left", fill="both", expand=True, anchor="n", padx=(0, 8) if i < cols - 1 else 0)
            colf.append(f)
        for i, (title, data, kind, color, note) in enumerate(cards):
            if not prev and kind in ("wr", "pr", "bru"):
                continue
            self.stat_card(colf[i % cols], title, data, kind, color, note, wid)
        # evolución dentro del parche en curso (solo si LOL-E guardó fotos de varios días)
        if self.current() == (self.versions[0] if self.versions else None):
            mv, d0, d1 = parche_stats.movers(parche_stats.days(core.CACHE, self.current(), self.tier()), lane=lane, only=only)
            if mv:
                fmt = lambda d: f"{int(d[8:10])}/{int(d[5:7])}"
                wid2 = max(280, self.width - 150)
                one = ui.frame(host)
                one.pack(fill="x", padx=8)
                self.stat_card(one, "EVOLUCIÓN DENTRO DEL PARCHE", mv, "wr", None, f"Victorias del {fmt(d0)} al {fmt(d1)}: solo cambios que superan el margen de error", wid2)
        # cambios de línea
        if prev:
            shifts = parche_stats.lane_shifts(rows, lane=lane, only=only)
            if shifts:
                self.shift_card(host, shifts)
            # efecto de las notas
            d = self.notes.get(self.current())
            if isinstance(d, dict):
                self.effects_card(host, rows, d, only, lane)
            elif d is None:
                self.want_notes(self.current())

    def stat_card(self, parent, title, data, kind, color, note, wid):
        ui = self.ui
        bg = self.hexm("card2")
        outer = tk.Frame(parent, bg=ui.bg(parent))
        outer.pack(fill="x", pady=(0, 8))
        card = tk.Frame(outer, bg=bg, highlightthickness=1, highlightbackground=self.hexm(ui.edge_color()))
        card.pack(fill="x")
        inner = tk.Frame(card, bg=bg)
        inner.pack(fill="x", padx=14, pady=12)
        tk.Label(inner, text=title, font=ui.tkf(9, True, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w")
        tk.Label(inner, text=note, font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w", pady=(0, 6))
        if not data:
            tk.Label(inner, text="Nada destacable con los filtros actuales.", font=ui.tkf(10, False, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w", pady=4)
            return
        for r in data:
            self.stat_row(inner, r, kind, color or ("good" if (r.get("dwr") or 0) > 0 else "bad"), bg)

    def stat_row(self, parent, r, kind, color, bg):
        ui = self.ui
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=4)
        ph = ui.champ_photo(r["cid"], 32)
        ic = tk.Label(row, image=ph, bd=0, bg=bg) if ph is not None else tk.Frame(row, width=int(32 * ui.scale_px()), height=int(32 * ui.scale_px()), bg=self.hexm("well"))
        ic.image = ph
        ic.pack(side="left", padx=(0, 10))
        mid = tk.Frame(row, bg=bg)
        mid.pack(side="left", fill="x", expand=True)
        top = tk.Frame(mid, bg=bg)
        top.pack(anchor="w")
        tk.Label(top, text=core.name(r["cid"], ui.champs), font=ui.tkf(11, True, False), fg=self.hexm("fg"), bg=bg).pack(side="left")
        tk.Label(top, text="  " + parche_stats.LANE_ES.get(r["lane"], r["lane"]), font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg).pack(side="left")
        if kind == "wr":
            big, sub = es_num(r["dwr"], 1, True) + " pts", f"{es_num(r['wr0'])} % → {es_num(r['wr'])} %  ·  {es_int(r['games'])} partidas"
        elif kind == "pr":
            big, sub = es_num(r["dpr"], 1, True) + " pts", f"uso {es_num(r['pr0'])} % → {es_num(r['pr'])} %  ·  victorias {es_num(r['wr'])} %"
        elif kind == "br":
            big, sub = es_num(r["br"]) + " %", (f"{es_num(r['dbr'], 1, True)} pts frente al anterior" if r["dbr"] is not None else "") + f"  ·  victorias {es_num(r['wr'])} %"
        else:
            big, sub = es_num(r["dbr"], 1, True) + " pts", f"baneo {es_num(r['br0'])} % → {es_num(r['br'])} %"
        tk.Label(mid, text=sub, font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w")
        tk.Label(row, text=big, font=ui.tkf(14, True, True), fg=self.hexm(color), bg=bg).pack(side="right", padx=(8, 0))

    def shift_card(self, host, shifts):
        ui = self.ui
        bg = self.hexm("card2")
        outer = tk.Frame(host, bg=ui.bg(host))
        outer.pack(fill="x", padx=8, pady=(0, 8))
        card = tk.Frame(outer, bg=bg, highlightthickness=1, highlightbackground=self.hexm(ui.edge_color()))
        card.pack(fill="x")
        inner = tk.Frame(card, bg=bg)
        inner.pack(fill="x", padx=14, pady=12)
        tk.Label(inner, text="CAMPEONES QUE CAMBIAN DE SITIO", font=ui.tkf(9, True, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w")
        tk.Label(inner, text="Cambia el reparto de las partidas de un campeón entre líneas (parche anterior → este)", font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w", pady=(0, 6))
        cols = 2 if self.width >= 900 else 1
        g = tk.Frame(inner, bg=bg)
        g.pack(fill="x")
        for i in range(cols):
            g.columnconfigure(i, weight=1, uniform="sh")
        for i, s in enumerate(shifts[:8]):
            cell = tk.Frame(g, bg=bg)
            cell.grid(row=i // cols, column=i % cols, sticky="ew", pady=4, padx=(0, 10))
            ph = ui.champ_photo(s["cid"], 32)
            ic = tk.Label(cell, image=ph, bd=0, bg=bg) if ph is not None else tk.Frame(cell, width=int(32 * ui.scale_px()), height=int(32 * ui.scale_px()), bg=self.hexm("well"))
            ic.image = ph
            ic.pack(side="left", padx=(0, 10))
            mid = tk.Frame(cell, bg=bg)
            mid.pack(side="left")
            tk.Label(mid, text=core.name(s["cid"], ui.champs), font=ui.tkf(11, True, False), fg=self.hexm("fg"), bg=bg).pack(anchor="w")
            lane = parche_stats.LANE_ES.get(s["lane"], s["lane"])
            txt = (f"Pasa a jugarse sobre todo en {lane.lower()} ({es_num(s['share0'], 0)} % → {es_num(s['share'], 0)} %)" if s["kind"] == "main"
                   else f"{lane}: {es_num(s['share0'], 0)} % → {es_num(s['share'], 0)} % de sus partidas")
            tk.Label(mid, text=txt, font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg, justify="left", anchor="w").pack(anchor="w")
            tk.Label(cell, text=es_num(s["dshare"], 0, True) + " pts", font=ui.tkf(12, True, True), fg=self.hexm("info" if s["dshare"] > 0 else "warn"), bg=bg).pack(side="right", padx=(8, 0))

    def effects_card(self, host, rows, d, only, lane):
        """Qué ha pasado con los campeones que tocaron las notas: veredicto de Riot (estimado) frente a la variación real de su línea principal."""
        ui = self.ui
        eff = parche_stats.note_effects(parche.changes(d), rows, parche_stats.champion_index(ui.champs))
        eff = [e for e in eff if (only is None or e["cid"] in only) and (lane is None or e["lane"] == lane)]
        if not eff:
            return
        bg = self.hexm("card2")
        outer = tk.Frame(host, bg=ui.bg(host))
        outer.pack(fill="x", padx=8, pady=(0, 8))
        card = tk.Frame(outer, bg=bg, highlightthickness=1, highlightbackground=self.hexm(ui.edge_color()))
        card.pack(fill="x")
        inner = tk.Frame(card, bg=bg)
        inner.pack(fill="x", padx=14, pady=12)
        tk.Label(inner, text="EFECTO DE LOS CAMBIOS DE LAS NOTAS", font=ui.tkf(9, True, False), fg=self.hexm("dim"), bg=bg).pack(anchor="w")
        tk.Label(inner, text="Campeones tocados en este parche y cómo se mueve su línea principal. Una mejora que sube o una debilitación que baja es lo esperado; "
                             "con pocas partidas puede ser solo ruido.", font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg, justify="left", anchor="w",
                 wraplength=int((self.width - 190) * ui.scale_px())).pack(anchor="w", pady=(0, 8))
        head = tk.Frame(inner, bg=bg)
        head.pack(fill="x")
        for text, w in (("Campeón", 0), ("Nota", 14), ("Victorias", 11), ("Uso", 9), ("Partidas", 9), ("", 3)):
            pass
        for e in eff:
            row = tk.Frame(inner, bg=bg)
            row.pack(fill="x", pady=3)
            ph = ui.champ_photo(e["cid"], 28)
            ic = tk.Label(row, image=ph, bd=0, bg=bg) if ph is not None else tk.Frame(row, width=int(28 * ui.scale_px()), height=int(28 * ui.scale_px()), bg=self.hexm("well"))
            ic.image = ph
            ic.pack(side="left", padx=(0, 10))
            tk.Label(row, text=core.name(e["cid"], ui.champs), font=ui.tkf(11, True, False), fg=self.hexm("fg"), bg=bg, width=14, anchor="w").pack(side="left")
            vk, vcol = VERDICT.get(e["verdict"], VERDICT["adjust"])
            tk.Label(row, text=vk, font=ui.tkf(10, True, False), fg=self.hexm(vcol), bg=bg, width=15, anchor="w").pack(side="left")
            tk.Label(row, text=parche_stats.LANE_ES.get(e["lane"], e["lane"]), font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg, width=9, anchor="w").pack(side="left")
            dw = e["dwr"]
            tk.Label(row, text=("victorias " + es_num(dw, 1, True) + " pts") if dw is not None else "—", font=ui.tkf(10, True, False),
                     fg=self.hexm("good" if (dw or 0) > 0.3 else "bad" if (dw or 0) < -0.3 else "dim"), bg=bg, width=20, anchor="w").pack(side="left")
            tk.Label(row, text=("uso " + es_num(e["dpr"], 1, True) + " pts") if e["dpr"] is not None else "", font=ui.tkf(10, False, False), fg=self.hexm("dim"), bg=bg, width=14, anchor="w").pack(side="left")
            tk.Label(row, text=f"{es_int(e['games'])} partidas", font=ui.tkf(9, False, False), fg=self.hexm("dim"), bg=bg, anchor="w").pack(side="left", padx=(0, 10))
            ex = e["expected"]
            mark, mcol, tip = (("✔", "good", "El cambio de victorias va en el sentido de la nota") if ex else
                               ("✖", "bad", "El cambio de victorias va al revés de lo que decía la nota") if ex is False else ("·", "dim", "Sin conclusión: cambio pequeño o nota con efectos mezclados"))
            m = tk.Label(row, text=mark, font=ui.tkf(12, True, False), fg=self.hexm(mcol), bg=bg)
            m.pack(side="right")
            ui.tip(m, tip)


def ARROW_OK(ln):
    """¿Se puede enseñar el cambio como «antes → después»? Solo si hay una flecha única (si no, el texto completo es más fiel)."""
    return ln["text"].count("⇒") == 1


def patch_chip(ui, parent, cid, bg=None):
    """Una línea pequeña «Tocado en el parche 26.22 · ▲ Mejora» para el campeón `cid`, o None si las últimas notas guardadas no lo tocan. No usa red."""
    if not parche.ACTIVO:
        return None
    info = parche.latest_effect(core.CACHE, ui.champs).get(cid)
    if not info:
        return None
    vk, vcol = VERDICT.get(info["verdict"], VERDICT["adjust"])
    row = tk.Frame(parent, bg=bg or ui.bg(parent))
    tk.Label(row, text=f"Parche {info['v']}: ", font=ui.tkf(10, False, False), fg=ui.hexm(PAL["dim"]), bg=row.cget("bg")).pack(side="left")
    tk.Label(row, text=vk, font=ui.tkf(10, True, False), fg=ui.hexm(PAL[vcol]), bg=row.cget("bg")).pack(side="left")
    if info["text"]:
        ui.tip(row, info["text"])
        for w in row.winfo_children():
            ui.tip(w, info["text"])
    return row
