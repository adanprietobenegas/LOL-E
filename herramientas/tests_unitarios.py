"""Pruebas de la lógica que no necesita el cliente de League ni ventana. Se ejecutan con:  python herramientas/tests_unitarios.py

Cubren sonidos por fase, conjunto de objetos (formato y archivo del juego), numeración de huecos de objeto (las botas no cuentan),
selector de rival y coherencia de versión/notas. Las pruebas con ventana y datos simulados siguen en herramientas/test_modes.py y demo_live.py.
"""
import json, math, os, struct, sys, tempfile, time, unittest, wave

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
        self.assertIn("4 victorias seguidas", textos)
        self.assertIn("Fuera de su línea", textos)
        self.assertEqual(ui_vs.badges(None, x, {"p"}, None), [("Dúo contigo", "info")])
        nuevo = {"mastery": {99: 5000}, "stats": {}, "roles": [], "level": 200, "solo": {"key": "GOLD"}}
        self.assertIn("Primera vez con este campeón", [t for t, _ in ui_vs.badges(nuevo, x, set(), None)])
        sin_lista = {"mastery": {}, "stats": {}, "roles": [], "level": 200, "solo": {"key": "GOLD"}}
        self.assertEqual(ui_vs.badges(sin_lista, x, set(), None), [])            # sin maestrías leídas no se inventa «primera vez»
        con = {"mastery": {5: 30000}, "stats": {"champs": [{"c": 5, "n": 5, "w": 4, "kda": 3}]}, "roles": [], "level": 200, "solo": {"key": "GOLD"}}
        self.assertIn("Le va bien con él: 4V 1D", [t for t, _ in ui_vs.badges(con, x, set(), None)])
        con["stats"]["champs"][0].update(n=3, w=3)                               # con tres partidas no se dice nada
        self.assertEqual(ui_vs.badges(con, x, set(), None), [])
        self.assertIn(("Juntos 3V 2D", "good"), ui_vs.badges(None, x, set(), (5, 3)))

    def test_frase_resumen_del_analisis(self):
        import analysis
        its = [{"title": "Muertes evitables", "tone": "bad"}, {"title": "Visión baja", "tone": "bad"}, {"title": "Buen farmeo", "tone": "good"}]
        self.assertEqual(analysis.headline({"win": False}, its), "Derrota. Lo que más pesó: muertes evitables y visión baja. Lo mejor: buen farmeo.")
        self.assertEqual(analysis.headline({"win": True}, its), "Victoria. Lo mejor: buen farmeo. A mejorar: muertes evitables.")
        self.assertEqual(analysis.headline({"win": True}, its[:1]), "Victoria, aunque con cosas a mejorar: muertes evitables.")
        self.assertEqual(analysis.headline({"win": False}, []), "")


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

    def test_una_direccion_guardada_vacia_no_apaga_las_actualizaciones(self):
        tmp = tempfile.mkdtemp()
        orig = core.CONF_FILE
        core.CONF_FILE = os.path.join(tmp, "config.json")
        try:
            for guardada in ("", "   ", None):
                json.dump({"update_url": guardada, "top_n": 7}, open(core.CONF_FILE, "w"))
                conf = core.load_conf()
                self.assertEqual(conf["update_url"], core.DEFAULT_CONF["update_url"], repr(guardada))
                self.assertEqual(conf["top_n"], 7)                     # lo demás guardado se respeta
            json.dump({"update_url": "https://github.com/otro/repo/releases/latest/download/latest.json"}, open(core.CONF_FILE, "w"))
            self.assertIn("otro/repo", core.load_conf()["update_url"])  # una dirección propia se respeta
        finally:
            core.CONF_FILE = orig

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


class NadieSeQuedaFueraDelTablero(unittest.TestCase):
    def reparto(self, roles):
        import ui_vs
        return ui_vs.lane_slots([({"role": r, "cid": i}, None) for i, r in enumerate(roles)])

    def test_cinco_lineas_normales(self):
        s = self.reparto(["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT"])
        self.assertEqual([s[k][0]["cid"] for k in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT")], [0, 1, 2, 3, 4])

    def test_linea_repetida_o_vacia_no_esconde_a_nadie(self):
        for roles in (["TOP", "JUNGLE", "JUNGLE", "BOTTOM", "SUPPORT"], ["TOP", "", "MIDDLE", "BOTTOM", ""], ["", "", "", "", ""],
                      ["JUNGLE"] * 5, ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT", "TOP"]):
            s = self.reparto(roles)
            self.assertEqual(sorted(v[0]["cid"] for v in s.values()), list(range(len(roles))), roles)
        s = self.reparto(["TOP", "JUNGLE", "JUNGLE", "BOTTOM", "SUPPORT"])
        self.assertEqual((s["JUNGLE"][0]["cid"], s["MIDDLE"][0]["cid"]), (1, 2))   # el repetido ocupa la línea que quedaba libre


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

        class Reloj:   # el bucle «duerme» sin esperar: cada siesta avanza un paso del guion y el reloj ~40 s (los reintentos «cada 30 s» ocurren)
            time = staticmethod(lambda: real.time() + fake.paso * 40)
            strftime, perf_counter = staticmethod(real.strftime), staticmethod(real.perf_counter)
            sleep = staticmethod(fake.dormir)

        class Ventana:
            def stopped(self): return fake.terminado
            def poll_cmd(self): return None
            def __getattr__(self, name): return lambda *a: ev.append((name,) + a)
        history.ACCOUNT = ""
        core.CACHE, core.time = self.tmp, Reloj
        core.find_client, core.LCU = (lambda conf: ("x",)), (lambda *a: fake)
        core.start_meta = core.detect_account = lambda *a, **k: None
        core.play_phase = lambda conf, fase: ev.append(("sonido", fase))
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
        estados = [e[1] for e in ev if e[0] == "status"]
        self.assertIn("Conectado. Cargando tus datos…", estados)
        self.assertEqual(estados[estados.index("Conectado. Cargando tus datos…") + 1:][:1], [""])     # y deja de decirlo en cuanto llegan
        self.assertTrue(any("Partida en curso" in m for m in msgs))
        self.assertTrue(any("Partida terminada" in m for m in msgs))
        self.assertIn(("analysis.load", "900", YO), ev)                                # se analiza la partida nueva, no la anterior
        guardadas = json.loads(self.leer(f"history_{YO}.json"))
        self.assertEqual(sorted(guardadas), ["100", "101", "900"])
        # la partida nueva se guarda con la línea y el rival bien aunque el cliente etiquete mal («JUNGLE» a tu toplane y al rival)
        self.assertEqual(guardadas["900"]["r"], "TOP")
        g900 = json.loads(self.leer(f"games_{YO}.json"))["900"]
        self.assertEqual((g900["r"], g900["o"], g900["rv"]), ("TOP", 157, 2))      # rival: Yasuo, su toplane (también etiquetado «JUNGLE»)
        self.assertEqual((sorted(g900["p"]), len(g900["a"])), (["a1", "a2", "a3", "a4"], 4))   # y quiénes jugaron contigo
        self.assertEqual(self.leer("history.json"), "")                                # nada va ya al archivo sin dueño
        d = self.leer("diag.log")
        for trozo in ("Cliente de LoL encontrado", "Selección de campeón: cola 420, tipo sr", "Fase: ReadyCheck -> ", "Partida terminada: 900"):
            self.assertIn(trozo, d)
        self.assertNotIn("Prueba", d)                                                  # sin nombres de jugador

    def test_en_partida_el_motor_lee_la_api_en_vivo_y_manda_el_resumen(self):
        import augments
        from cliente_falso import ClienteFalso, live_sample
        original, llamadas = augments.fetch_live, []
        augments.fetch_live = lambda: llamadas.append(1) or live_sample()
        try:
            ev = self.correr(ClienteFalso())
        finally:
            augments.fetch_live = original
        vivos = [e[1] for e in ev if e[0] == "live"]
        self.assertTrue(vivos and llamadas)                                  # se pidió durante la partida y se mandó a la ventana
        self.assertEqual((len(vivos[0]["players"]), vivos[0]["me_team"], vivos[0]["teams"]["CHAOS"]["towers"]), (10, "ORDER", 1))
        self.assertLessEqual(len(llamadas), 3)                               # no se pide en cada vuelta del bucle (cada ~10 s)
        self.assertEqual(self.leer("error.log"), "")

    def test_con_los_datos_en_vivo_desactivados_no_se_manda_nada(self):
        import augments
        from cliente_falso import ClienteFalso, live_sample
        original, llamadas = augments.fetch_live, []
        augments.fetch_live = lambda: llamadas.append(1) or live_sample()
        conf0 = core.load_conf
        core.load_conf = lambda: {**conf0(), "live_enabled": False}
        try:
            ev = self.correr(ClienteFalso())
        finally:
            augments.fetch_live, core.load_conf = original, conf0
        self.assertFalse([e for e in ev if e[0] == "live"])
        self.assertFalse(llamadas)                                           # y ni se lee el puerto salvo en Mayhem

    def test_otra_partida_encontrada_sin_pasar_por_la_cola_suena_otra_vez(self):
        from cliente_falso import ClienteFalso
        fake = ClienteFalso(guion=["None", "Matchmaking", "ReadyCheck", "ReadyCheck", "ReadyCheck", "ReadyCheck", "ReadyCheck", "ChampSelect", "ChampSelect", "None", "None"])
        rc = lambda timer, resp="None", st="InProgress": {"state": st, "playerResponse": resp, "timer": timer}
        # el contador sube; aceptas; alguien no acepta y el cliente enseña otra ventana sin pasar por «En cola» (el contador vuelve a 0)
        fake.rc = {2: rc(1), 3: rc(3, "Accepted"), 4: rc(0.5), 5: rc(2), 6: rc(4, "Accepted")}
        self.correr(fake)
        self.assertEqual(self.leer("diag.log").count("Otra partida encontrada"), 1)
        self.assertEqual(self.leer("error.log"), "")

    def test_cada_partida_encontrada_suena_aunque_se_repita_la_cola(self):
        from cliente_falso import ClienteFalso
        g = ["None", "Matchmaking", "ReadyCheck", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "None", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "None", "None"]
        ev = self.correr(ClienteFalso(guion=g))
        sonidos = [e[1] for e in ev if e[0] == "sonido"]
        self.assertEqual(sonidos.count("found"), 3)        # dos rechazos/esquives y una final: tres veces «encontrada»
        self.assertEqual(self.leer("error.log"), "")

    def test_la_seleccion_llega_a_la_ventana_como_fase(self):
        from cliente_falso import ClienteFalso
        ev = self.correr(ClienteFalso(guion=["None", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "InProgress", "InProgress", "EndOfGame", "None", "None"]))
        fases = [e[1] for e in ev if e[0] == "phase"]
        self.assertIn("ChampSelect", fases)
        self.assertLess(fases.index("ReadyCheck"), fases.index("ChampSelect"))
        self.assertIn("ReadyCheck -> ChampSelect", self.leer("diag.log"))

    def test_un_error_puntual_del_cliente_no_acaba_la_seleccion(self):
        from cliente_falso import ClienteFalso
        g = ["None", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "ChampSelect", "ChampSelect", "InProgress", "InProgress", "EndOfGame", "None", "None"]
        ev = self.correr(ClienteFalso(guion=g, fallos=(5,)))     # un 5xx en mitad de la selección
        diag = self.leer("diag.log")
        self.assertEqual(diag.count("Selección de campeón"), 1)   # no se vuelve a empezar la selección
        self.assertEqual(diag.count("Selección terminada"), 1)
        self.assertEqual(self.leer("error.log"), "")

    def test_el_cliente_cae_a_mitad_de_seleccion_y_vuelve(self):
        from cliente_falso import ClienteFalso
        g = ["None", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "ChampSelect", "ChampSelect", "InProgress", "InProgress", "EndOfGame", "None", "None"]
        self.correr(ClienteFalso(guion=g, caidas=(5,)))
        diag = self.leer("diag.log")
        self.assertIn("Cliente de LoL perdido", diag)
        self.assertEqual(diag.count("Selección de campeón"), 2)   # al volver se empieza una selección nueva con todo limpio
        self.assertIn("Partida terminada: 900", diag)
        self.assertEqual(self.leer("error.log"), "")

    def test_partida_ya_empezada_al_abrir_se_analiza_al_terminar(self):
        from cliente_falso import ClienteFalso
        ev = self.correr(ClienteFalso(guion=["None", "InProgress", "InProgress", "InProgress", "EndOfGame", "None", "None", "None"]))
        diag = self.leer("diag.log")
        self.assertIn("en marcha sin haber visto su selección", diag)
        self.assertIn("Partida terminada: 900", diag)
        self.assertTrue([e for e in ev if e[0] == "analysis.load"])

    def test_partida_que_nunca_aparece_en_el_historial_no_analiza_otra(self):
        from cliente_falso import ClienteFalso
        ev = self.correr(ClienteFalso(guion=["None", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "InProgress", "InProgress", "EndOfGame"] + ["None"] * 14, sin_historial=True))
        diag = self.leer("diag.log")
        self.assertIn("no aparece en el historial", diag)
        self.assertNotIn("Partida terminada: ", diag)
        self.assertFalse([e for e in ev if e[0] == "analysis.load"])

    def test_si_el_cliente_da_9_de_10_jugadores_se_relee(self):
        from cliente_falso import ClienteFalso
        g = ["None", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "InProgress", "InProgress", "InProgress", "InProgress", "InProgress", "InProgress", "EndOfGame", "None", "None"]
        ev = self.correr(ClienteFalso(guion=g, sin_ultimo_hasta=8))
        diag = self.leer("diag.log")
        self.assertIn("9 leídos", diag)
        self.assertIn("ahora 10 leídos (antes 9)", diag)
        self.assertEqual(len([e for e in ev if e[0] == "roster"]), 2)           # primera lectura y la completa
        self.assertEqual(self.leer("error.log"), "")

    def test_una_sola_partida_encontrada_no_suena_dos_veces(self):
        from cliente_falso import ClienteFalso
        fake = ClienteFalso(guion=["None", "Matchmaking", "ReadyCheck", "ReadyCheck", "ReadyCheck", "ChampSelect", "ChampSelect", "None", "None"])
        fake.rc = {2: {"state": "InProgress", "playerResponse": "None", "timer": 1}, 3: {"state": "InProgress", "playerResponse": "Accepted", "timer": 2},
                   4: {"state": "EveryoneReady", "playerResponse": "Accepted", "timer": 3}}
        self.correr(fake)
        self.assertNotIn("Otra partida encontrada", self.leer("diag.log"))

    def test_esquivar_la_partida_no_guarda_ni_analiza_nada(self):
        from cliente_falso import ClienteFalso
        ev = self.correr(ClienteFalso(guion=["None", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "None", "None"]))
        self.assertEqual(self.leer("error.log"), "")
        self.assertTrue([e for e in ev if e[0] == "show"])                              # la selección se llegó a enseñar
        self.assertTrue(any("Selección terminada" in e[2] for e in ev if e[0] == "idle"))
        self.assertFalse([e for e in ev if e[0] in ("roster", "analysis.load")])        # no hubo partida: ni jugadores ni análisis
        self.assertNotIn("Partida terminada", self.leer("diag.log"))
        self.assertEqual(sorted(json.loads(self.leer("history_" + __import__("cliente_falso").YO + ".json"))), ["100", "101"])

    def test_los_pl_ganados_se_guardan_aunque_el_perfil_estuviera_vacio_al_arrancar(self):
        from cliente_falso import ClienteFalso
        import analysis
        ev = self.correr(ClienteFalso(pl=(40, 57)))
        self.assertEqual(self.leer("error.log"), "")
        self.assertIn("Partida terminada: 900", self.leer("diag.log"))
        self.assertEqual(analysis.lp_for(self.tmp, 900)["d"], 17)                      # 40 -> 57: +17, tomado del rango leído al encontrar partida

    def test_remake_se_reconoce_y_no_guarda_variacion_de_pl(self):
        from cliente_falso import ClienteFalso, partida, YO
        import history as h
        self.assertTrue(h.is_remake(partida(1, 86, True, 1, remake=True), YO))
        self.assertFalse(h.is_remake(partida(1, 86, True, 1), YO))
        ev = self.correr(ClienteFalso(remake=True))
        d = self.leer("diag.log")
        self.assertIn("Partida anulada por remake", d)
        self.assertIn("Partida terminada", d)                                          # el cierre sigue su curso (se actualiza el historial)
        self.assertEqual(self.leer("error.log"), "")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "lp.json")))             # y no queda ninguna variación de PL

    def test_save_lp_no_pisa_una_variacion_real_con_un_cero(self):
        import analysis
        tmp = tempfile.mkdtemp()
        analysis.save_lp(tmp, 101, {"d": 17, "now": 57, "tier": "Oro II", "move": ""})
        analysis.save_lp(tmp, 101, {"d": 0, "now": 57, "tier": "Oro II", "move": ""})          # el rango aún no se había actualizado
        self.assertEqual(analysis.lp_for(tmp, 101)["d"], 17)
        analysis.save_lp(tmp, 101, {"d": -20, "now": 37, "tier": "Oro II", "move": ""})        # una variación distinta de cero sí sustituye
        self.assertEqual(analysis.lp_for(tmp, 101)["d"], -20)
        analysis.save_lp(tmp, 102, {"d": 0, "now": 37, "tier": "Oro II", "move": ""})          # y un 0 en una partida nueva sí se guarda
        self.assertEqual(analysis.lp_for(tmp, 102)["d"], 0)

    def test_si_la_cuenta_aun_no_es_conocida_se_reintenta_y_se_guarda_despues(self):
        from cliente_falso import ClienteFalso, YO
        fake = ClienteFalso(guion=["None"] * 8, cuenta_desde=3)
        ev = self.correr(fake)
        d = self.leer("diag.log")
        self.assertIn("cuenta aún desconocida", d)                                      # al principio no sabía quién eres y no guardó nada
        self.assertEqual(self.leer("error.log"), "")
        guardadas = json.loads(self.leer(f"history_{YO}.json"))                          # y al saberlo, el reintento guardó el historial
        self.assertEqual(sorted(guardadas), ["100", "101"])
        self.assertTrue(any("Historial cargado" in e[2] for e in ev if e[0] == "idle"))

    def test_el_cliente_se_cae_en_plena_seleccion_y_vuelve(self):
        from cliente_falso import ClienteFalso
        ev = self.correr(ClienteFalso(guion=["None", "ChampSelect", "ChampSelect", "ChampSelect", "ChampSelect", "None", "None"], caidas={2}))
        enlaces = [e[1] for e in ev if e[0] == "link"]
        self.assertEqual(enlaces[:3], [True, False, True])                              # conectado, caído, y de nuevo conectado
        self.assertEqual(self.leer("error.log"), "")                                    # una caída no es un fallo del programa
        d = self.leer("diag.log")
        self.assertIn("Cliente de LoL perdido", d)
        self.assertGreaterEqual(d.count("Cliente de LoL encontrado"), 2)
        self.assertGreaterEqual(len([e for e in ev if e[0] == "show"]), 2)              # y la selección se vuelve a enseñar al recuperarlo

    def test_aram_y_arena_no_rompen_el_bucle(self):
        from cliente_falso import ClienteFalso
        for modo, tipo in (("aram", "aram"), ("arena", "other")):
            ev = self.correr(ClienteFalso(modo=modo, guion=["None", "ChampSelect", "ChampSelect", "InProgress", "InProgress", "EndOfGame", "None", "None"]))
            self.assertEqual(self.leer("error.log"), "", modo)
            shows = [e[2] for e in ev if e[0] == "show"]
            self.assertTrue(shows, modo)
            self.assertEqual(shows[0]["mode"]["kind"], tipo, modo)
            if modo == "aram":
                self.assertTrue(shows[0]["cands"])                                      # hay campeones del banquillo que recomendar
            else:
                self.assertEqual(shows[0]["cands"], [])                                 # en Arena no se recomienda nada
            self.assertIn("Partida terminada", self.leer("diag.log"), modo)

    def test_reconectar_a_una_partida_en_curso(self):
        from cliente_falso import ClienteFalso
        ev = self.correr(ClienteFalso(guion=["None", "ChampSelect", "InProgress", "Reconnect", "InProgress", "EndOfGame", "None", "None"]))
        self.assertEqual(self.leer("error.log"), "")
        fases = [e[1] for e in ev if e[0] == "phase"]
        self.assertIn("Reconnect", fases)
        self.assertEqual(len([e for e in ev if e[0] == "roster"]), 1)                   # los 10 jugadores se leen una sola vez, no por reconexión

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


class CertificadosRaiz(unittest.TestCase):
    def test_se_suman_los_certificados_de_certifi_a_los_del_sistema(self):
        import ssl
        try:
            import certifi  # noqa: F401
        except ImportError:
            self.skipTest("certifi no está instalado en este Python")
        original = ssl._create_default_https_context
        try:
            base = len(ssl.create_default_context().get_ca_certs())
            self.assertTrue(core.install_certs())
            ctx = ssl._create_default_https_context()
            self.assertGreater(len(ctx.get_ca_certs()), base)           # ahora hay más raíces de confianza
            self.assertTrue(ctx.check_hostname)                         # y se sigue verificando el nombre del servidor
            self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)        # y el certificado
            self.assertIsNot(core.CTX, ctx)                             # el contexto sin verificar del cliente de LoL es otro
            self.assertEqual(core.CTX.verify_mode, ssl.CERT_NONE)
        finally:
            ssl._create_default_https_context = original

    def test_sin_certifi_no_falla(self):
        import ssl
        original, mod = ssl._create_default_https_context, sys.modules.get("certifi")
        sys.modules["certifi"] = None                                    # fuerza el ImportError
        try:
            self.assertFalse(core.install_certs())
            self.assertIs(ssl._create_default_https_context, original)   # y no toca nada
        finally:
            ssl._create_default_https_context = original
            if mod is None:
                sys.modules.pop("certifi", None)
            else:
                sys.modules["certifi"] = mod


