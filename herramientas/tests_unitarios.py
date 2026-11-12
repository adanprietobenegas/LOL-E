"""Pruebas de la lógica que no necesita el cliente de League ni ventana. Se ejecutan con:  python herramientas/tests_unitarios.py

Cubren sonidos por fase, conjunto de objetos (formato y archivo del juego), numeración de huecos de objeto (las botas no cuentan),
selector de rival y coherencia de versión/notas. Las pruebas con ventana y datos simulados siguen en herramientas/test_modes.py y demo_live.py.
"""
import json, math, os, struct, sys, tempfile, unittest, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # cliente_falso.py

import itemset  # noqa: E402
import lol_advisor as core  # noqa: E402
import sounds  # noqa: E402


class Sonidos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        sounds.CACHE_DIR = self.tmp

    def test_valores_por_defecto_de_cada_fase(self):
        conf = {"sound": "Campana", "phase_sounds": {}}
        self.assertEqual(sounds.phase_cfg(conf, "ban"), ("Campana", ""))        # sin ajuste propio: el sonido general
        self.assertEqual(sounds.phase_cfg(conf, "locked")[0], "Arpegio")
        self.assertEqual(sounds.phase_cfg(conf, "start")[0], sounds.NONE)

    def test_ajuste_propio(self):
        conf = {"phase_sounds": {"pick": {"sound": sounds.FILE, "file": "x.wav"}}}
        self.assertEqual(sounds.phase_cfg(conf, "pick"), (sounds.FILE, "x.wav"))

    def test_wav_propio_se_escala_al_volumen(self):
        src = os.path.join(self.tmp, "u.wav")
        with wave.open(src, "wb") as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(22050)
            f.writeframes(struct.pack("<2000h", *(int(20000 * math.sin(i / 5)) for i in range(2000))))
        out = sounds._scaled_wav(src, 0.5)
        with wave.open(out) as f:
            peak = max(struct.unpack("<2000h", f.readframes(2000)))
        self.assertTrue(9000 < peak < 11000, peak)

    def test_archivo_inexistente_o_no_wav(self):
        self.assertFalse(sounds.play_file(os.path.join(self.tmp, "no.wav"), 0.5))
        mp3 = os.path.join(self.tmp, "a.mp3")
        open(mp3, "w").close()
        self.assertFalse(sounds.play_file(mp3, 0.5))

    def test_play_phase_respeta_el_interruptor_y_el_respaldo(self):
        calls = []
        real_alert, real_file = sounds.play_alert, sounds.play_file
        try:
            sounds.play_alert = lambda s, v: calls.append(("a", s, v))
            sounds.play_file = lambda p, v: (calls.append(("f", p)), False)[1]
            sounds.play_phase({"beep": False}, "found")
            self.assertEqual(calls, [])
            sounds.play_phase({"beep": True, "volume": .4, "sound": "Pulso",
                               "phase_sounds": {"pick": {"sound": sounds.FILE, "file": "z.wav"}}}, "pick")
            self.assertEqual(calls, [("f", "z.wav"), ("a", "Pulso", .4)])   # el archivo falla: suena el general
        finally:
            sounds.play_alert, sounds.play_file = real_alert, real_file


class ConjuntoDeObjetos(unittest.TestCase):
    def test_make_set_y_merge_conservan_los_ajenos(self):
        s = itemset.make_set("lole-238-middle", "LOL-E · Zed", 238, [("Inicio", [1055, 2003]), ("Vacío", [])])
        self.assertEqual(s["associatedChampions"], [238])
        self.assertEqual(len(s["blocks"]), 1)                      # los bloques vacíos no se envían
        self.assertEqual(s["blocks"][0]["items"][0], {"id": "1055", "count": 1})
        ajeno = {"uid": "otro", "title": "mío"}
        viejo = {"uid": "lole-238-middle", "title": "viejo"}
        out = itemset.merge([ajeno, viejo], s)
        self.assertIn(ajeno, out)
        self.assertEqual([x["title"] for x in out if x["uid"] == "lole-238-middle"], ["LOL-E · Zed"])

    def test_merge_limita_los_de_lole(self):
        existentes = [{"uid": f"lole-{i}-top", "title": str(i)} for i in range(30)]
        nuevo = itemset.make_set("lole-999-top", "n", 999, [("a", [1])])
        self.assertEqual(len([x for x in itemset.merge(existentes, nuevo) if x["uid"].startswith("lole-")]), itemset.KEEP)

    def test_archivo_del_juego_y_comprobacion_de_copia(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "Config"))
        conf = {"lol_path": d}
        path = itemset.write_game_file(conf, "MonkeyKing", "LOL-E Wukong", [("Inicio", [1055, 2003]), ("Vacío", [])])
        j = json.load(open(path, encoding="utf-8"))
        self.assertEqual((j["map"], j["mode"], j["type"]), ("SR", "any", "custom"))
        self.assertEqual(len(j["blocks"]), 1)
        self.assertFalse(itemset.client_copied(conf, "MonkeyKing", "lole-62-top", wait=0.3))
        with open(os.path.join(os.path.dirname(path), "RIOT_ItemSet_1.json"), "w") as f:
            f.write('{"uid":"lole-62-top"}')
        self.assertTrue(itemset.client_copied(conf, "MonkeyKing", "lole-62-top", wait=0.3))


