"""El tour guiado de la demostración: lecciones cortas sobre la app real (con datos de ejemplo) y la tarjeta que las cuenta.

Las lecciones (`LESSONS`) son datos: cada paso dice a qué situación llevar la app (`scene`), a qué pantalla (`page`), qué elemento resaltar (`target`, un id de `TARGETS`) y el texto
(título de 3 a 5 palabras y una o dos frases). Las reglas de redacción vienen de la revisión de un experto: textos de unas 25 palabras, lenguaje de usuario, y «cuándo lo verás» y
«de dónde sale» plegados tras «Más». `RECORRIDO` es el orden del recorrido completo; `PREGUNTAS` enlaza las preguntas de la Ayuda (ayuda.TOPICS) con su lección.

`Tour` es la tarjeta: Anterior, Siguiente, Salir, «Saltar lección», progreso «Paso n de N» en texto y atajos de teclado (flechas e Intro, Esc). Un clic fuera de la tarjeta no la cierra ni
avanza; el elemento resaltado lleva un borde ámbar y la etiqueta «AQUÍ», para que el color no sea la única señal."""

# id de elemento -> cómo encontrarlo en la ventana (`ui` es gui.GUI)
TARGETS = {
    "nav.inicio": lambda ui: ui.tab_seg.btns["Asesor"],
    "nav.partida": lambda ui: ui.tab_seg.btns["Partida"],
    "nav.enfrentamiento": lambda ui: ui.tab_seg.btns["Enfrentamiento"],
    "nav.campeones": lambda ui: ui.tab_seg.btns["Repertorio"],
    "nav.historial": lambda ui: ui.tab_seg.btns["Historial"],
    "banda.vivo": lambda ui: ui.band,
    "boton.ayuda": lambda ui: ui.ayuda_btn,
    "boton.ajustes": lambda ui: ui.ajustes_btn,
    "cuerpo": lambda ui: ui.body,
    "pagina.datos": lambda ui: ui.data_view.box,
    "nav.todo": lambda ui: ui.tab_seg.frame,
}
# además de los de arriba, los elementos anotados con `kit.reg(id, widget)` en las pantallas: inicio.perfil, inicio.grafica, recs.hero, recs.pestanas, build.runas, build.hechizos,
# vivo.tira, vivo.objetivos, vivo.objeto, analisis.cabecera, analisis.tarjeta, hist.resumen, hist.anio
REGISTRADOS = ("inicio.perfil", "inicio.grafica", "recs.hero", "recs.pestanas", "build.runas", "build.hechizos", "vivo.tira", "vivo.objetivos", "vivo.objeto",
               "analisis.cabecera", "analisis.tarjeta", "hist.resumen", "hist.anio", "partida.jugadores", "partida.rival", "partida.objetivo", "inicio.sesion", "hist.patron")


def find(ui, tid):
    """El elemento de un id, o None si no está en pantalla ahora (entonces el paso se enseña sin resalte)."""
    try:
        w = TARGETS[tid](ui) if tid in TARGETS else ui.kit.tour_ids.get(tid)
        return w if w is not None and w.winfo_exists() and w.winfo_ismapped() else None
    except Exception:
        return None

SCENES = ("idle", "queue", "select", "locked", "aram", "arena", "game", "end")
ACTS = ("rival", "ajustes", "cerrar_ajustes", "abrir_jugadores", "abrir_anio")
PAGES = ("Asesor", "Partida", "Enfrentamiento", "Repertorio", "Historial", "Datos")


def step(title, text, scene=None, page=None, target=None, when=None, source=None, act=None, try_it=None):
    """`act`: una acción de la demostración antes de enseñar el paso (demo.act): «rival» elige un rival en Enfrentamiento, «ajustes» abre Ajustes y «cerrar_ajustes» lo cierra."""
    return {"title": title, "text": text, "scene": scene, "page": page, "target": target, "when": when, "source": source, "act": act, "try_it": try_it}