class PreparacionDeLaPublicacion(unittest.TestCase):
    def test_notas_de_la_publicacion_salen_de_novedades_y_dicen_lo_no_probado(self):
        import publicar
        e = {"v": "9.9.9", "titulo": "Un título", "items": [("arreglo", "Arregla algo."), ("nuevo", "Añade algo.")]}
        t = publicar.notas_markdown(e, "el flujo de una partida completa.")
        self.assertTrue(t.startswith("Un título.\n\n- **Arreglo:** Arregla algo.\n- **Nuevo:** Añade algo.\n"))
        self.assertIn("instala esta a mano una vez", t)
        self.assertTrue(t.rstrip().endswith("Sin probar todavía: el flujo de una partida completa."))
        for tipo, _ in __import__("novedades").NOTES[0]["items"]:           # todos los tipos reales tienen etiqueta propia
            self.assertIn(tipo, publicar.TIPOS)

    def test_los_archivos_de_release_se_verifican(self):
        import hashlib, publicar
        rel = tempfile.mkdtemp()
        self.assertTrue(publicar.problemas_de_artefactos(rel, "1.0.0"))                  # no hay nada
        exe = os.path.join(rel, "Instalar-LOL-E-1.0.0.exe")
        open(exe, "wb").write(b"x" * 6_000_000)
        open(os.path.join(rel, "LOL-E-1.0.0.zip"), "wb").write(b"z")
        info = {"version": "1.0.0", "url": "https://github.com/a/b/releases/latest/download/Instalar-LOL-E-1.0.0.exe",
                "sha256": hashlib.sha256(open(exe, "rb").read()).hexdigest()}
        json.dump(info, open(os.path.join(rel, "latest.json"), "w"))
        self.assertEqual(publicar.problemas_de_artefactos(rel, "1.0.0"), [])
        json.dump({**info, "sha256": "0" * 64}, open(os.path.join(rel, "latest.json"), "w"))
        self.assertIn("la huella SHA-256 de latest.json no es la del instalador", publicar.problemas_de_artefactos(rel, "1.0.0"))
        json.dump({**info, "version": "0.9.0"}, open(os.path.join(rel, "latest.json"), "w"))
        self.assertTrue(any("latest.json dice 0.9.0" in m for m in publicar.problemas_de_artefactos(rel, "1.0.0")))
        json.dump({**info, "url": "https://github.com/a/b/releases/latest/download/Instalar-LOL-E-0.9.0.exe"}, open(os.path.join(rel, "latest.json"), "w"))
        self.assertTrue(any("no apunta al instalador" in m for m in publicar.problemas_de_artefactos(rel, "1.0.0")))


GAREN = {"icon": "Garen", "name": "Garen"}


class BuildSinRed(unittest.TestCase):
    def setUp(self):
        import builds, tempfile
        self.b, self.d = builds, tempfile.mkdtemp()

    def guardada(self, edad):
        import json, os, time
        p = self.b._path(self.d, GAREN, "top", None)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump({"ts": time.time() - edad, "data": {"v": 3, "runes": {"keystone": 1}, "items": {"core": [1]}, "patch": "26.21"}}, open(p, "w"))

    def pagina(self, texto):
        import io
        from unittest import mock
        r = mock.MagicMock()
        r.__enter__.return_value.read.return_value = texto.encode()
        return mock.patch("builds.urllib.request.urlopen", return_value=r)

    def test_sin_red_se_usa_lo_guardado_con_su_marca(self):
        from unittest import mock
        self.guardada(self.b.TTL + 100)
        with mock.patch("builds.urllib.request.urlopen", side_effect=OSError("sin red")):
            d = self.b.load(self.d, GAREN, "top")
        self.assertTrue(d["stale"])
        self.assertEqual(d["patch"], "26.21")
        import ui_build
        self.assertIn("últimos datos guardados", ui_build.source_note(d))

    def test_sin_red_ni_guardado_el_error_es_claro(self):
        from unittest import mock
        with mock.patch("builds.urllib.request.urlopen", side_effect=OSError("sin red")):
            with self.assertRaises(RuntimeError) as cm:
                self.b.load(self.d, GAREN, "top")
        self.assertIn("No se pudo leer", str(cm.exception))

    def test_pagina_con_otro_formato_se_avisa(self):
        self.guardada(self.b.TTL + 100)
        with self.pagina("<html>" + "x" * 6000 + "</html>"):
            d = self.b.load(self.d, GAREN, "top")          # hay guardado: se usa, pero marcado
        self.assertTrue(d.get("stale"))
        import shutil, tempfile
        vacio = tempfile.mkdtemp()
        with self.pagina("<html>" + "x" * 6000 + "</html>"):
            with self.assertRaises(RuntimeError) as cm:
                self.b.load(vacio, GAREN, "top")
        self.assertIn("cambiado el formato", str(cm.exception))


class MetaSinRed(unittest.TestCase):
    def test_sin_red_se_usa_el_ultimo_meta_guardado(self):
        import json, os, tempfile, time
        from unittest import mock
        import meta
        d = tempfile.mkdtemp()
        json.dump({"ts": time.time() - 99 * 3600, "patch": "16.20", "current": "16.20", "tier": "gold_plus", "avg": {"top": 50},
                   "lanes": {"top": {"10": {"wr": 51.0, "pr": 1, "br": 1, "games": 500, "d": 0}}}}, open(os.path.join(d, "meta.json"), "w"))
        with mock.patch("meta.urllib.request.urlopen", side_effect=OSError("sin red")):
            m = meta.load(d, "16.21.1", "gold_plus")
            self.assertTrue(m["stale"])
            self.assertIn(10, m["lanes"]["top"])                       # claves convertidas a entero como siempre
            with self.assertRaises(RuntimeError):
                meta.load(tempfile.mkdtemp(), "16.21.1", "gold_plus")  # sin nada guardado sigue fallando con claridad


class InformeDeDiagnostico(unittest.TestCase):
    def test_incluye_el_estado_de_los_datos_sin_rutas_personales(self):
        import lol_advisor as l
        txt = l.diagnostics(["Ajustes: x=sí"])
        for k in ("Esquema de datos", "Partidas de la Grieta", "Ajustes: x=sí"):
            self.assertIn(k, txt)
        self.assertNotIn(os.path.expanduser("~") + os.sep + "Documents", txt.replace("\\", os.sep))   # las rutas personales se abrevian con ~


class Op_ggSinRed(unittest.TestCase):
    def test_sin_red_se_usa_lo_guardado_y_se_marca(self):
        import json, os, tempfile, time
        from unittest import mock
        import opgg_builds, aram_builds, trends, matchups
        d = tempfile.mkdtemp()
        champ = {"icon": "Garen", "name": "Garen"}
        os.makedirs(os.path.join(d, "builds"))
        for mod, nombre, arg in ((opgg_builds, f"opgg_{matchups.slug(champ)}_top.json", "top"), (aram_builds, f"mode_aram_{matchups.slug(champ)}.json", "aram")):
            json.dump({"ts": time.time() - 99 * 86400, "data": {"v": 1, "core": [1], "boots": [2]}}, open(os.path.join(d, "builds", nombre), "w"))
            with mock.patch.object(mod, "_fetch", side_effect=OSError("sin red")):
                r = mod.load(d, champ, arg)
            self.assertTrue(r["stale"])
            with mock.patch.object(mod, "_fetch", return_value="<html>otro formato</html>"):
                self.assertTrue(mod.load(d, champ, arg)["stale"])                 # la página cambió y ya no se sabe leer: también lo guardado
        vacio = tempfile.mkdtemp()
        with mock.patch.object(opgg_builds, "_fetch", side_effect=OSError("sin red")):
            with self.assertRaises(OSError):
                opgg_builds.load(vacio, champ, "top")                              # sin nada guardado sigue fallando
        json.dump({"v": trends.VERSION, "ts": time.time() - 99 * 3600, "patch": "16.20", "region": "all", "lanes": {"top": {"1": {"g": 5}}}}, open(os.path.join(d, "trends.json"), "w"))
        with mock.patch.object(trends, "_fetch", return_value={}):
            self.assertTrue(trends.load(d, "16.21")["stale"])


class PuestoOpgg(unittest.TestCase):
    def test_si_la_pagina_pierde_el_puesto_se_conserva_el_ultimo(self):
        import json, tempfile, time
        from unittest import mock
        import lol_advisor as l
        tmp = tempfile.mkdtemp()
        conf = {"opgg_name": "N", "opgg_tag": "T", "opgg_region": "euw", "opgg_enabled": True, "opgg_update_hours": 0, "opgg_update_games": 0}
        champs = "".join('{"id":%d,"play":10,"win":5,"lose":5,"match_up_stats":[]}' % i for i in range(1, 7))
        con = champs + 'Ladder Rank <span class="x">1,000</span> (12.5% of top)'
        sin = champs
        old_cache, old_try = l.CACHE, l._opgg_last_try
        l.CACHE = tmp
        try:
            for html, esperado in ((con, {"rank": 1000, "top": 12.5}), (sin, {"rank": 1000, "top": 12.5})):
                l._opgg_last_try = 0
                with mock.patch.object(l, "fetch_opgg", return_value=html):
                    l.maybe_update_opgg(conf, {}, {"games": 5}, force=True)
                self.assertEqual(json.load(open(l.opgg_path(conf)))["ladder"], esperado)
        finally:
            l.CACHE, l._opgg_last_try = old_cache, old_try


class MetaFormato(unittest.TestCase):
    def prueba(self, wr):
        import io, json
        from unittest import mock
        import meta
        cuerpo = json.dumps({"avgWr": 50, "cid": {str(i): {"wr": wr, "pr": 1, "br": 1, "games": 500, "lane": "top"} for i in range(1, 8)}}).encode()
        r = mock.MagicMock()
        r.__enter__.return_value.read.return_value = cuerpo
        with mock.patch("meta.urllib.request.urlopen", return_value=r):
            return meta._fetch("16.21", "top", "gold_plus")

    def test_tasas_en_porcentaje_se_aceptan_y_otras_escalas_se_rechazan(self):
        self.assertEqual(len(self.prueba(51.5)[0]), 7)
        with self.assertRaises(ValueError):
            self.prueba(0.515)                      # la web pasó a fracciones
        with self.assertRaises(ValueError):
            self.prueba(515)                        # o a décimas de punto


class ReservaSoloSiEncaja(unittest.TestCase):
    def test_tendencias_de_otra_region_y_meta_de_otro_rango_no_sirven_de_reserva(self):
        import json, os, tempfile, time
        from unittest import mock
        import meta, trends
        d = tempfile.mkdtemp()
        json.dump({"v": trends.VERSION, "ts": time.time() - 99 * 3600, "patch": "16.20", "region": "euw", "lanes": {"top": {"1": {"g": 5}}}}, open(os.path.join(d, "trends.json"), "w"))
        with mock.patch.object(trends, "_fetch", return_value={}):
            with self.assertRaises(RuntimeError):
                trends.load(d, "16.21", region="na")                 # lo guardado es de euw: no se enseña como si fuera de na
            self.assertTrue(trends.load(d, "16.21", region="euw")["stale"])
        json.dump({"ts": time.time() - 99 * 3600, "patch": "16.20", "current": "16.20", "tier": "silver_plus", "avg": {"top": 50},
                   "lanes": {"top": {"10": {"wr": 51.0, "pr": 1, "br": 1, "games": 500, "d": 0}}}}, open(os.path.join(d, "meta.json"), "w"))
        with mock.patch("meta.urllib.request.urlopen", side_effect=OSError("sin red")):
            with self.assertRaises(RuntimeError):
                meta.load(d, "16.21.1", "gold_plus")                 # lo guardado es de Plata+: no sirve para Oro+

    def test_build_obsoleta_se_reintenta_pasado_un_rato(self):
        import time
        from unittest import mock
        import builds
        llamadas = []
        def load(*a, **k):
            llamadas.append(1)
            return {"stale": True} if len(llamadas) == 1 else {"ok": 1}
        champ = {"icon": "Zed", "name": "Zed"}
        with mock.patch.object(builds, "load", load):
            key = builds.request("x", champ, "mid")
            for _ in range(50):
                if builds.peek(key)[0] != "loading": break
                time.sleep(.02)
            self.assertTrue(builds.peek(key)[1]["stale"])
            builds.request("x", champ, "mid")                          # antes de 5 min: no se vuelve a pedir
            time.sleep(.1); self.assertEqual(len(llamadas), 1)
            builds._stale_at[key] = time.time() - builds.STALE_RETRY - 1
            builds.request("x", champ, "mid")                          # pasado el plazo: se reintenta y llega lo bueno
            for _ in range(50):
                if not builds.peek(key)[1].get("stale"): break
                time.sleep(.02)
            self.assertEqual(builds.peek(key)[1], {"ok": 1})

    def test_un_cero_real_cuenta_en_la_media_por_minuto(self):
        import analysis
        g = lambda i, v: {"id": str(i), "c": 1, "q": 420, "k": 1, "de": 1, "a": 1, "cs": 10, "d": 1800, "dm": 1000, "v": v, "w": True}
        r = analysis.vs_average(g(100, 30), [g(1, 0), g(2, 0), g(3, 30)])
        self.assertAlmostEqual(r["vpm"][1], 30 / 90)                  # (0+0+30) puntos en 90 minutos: los ceros cuentan


class PaginasDeRunas(unittest.TestCase):
    D = {"header": {"n": 1000}, "summary": {"runes": {
        "pick": {"wr": 52.5, "n": 600, "set": {"pri": [8010, 9111, 9105, 8299], "sec": [8451, 8444], "mod": [5008, 5008, 5001]}},
        "win": {"wr": 53.3, "n": 300, "set": {"pri": [8230, 8224, 8234, 8236], "sec": [8444, 8451], "mod": [5008, 5010, 5013]}}}}}

    def test_dos_paginas_con_su_porcentaje_y_uso(self):
        import builds
        r = builds.parse_rune_pages(self.D)
        self.assertEqual([p["label"] for p in r], ["Más usada", "Mayor % de victorias"])
        self.assertEqual((r[0]["wr"], r[0]["n"], r[0]["pr"]), (52.5, 600, 60.0))
        self.assertEqual(r[1]["runes"], {"keystone": 8230, "primary": [8224, 8234, 8236], "secondary": [8444, 8451], "shards": [5008, 5010, 5013]})

    def test_si_son_la_misma_pagina_queda_una_con_las_dos_etiquetas(self):
        import builds, copy
        d = copy.deepcopy(self.D)
        d["summary"]["runes"]["win"] = copy.deepcopy(d["summary"]["runes"]["pick"])
        r = builds.parse_rune_pages(d)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["label"], "Más usada y mayor % de victorias")

    def test_una_forma_distinta_no_pinta_datos_falsos(self):
        import builds, copy
        self.assertEqual(builds.parse_rune_pages({}), [])
        self.assertEqual(builds.parse_rune_pages({"summary": {"runes": {}}}), [])
        d = copy.deepcopy(self.D)
        d["summary"]["runes"]["pick"]["wr"] = 0.525                       # otra escala
        self.assertEqual([p["id"] for p in builds.parse_rune_pages(d)], ["win"])
        d["summary"]["runes"]["win"]["set"]["pri"] = [1, 2]               # y una página incompleta
        self.assertEqual(builds.parse_rune_pages(d), [])


class EstiloYTarjeta(unittest.TestCase):
    def g(self, i, de=3, k=5, a=8, cs=150, d=1800, v=20, r="MIDDLE"):
        return {"id": str(i), "t": 1_800_000_000_000 - i * 86_400_000, "d": d, "c": 86, "w": True, "k": k, "de": de, "a": a, "cs": cs, "v": v, "r": r, "gm": "CLASSIC"}

    def test_estilos(self):
        import wrapped
        n = lambda **kw: wrapped.style([self.g(i, **kw) for i in range(12)])[0]
        self.assertEqual(n(de=15), "El kamikaze")                      # 15 muertes en 30 min = 0,5 por minuto
        self.assertEqual(n(de=2), "El superviviente")
        self.assertEqual(n(de=8, cs=240), "El granjero")               # 8 cs/min
        self.assertEqual(n(de=8, cs=100, v=60), "El vigía")            # 2 de visión por minuto
        self.assertEqual(n(de=8, cs=100, v=10, k=3, a=9), "El asistente")
        self.assertEqual(n(de=8, cs=100, v=10, k=5, a=8), "El todoterreno")
        self.assertIsNone(wrapped.style([self.g(i) for i in range(5)]))   # pocas partidas

    def test_tarjeta_de_partida(self):
        import wrapped, tempfile, os
        out = os.path.join(tempfile.mkdtemp(), "p.png")
        wrapped.render_game(dict(self.g(1), dm=23000), lambda c: "Ahri", lambda c: None, out, {"d": 21, "now": 45, "tier": "Oro II"}, ["KDA 3,1 frente a tu media de 2,4."])
        self.assertGreater(os.path.getsize(out), 5000)
        out2 = os.path.join(tempfile.mkdtemp(), "q.png")
        wrapped.render_game({"id": "9", "t": 1_800_000_000_000, "c": 1, "w": False, "rm": True, "k": None}, lambda c: "?", lambda c: None, out2)   # sin detalle ni PL: no falla
        self.assertTrue(os.path.exists(out2))


class ResumenDelAnio(unittest.TestCase):
    NOW = 1_800_000_000_000

    def g(self, i, dias, w, c=86, d=1800, k=5, de=3, a=7):
        return {"id": str(i), "t": self.NOW - int(dias * 86_400_000), "d": d, "c": c, "w": w, "k": k, "de": de, "a": a}

    def test_cifras(self):
        import wrapped
        games = [self.g(i, i, i % 3 != 0, c=86 if i % 2 else 122) for i in range(1, 13)]
        s = wrapped.compute(games, self.NOW, "all")
        self.assertEqual((s["n"], s["wins"], s["losses"]), (12, 8, 4))
        self.assertAlmostEqual(s["hours"], 12 * 1800 / 3600)
        self.assertEqual(s["kills"], 60)
        self.assertEqual(s["top"][0][1], 6)
        self.assertGreaterEqual(s["best_streak"][0], 2)
        self.assertTrue(wrapped.lines(s, lambda c: str(c)))

    def test_util_y_curiosidades_dicen_muestra_y_fecha(self):
        import wrapped
        games = [self.g(i, i, i % 5 != 0, c=86 if i % 2 else 122, d=1800 + i * 60) for i in range(1, 25)]   # rachas de 4 victorias
        s = wrapped.compute(games, self.NOW, "all")
        util, cur = wrapped.useful(s, lambda c: f"C{c}"), wrapped.curious(s, lambda c: f"C{c}")
        self.assertTrue(all({"title", "value", "detail", "tone"} <= set(r) for r in util + cur))
        mejor = next(r for r in util if r["title"] == "Tu mejor campeón")
        self.assertRegex(mejor["detail"], r"en \d+ partidas")                              # dice sobre cuántas partidas
        larga = next(r for r in cur if r["title"] == "Partida más larga")
        self.assertRegex(larga["detail"], r"\d\d/\d\d/\d{4}")                              # y cuándo fue
        racha = next(r for r in cur if r["title"] == "Mejor racha")
        self.assertIn(" al ", racha["detail"])                                              # con inicio y fin
        self.assertIn("Periodo", "Periodo " + wrapped.period(s))

    def test_pocas_partidas_o_fuera_del_anio(self):
        import wrapped
        games = [self.g(i, i, True) for i in range(1, 9)]
        self.assertIsNone(wrapped.compute(games, self.NOW, "all"))                         # solo 8
        viejas = [self.g(i, 700 + i, True) for i in range(1, 15)]
        self.assertIsNone(wrapped.compute(viejas, self.NOW, "year"))                       # de hace casi 2 años
        self.assertIsNotNone(wrapped.compute(viejas, self.NOW, "all"))

    def test_remakes_y_entradas_sin_detalle(self):
        import wrapped
        games = [self.g(i, i, True) for i in range(1, 12)] + [dict(self.g(99, 1, False), rm=True)]
        games.append({"id": "x", "t": self.NOW - 1000, "d": 0, "c": 86, "w": False, "k": None, "de": None, "a": None})
        s = wrapped.compute(games, self.NOW, "all")
        self.assertEqual(s["n"], 12)                                                      # sin el remake
        self.assertEqual(s["kda_n"], 11)                                                  # y la entrada sin detalle no cuenta para el KDA

    def test_imagen(self):
        import wrapped, tempfile, os
        games = [self.g(i, i, i % 2 == 0, c=[86, 122, 54][i % 3]) for i in range(1, 20)]
        s = wrapped.compute(games, self.NOW, "all")
        out = os.path.join(tempfile.mkdtemp(), "r.png")
        wrapped.render(s, lambda c: str(c), lambda c: None, out)
        self.assertGreater(os.path.getsize(out), 5000)


class DondeMueres(unittest.TestCase):
    def test_zonas_del_mapa(self):
        import patrones
        self.assertEqual(patrones.zone(7400, 7400, 100), "río")
        self.assertEqual(patrones.zone(1000, 1000, 100), "línea")
        self.assertEqual(patrones.zone(7400, 1200, 100), "línea")        # línea de abajo
        self.assertEqual(patrones.zone(11000, 6000, 100), "jungla rival")
        self.assertEqual(patrones.zone(4000, 6000, 100), "jungla propia")
        self.assertEqual(patrones.zone(11000, 6000, 200), "jungla propia")   # el equipo rojo lo ve al revés

    def partida(self, pos_x, n):
        mins = list(range(0, 21))
        pl = {"pid": 1, "team": 100, "role": "TOP", "pos": [[pos_x, 6000]] * 21}
        return {"queue": 420, "win": False, "me": 1, "team": 100, "minutes": mins, "players": {"1": pl},
                "kills": [{"t": 5 + i, "killer": 2, "victim": 1, "assists": []} for i in range(n)]}

    def test_mapa_y_frase(self):
        import patrones
        dm = patrones.death_map([self.partida(11000, 3) for _ in range(4)] + [self.partida(4000, 1)])
        self.assertEqual(dm, {"jungla rival": 12, "jungla propia": 1})
        self.assertIn("92 %", patrones.death_sentence(dm))
        self.assertIsNone(patrones.death_map([self.partida(11000, 3)]))                   # muy pocas muertes
        self.assertIsNone(patrones.death_sentence({"línea": 10, "jungla propia": 3}))      # morir en tu línea no es un patrón de posicionamiento


