"""Maquetas del «resumen de 10 segundos» al acabar una partida (propuesta A5). Dibuja tres variantes con los colores de la app y los datos de una
clasificatoria real; no forma parte de la aplicación. Uso: python docs/rediseno/cierre/maquetas.py"""
import os

from PIL import Image, ImageDraw, ImageFont

D = os.path.dirname(os.path.abspath(__file__))
BG, CARD, CARD2 = "#06101f", "#111d31", "#1b2c46"
FG, DIM, GOOD, BAD, WARN, ACC, EDGE = "#f0ead8", "#94a3b8", "#3ddc84", "#ff5a5f", "#ffa14a", "#c8a96a", "#35465f"
W = 1060
S = 2   # se dibuja al doble y se reduce: bordes suaves


def font(size, bold=False):
    return ImageFont.truetype(r"C:\Windows\Fonts\%s" % ("segoeuib.ttf" if bold else "segoeui.ttf"), size * S)


class Lienzo:
    def __init__(self, h, title):
        self.h = h
        self.im = Image.new("RGB", (W * S, h * S), BG)
        self.d = ImageDraw.Draw(self.im)
        self.text(24, 14, title, 17, ACC, True)

    def box(self, x, y, w, h, fill=CARD, r=14, outline=None):
        self.d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], r * S, fill=fill, outline=outline, width=S)

    def text(self, x, y, t, size=13, color=FG, bold=False, anchor="la"):
        self.d.text((x * S, y * S), t, font=font(size, bold), fill=color, anchor=anchor)

    def champ(self, x, y, s, ring, letter):
        self.box(x, y, s, s, CARD2, s // 5, ring)
        self.text(x + s / 2, y + s / 2, letter, s // 3, FG, True, "mm")

    def button(self, x, y, w, t, primary=True):
        self.box(x, y, w, 34, ACC if primary else CARD2, 9)
        self.text(x + w / 2, y + 17, t, 12, BG if primary else FG, True, "mm")

    def save(self, name):
        self.im.resize((W, self.h), Image.LANCZOS).save(os.path.join(D, name))


def variante_a():
    c = Lienzo(330, "A · Una sola ficha: se lee de arriba abajo")
    c.box(24, 52, W - 48, 254)
    c.champ(48, 76, 64, ACC, "Ur")
    c.text(130, 74, "Victoria  ·  +22 PL", 26, GOOD, True)
    c.text(130, 112, "Platino I · 73 PL     Urgot · 16 / 7 / 12 · 30:51", 13, DIM)
    c.box(48, 158, W - 96, 40, CARD2, 10)
    c.box(48, 158, 5, 40, GOOD, 2)
    c.text(66, 178, "Objetivo cumplido: llegaste al minuto 10 a menos de 10 súbditos de tu rival.", 14, GOOD, True, "lm")
    c.text(50, 216, "A mejorar en la siguiente", 11, DIM, True)
    c.text(50, 236, "Muertes que costaron objetivos: espera si no hay visión o tu equipo no está.", 16, FG, True)
    c.button(W - 262, 76, 214, "Ver el análisis completo", False)
    c.save("variante_A.png")


def variante_b():
    c = Lienzo(330, "B · Tres columnas: resultado, objetivo y qué mejorar")
    w = (W - 48 - 24) // 3
    for i, (title, color) in enumerate((("RESULTADO", GOOD), ("TU OBJETIVO", GOOD), ("A MEJORAR", WARN))):
        x = 24 + i * (w + 12)
        c.box(x, 52, w, 210)
        c.box(x + 18, 70, 4, 16, color, 2)
        c.text(x + 30, 68, title, 12, DIM, True)
    x = 24
    c.text(x + 18, 106, "Victoria", 30, GOOD, True)
    c.text(x + 18, 154, "+22 PL", 22, FG, True)
    c.text(x + 18, 190, "Platino I · 73 PL", 13, DIM)
    c.text(x + 18, 216, "Urgot · 16 / 7 / 12", 13, DIM)
    x = 24 + w + 12
    c.text(x + 18, 106, "Cumplido", 30, GOOD, True)
    for j, t in enumerate(("Llegar al minuto 10 a menos", "de 10 súbditos de tu rival.")):
        c.text(x + 18, 156 + j * 22, t, 14, FG)
    x = 24 + 2 * (w + 12)
    for j, t in enumerate(("Muertes que costaron", "objetivos")):
        c.text(x + 18, 106 + j * 34, t, 21, WARN, True)
    for j, t in enumerate(("Espera si no hay visión", "o tu equipo no está.")):
        c.text(x + 18, 188 + j * 22, t, 14, FG)
    c.button(W // 2 - 120, 278, 240, "Ver el análisis completo")
    c.save("variante_B.png")


def variante_c():
    c = Lienzo(350, "C · Franja de resultado y tres frases")
    c.box(24, 52, W - 48, 82)
    c.box(24, 52, 6, 82, GOOD, 3)
    c.champ(50, 66, 54, ACC, "Ur")
    c.text(120, 68, "Victoria", 22, GOOD, True)
    c.text(120, 102, "Urgot contra Riven · 16 / 7 / 12", 12, DIM)
    c.text(W - 50, 68, "+22 PL", 22, GOOD, True, "ra")
    c.text(W - 50, 102, "Platino I · 73 PL", 12, DIM, False, "ra")
    rows = (("LO MEJOR", "Ganaste el inicio en tu línea y los objetivos épicos.", GOOD),
            ("A MEJORAR", "Muertes que costaron objetivos.", WARN),
            ("PARA LA SIGUIENTE", "Objetivo cumplido; repítelo: minuto 10 a menos de 10 súbditos de tu rival.", ACC))
    for i, (k, t, color) in enumerate(rows):
        y = 146 + i * 50
        c.box(24, y, W - 48, 42, CARD, 10)
        c.text(44, y + 21, k, 11, color, True, "lm")
        c.text(210, y + 21, t, 14, FG, False, "lm")
    c.button(24, 300, 240, "Ver el análisis completo", False)
    c.save("variante_C.png")


if __name__ == "__main__":
    variante_a()
    variante_b()
    variante_c()
    print("ok")
