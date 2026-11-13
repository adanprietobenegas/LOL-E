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

    def test_esquivar_la_partida_no_guarda_ni_analiza_nada(self):
        from cliente_falso import ClienteFalso
        ev = self.correr(ClienteFalso(guion=["None", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "None", "None"]))
        self.assertEqual(self.leer("error.log"), "")
        self.assertTrue([e for e in ev if e[0] == "show"])                              # la selección se llegó a enseñar
        self.assertTrue(any("Selección terminada" in e[2] for e in ev if e[0] == "idle"))
        self.assertFalse([e for e in ev if e[0] in ("roster", "analysis.load")])        # no hubo partida: ni jugadores ni análisis
        self.assertNotIn("Partida terminada", self.leer("diag.log"))
        self.assertEqual(sorted(json.loads(self.leer("history_" + __import__("cliente_falso").YO + ".json"))), ["100", "101"])

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

    def test_aram_no_compara_el_farmeo(self):
        import analysis
        hoy = self.g(100, 147, 8, 2, 8, q=450)
        r = analysis.vs_average(hoy, [self.g(i, 147, 2, 4, 6, q=450) for i in range(1, 5)])
        self.assertIsNone(r["cspm"])
        self.assertEqual(len(analysis.average_lines(r, "Seraphine")), 1)


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
        self.assertEqual((t["ORDER"]["towers"], t["CHAOS"]["towers"]), (1, 1))   # la T2 que cae la tumba ORDER; la T1, CHAOS
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
