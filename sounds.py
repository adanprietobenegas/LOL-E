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


PHASES = [  # (clave, rótulo, descripción)
    ("found", "Partida encontrada", "Cuando el cliente te pide aceptar la partida."),
    ("ban", "Tu turno de baneo", "Cuando te toca banear."),
    ("pick", "Tu turno de elegir", "Cuando te toca elegir campeón."),
    ("locked", "Campeón confirmado", "Cuando bloqueas tu campeón."),
    ("start", "Empieza la partida", "Cuando la partida arranca."),
]
NONE = "Sin sonido"
FILE = "Mi archivo…"  # el sonido de esa fase es un .wav elegido por el usuario
DEFAULTS = {"found": "Campana", "ban": "", "pick": "", "locked": "Arpegio", "start": NONE}  # "" = el sonido general de siempre


def phase_cfg(conf, phase):
    """(sonido, archivo) de una fase: su ajuste propio o, si no lo tiene, el predeterminado."""
    c = (conf.get("phase_sounds") or {}).get(phase) or {}
    snd = c.get("sound") or DEFAULTS.get(phase, "")
    if snd == "":
        snd = conf.get("sound", "Doble tono")
    return snd, c.get("file", "")


def _scaled_wav(src, volume):
    """Copia de un .wav de 16 bits a otro volumen (winsound no lo tiene). Devuelve la ruta a reproducir o None."""
    step = max(1, round(volume * 20))
    key = f"{abs(hash((src, os.path.getmtime(src)))) % 10**10}_{step}"
    out = os.path.join(CACHE_DIR, "sounds", f"user_{key}.wav")
    if os.path.exists(out):
        return out
    with wave.open(src, "rb") as r:
        if r.getsampwidth() != 2:
            return src  # solo se escalan los de 16 bits; el resto suena a su volumen
        params, raw = r.getparams(), r.readframes(r.getnframes())
    n = len(raw) // 2
    k = step / 20
    data = struct.pack("<%dh" % n, *(max(-32768, min(32767, int(v * k))) for v in struct.unpack("<%dh" % n, raw)))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with wave.open(out, "wb") as w:
        w.setparams(params)
        w.writeframes(data)
    return out


def play_file(path, volume):
    """Reproduce un .wav del usuario. Devuelve False si no existe o no se puede leer."""
    if volume <= 0:
        return True
    try:
        import winsound
        if not (path and os.path.isfile(path) and path.lower().endswith(".wav")):
            return False
        winsound.PlaySound(_scaled_wav(path, volume), winsound.SND_FILENAME | winsound.SND_ASYNC)
        return True
    except Exception:
        return False


def play_alert(sound, volume):
    """Reproduce un aviso al volumen dado (0 a 1). winsound no tiene volumen: el archivo ya sale escalado."""
    if volume <= 0 or sound == NONE:
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


def play_phase(conf, phase):
    """Suena el sonido de una fase (si los avisos están activados). Con un archivo propio que falla, suena el sonido general."""
    conf = conf or {}
    if not conf.get("beep", True):
        return
    snd, file = phase_cfg(conf, phase)
    vol = conf.get("volume", 0.7)
    if snd == FILE:
        if not play_file(file, vol):
            play_alert(conf.get("sound", "Doble tono"), vol)
        return
    play_alert(snd, vol)


def beep(conf=None):
    """Aviso de turno (se mantiene por compatibilidad): suena el de baneo o el de elegir según el turno."""
    play_phase(conf, "pick")