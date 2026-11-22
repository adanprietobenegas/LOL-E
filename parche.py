"""Notas del parche: las notas OFICIALES de Riot en español (leagueoflegends.com/es-es), leídas de la propia web y convertidas en datos.

Sin ventana ni red dentro de las funciones de análisis (`parse`, `trend`…), para poder probarlas con textos de ejemplo. La descarga va aparte (`load`).

Por qué la web y no una API: Riot no publica las notas en ningún servicio abierto; sus páginas llevan el contenido como JSON incrustado (`__NEXT_DATA__`)
y el cuerpo de las notas como HTML con una estructura estable: títulos de sección (h2), una ficha por campeón u objeto (h3 + nota del diseñador +
habilidades con h4 + cambios «antes ⇒ después» en listas). Todo el texto sale tal cual lo escribió Riot en español: aquí no se traduce nada.
Si la web cambia y no se reconoce nada, `parse` devuelve secciones vacías y la pantalla lo dice (y enseña el enlace a la página oficial).

Modelo de salida de `parse`:
  {"v": "26.22", "title", "date", "summary", "url", "banner", "authors": [...], "intro": [párrafos],
   "sections": [{"id", "title", "kind", "intro": [...], "groups": [{"title", "entries": [entrada], "bullets": [línea]}]}]}
  entrada: {"name", "kind": "champion|item|augment|rune|other", "tag": "NOVEDAD|…|None", "href", "icon", "note": [...], "blocks": [{"title", "icon", "lines": [línea]}], "verdict": …}
  línea: {"runs": [[texto, negrita]], "text", "label", "before", "after", "trend": +1|-1|0}
"""
import json, os, re, time, urllib.error, urllib.request
from html.parser import HTMLParser

# Interruptor de la pantalla «Parche»: encendida desde la 1.23.0 (el usuario la reservó hasta revisarla con un parche real; se revisó con el 26.23 el 22/11/2026).
# Para apagarla (p. ej. si Riot cambia su web y las notas dejan de leerse): variable de entorno LOLE_PARCHE=0, o poner False aquí.
ACTIVO = os.environ.get("LOLE_PARCHE", "1") != "0"

BASE = "https://www.leagueoflegends.com"
LIST_URL = BASE + "/es-es/news/tags/patch-notes/"
NOTE_URL = BASE + "/es-es/news/game-updates/league-of-legends-patch-{a}-{b}-notes"
UA = {"User-Agent": "Mozilla/5.0 (compatible; LOL-E)", "Accept-Language": "es-ES,es;q=0.9"}
VERSION = 3          # sube al cambiar la forma de los datos guardados: se vuelve a leer todo
TTL_CURRENT = 6 * 3600       # el último parche se relee de vez en cuando (Riot lo corrige)
TTL_OLD = 14 * 24 * 3600
TTL_LIST = 3 * 3600

# ---------------------------------------------------------------- árbol HTML mínimo
VOID = {"br", "hr", "img", "meta", "link", "input"}


class Node:
    def __init__(self, tag, attrs):
        self.tag, self.attrs, self.kids = tag, dict(attrs), []

    @property
    def cls(self):
        return (self.attrs.get("class") or "").split()


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", [])
        self.st = [self.root]

    def handle_starttag(self, t, a):
        n = Node(t, a)
        self.st[-1].kids.append(n)
        if t not in VOID:
            self.st.append(n)

    def handle_startendtag(self, t, a):
        self.st[-1].kids.append(Node(t, a))

    def handle_endtag(self, t):
        for i in range(len(self.st) - 1, 0, -1):
            if self.st[i].tag == t:
                del self.st[i:]
                return

    def handle_data(self, d):
        self.st[-1].kids.append(d)


def tree(html):
    b = _Builder()
    b.feed(html or "")
    return b.root


def clean(s):
    return re.sub(r"[ \t\r\f\v]+", " ", (s or "").replace("\xa0", " ").replace("​", "")).strip()


def text(n):
    if isinstance(n, str):
        return n
    if n.tag == "br":
        return "\n"
    return "".join(text(k) for k in n.kids)


def flat(n):
    """Texto de un nodo en una sola línea."""
    return clean(re.sub(r"\s+", " ", text(n)))