LESSONS = {
    "que_es": {"title": "Qué es LOL-E", "steps": [
        step("Bienvenido a LOL-E", "Es un asesor para League of Legends: lee tu cliente y te ayuda a elegir campeón, a jugar y a revisar tus partidas.", scene="idle", page="Asesor",
             when="Lo dejas abierto mientras juegas; se activa solo.", source="Tu cliente de LoL, más Lolalytics y op.gg para las estadísticas."),
        step("Esto es una demostración", "Todo lo que ves son datos inventados. La franja de arriba te lo recuerda y no se guarda nada.", target="cuerpo"),
        step("Solo lee, no toca nada", "LOL-E solo lee el cliente local y la API local de la partida. No inyecta nada ni automatiza el juego."),
    ]},
    "antes": {"title": "Antes de jugar", "steps": [
        step("Inicio: tu perfil y rango", "Aquí ves tu rango en cada cola y tus últimas cinco partidas.", scene="idle", page="Asesor", target="inicio.perfil",
             when="Siempre que no haya partida en marcha.", source="Tu cliente de LoL."),
        step("Tu rango en el tiempo", "La gráfica muestra tus PL partida a partida. Puedes cambiar el tramo y ver solo datos reales o también estimados.", target="inicio.grafica",
             try_it="pulsa «7 días» o «Todo» y mira cómo cambia el eje."),
        step("Al buscar partida", "Al entrar en cola, «Partida» pasa a «En vivo» y aparece esta banda con la fase. Desde aquí vas y vuelves a consultar.", scene="queue", target="banda.vivo"),
    ]},
    "seleccion": {"title": "Selección, runas y builds", "steps": [
        step("Te toca elegir", "En la selección, Inicio te recomienda campeones para tu línea con una afinidad de 0 a 100 y filtros.", scene="select", page="Asesor", target="recs.hero",
             when="Solo durante la selección de campeón.", source="Lolalytics, op.gg y tu historial."),
        step("Mira cada campeón", "Resumen, Contra rival, Sinergias y Meta y build: cada pestaña te cuenta algo distinto del campeón elegido.", target="recs.pestanas",
             try_it="pulsa «Contra rival» y luego «Sinergias»."),
        step("Tus runas recomendadas", "Con tu campeón elegido, «En vivo» muestra sus runas: la más usada o la de mayor % de victorias, con su uso.", scene="locked", page="Partida",
             target="build.runas", when="Desde que eliges campeón y durante toda la partida.", source="Lolalytics y op.gg, con tu rango y tu línea."),
        step("Hechizos, habilidades y objetos", "Debajo siguen hechizos, orden de habilidades y objetos, con pestañas Variantes y Situaciones.", target="build.hechizos"),
    ]},
    "partida": {"title": "En partida", "steps": [
        step("La banda y su reloj", "Mientras juegas, la banda muestra la fase y el tiempo. «Consultar» te deja revisar otras pantallas y volver.", scene="game", page="Partida", target="banda.vivo"),
        step("Marcador y objetivos", "Bajas, oro en objetos y objetivos. Dragón, larvas y Barón llevan avisos estimados antes de salir.", target="vivo.objetivos",
             when="Cada ~10 segundos durante la partida.", source="La API local del propio juego (la de la tabla de puntuación)."),
        step("Tu siguiente objeto", "Te dice cuánto oro te falta para el siguiente objeto de tu build y qué objeto conviene contra tus rivales.", target="vivo.objeto"),
    ]},
    "terminar": {"title": "Al terminar y revisar", "steps": [
        step("El análisis", "Al acabar, «En vivo» muestra el resultado, tus PL, y cómo fuiste frente a tu rival y a tu media.", scene="end", page="Partida", target="analisis.cabecera",
             when="Tras cada partida, unos segundos después de acabar.", source="El detalle de la partida que da tu cliente."),
        step("Guarda la tarjeta", "Puedes guardar una tarjeta de la partida como imagen para compartirla.", target="analisis.tarjeta"),
        step("Tu historial", "Todas tus partidas guardadas, con filtros y un resumen con tu sesión, tu patrón de derrotas y dónde mueres.", scene="idle", page="Historial", target="hist.resumen"),
        step("Tu año en LoL", "Un resumen de tu temporada, con lo útil para mejorar y curiosidades, que puedes guardar como imagen.", target="hist.anio"),
    ]},
    "fuentes": {"title": "De dónde sale y cuánto fiarme", "steps": [
        step("La página Datos", "Explica de dónde sale cada dato y cómo se calcula la afinidad. Se abre desde Ajustes.", page="Datos", target="pagina.datos"),
        step("Las fuentes", "Builds y porcentajes: Lolalytics y op.gg. Tu historial y rango: tu cliente. El marcador en vivo: la API local del juego.", target="pagina.datos"),
        step("Cuánto fiarte", "Los datos con pocas partidas se marcan, y los avisos de objetivos son estimaciones, no el reloj real del juego.", target="pagina.datos"),
    ]},
}

