"""Sonidos de aviso: se sintetizan al vuelo (no hay archivos que distribuir) y se escalan al volumen elegido."""
import math, os, struct, wave

CACHE_DIR = ""  # lo fija lol_advisor al arrancar

# notas: (frecuencia en Hz, duración en s, inicio en s)
SOUNDS = {
    "Doble tono": [(880, 0.16, 0), (1175, 0.24, 0.17)],
    "Campana": [(784, 0.9, 0), (1568, 0.7, 0), (2352, 0.4, 0)],
    "Arpegio": [(523, 0.14, 0), (659, 0.14, 0.12), (784, 0.14, 0.24), (1047, 0.34, 0.36)],
    "Pulso": [(1000, 0.08, 0), (1000, 0.08, 0.14), (1000, 0.08, 0.28)],
    "Cristal": [(1760, 0.5, 0), (2637, 0.35, 0.06)],
    "Alerta": [(660, 0.18, 0), (880, 0.18, 0.2), (660, 0.18, 0.4)],
}


def synth_wav(path, name, volume):
    rate = 22050
    notes = SOUNDS.get(name) or SOUNDS["Doble tono"]
    n = int((max(s + d for _, d, s in notes) + 0.05) * rate)
    buf = [0.0] * n
    for f, d, s in notes:
        a = int(s * rate)
        for i in range(int(d * rate)):
            if a + i >= n:
                break
            t = i / rate
            buf[a + i] += math.sin(2 * math.pi * f * t) * min(1.0, t / 0.004) * math.exp(-3.2 * t / d)
    peak = max(abs(v) for v in buf) or 1
    scale = 32767 * 0.9 * max(0.0, min(1.0, volume)) / peak
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % n, *(int(v * scale) for v in buf)))


def play_alert(sound, volume):
    """Reproduce un aviso al volumen dado (0 a 1). winsound no tiene volumen: el archivo ya sale escalado."""
    if volume <= 0:
        return
    try:
        import winsound
        step = max(1, round(volume * 20))
        path = os.path.join(CACHE_DIR, "sounds", f"{sound}_{step}.wav")
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            synth_wav(path, sound, step / 20)
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass


def beep(conf=None):
    conf = conf or {}
    if conf.get("beep", True):
        play_alert(conf.get("sound", "Doble tono"), conf.get("volume", 0.7))