class HuecosDeObjeto(unittest.TestCase):
    class Kit:
        items = {1: {"t": ["Boots"]}, 2: {"t": ["Damage"]}, 3: {"t": ["Damage"]}}

    def labels(self, it):
        import ui_build
        return ui_build.slot_labels(self.Kit, it)

    def test_botas_entre_los_principales(self):
        self.assertEqual(list(self.labels({"core": [2, 1, 3], "i4": [2], "i5": [2], "i6": [2]}).values()),
                         ["3.º objeto", "4.º objeto", "5.º objeto"])

    def test_sin_botas_en_los_principales(self):
        self.assertEqual(list(self.labels({"core": [2, 3, 2], "i4": [2], "i5": [2], "i6": [2]}).values()),
                         ["4.º objeto", "5.º objeto", "6.º objeto"])

    def test_botas_en_el_primer_hueco(self):
        r = self.labels({"core": [2, 3, 2], "i4": [1], "i5": [2], "i6": [2]})
        self.assertEqual(list(r.values()), ["Con las botas", "4.º objeto", "5.º objeto"])


class SelectorDeRival(unittest.TestCase):
    class Kit:
        champs = {157: {"name": "Yasuo"}, 23: {"name": "Tryndamere"}}

    def test_porcentaje_contra_cada_rival(self):
        import ui_opp
        filas = [{"name": "Yasuo", "wr": 49.6, "games": 500}, {"name": "Tryndamere", "wr": 42.0, "games": 10}]
        self.assertEqual(ui_opp.wr_vs(self.Kit, filas, 157), (49.6, 500))
        self.assertIsNone(ui_opp.wr_vs(self.Kit, filas, 23))        # menos de 20 partidas: sin datos
        self.assertIsNone(ui_opp.wr_vs(self.Kit, "cargando", 157))
        self.assertIsNone(ui_opp.wr_vs(self.Kit, filas, 999))


class JugadoresDeLaPartida(unittest.TestCase):
    def sesion(self):
        def p(pu, cid, pos):
            return {"puuid": pu, "championId": cid, "selectedPosition": pos, "profileIconId": 1}
        return {"gameData": {
            "teamOne": [p("a2", 11, "JUNGLE"), p("a1", 10, "TOP"), p("me", 14, "UTILITY")],
            "teamTwo": [p("e2", 21, "MIDDLE"), p("e1", 20, "TOP"), p("e3", 22, "")],
            "playerChampionSelections": [{"puuid": "me", "spell1Id": 4, "spell2Id": 3}]}}

    def test_equipos_roles_y_orden(self):
        import players
        ros = players.game_roster(self.sesion(), "me")
        self.assertEqual([(x["team"], x["role"]) for x in ros],
                         [("ally", "TOP"), ("ally", "JUNGLE"), ("ally", "SUPPORT"), ("enemy", "TOP"), ("enemy", "MIDDLE"), ("enemy", "")])
        self.assertEqual([x["puuid"] for x in ros if x["me"]], ["me"])
        self.assertEqual(next(x for x in ros if x["me"])["spells"], [4, 3])

    def test_mi_equipo_puede_ser_el_dos(self):
        import players
        ros = players.game_roster(self.sesion(), "e1")
        self.assertEqual([x["cid"] for x in ros if x["team"] == "ally"], [20, 21, 22])

    def test_sin_datos_o_sin_mi_equipo(self):
        import players
        self.assertIsNone(players.game_roster({}, "me"))
        self.assertIsNone(players.game_roster({"gameData": {"teamOne": [], "teamTwo": []}}, "me"))
        self.assertIsNone(players.game_roster(self.sesion(), "otro"))
        self.assertIsNone(players.game_roster(self.sesion(), ""))