LESSONS.update({
    "sin_datos": {"title": "No veo datos", "steps": [
        step("Conecta con League of Legends", "Abre LoL e inicia sesión: arriba debe poner «Conectado a LoL». LOL-E se conecta solo en unos segundos.", scene="idle", page="Asesor", target="cuerpo",
             when="Siempre que abras LOL-E.", source="El cliente local de LoL, que LOL-E busca en tu PC."),
        step("Si ya está abierto", "Si no conecta, reinicia LOL-E. Sin partidas guardadas, el Historial y las estadísticas están vacíos hasta que juegues.", page="Historial", target="nav.historial"),
        step("El informe de diagnóstico", "En Ajustes, «Copiar informe de diagnóstico» recoge lo que falla, sin datos personales, para que puedas compartirlo.", target="boton.ajustes"),
    ]},
    "enfrentamiento": {"title": "Comparar un enfrentamiento", "steps": [
        step("Elige a tu rival", "Escribe su nombre o toca uno reciente; en la selección se rellena solo con tu rival de línea.", scene="idle", page="Enfrentamiento", target="cuerpo",
             when="Cuando quieras preparar un cruce, en o fuera de partida.", source="Lolalytics (todos los jugadores) y tu historial."),
        step("Qué campeón le gana", "Con un rival elegido, ves qué campeones le ganan más, con tu porcentaje si ya jugaste ese cruce.", act="rival", target="cuerpo",
             try_it="prueba el filtro «Los que tengo» o cambia el orden."),
    ]},
    "aprender": {"title": "Qué campeón aprender", "steps": [
        step("Tu repertorio", "Con qué campeones juegas y cómo te va con cada uno, en la Grieta o en todos los modos.", scene="idle", page="Repertorio", target="cuerpo",
             when="Cuando quieras revisar tus campeones.", source="Tu historial guardado."),
        step("Qué aprender", "Si en una línea dependes mucho de un solo campeón, te propone hasta tres alternativas con buena tasa en el parche.", target="cuerpo", source="Lolalytics."),
    ]},
    "personalizar": {"title": "Personalizar la app", "steps": [
        step("Ajustes y datos", "Aquí cambias el tema, el color, el tamaño, la barra lateral, los avisos sonoros y los datos en vivo.", scene="idle", page="Asesor", act="ajustes", target="boton.ajustes"),
        step("Datos", "Arriba de Ajustes está el acceso a la página Datos, que explica de dónde sale todo.", target="boton.ajustes"),
        step("Cerrar Ajustes", "Los cambios se aplican al instante y se guardan solos.", act="cerrar_ajustes", target="boton.ajustes"),
    ]},
})

