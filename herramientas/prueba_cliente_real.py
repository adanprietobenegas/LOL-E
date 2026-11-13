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
lcu = core.LCU(*found)
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
err = leer("error.log")
paso("ningún fallo del programa registrado", not err, err[:600])
print("\nRegistro de diagnóstico de esta prueba:")
print(leer("diag.log") or "  (vacío)")
print("TODO BIEN" if ok else "HAY FALLOS: ver las líneas marcadas con MAL")
sys.exit(0 if ok else 1)