class TemporizadorDelBaron(unittest.TestCase):
    def test_avisa_cerca_del_spawn_y_tras_una_muerte(self):
        import live
        s = lambda t, kills=(): {"mode": "CLASSIC", "t": t, "baron_kills": list(kills), "teams": {"ORDER": {"grubs": 3}}}   # larvas ya matadas: aquí solo cuenta el Barón
        self.assertIsNone(live.timers(s(600)))                                   # lejos
        self.assertIn("aparece en 0:45", live.timers(s(1155)))
        self.assertIn("disponible", live.timers(s(1230)))
        self.assertIsNone(live.timers(s(1600)))                                  # hace mucho que debería haber salido: se calla
        self.assertIn("reaparece en 0:50", live.timers(s(1510, [1200])))         # murió a los 20:00: vuelve a los 26:00 (1560)
        self.assertIsNone(live.timers(s(1300, [1200])))                          # aún falta mucho
        self.assertIsNone(live.timers({"mode": "ARAM", "t": 1190}))              # ARAM no tiene Barón

    def test_dragon(self):
        import live
        s = lambda t, dk=(): {"mode": "CLASSIC", "t": t, "drake_kills": list(dk), "baron_kills": [], "teams": {"ORDER": {"grubs": 3}}}
        self.assertIn("dragón aparece en 0:20", live.timers(s(280)))
        self.assertIn("reaparece en 0:30", live.timers(s(870, [(600, "Fire")])))
        self.assertIsNone(live.timers(s(700, [(600, "Fire")])))
        four = [(300, "Fire"), (700, "Water"), (1100, "Earth"), (1500, "Air")]
        con_alma = lambda t, dk: {**s(t, dk), "teams": {"ORDER": {"dragons": 4}, "CHAOS": {"dragons": 0}}}
        repartidos = lambda t, dk: {**s(t, dk), "teams": {"ORDER": {"dragons": 2}, "CHAOS": {"dragons": 2}}}
        self.assertIsNone(live.timers(con_alma(1790, four)))                 # con el alma tomada (4 de un equipo) no se avisa
        self.assertIn("reaparece", live.timers(repartidos(1790, four)) or "")    # 2-2: nadie tiene el alma y el dragón sigue reapareciendo

    def test_inhibidores(self):
        import live
        s = lambda t, kills, me="ORDER": {"mode": "CLASSIC", "t": t, "me_team": me, "inhib_kills": kills, "teams": {"ORDER": {"heralds": 1, "grubs": 3}, "CHAOS": {}}}
        self.assertIn("Tu inhibidor reaparece en 3:20", live.timers(s(1000, [(900.0, "ORDER")])))
        self.assertIn("Un inhibidor rival reaparece en 4:00", live.timers(s(1000, [(940.0, "CHAOS")])))
        self.assertNotIn("inhibidor", live.timers(s(1300, [(900.0, "ORDER")])) or "")      # ya reapareció
        d = {"allPlayers": [{"championName": "Ahri", "team": "ORDER", "scores": {}, "items": []}], "activePlayer": {},
             "events": {"Events": [{"EventName": "InhibKilled", "EventTime": 905.0, "InhibKilled": "Inhib_TOrder_L1_P1_1234", "KillerName": "x"}]}, "gameData": {"gameTime": 1000, "gameMode": "CLASSIC"}}
        self.assertEqual(live.summarize(d, {})["inhib_kills"], [(905.0, "ORDER")])          # de qué equipo era (no de quien lo mató)

    def test_heraldo(self):
        import live
        s = lambda t, h=0: {"mode": "CLASSIC", "t": t, "teams": {"ORDER": {"heralds": h, "grubs": 3}, "CHAOS": {"heralds": 0, "grubs": 0}}}
        self.assertIn("Heraldo de la Grieta aparece en 0:30", live.timers(s(870)))
        self.assertIn("sigue en la Grieta hasta el 19:45", live.timers(s(1000)))
        self.assertIsNone(live.timers(s(1000, 1)))             # ya lo han matado
        self.assertNotIn("Heraldo", live.timers(s(1190)) or "")   # ya se fue (y ahora toca el aviso del Barón)
        self.assertIsNone(live.timers(s(600)))                 # aún falta mucho

    def test_larvas_del_vacio(self):
        import live
        s = lambda t, grubs=0: {"mode": "CLASSIC", "t": t, "teams": {"ORDER": {"grubs": grubs}, "CHAOS": {"grubs": 0}}}
        self.assertIn("aparecen en 0:30", live.timers(s(450)))
        self.assertIn("hasta el 14:45", live.timers(s(600)))
        self.assertIsNone(live.timers(s(600, 3)))          # ya las han matado
        self.assertNotIn("larvas", live.timers(s(900)) or "")   # ya se fueron

    def test_resumen_trae_las_muertes_del_baron(self):
        import live
        d = {"allPlayers": [{"championName": "Ahri", "team": "ORDER", "scores": {}, "items": []}], "activePlayer": {},
             "events": {"Events": [{"EventName": "BaronKill", "EventTime": 1250.5, "KillerName": "x"}]}, "gameData": {"gameTime": 1300, "gameMode": "CLASSIC"}}
        self.assertEqual(live.summarize(d, {})["baron_kills"], [1250.5])


class PatronesRepetidos(unittest.TestCase):
    def partida(self, win, muertes_pronto, cs_dif=0, oro_dif=0):
        mins = list(range(0, 21))
        pl = lambda pid, team, cs, gold: {"pid": pid, "team": team, "role": "MIDDLE", "k": 0, "d": 0, "a": 0, "dmg": 1, "gold": 1, "cs": 1, "lvl": 1,
                                         "cs_s": [cs * m / 20 for m in mins], "gold_s": [gold * m / 20 for m in mins],
                                         "xp_s": [0] * 21, "lvl_s": [1] * 21}
        return {"queue": 420, "win": win, "me": 1, "team": 100, "minutes": mins,
                "players": {"1": pl(1, 100, 200 + cs_dif * 2, 10000 + oro_dif * 20 / 15 * 0 + oro_dif * 4 / 3), "2": pl(2, 200, 200, 10000)},
                "kills": [{"t": 3 + i, "killer": 2, "victim": 1, "assists": []} for i in range(muertes_pronto)]}

    def test_patron_en_derrotas(self):
        import patrones
        g = [self.partida(False, 2) for _ in range(5)] + [self.partida(True, 0) for _ in range(4)] + [self.partida(False, 0)]
        p = patrones.find(g)
        self.assertEqual(p["clave"], "muertes_pronto")
        self.assertEqual((p["derrotas"], p["victorias"]), ((5, 6), (0, 4)))
        self.assertIn("5 de 6", patrones.sentence(p))

    def test_sin_muestra_o_sin_diferencia_no_dice_nada(self):
        import patrones
        self.assertIsNone(patrones.find([self.partida(False, 2) for _ in range(5)]))                              # solo 5 partidas
        mix = [self.partida(w, 2) for w in (False, True) * 5]
        self.assertIsNone(patrones.find(mix))                                                                      # igual en victorias que en derrotas
        self.assertIsNone(patrones.sentence(None))

    def test_objetivo_sale_del_patron(self):
        import patrones
        g = [self.partida(False, 2) for _ in range(5)] + [self.partida(True, 0) for _ in range(4)] + [self.partida(False, 0)]
        self.assertIn("minuto 15", patrones.goal(patrones.find(g)))
        self.assertIsNone(patrones.goal(None))

    def test_resultado_del_objetivo(self):
        import patrones
        p = {"clave": "muertes_pronto"}
        ok, txt = patrones.result(self.partida(True, 1), p)
        self.assertTrue(ok)
        self.assertTrue(txt.startswith("Objetivo cumplido"))
        self.assertFalse(patrones.result(self.partida(False, 3), p)[0])
        self.assertIsNone(patrones.result(self.partida(True, 0), None))
        self.assertIsNone(patrones.result(dict(self.partida(True, 0), queue=450), p))

    def test_ignora_colas_sin_linea(self):
        import patrones
        g = [dict(self.partida(False, 2), queue=450) for _ in range(10)]
        self.assertIsNone(patrones.find(g))


class PicosDelRival(unittest.TestCase):
    def snap(self, t, lvl, value, mine=5):
        mk = lambda cid, team, me, level, v: {"cid": cid, "team": team, "me": me, "level": level, "value": v, "items": [], "k": 0, "d": 0, "a": 0}
        return {"t": t, "players": [mk(1, "ORDER", True, mine, 3000), mk(2, "CHAOS", False, lvl, value)]}

    def test_nivel_y_compra(self):
        import live
        a, b = self.snap(300, 5, 3000), self.snap(310, 6, 5000)
        out = live.spikes(a, b, 2)
        self.assertEqual(len(out), 2)
        self.assertIn("nivel 6 y tú aún no", out[0])
        self.assertIn("2.0", out[1].replace(",", "."))

    def test_sin_aviso_sin_cambios_o_sin_rival(self):
        import live
        a = self.snap(300, 6, 3000)
        self.assertEqual(live.spikes(a, self.snap(310, 6, 3500), 2), [])      # ya era 6 y la compra es pequeña
        self.assertEqual(live.spikes(None, a, 2), [])
        self.assertEqual(live.spikes(a, a, 0), [])                            # no se sabe quién es el rival
        self.assertEqual(live.spikes(self.snap(400, 5, 0), self.snap(300, 6, 9999), 2), [])   # una lectura más vieja: no se mezcla


class TourDeLaDemostracion(unittest.TestCase):
    def test_las_lecciones_son_validas(self):
        import tour
        self.assertEqual(set(tour.RECORRIDO) - set(tour.LESSONS), set())
        validos = set(tour.TARGETS) | set(tour.REGISTRADOS)
        for lid, lesson in tour.LESSONS.items():
            self.assertTrue(lesson["steps"], lid)
            for i, s in enumerate(lesson["steps"]):
                donde = f"{lid} paso {i + 1}"
                self.assertIn(s["scene"], (None,) + tour.SCENES, donde)
                self.assertIn(s["page"], (None,) + tour.PAGES, donde)
                self.assertIn(s.get("act"), (None,) + tour.ACTS, donde)
                self.assertTrue(s["target"] is None or s["target"] in validos, f"{donde}: el elemento «{s['target']}» no existe")
                self.assertLessEqual(len(s["title"].split()), 5, f"{donde}: el título debe tener de 3 a 5 palabras")
                self.assertLessEqual(tour.words(s["text"]), 30, f"{donde}: el texto debe ser corto (unas 25 palabras)")

    def test_las_preguntas_de_la_ayuda_enlazan_con_lecciones_reales(self):
        import ayuda, tour
        ids = {t[0] for t in ayuda.TOPICS}
        for pregunta, leccion in tour.PREGUNTAS.items():
            self.assertIn(pregunta, ids)
            self.assertIn(leccion, tour.LESSONS)
        self.assertIn("runas_builds", tour.PREGUNTAS)       # la pregunta estrella tiene su lección
        self.assertIn("en_partida", tour.PREGUNTAS)

    def test_todos_los_ids_registrados_se_anotan_en_alguna_pantalla(self):
        import tour
        codigo = " ".join(open(os.path.join(ROOT, f), encoding="utf-8").read() for f in os.listdir(ROOT) if f.startswith("ui_") and f.endswith(".py"))
        for tid in tour.REGISTRADOS:
            self.assertIn(f'reg("{tid}"', codigo, f"nadie anota «{tid}»: el tour no lo encontraría")

    def test_los_datos_de_ejemplo_son_deterministas_y_no_son_de_nadie(self):
        import demo_data
        a, b = demo_data.history_entries(1_800_000_000_000), demo_data.history_entries(1_800_000_000_000)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 80)
        self.assertEqual(demo_data.PROFILE["name"], "Jugador")


class MejoresContraRivales(unittest.TestCase):
    def test_objetivos_rival_de_linea_primero_y_el_resto_por_su_linea(self):
        import ui_sections
        champs = {1: {"pos": ["TOP"]}, 2: {"pos": ["UTILITY"]}, 3: {"pos": []}, 4: {"pos": ["MIDDLE"]}}
        cp = ui_sections.CounterPicks.__new__(ui_sections.CounterPicks)
        cp.ui = type("U", (), {"champs": champs})()
        r = {"role": "TOP", "lane_opp": 4, "enemies": [1, 2, 3, 4, 99]}
        self.assertEqual(cp.targets({"r": r}), [(4, "top", True), (1, "top", False), (2, "support", False)])
        r["lane_opp"] = 0   # sin rival de línea conocido: solo los demás
        self.assertEqual([t[0] for t in cp.targets({"r": r})], [1, 2, 4])


class ContrarrestosNombres(unittest.TestCase):
    def test_nombres_con_apostrofo_y_signo_y(self):
        import matchups as m
        self.assertEqual(m.norm("Cho&#39;Gath"), m.norm("Cho'Gath"))
        self.assertEqual(m.norm("Kai&#39;Sa"), "kaisa")
        self.assertEqual(m.norm("Nunu &amp; Willump"), m.norm("Nunu y Willump"))

    def test_el_selector_de_rival_tiene_su_constante_de_reintento(self):
        import ui_opp
        self.assertEqual(ui_opp.RETRY, 60)   # un salto de línea escrito dentro de un comentario la dejó sin definir y rompía el selector tras cualquier error de datos


class FuentesSinMartilleo(unittest.TestCase):
    def test_una_build_que_falla_no_se_vuelve_a_pedir_en_cada_repintado(self):
        import builds, time as _t
        llamadas = []
        orig = builds.load
        def falla(*a, **k):
            llamadas.append(1)
            raise RuntimeError("sin datos")
        builds.load = falla
        builds._state.clear()
        champ = {"icon": "Ahri", "name": "Ahri"}
        try:
            for _ in range(5):
                builds.request("x", champ, "middle")
                _t.sleep(0.15)
            self.assertEqual(len(llamadas), 1)
            self.assertEqual(builds.peek(("ahri", "middle", ""))[0], "error")
        finally:
            builds.load = orig
            builds._state.clear()


class ContrarrestosSinRed(unittest.TestCase):
    def test_sin_red_se_usa_lo_guardado_aunque_haya_caducado(self):
        import matchups, urllib.request, urllib.error, tempfile
        d = tempfile.mkdtemp()
        champ = {"icon": "Ahri", "name": "Ahri"}
        os.makedirs(os.path.join(d, "matchups"))
        json.dump({"ts": 1, "rows": [{"name": "Cho&#39;Gath", "wr": 51.0, "d1": 1.0, "d2": 1.0, "avg": 50.0, "games": 500}]},
                  open(os.path.join(d, "matchups", "ahri_middle.json"), "w"))
        orig = urllib.request.urlopen
        def sin_red(*a, **k):
            raise urllib.error.URLError("sin red")
        urllib.request.urlopen = sin_red
        try:
            rows = matchups.load(d, champ, "middle")
            self.assertEqual(rows[0]["games"], 500)
            os.remove(os.path.join(d, "matchups", "ahri_middle.json"))
            with self.assertRaises(RuntimeError) as cm:
                matchups.load(d, champ, "middle")
            self.assertIn("no responde", str(cm.exception))      # y no el engañoso «no tiene datos»
        finally:
            urllib.request.urlopen = orig


class CachesIncompletas(unittest.TestCase):
    def test_tendencias_con_una_linea_vacia_caducan_pronto(self):
        import trends, tempfile
        d = tempfile.mkdtemp()
        orig = trends._fetch
        trends._fetch = lambda patch, lane, region: {} if lane == "support" else {"1": {"g": 100, "pr": 5.0, "wr": 50.0}}
        try:
            data = trends.load(d, "26.23", True, "euw")
        finally:
            trends._fetch = orig
        self.assertTrue(data["partial"])
        saved = json.load(open(os.path.join(d, "trends.json"), encoding="utf-8"))
        saved["ts"] -= 3600          # hace una hora: una caché parcial ya no vale (una completa duraría medio día)
        json.dump(saved, open(os.path.join(d, "trends.json"), "w"))
        trends._fetch = lambda patch, lane, region: {"1": {"g": 100, "pr": 5.0, "wr": 50.0}}
        try:
            self.assertFalse(trends.load(d, "26.23", False, "euw")["partial"])      # se vuelve a pedir y ya viene completa
        finally:
            trends._fetch = orig


class BloqueEnVivoRobusto(unittest.TestCase):
    def test_dos_jugadores_con_el_mismo_nombre_y_distinta_etiqueta(self):
        import live
        pl = lambda team, rid, name, champ: {"championName": champ, "team": team, "riotId": rid, "summonerName": rid, "riotIdGameName": name, "scores": {}, "items": []}
        d = {"allPlayers": [pl("ORDER", "Ahri#EUW", "Ahri", "Garen"), pl("CHAOS", "Ahri#1234", "Ahri", "Darius")],
             "activePlayer": {"riotId": "Ahri#1234", "summonerName": "Ahri#1234", "riotIdGameName": "Ahri"}, "gameData": {"gameTime": 100, "gameMode": "CLASSIC"}}
        r = live.summarize(d, {})
        self.assertEqual([p["me"] for p in r["players"]], [False, True])              # tú eres el de la etiqueta completa
        d["events"] = {"Events": [{"EventName": "DragonKill", "EventTime": 400.0, "KillerName": "Ahri#1234", "DragonType": "Fire"}]}
        r2 = live.summarize(d, {})
        self.assertEqual((r2["teams"]["CHAOS"]["dragons"], r2["teams"]["ORDER"]["dragons"]), (1, 0))   # el dragón es del de la etiqueta completa, no del otro «Ahri»
        d["activePlayer"] = {"riotIdGameName": "Ahri"}                                  # solo el nombre corto y dos jugadores lo llevan: no se sabe quién eres
        self.assertEqual([p["me"] for p in live.summarize(d, {})["players"]], [False, False])

    def test_iconos_que_no_existen_no_se_piden_en_bucle(self):
        import augments
        augments._tried.clear()
        orig_find, orig_icon = augments.core.find_client, augments.icon_path
        llamadas = []
        augments.core.find_client = lambda conf: (_ for _ in ()).throw(OSError("sin cliente"))
        augments.icon_path = lambda i: None
        try:
            t = augments.fetch_icons([991, 992], {}, done=lambda: llamadas.append(1))
            t.join(5)
            self.assertIsNone(augments.fetch_icons([991, 992], {}, done=lambda: llamadas.append(1)))   # ya intentados: no hay hilo nuevo
            self.assertEqual(llamadas, [])                                                              # y sin iconos nuevos no se repinta nada
        finally:
            augments.core.find_client, augments.icon_path = orig_find, orig_icon
            augments._tried.clear()

    def test_el_plan_de_otro_campeon_no_da_build(self):
        import ui_live
        class UI:
            champs = {1: {"icon": "Garen"}, 2: {"icon": "Ahri"}}
            items = {1: {}}
        snap = {"players": [{"me": True, "cid": 2}]}
        self.assertIsNone(ui_live._my_build(UI(), snap, {"cid": 1, "role": "TOP", "kind": "sr"}))


class PuntuacionAjustada(unittest.TestCase):
    """Ajustes del motor (22/11/2026): muestras pequeñas pesan menos y las reglas usan la línea asignada."""

    def setUp(self):
        self.champs = {1: {"name": "Uno", "icon": "Uno", "tags": ["Fighter"], "pos": ["TOP"], "info": {"defense": 5}, "attr": {}},
                       2: {"name": "Dos", "icon": "Dos", "tags": ["Fighter"], "pos": ["TOP"], "info": {"defense": 5}, "attr": {}}}
        self.conf = {"weights": {"mastery": 0, "winrate": 4.0, "role": 0, "comp": 0, "counter": 0, "synergy": 0, "meta": 0}, "params": dict(core.params.DEFAULT_PARAMS)}

    def P(self, **kw):
        base = {"mastery": {}, "stats": {}, "rstats": {}, "season": {}, "matchups": {}, "opp": {}, "oppr": {}, "pairs": {}}
        base.update(kw)
        return base

    def test_una_partida_en_el_rol_no_anula_un_historial_grande(self):
        # el campeón 1: 150 partidas al 57 % en total y 1 de 1 en este rol; el 2: solo 1 de 1 en total y en este rol
        P = self.P(stats={1: [150, 85], 2: [1, 1]}, rstats={(1, "TOP"): [1, 1], (2, "TOP"): [1, 1]})
        s1 = core.score(1, self.champs, "TOP", [], [], 0, 0, P, self.conf, 1)[2]["winrate"]
        s2 = core.score(2, self.champs, "TOP", [], [], 0, 0, P, self.conf, 1)[2]["winrate"]
        self.assertGreater(s1, s2)                                  # antes ganaba el de 1 partida (1/1 = +0,8)

    def test_el_meta_con_pocas_partidas_pesa_menos(self):
        old = core.META["data"]
        core.META["data"] = {"lanes": {"top": {1: {"wr": 58.0, "pr": 5, "br": 1, "games": 220, "d": 0}, 2: {"wr": 54.0, "pr": 5, "br": 1, "games": 200000, "d": 0}}},
                             "avg": {"top": 50}, "patch": "16.22", "tier": "emerald_plus"}
        conf = {**self.conf, "weights": {**self.conf["weights"], "meta": 2.2}, "meta_enabled": True}
        try:
            m1 = core.metamod.get(core.META["data"], "TOP", 1)
            m2 = core.metamod.get(core.META["data"], "TOP", 2)
            adj = lambda m: 50 + (m["wr"] - 50) * m["games"] / (m["games"] + core.META_K)
            self.assertLess(adj(m1), adj(m2))                       # 58 % con 220 partidas ya no gana a 54 % con 200.000
        finally:
            core.META["data"] = old

    def test_sugerencias_de_ban_solo_de_tu_linea_y_suavizadas(self):
        P = self.P(opp={1: [5, 4], 2: [2, 2]}, oppr={("TOP", 1): [5, 4], ("SUPPORT", 2): [2, 2]})
        self.assertEqual([b[3] for b in core.ban_suggestions(self.champs, P, set(), 5, self.conf, "TOP")], [1])        # el 2 lo perdiste jugando apoyo
        self.assertEqual([b[3] for b in core.ban_suggestions(self.champs, P, set(), 5, self.conf, "SUPPORT")], [2])
        self.assertEqual([b[3] for b in core.ban_suggestions(self.champs, P, set(), 5, self.conf)], [1, 2])             # sin línea: más derrotas primero

    def test_la_sinergia_de_duo_usa_la_linea_asignada_del_aliado(self):
        import synergy
        champs = {1: {"name": "Tirador", "tags": ["Marksman"], "pos": ["BOTTOM"], "attr": {}},
                  2: {"name": "Zyra", "tags": ["Mage", "Support"], "pos": ["MIDDLE", "SUPPORT"], "attr": {"utility": 2, "control": 2}}}
        lean = lambda c: 0.0
        con_rol = synergy.pair(champs, 1, 2, lean, "BOTTOM", "MIDDLE")        # Zyra juega central: no hay dúo de línea
        sin_rol = synergy.pair(champs, 1, 2, lean, "BOTTOM", "")              # sin saberlo, vale como apoyo posible
        self.assertFalse([x for x in con_rol if "dúo" in x[1] or "protege" in x[1]])
        self.assertTrue([x for x in sin_rol if x[0] > 0])

    def test_el_motivo_de_sinergia_no_es_una_regla_negativa(self):
        import synergy
        champs = {1: {"name": "A", "tags": ["Fighter"], "pos": ["TOP"], "attr": {}}, 2: {"name": "B", "tags": ["Fighter"], "pos": ["MIDDLE"], "attr": {}}}
        lean = lambda c: 1.0
        r = synergy.synergy_for(champs, 1, [2], {(1, 2): (3, 3)}, lean)
        self.assertNotIn("mismo tipo de daño", r["items"][0]["text"] or "")

    def test_diferencia_de_sesion_con_muestra_pequena_es_ruido(self):
        import sesion
        self.assertFalse(sesion.clearly_higher((8, 6), (8, 4)))                 # 75 % contra 50 % con 8 partidas cada una
        self.assertTrue(sesion.clearly_higher((200, 130), (200, 100)))           # 65 % contra 50 % con 200