def runs(n):
    """[(texto, negrita)] de un nodo, fusionando tramos contiguos del mismo estilo."""
    out = []

    def go(x, bold):
        if isinstance(x, str):
            t = x.replace("\xa0", " ")
            if t:
                out.append([t, bold])
            return
        if x.tag == "br":
            out.append(["\n", bold])
            return
        b = bold or x.tag in ("strong", "b")
        for k in x.kids:
            go(k, b)
    go(n, False)
    merged = []
    for t, b in out:
        if merged and merged[-1][1] == b:
            merged[-1][0] += t
        else:
            merged.append([t, b])
    # recorte de espacios en los extremos
    if merged:
        merged[0][0] = merged[0][0].lstrip()
        merged[-1][0] = merged[-1][0].rstrip()
    return [[re.sub(r"[ \t]+", " ", t), b] for t, b in merged if t]


def find(n, pred, out=None):
    out = [] if out is None else out
    if isinstance(n, str):
        return out
    if pred(n):
        out.append(n)
    for k in n.kids:
        find(k, pred, out)
    return out


def first(n, pred):
    r = find(n, pred)
    return r[0] if r else None


# ---------------------------------------------------------------- tendencia de un cambio («antes ⇒ después»)
ARROW = "⇒"
NUM = re.compile(r"\d+(?:[.,]\d+)?")
LOWER_BETTER = ("enfriamiento", "coste", "recarga", "tiempo de lanzamiento", "retardo", "demora", "reutilización", "tiempo de carga",
                "tiempo de acumulación", "tiempo de preparación", "tiempo de canalización", "tiempo de lanzado", "tiempo de espera", "tiempo de activación", "tiempo de retraso")
NOT_LOWER = re.compile(r"^(recuperaci|reducci|restauraci|aceleraci|reinicio|reembolso)\w*\s+(de|del)\s+(el\s+|la\s+)?(enfriamiento|tiempo de recarga|recarga)")
HIGHER_WORSE = ("daño recibido", "daño sufrido")   # subirlo es peor para quien lo lleva (poco habitual; el resto se lee en sentido normal)


def nums(s):
    return [float(x.replace(",", ".")) for x in NUM.findall(s or "")]


SEQ = re.compile(r"\d+(?:[.,]\d+)?(?:\s*[/\-–]\s*\d+(?:[.,]\d+)?)*")


def skeleton(s):
    """El texto sin cifras (cada serie «50/75/100» o «8-30» cuenta como una): dos textos con el mismo esqueleto son el mismo tipo de dato con otros números."""
    s = re.sub(r"\([^()\d+\-][^()]*\)", "", (s or "").lower())   # aclaraciones como «(tarda 0,047 s más…)»
    s = SEQ.sub("#", s)
    s = re.sub(r"[^\W\d_]+", "", s)                              # sin palabras: «%», «s», «del PH»… no cambian el tipo de dato
    return re.sub(r"\s+", "", s)


def trend(label, before, after):
    """+1 si el cambio mejora lo que el campeón u objeto ofrece, -1 si lo empeora, 0 si no se sabe (cambios cualitativos, o textos que no son comparables:
    otra fórmula, otras unidades). Se compara número a número; en «enfriamiento», «coste»… bajar es mejorar. Es una estimación automática, no la opinión de Riot."""
    if after.lstrip().startswith("(") and "(" in before:   # «120/200/280 (+35 %) ⇒ (+40 %)»: lo que no se repite es lo que no cambia
        after = before.split("(", 1)[0].strip() + " " + after.strip()
    if skeleton(before) != skeleton(after):
        return 0
    b, a = nums(before), nums(after)
    if not b or not a:
        return 0
    sb, sa = SEQ.findall(before), SEQ.findall(after)

    def cmp(x, y):
        px, py = nums(x), nums(y)
        if not px or not py:
            return 0
        if len(px) == len(py):
            return (sum((q > p) - (q < p) for p, q in zip(px, py)) > 0) - (sum((q > p) - (q < p) for p, q in zip(px, py)) < 0)
        mx, my = sum(px) / len(px), sum(py) / len(py)
        return (my > mx) - (my < mx)
    # cada serie de cifras (base, relación con la habilidad…) vota; un cambio mixto («vida 640 ⇒ 590 pero +99 ⇒ +107 por nivel») queda en 0
    d = sum(cmp(x, y) for x, y in zip(sb, sa)) if len(sb) == len(sa) else (cmp(sb[0], sa[0]) if sb and sa else 0)
    d = (d > 0) - (d < 0)
    lab = (label or "").lower().strip()
    if NOT_LOWER.match(lab):   # «Recuperación de enfriamiento»: subirlo es bueno
        return d
    if any(k in lab for k in LOWER_BETTER) or any(lab.startswith(k) for k in HIGHER_WORSE):
        d = -d
    return d


