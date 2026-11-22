"""Partida encontrada (la ventana de «Aceptar»): detectar cuándo empieza una NUEVA aunque la fase del cliente no cambie.

Si alguien no acepta, el cliente vuelve a la cola y casi enseguida encuentra otra partida. Ese «En cola» puede durar menos que el intervalo de lectura,
y entonces la fase sigue siendo «ReadyCheck» de principio a fin y el aviso sonoro no volvía a sonar. Por eso, mientras dura la fase, se lee también
`/lol-matchmaking/v1/ready-check` (estado, tu respuesta y el tiempo transcurrido) y se compara cada lectura con la anterior.
"""
import time


def read(lcu):
    """Lectura mínima de la ventana de aceptar: {"state", "response", "timer", "t"} (t = hora de la lectura) o None si el cliente no la da."""
    try:
        d = lcu.get("/lol-matchmaking/v1/ready-check")
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    try:
        timer = float(d.get("timer"))
    except (TypeError, ValueError):
        timer = None
    return {"state": d.get("state") or "", "response": d.get("playerResponse") or "None", "timer": timer, "t": time.time()}


def new_round(prev, cur):
    """True si `cur` es otra ventana de aceptar distinta de la de `prev` (ambas del mismo estado de fase «ReadyCheck»).

    Señales de una ronda nueva: el contador de tiempo vuelve a empezar, tu respuesta vuelve a «ninguna» tras haber aceptado o rechazado,
    o el estado pasa de uno final (todos listos, alguien no aceptó, no válido) a «en curso» otra vez."""
    if not prev or not cur:
        return False
    pt, ct = prev.get("timer"), cur.get("timer")
    if pt is not None and ct is not None and prev.get("t") and cur.get("t"):
        # el contador avanza al ritmo del reloj (sea cual sea su sentido); si salta de otra forma, es una ventana nueva
        if abs(abs(ct - pt) - (cur["t"] - prev["t"])) > 3:
            return True
    if prev.get("response") in ("Accepted", "Declined") and cur.get("response") == "None":
        return True
    if prev.get("state") not in ("", "InProgress") and cur.get("state") == "InProgress":
        return True
    return False
