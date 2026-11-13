"""Cliente de League of Legends de mentira para probar el bucle principal sin abrir el juego.

Responde a las mismas rutas que usa LOL-E (`get(ruta)`) siguiendo un guion por pasos:
cola -> partida encontrada -> selección de campeón -> partida en curso -> fin de partida.
El guion avanza un paso cada vez que el bucle «duerme» (ver `dormir`), así que la prueba dura décimas de segundo.

Las respuestas son inventadas con la forma que entrega el cliente real; no son grabaciones de una partida.
"""
import copy, re

YO = "yo-puuid-0001"
GUION = ["None", "Matchmaking", "ReadyCheck", "ChampSelect", "ChampSelect", "InProgress", "InProgress", "EndOfGame", "None", "None"]


def partida(gid, champ, win, t, queue=450, puuid=YO, lane="NONE", role="NONE", item=0, spells=(4, 14)):
    """Una partida como las de la lista del historial: un solo participante (tú)."""
    return {"gameId": gid, "gameCreation": t, "gameDuration": 1200, "queueId": queue, "gameMode": "ARAM", "gameType": "MATCHED_GAME",
            "participantIdentities": [{"participantId": 1, "player": {"puuid": puuid}}],
            "participants": [{"participantId": 1, "teamId": 100, "championId": champ, "spell1Id": spells[0], "spell2Id": spells[1],
                              "stats": {"win": win, "kills": 5, "deaths": 3, "assists": 9, "totalMinionsKilled": 40,
                                        "neutralMinionsKilled": 0, "champLevel": 16, "totalDamageDealtToChampions": 21000,
                                        "goldEarned": 11000, "visionScore": 0, "roleBoundItem": item},
                              "timeline": {"lane": lane, "role": role}}]}


def detalle(gid, champ, win, t, queue=420, puuid=YO):
    """Detalle de una partida de la Grieta como lo entrega el cliente (los 10 jugadores), con el defecto real: la etiqueta de línea
    falla (tu toplane, y el toplane rival, llegan como «JUNGLE»). Las señales fiables (objeto de rol, Aplastar) sí son correctas.
    Anonimizado: identificadores inventados."""
    def p(pid, team, c, lane, role, item, smite=False, pu=""):
        return {"participantId": pid, "teamId": team, "championId": c, "spell1Id": 11 if smite else 4, "spell2Id": 14,
                "stats": {"win": (team == 100) == win, "roleBoundItem": item, "kills": 2, "deaths": 2, "assists": 2},
                "timeline": {"lane": lane, "role": role}}, {"participantId": pid, "player": {"puuid": pu}}
    filas = [p(1, 100, champ, "JUNGLE", "NONE", 1220, False, puuid), p(2, 100, 64, "JUNGLE", "NONE", 1209, True, "a1"),
             p(3, 100, 103, "MIDDLE", "SOLO", 1206, False, "a2"), p(4, 100, 222, "BOTTOM", "CARRY", 3006, False, "a3"),
             p(5, 100, 89, "BOTTOM", "SUPPORT", 2055, False, "a4"),
             p(6, 200, 157, "JUNGLE", "NONE", 1220, False, "r1"), p(7, 200, 23, "JUNGLE", "NONE", 1209, True, "r2"),
             p(8, 200, 134, "MIDDLE", "SOLO", 1206, False, "r3"), p(9, 200, 51, "BOTTOM", "CARRY", 3009, False, "r4"),
             p(10, 200, 412, "BOTTOM", "SUPPORT", 2055, False, "r5")]
    return {"gameId": gid, "gameCreation": t, "gameDuration": 1500, "queueId": queue, "gameMode": "CLASSIC", "gameType": "MATCHED_GAME",
            "participants": [a for a, _ in filas], "participantIdentities": [b for _, b in filas]}


SELECCION = {
    "localPlayerCellId": 0,
    "myTeam": [{"cellId": 0, "championId": 0, "assignedPosition": "top", "puuid": YO},
               {"cellId": 1, "championId": 64, "assignedPosition": "jungle", "puuid": "a1"},
               {"cellId": 2, "championId": 103, "assignedPosition": "middle", "puuid": "a2"},
               {"cellId": 3, "championId": 222, "assignedPosition": "bottom", "puuid": "a3"},
               {"cellId": 4, "championId": 89, "assignedPosition": "utility", "puuid": "a4"}],
    "theirTeam": [{"cellId": 5, "championId": 157, "assignedPosition": "top"}, {"cellId": 6, "championId": 0, "assignedPosition": "jungle"}],
    "bans": {"myTeamBans": [238], "theirTeamBans": [99]},
    "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 25000, "totalTimeInPhase": 30000},
    "actions": [[{"actorCellId": 0, "type": "pick", "isInProgress": True, "completed": False, "championId": 0}]],
    "benchChampions": [],
}


