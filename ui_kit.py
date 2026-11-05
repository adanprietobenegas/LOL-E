"""Piezas comunes de la interfaz de LOL-E: paleta, dibujo (anillos, tarjeta principal), imágenes y widgets base.

Todo lo que cuesta (imágenes, tarjetas con arte) se guarda en memoria para no repetirlo al redimensionar o cambiar de pestaña.
"""
import math, os, sys, threading, tkinter as tk, tkinter.font as tkfont, urllib.request

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk

import lol_advisor as core
from lol_advisor import CACHE, name, why_kind

# colores como (modo claro, modo oscuro): CustomTkinter elige solo según el tema activo
PAL = {
    "bg": ("#eef1f5", "#070d14"), "card": ("#ffffff", "#0e161f"), "card2": ("#e9edf3", "#141e2a"),
    "border": ("#d5dce6", "#1f2c3b"), "fg": ("#142033", "#ece6d6"), "dim": ("#5b6b80", "#8896a8"),
    "good": ("#15803d", "#3ddc84"), "bad": ("#dc2626", "#ff5a5f"), "info": ("#2563eb", "#58a6ff"),
    "warn": ("#b45309", "#ff9f43"), "chip": ("#e2e8f0", "#1a2634"),
}
ACCENTS = {"Dorado": ("#8a6a2f", "#c8aa6e"), "Azul": ("#2563eb", "#58a6ff"), "Verde": ("#15803d", "#3ddc84"),
           "Morado": ("#7c3aed", "#a78bfa"), "Rojo": ("#dc2626", "#ff6b6b"), "Cian": ("#0e7490", "#22d3ee")}
THEMES = {"Oscuro": "dark", "Claro": "light", "Sistema": "system"}
PHASES = {"PLANNING": "Planificación", "BAN_PICK": "Bans y picks", "FINALIZATION": "Últimos retoques",
          "GAME_STARTING": "Empezando la partida"}
ROLES_ES = {"TOP": "Superior", "JUNGLE": "Jungla", "MIDDLE": "Central", "BOTTOM": "Tirador", "SUPPORT": "Apoyo"}
TIER_COLORS = {"IRON": "#9a9a9a", "BRONZE": "#c0804a", "SILVER": "#b4c2d0", "GOLD": "#e8bd4e", "PLATINUM": "#4fc0b0",
               "EMERALD": "#3ddc84", "DIAMOND": "#6a9bff", "MASTER": "#c06bff", "GRANDMASTER": "#ff6b6b", "CHALLENGER": "#ffd86b"}
ON_FILL = ("#ffffff", "#07101a")
DISPLAY, BODY = "Chakra Petch", "Segoe UI"


