"""Perfil propio y datos de los jugadores de tu equipo, todo leído de tu cliente de LoL (nada sale a internet)."""
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import history

TIERS_ES = {"IRON": "Hierro", "BRONZE": "Bronce", "SILVER": "Plata", "GOLD": "Oro", "PLATINUM": "Platino",
            "EMERALD": "Esmeralda", "DIAMOND": "Diamante", "MASTER": "Maestro", "GRANDMASTER": "Gran Maestro",
            "CHALLENGER": "Aspirante"}
APEX = ("MASTER", "GRANDMASTER", "CHALLENGER")
SR_QUEUES = {400, 420, 430, 440, 480, 490, 700, 710}
RANKED_QUEUES = {420, 440, 710}
CACHE_TTL = 600  # los datos de un jugador valen 10 minutos


on_fail = None   # lo pone lol_advisor: deja rastro de una lectura fallida (este módulo no puede importarlo: sería circular)


def _fail(where):
    if on_fail:
        on_fail(where)


def rank_info(q):
    if not q or not q.get("tier"):
        return None
    t = q["tier"].upper()
    w, l = q.get("wins", 0), q.get("losses", 0)
    return {"key": t, "tier": TIERS_ES.get(t, t.title()), "div": "" if t in APEX else q.get("division", ""),
            "lp": q.get("leaguePoints", 0), "w": w, "l": l, "wr": (w / (w + l)) if w + l else 0.0}


def load_profile(lcu):
    """Tu invocador: nombre, nivel, icono y rango en Solo/Dúo y Flexible."""
    me = lcu.get("/lol-summoner/v1/current-summoner") or {}
    qm = (lcu.get("/lol-ranked/v1/current-ranked-stats") or {}).get("queueMap", {})
    return {"name": me.get("gameName", ""), "tag": me.get("tagLine", ""), "level": me.get("summonerLevel", 0),
            "icon": me.get("profileIconId", 0), "puuid": me.get("puuid", ""),
            "solo": rank_info(qm.get("RANKED_SOLO_5x5")), "flex": rank_info(qm.get("RANKED_FLEX_SR")),
            "prem": rank_info(qm.get("RANKED_PREMADE_5x5")),
            "extra": load_extra(lcu)}


def load_extra(lcu):
    """Rango máximo, retos, honor y maestría total, leídos de tu cliente. Cada dato es opcional: si falta, no se muestra."""
    out = {}
    try:
        st = lcu.get("/lol-ranked/v1/current-ranked-stats") or {}
        qm = st.get("queueMap") or {}
        solo = qm.get("RANKED_SOLO_5x5") or {}
        order = {"I": 0, "II": 1, "III": 2, "IV": 3}
        entries = [e for e in list(qm.values()) + [st.get("highestRankedEntry") or {}] if isinstance(e, dict)]
        best = [(e.get("highestTier") or "").upper() for e in entries]
        tiers = list(TIERS_ES)
        peak_t = (st.get("highestCurrentSeasonReachedTierSR") or "").upper()
        if not peak_t or peak_t == "NONE":  # sin dato global: el mejor de las colas
            peak_t = max((t for t in best if t in tiers), key=tiers.index, default="")
        if peak_t and peak_t not in ("NONE", "NA"):
            divs = [e.get("highestDivision") for e in entries if (e.get("highestTier") or "").upper() == peak_t and e.get("highestDivision") in order]
            out["peak"] = {"key": peak_t, "tier": TIERS_ES.get(peak_t, peak_t.title()),
                           "div": "" if peak_t in APEX else (min(divs, key=order.get) if divs else "")}
        prev_t = (solo.get("previousSeasonEndTier") or st.get("highestPreviousSeasonEndTier") or "").upper()
        if prev_t and prev_t not in ("NONE", "NA"):
            out["prev"] = {"key": prev_t, "tier": TIERS_ES.get(prev_t, prev_t.title()),
                           "div": "" if prev_t in APEX else (solo.get("previousSeasonEndDivision") or st.get("highestPreviousSeasonEndDivision") or "").replace("NA", "")}
    except Exception:
        _fail("Leer tu rango máximo")
    try:
        ch = lcu.get("/lol-challenges/v1/summary-player-data/local-player") or {}
        lvl = (ch.get("overallChallengeLevel") or "").upper()
        if lvl and lvl != "NONE":
            cats = [{"cat": c.get("category", ""), "level": (c.get("level") or "").upper(), "pct": c.get("positionPercentile"),
                     "pts": c.get("current", 0), "max": c.get("max", 0)} for c in ch.get("categoryProgress") or [] if c.get("level")]
            out["challenges"] = {"level": lvl, "pct": ch.get("positionPercentile"), "points": ch.get("totalChallengeScore", 0),
                                 "next": ch.get("pointsUntilNextRank", 0), "cats": cats}
    except Exception:
        _fail("Leer tus retos")
    try:
        out["honor"] = (lcu.get("/lol-honor-v2/v1/profile") or {}).get("honorLevel")
    except Exception:
        _fail("Leer tu honor")
    try:
        sc = lcu.get("/lol-champion-mastery/v1/local-player/champion-mastery-score")
        if isinstance(sc, (int, float)):
            out["mastery_score"] = int(sc)
    except Exception:
        _fail("Leer tu puntuación de maestría")
    return out