class CuentaAnonimaDeInstalaciones(unittest.TestCase):
    """Voluntaria, anónima y apagada de fábrica (stats.py)."""

    def servidor(self):
        import http.server, threading, json as _j
        recibidos = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                recibidos.append((self.path, _j.loads(self.rfile.read(n).decode("utf-8")), dict(self.headers)))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

            def do_GET(self):
                recibidos.append((self.path, None, dict(self.headers)))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"total": 3, "activas": {"1": 1, "7": 2, "30": 3}}')

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_address[1]}", recibidos

    def test_apagada_de_fabrica_y_sin_servidor_no_hay_nada(self):
        import stats
        self.assertTrue(not stats.STATS_URL or stats.STATS_URL.startswith("https://"))    # solo HTTPS
        self.assertFalse(stats.enabled(""))
        self.assertIsNone(core.DEFAULT_CONF["stats_optin"])                          # sin respuesta del usuario: no se pregunta ni se envía
        self.assertFalse(stats.due({"stats_optin": None, "stats_id": "x"}))
        self.assertFalse(stats.due({"stats_optin": False, "stats_id": "x"}))
        self.assertFalse(stats.due({"stats_optin": True, "stats_id": ""}))
        self.assertFalse(stats.ping({"stats_optin": True, "stats_id": "x"}, "1.0.0", url=""))    # sin servidor configurado no se envía

    def test_solo_se_envia_el_id_y_la_version(self):
        import stats
        url, recibidos = self.servidor()
        conf = {"stats_optin": True, "stats_id": stats.new_id(), "stats_last": 0, "opgg_name": "SecretoNombre", "lol_path": "C:\Juegos"}
        guardado = []
        self.assertTrue(stats.ping(conf, "1.23.0", url=url, save=lambda c: guardado.append(1), now=1e6))
        path, cuerpo, cab = recibidos[0]
        self.assertEqual(path, "/ping")
        self.assertEqual(sorted(cuerpo), ["id", "v"])                                # nada más: ni nombre, ni ruta, ni ajustes
        self.assertEqual(cuerpo["v"], "1.23.0")
        self.assertNotIn("SecretoNombre", json.dumps(cuerpo))
        self.assertEqual(conf["stats_last"], 1e6)
        self.assertEqual(guardado, [1])
        self.assertFalse(stats.ping(conf, "1.23.0", url=url, now=1e6 + 3600))     # una hora después: aún no toca (una vez al día)
        self.assertEqual(len(recibidos), 1)
        self.assertTrue(stats.ping(conf, "1.23.0", url=url, now=1e6 + stats.PING_EVERY + 1))

    def test_retirar_el_permiso_pide_borrar_el_registro(self):
        import stats
        url, recibidos = self.servidor()
        ident = stats.new_id()
        self.assertTrue(stats.forget({"stats_id": ident}, url=url))
        self.assertEqual(recibidos[0][0], "/olvidar")
        self.assertEqual(recibidos[0][1], {"id": ident})
        self.assertFalse(stats.forget({"stats_id": ""}, url=url))                    # sin id no hay nada que borrar

    def test_un_servidor_caido_no_rompe_nada(self):
        import stats
        conf = {"stats_optin": True, "stats_id": stats.new_id(), "stats_last": 0}
        self.assertFalse(stats.ping(conf, "1.23.0", url="http://127.0.0.1:9", now=5.0))   # puerto cerrado: se ignora y se reintentará
        self.assertEqual(conf["stats_last"], 0)

    def test_panel_del_administrador_solo_con_clave(self):
        import stats
        url, recibidos = self.servidor()
        self.assertEqual(stats.admin_url({"admin_token": ""}, url=url), "")
        self.assertTrue(stats.admin_url({"admin_token": "k1"}, url=url).endswith("/panel?k=k1"))
        self.assertTrue(stats.admin_url({"admin_token": "a&b#c"}, url=url).endswith("/panel?k=a%26b%23c"))     # una clave con símbolos no rompe la dirección
        self.assertIsNone(stats.admin_summary({"admin_token": ""}, url=url))
        res = stats.admin_summary({"admin_token": "k1"}, url=url)
        self.assertEqual(res["activas"]["7"], 2)
        self.assertEqual(recibidos[0][0], "/resumen?k=k1")


class ComprobacionDelEmpaquetado(unittest.TestCase):
    def test_la_lista_de_modulos_de_la_autoprueba_es_la_de_la_carpeta(self):
        import glob
        excluidos = {"app", "build_release", "make_icon", "make_icon_options", "make_icon_options2", "make_icon_options3", "draft5"}
        en_carpeta = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(os.path.dirname(core.__file__), "*.py"))} - excluidos
        self.assertEqual(sorted(core.AUTOTEST_MODULES), sorted(en_carpeta))   # un módulo nuevo debe entrar en la lista (y así se prueba en el ejecutable)

    def test_la_autoprueba_pasa_desde_el_codigo_fuente(self):
        self.assertEqual(core.autotest(), [])


class ActualizacionIncompleta(unittest.TestCase):
    def test_se_avisa_si_la_actualizacion_no_llego_a_completarse(self):
        import updater, tempfile
        d = tempfile.mkdtemp()
        updater.mark_pending(d, r"C:\temp\Instalar-LOL-E-1.22.30.exe")
        self.assertEqual(updater.check_pending(d, "1.22.29"), "1.22.30")           # sigue la versión de antes: falló
        self.assertIsNone(updater.check_pending(d, "1.22.29"))                      # solo se avisa una vez
        updater.mark_pending(d, r"C:\temp\Instalar-LOL-E-1.22.30.exe")
        self.assertIsNone(updater.check_pending(d, "1.22.30"))                      # se completó: nada que decir
        updater.mark_pending(d, "otra-cosa.exe")                                    # un nombre raro no escribe nada
        self.assertIsNone(updater.check_pending(d, "1.0.0"))


class DescargaDeActualizaciones(unittest.TestCase):
    class Resp:
        def __init__(self, data, length=None):
            self.data, self.pos = data, 0
            self.headers = {"Content-Length": str(len(data) if length is None else length)}
        def read(self, n):
            c = self.data[self.pos:self.pos + n]
            self.pos += len(c)
            return c
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def close(self): pass

    def run_download(self, data, sha=None, length=None):
        import updater, hashlib, tempfile
        orig_open, orig_tmp = updater._open, tempfile.gettempdir
        d = tempfile.mkdtemp()
        updater._open = lambda url, timeout=20: self.Resp(data, length)
        tempfile.gettempdir = lambda: d
        try:
            info = {"version": "9.9.9", "url": "https://github.com/x/y", "sha256": sha or hashlib.sha256(data).hexdigest()}
            try:
                return updater.download(info), d
            except RuntimeError as e:
                return str(e), d
        finally:
            updater._open, tempfile.gettempdir = orig_open, orig_tmp

    def test_descarga_buena(self):
        r, d = self.run_download(b"x" * 1000)
        self.assertTrue(r.endswith("Instalar-LOL-E-9.9.9.exe") and os.path.exists(r))
        self.assertEqual([n for n in os.listdir(os.path.join(d, "LOL-E-update")) if n.endswith(".part")], [])

    def test_huella_distinta_se_descarta(self):
        r, d = self.run_download(b"x" * 1000, sha="0" * 64)
        self.assertIn("huella", r)
        self.assertEqual(os.listdir(os.path.join(d, "LOL-E-update")), [])

    def test_descarga_cortada_se_descarta_con_mensaje_claro(self):
        r, d = self.run_download(b"x" * 500, length=1000)
        self.assertIn("se cortó", r)
        self.assertEqual(os.listdir(os.path.join(d, "LOL-E-update")), [])


class DatosDelUsuarioSeguros(unittest.TestCase):
    """Lo que el cliente no puede volver a dar (historial, PL, partidas con rival, ajustes, fotos de rango) no se pierde por un archivo dañado."""

    def setUp(self):
        import tempfile
        self.d = tempfile.mkdtemp()

    def p(self, n):
        return os.path.join(self.d, n)

    def test_escribir_deja_el_archivo_completo_y_sin_temporales(self):
        import safeio
        safeio.write(self.p("a.json"), {"x": 1})
        safeio.write(self.p("a.json"), {"x": 2})
        self.assertEqual(json.load(open(self.p("a.json"), encoding="utf-8")), {"x": 2})
        self.assertEqual([n for n in os.listdir(self.d) if n.endswith(".tmp")], [])

    def test_un_archivo_danado_se_aparta_y_no_se_pisa(self):
        import safeio
        open(self.p("a.json"), "w").write('{"x": 1')            # truncado
        d, st = safeio.read(self.p("a.json"))
        self.assertEqual((d, st), ({}, "corrupt"))
        self.assertFalse(os.path.exists(self.p("a.json")))
        self.assertEqual(len([n for n in os.listdir(self.d) if ".corrupt-" in n]), 1)
        self.assertEqual(safeio.read(self.p("nada.json"))[1], "missing")

    def test_lp_dañado_no_se_sobrescribe_con_uno_casi_vacio(self):
        import analysis
        analysis.save_lp(self.d, 1, {"d": 10})
        analysis.save_lp(self.d, 2, {"d": -5})
        raw = open(self.p("lp.json"), encoding="utf-8").read()
        open(self.p("lp.json"), "w").write(raw[:-3])             # corte de luz a medias
        analysis.save_lp(self.d, 3, {"d": 7})
        copias = [n for n in os.listdir(self.d) if n.startswith("lp.json.corrupt-")]
        self.assertEqual(len(copias), 1)                          # lo dañado se conserva para recuperarlo
        self.assertEqual(open(self.p(copias[0]), encoding="utf-8").read(), raw[:-3])

    def test_historial_danado_usa_la_copia_y_no_pisa_la_copia_con_el_dano(self):
        import history
        path = self.p("history_x.json")
        history.save(path, [{"id": "1", "t": 1000, "c": 1, "w": True}])
        history.save(path, [{"id": "2", "t": 2000, "c": 2, "w": False}])
        self.assertTrue(os.path.exists(path + ".bak"))
        bueno = open(path + ".bak", encoding="utf-8").read()
        open(path, "w").write('{"1": {')                          # dañado
        history.save(path, [{"id": "3", "t": 3000, "c": 3, "w": True}])
        self.assertEqual(open(path + ".bak", encoding="utf-8").read(), bueno)   # la copia buena sigue intacta
        d = json.load(open(path, encoding="utf-8"))
        self.assertIn("3", d)
        self.assertTrue([n for n in os.listdir(self.d) if ".corrupt-" in n])

    def test_historial_que_no_se_puede_leer_ahora_no_se_pisa(self):
        import history, safeio
        path = self.p("history_y.json")
        history.save(path, [{"id": "1", "t": 1000, "c": 1, "w": True}])
        antes = open(path, encoding="utf-8").read()
        original = safeio.read
        safeio.read = lambda p, default=None, kind=dict: ({}, "unreadable") if p == path else original(p, default, kind)
        try:
            history.save(path, [{"id": "2", "t": 2000, "c": 2, "w": True}])
        finally:
            safeio.read = original
        self.assertEqual(open(path, encoding="utf-8").read(), antes)

    def test_los_patrones_solo_usan_partidas_de_la_cuenta_actual(self):
        import history, patrones
        os.makedirs(self.p("analysis"))
        for gid, t_ in (("11", 1000), ("22", 2000)):
            json.dump({"gid": gid}, open(self.p(f"analysis/{gid}.json"), "w"))
        json.dump({"33": {"id": "33", "t": 3000}}, open(self.p("history_otra.json"), "w"))
        old = history.ACCOUNT
        try:
            history.ACCOUNT = "otra"
            patrones._CACHE.clear()
            json.dump({"22": {"id": "22", "t": 2000}, "11": {"id": "11", "t": 1000}}, open(self.p("history_otra.json"), "w"))
            self.assertEqual([a["gid"] for a in patrones.load(self.d)], ["22", "11"])   # la más reciente por fecha de la partida
            json.dump({"11": {"id": "11", "t": 1000}}, open(self.p("history_otra.json"), "w"))
            self.assertEqual([a["gid"] for a in patrones.load(self.d)], ["11"])        # ya no entran las de otra cuenta
        finally:
            history.ACCOUNT = old
            patrones._CACHE.clear()

    def test_las_fotos_de_rango_son_de_cada_perfil_de_opgg(self):
        old = core.CACHE
        core.CACHE = self.d
        try:
            json.dump({"2026-11-01": {"x": 1}}, open(self.p("opgg_lp.json"), "w"))
            a = core.snaps_path({"opgg_region": "euw", "opgg_name": "Ana", "opgg_tag": "EUW"})
            b = core.snaps_path({"opgg_region": "euw", "opgg_name": "Beto", "opgg_tag": "EUW"})
            self.assertNotEqual(a, b)
            self.assertTrue(os.path.exists(a) and os.path.exists(b))       # cada uno hereda lo anterior la primera vez
            json.dump({"2026-11-02": {"x": 2}}, open(a, "w"))
            self.assertEqual(json.load(open(core.snaps_path({"opgg_region": "euw", "opgg_name": "Beto", "opgg_tag": "EUW"}))), {"2026-11-01": {"x": 1}})
        finally:
            core.CACHE = old

    def test_ajustes_dañados_se_apartan_y_arranca_con_los_de_fabrica(self):
        original = core.CONF_FILE
        core.CONF_FILE = self.p("config.json")
        try:
            open(core.CONF_FILE, "w").write("{")
            c = core.load_conf()
            self.assertEqual(c["preset"], core.DEFAULT_CONF["preset"])
            self.assertTrue([n for n in os.listdir(self.d) if n.startswith("config.json.corrupt-")])
        finally:
            core.CONF_FILE = original


class VentanaDeAceptar(unittest.TestCase):
    def test_nueva_ronda(self):
        import readycheck as r
        a = {"state": "InProgress", "response": "None", "timer": 3.0, "t": 100.0}
        self.assertFalse(r.new_round(None, a))
        self.assertFalse(r.new_round(a, None))
        self.assertFalse(r.new_round(a, {**a, "timer": 4.0, "t": 101.0}))                              # sigue la misma ventana
        self.assertFalse(r.new_round(a, {**a, "response": "Accepted", "timer": 4.0, "t": 101.0}))      # aceptas: misma ventana
        self.assertTrue(r.new_round({**a, "timer": 9.0}, {**a, "timer": 0.5, "t": 101.0}))                # el contador vuelve a empezar
        self.assertTrue(r.new_round({**a, "response": "Accepted"}, {**a, "timer": 4.0, "t": 101.0}))    # tu respuesta se borra
        self.assertTrue(r.new_round({**a, "state": "PartyNotReady"}, {**a, "timer": 4.0, "t": 101.0}))  # de un estado final a «en curso»
        self.assertFalse(r.new_round(a, {**a, "timer": 7.0, "t": 105.0}))                               # una pausa larga en la lectura no es una ventana nueva
        self.assertFalse(r.new_round({**a, "timer": None}, {**a, "timer": None, "t": 101.0}))           # sin contador, solo valen las otras señales


class AvisoDeParcheConTusCampeones(unittest.TestCase):
    def test_solo_los_campeones_que_has_jugado(self):
        import ui_patch
        class V:
            played = lambda self: {1, 3}
            champ_id = lambda self, e: {"A": 1, "B": 2, "C": 3}.get(e["name"])
        notas = {"sections": [{"kind": "champions", "groups": [{"entries": [{"kind": "champion", "name": n} for n in ("A", "B", "C", "A")]}]},
                              {"kind": "classic", "groups": [{"entries": [{"kind": "champion", "name": "A"}]}]},
                              {"kind": "items", "groups": [{"entries": [{"kind": "item", "name": "C"}]}]}]}
        self.assertEqual(ui_patch.PatchView.touched_mine(V(), notas), ["A", "C"])          # sin repetir, sin Classic ni objetos, sin los que no juegas
        self.assertEqual(ui_patch.PatchView.touched_mine(V(), None), [])


class ParcheEncendida(unittest.TestCase):
    """Desde la 1.23.0 la pantalla «Parche» está encendida: aparece en la barra, en la Ayuda y en la demostración."""

    def test_encendida_aparece_en_todos_los_sitios(self):
        import parche, ui_rail, ayuda, tour
        if not parche.ACTIVO:
            self.skipTest("LOLE_PARCHE=0: apagada a propósito")
        self.assertIn("Parche", [i[0] for i in ui_rail.ITEMS])
        self.assertIn("Parche", ayuda.PAGES)
        self.assertIn("parche", tour.LESSONS)
        self.assertIn("parche", tour.OTRAS)
        self.assertEqual(tour.PREGUNTAS.get("parche"), "parche")


class ParcheReservada(unittest.TestCase):
    """La pantalla «Parche» está reservada hasta revisarla con un parche real: sin `parche.ACTIVO` no se ve en ningún sitio."""

    def test_apagada_no_aparece(self):
        import parche, ui_rail, ayuda, tour
        if parche.ACTIVO:
            self.skipTest("LOLE_PARCHE=1: la pantalla está encendida a propósito")
        self.assertNotIn("Parche", [i[0] for i in ui_rail.ITEMS])
        self.assertNotIn("Parche", ayuda.PAGES)
        self.assertNotIn("parche", [t[0] for t in ayuda.TOPICS])
        self.assertNotIn("parche", tour.LESSONS)
        self.assertNotIn("parche", tour.OTRAS)
        self.assertNotIn("parche", tour.PREGUNTAS)