class TableroCincoContraCinco(unittest.TestCase):
    def test_rango_medio(self):
        import ui_vs
        oro4, plat1 = {"key": "GOLD", "div": "IV"}, {"key": "PLATINUM", "div": "I"}
        self.assertLess(ui_vs.rank_score(oro4), ui_vs.rank_score(plat1))
        self.assertEqual(ui_vs.score_rank((ui_vs.rank_score(oro4) + ui_vs.rank_score(plat1)) / 2)[0].split()[0] in ("Oro", "Platino"), True)
        self.assertEqual(ui_vs.score_rank(ui_vs.rank_score(plat1))[0], "Platino I")
        self.assertIsNone(ui_vs.rank_score(None))
        self.assertEqual(ui_vs.score_rank(ui_vs.rank_score({"key": "MASTER", "div": ""}))[0], "Maestro")   # las ligas altas no llevan división

    def test_etiquetas(self):
        import ui_vs
        x = {"cid": 5, "role": "TOP", "puuid": "p", "me": False}
        p = {"mastery": {5: 250000}, "stats": {"streak": 4, "otp": 5, "sr_n": 10}, "roles": ["JUNGLE"], "level": 200, "solo": {"key": "GOLD"}}
        textos = [t for t, _ in ui_vs.badges(p, x, set(), None)]
        self.assertIn("Maestría 250k", textos)
        self.assertIn("Racha +4", textos)
        self.assertIn("Fuera de su línea", textos)
        self.assertEqual(ui_vs.badges(None, x, {"p"}, None), [("Dúo contigo", "info")])
        nuevo = {"mastery": {}, "stats": {}, "roles": [], "level": 200, "solo": {"key": "GOLD"}}
        self.assertIn("Primera vez", [t for t, _ in ui_vs.badges(nuevo, x, set(), None)])


class ClavesDelCampeon(unittest.TestCase):
    def test_archivo_valido_y_con_los_casos_conocidos(self):
        import claves
        d = claves.load()
        self.assertTrue(d["patch"] and len(d["champs"]) > 50)
        for k, v in d["champs"].items():
            self.assertTrue(v["n"] and v["c"], k)
            for tipo, texto in v["c"]:
                self.assertIn(tipo, claves.TIPOS, k)
                self.assertTrue(10 < len(texto) <= 260, (k, len(texto)))
        kaisa = " ".join(t for _, t in claves.for_champ("Kaisa"))
        self.assertIn("100", kaisa)                      # umbrales de evolución
        cas = " ".join(t for _, t in claves.for_champ("Cassiopeia")).lower()
        self.assertIn("sí puede comprar botas", cas)     # error de la primera pasada, corregido
        self.assertNotIn("no puede comprar botas", cas)
        self.assertEqual(claves.for_champ("NoExiste"), [])
        self.assertEqual(claves.for_champ(None), [])

    def test_aviso_de_parche(self):
        import claves
        self.assertEqual(claves.patch_of("16.22.1"), "26.22")
        self.assertEqual(claves.patch_of(""), "")
        self.assertEqual(claves.stale("16.22.1"), "" if claves.load()["patch"] == "26.22" else "26.22")
        self.assertEqual(claves.stale("16.23.1"), "26.23")
        self.assertEqual(claves.stale("basura"), "")

    def test_el_archivo_de_la_app_sale_del_documento_verificado(self):
        src = json.load(open(os.path.join(ROOT, "docs", "rediseno", "claves_campeones.json"), encoding="utf-8"))["campeones"]
        import claves
        for k in claves.load()["champs"]:
            self.assertIn(k, src)