def split_change(runs_):
    """(etiqueta, antes, después) de una línea con «⇒»; None si no es un cambio numérico. Las líneas con varias flechas (varios cambios) se devuelven enteras."""
    t = "".join(r[0] for r in runs_)
    if ARROW not in t:
        return None
    left, _, right = t.partition(ARROW)
    label = ""
    left = re.sub(r"^\s*(?:NOVEDAD|ELIMINADO|ACTUALIZACIÓN)\s+", "", left)
    if ":" in left:   # «Habilidad: Estadística: antes»: la etiqueta es todo lo anterior al último «:» (si no hay cifras antes de él)
        head, _, tail = left.rpartition(":")
        head = head.strip(" :")
        if 2 <= len(head) <= 140 and not re.search(r"\d\s*:\s*$", head):
            label, left = head, tail
    left = left.lstrip(": ")
    return label, clean(left), clean(right.rstrip(" .;"))


def make_line(r):
    runs_ = [x for x in r if x[0]]
    plain = clean("".join(x[0] for x in runs_))
    line = {"runs": runs_, "text": plain, "label": "", "before": "", "after": "", "trend": 0}
    sp = split_change(runs_)
    if sp:
        line["label"], line["before"], line["after"] = sp
        if plain.count(ARROW) == 1:
            line["trend"] = trend(sp[0], sp[1], sp[2])
        else:   # varios cambios en una línea: se suma lo que sube y baja
            parts = re.split(r"(?<=[\.\)])\s+(?=[A-ZÁÉÍÓÚ])", plain)
            tt = 0
            for p in parts:
                s2 = split_change([[p, False]])
                if s2:
                    tt += trend(s2[0], s2[1], s2[2])
            line["trend"] = (tt > 0) - (tt < 0)
    if re.match(r"^\s*ELIMINADO\b", plain):
        line["trend"] = -1
    return line


def verdict(blocks):
    """Resumen de una ficha: «Mejora», «Debilitación», «Mixto», «Novedad» o «Ajuste» según los cambios numéricos que pueda leer."""
    up = dn = 0
    for b in blocks:
        for ln in b["lines"]:
            if ln["trend"] > 0:
                up += 1
            elif ln["trend"] < 0:
                dn += 1
    if up and dn:
        return "mixed", up, dn
    if up:
        return "buff", up, dn
    if dn:
        return "nerf", up, dn
    return "adjust", up, dn


# ---------------------------------------------------------------- análisis del cuerpo de las notas
KIND_WORDS = (("campe", "champion"), ("objet", "item"), ("aument", "augment"), ("runa", "rune"))
CATEGORY_WORDS = ("campeones", "objetos", "aumentos", "sistemas", "runas", "corrección de errores", "mejoras de calidad", "mapa", "modos de juego", "hechizos de invocador")
TAGS = ("NOVEDAD", "ACTUALIZACIÓN", "ELIMINADO", "REVERTIDO", "VUELVE", "TEMPORAL")


def kind_of(title):
    t = (title or "").lower()
    for w, k in KIND_WORDS:
        if w in t:
            return k
    return "other"


def section_kind(title, sid=""):
    t = (title or "").lower()
    if "tft" in t or "teamfight" in t or "tft" in (sid or ""):
        return "tft"
    if "plato" in t or "highlight" in (sid or ""):
        return "highlights"
    if "aspecto" in t or "chroma" in t or "skins" in (sid or ""):
        return "skins"
    if "pase" in t:
        return "pass"
    if "corrección de errores" in t or "calidad" in t:
        return "bugs"
    if t.strip() == "campeones":
        return "champions"
    if t.strip() == "objetos":
        return "items"
    if "aram" in t:
        return "aram"
    if "arena" in t:
        return "arena"
    if "classic" in t:
        return "classic"
    return "other"


