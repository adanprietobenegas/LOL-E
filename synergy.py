"""Sinergias entre campeones: reglas de composición + tu historial jugando con cada pareja."""


def _a(c, k, d=2):
    return (c.get("attr") or {}).get(k, d)


def _support_kind(c):
    if "Tank" in c["tags"] or _a(c, "control") >= 3:
        return "inicia"
    if _a(c, "utility") >= 2 and _a(c, "control") <= 2:
        return "protege"
    return "otro"


def pair(champs, a, b, lean, role=""):
    """Reglas entre un campeón candidato (a) y un aliado (b). Devuelve [(puntos, texto)]."""
    ca, cb = champs[a], champs[b]
    ta, tb = set(ca["tags"]), set(cb["tags"])
    pa, pb = set(ca.get("pos", [])), set(cb.get("pos", []))
    nb = cb["name"]
    out = []
    adc_a, sup_a = "BOTTOM" in pa and "Marksman" in ta, "SUPPORT" in pa
    adc_b, sup_b = "BOTTOM" in pb and "Marksman" in tb, "SUPPORT" in pb
    if adc_a and sup_b and role in ("", "BOTTOM"):
        k = _support_kind(cb)
        out.append({"inicia": (0.6, f"{nb} inicia el combate y tú rematas"),
                    "protege": (0.6, f"{nb} te protege y te potencia"),
                    "otro": (0.2, f"Formáis dúo de línea con {nb}")}[k])
    if sup_a and adc_b and role in ("", "SUPPORT"):
        k = _support_kind(ca)
        out.append({"inicia": (0.6, f"Inicias el combate para {nb}"),
                    "protege": (0.6, f"Proteges y potencias a {nb}"),
                    "otro": (0.2, f"Formáis dúo de línea con {nb}")}[k])
    front_a = "Tank" in ta or _a(ca, "toughness") >= 3
    front_b = "Tank" in tb or _a(cb, "toughness") >= 3
    carry_a = "Marksman" in ta or "Mage" in ta
    carry_b = "Marksman" in tb or "Mage" in tb
    if front_a and carry_b and not sup_a:
        out.append((0.35, f"Haces de primera línea para {nb}"))
    if front_b and carry_a and not sup_b:
        out.append((0.35, f"{nb} abre el combate para ti"))
    if "Assassin" in ta and _a(cb, "control") >= 3:
        out.append((0.3, f"El control de {nb} prepara tu entrada"))
    if "Assassin" in tb and _a(ca, "control") >= 3:
        out.append((0.3, f"Tu control prepara la entrada de {nb}"))
    la, lb = lean(ca), lean(cb)
    carries = (carry_a or "Assassin" in ta or "Fighter" in ta) and (carry_b or "Assassin" in tb or "Fighter" in tb)
    if carries and la * lb < -0.25 and abs(la) > .5 and abs(lb) > .5:
        out.append((0.25, f"Daño complementario con {nb} (físico y mágico)"))
    elif carries and la * lb > 0.6:
        out.append((-0.2, f"Hacéis el mismo tipo de daño que {nb}"))
    if "Tank" in ta and "Tank" in tb and _a(ca, "damage") <= 2 and _a(cb, "damage") <= 2:
        out.append((-0.3, f"Poco daño entre ambos con {nb}"))
    return out


def synergy_for(champs, cid, allies, pairs, lean, role="", min_pair=2):
    """Sinergia de un candidato con los aliados ya elegidos.
    Devuelve {'score': -1..1, 'items': [{ally, score, text, record}], 'why': [texto corto]}."""
    items = []
    for al in allies:
        if al not in champs or al == cid:
            continue
        ps = pair(champs, cid, al, lean, role)
        s = sum(p for p, _ in ps)
        g, w = pairs.get((cid, al), (0, 0))
        if g >= min_pair:  # lo que ya has vivido jugando con esta pareja
            s += ((w + 1) / (g + 2) - 0.5) * 1.2
        best = max(ps, key=lambda x: abs(x[0]))[1] if ps else ""
        items.append({"ally": al, "score": s, "text": best, "record": (g, w) if g else None})
    total = max(-1.0, min(1.0, sum(i["score"] for i in items) / 1.5)) if items else 0.0
    why = [i["text"] for i in sorted(items, key=lambda i: -i["score"]) if i["score"] >= 0.5 and i["text"]][:1]
    return {"score": total, "items": items, "why": why}