class Temas(unittest.TestCase):
    ROLES = ("bg", "s1", "s2", "text", "text2", "acento_consulta", "acento_vivo", "positivo", "negativo", "aliado", "rival", "aviso")

    @staticmethod
    def lum(h):
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
        return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]

    def cr(self, a, b):
        la, lb = sorted((self.lum(a), self.lum(b)), reverse=True)
        return (la + .05) / (lb + .05)

    def test_todos_los_temas_tienen_los_dos_modos_y_contraste(self):
        import temas
        for nombre, t in {**temas.COLORES, **temas.LOOKS}.items():
            for modo in ("oscuro", "claro"):
                m = t[modo]
                self.assertTrue(all(r in m for r in self.ROLES), (nombre, modo))
                for r in ("text", "text2"):
                    self.assertGreaterEqual(self.cr(m[r], m["s2"]), 4.5, (nombre, modo, r))
                for r in ("positivo", "negativo", "aliado", "rival", "aviso"):
                    self.assertGreaterEqual(self.cr(m[r], m["s2"]), 4.4, (nombre, modo, r))   # 4,4: margen de redondeo del cálculo

    def test_estilos_y_looks_tienen_todos_los_tokens(self):
        import temas
        for nombre, e in {**temas.ESTILOS, **temas.FORMA_LOOKS}.items():
            for k in ("radio", "bw", "sombra", "borde", "filo", "sombra_color", "doble", "titulo", "nota"):
                self.assertIn(k, e, (nombre, k))
        for nombre in temas.LOOKS:
            self.assertIn(nombre, temas.FORMA_LOOKS)

    def test_aplicar_cambia_paleta_estilo_y_tipografia(self):
        import temas, ui_kit
        try:
            temas.apply({"color_theme": "Terminal", "style": "Plano"})
            self.assertEqual(ui_kit.BODY, "Consolas")
            self.assertEqual(temas.style()["titulo"], "corchetes")
            self.assertEqual(ui_kit.PAL["fg"][1].upper(), "#C8F5D0")
            temas.apply({"color_theme": "Abisal", "style": "Brutal"})
            self.assertEqual(ui_kit.BODY, "Segoe UI")        # un tema de color no cambia la tipografía
            self.assertEqual(temas.style()["bw"], 2)
        finally:
            temas.apply({"color_theme": "Predeterminado", "style": "Plano"})
        self.assertEqual(tuple(ui_kit.PAL["bg"]), temas._DEFAULT_PAL["bg"])
        self.assertNotIn("Tema", ui_kit.ACCENTS)


class JugadoresDeLaPartidaCarga(unittest.TestCase):
    def test_la_lectura_avisa_una_sola_vez(self):
        import players
        orig = players.fetch_player
        players.fetch_player = lambda lcu, pu: {"puuid": pu, "name": pu}
        try:
            ros = [{"puuid": f"p{i}", "me": i == 0} for i in range(10)] + [{"puuid": "", "me": False}]
            avisos, prog = [], []
            players.fetch_roster(None, ros, avisos.append, lambda h, t: prog.append((h, t)))
        finally:
            players.fetch_player = orig
        self.assertEqual(len(avisos), 1)                  # el tablero se dibuja una vez, no por cada jugador
        self.assertEqual(len(avisos[0]), 10)              # incluido el propio
        self.assertEqual(prog[-1], (10, 10))


class ActualizacionAutomatica(unittest.TestCase):
    def test_instalacion_sin_ventanas_y_activada_por_defecto(self):
        import inspect, updater
        self.assertIn("/VERYSILENT", inspect.getsource(updater.install))
        self.assertTrue(core.DEFAULT_CONF["auto_update"] and core.DEFAULT_CONF["auto_install"])

    def test_solo_github(self):
        import updater
        self.assertTrue(updater.safe_url(core.DEFAULT_CONF["update_url"]))
        self.assertTrue(updater.safe_url("https://objects.githubusercontent.com/x/Instalar.exe"))
        for mala in ("http://github.com/a/b.exe", "https://github.com.evil.es/a.exe", "https://evil.es/github.com/a.exe", "file:///c:/a.exe", ""):
            self.assertFalse(updater.safe_url(mala), mala)

    def test_comparacion_de_versiones(self):
        import updater
        self.assertGreater(updater.vtuple("1.20.0"), updater.vtuple("1.19.9"))
        self.assertGreater(updater.vtuple("v1.10.0"), updater.vtuple("1.9.9"))