def _slug(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _tokens(sec):
    """Elementos de una sección en orden: ("quote", [párrafos]), ("hr",), ("h4", texto, es_habilidad, icono), ("h3", nombre, enlace, icono),
    ("p", runs, texto), ("ul", [runs de cada li]), ("img", url)."""
    toks = []
    pending_icon = [None]

    def go(n):
        if isinstance(n, str):
            return
        c, t = n.cls, n.tag
        if t == "blockquote":
            paras = [clean(x) for x in re.split(r"\n\s*\n|\n{2,}", text(n).replace("\r", ""))]
            paras = [p for p in (clean(re.sub(r"\s*\n\s*", " ", p)) for p in paras) if p]
            toks.append(("quote", paras))
            return
        if t == "hr":
            toks.append(("hr",))
            return
        if t == "h3":
            a = first(n, lambda x: x.tag == "a")
            toks.append(("h3", flat(n), (a.attrs.get("href") if a else "") or "", pending_icon[0], n.attrs.get("id", "")))
            pending_icon[0] = None
            return
        if t == "h4":
            im = first(n, lambda x: x.tag == "img")
            toks.append(("h4", flat(n), "ability-title" in c, im.attrs.get("src") if im else None, "skin-title" in c))
            return
        if t == "ul":
            toks.append(("ul", [runs(li) for li in n.kids if not isinstance(li, str) and li.tag == "li"]))
            return
        if t == "p":
            ref = first(n, lambda x: x.tag == "a" and "reference-link" in x.cls)
            if ref is not None:
                im = first(ref, lambda x: x.tag == "img")
                pending_icon[0] = (im.attrs.get("src") if im else None, ref.attrs.get("href") or "")
                return
            im = first(n, lambda x: x.tag == "img")
            r = runs(n)
            if r and flat(n):
                toks.append(("p", r, flat(n)))
            elif im is not None:
                toks.append(("img", im.attrs.get("src")))
            return
        if t == "img":
            toks.append(("img", n.attrs.get("src")))
            return
        for k in n.kids:
            go(k)
    go(sec)
    return toks


def _is_heading_p(tok, nxt):
    """Un párrafo corto que abre una ficha (campeón, objeto, aumento): sin «:» ni «⇒» y seguido de nota, lista o habilidad."""
    if tok[0] != "p":
        return False
    t = tok[2]
    if len(t) > 70 or ":" in t or ARROW in t or t.endswith("."):
        return False
    return bool(nxt) and nxt[0] in ("quote", "ul", "h4")


def _entry_name(t):
    """(etiqueta, nombre) de «NOVEDAD - Volibear» o de «Aatrox»."""
    m = re.match(r"^\s*(%s)\b\s*[-–—:]?\s*(.+)$" % "|".join(TAGS), t, re.I)
    if m:
        return m.group(1).upper(), clean(m.group(2))
    return None, clean(t)


def parse_section(node, sid, title):
    kind = section_kind(title, sid)
    sec = {"id": sid, "title": clean(title), "kind": kind, "intro": [], "groups": []}
    if kind in ("tft", "skins", "highlights"):
        sec["images"] = [t[1] for t in _tokens(node) if t[0] == "img" and t[1]] if kind == "highlights" else []
        return sec
    toks = _tokens(node)
    group = {"title": "", "kind": {"champions": "champion", "items": "item"}.get(kind, "other"), "entries": [], "bullets": []}
    sec["groups"].append(group)
    entry = block = None
    pend_note = []
    started = False

    def new_group(t):
        nonlocal group, entry, block
        group = {"title": clean(t), "kind": kind_of(t) if kind_of(t) != "other" else "other", "entries": [], "bullets": []}
        sec["groups"].append(group)
        entry = block = None

    def new_entry(name, tag=None, href="", icon=None):
        nonlocal entry, block
        entry = {"name": name, "kind": group["kind"], "tag": tag, "href": href, "icon": icon, "note": [], "blocks": []}
        block = {"title": "", "icon": None, "lines": []}
        entry["blocks"].append(block)
        group["entries"].append(entry)

    i = 0
    while i < len(toks):
        tok = toks[i]
        nxt = next((x for x in toks[i + 1:] if x[0] != "hr"), None)
        k = tok[0]
        if k == "quote":
            if entry is not None:
                entry["note"].extend(tok[1])
            elif not started and not group["title"]:
                sec["intro"].extend(tok[1])
            elif group["title"] and not group["entries"] and not group["bullets"] and not pend_note and nxt is None:
                sec["intro"].extend(tok[1])
            else:
                pend_note.extend(tok[1])
        elif k == "h3":
            started = True
            icon = None
            href = tok[2]
            ic = None
            new_entry(clean(tok[1]), None, href, None)
            entry["icon"] = tok[3][0] if tok[3] else None
            entry["slug"] = tok[4]
        elif k == "h4":
            _, ttl, ability, icon, skin = tok
            started = True
            low = ttl.lower()
            is_cat = any(w in low for w in CATEGORY_WORDS)
            heading = (not ability and not is_cat and not low.startswith("estad") and not skin and nxt is not None and len(ttl) < 70
                       and (nxt[0] in ("quote", "ul") or (nxt[0] == "h4" and nxt[2])))
            if heading:   # el nombre del campeón como h4 (sección Classic): abre ficha, no grupo ni bloque
                tag, name = _entry_name(ttl)
                new_entry(name, tag)
                if pend_note:
                    entry["note"].extend(pend_note)
                    pend_note = []
            elif (not ability) and (is_cat or entry is None) and not (entry is not None and low.startswith("estad")):
                new_group(ttl)
            else:
                if entry is None:
                    new_entry(ttl)
                    entry["blocks"] = []
                    entry["kind"] = "other"
                block = {"title": clean(ttl), "icon": icon, "lines": []}
                entry["blocks"] = [b for b in entry["blocks"] if b["lines"] or b["title"]] + [block]
        elif k == "p":
            started = True
            if entry is not None and tok[2].startswith("/") and len(tok[2]) < 60 and entry["blocks"] and entry["blocks"][-1]["title"] and not entry["blocks"][-1]["lines"]:
                # «Q - Bumerán» + «/Peñascazo» (la habilidad de Gnar cambia de forma): el segundo párrafo es la otra mitad del título, no una ficha
                entry["blocks"][-1]["title"] = clean(entry["blocks"][-1]["title"] + tok[2])
            elif re.match(r"^Correcci.{1,2}n de errores", tok[2]) and len(tok[2]) < 40:
                new_group(tok[2])   # «Corrección de errores» en negrita dentro de Classic: un grupo de viñetas, no un campeón
            elif entry is not None and nxt and nxt[0] == "ul" and re.match(r"^(Pasiva|P|Q|W|E|R)\s*[-–—]\s*\S|^Estad[ií]sticas\b", tok[2]) and len(tok[2]) < 90:
                # «Q - Golpe de erizo de mar» como párrafo en negrita: es el título de una habilidad de la ficha abierta, no una ficha nueva
                block = {"title": clean(tok[2]), "icon": None, "lines": []}
                entry["blocks"] = [x for x in entry["blocks"] if x["lines"] or x["title"]] + [block]
            elif _is_heading_p(tok, nxt):
                tag, name = _entry_name(tok[2])
                new_entry(name, tag)
                if pend_note:
                    entry["note"].extend(pend_note)
                    pend_note = []
            elif entry is None and not group["title"]:
                # párrafo suelto antes de cualquier ficha: va a la introducción de la sección
                sec["intro"].append(tok[2])
            elif entry is None:
                group["bullets"].append(make_line(tok[1]))
            else:
                block["lines"].append(make_line(tok[1]))
        elif k == "ul":
            started = True
            rows = []
            for r in tok[1]:
                if not flat_runs(r):
                    continue
                if flat_runs(r).startswith(ARROW) and rows:   # Riot parte a veces «antes» y «⇒ después» en dos elementos de la lista
                    rows[-1] = rows[-1] + [[" ", False]] + r
                else:
                    rows.append(r)
            for r in rows:
                if entry is None:
                    group["bullets"].append(make_line(r))
                else:
                    block["lines"].append(make_line(r))
        i += 1
    for g in sec["groups"]:
        for e in g["entries"]:
            e["blocks"] = [b for b in e["blocks"] if b["lines"]]
            e["verdict"], e["up"], e["down"] = verdict(e["blocks"])
            if e.get("tag") == "NOVEDAD":
                e["verdict"] = "new"
    sec["groups"] = [g for g in sec["groups"] if g["entries"] or g["bullets"]]
    return sec


def flat_runs(r):
    return clean("".join(x[0] for x in r))


def parse(page):
    """Datos de un parche a partir del JSON de `__NEXT_DATA__` de su página (campo props.pageProps.page). Siempre devuelve el modelo, con secciones vacías si no reconoce nada."""
    blades = page.get("blades") or []
    mast = next((b for b in blades if b.get("type") == "articleMasthead"), {}) or {}
    rich = next((b for b in blades if b.get("type") == "patchNotesRichText"), {}) or {}
    title = mast.get("title") or page.get("title") or ""
    m = re.search(r"(\d{2})\.(\d{1,2})", title) or re.search(r"(\d{2})\.(\d{1,2})", page.get("url") or "") or re.search(r"(\d{2})-(\d{1,2})", page.get("url") or "")
    v = f"{m.group(1)}.{int(m.group(2))}" if m else str(rich.get("fragmentId") or "")
    body = ((rich.get("richText") or {}).get("body")) or ""
    root = tree(body)
    out = {"schema": VERSION, "v": v, "title": clean(title), "date": mast.get("publishDate") or page.get("displayedPublishDate") or "",
           "summary": clean(re.sub(r"<[^>]+>", "", ((mast.get("description") or {}).get("body")) or page.get("description") or "")),
           "url": page.get("url") or "", "banner": ((mast.get("banner") or {}).get("url")) or ((page.get("metaImage") or {}).get("url")) or "",
           "authors": [a.get("name") for a in (mast.get("authors") or []) if a.get("name")], "intro": [], "designers": [], "sections": []}
    # introducción y diseñadores (antes de la primera sección)
    first_q = first(root, lambda n: n.tag == "blockquote" and "context" in n.cls)
    if first_q is not None:
        paras = re.split(r"\n\s*\n", text(first_q).replace("\r", ""))
        out["intro"] = [p for p in (clean(re.sub(r"\s*\n\s*", " ", x)) for x in paras) if p]
    out["designers"] = [flat(n) for n in find(root, lambda n: "context-designer" in n.cls)]
    # secciones: cada h2 abre una, y su contenido llega hasta el siguiente h2
    container = first(root, lambda n: n.attrs.get("id") == "patch-notes-container") or root
    seq = []   # lista plana de (h2 | nodo de contenido) en orden de documento

    def walk(n):
        if isinstance(n, str):
            return
        if n.tag == "h2":
            seq.append(("h2", n))
            return
        if n.tag in ("blockquote", "p", "ul", "h3", "h4", "hr", "img") and not ("context" in n.cls and n.tag == "blockquote" and not seq):
            seq.append(("n", n))
            if n.tag in ("blockquote", "p", "ul", "h3", "h4"):
                return
        for k in n.kids:
            walk(k)
    walk(container)
    cur = None
    for kind, n in seq:
        if kind == "h2":
            cur = [n, Node("div", [])]
            out["sections"].append(cur)
        elif cur is not None:
            cur[1].kids.append(n)
    parsed = []
    for h, body_node in out["sections"]:
        sec = parse_section(body_node, h.attrs.get("id", ""), flat(h))
        if not sec["title"]:   # «patch-top»: un h2 vacío que solo abre la introducción
            if not out["intro"]:
                out["intro"] = sec["intro"]
            continue
        parsed.append(sec)
    out["sections"] = parsed
    out["intro"] = [p for p in out["intro"] if not re.search(r"wiki de nuestra comunidad|notas de (la )?versi[oó]n que buscab|notas de la versi[oó]n de TFT", p, re.I)]
    return out


# ---------------------------------------------------------------- descarga y caché
def _get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf8", "replace")


def next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html or "", re.S)
    if not m:
        raise ValueError("la página no trae los datos esperados (Riot ha cambiado su web)")
    return json.loads(m.group(1))