class NotasDelParche(unittest.TestCase):
    HTML = (
        '<div id="patch-notes-container"><h2 id="patch-top">&nbsp;</h2><blockquote class="blockquote context"><p>Intro uno.<br><br>Intro dos. '
        '<a href="x">wiki de nuestra comunidad</a></p></blockquote>'
        '<h2 id="patch-champions">Campeones</h2>'
        '<div class="patch-change-block"><div><p><a class="reference-link" href="https://leagueoflegends.com/en-us/champions/corki/"><img src="c.png"></a></p>'
        '<h3 class="change-title" id="patch-corki"><a href="https://www.leagueoflegends.com/en-us/champions/corki/">Corki</a></h3>'
        '<blockquote class="blockquote context"><p>Nota de Corki.</p></blockquote><hr class="divider">'
        '<h4 class="change-detail-title ability-title"><img src="q.png">R - Andanada</h4>'
        '<ul><li><strong>Daño</strong>: 90/170/250 (+85&nbsp;% del DA) ⇒ <strong>100/190/280 (+90&nbsp;% del DA)</strong>.</li>'
        '<li><strong>Enfriamiento</strong>: 10/9/8 s</li><li style="list-style:none;">⇒ <strong>8/7/6 s</strong>.</li></ul>'
        '<p><strong>Coste de maná:</strong>: 60 ⇒ <strong>50</strong>.</p>'
        '<hr class="divider"><p><a class="reference-link" href="https://leagueoflegends.com/en-us/champions/yasuo/"><img src="y.png"></a></p>'
        '<h3 class="change-title" id="patch-yasuo"><a href="#">Yasuo</a></h3><ul><li>Daño: 105 ⇒ <strong>100</strong>.</li></ul></div></div>'
        '<h2 id="patch-aram:-mayhem">ARAM: Caos</h2><blockquote class="blockquote context"><p>Intro de Caos.</p></blockquote><hr class="divider">'
        '<h4 class="change-detail-title">Aumentos</h4><p>Impacto blindado</p><ul><li>Daño: 50 ⇒ 25.</li></ul>'
        '<p>¡ABEJAS!</p><ul><li>Tiempo: 0,75 s ⇒ 1,1 s.</li></ul>'
        '<hr class="divider"><h4 class="change-detail-title">Corrección de errores</h4><ul><li>Hemos corregido un error.</li></ul>'
        '<h2 id="patch-classic">Classic</h2><h4 class="change-detail-title">Campeones</h4>'
        '<p><span><strong>&nbsp; NOVEDAD &nbsp;</strong></span>&nbsp;<strong>Fizz</strong></p><blockquote class="blockquote context"><p>Nota de Fizz.</p></blockquote>'
        '<p><br><strong>Q - Golpe de erizo</strong></p><ul><li>Se desliza.</li></ul>'
        '<h2 id="patch-bugfixes-and-qol-changes"><strong>Corrección de errores y mejoras de calidad</strong></h2><ul><li>Error uno.</li><li>Error dos.</li></ul>'
        '<h2 id="patch-tft-standalone-client">Cliente independiente de TFT</h2><blockquote class="blockquote context"><p>TFT.</p></blockquote></div>')

    def page(self):
        return {"url": "https://www.leagueoflegends.com/es-es/news/game-updates/league-of-legends-patch-26-22-notes", "title": "Notas de la versión 26.22 de League of Legends",
                "blades": [{"type": "articleMasthead", "title": "Notas de la versión 26.22 de League of Legends", "publishDate": "2026-11-03T19:00:00.000Z",
                            "description": {"body": "Resumen del <b>parche</b>."}, "banner": {"url": "b.jpg"}, "authors": [{"name": "Riot A"}]},
                           {"type": "patchNotesRichText", "fragmentId": "26.22", "richText": {"body": self.HTML}}]}

    def setUp(self):
        import parche
        self.p = parche
        self.d = parche.parse(self.page())

    def test_cabecera_y_versiones(self):
        d = self.d
        self.assertEqual((d["v"], d["date"][:10], d["summary"], d["authors"]), ("26.22", "2026-11-03", "Resumen del parche.", ["Riot A"]))
        self.assertEqual([s["kind"] for s in d["sections"]], ["champions", "aram", "classic", "bugs", "tft"])   # el h2 vacío no es una sección
        self.assertTrue(d["intro"][0].startswith("Intro uno"))
        self.assertFalse(any("wiki" in p for p in d["intro"]))                  # el enlace a la wiki no es contenido del parche
        self.assertEqual(self.p.list_versions('/league-of-legends-patch-26-9-notes /league-of-legends-patch-26-22-notes /league-of-legends-patch-26-10-notes'),
                         ["26.22", "26.10", "26.9"])

    def test_ficha_de_campeon(self):
        corki = self.d["sections"][0]["groups"][0]["entries"][0]
        self.assertEqual((corki["name"], corki["kind"], corki["verdict"]), ("Corki", "champion", "buff"))
        self.assertEqual(self.p.champion_slug(corki), "corki")
        self.assertEqual(corki["note"], ["Nota de Corki."])
        b = corki["blocks"][0]
        self.assertEqual(b["title"], "R - Andanada")
        lab = [(l["label"], l["trend"]) for l in b["lines"]]
        self.assertEqual(lab, [("Daño", 1), ("Enfriamiento", 1), ("Coste de maná", 1)])   # bajar enfriamiento y coste es mejorar; el «⇒» partido en dos <li> se une
        self.assertEqual(b["lines"][1]["before"], "10/9/8 s")
        self.assertEqual(b["lines"][1]["after"], "8/7/6 s")
        yasuo = self.d["sections"][0]["groups"][0]["entries"][1]
        self.assertEqual((yasuo["name"], yasuo["verdict"]), ("Yasuo", "nerf"))

    def test_aumentos_y_errores(self):
        aram = self.d["sections"][1]
        self.assertEqual(aram["intro"], ["Intro de Caos."])
        groups = {g["title"]: g for g in aram["groups"]}
        self.assertEqual([(e["name"], e["kind"]) for e in groups["Aumentos"]["entries"]], [("Impacto blindado", "augment"), ("¡ABEJAS!", "augment")])
        self.assertEqual(groups["Aumentos"]["entries"][0]["verdict"], "nerf")
        self.assertEqual([b["text"] for b in groups["Corrección de errores"]["bullets"]], ["Hemos corregido un error."])
        self.assertEqual(len(self.d["sections"][3]["groups"][0]["bullets"]), 2)

    def test_novedad_y_habilidades_en_parrafo(self):
        fizz = self.d["sections"][2]["groups"][0]["entries"][0]
        self.assertEqual((fizz["name"], fizz["tag"], fizz["verdict"]), ("Fizz", "NOVEDAD", "new"))
        self.assertEqual(fizz["blocks"][0]["title"], "Q - Golpe de erizo")          # no se parte en una ficha por habilidad

    def test_tendencia_de_un_cambio(self):
        t = self.p.trend
        self.assertEqual(t("Daño", "50/75/100", "50/80/110"), 1)
        self.assertEqual(t("Enfriamiento", "12/11/10", "10/9/8"), 1)
        self.assertEqual(t("Coste de maná", "50", "60"), -1)
        self.assertEqual(t("Daño", "640 + 99/nivel", "590 + 107/nivel"), 0)         # una cifra sube y otra baja: mixto
        self.assertEqual(t("Daño", "100 (+50 % del PH)", "100 (+60 % del PH)"), 1)  # misma serie principal: manda la relación
        self.assertEqual(t("Efecto", "visibles para todos", "visibles solo para quien lo tiene"), 0)   # sin números
        self.assertEqual(t("Daño", "(15+5 % de velocidad)", "17 % de vida que falte"), 0)              # otra fórmula: no se compara
        self.assertEqual(self.p.verdict([{"lines": [{"trend": 1}, {"trend": -1}]}])[0], "mixed")

    def test_casos_de_la_revision(self):
        t = self.p.trend
        self.assertEqual(t("Recuperación de enfriamiento", "70 %", "50 %"), -1)    # subir esa recuperación es bueno: bajarla es debilitar
        self.assertEqual(t("Reducción de enfriamiento de la E", "0,5", "0,75"), 1)
        self.assertEqual(t("Tiempo de acumulación", "10 s", "5 s"), 1)              # bajar el tiempo es mejorar
        self.assertEqual(t("Daño por segundo", "120/200/280 (+35 % del PH)", "(+40 % del PH)"), 1)   # solo cambia la relación
        self.assertEqual(t("Velocidad del proyectil", "3800", "3200 (tarda 0,047 s más en llegar)"), -1)   # la aclaración no cuenta como otra fórmula
        ln = self.p.make_line([["Oscuridad lacerante: Daño: 50 % del PH ⇒ 80 % del PH", False]])
        self.assertEqual((ln["label"], ln["before"], ln["after"], ln["trend"]), ("Oscuridad lacerante: Daño", "50 % del PH", "80 % del PH", 1))

    def test_nombre_de_campeon_como_h4_en_classic(self):
        html = ('<div id="patch-notes-container"><h2 id="patch-classic">Classic</h2><h4 class="change-detail-title">Campeones</h4>'
                '<h4 class="change-detail-title">NOVEDAD - Akali</h4><blockquote class="blockquote context"><p>Nota de Akali.</p></blockquote>'
                '<h4 class="change-detail-title ability-title">Q - Marca</h4><ul><li>Daño: 10 ⇒ 20.</li></ul>'
                '<h4 class="change-detail-title">Kennen</h4><ul><li>Daño: 5 ⇒ 4.</li></ul></div>')
        d = self.p.parse({"blades": [{"type": "patchNotesRichText", "richText": {"body": html}}]})
        es = d["sections"][0]["groups"][0]["entries"]
        self.assertEqual([(e["name"], e["tag"]) for e in es], [("Akali", "NOVEDAD"), ("Kennen", None)])
        self.assertEqual(es[0]["blocks"][0]["title"], "Q - Marca")
        self.assertEqual(es[1]["verdict"], "nerf")

    def test_habilidad_con_dos_formas_y_correccion_de_errores_en_classic(self):
        # parche 26.23 real: «Q - Bumerán» y en otro párrafo «/Peñascazo» (Gnar) no es otro campeón; «Corrección de errores» en negrita cierra Classic con viñetas
        html = ('<div id="patch-notes-container"><h2 id="patch-champions">Campeones</h2>'
                '<h3 class="change-title" id="patch-gnar"><a href="#">Gnar</a></h3><blockquote class="blockquote context"><p>Nota.</p></blockquote>'
                '<h4 class="change-detail-title ability-title">Q - Bumer\u00e1n</h4><p>/Pe\u00f1ascazo</p><ul><li>Da\u00f1o: 5 \u21d2 <strong>6</strong>.</li></ul>'
                '<h2 id="patch-classic">Classic</h2><h4 class="change-detail-title">Campeones</h4>'
                '<h4 class="change-detail-title">NOVEDAD - Akali</h4><blockquote class="blockquote context"><p>Nota de Akali.</p></blockquote><ul><li>Hace cosas.</li></ul>'
                '<p><strong>Correcci\u00f3n de errores</strong></p><ul><li>Se arregl\u00f3 algo.</li></ul></div>')
        d = self.p.parse({"blades": [{"type": "patchNotesRichText", "richText": {"body": html}}]})
        gnar = d["sections"][0]["groups"][0]["entries"]
        self.assertEqual([e["name"] for e in gnar], ["Gnar"])
        self.assertEqual(gnar[0]["blocks"][0]["title"], "Q - Bumer\u00e1n/Pe\u00f1ascazo")
        cl = d["sections"][1]["groups"]
        self.assertEqual([e["name"] for e in cl[0]["entries"]], ["Akali"])
        self.assertEqual(len(cl[1]["bullets"]), 1)

    def test_cambios_para_cruzar_con_estadisticas(self):
        ch = self.p.changes(self.d)
        self.assertEqual([(c["slug"], c["verdict"], c["section"]) for c in ch[:2]], [("corki", "buff", "champions"), ("yasuo", "nerf", "champions")])

    def test_aviso_de_campeon_tocado_sin_red(self):
        import tempfile, json as _j
        d = tempfile.mkdtemp()
        data = self.p.parse(self.page())
        data["fetched"] = 0
        os.makedirs(os.path.join(d, "parche"))
        _j.dump(data, open(os.path.join(d, "parche", "notas_26.22.json"), "w", encoding="utf-8"))
        _j.dump({"ts": 0, "schema": self.p.VERSION, "versions": ["26.22"]}, open(os.path.join(d, "parche", "lista.json"), "w", encoding="utf-8"))
        champs = {42: {"icon": "Corki", "name": "Corki"}, 157: {"icon": "Yasuo", "name": "Yasuo"}, 1: {"icon": "Annie", "name": "Annie"}}
        by = self.p.latest_effect(d, champs)
        self.assertEqual((by[42]["verdict"], by[157]["verdict"], by[42]["v"]), ("buff", "nerf", "26.22"))
        self.assertNotIn(1, by)
        self.assertIn("→", by[42]["text"])
        self.assertEqual(self.p.latest_effect(tempfile.mkdtemp(), champs), {})   # sin notas descargadas: nada, y sin errores

    def test_si_la_web_cambia_no_revienta(self):
        d = self.p.parse({"blades": [{"type": "patchNotesRichText", "richText": {"body": "<div>nada reconocible</div>"}}]})
        self.assertEqual(d["sections"], [])
        d = self.p.parse({})
        self.assertEqual(d["sections"], [])
        with self.assertRaises(ValueError):
            self.p.next_data("<html>sin datos</html>")


class EstadisticasDelParche(unittest.TestCase):
    def snap(self, rows):
        lanes = {l: {} for l in ("top", "jungle", "middle", "bottom", "support")}
        for (lane, cid), (wr, pr, br, games, share) in rows.items():
            lanes[lane][cid] = {"wr": wr, "pr": pr, "br": br, "games": games, "share": share, "home": lane}
        return {"lanes": lanes}

    def setUp(self):
        import parche_stats
        self.s = parche_stats
        self.prev = self.snap({("top", 1): (50.0, 3.0, 5.0, 30000, 90), ("top", 2): (50.0, 3.0, 1.0, 30000, 80), ("middle", 2): (50.0, 1.0, 1.0, 10000, 20),
                               ("top", 3): (50.0, 0.1, 1.0, 400, 10)})
        self.cur = self.snap({("top", 1): (53.0, 5.0, 8.0, 30000, 90), ("top", 2): (49.0, 2.0, 1.0, 30000, 60), ("middle", 2): (50.0, 3.0, 1.0, 20000, 40),
                              ("top", 3): (58.0, 0.1, 1.0, 450, 10)})

    def test_versiones_y_numeracion(self):
        self.assertEqual((self.s.internal("26.22"), self.s.public("16.22"), self.s.prev_version("26.22"), self.s.prev_version("26.1")), ("16.22", "26.22", "26.21", None))

    def test_comparacion_y_listas(self):
        rows = self.s.compare(self.cur, self.prev)
        r1 = next(r for r in rows if r["cid"] == 1)
        self.assertEqual((r1["dwr"], r1["dpr"], r1["dbr"]), (3.0, 2.0, 3.0))
        rk = self.s.rankings(rows)
        self.assertEqual([r["cid"] for r in rk["wr_up"]], [1])                   # 3 es de poca muestra (450 partidas) y no pasa el margen de error
        self.assertEqual([r["cid"] for r in rk["wr_dn"]], [2])
        self.assertEqual({r["cid"] for r in rk["pr_up"]}, {1, 2})                 # el uso sube en los dos; primero el que más sube en proporción
        self.assertEqual([r["cid"] for r in rk["bans"]][:1], [1])
        self.assertEqual(len({r["cid"] for r in rk["bans"]}), len(rk["bans"]))   # el baneo es del campeón: una sola fila
        self.assertEqual([r["cid"] for r in self.s.rankings(rows, lane="middle")["pr_up"]], [2])
        self.assertEqual(self.s.rankings(rows, only={2})["wr_up"], [])

    def test_sin_parche_anterior_no_hay_cambios(self):
        rows = self.s.compare(self.cur, None)
        self.assertTrue(all(r["dwr"] is None for r in rows))
        self.assertEqual(self.s.rankings(rows)["wr_up"], [])

    def test_cambios_de_linea(self):
        rows = self.s.compare(self.cur, self.prev)
        sh = self.s.lane_shifts(rows)
        self.assertTrue(any(s["cid"] == 2 and s["lane"] == "middle" and s["dshare"] == 20 for s in sh))

    def test_efecto_de_las_notas(self):
        rows = self.s.compare(self.cur, self.prev)
        idx = self.s.champion_index({1: {"icon": "Corki", "name": "Corki"}, 2: {"icon": "Yasuo", "name": "Yasuo"}})
        ch = [{"slug": "corki", "name": "Corki", "verdict": "buff", "section": "champions"}, {"slug": "yasuo", "name": "Yasuo", "verdict": "buff", "section": "champions"},
              {"slug": "nadie", "name": "Nadie", "verdict": "nerf", "section": "champions"}]
        eff = {e["name"]: e for e in self.s.note_effects(ch, rows, idx)}
        self.assertTrue(eff["Corki"]["expected"])           # mejora y sube
        self.assertFalse(eff["Yasuo"]["expected"])          # mejora y baja: al revés
        self.assertNotIn("Nadie", eff)

    def test_evolucion_dentro_del_parche(self):
        d = {"2026-11-03": {"games": 1000, "rows": {"top:1": [50.0, 3.0, 3000], "top:2": [50.0, 3.0, 3000], "top:3": [50.0, 0.2, 300]}},
             "2026-11-10": {"games": 9000, "rows": {"top:1": [54.0, 3.0, 20000], "top:2": [50.4, 3.0, 20000], "top:3": [60.0, 0.2, 400]}}}
        mv, a, b = self.s.movers(d)
        self.assertEqual([(r["cid"], r["dwr"]) for r in mv], [(1, 4.0)])           # 2 es ruido y 3 tiene muy poca muestra
        self.assertEqual((a, b), ("2026-11-03", "2026-11-10"))
        self.assertEqual(self.s.movers({"2026-11-03": d["2026-11-03"]}), ([], None, None))   # con un solo día no hay con qué comparar

    def test_filtros_antes_de_recortar_y_baneos_por_linea(self):
        rows = self.s.compare(self.cur, self.prev)
        cur = self.snap({("top", 1): (50.0, 3.0, 8.0, 30000, 90), ("support", 1): (50.0, 0.1, 8.0, 500, 3)})   # el baneo es del campeón: con «Apoyo» elegido no entra si allí casi no se juega
        self.assertEqual(self.s.rankings(self.s.compare(cur, None), lane="support")["bans"], [])
        self.assertEqual([r["cid"] for r in self.s.rankings(self.s.compare(cur, None), lane="top")["bans"]], [1])
        d = {"2026-11-03": {"games": 1, "rows": {"top:1": [50.0, 3.0, 3000], "jungle:1": [50.0, 3.0, 3000]}},
             "2026-11-10": {"games": 1, "rows": {"top:1": [54.0, 3.0, 20000], "jungle:1": [45.0, 3.0, 20000]}}}
        self.assertEqual([r["lane"] for r in self.s.movers(d, lane="jungle")[0]], ["jungle"])
        self.assertEqual(len(self.s.movers(d, n=1)[0]), 1)
        self.assertEqual([s["cid"] for s in self.s.lane_shifts(self.s.compare(self.cur, self.prev), only={1})], [])

    def test_parche_provisional(self):
        cur = self.snap({("top", 1): (50, 3, 5, 3000, 90)})
        prev = self.snap({("top", 1): (50, 3, 5, 30000, 90)})
        r, warn = self.s.reliability(cur, prev)
        self.assertLess(r, 0.35)
        self.assertIn("provisionales", warn)
        self.assertEqual(self.s.reliability(prev, prev)[1], "")


class AyudaDeLaApp(unittest.TestCase):
    def test_cada_pregunta_apunta_a_una_pagina_que_existe(self):
        import ayuda
        ids = [t[0] for t in ayuda.TOPICS]
        self.assertEqual(len(ids), len(set(ids)))
        for tid, q, a, dest, kw in ayuda.TOPICS:
            self.assertTrue(dest == "ajustes" or dest in ayuda.PAGES, tid)
            self.assertLessEqual(len(a), 330, f"{tid}: la respuesta es larga; una o dos frases")
            self.assertTrue(q.startswith("¿") and q.endswith("?"), tid)

    def test_todas_las_paginas_de_la_barra_tienen_ayuda(self):
        import ayuda, ui_rail
        for key, _icon, _label, _live in ui_rail.ITEMS:
            self.assertIn(key, ayuda.PAGES)
            self.assertEqual(len(ayuda.PAGES[key]), 4)
        self.assertIn("Datos", ayuda.PAGES)

    def test_glosario(self):
        import ayuda
        for termino, texto in ayuda.GLOSARIO.items():
            self.assertEqual(termino, termino.upper())
            self.assertLessEqual(len(texto), 140, termino)       # un globo, no un párrafo
        self.assertIsNotNone(ayuda.glossary("kda medio"))
        self.assertIsNone(ayuda.glossary("cosa inventada"))

    def test_buscador_sin_acentos_y_con_varias_palabras(self):
        import ayuda
        self.assertEqual(len(ayuda.search("")), len(ayuda.TOPICS))
        self.assertIn("runas_builds", [t[0] for t in ayuda.search("RUNAS")])
        self.assertIn("seguro", [t[0] for t in ayuda.search("sancion")])           # sin tilde
        self.assertIn("seguro", [t[0] for t in ayuda.search("sanción riot")])      # con tilde y dos palabras
        self.assertEqual(ayuda.search("zzzz nada"), [])
        self.assertEqual([t[0] for t in ayuda.search("datos")][0], "que_es")       # respeta el orden del catálogo

    def test_los_nombres_de_la_barra_coinciden_con_la_ayuda(self):
        import ayuda, ui_rail
        for key, _icon, label, live in ui_rail.ITEMS:
            esperado = "En vivo" if key == "Partida" else label    # la ayuda llama a la página por el nombre que tiene en modo en vivo
            self.assertEqual(ayuda.PAGES[key][0], esperado)


class SesionDeJuego(unittest.TestCase):
    H = 3600 * 1000
    NOW = 1_800_000_000_000

    def g(self, horas, w, d=1800):
        return {"t": self.NOW - int(horas * self.H), "d": d, "w": w}

    def test_sesion_en_curso_y_rachas(self):
        import sesion
        games = [self.g(30, True), self.g(5, True), self.g(3.5, False), self.g(2.5, False), self.g(1.5, False)]
        s = sesion.current(games, self.NOW)
        self.assertEqual((s["n"], s["w"], s["l"], s["loss_streak"]), (4, 1, 3, 3))     # la de hace 30 h es otra sesión
        self.assertIsNone(sesion.current(games, self.NOW + 6 * self.H))                 # ya pasaron más de 2 h: no hay sesión
        self.assertIsNone(sesion.current([], self.NOW))

    def test_remakes_no_cuentan(self):
        import sesion
        games = [self.g(3, False), dict(self.g(2, False), rm=True), self.g(1, True)]
        self.assertEqual(sesion.current(games, self.NOW)["n"], 2)

    def test_despues_de_perder(self):
        import sesion
        # sesión A: D D D V ; sesión B (otro día): V
        games = [self.g(100, False), self.g(99, False), self.g(98, False), self.g(97, True), self.g(5, True)]
        a = sesion.after_losses(games)
        self.assertEqual(a[0], (2, 1))      # la 1.ª de A (derrota) y la de B (victoria)
        self.assertEqual(a[1], (1, 0))      # la 2.ª de A venía de 1 derrota
        self.assertEqual(a[2], (2, 1))      # la 3.ª (D) y la 4.ª (V) venían de 2 o más

    def test_aviso_solo_con_muestra_y_diferencia(self):
        import sesion
        sess = {"n": 3, "w": 1, "l": 2, "loss_streak": 2, "win_streak": 0}
        self.assertIn("quizá", sesion.tilt_note(sess, {0: (30, 18), 2: (10, 3)}))
        self.assertNotIn("quizá", sesion.tilt_note(sess, {0: (30, 18), 2: (5, 1)}))     # pocas partidas: solo el hecho
        self.assertNotIn("quizá", sesion.tilt_note(sess, {0: (30, 15), 2: (12, 6)}))    # sin diferencia: sin consejo
        self.assertIsNone(sesion.tilt_note(dict(sess, loss_streak=1), {}))

    def test_mejor_franja(self):
        import sesion
        self.assertEqual(sesion.best_slot({"noche": (20, 14), "tarde": (20, 8), "mañana": (3, 3)})[0], "noche")
        self.assertIsNone(sesion.best_slot({"noche": (20, 11), "tarde": (20, 10)}))