def res(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", *parts)


def col(c):
    return PAL[c] if isinstance(c, str) and c in PAL else c


def hexc(c, dark):
    c = col(c)
    return c[1 if dark else 0] if isinstance(c, tuple) else c


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def partidas(n):
    return f"{n} partida" if n == 1 else f"{n} partidas"


def pct_es(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def pil_font(weight, size):
    f = {"bold": "ChakraPetch-Bold.ttf", "semi": "ChakraPetch-SemiBold.ttf", "med": "ChakraPetch-Medium.ttf"}[weight]
    try:
        return ImageFont.truetype(res("fonts", f), size)
    except Exception:
        return ImageFont.load_default()


def ring_image(frac, size, text, fill, track, ink, font_ratio=.36, thick=.11):
    """Anillo de progreso con un número en el centro, dibujado a 4x para que quede suave."""
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = int(S * thick)
    box = (w // 2, w // 2, S - w // 2 - 1, S - w // 2 - 1)
    d.arc(box, 0, 360, fill=track, width=w)
    if frac > 0.004:
        d.arc(box, -90, -90 + 360 * min(frac, 1), fill=fill, width=w)
    if text:
        d.text((S / 2, S / 2 + S * .01), text, font=pil_font("bold", int(S * font_ratio)), fill=ink, anchor="mm")
    return im.resize((size, size), Image.LANCZOS)


def make_hero(art_path, title, eyebrow, pct, w, h, accent, label="AFINIDAD"):
    """La pieza propia del producto: el arte del campeón recomendado con su afinidad en un anillo."""
    S = 2
    W, H = w * S, h * S
    if art_path and os.path.exists(art_path):
        im = Image.open(art_path).convert("RGB")
        iw, ih = im.size
        cw, ch = iw, int(iw * H / W)
        if ch > ih:
            ch, cw = ih, int(ih * W / H)
        x0 = max(0, min(iw - cw, int(iw * .60) - cw // 2))
        y0 = max(0, min(ih - ch, int(ih * .10)))
        im = im.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.LANCZOS)
    else:
        im = Image.new("RGB", (W, H), (16, 26, 38))
    im = im.convert("RGBA")
    gx = ImageOps.invert(Image.linear_gradient("L").rotate(90, expand=True).resize((W, H)))
    ov = Image.new("RGBA", (W, H), (5, 10, 16, 255))
    ov.putalpha(gx.point(lambda v: int(min(255, v * 1.15) * .93)))
    im.alpha_composite(ov)
    bot = Image.new("RGBA", (W, H), (5, 10, 16, 255))
    bot.putalpha(Image.linear_gradient("L").resize((W, H)).point(lambda v: int(v * .55)))
    im.alpha_composite(bot)
    d = ImageDraw.Draw(im)
    d.text((24 * S, 22 * S), eyebrow.upper(), font=pil_font("med", 11 * S), fill=accent)
    size = 40
    f = pil_font("bold", size * S)
    while f.getlength(title) > W * .52 and size > 22:
        size -= 2
        f = pil_font("bold", size * S)
    d.text((24 * S, 44 * S), title, font=f, fill=(240, 232, 214))
    rs = 84
    ring = ring_image(pct / 100, rs * S, str(pct), accent, (255, 255, 255, 46), (240, 232, 214), .34, .10)
    rx, ry = W - 24 * S - rs * S, 24 * S
    im.alpha_composite(ring, (rx, ry))
    d.text((rx + rs * S / 2, ry + rs * S + 7 * S), label, font=pil_font("med", 9 * S), fill=(200, 192, 176), anchor="mt")
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=14 * S, fill=255)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out.resize((w, h), Image.LANCZOS)


def mix(a, b, t):
    """Color intermedio entre dos colores hexadecimales."""
    ca, cb = rgb(a), rgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))


def role_glyph(role, size, on, off, bg, border):
    """Icono de línea: el mapa con la línea asignada resaltada (superior, jungla, central, tirador o apoyo)."""
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * .22), fill=bg + (255,), outline=border + (255,), width=max(2, S // 40))
    p = lambda x, y: (S * x, S * y)
    m = .21
    thin, thick = int(S * .045), int(S * .10)
    lanes = {"TOP": [p(m, 1 - m), p(m, m), p(1 - m, m)], "BOTTOM": [p(m, 1 - m), p(1 - m, 1 - m), p(1 - m, m)],
             "MIDDLE": [p(m, 1 - m), p(1 - m, m)]}
    for name, pts in lanes.items():
        hot = role == name or (role == "SUPPORT" and name == "BOTTOM")
        col_, w = (on if hot else off), (thick if role == name else thin if not hot else int(S * .07))
        d.line(pts, fill=col_ + (255,), width=w, joint="curve")
    for cx, cy in ((.34, .62), (.66, .38)):  # campamentos de la jungla
        r = S * (.075 if role == "JUNGLE" else .05)
        d.polygon([(S * cx, S * cy - r), (S * cx + r, S * cy), (S * cx, S * cy + r), (S * cx - r, S * cy)],
                  fill=(on if role == "JUNGLE" else off) + (255,))
    if role == "SUPPORT":  # una cruz junto al carril inferior
        c, r = p(.7, .7), S * .07
        d.line([(c[0] - r, c[1]), (c[0] + r, c[1])], fill=on + (255,), width=int(S * .045))
        d.line([(c[0], c[1] - r), (c[0], c[1] + r)], fill=on + (255,), width=int(S * .045))
    return im.resize((size, size), Image.LANCZOS)


class Kit:
    """Estado y utilidades compartidas por todas las secciones."""

    def __init__(self, root, conf, champs, notify):
        self.root, self.conf, self.champs, self.notify = root, conf, champs, notify
        self.fonts, self.icons, self.heroes, self.fetching = {}, {}, {}, set()
        self.runedata = {}  # runas y hechizos (Data Dragon), cargados en segundo plano
        self.photos, self.pils = {}, {}  # imágenes ligeras (PhotoImage) y sus originales
        self.items = {}  # objetos del juego (id -> nombre, coste, descripción), cargados en segundo plano
        self.epoch = 0   # sube cuando cambia tema, acento o imágenes: obliga a las secciones a repintarse
        self.anim = False

    @property
    def acc(self):
        return ACCENTS.get(self.conf["accent"], ACCENTS["Dorado"])

    # ---- color efectivo y fuentes para los widgets ligeros de Tk ----
    def anim_on(self):
        return bool(self.conf.get("animations", True))

    def mode_dark(self):
        return ctk.get_appearance_mode() == "Dark"

    def hexm(self, c):
        """Color en el modo actual (los widgets ligeros no cambian solos al cambiar de tema)."""
        return hexc(c, self.mode_dark())

    def bg(self, w):
        """Color de fondo real de un contenedor, subiendo por los padres mientras sean transparentes."""
        while w is not None:
            try:
                fc = w.cget("fg_color")
            except Exception:
                fc = None
                try:
                    return w.cget("bg")
                except Exception:
                    pass
            if fc not in (None, "transparent"):
                return self.hexm(fc)
            w = getattr(w, "master", None)
        return self.hexm(PAL["bg"])

    def scale_px(self):
        try:
            return ctk.ScalingTracker.get_widget_scaling(self.root)
        except Exception:
            return 1.0

    def tkf(self, size, bold, display):
        k = ("tk", size, bold, display)
        if k not in self.fonts:
            self.fonts[k] = tkfont.Font(family=DISPLAY if display else BODY, size=-max(1, round(size * self.scale_px())),
                                        weight="bold" if bold else "normal")
        return self.fonts[k]

    # ---- widgets base ----
    def font(self, size=12, bold=False, display=False):
        k = (size, bold, display)
        if k not in self.fonts:
            self.fonts[k] = ctk.CTkFont(family=DISPLAY if display else BODY, size=size, weight="bold" if bold else "normal")
        return self.fonts[k]

    def clbl(self, parent, text, size=12, color="fg", bold=False, display=False, **kw):
        """Etiqueta de CustomTkinter: cambia sola de color con el tema. Para lo que no se reconstruye (cabecera, ajustes)."""
        return ctk.CTkLabel(parent, text=text, font=self.font(size, bold, display), text_color=col(color), **kw)

    def lbl(self, parent, text, size=12, color="fg", bold=False, display=False, **kw):
        """Etiqueta ligera de Tk (mucho más rápida). Las secciones se reconstruyen al cambiar de tema, así que no hace falta más."""
        width = kw.pop("width", None)
        f = self.tkf(size, bold, display)
        wl = kw.pop("wraplength", 0)
        host = tk.Frame(parent, bg=self.bg(parent), width=int(width * self.scale_px()), height=f.metrics("linespace")) if width else None
        if host is not None:
            host.pack_propagate(False)
        lab = tk.Label(host or parent, text=text, font=f, fg=self.hexm(color), bg=self.bg(parent), bd=0, padx=0, pady=0,
                       anchor=kw.pop("anchor", "center"), justify=kw.pop("justify", "center"),
                       wraplength=int(wl * self.scale_px()) if wl else 0)
        if host is not None:
            lab.pack(fill="both", expand=True)
            return host
        return lab

    def frame(self, parent, **kw):
        """Contenedor invisible ligero. Con color propio (fg_color) o forma, se usa el de CustomTkinter."""
        if kw:
            kw.setdefault("fg_color", "transparent")
            return ctk.CTkFrame(parent, **kw)
        return tk.Frame(parent, bg=self.bg(parent))

    def card(self, parent, title=None, pad=6):
        f = ctk.CTkFrame(parent, fg_color=PAL["card"], corner_radius=14, border_width=1, border_color=PAL["border"])
        f.pack(fill="x", padx=6, pady=pad)
        inner = self.frame(f)
        inner.pack(fill="x", padx=16, pady=14)
        if title:
            self.lbl(inner, title.upper(), 10, "dim", True).pack(anchor="w", pady=(0, 8))
        return inner

    def seg(self, parent, values, current, command, **kw):
        b = ctk.CTkSegmentedButton(parent, values=values, command=command, font=self.font(11), selected_color=self.acc,
                                   selected_hover_color=self.acc, unselected_color=PAL["card2"],
                                   unselected_hover_color=PAL["border"], text_color=PAL["fg"], fg_color=PAL["card2"], **kw)
        def paint():
            cur = b.get()
            for k, btn in getattr(b, "_buttons_dict", {}).items():
                try:
                    btn.configure(text_color=ON_FILL if k == cur else PAL["fg"])
                except Exception:
                    pass
        orig_set = b.set

        def set_(v, *args, **kw):  # CustomTkinter lo llama con from_button_callback=True al pulsar un botón
            orig_set(v, *args, **kw)
            paint()
        b.set = set_

        def wrapped(v):
            paint()
            command(v)
        b.configure(command=wrapped)
        b.set(current)
        return b

    def fold(self, parent, title, build, summary="", key=None, open_=False):
        """Sección plegable: cabecera con flecha, título y un resumen a la derecha. El cuerpo se construye al abrirla por primera vez
        (con una animación breve) y se recuerda si estaba abierta. Devuelve el contenedor; `box.set_summary(texto)` cambia el resumen."""
        folds = self.conf.setdefault("folds", {})
        state = {"open": folds.get(key, open_) if key else open_, "outer": None}
        bgp = self.bg(parent)
        card, fg, dim = self.hexm(PAL["card2"]), self.hexm(PAL["fg"]), self.hexm(PAL["dim"])
        hover = self.hexm(PAL["border"])
        box = tk.Frame(parent, bg=bgp)
        box.pack(fill="x", pady=(0, 6), padx=6)
        head = tk.Frame(box, bg=card, cursor="hand2")
        head.pack(fill="x")
        arrow = tk.Label(head, text="▾" if state["open"] else "▸", bg=card, fg=dim, font=self.tkf(12, False, False), width=2)
        arrow.pack(side="left", padx=(10, 2), pady=7)
        ttl = tk.Label(head, text=title, bg=card, fg=fg, font=self.tkf(11, True, False), anchor="w")
        ttl.pack(side="left")
        sm = tk.Label(head, text=summary, bg=card, fg=dim, font=self.tkf(9, False, False), anchor="e")
        sm.pack(side="right", padx=12)

        def paint_open():
            if state["open"]:
                if state["outer"] is None:
                    state["outer"] = self.reveal(box, build)
                    state["outer"].pack_configure(padx=12, pady=(8, 6))
                else:
                    state["outer"].pack(fill="x", padx=12, pady=(8, 6))
            elif state["outer"] is not None:
                state["outer"].pack_forget()
            arrow.configure(text="▾" if state["open"] else "▸")

        def toggle(_e=None):
            state["open"] = not state["open"]
            if key:
                folds[key] = state["open"]
                core.save_conf(self.conf)
            paint_open()

        def tint(on):
            c = hover if on else card
            for w in (head, arrow, ttl, sm):
                w.configure(bg=c)
        for w in (head, arrow, ttl, sm):
            w.bind("<Button-1>", toggle)
            w.bind("<Enter>", lambda e: tint(True))
            w.bind("<Leave>", lambda e: tint(False))
        box.set_summary = lambda t: sm.configure(text=t)
        if state["open"]:
            paint_open()
        return box

    def menu(self, parent, values, current, command, width=130):
        m = ctk.CTkOptionMenu(parent, values=values, command=command, width=width, height=28, font=self.font(11),
                              dropdown_font=self.font(11), fg_color=PAL["card2"], button_color=PAL["border"],
                              button_hover_color=PAL["border"], text_color=PAL["fg"], dropdown_fg_color=PAL["card2"],
                              dropdown_text_color=PAL["fg"], dropdown_hover_color=PAL["border"])
        m.set(current)
        return m

    def bar(self, parent, parts, h=6, animate=False):
        """Barra con tramos [(fracción, color)…]. Con animate, crece al aparecer."""
        box = ctk.CTkFrame(parent, height=h, corner_radius=h // 2, fg_color=PAL["card2"])
        box.pack_propagate(False)
        x = 0.0
        for frac, color in parts:
            frac = max(0.0, min(1.0 - x, frac))
            if frac > 0.005:
                fill = ctk.CTkFrame(box, corner_radius=h // 2, fg_color=col(color))
                if animate and self.anim and self.anim_on():
                    fill.place(relx=x, rely=0, relwidth=0.001, relheight=1)
                    self._grow(fill, x, frac, 0)
                else:
                    fill.place(relx=x, rely=0, relwidth=frac, relheight=1)
            x += frac
        return box

    def _grow(self, w, x, target, step, n=14):
        try:
            if not w.winfo_exists():
                return
            t = 1 - (1 - (step + 1) / n) ** 3
            w.place_configure(relx=x, relwidth=max(.001, target * t))
            if step + 1 < n:
                self.root.after(16, lambda: self._grow(w, x, target, step + 1, n))
        except Exception:
            pass

    def chip(self, parent, text, color="dim"):
        c = ctk.CTkLabel(parent, text=f"  {text[:1].upper()}{text[1:]}  ", font=self.font(10), text_color=col(color), height=22,
                         fg_color=PAL["chip"], corner_radius=8)
        return c

    def chips(self, parent, items, per_row=3):
        for j in range(0, len(items), per_row):
            line = self.frame(parent)
            line.pack(anchor="w", pady=2)
            for w in items[j:j + per_row]:
                self.chip(line, w, PAL[why_kind(w)]).pack(side="left", padx=(0, 5))

    def dots(self, parent, results, size=9):
        """Resultados recientes como puntos verdes (victoria) y rojos (derrota)."""
        row = self.frame(parent)
        for w in results:
            tk.Frame(row, width=size, height=size, bg=self.hexm(PAL["good" if w else "bad"])).pack(side="left", padx=1)
        return row

    def clickable(self, w, cb):
        try:
            w.configure(cursor="hand2")
        except Exception:
            pass
        w.bind("<Button-1>", lambda e=None: cb(), add="+")
        for ch in w.winfo_children():
            self.clickable(ch, cb)

    def kpi(self, parent, value, label):
        f = self.frame(parent)
        f.pack(side="left", expand=True)
        lab = self.lbl(f, "0" if value.isdigit() and self.anim and self.anim_on() else value, 20, self.acc, True, True)
        lab.pack()
        self.lbl(f, label, 9, "dim").pack()
        if value.isdigit() and self.anim and self.anim_on():
            self.count_up(lab, int(value))

    def count_up(self, lab, target, step=0, n=12):
        """Los números suben desde 0 hasta su valor."""
        try:
            if not lab.winfo_exists():
                return
            t = 1 - (1 - (step + 1) / n) ** 3
            lab.configure(text=str(round(target * t)))
            if step + 1 < n:
                self.root.after(22, lambda: self.count_up(lab, target, step + 1, n))
        except Exception:
            pass

    def pulse(self, w, c1, c2, n=6, step=0):
        """Parpadeo suave del color de una etiqueta (por ejemplo el punto de «te toca»)."""
        try:
            if not w.winfo_exists():
                return
            w.configure(fg=c2 if step % 2 == 0 and step < n else c1)
            if step < n:
                self.root.after(380, lambda: self.pulse(w, c1, c2, n, step + 1))
        except Exception:
            pass

    def smooth_btn(self, btn, base, hover, ms=14):
        """Transición suave de color al pasar el ratón (en vez del salto brusco)."""
        st = {"t": 0.0, "goal": 0.0, "run": False}

        def tick():
            st["t"] += (st["goal"] - st["t"]) * 0.45
            done = abs(st["goal"] - st["t"]) < 0.03
            if done:
                st["t"], st["run"] = st["goal"], False
            try:
                btn.configure(fg_color=base if (done and st["goal"] == 0) else mix(self.hexm(base), self.hexm(hover), st["t"]))
            except Exception:
                st["run"] = False
                return
            if not done:
                self.root.after(ms, tick)

        def go(goal):
            st["goal"] = goal
            if self.anim_on() and not st["run"]:
                st["run"] = True
                tick()
            elif not self.anim_on():
                btn.configure(fg_color=hover if goal else base)
        btn.bind("<Enter>", lambda e: go(1.0), add="+")
        btn.bind("<Leave>", lambda e: go(0.0), add="+")

    def role_icon(self, role, size):
        key = ("role", role, size, self.conf["accent"])
        if key not in self.icons:
            imgs = [role_glyph(role, size * 2, rgb(hexc(self.acc, d)), rgb(hexc("dim", d)), rgb(hexc("card2", d)),
                               rgb(hexc("border", d))) for d in (False, True)]
            self.icons[key] = ctk.CTkImage(light_image=imgs[0], dark_image=imgs[1], size=(size, size))
        return self.icons[key]

    def pct(self, score, scale):
        return round(min(max(score, 0) / max(scale, 1), 1) * 100)

    # ---- imágenes ----
    def fetch(self, url, path, event="assets"):
        """Descarga en segundo plano (una vez) y avisa a la ventana al terminar."""
        if path in self.fetching:
            return
        self.fetching.add(path)

        def go():
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; LOL-E)"})
                with urllib.request.urlopen(req, timeout=25) as r, open(path + ".tmp", "wb") as f:
                    f.write(r.read())
                os.replace(path + ".tmp", path)
                self.notify(event)
            except Exception:
                pass
        threading.Thread(target=go, daemon=True).start()

    def icon(self, cid, size, border=None):
        key = (cid, size, border)
        if key in self.icons:
            return self.icons[key]
        c = self.champs.get(cid)
        path = os.path.join(CACHE, "icons", f"{c['icon']}.png") if c and c.get("icon") else ""
        if not (path and os.path.exists(path)):
            return None
        try:
            S = size * 2
            im = Image.open(path).convert("RGBA").crop((6, 6, 114, 114)).resize((S, S), Image.LANCZOS)
            mask = Image.new("L", (S, S), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * .22), fill=255)
            out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            out.paste(im, (0, 0), mask)
            if border:
                ImageDraw.Draw(out).rounded_rectangle((1, 1, S - 2, S - 2), radius=int(S * .22), outline=border, width=max(3, S // 20))
            img = ctk.CTkImage(light_image=out, dark_image=out, size=(size, size))
            self.icons[key] = img
            self.pils[("c",) + key] = out
            return img
        except Exception:
            return None

    def _photo(self, key, pil, size):
        """PhotoImage al tamaño real en píxeles (con la escala de la ventana), guardado en memoria."""
        k = key + (size,)
        ph = self.photos.get(k)
        if ph is None:
            px = max(1, int(round(size * self.scale_px())))
            ph = ImageTk.PhotoImage(pil.resize((px, px), Image.LANCZOS))
            self.photos[k] = ph
        return ph

    def champ_photo(self, cid, size, border=None):
        if self.icon(cid, size, border) is None:
            return None
        pil = self.pils.get(("c", cid, size, border))
        return self._photo(("c", cid, border), pil, size) if pil is not None else None

    def item_photo(self, iid, size):
        """Icono ligero de un objeto; si aún no está en disco lo descarga y devuelve None."""
        pil = self.pils.get(("i", iid))
        if pil is None:
            path = os.path.join(CACHE, "items", f"{iid}.png")
            if not os.path.exists(path):
                if core.DD_VERSION and iid:
                    self.fetch(f"https://ddragon.leagueoflegends.com/cdn/{core.DD_VERSION}/img/item/{iid}.png", path)
                return None
            try:
                pil = Image.open(path).convert("RGBA")
            except Exception:
                return None
            self.pils[("i", iid)] = pil
        return self._photo(("i", iid), pil, size)

    def item_icon(self, iid, size):
        """Icono de un objeto (Data Dragon). Si aún no está en disco se descarga y devuelve None."""
        key = ("item", iid, size)
        if key in self.icons:
            return self.icons[key]
        path = os.path.join(CACHE, "items", f"{iid}.png")
        if not os.path.exists(path):
            if core.DD_VERSION and iid:
                self.fetch(f"https://ddragon.leagueoflegends.com/cdn/{core.DD_VERSION}/img/item/{iid}.png", path)
            return None
        try:
            im = Image.open(path).convert("RGBA")
            img = ctk.CTkImage(light_image=im, dark_image=im, size=(size, size))
            self.icons[key] = img
            return img
        except Exception:
            return None

    def _icon_file(self, kind, key, url, size, ext="png"):
        k = (kind, key, size)
        if k in self.icons:
            return self.icons[k]
        path = os.path.join(CACHE, kind, f"{key}.{ext}")
        if not os.path.exists(path):
            self.fetch(url, path)
            return None
        try:
            im = Image.open(path).convert("RGBA")
            img = ctk.CTkImage(light_image=im, dark_image=im, size=(size, size))
            self.icons[k] = img
            return img
        except Exception:
            return None

    def rune_icon(self, rid, size):
        info = (self.runedata.get("runes") or {}).get(rid)
        return self._icon_file("runeicons", rid, f"https://ddragon.leagueoflegends.com/cdn/img/{info['i']}", size) if info else None

    def spell_icon(self, sid, size):
        info = (self.runedata.get("spells") or {}).get(sid)
        return self._icon_file("spellicons", sid, f"https://ddragon.leagueoflegends.com/cdn/{core.DD_VERSION}/img/spell/{info['i']}", size) if info else None

    def shard_icon(self, sid, size):
        return self._icon_file("shardicons", sid, f"https://cdn5.lolalytics.com/statmod32/{sid}.webp", size, "webp")

    def reveal(self, parent, build, steps=9):
        """Crea un panel y lo hace crecer desde cero hasta su alto (si las animaciones están activas)."""
        outer = tk.Frame(parent, bg=self.bg(parent), height=1)
        outer.pack(fill="x")
        inner = tk.Frame(outer, bg=self.bg(parent))
        build(inner)
        inner.place(x=0, y=0, relwidth=1.0)
        outer.pack_propagate(False)
        outer.update_idletasks()
        target = max(1, inner.winfo_reqheight())
        def finish():
            # terminada la animación, el panel vuelve a ajustarse solo a su contenido (así lo que se añada después no se recorta)
            if outer.winfo_exists():
                inner.place_forget()
                inner.pack(fill="x")
                outer.pack_propagate(True)

        if not self.anim_on():
            finish()
            return outer

        def step(i=1):
            if not outer.winfo_exists():
                return
            t = 1 - (1 - i / steps) ** 3
            outer.configure(height=max(1, int(target * t)))
            if i < steps:
                outer.after(14, lambda: step(i + 1))
            else:
                finish()
        step()
        return outer

    def rrect(self, cv, x1, y1, x2, y2, r, **kw):
        """Rectángulo redondeado dibujado en un lienzo."""
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(pts, smooth=True, **kw)

    def fit(self, text, font, maxw):
        """Recorta un texto con «…» para que quepa en maxw píxeles."""
        if font.measure(text) <= maxw:
            return text
        while text and font.measure(text + "…") > maxw:
            text = text[:-1]
        return text + "…"

    def canvas_tip(self, cv, item, text):
        """Globo de ayuda para un elemento dibujado en un lienzo."""
        st = {"t": None}

        def hide(_e=None):
            if st["t"] is not None:
                st["t"].destroy()
                st["t"] = None

        def show(e):
            hide()
            t = tk.Toplevel(cv)
            t.wm_overrideredirect(True)
            t.attributes("-topmost", True)
            tk.Label(t, text=text, bg=self.hexm(PAL["card2"]), fg=self.hexm(PAL["fg"]), font=self.tkf(10, False, False), bd=1, relief="solid",
                     padx=8, pady=4, justify="left").pack()
            t.geometry(f"+{e.x_root + 12}+{e.y_root + 16}")
            st["t"] = t
        cv.tag_bind(item, "<Enter>", show, add="+")
        cv.tag_bind(item, "<Leave>", hide, add="+")

    def tip(self, w, text):
        """Globo de ayuda al pasar el ratón."""
        st = {"t": None}

        def hide(_e=None):
            if st["t"] is not None:
                st["t"].destroy()
                st["t"] = None

        def show(e):
            hide()
            t = tk.Toplevel(w)
            t.wm_overrideredirect(True)
            t.attributes("-topmost", True)
            tk.Label(t, text=text, bg=self.hexm(PAL["card2"]), fg=self.hexm(PAL["fg"]), font=self.tkf(10, False, False), bd=1,
                     relief="solid", padx=8, pady=4, justify="left").pack()
            t.geometry(f"+{e.x_root + 12}+{e.y_root + 16}")
            st["t"] = t
        w.bind("<Enter>", show, add="+")
        w.bind("<Leave>", hide, add="+")
        w.bind("<Destroy>", hide, add="+")

    def champ(self, parent, cid, size, caption=True, border=None):
        f = self.frame(parent)
        ph = self.champ_photo(cid, size, border) if cid else None
        if ph is not None:
            lab = tk.Label(f, image=ph, bd=0, highlightthickness=0, bg=self.bg(parent))
            lab.image = ph
            lab.pack()
        else:
            ph = ctk.CTkFrame(f, width=size, height=size, corner_radius=int(size * .22), fg_color=PAL["card2"],
                              border_width=1, border_color=PAL["border"])
            ph.pack()
            ph.pack_propagate(False)
            self.lbl(ph, self.champs[cid]["name"][:3] if cid in self.champs else "?", max(9, size // 5), "dim", True).pack(expand=True)
        if caption:
            self.lbl(f, name(cid, self.champs)[:11], 10, "fg" if cid else "dim").pack(pady=(3, 0))
        return f

    def splash(self, cid):
        """Arte del campeón (se descarga bajo demanda). None mientras no esté."""
        c = self.champs.get(cid)
        if not c or not c.get("icon"):
            return None
        p = os.path.join(CACHE, "splash", f"{c['icon']}_0.jpg")
        if os.path.exists(p):
            return p
        self.fetch(f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{c['icon']}_0.jpg", p, "splash")
        return None

    def profile_icon(self, pid, size):
        key = ("pf", pid, size)
        if key in self.icons:
            return self.icons[key]
        p = os.path.join(CACHE, "profileicons", f"{pid}.png")
        if not os.path.exists(p):
            if core.DD_VERSION:
                self.fetch(f"https://ddragon.leagueoflegends.com/cdn/{core.DD_VERSION}/img/profileicon/{pid}.png", p)
            return None
        try:
            S = size * 2
            im = Image.open(p).convert("RGBA").resize((S, S), Image.LANCZOS)
            mask = Image.new("L", (S, S), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, S - 1, S - 1), fill=255)
            out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            out.paste(im, (0, 0), mask)
            self.icons[key] = ctk.CTkImage(light_image=out, dark_image=out, size=(size, size))
            return self.icons[key]
        except Exception:
            return None

    def emblem(self, tier_key, size):
        key = ("em", tier_key, size)
        if key in self.icons:
            return self.icons[key]
        p = os.path.join(CACHE, "emblems", f"{tier_key.lower()}.png")
        if not os.path.exists(p):
            self.fetch("https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/"
                       f"ranked-emblem/emblem-{tier_key.lower()}.png", p)
            return None
        try:
            im = Image.open(p).convert("RGBA")
            im = im.crop(im.getbbox() or (0, 0, *im.size))
            im.thumbnail((size * 2, size * 2), Image.LANCZOS)
            self.icons[key] = ctk.CTkImage(light_image=im, dark_image=im, size=(im.width // 2, im.height // 2))
            return self.icons[key]
        except Exception:
            return None

    def ring(self, frac, size, text, color):
        """Anillo en las dos versiones de tema: CustomTkinter cambia solo entre ellas."""
        imgs = [ring_image(frac, size * 2, text, rgb(hexc(color, dark)), rgb(hexc("border", dark)) + (255,),
                           rgb(hexc("fg", dark)), .34, .11) for dark in (False, True)]
        return ctk.CTkImage(light_image=imgs[0], dark_image=imgs[1], size=(size, size))

    def hero_pil(self, cid, eyebrow, pct, w, label="AFINIDAD"):
        """Tarjeta principal con el arte del campeón; se guarda en memoria para no rehacerla."""
        art = self.splash(cid)
        key = (art or "", name(cid, self.champs), eyebrow, pct, w, hexc(self.acc, True), label)
        if key not in self.heroes:
            if len(self.heroes) > 24:
                self.heroes.pop(next(iter(self.heroes)))
            self.heroes[key] = make_hero(art, name(cid, self.champs), eyebrow, pct, w, 150, rgb(hexc(self.acc, True)), label)
        return self.heroes[key]
