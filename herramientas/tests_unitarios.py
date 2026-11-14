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