LESSONS.update({
    "primera_partida": {"title": "Tu primera partida", "steps": [
        step("Tus datos aparecen solos", "El rango y tus estadísticas salen del cliente al conectar. Lo que LOL-E guarda por su cuenta empieza cuando juegas con la app abierta.", scene="idle", page="Asesor",
             target="inicio.perfil", when="Desde el primer arranque.", source="Tu cliente de LoL."),
        step("El historial crece contigo", "El cliente solo entrega las partidas más recientes: LOL-E guarda cada una que ve y así el historial va creciendo.", page="Historial", target="nav.historial"),
        step("El análisis llega solo", "Al terminar cada partida, unos segundos después, aparece su análisis en «En vivo».", scene="end", page="Partida", target="analisis.cabecera"),
        step("Con unas diez partidas", "Ya hay resumen, patrones y tu año en LoL. Con menos, la app lo dice en vez de inventar.", scene="idle", page="Historial", target="hist.resumen"),
    ]},
    "afinidad": {"title": "Cómo leer la afinidad", "steps": [
        step("Qué es la afinidad", "Un número de 0 a 100: cuánto encaja un campeón contigo ahora mismo. No es una probabilidad de ganar.", scene="select", page="Asesor", target="recs.hero"),
        step("Qué cuenta", "Suma varios factores, cada uno con su peso: tu historial con el campeón, el parche, tu equipo y tu rival. Los pesos se ven en Datos.", target="recs.hero",
             source="Tu historial, Lolalytics y lo que ya han elegido en la selección."),
        step("Qué hacer con ella", "Úsala para ordenar, no para obedecer: con los filtros y las pestañas ves el porqué de cada recomendación.", target="recs.pestanas",
             try_it="pulsa las flechas del carrusel y compara la afinidad de cada campeón."),
    ]},
    "jugadores": {"title": "Los 10 jugadores", "steps": [
        step("Quién juega", "Rango, rachas y lo que más juega cada uno, de tu equipo y del rival. Es plegable para centrarte en la build.", scene="game", page="Partida",
             act="abrir_jugadores", target="partida.jugadores", when="Desde la pantalla de carga y durante la partida.", source="El cliente de LoL, igual que en la selección."),
        step("Tu rival de línea", "Confírmalo o elígelo aquí: la build y los porcentajes se ajustan contra él.", target="partida.rival"),
    ]},
    "patron": {"title": "Tu sesión y tu patrón", "steps": [
        step("El aviso de sesión", "Si llevas dos derrotas seguidas, te lo dice con tu propio dato antes de entrar en otra cola.", scene="idle", page="Asesor", target="inicio.sesion"),
        step("Tu patrón de derrotas", "Con tus partidas analizadas, detecta qué se repite al perder: muertes tempranas, farmeo u oro por detrás.", page="Historial", target="hist.patron"),
        step("Tu objetivo de la partida", "De ese patrón sale un objetivo medible para cada partida; al acabar, el análisis dice si lo cumpliste.", scene="game", page="Partida", target="partida.objetivo"),
    ]},
    "otros_modos": {"title": "ARAM, Arena y otros modos", "steps": [
        step("ARAM: sin líneas", "En ARAM no hay línea ni rival directo: LOL-E muestra tu campeón, su build y el banquillo.", scene="aram", page="Asesor", target="cuerpo"),
        step("Arena y otros modos", "Fuera de la Grieta no hay plan de línea ni build recomendada, pero el análisis al terminar sí sale.", scene="arena", target="cuerpo"),
    ]},
    "compartir": {"title": "Compartir tus partidas", "steps": [
        step("La tarjeta de una partida", "En el análisis, «Guardar tarjeta de la partida» crea una imagen con tu campeón, el resultado y tus cifras.", scene="end", page="Partida", target="analisis.tarjeta"),
        step("Tu año en LoL", "En el Historial, un resumen de tu temporada que también puedes guardar como imagen para compartir.", scene="idle", page="Historial", act="abrir_anio", target="hist.anio"),
    ]},
    "atajos": {"title": "Atajos y accesibilidad", "steps": [
        step("La barra lateral", "Ctrl+1 a Ctrl+7 o las flechas cambian de pantalla. Con la ventana ancha ves los nombres; con la estrecha, solo iconos.", scene="idle", page="Asesor", target="nav.todo"),
        step("Ayuda con F1", "F1 o el botón ? abren la ayuda de la pantalla y las preguntas frecuentes.", target="boton.ayuda"),
        step("Tamaño y colores", "En Ajustes: tamaño de la interfaz de 90 a 130 %, tema claro u oscuro y paletas revisadas por contraste.", act="ajustes", target="boton.ajustes"),
        step("Listo", "Los cambios se aplican al instante y se guardan solos.", act="cerrar_ajustes", target="boton.ajustes"),
    ]},
})

RECORRIDO = ["que_es", "antes", "seleccion", "partida", "terminar", "fuentes"]
OTRAS = ["primera_partida", "sin_datos", "afinidad", "jugadores", "patron", "otros_modos", "compartir", "enfrentamiento", "aprender", "personalizar", "atajos"]   # sueltas, fuera del recorrido

# pregunta de la Ayuda -> lección que la enseña (las que no tienen lección propia aún no aparecen)
PREGUNTAS = {"primera": "primera_partida", "afinidad": "afinidad", "jugadores": "jugadores", "patron": "patron", "modos": "otros_modos", "compartir": "compartir",
             "atajos": "atajos", "sin_datos": "sin_datos", "enfrentamiento": "enfrentamiento", "aprender": "aprender", "personalizar": "personalizar", "que_es": "que_es", "seguro": "que_es", "antes": "antes", "cola": "antes", "elegir": "seleccion", "runas_builds": "seleccion", "en_partida": "partida",
             "terminar": "terminar", "historial": "terminar", "fuentes": "fuentes"}