def list_versions(html):
    """Versiones publicadas, de la más nueva a la más antigua, a partir de la página de notas de versión."""
    found = {}
    for a, b in re.findall(r"league-of-legends-patch-(\d{2})-(\d{1,2})-notes", html or ""):
        found[f"{a}.{int(b)}"] = True
    key = lambda v: tuple(int(x) for x in v.split("."))
    return sorted(found, key=key, reverse=True)


def _path(cache_dir, name):
    return os.path.join(cache_dir, "parche", name)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def versions(cache_dir, force=False):
    """Lista de versiones disponibles (con caché de unas horas). Sin red devuelve lo último guardado, o [] si no hay nada."""
    p = _path(cache_dir, "lista.json")
    saved = _read(p)
    if saved and not force and time.time() - saved.get("ts", 0) < TTL_LIST and saved.get("schema") == VERSION:
        return saved["versions"]
    try:
        vs = list_versions(_get(LIST_URL))
        if vs:
            _write(p, {"ts": time.time(), "schema": VERSION, "versions": vs})
            return vs
    except Exception:
        pass
    return (saved or {}).get("versions", [])


def load(cache_dir, v, latest=None, force=False):
    """Las notas de la versión `v` («26.22»): del disco si están frescas, si no de la web. Lanza una excepción si no hay forma de tenerlas."""
    p = _path(cache_dir, f"notas_{v}.json")
    saved = _read(p)
    ttl = TTL_CURRENT if v == latest else TTL_OLD
    closed_ok = v == latest or saved.get("final") if saved else False   # guardado siendo el último y ya no lo es: se relee una vez
    if saved and saved.get("schema") == VERSION and not force and closed_ok and time.time() - saved.get("fetched", 0) < ttl:
        return saved
    a, b = v.split(".")
    try:
        data = parse(next_data(_get(NOTE_URL.format(a=a, b=b)))["props"]["pageProps"]["page"])
        data["fetched"] = time.time()
        data["final"] = v != latest
        if not data["v"]:
            data["v"] = v
        _write(p, data)
        return data
    except Exception:
        if saved and saved.get("schema") == VERSION:
            return saved   # sin red: lo último que hubiera
        raise


