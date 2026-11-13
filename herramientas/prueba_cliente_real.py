"""Prueba de solo lectura contra el cliente REAL de LoL (tiene que estar abierto): ejercita lo que no se puede comprobar
con el cliente falso. No toca la carpeta de datos del proyecto ni la de la app instalada: trabaja sobre una copia temporal.

    python herramientas/prueba_cliente_real.py

Comprueba: que se encuentra el cliente, que se sabe qué cuenta es, la lectura del historial y su reparto por cuenta
(incluida la herencia del historial antiguo), el perfil, la lectura de un jugador y qué queda en los registros.
No imprime nombres ni identificadores completos.
"""
import os, shutil, sys, tempfile, time
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)
import lol_advisor as core, history, players

REAL = core.CACHE
TMP = os.path.join(tempfile.mkdtemp(), "cache")
shutil.copytree(REAL, TMP, ignore=shutil.ignore_patterns("history_*", "games_*", "account.json", "schema.json", "*.log", "splash", "icons",
                                                         "items", "profileicons", "emblems", "sounds", "live_samples"))
core.CACHE = TMP
history.ACCOUNT = ""
ok = True


def paso(texto, bien, detalle=""):
    global ok
    ok = ok and bool(bien)
    print(("  bien  " if bien else "  MAL   ") + texto + (f"  ·  {detalle}" if detalle else ""), flush=True)


def leer(name):
    p = os.path.join(TMP, name)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


conf = core.load_conf()
found = core.find_client(conf)
if not found:
    print("El cliente de League of Legends no está abierto: no hay nada que probar.")
    sys.exit(2)
import urllib.error
lcu = core.LCU(*found)
try:
    lcu.get("/lol-gameflow/v1/gameflow-phase")
except (urllib.error.URLError, ConnectionError, OSError):
    print("El cliente de League of Legends no responde (puede que se haya cerrado hace poco): ábrelo y vuelve a probar.")
    sys.exit(2)
print("Cliente encontrado. Fase:", lcu.get("/lol-gameflow/v1/gameflow-phase"))
champs = core.load_champions()
legacy = len(core.read_json(os.path.join(TMP, "history.json"), {}) or {})
core.check_schema()
t = time.time()
P = core.load_player_data(lcu, core.load_season(champs, conf))
print(f"Datos del jugador leídos en {time.time() - t:.1f} s")
pu = P.get("puuid") or ""
paso("se sabe qué cuenta es", bool(pu), f"cuenta {pu[:8]}")
paso("el cliente entregó el historial", P.get("hist_ok"))
paso("la cuenta activa es la del cliente", history.ACCOUNT == history._safe(pu))
hp = history.hpath(TMP)
mine = core.read_json(hp, {}) or {}
paso("el historial se guarda en el archivo de la cuenta", os.path.exists(hp) and os.path.basename(hp).startswith("history_"), f"{len(mine)} partidas")
owner = core.read_json(os.path.join(TMP, "history_owner.json"), {}) or {}
if legacy:
    paso("el historial antiguo se hereda (o se deja, si no es de esta cuenta)", True,
         f"antiguo: {legacy} partidas · dueño anotado: {'esta cuenta' if owner.get('puuid') == history._safe(pu) else owner.get('puuid', 'nadie')[:8]}")
    if owner.get("puuid") == history._safe(pu):
        paso("no se pierde ninguna partida al heredar", len(mine) >= legacy, f"{legacy} -> {len(mine)}")