def total_steps(ids):
    return sum(len(LESSONS[i]["steps"]) for i in ids)


def words(text):
    return len(text.split())


class Tour:
    """La tarjeta de narración sobre la ventana de la demostración. `demo` es demo_mode.Demo."""

    def __init__(self, demo):
        import tkinter as tk
        self.demo, self.ui, self.tk = demo, demo.ui, tk
        self.ids, self.li, self.si = [], 0, 0
        self.card = None
        self.marks = []
        self.more = False

    # ---- ciclo de vida ----
    def start(self, ids):
        self.ids, self.li, self.si, self.more = list(ids), 0, 0, False
        root = self.ui.root
        root.bind("<Right>", self.on_next)
        root.bind("<Return>", self.on_next)
        root.bind("<Left>", self.on_prev)
        root.bind("<Escape>", self.on_exit)
        self.enter()

    def active(self):
        return bool(self.ids)

    def exit(self):
        self.ids = []
        self.clear_marks()
        if self.card is not None:
            self.card.destroy()
            self.card = None
        root = self.ui.root
        for k in ("<Right>", "<Return>", "<Left>", "<Escape>"):
            root.unbind(k)
        root.bind("<Left>", lambda e: self.ui.key_go(-1))
        root.bind("<Right>", lambda e: self.ui.key_go(1))
        root.bind("<Escape>", lambda e: self.ui.close_dock())

    on_next = lambda self, e=None: (self.next(), "break")[1]
    on_prev = lambda self, e=None: (self.prev(), "break")[1]
    on_exit = lambda self, e=None: (self.exit(), "break")[1]

    # ---- el menú de bienvenida ----
    def menu(self):
        """La tarjeta del principio: recorrido completo, una lección suelta o explorar por tu cuenta."""
        import customtkinter as ctk
        from ui_kit import PAL
        ui, k = self.ui, self.ui.kit
        if self.card is not None:
            self.card.destroy()
        w = max(360, min(620, ui.root.winfo_width() - 60))
        self.card = card = ctk.CTkFrame(ui.root, fg_color=PAL["card"], corner_radius=16, border_width=2, border_color=PAL["warn"], width=w)
        inner = k.frame(card)
        inner.pack(fill="x", padx=20, pady=16)
        k.clbl(inner, "BIENVENIDO A LA DEMOSTRACIÓN", 9, "dim", True).pack(anchor="w")
        k.clbl(inner, "¿Cómo quieres verla?", 20, "fg", True, True).pack(anchor="w", pady=(2, 4))
        k.clbl(inner, "Es la app real con datos inventados: puedes tocar todo sin miedo. Elige un recorrido o una lección corta.", 11, "dim", wraplength=w - 56, justify="left").pack(anchor="w")
        full = ctk.CTkButton(inner, text=f"Recorrido completo  ·  {total_steps(RECORRIDO)} pasos, unos {max(1, round(total_steps(RECORRIDO) * 12 / 60))} minutos", height=38, corner_radius=10,
                             font=k.font(13, True), fg_color=k.acc, text_color=PAL["bg"], hover_color=k.acc, command=lambda: self.start(RECORRIDO))
        full.pack(fill="x", pady=(12, 6))
        k.clbl(inner, "O UNA LECCIÓN", 9, "dim", True).pack(anchor="w", pady=(6, 2))
        grid = k.frame(inner)
        grid.pack(fill="x")
        for c in (0, 1):
            grid.columnconfigure(c, weight=1, uniform="les")
        for n, lid in enumerate(RECORRIDO + OTRAS):
            ctk.CTkButton(grid, text=f"{LESSONS[lid]['title']}", height=30, corner_radius=9, font=k.font(11), anchor="w",
                          fg_color=PAL["card2"], text_color=PAL["fg"], hover_color=PAL["border"], command=lambda l=lid: self.start([l])).grid(row=n // 2, column=n % 2, sticky="ew", padx=2, pady=2)
        ctk.CTkButton(inner, text="Explorar por mi cuenta", height=32, corner_radius=9, font=k.font(12), fg_color="transparent", border_width=1, border_color=PAL["edge"],
                      text_color=PAL["dim"], hover_color=PAL["card2"], command=self.exit).pack(fill="x", pady=(10, 0))
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.lift()

    # ---- navegación ----
    def cur(self):
        return LESSONS[self.ids[self.li]]["steps"][self.si]

    def next(self):
        if not self.active():
            return
        if self.si + 1 < len(LESSONS[self.ids[self.li]]["steps"]):
            self.si += 1
        elif self.li + 1 < len(self.ids):
            self.li, self.si = self.li + 1, 0
        else:
            return self.exit()
        self.enter()

    def prev(self):
        if not self.active():
            return
        if self.si > 0:
            self.si -= 1
        elif self.li > 0:
            self.li -= 1
            self.si = len(LESSONS[self.ids[self.li]]["steps"]) - 1
        else:
            return
        self.enter()

    def skip_lesson(self):
        if self.li + 1 < len(self.ids):
            self.li, self.si = self.li + 1, 0
            self.enter()
        else:
            self.exit()

    # ---- pintar el paso ----
    def enter(self):
        s = self.cur()
        self.more = False
        if s["scene"]:
            self.demo.scene(s["scene"])
        if s["page"]:
            self.demo.go(s["page"])
        if s.get("act"):
            self.demo.act(s["act"])
        self.ui.root.after(900, self.paint)   # la pantalla tarda un instante en pintarse: el resalte y la tarjeta van después

    def paint(self, tries=0):
        """Pinta la tarjeta y resalta el elemento. Si aún no está en pantalla (las builds y runas tardan en llegar) se reintenta unas veces; si queda fuera de la vista, se desplaza hasta él."""
        if not self.active():
            return
        step_now = (self.li, self.si)
        target = self.cur()["target"]
        w = find(self.ui, target) if target else None
        if target and w is None and tries < 5:
            self.ui.root.after(500, lambda: self.paint(tries + 1) if (self.active() and (self.li, self.si) == step_now) else None)
            if tries == 0:
                self.clear_marks()
                self.build_card()
            return
        if w is not None and self.reveal(w) and tries < 5:
            self.ui.root.after(350, lambda: self.paint(tries + 1) if (self.active() and (self.li, self.si) == step_now) else None)
            return
        self.clear_marks()
        self.build_card()
        self.highlight(target)

    def reveal(self, w):
        """Si el elemento queda fuera de la vista, desplaza la pantalla hasta dejarlo a un cuarto de la altura; devuelve True si desplazó."""
        ui = self.ui
        try:
            top, h = ui.root.winfo_rooty(), ui.root.winfo_height()
            y = w.winfo_rooty() - top
            if 150 < y < h * 0.62:
                return False
            canvas = ui.body._parent_canvas
            total = max(1, ui.body.winfo_height())
            inner_y = w.winfo_rooty() - ui.body.winfo_rooty()
            canvas.yview_moveto(max(0.0, min(1.0, (inner_y - 140) / total)))
            return True
        except Exception:
            return False

    def clear_marks(self):
        for w in self.marks:
            try:
                w.destroy()
            except Exception:
                pass
        self.marks = []

    def highlight(self, target):
        """Borde ámbar de 3 px alrededor del elemento y una etiqueta «AQUÍ»; el resalte no captura clics (son marcos finos, no una capa)."""
        if not target:
            return
        tk, ui = self.tk, self.ui
        try:
            w = find(ui, target)
            if w is None:
                return
            ui.root.update_idletasks()
            x, y = w.winfo_rootx() - ui.root.winfo_rootx(), w.winfo_rooty() - ui.root.winfo_rooty()
            ww, hh = w.winfo_width(), w.winfo_height()
        except Exception:
            return
        if ww < 8 or hh < 8:
            return
        color = "#ff9f43"
        t = 3
        for gx, gy, gw, gh in ((x - t, y - t, ww + 2 * t, t), (x - t, y + hh, ww + 2 * t, t), (x - t, y, t, hh), (x + ww, y, t, hh)):
            f = tk.Frame(ui.root, bg=color)
            f.place(x=gx, y=gy, width=gw, height=gh)
            f.lift()
            self.marks.append(f)
        tag = tk.Label(ui.root, text=" AQUÍ ", bg=color, fg="#111111", font=("Segoe UI", 9, "bold"))
        tag.place(x=max(0, x), y=max(0, y - 22))
        tag.lift()
        self.marks.append(tag)
        if self.card is not None:
            self.card.lift()

    def build_card(self):
        import customtkinter as ctk
        from ui_kit import PAL
        ui, k = self.ui, self.ui.kit
        if self.card is not None:
            self.card.destroy()
        lesson = LESSONS[self.ids[self.li]]
        s = self.cur()
        root_w = ui.root.winfo_width()
        w = max(360, min(760, root_w - 40))
        self.card = card = ctk.CTkFrame(ui.root, fg_color=PAL["card"], corner_radius=14, border_width=2, border_color=PAL["warn"], width=w)
        inner = k.frame(card)
        inner.pack(fill="x", padx=16, pady=(12, 12))
        head = k.frame(inner)
        head.pack(fill="x")
        n = len(lesson["steps"])
        k.clbl(head, f"{lesson['title'].upper()}  ·  PASO {self.si + 1} DE {n}" + (f"  ·  LECCIÓN {self.li + 1} DE {len(self.ids)}" if len(self.ids) > 1 else ""), 9, "dim", True).pack(side="left")
        k.clbl(inner, s["title"], 17, "fg", True, True).pack(anchor="w", pady=(4, 0))
        k.clbl(inner, s["text"], 12, "fg", wraplength=w - 48, justify="left").pack(anchor="w", pady=(2, 0))
        if s.get("try_it"):   # opcional: nada espera a que lo hagas, «Siguiente» siempre vale
            k.clbl(inner, "PRUÉBALO TÚ: " + s["try_it"], 11, "info", True, wraplength=w - 48, justify="left").pack(anchor="w", pady=(6, 0))
        if s.get("when") or s.get("source"):
            more = k.frame(inner)
            btn = k.clbl(inner, "▸ Más: cuándo lo verás y de dónde sale", 10, "info", True)
            btn.pack(anchor="w", pady=(6, 0))
            btn.configure(cursor="hand2")

            def flip(_e=None):
                self.more = not self.more
                if self.more:
                    btn.configure(text="▾ Más: cuándo lo verás y de dónde sale")
                    more.pack(anchor="w", pady=(4, 0))
                else:
                    btn.configure(text="▸ Más: cuándo lo verás y de dónde sale")
                    more.pack_forget()
            btn.bind("<Button-1>", flip)
            for title, text in (("Cuándo lo verás", s.get("when")), ("De dónde sale", s.get("source"))):
                if text:
                    k.clbl(more, f"{title.upper()}: ", 9, "info", True).pack(anchor="w")
                    k.clbl(more, text, 11, "fg", wraplength=w - 48, justify="left").pack(anchor="w")
        row = k.frame(inner)
        row.pack(fill="x", pady=(10, 0))
        mk = lambda text, cmd, primary=False: ctk.CTkButton(row, text=text, width=104, height=32, corner_radius=9, font=k.font(12, True),
                                                           fg_color=k.acc if primary else PAL["card2"], text_color=PAL["bg"] if primary else PAL["fg"],
                                                           hover_color=k.acc if primary else PAL["border"], command=cmd)
        last = self.li == len(self.ids) - 1 and self.si == n - 1
        mk("Salir", self.exit).pack(side="left")
        if len(self.ids) > 1 and self.li < len(self.ids) - 1:
            mk("Saltar lección", self.skip_lesson).pack(side="left", padx=(8, 0))
        nxt = mk("Terminar" if last else "Siguiente ›", self.next, True)
        nxt.pack(side="right")
        if self.li > 0 or self.si > 0:
            mk("‹ Anterior", self.prev).pack(side="right", padx=(0, 8))
        k.clbl(row, "← →  Intro  Esc", 9, "dim").pack(side="right", padx=12)
        # abajo, salvo que lo resaltado esté abajo: entonces arriba (la tarjeta no tapa lo que explica)
        top = False
        try:
            wid = find(ui, s["target"]) if s["target"] else None
            if wid is not None:
                top = (wid.winfo_rooty() - ui.root.winfo_rooty()) > ui.root.winfo_height() * 0.45
        except Exception:
            pass
        if top:
            card.place(relx=0.5, y=118, anchor="n")
        else:
            card.place(relx=0.5, rely=1.0, y=-38, anchor="s")
        card.lift()
        card.focus_set()
