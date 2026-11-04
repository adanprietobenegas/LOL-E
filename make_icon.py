"""Fija el icono de la aplicación a partir de una de las propuestas de assets/icon_options.

Uso:  python make_icon.py [número del diseño, 1-6]      (por defecto, el 4)
"""
import os, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DESIGNS = {"1": "1_ojos", "2": "2_monograma_E", "3": "3_escudo", "4": "4_robot", "5": "5_mirilla", "6": "6_LE",
           "A": "wA_apilado_dorado", "B": "wB_linea_neon", "C": "wC_insignia_dorada", "D": "wD_rosa", "E": "wE_crema",
           "F": "wF_burbuja", "B1": "b1_limpia", "B2": "b2_dorada", "B3": "b3_degradada", "B4": "b4_rosa", "B5": "b5_apilada",
           "B6": "b6_crema"}
n = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
src = os.path.join(HERE, "assets", "icon_options", f"{DESIGNS[n]}.png")
img = Image.open(src).convert("RGBA")
img.save(os.path.join(HERE, "assets", "icon.png"))
img.save(os.path.join(HERE, "assets", "icon.ico"), sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print(f"icono fijado: diseño {n} ({DESIGNS[n]})")