class QuienSoyEnLaPartida(unittest.TestCase):
    """Tu jugador se localiza por tu puuid; nunca «el primero de la lista» (así salió Sona en una partida jugada con Lillia)."""

    def detalle(self):
        parts = [{"participantId": i + 1, "teamId": 100 if i < 5 else 200, "championId": c,
                  "stats": {"win": i < 5, "kills": i, "deaths": 1, "assists": 2}, "timeline": {}}
                 for i, c in enumerate((37, 119, 25, 26, 876, 2, 111, 64, 43, 121))]
        ids = [{"participantId": i + 1, "player": {"puuid": f"pu{i + 1}"}} for i in range(10)]
        return {"gameId": 77, "gameDuration": 600, "queueId": 2400, "gameCreation": 5, "participants": parts, "participantIdentities": ids}

    def test_en_el_detalle_no_se_supone_el_primero(self):
        import history
        d = self.detalle()
        self.assertEqual(history.my_part(d, "pu5")["championId"], 876)      # Lillia, no Sona (37)
        self.assertIsNone(history.my_part(d, ""))                           # sin puuid y con diez jugadores: no se adivina
        self.assertIsNone(history.from_game(d, "desconocido"))
        self.assertEqual(history.from_game(d, "pu5")["c"], 876)

    def test_la_lista_de_un_solo_participante_sigue_valiendo(self):
        import history
        d = self.detalle()
        g = {**d, "participants": [d["participants"][4]], "participantIdentities": [d["participantIdentities"][4]]}
        self.assertEqual(history.from_game(g)["c"], 876)
        self.assertEqual(history.from_game(g, "otro puuid")["c"], 876)

    def test_el_analisis_no_adivina_y_corrige_los_guardados(self):
        import analysis, history
        d, tmp = self.detalle(), tempfile.mkdtemp()
        tl = {"frames": [{"timestamp": 0, "participantFrames": {}, "events": []}]}

        class Lcu:
            def __init__(self, puuid): self.puuid = puuid
            def get(self, path, timeout=0):
                if "current-summoner" in path: return {"puuid": self.puuid}
                return tl if "timelines" in path else d
        self.assertIsNone(analysis.load(Lcu(""), 77, "", tmp))                      # sin saber quién eres: no se analiza
        self.assertFalse(os.path.exists(os.path.join(tmp, "analysis", "77.json")))   # ni se guarda nada equivocado
        a = analysis.load(Lcu("pu5"), 77, "", tmp)                                   # el puuid se pide al cliente si falta
        self.assertEqual((a["me"], analysis.me(a)["champ"], a["sure"]), (5, 876, True))
        # un análisis guardado por una versión anterior con el jugador equivocado se corrige al abrirlo
        mal = analysis.compute(d, tl, 1)
        json.dump(mal, open(os.path.join(tmp, "analysis", "77.json"), "w", encoding="utf-8"))
        a = analysis.load(Lcu("pu5"), 77, "pu5", tmp)
        self.assertEqual((a["me"], a["team"], a["win"]), (5, 100, True))
        # y sin cliente, con el historial guardado (campeón, resultado y K/D/A)
        json.dump(analysis.compute(d, tl, 1), open(os.path.join(tmp, "analysis", "77.json"), "w", encoding="utf-8"))
        history.save(os.path.join(tmp, "history.json"), [history.from_game(d, "pu5")])

        class Cerrado:
            def get(self, *a, **k): raise ConnectionError()
        self.assertEqual(analysis.load(Cerrado(), 77, "", tmp)["me"], 5)