def _role(p):
    t = p.get("timeline", {})
    lane = t.get("lane", "")
    if lane == "BOTTOM":
        return "SUPPORT" if t.get("role") == "SUPPORT" else "BOTTOM"
    return "" if lane in ("", "NONE") else lane


_cache = {}


def marks_info(st):
    """Rango más alto de la temporada y rango con el que terminó la anterior."""
    out = {}
    pk = (st.get("highestCurrentSeasonReachedTierSR") or "").upper()
    if pk and pk not in ("NONE", "NA"):
        out["peak"] = TIERS_ES.get(pk, pk.title())
    pv = (st.get("highestPreviousSeasonEndTier") or "").upper()
    if pv and pv not in ("NONE", "NA"):
        dv = (st.get("highestPreviousSeasonEndDivision") or "").replace("NA", "")
        out["prev"] = (TIERS_ES.get(pv, pv.title()) + (" " + dv if dv and pv not in APEX else "")).strip()
    return out


def recent_stats(recent, sr, allrec):
    """Cifras de sus últimas partidas de Grieta: KDA, CS, daño, visión, racha, campeones y líneas."""
    st = {"n": len(recent)}
    if recent:
        mins = sum(x["dur"] for x in recent) / 60 or 1
        k, d, a = (sum(x[f] for x in recent) for f in "kda")
        st.update(k=k / len(recent), d=d / len(recent), a=a / len(recent), kda=(k + a) / max(1, d), cspm=sum(x["cs"] for x in recent) / mins,
                  dpm=sum(x["dmg"] for x in recent) / mins, vpm=sum(x["vis"] for x in recent) / mins,
                  dur=sum(x["dur"] for x in recent) / len(recent))
        run = 0
        for x in recent:
            if run == 0:
                run = 1 if x["w"] else -1
            elif (run > 0) == x["w"]:
                run += 1 if run > 0 else -1
            else:
                break
        st["streak"] = run
    by = {}
    for x in sr:
        b = by.setdefault(x["c"], [0, 0, 0, 0, 0])
        b[0] += 1; b[1] += x["w"]; b[2] += x["k"]; b[3] += x["d"]; b[4] += x["a"]
    st["champs"] = [{"c": c, "n": b[0], "w": b[1], "kda": (b[2] + b[4]) / max(1, b[3])} for c, b in sorted(by.items(), key=lambda kv: -kv[1][0])[:5]]
    rc = Counter(x["role"] for x in sr if x["role"])
    tot = sum(rc.values()) or 1
    st["roles"] = [(r, n / tot) for r, n in rc.most_common(3)]
    st["sr_n"] = len(sr)
    if st["champs"] and len(sr) >= 6 and st["champs"][0]["n"] / len(sr) >= .5:
        st["otp"] = st["champs"][0]["c"]
    if allrec:
        st["last_days"] = max(0, (time.time() * 1000 - max(x["t"] for x in allrec)) / 86400000)
    return st


