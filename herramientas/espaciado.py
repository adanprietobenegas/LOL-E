"""Unifica los espaciados de la interfaz (padx / pady de los ui*.py y gui.py) en una escala corta.

    python herramientas/espaciado.py            # solo cuenta lo que cambiaría
    python herramientas/espaciado.py --aplicar  # reescribe los archivos

Escala: 0, 2, 4, 8, 12, 16, 24 (px lógicos). Cada valor pasa al más cercano de la escala; en empate, al mayor (así nada queda más apretado de lo que estaba por
una diferencia de 1 px). Solo toca los argumentos `padx=`, `pady=`, `ipadx=` y `ipady=`, con un número o una pareja de números; no toca tamaños, radios, fuentes ni
nada que no sea un espaciado. Se puede repetir sin efecto (ya idempotente)."""
import glob
import os
import re
import sys

ESCALA = (0, 2, 4, 8, 12, 16, 24)
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile(r"\b((?:i?pad[xy])=)(\([^)]*\)|\d+)")


def cerca(n):
    """El valor de la escala más cercano a n (en empate, el mayor)."""
    return min(ESCALA, key=lambda e: (abs(e - n), -e))


def nuevo(valor):
    return re.sub(r"\d+", lambda m: str(cerca(int(m.group(0)))), valor)


def procesar(texto):
    cambios = []

    def sub(m):
        n = m.group(1) + nuevo(m.group(2))
        if n != m.group(0):
            cambios.append((m.group(0), n))
        return n
    return PAT.sub(sub, texto), cambios


def main(aplicar):
    total, por_valor = 0, {}
    for f in sorted(glob.glob(os.path.join(D, "ui*.py")) + [os.path.join(D, "gui.py")]):
        with open(f, encoding="utf-8", newline="") as fh:
            s = fh.read()
        n, cambios = procesar(s)
        total += len(cambios)
        for a, b in cambios:
            por_valor[(a, b)] = por_valor.get((a, b), 0) + 1
        if aplicar and cambios:
            with open(f, "w", encoding="utf-8", newline="") as fh:
                fh.write(n)
    print(f"{total} espaciados {'cambiados' if aplicar else 'cambiarían'}")
    for (a, b), k in sorted(por_valor.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {k:4d}  {a}  ->  {b}")


if __name__ == "__main__":
    main("--aplicar" in sys.argv)
