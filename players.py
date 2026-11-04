"""Perfil propio y datos de los jugadores de tu equipo, todo leído de tu cliente de LoL (nada sale a internet)."""
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

TIERS_ES = {"IRON": "Hierro", "BRONZE": "Bronce", "SILVER": "Plata", "GOLD": "Oro", "PLATINUM": "Platino",
            "EMERALD": "Esmeralda", "DIAMOND": "Diamante", "MASTER": "Maestro", "GRANDMASTER": "Gran Maestro",
            "CHALLENGER": "Aspirante"}
APEX = ("MASTER", "GRANDMASTER", "CHALLENGER")
SR_QUEUES = {400, 420, 430, 440, 480, 490}
RANKED_QUEUES = {420, 440}
CACHE_TTL = 600  # los datos de un jugador valen 10 minutos


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
        pass
    try:
        ch = lcu.get("/lol-challenges/v1/summary-player-data/local-player") or {}
        lvl = (ch.get("overallChallengeLevel") or "").upper()
        if lvl and lvl != "NONE":
            cats = [{"cat": c.get("category", ""), "level": (c.get("level") or "").upper(), "pct": c.get("positionPercentile"),
                     "pts": c.get("current", 0), "max": c.get("max", 0)} for c in ch.get("categoryProgress") or [] if c.get("level")]
            out["challenges"] = {"level": lvl, "pct": ch.get("positionPercentile"), "points": ch.get("totalChallengeScore", 0),
                                 "next": ch.get("pointsUntilNextRank", 0), "cats": cats}
    except Exception:
        pass
    try:
        out["honor"] = (lcu.get("/lol-honor-v2/v1/profile") or {}).get("honorLevel")
    except Exception:
        pass
    try:
        sc = lcu.get("/lol-champion-mastery/v1/local-player/champion-mastery-score")
        if isinstance(sc, (int, float)):
            out["mastery_score"] = int(sc)
    except Exception:
        pass
    return out


def _role(p):
    t = p.get("timeline", {})
    lane = t.get("lane", "")
    if lane == "BOTTOM":
        return "SUPPORT" if t.get("role") == "SUPPORT" else "BOTTOM"
    return "" if lane in ("", "NONE") else lane


_cache = {}


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
    try:
        games = lcu.get(f"/lol-match-history/v1/products/lol/{puuid}/matches?begIndex=0&endIndex=20", timeout=20)["games"]["games"]
        rec = [{"c": g["participants"][0]["championId"], "w": bool(g["participants"][0]["stats"]["win"]), "q": g.get("queueId"),
                "role": _role(g["participants"][0])} for g in games]
        sr = [x for x in rec if x["q"] in SR_QUEUES]
        base = [x for x in sr if x["q"] in RANKED_QUEUES] or sr
        out["recent"] = base[:10]
        if out["recent"]:
            out["wr10"] = sum(x["w"] for x in out["recent"]) / len(out["recent"])
        out["top"] = [c for c, _ in Counter(x["c"] for x in sr).most_common(3)]
        out["roles"] = [r for r, _ in Counter(x["role"] for x in sr if x["role"]).most_common(2)]
    except Exception:
        pass
    try:
        out["mastery"] = {m["championId"]: m["championPoints"] for m in lcu.get(f"/lol-champion-mastery/v1/{puuid}/champion-mastery") or []}
    except Exception:
        pass
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
    if not pus:
        emit({})
        return

    def one(pu):
        try:
            found[pu] = fetch_player(lcu, pu)
        except Exception:
            found[pu] = {"puuid": pu, "name": "", "error": True}
        emit(dict(found))
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(one, pus))


def lobby_party(lcu, my_puuid):
    """Puuids del resto de tu grupo (dúo o grupo de 5) mientras estás en la sala."""
    lob = lcu.get("/lol-lobby/v2/lobby")
    if not lob:
        return None
    return {m["puuid"] for m in lob.get("members", []) if m.get("puuid") and m["puuid"] != my_puuid}