class HistorialPorCuenta(unittest.TestCase):
    """Dos cuentas en el mismo PC no mezclan partidas, y el historial antiguo (sin dueño) solo lo hereda quien demuestra que es suyo."""
    def setUp(self):
        import history
        self.h, self.tmp = history, tempfile.mkdtemp()
        self.antes, history.ACCOUNT = history.ACCOUNT, ""

    def tearDown(self):
        self.h.ACCOUNT = self.antes

    def viejo(self):
        json.dump({"100": {"id": "100", "t": 1, "c": 1, "w": True}}, open(os.path.join(self.tmp, "history.json"), "w"))
        json.dump({"100": {"c": 1, "w": True, "t": 1, "q": 420}}, open(os.path.join(self.tmp, "games.json"), "w"))

    def test_sin_cuenta_se_usan_los_archivos_de_siempre(self):
        self.assertTrue(self.h.hpath(self.tmp).endswith("history.json"))
        self.assertEqual(self.h.set_account(self.tmp, ""), "")
        self.assertEqual(self.h.ACCOUNT, "")

    def test_la_cuenta_que_reconoce_sus_partidas_hereda_el_historial(self):
        self.viejo()
        self.assertEqual(self.h.set_account(self.tmp, "A", [100, 200]), "migrated")
        self.assertIn("100", json.load(open(self.h.hpath(self.tmp))))
        self.assertTrue(os.path.exists(self.h.gpath(self.tmp)))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "history.json")))          # el antiguo queda como copia
        self.assertEqual(self.h.set_account(self.tmp, "A", [100]), "")                    # y no se repite
        self.assertEqual(self.h.set_account(self.tmp, "B", [100]), "new")                 # otra cuenta ya no lo hereda
        self.assertFalse(os.path.exists(self.h.hpath(self.tmp)))

    def test_una_cuenta_sin_partidas_en_comun_no_hereda(self):
        self.viejo()
        self.assertEqual(self.h.set_account(self.tmp, "B", [555]), "new")
        self.assertFalse(os.path.exists(self.h.hpath(self.tmp)))
        self.assertEqual(self.h.set_account(self.tmp, "A", [100]), "migrated")            # la dueña de verdad sí, aunque llegue después

    def test_sin_partidas_del_cliente_no_se_decide_todavia(self):
        self.viejo()
        self.assertEqual(self.h.set_account(self.tmp, "A", []), "")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "history_owner.json")))
        self.assertEqual(self.h.set_account(self.tmp, "A", [100]), "migrated")

    def test_al_abrir_sin_cliente_se_recuerda_la_ultima_cuenta(self):
        self.h.set_account(self.tmp, "A", [1])
        self.h.ACCOUNT = ""
        self.assertEqual(self.h.load_account(self.tmp), "A")
        self.assertTrue(self.h.hpath(self.tmp).endswith("history_A.json"))

    def test_el_identificador_no_puede_salir_de_la_carpeta(self):
        self.h.set_account(self.tmp, "../..\\x:y", [1])
        self.assertEqual(os.path.dirname(self.h.hpath(self.tmp)), self.tmp)


