"""Barra de navegación lateral (prototipo v3): una columna de iconos que, con la ventana ancha, muestra también el nombre. Sustituye a las pestañas de arriba.

Mantiene la misma interfaz que el selector segmentado que reemplaza (`get`, `set`), de modo que el resto de la ventana no cambia. «Partida» pasa a llamarse
«En vivo» y se tiñe de ámbar mientras hay cola, selección o partida: es la señal de que la app está en modo juego. Los iconos se dibujan aquí (líneas
simples, del mismo grosor) para que todos midan lo mismo y los nombres queden alineados."""
import math

import customtkinter as ctk
from PIL import Image, ImageDraw

from ui_kit import PAL, hexc, rgb

# (clave de la página, icono, nombre en la barra, nombre en modo en vivo)
ITEMS = [("Asesor", "home", "Inicio", None), ("Partida", "live", "Partida", "En vivo"), ("Enfrentamiento", "swords", "Enfrentamiento", None),
         ("Repertorio", "star", "Campeones", None), ("Historial", "list", "Historial", None), ("Parche", "doc", "Parche", None)]


def icon(kind, color, size=22, dot=None):
    """Un icono de línea de `size` px lógicos dibujado a 8x (suave) con el color dado (tupla RGB)."""
    S = size * 8
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = int(S * .085)
    c = tuple(color) + (255,)
    p = lambda x, y: (S * x, S * y)
    if kind == "home":
        d.line([p(.12, .50), p(.50, .15), p(.88, .50)], fill=c, width=w, joint="curve")
        d.line([p(.22, .46), p(.22, .84), p(.78, .84), p(.78, .46)], fill=c, width=w, joint="curve")
        d.rectangle((S * .43, S * .56, S * .57, S * .84), outline=c, width=w)
    elif kind == "live":
        d.ellipse((S * .10, S * .10, S * .90, S * .90), outline=c, width=w)
        d.ellipse((S * .33, S * .33, S * .67, S * .67), fill=c)
    elif kind == "swords":
        d.line([p(.16, .84), p(.80, .20)], fill=c, width=w)
        d.line([p(.84, .84), p(.20, .20)], fill=c, width=w)
        d.line([p(.12, .66), p(.34, .88)], fill=c, width=w)
        d.line([p(.88, .66), p(.66, .88)], fill=c, width=w)
    elif kind == "star":
        pts = []
        for i in range(10):
            r = .42 if i % 2 == 0 else .18
            a = -math.pi / 2 + i * math.pi / 5
            pts.append(p(.5 + r * math.cos(a), .54 + r * math.sin(a)))
        d.polygon(pts, outline=c, width=w)
    elif kind == "doc":   # una hoja con la esquina doblada y tres renglones
        d.line([p(.22, .10), p(.60, .10), p(.80, .30), p(.80, .90), p(.22, .90), p(.22, .10)], fill=c, width=w, joint="curve")
        d.line([p(.60, .10), p(.60, .30), p(.80, .30)], fill=c, width=w, joint="curve")
        for y in (.50, .64, .78):
            d.line([p(.34, y), p(.68, y)], fill=c, width=w)
    else:   # list
        for y in (.26, .50, .74):
            d.line([p(.14, y), p(.86, y)], fill=c, width=w)
    if dot:   # punto de aviso arriba a la derecha (un parche nuevo sin mirar)
        d.ellipse((S * .62, S * .02, S * .98, S * .38), fill=tuple(dot) + (255,))
    return im.resize((size * 2, size * 2), Image.LANCZOS)


class RailNav:
    def __init__(self, kit, parent, command, current=""):
        self.k, self.cmd, self.cur = kit, command, current
        self.expanded, self.live = False, False
        self.badges = set()   # claves con punto de aviso
        self.cache = {}
        self.frame = kit.frame(parent)
        self.btns = {}
        for key, kind, label, live_label in ITEMS:
            b = ctk.CTkButton(self.frame, text="", width=44, height=40, corner_radius=10, font=kit.font(13), fg_color="transparent", compound="left",
                              hover_color=PAL["card2"], text_color=PAL["dim"], border_width=1, border_color=PAL["bg"], anchor="center",
                              command=lambda n=key: self.cmd(n))
            b.pack(pady=2)
            kit.tip(b, label)
            self.btns[key] = b
        self.paint()

    def image(self, kind, color, dot=False):
        """El icono en los dos temas (CustomTkinter elige solo). Con `dot`, lleva el punto de aviso."""
        key = (kind, color, dot)
        if key not in self.cache:
            imgs = [icon(kind, rgb(hexc(color, dark)), dot=rgb(hexc("warn", dark)) if dot else None) for dark in (False, True)]
            self.cache[key] = ctk.CTkImage(light_image=imgs[0], dark_image=imgs[1], size=(22, 22))
        return self.cache[key]

    # ---- interfaz del selector que sustituye ----
    def get(self):
        return self.cur

    def set(self, name):
        self.cur = name
        self.paint()

    # ---- estado ----
    def set_expanded(self, on):
        if on != self.expanded:
            self.expanded = on
            self.paint()

    def set_badge(self, key, on):
        if (key in self.badges) != on:
            (self.badges.add if on else self.badges.discard)(key)
            self.paint()

    def set_live(self, on):
        if on != self.live:
            self.live = on
            self.paint()

    def paint(self):
        k = self.k
        for key, kind, label, live_label in ITEMS:
            b = self.btns[key]
            name = live_label if (self.live and live_label) else label
            on = key == self.cur
            hot = self.live and live_label is not None
            tone = "warn" if hot else "fg" if on else "dim"
            b.configure(text=f"  {name}" if self.expanded else "", image=self.image(kind, tone, key in self.badges), width=164 if self.expanded else 44,
                        anchor="w" if self.expanded else "center", fg_color=PAL["card2"] if on else "transparent", text_color=PAL[tone],
                        border_color=(PAL["warn"] if hot else k.acc) if on else PAL["bg"])