class EstimacionDeRango(unittest.TestCase):
    NOW = 1_800_000_000_000

    def g(self, i, dias, w, q=420):
        return {"id": str(i), "t": self.NOW - int(dias * 86_400_000), "q": q, "c": 86, "w": w}

    def test_hacia_atras_desde_el_primer_punto_real(self):
        import lpseries as ls
        # partida 3 con PL real: acaba en Oro II 50 PL tras ganar 20 (venía de 30). Las 1 y 2 no tienen PL: se estiman hacia atrás.
        lp = {"3": {"d": 20, "now": 50, "tier": "Oro II"}}
        games = [self.g(1, 5, True), self.g(2, 4, False), self.g(3, 3, True)]
        est = ls.estimate(lp, games, {})
        self.assertEqual([p["id"] for p in est], ["2", "1"])
        base = 3 * 400 + 2 * 100
        self.assertEqual(est[0]["v"], base + 30)                    # tras la 2 estaba donde empezó la 3
        self.assertEqual(est[1]["v"], base + 30 + ls.LOSS)          # y tras la 1 estaba una derrota típica más arriba
        self.assertTrue(all(p["src"] == "est" for p in est))
        self.assertEqual(est[0]["tier"], "Oro II")

    def test_entre_dos_puntos_reales_cuadra(self):
        import lpseries as ls
        lp = {"1": {"d": 20, "now": 50, "tier": "Oro II"}, "4": {"d": 18, "now": 70, "tier": "Oro II"}}
        games = [self.g(1, 4, True), self.g(2, 3, True), self.g(3, 2, False), self.g(4, 1, True)]
        est = ls.estimate(lp, games, {})
        self.assertEqual(len(est), 2)
        self.assertAlmostEqual(est[-1]["v"], 3 * 400 + 200 + 70 - 18, delta=1)   # la última estimada acaba donde empezó la partida 4 real
        self.assertEqual(sum(p["d"] for p in est), (70 - 18) - 50)

    def test_sin_ancla_no_inventa_y_no_baja_de_cero(self):
        import lpseries as ls
        self.assertEqual(ls.estimate({}, [self.g(1, 2, True)], {}), [])
        lp = {"9": {"d": 10, "now": 15, "tier": "Hierro IV"}}
        games = [self.g(i, 30 - i, True) for i in range(1, 9)] + [self.g(9, 1, True)]
        self.assertTrue(all(p["v"] >= 0 for p in ls.estimate(lp, games, {})))

    def test_series_solo_incluye_estimadas_si_se_piden_y_el_resumen_las_cuenta(self):
        import lpseries as ls
        lp = {"3": {"d": 20, "now": 50, "tier": "Oro II"}}
        games = [self.g(1, 5, True), self.g(2, 4, False), self.g(3, 3, True)]
        self.assertEqual([p["src"] for p in ls.series(lp, games, {}, "solo")], ["game"])
        full = ls.series(lp, games, {}, "solo", with_estimate=True)
        self.assertEqual([p["src"] for p in full], ["est", "est", "game"])
        self.assertEqual(ls.summary(full)[1], 3)

    def test_medianas_propias(self):
        import lpseries as ls
        real = [{"w": True, "d": d} for d in (24, 25, 26)] + [{"w": False, "d": d} for d in (-14, -15, -16)]
        self.assertEqual(ls.typical(real), (25, 15))
        self.assertEqual(ls.typical([]), (ls.GAIN, ls.LOSS))


class SerieDeRango(unittest.TestCase):
    NOW = 1_800_000_000_000      # un «ahora» fijo en ms

    def partida(self, i, dias, q=420, c=86, w=True, rm=False):
        return {"id": str(i), "t": self.NOW - int(dias * 86_400_000), "q": q, "c": c, "w": w, "rm": rm}

    def test_valor_y_nombre_de_la_escala(self):
        import lpseries as ls
        self.assertEqual(ls.value_of("GOLD", "II", 40), 3 * 400 + 2 * 100 + 40)
        self.assertEqual(ls.parse_tier_text("Platino III"), ("PLATINUM", "III"))
        self.assertEqual(ls.parse_tier_text("Maestro"), ("MASTER", ""))
        self.assertEqual(ls.parse_tier_text("Cosa rara"), (None, ""))
        self.assertEqual(ls.label_of(3 * 400 + 2 * 100), "Oro II")
        self.assertEqual(ls.label_of(2800 + 300), "Maestro+")

    def test_puntos_de_partida_por_cola_y_sin_remakes(self):
        import lpseries as ls
        lp = {"1": {"d": 18, "now": 58, "tier": "Oro II"}, "2": {"d": -15, "now": 43, "tier": "Oro II"}, "3": {"d": 20, "now": 70, "tier": "Oro III"},
              "4": {"d": 9, "now": 10, "tier": "Oro II"}, "5": {"d": 5, "now": 5, "tier": "Oro II"}, "6": {"d": 1, "now": 1}}
        games = [self.partida(1, 3), self.partida(2, 2, w=False), self.partida(3, 1, q=440), self.partida(4, 1, rm=True), self.partida(5, 0.5, q=450),
                 self.partida(6, 0.2)]
        solo = ls.game_points(lp, games, "solo")
        self.assertEqual([(p["d"], p["v"], p["w"]) for p in solo], [(18, 1458, True), (-15, 1443, False)])   # sin remake, sin ARAM, sin rango ilegible
        self.assertEqual([p["d"] for p in ls.game_points(lp, games, "flex")], [20])
        self.assertEqual(ls.summary(solo), (3, 2, 1, 1))

    def test_fotos_de_opgg_solo_en_dias_sin_partida(self):
        import lpseries as ls
        hist = [{"created_at": "2026-11-04T00:00:32+09:00", "tier_info": {"lp": 1956, "tier": "CHALLENGER", "label": "C 1"}},
                {"created_at": "2026-11-05T00:00:29+09:00", "tier_info": {"lp": 50, "tier": "PLATINUM", "label": "P 3"}},
                {"created_at": "2026-11-06T00:00:29+09:00", "tier_info": {"lp": 1, "tier": "RARO", "label": "R 1"}},
                {"created_at": "mal", "tier_info": {}}]
        snaps = ls.parse_snapshots(hist)
        self.assertEqual(sorted(snaps), ["2026-11-04", "2026-11-05"])                    # lo que no se entiende se ignora
        self.assertEqual((snaps["2026-11-05"]["key"], snaps["2026-11-05"]["div"]), ("PLATINUM", "III"))
        dias = ls.day_points(snaps, taken_days={"2026-11-04"})
        self.assertEqual([p["tier"] for p in dias], ["Platino III"])                      # el día 4 ya tiene partida propia: no se duplica
        d = tempfile.mkdtemp()
        path = os.path.join(d, "opgg_lp.json")
        self.assertEqual(ls.save_snapshots(path, snaps), 2)
        self.assertEqual(ls.save_snapshots(path, {**snaps, "2026-11-06": snaps["2026-11-05"]}), 1)   # solo cuenta lo nuevo: la historia se acumula
        self.assertEqual(len(ls.load_snapshots(path)), 3)

    def test_tramos(self):
        import lpseries as ls
        pts = [{"t": self.NOW - dias * 86_400_000, "v": 1000 + dias, "src": "game", "d": 1, "w": True} for dias in (120, 60, 20, 5, 1)]
        self.assertEqual(len(ls.select(pts, "all", self.NOW)), 5)
        self.assertEqual(len(ls.select(pts, "7", self.NOW)), 2)
        self.assertEqual(len(ls.select(pts, "30", self.NOW)), 3)
        self.assertEqual(len(ls.select(pts, "90", self.NOW)), 4)
        many = [{"t": i, "v": 1000, "src": "game", "d": 1, "w": True} for i in range(50)]
        self.assertEqual(len(ls.select(many, "n20", self.NOW)), 20)
        self.assertEqual(ls.select([], "30", self.NOW), [])

    def test_bandas_de_division(self):
        import lpseries as ls
        self.assertEqual(ls.bands(1150, 1450), [(1200, "Oro IV"), (1300, "Oro III"), (1400, "Oro II")])
        self.assertEqual(ls.bands(2750, 3000), [(2800, "Maestro+")])


class FotosDePLdeOpgg(unittest.TestCase):
    def test_se_leen_del_perfil_y_se_acumulan(self):
        import json, tempfile
        from unittest import mock
        import lol_advisor as l
        lista = [{"created_at": "2026-11-04T00:00:32+09:00", "tier_info": {"lp": 40, "tier": "GOLD", "label": "G 2"}, "elo_point": 1},
                 {"created_at": "2026-11-05T00:00:29+09:00", "tier_info": {"lp": 61, "tier": "GOLD", "label": "G 2"}, "elo_point": 2}]
        crudo = '<script>self.__next_f.push([1,"x:{@@lpHistories@@:' + json.dumps(lista).replace('"', '@@') + ',@@otra@@:1}"])</script>'
        html = crudo.replace("@@", chr(92) + chr(34))          # como viene en la página: el JSON escapado dentro de una cadena de JavaScript
        self.assertEqual(l.parse_lp_histories(html), lista)
        self.assertEqual(l.parse_lp_histories("<html>sin datos</html>"), [])
        self.assertEqual(l.parse_lp_histories('"lpHistories":"$62:props"'), [])        # la referencia (cadena) no es la lista
        old = l.CACHE
        l.CACHE = tempfile.mkdtemp()
        try:
            with mock.patch.object(l, "fetch_opgg", return_value=html):
                self.assertEqual(l.save_lp_snapshots({}), 2)
                self.assertEqual(l.save_lp_snapshots({}), 0)                              # la segunda vez no hay nada nuevo
        finally:
            l.CACHE = old


class ParcheDeLaBuild(unittest.TestCase):
    def test_el_parche_se_lee_de_la_pagina(self):
        import builds
        self.assertEqual(builds.patch_of("<head>... Patch 16.22 are found on LoLalytics.</head>"), "26.22")
        self.assertEqual(builds.patch_of("<!-- Patch 15.1 -->sin parche visible"), "")        # un comentario no cuenta
        self.assertEqual(builds.patch_of("Patch 16.3 más texto"), "26.3")
        self.assertEqual(builds.patch_of("nada"), "")

    def test_nota_de_procedencia(self):
        import ui_build
        ahora = 1_800_000_000
        d = {"patch": "26.22", "read": ahora - 3 * 86400}
        self.assertEqual(ui_build.source_note(d, "26.22", ahora), "Fuente: Lolalytics (build más jugada, parche 26.22, leída hace 3 días).")
        self.assertIn("parche anterior al actual (26.23)", ui_build.source_note(d, "26.23", ahora))
        self.assertIn("leída hoy", ui_build.source_note({"patch": "26.22", "read": ahora - 600}, "26.22", ahora))
        self.assertIn("leída ayer", ui_build.source_note({"read": ahora - 90000}, "", ahora))
        # una build guardada por una versión anterior (sin parche ni fecha) sigue mostrando solo la fuente, sin inventar nada
        self.assertEqual(ui_build.source_note({}, "26.22", ahora), "Fuente: Lolalytics (build más jugada).")
        antes, core.DD_VERSION = core.DD_VERSION, "16.22.1"
        try:
            self.assertEqual(ui_build.current_patch(), "26.22")
            core.DD_VERSION = ""
            self.assertEqual(ui_build.current_patch(), "")
        finally:
            core.DD_VERSION = antes


class PrivacidadDeLosDatosGuardados(unittest.TestCase):
    def test_scrub_vacia_solo_las_claves_que_identifican(self):
        d = {"myTeam": [{"cellId": 1, "championId": 54, "puuid": "abc", "gameName": "Fulano", "tagLine": "EUW", "summonerId": 7}],
             "allPlayers": [{"championName": "Malphite", "riotId": "Fulano#EUW", "summonerName": "Fulano", "items": [1, 2]}], "n": 3}
        s = core.scrub(d)
        self.assertEqual(s["myTeam"][0], {"cellId": 1, "championId": 54, "puuid": "", "gameName": "", "tagLine": "", "summonerId": ""})
        self.assertEqual(s["allPlayers"][0], {"championName": "Malphite", "riotId": "", "summonerName": "", "items": [1, 2]})
        self.assertEqual(d["myTeam"][0]["gameName"], "Fulano")          # el original no se toca
        self.assertNotIn("Fulano", json.dumps(s))

    def test_la_migracion_limpia_lo_ya_guardado(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "live_samples"))
        json.dump({"myTeam": [{"puuid": "abc", "gameName": "Fulano"}]}, open(os.path.join(tmp, "last_session.json"), "w"))
        json.dump({"allPlayers": [{"summonerName": "Mengano", "riotId": "Mengano#1"}]}, open(os.path.join(tmp, "live_samples", "a.json"), "w"))
        core._DIAG["last"], antes = "", core.CACHE
        core.CACHE = tmp
        try:
            core._scrub_3(tmp)
        finally:
            core.CACHE = antes
        for f in ("last_session.json", os.path.join("live_samples", "a.json")):
            t = open(os.path.join(tmp, f), encoding="utf-8").read()
            self.assertNotIn("Fulano", t); self.assertNotIn("Mengano", t); self.assertNotIn("abc", t)

    def test_las_muestras_en_vivo_viejas_se_borran(self):
        tmp, antes = tempfile.mkdtemp(), core.CACHE
        os.makedirs(os.path.join(tmp, "live_samples"))
        viejo, nuevo = os.path.join(tmp, "live_samples", "v.json"), os.path.join(tmp, "live_samples", "n.json")
        for f in (viejo, nuevo):
            open(f, "w").write("{}")
        hace = time.time() - 20 * 86400
        os.utime(viejo, (hace, hace))
        core.CACHE = tmp
        try:
            core.prune_cache()
        finally:
            core.CACHE = antes
        self.assertFalse(os.path.exists(viejo))
        self.assertTrue(os.path.exists(nuevo))

    def test_la_conexion_sin_verificar_certificado_solo_va_al_equipo_local(self):
        """El cliente de LoL usa un certificado propio, así que se acepta sin verificar; eso solo es admisible si la
        dirección es siempre 127.0.0.1. Cualquier otro uso de esa excepción haría fallar esta prueba."""
        import re
        self.assertTrue(core.LCU(2999, "x").base.startswith("https://127.0.0.1:"))
        permitidos = {"lol_advisor.py", "augments.py"}      # CTX sin verificar (LCU) y el sondeo del puerto 2999
        for f in sorted(os.listdir(ROOT)):
            if not f.endswith(".py"):
                continue
            src = open(os.path.join(ROOT, f), encoding="utf-8").read()
            if re.search(r"CERT_NONE|_create_unverified_context", src):
                self.assertIn(f, permitidos, f"{f} desactiva la verificación de certificado")
        aug = open(os.path.join(ROOT, "augments.py"), encoding="utf-8").read()
        self.assertEqual(re.findall(r'urlopen\(\s*"([^"]+)"', aug), ["https://127.0.0.1:2999/liveclientdata/allgamedata"])
        for f in ("itemset.py", "lol_advisor.py"):       # los demás usuarios de CTX construyen la dirección con lcu.base / self.base
            src = open(os.path.join(ROOT, f), encoding="utf-8").read()
            for m in re.finditer(r"Request\(([^,)]+)", src):
                if "context=" in src[m.start():m.start() + 400] and "CTX" in src[m.start():m.start() + 400]:
                    self.assertRegex(m.group(1), r"(lcu|self)\.base")


class TuPartidaFrenteATuMedia(unittest.TestCase):
    @staticmethod
    def g(i, c, k, de, a, cs=150, d=1800, q=420, w=True, **extra):
        return {"id": str(i), "c": c, "q": q, "k": k, "de": de, "a": a, "cs": cs, "d": d, "w": w, **extra}

    def test_con_ese_campeon_si_hay_partidas_suficientes(self):
        import analysis
        hoy = self.g(100, 147, 1, 6, 14, cs=30, d=1700)                                     # Seraphine, 15/6 de KDA 2,5
        previas = [self.g(i, 147, 2, 4, 6, cs=24, d=1800) for i in range(1, 5)] + [self.g(50, 86, 9, 1, 1, cs=300)]
        r = analysis.vs_average(hoy, previas + [hoy])
        self.assertEqual((r["scope"], r["n"], r["wins"]), ("champ", 4, (4, 4)))              # solo las 4 de Seraphine; la de Garen no cuenta
        self.assertAlmostEqual(r["kda"][0], 15 / 6)
        self.assertAlmostEqual(r["kda"][1], (4 * 8) / 16)                                    # (suma de K+A) / suma de muertes, no media de cocientes
        self.assertAlmostEqual(r["cspm"][0], 30 / (1700 / 60))
        lineas = analysis.average_lines(r, "Seraphine")
        self.assertEqual(lineas[0], ("KDA 2,5 frente a tu media de 2,0 con Seraphine (4 partidas).", "good"))    # +25 %
        self.assertEqual(lineas[1][1], "dim" if abs(r["cspm"][0] / r["cspm"][1] - 1) < .25 else lineas[1][1])

    def test_sin_partidas_con_ese_campeon_se_compara_con_el_modo(self):
        import analysis
        hoy = self.g(100, 147, 8, 2, 8)
        previas = [self.g(i, 86, 2, 4, 6) for i in range(1, 6)] + [self.g(20, 86, 9, 1, 1, q=450)]    # una de ARAM: otro modo
        r = analysis.vs_average(hoy, previas)
        self.assertEqual((r["scope"], r["n"]), ("mode", 5))
        self.assertIn("en este modo (5 partidas)", analysis.average_lines(r, "Seraphine")[0][0])

    def test_no_se_compara_sin_datos_o_con_registros_antiguos(self):
        import analysis
        hoy = self.g(100, 147, 8, 2, 8)
        self.assertIsNone(analysis.vs_average(hoy, [hoy]))                                   # nada con qué comparar
        self.assertIsNone(analysis.vs_average(hoy, [hoy, self.g(1, 86, 1, 1, 1), self.g(2, 86, 1, 1, 1)]))   # solo 2: poco
        self.assertIsNone(analysis.vs_average({"id": "1", "c": 1, "q": 420, "k": None}, []))   # un registro antiguo sin K/D/A
        self.assertEqual(analysis.average_lines(None, "X"), [])
        legacy = [{"id": str(i), "c": 147, "q": 420, "k": None} for i in range(9)]            # partidas guardadas sin K/D/A: no cuentan
        self.assertIsNone(analysis.vs_average(hoy, legacy))

    def test_dano_y_vision_por_minuto(self):
        import analysis
        hoy = self.g(100, 147, 8, 2, 8, d=1800, dm=30000, v=60)                              # 1000 de daño y 2 de visión por minuto
        previas = [self.g(i, 147, 2, 4, 6, d=1800, dm=18000, v=30) for i in range(1, 5)]    # 600 y 1
        r = analysis.vs_average(hoy, previas)
        self.assertAlmostEqual(r["dpm"][0], 1000); self.assertAlmostEqual(r["dpm"][1], 600)
        self.assertAlmostEqual(r["vpm"][0], 2); self.assertAlmostEqual(r["vpm"][1], 1)
        lineas = dict((t.split()[0], tono) for t, tono in analysis.average_lines(r, "Seraphine"))
        self.assertEqual((lineas["Daño"], lineas["Visión"]), ("good", "good"))
        self.assertIn("Daño a campeones 1000 por minuto frente a 600.", [t for t, _ in analysis.average_lines(r, "X")])
        arena = analysis.vs_average(self.g(100, 147, 8, 2, 8, q=1700, dm=30000, v=60), [self.g(i, 147, 2, 4, 6, q=1700, dm=18000, v=30) for i in range(1, 5)])
        self.assertIsNone(arena["vpm"])                                                      # la visión no se compara en Arena ni ARAM
        self.assertIsNotNone(arena["dpm"])
        self.assertIsNone(analysis.vs_average(self.g(100, 147, 8, 2, 8), previas)["dpm"])    # sin daño guardado en la partida: no se inventa

    def test_aram_no_compara_el_farmeo(self):
        import analysis
        hoy = self.g(100, 147, 8, 2, 8, q=450)
        r = analysis.vs_average(hoy, [self.g(i, 147, 2, 4, 6, q=450) for i in range(1, 5)])
        self.assertIsNone(r["cspm"])
        self.assertEqual(len(analysis.average_lines(r, "Seraphine")), 1)


class PuedesComprar(unittest.TestCase):
    CAT = {11: {"g": 500, "n": "Hoja A", "from": [], "t": []}, 12: {"g": 300, "n": "Gema B", "from": [], "t": []},
           21: {"g": 1500, "n": "Objeto C", "from": [11, 12], "t": []},            # montar C cuesta 700 más sus componentes
           31: {"g": 3000, "n": "Objeto D", "from": [21, 11], "t": []},            # montar D cuesta 1000 más C y otra Hoja A
           41: {"g": 900, "n": "Botas", "from": [], "t": ["Boots"]}, 51: {"g": 400, "n": "X", "from": [], "t": []},
           52: {"g": 400, "n": "Y", "from": [], "t": []}, 53: {"g": 400, "n": "Z", "from": [], "t": []}}

    def setUp(self):
        import shopping
        self.s = shopping

    def test_arbol_de_la_receta(self):
        self.assertEqual(self.s.recipe_tree(31, self.CAT), {21, 11, 12})
        self.assertEqual(self.s.recipe_tree(11, self.CAT), set())
        self.assertEqual(self.s.recipe_tree(999, self.CAT), set())

    def test_lo_que_te_falta_resta_los_componentes_que_ya_llevas(self):
        r = lambda i, inv: self.s.remaining_cost(i, self.CAT, inv)
        self.assertEqual(r(21, []), 1500)
        self.assertEqual(r(21, [11]), 700 + 300)                 # llevas la Hoja A: faltan el montaje y la Gema B
        self.assertEqual(r(21, [11, 12]), 700)                   # llevas los dos componentes: solo el montaje
        self.assertEqual(r(21, [21]), 0)                         # ya lo llevas
        self.assertEqual(r(31, [11]), 1000 + (700 + 300) + 500)  # una sola Hoja A cubre una sola vez: la otra se paga
        self.assertEqual(r(31, [11, 11, 12]), 1000 + 700)        # con dos Hojas A y la Gema B
        self.assertIsNone(r(999, []))                            # un objeto que no está en el catálogo: no se inventa un precio

    def test_orden_de_compra_de_la_build(self):
        build = {"core": [11, 41, 21], "i4": [31, 51], "i5": [52], "i6": [], "start": [1054]}
        botas = lambda i: i == 41
        self.assertEqual(self.s.build_order(build, botas), [11, 41, 21, 31, 52])        # principal, botas, resto, primera opción de cada hueco
        self.assertEqual(self.s.build_order({"core": [11, 21]}, botas), [11, 21])        # sin botas
        self.assertEqual(self.s.build_order({}, botas), [])

    def test_siguiente_compra(self):
        orden = [21, 41, 31]
        res = self.s.next_purchase(orden, [11], 2000, self.CAT)
        self.assertEqual((res["id"], res["remaining"], res["affordable"], res["missing"], res["partial"]), (21, 1000, True, 0, [11]))
        res = self.s.next_purchase(orden, [11], 600, self.CAT)
        self.assertEqual((res["affordable"], res["missing"]), (False, 400))
        self.assertEqual(self.s.describe(res, self.CAT), "Siguiente objeto de tu build: Objeto C. Te faltan 400 de oro (ya llevas Hoja A).")
        self.assertIn("ya puedes comprarlo (1000 de oro)", self.s.describe(self.s.next_purchase(orden, [11], 2000, self.CAT), self.CAT))
        self.assertEqual(self.s.next_purchase(orden, [21], 100, self.CAT)["id"], 41)      # C ya lo llevas: toca el calzado
        self.assertEqual(self.s.next_purchase(orden, [31], 100, self.CAT)["id"], 41)      # D contiene C: C cuenta como hecho, siguen las botas
        self.assertIsNone(self.s.next_purchase(orden, [31, 41], 100, self.CAT))           # todo comprado (o mejorado): nada que proponer
        self.assertIsNone(self.s.next_purchase([999], [], 100, self.CAT))                 # precio desconocido: no opina
        self.assertIsNone(self.s.next_purchase([], [11], 100, self.CAT))