class FlujoCompleto(unittest.TestCase):
    """El bucle principal contra un cliente de mentira: cola -> selección -> partida -> fin. No abre ventana ni red."""
    def setUp(self):
        import analysis, history, players
        try:
            self.champs = core.load_champions()
        except Exception as e:
            self.skipTest(f"sin datos de campeones en cache/: {e}")
        if 86 not in self.champs:
            self.skipTest("sin datos de campeones en cache/")
        self.tmp = tempfile.mkdtemp()
        self.mods = (analysis, history, players)
        names = {core: ("CACHE", "time", "find_client", "LCU", "start_meta", "maybe_update_opgg", "play_phase", "detect_account", "load_season"),
                 players: ("fetch_team", "fetch_roster", "lobby_party"), analysis: ("load",), history: ("ACCOUNT",)}
        self.saved = [(m, n, getattr(m, n)) for m, ns in names.items() for n in ns]
        self.meta, core.META["data"] = core.META.get("data"), None
        core._DIAG["last"] = ""

    def tearDown(self):
        for m, n, v in getattr(self, "saved", []):
            setattr(m, n, v)
        if hasattr(self, "saved"):
            core.META["data"] = self.meta

    def correr(self, fake):
        import time as real
        analysis, history, players = self.mods
        ev = []

        class Reloj:   # el bucle «duerme» sin esperar: cada siesta avanza un paso del guion
            time, strftime, perf_counter = staticmethod(real.time), staticmethod(real.strftime), staticmethod(real.perf_counter)
            sleep = staticmethod(fake.dormir)

        class Ventana:
            def stopped(self): return fake.terminado
            def poll_cmd(self): return None
            def __getattr__(self, name): return lambda *a: ev.append((name,) + a)
        history.ACCOUNT = ""
        core.CACHE, core.time = self.tmp, Reloj
        core.find_client, core.LCU = (lambda conf: ("x",)), (lambda *a: fake)
        core.start_meta = core.play_phase = core.detect_account = lambda *a, **k: None
        core.maybe_update_opgg, core.load_season = (lambda *a, **k: None), (lambda *a, **k: {})
        players.fetch_team = lambda lcu, session, emit: ev.append(("fetch_team",))
        players.fetch_roster = lambda *a, **k: ev.append(("fetch_roster",))
        players.lobby_party = lambda *a, **k: None
        analysis.load = lambda lcu, gid, puuid, cache: ev.append(("analysis.load", str(gid), puuid)) or {"gid": gid}
        conf = core.load_conf()
        conf["poll_seconds"] = 0
        core.run(conf, self.champs, Ventana())
        return ev

    def leer(self, name):
        p = os.path.join(self.tmp, name)
        return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

    def test_cola_seleccion_partida_y_fin(self):
        from cliente_falso import ClienteFalso, YO
        fake = ClienteFalso()
        ev = self.correr(fake)
        self.assertEqual(self.leer("error.log"), "")                                   # ningún fallo registrado por el camino
        self.assertIn(("link", True), ev)
        fases = [e[1] for e in ev if e[0] == "phase"]
        self.assertEqual([f for f in fases if f in ("Matchmaking", "ReadyCheck", "InProgress", "EndOfGame")],
                         ["Matchmaking", "ReadyCheck", "InProgress", "EndOfGame"])
        shows = [e[2] for e in ev if e[0] == "show"]
        self.assertEqual(len(shows), 2)                                                # tu turno y, después, el campeón bloqueado
        self.assertEqual((shows[0]["turn"], shows[0]["mode"]["kind"], shows[0]["role"]), ("pick", "sr", "TOP"))
        self.assertTrue(shows[0]["cands"])
        self.assertEqual((shows[1]["mine"], bool(shows[1]["mine_locked"])), (86, True))
        self.assertIn(("fetch_team",), ev)
        ros = [e[1] for e in ev if e[0] == "roster"]
        self.assertEqual(len(ros), 1)                                                  # los 10 jugadores, una sola vez por partida
        self.assertEqual((len(ros[0]), ros[0][0]["me"], ros[0][0]["cid"]), (10, True, 86))
        msgs = [e[2] for e in ev if e[0] == "idle"]
        self.assertTrue(any("Partida en curso" in m for m in msgs))
        self.assertTrue(any("Partida terminada" in m for m in msgs))
        self.assertIn(("analysis.load", "900", YO), ev)                                # se analiza la partida nueva, no la anterior
        guardadas = json.loads(self.leer(f"history_{YO}.json"))
        self.assertEqual(sorted(guardadas), ["100", "101", "900"])
        self.assertEqual(self.leer("history.json"), "")                                # nada va ya al archivo sin dueño
        d = self.leer("diag.log")
        for trozo in ("Cliente de LoL encontrado", "Selección de campeón: cola 420, tipo sr", "Fase: ReadyCheck -> ", "Partida terminada: 900"):
            self.assertIn(trozo, d)
        self.assertNotIn("Prueba", d)                                                  # sin nombres de jugador

    def test_sin_cuenta_no_se_guarda_nada(self):
        from cliente_falso import ClienteFalso
        fake = ClienteFalso(puuid="", guion=["None", "None", "None"])
        self.correr(fake)
        self.assertEqual([f for f in os.listdir(self.tmp) if f.startswith(("history", "games"))], [])
        self.assertIn("cuenta aún desconocida", self.leer("diag.log"))

    def test_dos_cuentas_no_se_mezclan(self):
        from cliente_falso import ClienteFalso, partida
        self.correr(ClienteFalso(puuid="cuentaA", guion=["None", "None"]))
        b = ClienteFalso(puuid="cuentaB", guion=["None", "None"])
        b.viejas = [partida(500, 54, True, 3_000, puuid="cuentaB")]
        self.correr(b)
        self.assertEqual(sorted(json.loads(self.leer("history_cuentaA.json"))), ["100", "101"])
        self.assertEqual(sorted(json.loads(self.leer("history_cuentaB.json"))), ["500"])


class Versiones(unittest.TestCase):
    def test_la_version_tiene_notas_y_documentacion(self):
        import novedades
        v = core.APP_VERSION
        self.assertEqual(novedades.NOTES[0]["v"], v)
        for n in novedades.NOTES:
            for tipo, texto in n["items"]:
                self.assertIn(tipo, novedades.TIPOS)
                self.assertTrue(texto.strip())
        notas = open(os.path.join(ROOT, "docs", "NOTAS_DE_VERSION.txt"), encoding="utf-8").read()
        self.assertIn(f"VERSIÓN {v}", notas)

    def test_latest_json_coincide_si_existe(self):
        p = os.path.join(ROOT, "release", "latest.json")
        if os.path.exists(p):
            self.assertEqual(json.load(open(p, encoding="utf-8"))["version"], core.APP_VERSION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