paso("el archivo antiguo sigue en su sitio", (not legacy) or os.path.exists(os.path.join(TMP, "history.json")))
todas = history.load_all(history.hpath(TMP), history.gpath(TMP))
paso("todas las partidas guardadas tienen campeón y fecha", all(e.get("c") and e.get("t") for e in todas), f"{len(todas)} en total")
paso("los campeones del historial existen", all(e["c"] in champs for e in todas[:60]))
prof = P.get("profile") or {}
paso("perfil leído", bool(prof.get("name")), f"nivel {prof.get('level')} · rango {'sí' if prof.get('solo') or prof.get('flex') else 'sin clasificar'}")
paso("maestrías leídas", len(P.get("mastery") or {}) > 0, f"{len(P.get('mastery') or {})} campeones")
paso("campeones en propiedad leídos", len(P.get("owned") or ()) > 0, f"{len(P.get('owned') or ())}")
info = core.player_info(P)
paso("resumen para la pantalla de inicio", isinstance(info.get("modes"), list), f"{len(info['modes'])} modos · {P.get('games')} partidas de Grieta")
me = players.fetch_player(lcu, pu) if pu else {}
paso("lectura de un jugador (la tuya)", bool(me.get("name")) and not me.get("error"),
     f"{len(me.get('recent') or [])} recientes · {len(me.get('mastery') or {})} maestrías · etiquetas de {len((me.get('stats') or {}).get('champs') or [])} campeones")
mode = core.detect_mode(lcu)
paso("modo de partida (fuera de partida debe salir sin cola)", isinstance(mode, dict), str(mode))
paso("sala actual legible", True, f"{len(players.lobby_party(lcu, pu) or ())} compañeros en la sala")
# ---- línea que jugaste: nadie puede quedar como «jungla» sin llevar Aplastar ----
glist = lcu.get("/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex=200", timeout=40)["games"]["games"]
SR = core.SR_QUEUES
ventana = [g for g in glist if g.get("queueId") in SR]
mala, cuentas = [], {}
gamesf = core.read_json(history.gpath(TMP), {}) or {}
for g in ventana:
    me = history.my_part(g, pu)
    e = gamesf.get(str(g["gameId"])) or {}
    cuentas[e.get("r", "?")] = cuentas.get(e.get("r", "?"), 0) + 1
    if e.get("r") == "JUNGLE" and history.SMITE not in (me.get("spell1Id"), me.get("spell2Id")) and (me.get("stats") or {}).get("roleBoundItem") not in history.JUNGLE_ITEMS:
        mala.append(g["gameId"])
paso("ninguna partida de la ventana queda como jungla sin Aplastar", not mala, f"{len(ventana)} partidas de Grieta; líneas: {cuentas}")
paso("todas las de la ventana llevan la regla nueva", all((gamesf.get(str(g['gameId'])) or {}).get("rv") == history.ROLE_V for g in ventana))
renek = [g for g in ventana if (history.my_part(g, pu) or {}).get("championId") == 58]
paso("Renekton: ninguna partida figura como jungla", all((gamesf.get(str(g["gameId"])) or {}).get("r") != "JUNGLE" for g in renek),
     ", ".join(f"{(gamesf.get(str(g['gameId'])) or {}).get('r') or 'sin línea'}" for g in renek) or "no hay partidas con él en la ventana")
hist_f = core.read_json(hp, {}) or {}
paso("el historial coincide con las partidas", all((hist_f.get(str(g["gameId"])) or {}).get("r") == (gamesf.get(str(g["gameId"])) or {}).get("r") for g in ventana))
pend = [k for k, e in gamesf.items() if isinstance(e, dict) and e.get("q") in SR and e.get("rv") != history.ROLE_V]
paso("no queda ninguna partida de Grieta pendiente de la regla de líneas (también las que el cliente ya no lista)", not pend,
     f"{len(gamesf)} guardadas; pendientes: {len(pend)}")
sch = core.read_json(os.path.join(TMP, "schema.json"), {}) or {}
paso("datos migrados al esquema nuevo", sch.get("v") == core.SCHEMA, f"esquema {sch.get('v')}")
err = leer("error.log")
paso("ningún fallo del programa registrado", not err, err[:600])
print("\nRegistro de diagnóstico de esta prueba:")
print(leer("diag.log") or "  (vacío)")
print("TODO BIEN" if ok else "HAY FALLOS: ver las líneas marcadas con MAL")
sys.exit(0 if ok else 1)