class QueAprender(unittest.TestCase):
    META = {"avg": {"top": 50.0, "jungle": 50.0, "middle": 50.0, "bottom": 50.0, "support": 50.0},
            "lanes": {"top": {10: {"wr": 52.0, "pr": 3.0, "games": 9000}, 11: {"wr": 54.0, "pr": 2.0, "games": 9000}, 12: {"wr": 49.0, "pr": 5.0, "games": 9000},
                              13: {"wr": 56.0, "pr": 0.2, "games": 9000}, 14: {"wr": 55.0, "pr": 4.0, "games": 100}, 1: {"wr": 53.0, "pr": 4.0, "games": 9000}},
                      "support": {20: {"wr": 53.0, "pr": 3.0, "games": 9000}}}}

    def partidas(self, rol, cids, q=420):
        return [{"c": c, "r": rol, "q": q, "w": i % 2 == 0, "rm": False} for i, c in enumerate(cids)]

    def test_aconseja_cuando_una_linea_depende_de_un_campeon(self):
        import learn
        g = self.partidas("TOP", [1] * 9 + [10] * 1)
        r = learn.advice(g, self.META, owned={10, 11, 12, 13, 14, 1}, mastery={10: 5000})
        self.assertEqual(len(r), 1)
        it = r[0]
        self.assertEqual((it["role"], it["n"], it["main"], it["main_g"]), ("TOP", 10, 1, 9))
        # 10 se jugó una vez (no cuenta como «jugado»), pero lo conoces (maestría) y va primero; 12 no supera la media; 13 es una rareza; 14 tiene poca muestra
        self.assertEqual([c for c, _ in it["cands"]], [10, 11])
        self.assertIn("9 de 10", learn.line(it, lambda c: f"C{c}"))

    def test_no_aconseja_sin_motivo(self):
        import learn
        repartido = self.partidas("TOP", [1, 10, 1, 10, 11, 1, 10, 11, 1, 10])                      # ninguno pasa del 70 %
        self.assertEqual(learn.advice(repartido, self.META, owned={1, 10, 11}), [])
        self.assertEqual(learn.advice(self.partidas("TOP", [1] * 5), self.META), [])               # pocas partidas
        self.assertEqual(learn.advice(self.partidas("TOP", [1] * 12, q=450), self.META), [])       # ARAM no tiene líneas
        self.assertEqual(learn.advice(self.partidas("TOP", [1] * 12), None), [])                   # sin meta no se inventa
        self.assertEqual(learn.advice(self.partidas("TOP", [1] * 12), self.META, owned={1}), [])   # nada que proponer que tengas

    def test_solo_campeones_que_posees_y_apoyo_del_cliente(self):
        import learn
        r = learn.advice(self.partidas("UTILITY", [5] * 10), self.META, owned={20})
        self.assertEqual((r[0]["role"], [c for c, _ in r[0]["cands"]]), ("SUPPORT", [20]))


class ObjetoContraLosRivales(unittest.TestCase):
    CAT = {1: {"g": 2800, "n": "Casco", "t": ["Armor"], "x": [], "into": []}, 2: {"g": 2800, "n": "Manto", "t": ["SpellBlock"], "x": [], "into": []},
           3: {"g": 3000, "n": "Lanza", "t": ["Damage"], "x": ["penarm"], "into": []}, 4: {"g": 3000, "n": "Bastón", "t": ["SpellDamage"], "x": ["penmag"], "into": []},
           5: {"g": 3000, "n": "Arco", "t": ["Damage"], "x": [], "into": []}, 6: {"g": 900, "n": "Botas", "t": ["Boots"], "x": [], "into": []},
           7: {"g": 500, "n": "Pieza", "t": ["Armor"], "x": [], "into": [1]}}

    def setUp(self):
        import shopping
        self.s = shopping

    def test_la_cantera_solo_tiene_objetos_completos(self):
        b = {"palette": [1, 6, 7, 3, 1], "stats": {"i4": [{"id": 2}, {"id": 999}]}}
        self.assertEqual(self.s.candidate_pool(self.CAT, b), [1, 3, 2])        # sin botas, sin piezas intermedias, sin repetidos ni desconocidos

    def test_penetracion_si_acumulan_una_defensa(self):
        pool = [1, 2, 3, 4, 5]
        r = self.s.counter_item({"ad": 3000, "ap": 3000, "armor": 4000, "mr": 1000}, pool, self.CAT, [])
        self.assertEqual(r["id"], 3)
        r = self.s.counter_item({"ad": 3000, "ap": 3000, "armor": 500, "mr": 4000}, pool, self.CAT, [])
        self.assertEqual(r["id"], 4)

    def test_defensa_contra_su_tipo_de_dano(self):
        pool = [1, 2, 5]
        self.assertEqual(self.s.counter_item({"ad": 7000, "ap": 1000, "armor": 0, "mr": 0}, pool, self.CAT, [])["id"], 1)
        self.assertEqual(self.s.counter_item({"ad": 1000, "ap": 7000, "armor": 0, "mr": 0}, pool, self.CAT, [])["id"], 2)

    def test_no_opina_sin_motivo(self):
        pool = [1, 2, 3, 4, 5]
        self.assertIsNone(self.s.counter_item({"ad": 500, "ap": 300, "armor": 100, "mr": 0}, pool, self.CAT, []))                  # muy poco oro: no significa nada
        self.assertIsNone(self.s.counter_item({"ad": 3000, "ap": 3000, "armor": 2000, "mr": 1500}, pool, self.CAT, []))            # equilibrado
        self.assertIsNone(self.s.counter_item({"ad": 7000, "ap": 1000, "armor": 0, "mr": 0}, [1], self.CAT, [1]))                  # ya llevas el único que sirve
        self.assertIsNone(self.s.counter_item({"ad": 7000, "ap": 1000, "armor": 0, "mr": 0}, [5], self.CAT, []))                   # nada en tu cantera sirve


class ObjetosQueSeTransforman(unittest.TestCase):
    """Muramana, Abrazo del serafín, El gran invierno… no se compran: aparecen al transformarse el que ya llevas (Lágrima de la diosa y su familia)."""
    CAT = {3070: {"g": 400, "n": "Lágrima", "from": [], "t": ["Mana"], "into": [3004]},
           3004: {"g": 2900, "n": "Manamune", "from": [3070, 3133, 1036], "t": ["Damage"]}, 3133: {"g": 1100, "n": "Martillo", "from": [], "t": []},
           1036: {"g": 350, "n": "Espada larga", "from": [], "t": []}, 3042: {"g": 2900, "n": "Muramana", "from": [], "t": ["Damage"]},
           3003: {"g": 2900, "n": "Bastón del arcángel", "from": [3070], "t": []}, 3040: {"g": 2900, "n": "Abrazo del serafín", "from": [], "t": []},
           51: {"g": 400, "n": "X", "from": [], "t": []},
           3867: {"g": 400, "n": "Botín", "from": [], "t": ["Lane", "GoldPer"]}, 3869: {"g": 400, "n": "Detracción", "from": [3867], "t": ["Lane", "GoldPer"]},
           1001: {"g": 300, "n": "Botas", "from": [], "t": ["Boots"], "depth": None}, 3009: {"g": 1000, "n": "Rapidez", "from": [1001], "t": ["Boots"], "depth": 2},
           3006: {"g": 1100, "n": "Grebas", "from": [1001], "t": ["Boots"], "depth": 2}}

    def setUp(self):
        import shopping
        self.s = shopping

    def sig(self, order, inv, gold=9999):
        r = self.s.next_purchase(order, inv, gold, self.CAT)
        return r and r["id"]

    def test_con_manamune_no_se_propone_comprar_muramana(self):
        self.assertIsNone(self.sig([3042], [3004]))
        self.assertEqual(self.sig([3042, 51], [3004]), 51)

    def test_con_muramana_no_se_propone_manamune(self):
        self.assertEqual(self.sig([3004, 51], [3042]), 51)
        self.assertEqual(self.sig([3003, 51], [3040]), 51)

    def test_con_la_lagrima_la_build_con_muramana_propone_su_forma_comprable(self):
        r = self.s.next_purchase([3042], [3070], 9999, self.CAT)
        self.assertEqual((r["id"], r["partial"]), (3004, [3070]))
        self.assertEqual(r["remaining"], 2900 - 400)

    def test_los_objetos_de_mision_no_se_proponen(self):
        self.assertEqual(self.sig([3869, 51], [3867]), 51)

    def test_con_botas_hechas_no_se_propone_otro_par(self):
        self.assertIsNone(self.sig([3006], [3009]))
        self.assertEqual(self.sig([3006], [1001]), 3006)

    def test_contra_los_rivales_no_se_repite_una_forma_que_ya_llevas(self):
        enemy = {"armor": 3000, "mr": 0, "ad": 3000, "ap": 0}
        cat = {**self.CAT, 3004: {**self.CAT[3004], "x": ["penarm"], "t": ["Damage"]}}
        self.assertIsNone(self.s.counter_item(enemy, [3004], cat, [3042]))

    def test_variantes_de_modo_cuentan_como_el_objeto_base(self):
        cat = {**self.CAT, 773004: {"g": 2100, "n": "Manamune", "from": [], "t": []}}
        self.assertEqual(self.s.norm(773004, cat), 3004)
        self.assertIsNone(self.sig([3042], [773004]) if False else self.s.next_purchase([3042], [773004], 9999, cat))
        self.assertEqual(self.s.norm(555555, cat), 555555)   # desconocido: tal cual

    def test_el_catalogo_real_cuadra_con_la_tabla(self):
        import json
        p = os.path.join(ROOT, "cache", "items.json")
        if not os.path.exists(p):
            self.skipTest("sin catálogo guardado")
        with open(p, encoding="utf-8") as f:
            it = {int(k): v for k, v in json.load(f)["items"].items()}
        for b, e in self.s.EVOLVES.items():
            self.assertIn(b, it, b)
            self.assertIn(e, it, e)
        for e in (3042, 3040, 3121, 2530):   # las formas evolucionadas no tienen receta: por eso la tabla
            self.assertEqual(it[e]["from"], [], e)


class AvisoDeCompra(unittest.TestCase):
    def test_suena_una_vez_por_objeto_y_solo_si_esta_activado(self):
        from unittest import mock
        import gui, sounds, ui_live
        class Falso:
            conf = {"beep": True, "buy_alert": True, "volume": 0.5}
            ctx = {"plan": {}}
        g = Falso()
        veces = []
        pistas = iter([("a", 5, False), ("a", 5, True), ("a", 5, True), ("b", 7, True), None])
        with mock.patch.object(sounds, "play_alert", lambda s, v: veces.append((s, v))), mock.patch.object(ui_live, "buy_hint", lambda *a: next(pistas)):
            for _ in range(5):
                gui.GUI.buy_alert(g, {})
            self.assertEqual(veces, [("Cristal", 0.5), ("Cristal", 0.5)])          # objeto 5 una vez (al poder pagarlo) y objeto 7 otra
            g.conf["buy_alert"] = False
            pistas = iter([("c", 9, True)])
            gui.GUI.buy_alert(g, {})
            self.assertEqual(len(veces), 2)                                           # desactivado: silencio


class Documentacion(unittest.TestCase):
    """El punto de partida de las conversaciones nuevas (docs/CONTINUAR.md) no puede quedarse atrás: estas pruebas fallan si no se actualiza."""
    def leer(self, nombre):
        return open(os.path.join(ROOT, "docs", nombre), encoding="utf-8").read()

    def test_continuar_menciona_la_version_del_codigo(self):
        self.assertIn(core.APP_VERSION, self.leer("CONTINUAR.md"),
                      f"docs/CONTINUAR.md no menciona la versión {core.APP_VERSION}: actualiza su sección «Estado» y su registro")

    def test_todas_las_herramientas_estan_en_la_tabla(self):
        txt = self.leer("CONTINUAR.md")
        for f in sorted(os.listdir(os.path.join(ROOT, "herramientas"))):
            if f.endswith(".py") and not f.startswith("_"):
                self.assertIn(f, txt, f"herramientas/{f} no aparece en docs/CONTINUAR.md (sección «Herramientas»)")

    def test_los_documentos_de_contexto_existen_y_tienen_fecha(self):
        for nombre in ("CONTINUAR.md", "PLAN_DE_FUTURO.md", "HISTORIAL_DE_SESIONES.md"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, "docs", nombre)), nombre)
        self.assertRegex(self.leer("CONTINUAR.md"), r"Última actualización: \d{1,2}/\d{1,2}/\d{4}")
        self.assertRegex(self.leer("PLAN_DE_FUTURO.md"), r"Actualizado el \d{1,2}/\d{1,2}/\d{4}")

    def test_el_estado_dice_que_version_esta_publicada(self):
        self.assertRegex(self.leer("CONTINUAR.md"), r"Publicado en GitHub: \*{0,2}\d+\.\d+\.\d+")


class PartidaEnVivo(unittest.TestCase):
    def setUp(self):
        try:
            self.champs = core.load_champions()
        except Exception as e:
            self.skipTest(f"sin datos de campeones en cache/: {e}")
        import live
        from cliente_falso import live_sample
        self.live, self.d = live, live_sample()

    def test_resumen_de_una_muestra(self):
        r = self.live.summarize(self.d, self.champs)
        self.assertEqual((len(r["players"]), r["t"], r["mode"], r["gold"], r["me_team"]), (10, 916.0, "CLASSIC", 433, "ORDER"))
        self.assertTrue(all(p["cid"] for p in r["players"]), [p["name"] for p in r["players"] if not p["cid"]])   # los 10 campeones se reconocen
        yo = next(p for p in r["players"] if p["me"])
        self.assertEqual((self.champs[yo["cid"]]["name"], yo["team"], yo["level"], (yo["k"], yo["d"], yo["a"]), yo["cs"]), ("Garen", "ORDER", 13, (4, 2, 3), 121))
        self.assertEqual(yo["value"], 2700 + 1100 + 1300)                    # sin el consumible (pociones)
        self.assertEqual(yo["items"], [3068, 3047, 3036, 2003])               # en el orden de sus casillas
        self.assertEqual(sum(1 for p in r["players"] if p["me"]), 1)
        self.assertEqual([p["name"] for p in r["players"][:5]], ["Garen", "LeeSin", "Ahri", "Jinx", "Thresh"])   # por equipo y por línea
        self.assertTrue(all("names" not in p for p in r["players"]))          # nada de nombres en el resumen
        sy = next(p for p in r["players"] if p["name"] == "Syndra")
        self.assertEqual((sy["dead"], sy["respawn"]), (True, 17.5))

    def test_marcador_y_objetivos_por_equipo(self):
        t = self.live.summarize(self.d, self.champs)["teams"]
        self.assertEqual((t["ORDER"]["kills"], t["CHAOS"]["kills"]), (4 + 5 + 6 + 3 + 0, 6 + 9 + 4 + 5 + 1))
        self.assertEqual(t["ORDER"]["value"], (2700 + 1100 + 1300) + (3000 + 1100) + (3000 + 1100 + 850) + (3400 + 1100) + (2200 + 1000))
        self.assertEqual((t["ORDER"]["towers"], t["CHAOS"]["towers"]), (1, 1))   # cae una torre de cada equipo: la suma el equipo contrario (formato real «Turret_TChaos_…»)
        self.assertEqual((t["ORDER"]["inhibs"], t["CHAOS"]["inhibs"], t["ORDER"]["grubs"], t["CHAOS"]["grubs"]), (1, 0, 0, 1))   # inhibidor de CHAOS lo gana ORDER; la larva la mata CHAOS
        self.assertEqual((t["CHAOS"]["dragons"], t["ORDER"]["heralds"], t["ORDER"]["barons"]), (1, 1, 0))   # por el equipo de quien lo mata

    def test_lectura_de_los_objetos_rivales(self):
        db = {3031: {"t": ["CriticalStrike", "Damage"], "g": 3400}, 6655: {"t": ["SpellDamage", "Mana"], "g": 3000},
              3047: {"t": ["Armor", "Boots"], "g": 1100}, 3068: {"t": ["Health", "Armor"], "g": 2700}, 3190: {"t": ["Health", "SpellBlock", "Armor"], "g": 2200},
              2003: {"t": ["Consumable"], "g": 50}, 3340: {"t": ["Trinket"], "g": 0}}
        eq = [{"items": [3031, 3047, 2003]}, {"items": [3031, 3068]}, {"items": [6655, 3340]}]
        m = self.live.itemization(eq, db)
        self.assertEqual(m, {"ad": 6800, "ap": 3000, "armor": 3800, "mr": 0})        # sin consumibles ni baliza
        self.assertEqual(self.live.reading(m), ["Su daño, según sus objetos: 69 % físico · 31 % mágico.",
                                                "Acumulan armadura: la penetración de armadura rinde más que el daño bruto."])
        self.assertEqual(self.live.reading({"ad": 900, "ap": 500, "armor": 700, "mr": 100}), [])   # con poco oro no se opina
        self.assertIn("resistencia mágica", self.live.reading({"ad": 0, "ap": 0, "armor": 500, "mr": 3000})[0])
        self.assertIn("por igual", self.live.reading({"ad": 0, "ap": 0, "armor": 2000, "mr": 1500})[0])
        self.assertEqual(self.live.itemization([{"items": [999999]}], db), {"ad": 0, "ap": 0, "armor": 0, "mr": 0})   # objeto desconocido

    def test_tu_rival_directo(self):
        r = self.live.summarize(self.d, self.champs)
        garen = next(p for p in r["players"] if p["me"])
        darius = next(p for p in r["players"] if p["name"] == "Darius")
        yo, rival = self.live.duel(r, darius["cid"])
        self.assertEqual((yo["name"], rival["name"]), ("Garen", "Darius"))
        self.assertIsNone(self.live.duel(r, garen["cid"]))                       # el propio campeón no es «tu rival» (es de tu equipo)
        self.assertIsNone(self.live.duel(r, 0))
        self.assertIsNone(self.live.duel({"players": []}, darius["cid"]))
        txt = self.live.duel_line(yo, rival, "Darius")
        self.assertEqual(txt, "Tu rival directo, Darius: nivel 13 (tú 13) · objetos 5,7k (tú 5,1k) · 6/3/2.")   # 600 de diferencia (10 %): no se opina
        self.assertIn("Va por delante en objetos.", self.live.duel_line({**yo, "value": 4000}, {**rival, "value": 5700}, "Darius"))
        parejo = self.live.duel_line({**yo, "value": 5000}, {**rival, "value": 5300}, "Darius")
        self.assertNotIn("por delante", parejo)                                   # 300 de diferencia: ruido
        self.assertIn("Vas por delante", self.live.duel_line({**yo, "value": 8000}, {**rival, "value": 5000}))

    def test_datos_incompletos_no_rompen(self):
        self.assertIsNone(self.live.summarize({}, self.champs))
        self.assertIsNone(self.live.summarize({"allPlayers": []}, self.champs))
        r = self.live.summarize({"allPlayers": [{"championName": "Nadie", "team": "ORDER"}]}, self.champs)
        self.assertEqual((r["players"][0]["cid"], r["players"][0]["items"], r["players"][0]["value"], r["me_team"], r["t"]), (0, [], 0, "", 0.0))
        self.assertEqual((self.live.clock(872.4), self.live.clock(-5), self.live.money(12345)), ("14:32", "0:00", "12,3k"))


class SeleccionesRaras(unittest.TestCase):
    """Sesiones de selección con lo que cada modo trae (o NO trae): el motor no puede lanzar excepciones. Sustituye al viejo test_modes.py,
    que necesitaba el cliente real y una ventana. Caso real que lo originó: en Arena `advise` fallaba con AttributeError."""
    def setUp(self):
        try:
            self.champs = core.load_champions()
        except Exception as e:
            self.skipTest(f"sin datos de campeones en cache/: {e}")
        from cliente_falso import ClienteFalso
        self.P = core.load_player_data(ClienteFalso(), {})
        self.conf = core.load_conf()
        self.conf.pop("_opp", None)

    def ver(self, ses, mode):
        import copy
        r = core.advise(copy.deepcopy(ses), self.champs, self.P, self.conf, mode)
        self.assertIsInstance(r, dict)
        self.assertNotIn("error", r)
        return r

    def test_arena(self):
        ses = {"localPlayerCellId": 2, "myTeam": [{"cellId": 2, "championId": 0, "playerSubteamId": 1}, {"cellId": 3, "championId": 103, "playerSubteamId": 1}],
               "theirTeam": [], "timer": {"phase": "BAN_PICK"}, "actions": [[None]]}
        r = self.ver(core.sanitize_session(ses), {"id": 1750, "group": "Arena", "kind": "other"})
        self.assertEqual((r["mode"]["kind"], r["cands"]), ("other", []))

    def test_personalizada_de_la_grieta_sin_posiciones(self):
        ses = {"localPlayerCellId": 0, "myTeam": [{"cellId": i, "championId": c} for i, c in enumerate((0, 64, 103, 222, 89))],
               "theirTeam": [{"cellId": 5 + i, "championId": c} for i, c in enumerate((157, 23, 0, 0, 0))], "bans": {},
               "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 25000, "totalTimeInPhase": 30000}, "actions": []}
        for modo in ({"id": 0, "group": "Personalizada", "kind": "other"}, {"id": 0, "group": "", "kind": "sr"}):
            self.ver(core.sanitize_session(ses), modo)

    def test_aram_con_banquillo_vacio_o_con_huecos(self):
        casos = [{"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championId": 103}, {"cellId": 1, "championId": 64}], "theirTeam": [],
                  "benchChampions": [{"championId": 1}, {"championId": 51}], "timer": {"phase": "BAN_PICK"}, "actions": []},
                 {"localPlayerCellId": 0, "myTeam": [{"cellId": 0, "championId": None}], "theirTeam": None,
                  "benchChampions": [{"championId": None}, {}], "timer": None, "actions": None, "bans": None}]
        for ses in casos:
            self.ver(core.sanitize_session(ses), {"id": 450, "group": "ARAM", "kind": "aram"})

    def test_sesion_vacia_o_sin_nada(self):
        for ses in ({}, {"myTeam": None, "theirTeam": None}, {"localPlayerCellId": 7, "myTeam": [{"cellId": 0}]}):
            self.ver(core.sanitize_session(ses), {"id": 0, "group": "", "kind": "sr"})

    def test_grieta_normal_pone_tu_linea_y_candidatos(self):
        from cliente_falso import SELECCION
        r = self.ver(core.sanitize_session(SELECCION), {"id": 420, "group": "Solo/Dúo", "kind": "sr"})
        self.assertEqual((r["role"], r["turn"]), ("TOP", "pick"))
        self.assertTrue(r["cands"] and r["lane_opp"] == 157)