def champion_slug(entry):
    """Clave del campeón de una ficha: la del enlace oficial (.../champions/aurelionsol/), o el nombre sin signos."""
    m = re.search(r"/champions/([a-z0-9]+)", (entry.get("href") or "").lower())
    return m.group(1) if m else _slug(entry.get("name"))


def changes(data):
    """Todas las fichas de campeón de las notas, con su sección: [{"slug", "name", "verdict", "section", "entry"}]; un campeón puede salir en varias secciones (Grieta, ARAM…)."""
    out = []
    for s in data.get("sections", []):
        for g in s["groups"]:
            for e in g["entries"]:
                if e["kind"] == "champion":
                    out.append({"slug": champion_slug(e), "name": e["name"], "verdict": e["verdict"], "section": s["kind"], "entry": e})
    return out


_EFFECT = {"mtime": None, "v": None, "by": {}}


def latest_effect(cache_dir, champs):
    """{id_campeón: {"v": versión, "verdict", "name", "text"}} con lo que las ÚLTIMAS notas guardadas en disco dicen de cada campeón (sin red). Sirve para avisar en la
    selección y en «Partida» de que el campeón elegido se ha tocado. Vacío si aún no se han descargado las notas."""
    try:
        lst = _read(_path(cache_dir, "lista.json")) or {}
        vs = lst.get("versions") or []
        if not vs:
            return {}
        p = _path(cache_dir, f"notas_{vs[0]}.json")
        mt = os.path.getmtime(p)
        if _EFFECT["mtime"] == mt and _EFFECT["v"] == vs[0]:
            return _EFFECT["by"]
        data = _read(p)
        if not data or data.get("schema") != VERSION:
            return {}
        import parche_stats
        idx = parche_stats.champion_index(champs)
        by = {}
        for ch in changes(data):
            if ch["section"] != "champions":
                continue
            cid = idx.get(_slug(ch["slug"])) or idx.get(_slug(ch["name"]))
            if not cid or cid in by:
                continue
            e = ch["entry"]
            first = next(((b["title"], ln) for b in e["blocks"] for ln in b["lines"] if ln.get("before")), None)
            text = ""
            if first:
                title, ln = first
                text = f"{title + ': ' if title else ''}{ln['label'] + ' ' if ln['label'] else ''}{ln['before']} → {ln['after']}"
            by[cid] = {"v": vs[0], "verdict": ch["verdict"], "name": ch["name"], "text": text[:140]}
        _EFFECT.update(mtime=mt, v=vs[0], by=by)
        return by
    except Exception:
        return {}