class ClienteFalso:
    def __init__(self, puuid=YO, guion=GUION, partida_nueva=900):
        self.puuid, self.guion, self.paso, self.nueva = puuid, list(guion), 0, partida_nueva
        self.pedidas = []
        self.viejas = [partida(100, 103, True, 1_000), partida(101, 86, False, 2_000)]
        self.detalles = {}   # gameId -> detalle de la Grieta (los 10 jugadores); lo demás devuelve None, como el cliente con una partida que ya no tiene

    # ---- el reloj del guion ----
    @property
    def fase(self):
        return self.guion[min(self.paso, len(self.guion) - 1)]

    @property
    def terminado(self):
        return self.paso >= len(self.guion)

    def dormir(self, _s=0):
        self.paso += 1

    # ---- respuestas ----
    def historial(self):
        fin = "EndOfGame" in self.guion[: self.paso + 1]
        return ([partida(self.nueva, 86, True, 9_000, queue=420, lane="JUNGLE", item=1220)] if fin else []) + self.viejas[::-1]

    def get(self, path, timeout=None):
        self.pedidas.append(path)
        f = self.fase
        if path == "/lol-champ-select/v1/session":
            if f != "ChampSelect":
                return None
            s = copy.deepcopy(SELECCION)
            if self.guion[: self.paso + 1].count("ChampSelect") > 1:   # segundo paso: ya has bloqueado a Garen
                s["myTeam"][0]["championId"] = 86
                s["actions"] = [[{"actorCellId": 0, "type": "pick", "isInProgress": False, "completed": True, "championId": 86}]]
            return s
        if path == "/lol-gameflow/v1/gameflow-phase":
            return f
        if path == "/lol-gameflow/v1/session":
            gd = {"queue": {"id": 420, "gameMode": "CLASSIC"}, "isCustomGame": False}
            if f == "InProgress":
                gd.update(gameId=self.nueva,
                          teamOne=[{"puuid": YO, "championId": 86, "selectedPosition": "TOP"}] +
                                  [{"puuid": f"a{i}", "championId": c, "selectedPosition": p}
                                   for i, (c, p) in enumerate(((64, "JUNGLE"), (103, "MIDDLE"), (222, "BOTTOM"), (89, "UTILITY")), 1)],
                          teamTwo=[{"puuid": f"r{i}", "championId": c, "selectedPosition": p}
                                   for i, (c, p) in enumerate(((157, "TOP"), (23, "JUNGLE"), (134, "MIDDLE"), (51, "BOTTOM"), (412, "UTILITY")), 1)],
                          playerChampionSelections=[])
            return {"gameData": gd, "map": {"gameMode": "CLASSIC"}}
        if path == "/lol-summoner/v1/current-summoner":
            return {"puuid": self.puuid, "gameName": "Prueba", "tagLine": "TEST", "summonerLevel": 100, "profileIconId": 1}
        if path.startswith("/lol-match-history/v1/products/lol/current-summoner/matches"):
            return {"games": {"games": self.historial()}}
        m = re.match(r"/lol-match-history/v1/games/(\d+)$", path)
        if m:
            gid = int(m.group(1))
            if gid == self.nueva and "EndOfGame" in self.guion[: self.paso + 1]:
                return detalle(gid, 86, True, 9_000, 420, self.puuid)
            return self.detalles.get(gid)
        if path == "/lol-champion-mastery/v1/local-player/champion-mastery":
            return [{"championId": 86, "championPoints": 50000}, {"championId": 103, "championPoints": 20000}]
        if path == "/lol-champions/v1/owned-champions-minimal":
            return [{"id": 86}, {"id": 103}, {"id": 54}]
        if path == "/lol-ranked/v1/current-ranked-stats":
            return {"queueMap": {}}
        return None   # lo demás (retos, honor, sala…) el cliente real también puede no darlo

    post = put = get