class RivalElegidoAMano(unittest.TestCase):
    """Elegir a mano el rival de línea cambia también las puntuaciones, no solo la build."""
    def setUp(self):
        try:
            self.champs = core.load_champions()
        except Exception as e:
            self.skipTest(f"sin datos de campeones en cache/: {e}")
        from cliente_falso import ClienteFalso, SELECCION
        import copy
        self.s = copy.deepcopy(SELECCION)
        self.s["theirTeam"][1]["championId"] = 23          # el rival de la línea de arriba es Yasuo (157); Tryndamere (23) va de jungla
        self.P = core.load_player_data(ClienteFalso(), {})
        self.conf = core.load_conf()
        self.conf.pop("_opp", None)

    def cand(self, r, cid):
        return next(c for c in r["cands"] if c["cid"] == cid)

    def test_el_rival_elegido_cambia_la_puntuacion_y_se_puede_soltar(self):
        self.P["matchups"][(54, 23)] = [8, 8]               # con Malphite siempre has ganado a Tryndamere
        base = core.advise(self.s, self.champs, self.P, self.conf)
        self.assertEqual((base["lane_opp"], base["lane_opp_auto"]), (157, 157))
        self.assertNotIn("contra Tryndamere", " ".join(self.cand(base, 54)["why"]))
        self.conf["_opp"] = 23
        r = core.advise(self.s, self.champs, self.P, self.conf)
        self.assertEqual((r["lane_opp"], r["lane_opp_auto"]), (23, 157))     # el automático se conserva aparte
        self.assertIn("contra Tryndamere: 8/8", " ".join(self.cand(r, 54)["why"]))
        self.assertGreater(self.cand(r, 54)["score"], self.cand(base, 54)["score"])
        self.conf["_opp"] = 0                                                # «Auto»: vuelve a lo de antes
        self.assertEqual(self.cand(core.advise(self.s, self.champs, self.P, self.conf), 54)["score"], self.cand(base, 54)["score"])

    def test_un_rival_que_ya_no_esta_se_ignora(self):
        self.conf["_opp"] = 999
        self.assertEqual(core.advise(self.s, self.champs, self.P, self.conf)["lane_opp"], 157)

    def test_la_eleccion_no_se_guarda_en_la_configuracion(self):
        tmp, orig = tempfile.mkdtemp(), core.CONF_FILE
        core.CONF_FILE, core.DATA_DIR = os.path.join(tmp, "config.json"), tmp
        try:
            self.conf["_opp"] = 23
            core.save_conf(self.conf)
            self.assertNotIn("_opp", json.load(open(core.CONF_FILE)))
        finally:
            core.CONF_FILE, core.DATA_DIR = orig, os.path.dirname(orig)


class LineaQueJugaste(unittest.TestCase):
    """Caso real: Renekton aparecía como «jungla» en el historial. El cliente etiquetó JUNGLE a los dos jugadores de un equipo
    (Renekton y Master Yi) y a ninguno como TOP; solo Master Yi llevaba Aplastar."""
    @staticmethod
    def p(champ, lane, role, s1, s2, item, team=200):
        return {"participantId": champ, "teamId": team, "championId": champ, "spell1Id": s1, "spell2Id": s2,
                "stats": {"roleBoundItem": item, "win": True}, "timeline": {"lane": lane, "role": role}}

    def test_el_toplane_etiquetado_como_jungla_no_es_jungla(self):
        import history
        reneketon = self.p(58, "JUNGLE", "NONE", 4, 14, 1220)
        yi = self.p(11, "JUNGLE", "NONE", 11, 4, 1209)
        self.assertEqual(history.role_of(reneketon), "TOP")
        self.assertEqual(history.role_of(yi), "JUNGLE")

    def test_sin_pistas_no_se_adivina(self):
        import history
        self.assertEqual(history.role_of(self.p(1, "JUNGLE", "NONE", 4, 14, 0)), "")        # sin Aplastar ni objeto de rol
        self.assertEqual(history.role_of(self.p(1, "JUNGLE", "NONE", 4, 14, 1206)), "MIDDLE")  # el objeto de rol manda sobre la etiqueta
        self.assertEqual(history.role_of(self.p(1, "NONE", "NONE", 4, 14, 0)), "")
        self.assertEqual(history.role_of({}), "")

    def test_el_resto_de_lineas_siguen_igual(self):
        import history
        self.assertEqual(history.role_of(self.p(1, "TOP", "SOLO", 4, 12, 1220)), "TOP")
        self.assertEqual(history.role_of(self.p(1, "MIDDLE", "SOLO", 4, 14, 1206)), "MIDDLE")
        self.assertEqual(history.role_of(self.p(1, "BOTTOM", "CARRY", 4, 7, 3006)), "BOTTOM")
        self.assertEqual(history.role_of(self.p(1, "BOTTOM", "SUPPORT", 4, 3, 2055)), "SUPPORT")
        self.assertEqual(history.role_of(self.p(1, "MIDDLE", "SUPPORT", 4, 3, 1208)), "SUPPORT")   # apoyo que el cliente puso en mid
        self.assertEqual(history.role_of(self.p(1, "JUNGLE", "NONE", 11, 4, 0)), "JUNGLE")         # jungla sin objeto de rol

    def test_una_partida_real_donde_el_cliente_se_equivoca_en_4_de_10(self):
        """Partida real (campeones y datos del cliente, sin nombres): etiquetas del cliente con Jax «jungla», Fizz «top», Nami «bot» y
        Jhin «mid». Los objetos de rol y Aplastar reparten bien los cinco puestos de cada equipo."""
        import history

        def j(pid, team, champ, lane, role, item, smite=False):
            return {"participantId": pid, "teamId": team, "championId": champ, "spell1Id": 11 if smite else 4, "spell2Id": 7,
                    "stats": {"roleBoundItem": item}, "timeline": {"lane": lane, "role": role}}
        mio = [j(1, 100, 15, "BOTTOM", "CARRY", 3006), j(2, 100, 147, "BOTTOM", "SUPPORT", 2055), j(3, 100, 24, "JUNGLE", "NONE", 1220),
               j(4, 100, 98, "JUNGLE", "NONE", 1209, True), j(5, 100, 105, "TOP", "SOLO", 1206)]
        rival = [j(6, 200, 267, "BOTTOM", "SOLO", 2055), j(7, 200, 238, "JUNGLE", "NONE", 1209, True), j(8, 200, 101, "MIDDLE", "DUO", 1206),
                 j(9, 200, 202, "MIDDLE", "DUO", 3009), j(10, 200, 48, "TOP", "SOLO", 1220)]
        self.assertEqual(history.team_roles(mio), {1: "BOTTOM", 2: "SUPPORT", 3: "TOP", 4: "JUNGLE", 5: "MIDDLE"})
        self.assertEqual(history.team_roles(rival), {6: "SUPPORT", 7: "JUNGLE", 8: "MIDDLE", 9: "BOTTOM", 10: "TOP"})   # Jhin: botas + etiqueta MIDDLE
        self.assertEqual(history.role_of(rival[3]), "BOTTOM")
        self.assertEqual(history.role_of(self.p(1, "NONE", "SUPPORT", 4, 7, 3006)), "")           # botas con etiqueta NONE: no se interpreta
        d = {"participants": mio + rival}
        self.assertEqual(core.find_opponent(mio[1], d), 267)    # tu apoyo (Seraphine) contra su apoyo (Nami): antes salía «nadie»
        self.assertEqual(core.find_opponent(mio[0], d), 202)    # tu tirador contra su tirador (Jhin)
        self.assertEqual(core.find_opponent(mio[2], d), 48)     # tu toplane (Jax, «jungla» para el cliente) contra Trundle
        self.assertEqual(core.find_opponent(mio[4], d), 101)    # tu mid (Fizz, «top» para el cliente) contra Xerath

    def test_partidas_con_linea_none_se_reconocen_por_el_objeto_o_aplastar(self):
        import history
        self.assertEqual(history.role_of(self.p(1, "NONE", "SUPPORT", 4, 7, 1220)), "TOP")              # Fiora
        self.assertEqual(history.role_of(self.p(1, "NONE", "SUPPORT", 4, 7, 1206)), "MIDDLE")           # Hwei
        self.assertEqual(history.role_of(self.p(1, "NONE", "DUO", 4, 7, 1221)), "TOP")                  # Illaoi
        self.assertEqual(history.role_of(self.p(1, "NONE", "SUPPORT", 11, 4, 0)), "JUNGLE")             # Jarvan IV con Aplastar
        for item in (1202, 1001, 1200):                                                                 # objetos sin significado conocido
            self.assertEqual(history.role_of(self.p(1, "NONE", "SUPPORT", 4, 7, item)), "")

    def test_team_roles_no_inventa_si_falta_informacion(self):
        import history

        def j(pid, lane, item, smite=False):
            return {"participantId": pid, "teamId": 100, "championId": pid, "spell1Id": 11 if smite else 4, "spell2Id": 7,
                    "stats": {"roleBoundItem": item}, "timeline": {"lane": lane, "role": "NONE"}}
        r = history.team_roles([j(1, "TOP", 1220), j(2, "NONE", 0), j(3, "NONE", 0)])     # dos sin pistas y dos líneas libres
        self.assertEqual((r[1], r[2], r[3]), ("TOP", "", ""))
        self.assertEqual(history.team_roles([]), {})

    def test_el_rival_de_linea_ya_no_es_el_jungla(self):
        d = {"participants": [self.p(58, "JUNGLE", "NONE", 4, 14, 1220, 200), self.p(11, "JUNGLE", "NONE", 11, 4, 1209, 200),
                              self.p(86, "TOP", "SOLO", 4, 12, 1220, 100), self.p(64, "JUNGLE", "NONE", 11, 4, 1209, 100)]}
        me = d["participants"][0]
        self.assertEqual(core.find_opponent(me, d), 86)                 # el toplane rival (antes salía Master Yi / nadie)
        self.assertEqual(core.find_opponent(d["participants"][1], d), 64)   # y el jungla, su jungla

    def test_partidas_guardadas_con_la_regla_vieja_se_corrigen(self):
        import history
        tmp = tempfile.mkdtemp()
        gv = {"1": {"c": 58, "w": True, "r": "JUNGLE", "o": 11, "q": 420, "t": 1, "a": [], "p": []},
              "2": {"c": 1, "w": True, "r": "TOP", "o": 5, "q": 420, "t": 2, "a": [], "p": []},
              "3": {"c": 64, "w": True, "r": "JUNGLE", "o": 9, "q": 420, "t": 3, "a": [], "p": [], "rv": history.ROLE_V}}
        hv = {"1": {"id": "1", "c": 58, "r": "JUNGLE", "q": 420}, "2": {"id": "2", "c": 9, "r": "JUNGLE", "q": 450}}
        for f, d in (("games_x.json", gv), ("history_x.json", hv), ("history.json", hv)):
            json.dump(d, open(os.path.join(tmp, f), "w"))
        json.dump({"v": 1}, open(os.path.join(tmp, "history_owner.json"), "w"))
        json.dump({"1": 1}, open(os.path.join(tmp, "history_x.json.bak"), "w"))
        core._roles_1(tmp)
        g = json.load(open(os.path.join(tmp, "games_x.json")))
        self.assertEqual((g["1"]["r"], g["1"]["o"]), ("", 0))              # jungla sin comprobar: sin línea ni rival
        self.assertEqual((g["2"]["r"], g["2"]["o"]), ("TOP", 5))           # lo demás, intacto
        self.assertEqual((g["3"]["r"], g["3"]["o"]), ("JUNGLE", 9))        # lo ya comprobado con la regla nueva, intacto
        for f in ("history_x.json", "history.json"):
            self.assertEqual(json.load(open(os.path.join(tmp, f)))["1"]["r"], "")
        self.assertEqual(json.load(open(os.path.join(tmp, "history_owner.json"))), {"v": 1})

    def test_las_partidas_que_el_cliente_ya_no_lista_se_recalculan_con_su_detalle(self):
        import history
        tmp, antes = tempfile.mkdtemp(), (core.CACHE, history.ACCOUNT)
        core.CACHE, history.ACCOUNT = tmp, ""
        core._DIAG["last"] = ""

        def detalle(gid, champ, s1, s2, item):
            yo = {"participantId": 1, "teamId": 100, "championId": champ, "spell1Id": s1, "spell2Id": s2,
                  "stats": {"win": True, "roleBoundItem": item, "kills": 1, "deaths": 1, "assists": 1}, "timeline": {"lane": "JUNGLE", "role": "NONE"}}
            rival = {"participantId": 2, "teamId": 200, "championId": 86, "spell1Id": 4, "spell2Id": 12,
                     "stats": {"win": False, "roleBoundItem": 1220}, "timeline": {"lane": "TOP", "role": "SOLO"}}
            return {"gameId": gid, "gameCreation": gid, "gameDuration": 1500, "queueId": 420, "participants": [yo, rival],
                    "participantIdentities": [{"participantId": 1, "player": {"puuid": "yo"}}, {"participantId": 2, "player": {"puuid": "otro"}}]}
        detalles = {"1": detalle(1, 58, 4, 14, 1220), "2": detalle(2, 11, 11, 4, 1209)}      # 1: toplane etiquetado como jungla; 2: jungla de verdad

        class Lcu:
            def __init__(self): self.pedidas = []
            def get(self, path, timeout=0):
                gid = path.rsplit("/", 1)[-1]
                self.pedidas.append(gid)
                if gid == "3": raise ConnectionError("cerrado")
                return detalles.get(gid)                                                     # el 4 ya no existe: None
        try:
            gc = {"1": {"c": 58, "w": True, "r": "", "o": 0, "q": 420, "t": 1, "a": [], "p": []},
                  "2": {"c": 11, "w": True, "r": "", "o": 0, "q": 420, "t": 2, "a": [], "p": []},
                  "4": {"c": 9, "w": True, "r": "JUNGLE", "o": 3, "q": 420, "t": 4, "a": [], "p": []},
                  "5": {"c": 5, "w": True, "r": "TOP", "o": 7, "q": 420, "t": 5, "a": [], "p": [], "rv": history.ROLE_V},   # ya al día: no se pide
                  "6": {"c": 5, "w": True, "r": "", "o": 0, "q": 450, "t": 6, "a": [], "p": []}}                          # ARAM: no cuenta
            lcu = Lcu()
            self.assertTrue(core._refresh_old_games(lcu, "yo", gc))
            self.assertEqual(lcu.pedidas, ["4", "2", "1"])                  # de la más reciente a la más antigua; el 5 y el 6 no se piden
            self.assertEqual((gc["1"]["r"], gc["1"]["o"], gc["1"]["rv"]), ("TOP", 86, history.ROLE_V))
            self.assertEqual((gc["2"]["r"], gc["2"]["rv"]), ("JUNGLE", history.ROLE_V))
            self.assertEqual(gc["4"]["r"], "JUNGLE")                        # sin detalle: se deja como está...
            self.assertEqual(gc["4"]["rv"], history.ROLE_V)                 # ...y no se vuelve a pedir
            self.assertEqual(gc["6"].get("rv"), None)
            self.assertFalse(core._refresh_old_games(lcu, "yo", gc))        # ya no queda nada pendiente
            self.assertEqual(lcu.pedidas, ["4", "2", "1"])
            hist = json.load(open(os.path.join(tmp, "history.json")))
            self.assertEqual((hist["1"]["r"], hist["2"]["r"]), ("TOP", "JUNGLE"))
            # si el cliente se cierra a mitad, se para sin marcar las que faltan
            gc2 = {"7": {"c": 1, "w": True, "r": "", "o": 0, "q": 420, "t": 7, "a": [], "p": []},
                   "3": {"c": 1, "w": True, "r": "", "o": 0, "q": 420, "t": 3, "a": [], "p": []}}
            core._refresh_old_games(Lcu(), "yo", gc2)
            self.assertEqual(gc2["3"].get("rv"), None)
        finally:
            core.CACHE, history.ACCOUNT = antes

    def test_al_conectar_se_recalculan_las_partidas_de_la_ventana_del_cliente(self):
        import history
        from cliente_falso import ClienteFalso, YO
        tmp, antes = tempfile.mkdtemp(), (core.CACHE, history.ACCOUNT)
        core.CACHE, history.ACCOUNT = tmp, ""
        core._DIAG["last"] = ""
        try:
            def juego(gid, champ, lane, s1, s2, item, queue=420):
                return {"gameId": gid, "gameCreation": gid, "gameDuration": 1500, "queueId": queue, "gameMode": "CLASSIC",
                        "gameType": "MATCHED_GAME", "participantIdentities": [{"participantId": 1, "player": {"puuid": YO}}],
                        "participants": [{"participantId": 1, "teamId": 100, "championId": champ, "spell1Id": s1, "spell2Id": s2,
                                          "stats": {"win": True, "kills": 1, "deaths": 1, "assists": 1, "roleBoundItem": item},
                                          "timeline": {"lane": lane, "role": "NONE"}}]}
            fake = ClienteFalso()
            fake.viejas = [juego(11, 58, "JUNGLE", 4, 14, 1220), juego(12, 11, "JUNGLE", 11, 4, 1209)]
            antiguo = {"11": {"c": 58, "w": True, "r": "JUNGLE", "o": 7, "q": 420, "t": 11, "a": [], "p": []},
                       "12": {"c": 11, "w": True, "r": "JUNGLE", "o": 7, "q": 420, "t": 12, "a": [], "p": []}}
            json.dump(antiguo, open(os.path.join(tmp, f"games_{YO}.json"), "w"))
            P = core.load_player_data(fake, {})
            g = json.load(open(os.path.join(tmp, f"games_{YO}.json")))
            self.assertEqual((g["11"]["r"], g["11"]["rv"]), ("TOP", history.ROLE_V))     # Renekton: toplane
            self.assertEqual((g["12"]["r"], g["12"]["rv"]), ("JUNGLE", history.ROLE_V))  # el que sí lleva Aplastar
            self.assertEqual(P["rstats"].get((58, "TOP")), [1, 1])
            self.assertNotIn((58, "JUNGLE"), P["rstats"])
            self.assertEqual(P["rstats"].get((11, "JUNGLE")), [1, 1])
            self.assertIn("pasa de «JUNGLE» a «TOP»", open(os.path.join(tmp, "diag.log"), encoding="utf-8").read())
            hist = json.load(open(os.path.join(tmp, f"history_{YO}.json")))
            self.assertEqual(hist["11"]["r"], "TOP")
        finally:
            core.CACHE, history.ACCOUNT = antes


class FallosQueDejanRastro(unittest.TestCase):
    def setUp(self):
        self.tmp, self.cache = tempfile.mkdtemp(), core.CACHE
        core.CACHE = self.tmp
        core._DIAG["last"] = ""

    def tearDown(self):
        core.CACHE = self.cache

    def leer(self, name):
        p = os.path.join(self.tmp, name)
        return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

    def test_cliente_que_no_responde_va_al_diagnostico_y_un_fallo_del_programa_al_registro(self):
        try:
            raise ConnectionError("cerrado")
        except Exception:
            core.soft_fail("Leer tus maestrías")
        self.assertIn("Leer tus maestrías: el cliente no respondió", self.leer("diag.log"))
        self.assertEqual(self.leer("error.log"), "")
        try:
            {}["falta"]
        except Exception:
            core.soft_fail("Leer tu perfil y tu rango")
        self.assertIn("KeyError", self.leer("error.log"))

    def test_las_lecturas_de_otros_jugadores_tambien_avisan(self):
        import players
        self.assertIs(players.on_fail, core.soft_fail)

        class Roto:
            def get(self, path, timeout=0):
                if "summoners-by-puuid" in path or "ranked-stats" in path: return {}
                raise ConnectionError()
        players._cache.pop("zz", None)
        p = players.fetch_player(Roto(), "zz")
        players._cache.pop("zz", None)
        self.assertEqual(p["recent"], [])                                   # sigue devolviendo al jugador, sin datos
        self.assertIn("de un jugador: el cliente no respondió", self.leer("diag.log"))

    def test_version_de_los_datos_guardados(self):
        self.assertEqual(core.check_schema(), core.SCHEMA)
        self.assertEqual(json.loads(self.leer("schema.json"))["v"], core.SCHEMA)
        json.dump({"v": core.SCHEMA + 5}, open(os.path.join(self.tmp, "schema.json"), "w"))
        self.assertEqual(core.check_schema(), core.SCHEMA + 5)              # datos de una versión más nueva: no se tocan
        self.assertEqual(json.loads(self.leer("schema.json"))["v"], core.SCHEMA + 5)
        self.assertIn("más nueva", self.leer("diag.log"))
        json.dump({"v": 1}, open(os.path.join(self.tmp, "schema.json"), "w"))
        hechos, orig_s, orig_m = [], core.SCHEMA, core.MIGRATIONS
        core.SCHEMA, core.MIGRATIONS = 3, {1: lambda c: hechos.append(1), 2: lambda c: hechos.append(2)}
        try:
            self.assertEqual(core.check_schema(), 3)
        finally:
            core.SCHEMA, core.MIGRATIONS = orig_s, orig_m
        self.assertEqual(hechos, [1, 2])                                    # una a una y en orden
        self.assertEqual(json.loads(self.leer("schema.json"))["v"], 3)


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