def fetch_player(lcu, puuid):
    """Resumen de un jugador: nombre, nivel, rangos, últimas partidas, campeones y roles habituales y maestrías."""
    hit = _cache.get(puuid)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    out = {"puuid": puuid, "name": "", "level": 0, "icon": 0, "solo": None, "flex": None, "recent": [], "wr10": None,
           "top": [], "roles": [], "mastery": {}}
    s = lcu.get(f"/lol-summoner/v1/summoners-by-puuid-cached/{puuid}") or {}
    out.update(name=s.get("gameName") or s.get("displayName") or "", level=s.get("summonerLevel", 0), icon=s.get("profileIconId", 0))
    qm = (lcu.get(f"/lol-ranked/v1/ranked-stats/{puuid}") or {}).get("queueMap", {})
    out["solo"], out["flex"] = rank_info(qm.get("RANKED_SOLO_5x5")), rank_info(qm.get("RANKED_FLEX_SR"))
    out["prem"] = rank_info(qm.get("RANKED_PREMADE_5x5"))   # clasificatorias de 5: su propia escalera
    out["marks"] = marks_info(lcu.get(f"/lol-ranked/v1/ranked-stats/{puuid}") or {})
    try:
        games = lcu.get(f"/lol-match-history/v1/products/lol/{puuid}/matches?begIndex=0&endIndex=20", timeout=20)["games"]["games"]
        rec = []
        for g in games:
            pa = history.my_part(g, puuid)   # por puuid; nunca «el primero» si la lista trajera a los diez
            if pa is None:
                continue
            st = pa["stats"]
            rec.append({"c": pa["championId"], "w": bool(st["win"]), "q": g.get("queueId"), "role": _role(pa),
                        "k": st.get("kills", 0), "d": st.get("deaths", 0), "a": st.get("assists", 0),
                        "cs": st.get("totalMinionsKilled", 0) + st.get("neutralMinionsKilled", 0),
                        "dmg": st.get("totalDamageDealtToChampions", 0), "vis": st.get("visionScore", 0),
                        "dur": g.get("gameDuration", 0), "t": g.get("gameCreation", 0)})
        sr = [x for x in rec if x["q"] in SR_QUEUES]
        base = [x for x in sr if x["q"] in RANKED_QUEUES] or sr
        out["recent"] = base[:10]
        if out["recent"]:
            out["wr10"] = sum(x["w"] for x in out["recent"]) / len(out["recent"])
        out["top"] = [c for c, _ in Counter(x["c"] for x in sr).most_common(3)]
        out["roles"] = [r for r, _ in Counter(x["role"] for x in sr if x["role"]).most_common(2)]
        out["stats"] = recent_stats(out["recent"], sr, rec)
    except Exception:
        _fail("Leer las partidas de un jugador")
    try:
        ms = lcu.get(f"/lol-champion-mastery/v1/{puuid}/champion-mastery") or []
        out["mastery"] = {m["championId"]: m["championPoints"] for m in ms}
        out["mastery_top"] = [{"c": m["championId"], "pts": m["championPoints"], "lvl": m.get("championLevel", 0), "last": m.get("lastPlayTime", 0)}
                              for m in sorted(ms, key=lambda m: -m["championPoints"])[:5]]
    except Exception:
        _fail("Leer las maestrías de un jugador")
    _cache[puuid] = (time.time(), out)
    return out


