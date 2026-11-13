"""Valida la regla de líneas (history.role_of) con partidas reales: pide al cliente de LoL el detalle de las últimas
partidas de Grieta y cruza, para cada jugador, la etiqueta de línea, si lleva Aplastar y su objeto de rol.

    python herramientas/validar_lineas.py [cuántas partidas, por defecto 30]

Solo lee. Hace falta el cliente abierto. Qué mirar en la salida:
  · «equipos por (nº JUNGLE, nº TOP)»: lo normal sería (1, 1); cada equipo con otra combinación es un caso en que la
    etiqueta del cliente falla.
  · por objeto de rol: si 1220/1221 aparece casi siempre con TOP (o JUNGLE sin Aplastar), 1209 con Aplastar, 1206 con MIDDLE y
    1208/2055 con apoyo, los valores de history.TOP_ITEMS / JUNGLE_ITEMS / SUPPORT_ITEMS se confirman. Si no, hay que revisarlos.
  · cuántos jugadores tendría una línea distinta con la regla nueva que con la etiqueta cruda.
"""
import collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lol_advisor as l, history

found = l.find_client(l.load_conf())
if not found:
    print("El cliente de League of Legends no está abierto.")
    sys.exit(2)
import urllib.error
lcu = l.LCU(*found)
try:
    lcu.get("/lol-gameflow/v1/gameflow-phase")
except (urllib.error.URLError, ConnectionError, OSError):
    print("El cliente de League of Legends no responde (puede que se haya cerrado hace poco): ábrelo y vuelve a probar.")
    sys.exit(2)
cuantas = int(sys.argv[1]) if len(sys.argv) > 1 else 30
gs = lcu.get("/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=200", timeout=40)["games"]["games"]
sr = [g for g in gs if g["queueId"] in l.SR_QUEUES][:cuantas]
tab, equipos, cambia, n = collections.defaultdict(collections.Counter), collections.Counter(), collections.Counter(), 0
for g in sr:
    d = lcu.get(f"/lol-match-history/v1/games/{g['gameId']}")
    if not d:
        continue
    for team in (100, 200):
        lanes = collections.Counter(p["timeline"]["lane"] for p in d["participants"] if p["teamId"] == team)
        equipos[(lanes.get("JUNGLE", 0), lanes.get("TOP", 0))] += 1
    for p in d["participants"]:
        n += 1
        t = p["timeline"]
        item = p["stats"].get("roleBoundItem") or 0
        tab[item][(t["lane"], t["role"], "Aplastar" if history.SMITE in (p["spell1Id"], p["spell2Id"]) else "-")] += 1
        crudo = "SUPPORT" if t["lane"] == "BOTTOM" and t["role"] == "SUPPORT" else ("" if t["lane"] in ("", "NONE") else t["lane"])
        nuevo = history.role_of(p)
        if crudo != nuevo:
            cambia[(crudo or "-", nuevo or "-")] += 1
print(f"{n} jugadores de {len(sr)} partidas de Grieta")
print("equipos por (nº JUNGLE, nº TOP) según el cliente:", dict(equipos))
print("líneas que cambian con la regla nueva (cliente -> nueva):", dict(cambia))
for item, c in sorted(tab.items(), key=lambda x: -sum(x[1].values())):
    if sum(c.values()) >= 3:
        print(f"objeto {item}:", dict(c))