def team_puuids(lcu, session):
    """[(celda, puuid)] de tus aliados (sin ti). Si el cliente no da el puuid, se resuelve por el id de invocador."""
    me = session["localPlayerCellId"]
    res = []
    for p in session["myTeam"]:
        if p["cellId"] == me:
            continue
        pu = p.get("puuid") or ""
        if not pu and p.get("summonerId"):
            pu = (lcu.get(f"/lol-summoner/v1/summoners/{p['summonerId']}") or {}).get("puuid", "")
        res.append((p["cellId"], pu))
    return res


def fetch_team(lcu, session, emit):
    """Carga en paralelo a tus aliados y va avisando con emit({puuid: datos}) cada vez que llega uno."""
    found = {}
    pus = [pu for _, pu in team_puuids(lcu, session) if pu]
    # en algunas colas (clasificatorias de 5, Clash) el cliente enseña también los nombres del equipo rival: se leen primero (deciden los bans)
    rivals = [p["puuid"] for p in session.get("theirTeam", []) if p.get("puuid")]
    pus = rivals + [pu for pu in pus if pu not in rivals]
    if not pus:
        emit({})
        return

    def one(pu):
        try:
            found[pu] = fetch_player(lcu, pu)
        except Exception:
            found[pu] = {"puuid": pu, "name": "", "error": True}
        emit(dict(found))
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(one, pus))


ROLE_ORDER = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT"]


def game_roster(gf, my_puuid):
    """Los 10 jugadores de la partida en curso a partir de la sesión de gameflow (pantalla de carga y partida):
    [{team: «ally»|«enemy», cid, puuid, role, spells, me}], aliados primero y por línea. None si el cliente aún no los da
    o si no se sabe cuál es tu equipo (espectador)."""
    gd = (gf or {}).get("gameData") or {}
    one, two = gd.get("teamOne") or [], gd.get("teamTwo") or []
    if not one and not two:
        return None
    spells = {s.get("puuid"): [s.get("spell1Id", 0), s.get("spell2Id", 0)] for s in gd.get("playerChampionSelections") or [] if s.get("puuid")}
    mine = next((t for t in (one, two) if any(p.get("puuid") == my_puuid for p in t)), None) if my_puuid else None
    if mine is None:
        return None
    out = []
    for team, lst in (("ally", mine), ("enemy", two if mine is one else one)):
        for p in lst:
            pu = p.get("puuid") or ""
            role = (p.get("selectedPosition") or "").upper()
            role = "SUPPORT" if role == "UTILITY" else role
            out.append({"team": team, "cid": p.get("championId") or 0, "puuid": pu, "role": role if role in ROLE_ORDER else "",
                        "spells": spells.get(pu, []), "me": bool(pu) and pu == my_puuid, "icon": p.get("profileIconId", 0)})
    out.sort(key=lambda x: (x["team"] != "ally", ROLE_ORDER.index(x["role"]) if x["role"] else 9))
    return out


def fetch_roster(lcu, roster, emit, progress=None):
    """Lee en paralelo el perfil de los jugadores de la partida (incluido el tuyo) y avisa UNA sola vez con emit({puuid: datos}) cuando han llegado todos (así la pantalla se dibuja una vez, sin recargarse por cada jugador).
    `progress(hechos, total)` va diciendo cuántos faltan, para un contador sin redibujar nada."""
    found = {}
    pus = [x["puuid"] for x in roster if x["puuid"]]   # también el tuyo: tus 10 últimas y tu rendimiento salen igual que los de los demás
    if not pus:
        emit({})
        return

    def one(pu):
        try:
            found[pu] = fetch_player(lcu, pu)
        except Exception:
            found[pu] = {"puuid": pu, "name": "", "error": True}
        if progress:
            progress(len(found), len(pus))
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(one, pus))
    emit(dict(found))


def lobby_party(lcu, my_puuid):
    """Puuids del resto de tu grupo (dúo o grupo de 5) mientras estás en la sala."""
    lob = lcu.get("/lol-lobby/v2/lobby")
    if not lob:
        return None
    return {m["puuid"] for m in lob.get("members", []) if m.get("puuid") and m["puuid"] != my_puuid}
