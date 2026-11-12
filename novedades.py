"""Novedades de la aplicación, estilo nota de parche. Se muestran una vez al abrir una versión nueva y se pueden volver a consultar
desde Ajustes. Para añadir una versión: pon una entrada nueva ARRIBA de NOTES (las más recientes primero).

Cada punto es (tipo, texto). Tipos: "nuevo", "mejora", "arreglo".
"""
import customtkinter as ctk

from ui_kit import PAL

TIPOS = {"nuevo": ("NUEVO", "good"), "mejora": ("MEJORA", "info"), "arreglo": ("ARREGLO", "warn")}

NOTES = [
    {"v": "1.22.1", "fecha": "12 de noviembre de 2026", "titulo": "El análisis ya no te confunde con otro jugador", "items": [
        ("arreglo", "En «Partida > Análisis» podía salir el campeón de otro jugador (por ejemplo, Sona en una partida que jugaste con Lillia). Pasaba cuando LOL-E se abría antes de que el cliente terminara de iniciar sesión: no sabía qué cuenta eras y tomaba al primer jugador de la partida. Ahora tu jugador se busca siempre por tu cuenta; si no se puede saber, la partida no se analiza en vez de adivinar. Los análisis guardados con el jugador equivocado se corrigen solos al abrirlos."),
        ("arreglo", "Una partida que el cliente entregaba incompleta podía impedir que se guardaran todas las demás en el historial. Ahora se salta solo esa, y si el cliente no entrega las partidas se reintenta y el fallo queda en el registro de errores."),
        ("mejora", "La actualización automática solo acepta direcciones de GitHub por HTTPS, además de comprobar la huella del instalador como hasta ahora."),
        ("mejora", "La cola 1740 (Arena) se agrupa con Arena en el historial en vez de salir como «Otros»."),
    ]},
    {"v": "1.22.0", "fecha": "12 de noviembre de 2026", "titulo": "Temas y looks, Datos aparte y tu tarjeta en la carga", "items": [
        ("nuevo", "Temas de color y estilos: en Ajustes > Apariencia eliges una paleta (Predeterminado, Abisal, Neón medianoche, Brasa, Bosque, Cloud Dancer; cada una con modo oscuro y claro) y un estilo de tarjetas (Plano, Brutal con bordes gruesos y sombra dura, o Cristal con bordes luminosos). Son independientes: cualquier paleta vale con cualquier estilo, y el estilo cambia esquinas, bordes y sombras en toda la app."),
        ("nuevo", "Siete looks con personalidad propia, que no son solo colores: Terminal (todo en monoespaciada, verde fosforito), Papel (serif, crema y titulares subrayados), Blueprint (azul de plano, doble línea y rotulación técnica), Hextech (oro y azul profundo con doble marco), Arcade (neón sobre morado, bordes gruesos y sombra de color), Neón Tokio (doble borde luminoso rosa y cian) y Océano (esquinas muy redondas y verdes azulados). Cada uno trae su tipografía, su forma y su manera de titular las tarjetas."),
        ("mejora", "Todos los temas pasan una auditoría de contraste (texto, acentos y colores de victoria, derrota, aliado y rival), y la victoria y la derrota se distinguen también por forma (cuadrado entero o bajo) además del color. Los colores de rango son legibles en modo claro."),
        ("mejora", "«Datos» sale de las pestañas y pasa a un botón junto a Ajustes: son fuentes, cálculo y glosario, no un uso diario."),
        ("mejora", "«Jugadores de la partida» muestra también tu tarjeta (tus 10 últimas, rango, etiquetas y la ventana al pasar el ratón) y carga los 10 perfiles de una vez: ya no se redibuja por cada jugador que llega, solo avanza un contador."),
    ]},
    {"v": "1.21.0", "fecha": "11 de noviembre de 2026", "titulo": "Claves del campeón", "items": [
        ("nuevo", "«Claves del campeón» sobre la build, en la selección y en Partida > Plan: lo que cambia cómo se compra o se juega y no sale en las estadísticas. Por ejemplo, qué evoluciona cada habilidad de Kai'Sa (100 de AD, 100 de AP, 100 % de velocidad de ataque), los puntos de evolución de Kha'Zix, las cargas permanentes de Nasus o Veigar, las formas de Jayce o Kayn, o que Cassiopeia sí puede comprar botas. Son 250 claves de 95 campeones, verificadas en dos pasadas con notas de parche de Riot, Data Dragon y Lolalytics."),
        ("mejora", "Cada bloque indica el parche en el que se verificó y avisa cuando el parche actual es otro: los datos pueden haber cambiado y conviene comprobarlos. Se puede plegar y recuerda si lo dejaste abierto."),
        ("mejora", "«Jugadores de la partida» (pantalla de carga) se puede plegar para centrarte en la build, ya no sale en ARAM, Arena ni personalizadas, y la ventana al pasar el ratón enseña más: cómo le va con su campeón, su maestría, su línea habitual y los súbditos por minuto, el daño y la duración de cada partida."),
    ]},
    {"v": "1.20.0", "fecha": "11 de noviembre de 2026", "titulo": "Los 10 jugadores en la pantalla de carga y actualizaciones solas", "items": [
        ("nuevo", "Pantalla de carga: en Partida > Plan ves a los 10 jugadores a la vez, cada línea frente a su rival. Cada tarjeta lleva su campeón, su rango, sus últimas partidas en puntos verdes y rojos y etiquetas con lo destacado: mucha maestría con el campeón, primera vez con él, racha, especialista, fuera de su línea, posible cuenta secundaria, dúo contigo…"),
        ("nuevo", "Comparativa de equipos: rango medio, victorias recientes, maestría media con el campeón que llevan, daño físico y mágico, tanques y control; el lado mejor se marca en verde."),
        ("nuevo", "Pasa el ratón por una tarjeta para ver sus últimas 10 partidas (victoria o derrota, muertes/asistencias, KDA, cola y cuándo), su media, lo que más juega y avisos. Un clic abre su perfil completo bajo la línea."),
        ("mejora", "Con la línea de cada rival ya conocida, el plan deja de adivinar contra quién juegas: tu rival directo sale marcado y la build, las runas y la guía se rehacen contra él (salvo que lo hayas elegido tú a mano)."),
        ("nuevo", "Actualizaciones automáticas: LOL-E busca versiones nuevas al abrirse y cada pocas horas, y las instala solo (descarga, comprueba la huella y se reinicia), sin que nadie tenga que pulsar nada. Nunca lo hace durante la cola, la selección ni la partida: espera a que acabe. Se puede desactivar en Ajustes > Actualizaciones."),
        ("arreglo", "El récord de un rango ajeno («106V 0D, 100 %») ya no se muestra cuando el cliente no da las derrotas de otros jugadores."),
    ]},
    {"v": "1.19.0", "fecha": "10 de noviembre de 2026", "titulo": "Elige tu rival de línea", "items": [
        ("nuevo", "«Rival de línea»: cuando no sabes contra quién vas (por ejemplo en top, donde los rivales no traen línea) puedes elegir uno de los campeones rivales ya visibles. La build, las runas, el duelo y la guía se rehacen contra él, y cada ficha muestra el % de victorias de tu campeón contra ese rival en tu línea. «Auto» vuelve a la detección."),
        ("nuevo", "Lo mismo en Partida > Plan, para corregirlo cuando ya veas contra quién juegas (pantalla de carga o partida en curso)."),
        ("mejora", "El rival elegido solo vale para esa selección: al empezar otra, vuelve a Auto."),
    ]},
    {"v": "1.18.1", "fecha": "10 de noviembre de 2026", "titulo": "El conjunto de objetos llega a la partida", "items": [
        ("arreglo", "«Enviar al cliente» guardaba el conjunto en tu cuenta, pero el juego solo lo lee al empezar la partida y el cliente lo copiaba a su carpeta con retraso (hasta después de que la partida arrancara), así que no aparecía en la tienda. Ahora LOL-E también escribe el archivo en la carpeta del campeón (Config/Champions/<campeón>/Recommended) y comprueba que el cliente lo ha copiado."),
        ("mejora", "El botón explica qué ha pasado: si ya está en la carpeta del juego, o si no se ha podido copiar. Recuerda enviarlo durante la selección de campeón (o activar «Enviar siempre al elegir campeón»); con la partida ya cargada, el conjunto aparece en la siguiente."),
    ]},
    {"v": "1.18.0", "fecha": "10 de noviembre de 2026", "titulo": "Guía de juego, build al cliente y sonidos por fase", "items": [
        ("nuevo", "Nueva «Guía de juego» con tu campeón elegido, en la selección de campeón y en Partida > Plan: sus habilidades con enfriamientos, costes y alcances, su pasiva, los consejos que Riot escribe para jugar con él y sus picos de poder (niveles de la definitiva, habilidad principal y coste de los primeros objetos)."),
        ("nuevo", "«Tu duelo contra X»: compara a los dos campeones y te dice quién tiene alcance y velocidad, quién llega mejor al nivel 1, quién escala mejor, cuánto tarda en volver cada habilidad del rival (tu hueco para entrar), el maná que aguanta cada uno y su tipo de daño, más los consejos de Riot contra ese campeón y sus habilidades."),
        ("nuevo", "Botón «Enviar al cliente» en la build: crea en tu cliente de League un conjunto de objetos propio («LOL-E · campeón · línea») con inicio, botas, objetos principales, opciones de 4.º, 5.º y 6.º, una variante de más victorias y objetos para cada situación (los que encajan con el equipo rival, marcados con ★), para verlo en la tienda durante la partida. Solo toca los conjuntos de LOL-E, nunca los tuyos. También hay un interruptor para enviarlo solo al elegir campeón (desactivado por defecto)."),
        ("mejora", "Repaso estético centrado en el contraste: capas de color más separadas (fondo, tarjeta, panel interior), tarjetas con «sombra» y reflejo en el borde, barra de acento en los títulos, campos de texto y selectores hundidos, botones con borde, textos secundarios más claros, franja de estado (verde al elegir, rojo al banear) en la tarjeta de turno, cabecera de día más marcada en el historial y barras de desplazamiento discretas. También en el tema claro."),
        ("nuevo", "Sonido propio para cada fase: partida encontrada, tu turno de baneo, tu turno de elegir, campeón confirmado y empieza la partida. En Ajustes > Sonido de cada fase eliges uno de los sonidos de la app, «Sin sonido» o «Mi archivo…» con un .wav tuyo (se ajusta al volumen general), y un botón para probarlo. Por defecto suenan la partida encontrada (campana) y el campeón confirmado (arpegio); el baneo y el turno de elegir siguen con tu sonido de siempre."),
        ("arreglo", "Las botas contaban como un objeto más: la web (Lolalytics) las incluye entre los principales y la app recomendaba un «4.º objeto» cuando solo llevabas dos objetos completos. Ahora los huecos se numeran contando solo objetos completos (3.º, 4.º, 5.º cuando las botas van entre los principales), también en el conjunto que se envía al cliente y en la guía de juego."),
        ("mejora", "Todo sale de datos oficiales de Riot y de comparar a ambos campeones; no es una guía escrita a mano de cada pareja, y la app lo indica."),
    ]},
    {"v": "1.17.1", "fecha": "9 de noviembre de 2026", "titulo": "Botas que faltaban en algunas builds", "items": [
        ("arreglo", "En algunos campeones (sobre todo de jungla, como Lee Sin) la build recomendada no mostraba botas porque Lolalytics no las incluye entre sus objetos. Ahora se muestran las más usadas de op.gg, indicando de dónde salen."),
    ]},
    {"v": "1.17.0", "fecha": "8 de noviembre de 2026", "titulo": "Análisis de ARAM con los 10 jugadores", "items": [
        ("nuevo", "El análisis de ARAM y Mayhem ya no te compara con un «rival de línea»: tu campeón sale en grande y se ven los 10 jugadores."),
        ("nuevo", "Premios de la partida: más daño, más aguante, mejor KDA, más curación, más control y más asesinatos."),
        ("nuevo", "Clasificación de los 10 con filtros: ordena por daño, KDA, asesinatos, muertes, asistencias, daño recibido, mitigado, curación, control u oro, y mira los 10, tu equipo o el rival. Tu fila va resaltada y más grande."),
        ("mejora", "En ARAM se quitan la comparación 1 contra 1 y los gráficos de línea; queda la ventaja de oro de los equipos."),
    ]},
    {"v": "1.16.2", "fecha": "8 de noviembre de 2026", "titulo": "Análisis de ARAM pensado para ARAM", "items": [
        ("arreglo", "El análisis de una partida de ARAM / Mayhem ya no habla de muertes tempranas en línea, farmeo ni objetivos de rankeds."),
        ("nuevo", "«Lo más interesante de la partida»: tu puesto en daño, cuánto aguantaste, mejor KDA, rachas y multikills (pentakill, cuádruple, triple), curación, tiempo de control, estructuras, remontadas, primera sangre y tus mejoras."),
        ("mejora", "Las tarjetas de resumen cambian súbditos y visión por daño recibido y curación."),
    ]},
    {"v": "1.16.1", "fecha": "8 de noviembre de 2026", "titulo": "Ajustes tras jugar otro ARAM", "items": [
        ("arreglo", "Las mejoras sugeridas por op.gg salían todas como texto sin icono ni categoría: el catálogo guardado era de una versión anterior y ahora se refresca solo."),
        ("mejora", "En la selección de ARAM, la build de tu campeón sale antes que la lista del banquillo."),
        ("mejora", "Comprobado: al terminar la partida la ventana pasó sola al Análisis con las mejoras de los 10 jugadores."),
    ]},
    {"v": "1.16.0", "fecha": "8 de noviembre de 2026", "titulo": "Builds de ARAM y Mayhem, y análisis al terminar", "items": [
        ("nuevo", "Build sugerida para ARAM y ARAM: Mayhem (objetos iniciales, botas, 5 builds de 3 objetos y orden de habilidades), de op.gg. Sale en la selección con tu campeón y en Partida > Plan durante la partida."),
        ("nuevo", "En Mayhem, las mejoras que sugiere op.gg para tu campeón, agrupadas por categoría (Prismática, Oro, Plata) y con sus iconos, sin porcentajes."),
        ("nuevo", "Al terminar la partida la ventana pasa sola al Análisis de esa partida (con las mejoras de los 10 jugadores)."),
    ]},
    {"v": "1.15.2", "fecha": "8 de noviembre de 2026", "titulo": "Ajustes tras probar Mayhem", "items": [
        ("arreglo", "Al empezar una partida, la ventana enseña el plan y no el análisis de la anterior."),
        ("arreglo", "Los iconos de mejoras aparecen solos en cuanto se descargan (antes salían como letras hasta repintar)."),
        ("mejora", "Comprobado con una partida real: la API en vivo de Riot no incluye las mejoras de Mayhem, así que se ven al terminar la partida."),
    ]},
    {"v": "1.15.1", "fecha": "8 de noviembre de 2026", "titulo": "Preparado para probar Mayhem", "items": [
        ("mejora", "En una partida de Mayhem LOL-E consulta la API en vivo cada 20 s y guarda hasta 6 muestras completas (cache/live_samples) para ver qué datos de mejoras trae."),
        ("mejora", "Si la API trae mejoras, se muestran por su nombre y categoría en Partida > Plan."),
    ]},
    {"v": "1.15.0", "fecha": "8 de noviembre de 2026", "titulo": "ARAM: Mayhem y sus mejoras", "items": [
        ("nuevo", "En ARAM: Mayhem, la pestaña Partida > Plan enseña las mejoras que más has elegido con tu campeón (con icono, nombre y categoría)."),
        ("nuevo", "En el Análisis de una partida de Mayhem, «Mejoras elegidas» muestra las de los 10 jugadores. Sin líneas: el rival de comparación es el que más daño hizo."),
        ("nuevo", "Durante la partida LOL-E consulta la API de partida en vivo de Riot para ver si trae tus mejoras y guarda lo que encuentre, para poder aprovecharlo."),
        ("mejora", "Riot no permite que las aplicaciones muestren porcentajes de victoria de mejoras, así que LOL-E no los enseña ni inventa una «mejor mejora»."),
    ]},
    {"v": "1.14.1", "fecha": "8 de noviembre de 2026", "titulo": "ARAM mostraba la build del campeón anterior", "items": [
        ("arreglo", "En ARAM (y Arena y otros modos sin línea) la pestaña Partida enseñaba el plan y la build de la partida anterior (por ejemplo Urgot teniendo Lee Sin). Ahora muestra tu campeón actual y avisa de que en ese modo no hay plan de línea."),
        ("arreglo", "Al empezar una selección nueva sin campeón marcado se descarta el plan de la partida anterior."),
    ]},
    {"v": "1.14.0", "fecha": "8 de noviembre de 2026", "titulo": "Draft de 5 completo", "items": [
        ("nuevo", "Tarjeta «Draft de 5» en Clasificatorias de 5 y Clash: la tira de bans y picks (verde tu equipo, rojo el rival), de quién es el turno y cuántas acciones faltan para el tuyo."),
        ("nuevo", "Bans dirigidos: por cada rival que aún no ha elegido, los campeones que más puede jugar, con puntaje (maestría, veces jugado y % de victorias) a la vista."),
        ("nuevo", "Línea probable de cada rival (los rivales no la traen) y, con ella, tu rival directo: ya se usa para el enfrentamiento y la build."),
        ("nuevo", "Rango medio de cada equipo, diferencia entre jugadores y cuentas sin rango; los perfiles rivales se leen primero y más rápido."),
        ("mejora", "Bloque de rango «Clasificatorias de 5» en el Asesor cuando tienes rango en esa cola."),
    ]},
    {"v": "1.13.3", "fecha": "8 de noviembre de 2026", "titulo": "Perfil completo de cada jugador", "items": [
        ("nuevo", "En «Tu equipo» y «Equipo rival», cada jugador tiene «Perfil completo»: sus rangos (Solo/Dúo, Flexible y Clasificatorias de 5), máximo de la temporada y de la anterior, últimas partidas con campeón y resultado, rendimiento (KDA, súbditos, daño y visión por minuto, duración), campeones más jugados, mayor maestría, líneas y señales (rachas, inactividad, cuenta secundaria)."),
        ("arreglo", "La vista «Lista» de recomendaciones podía fallar y quedarse vacía con ciertas escalas de pantalla. Corregido."),
    ]},
    {"v": "1.13.2", "fecha": "8 de noviembre de 2026", "titulo": "Clasificatorias de 5: tu rango y el de los rivales", "items": [
        ("nuevo", "En Clasificatorias de 5 se usa el rango de esa cola (tiene su propia escalera), tanto el tuyo como el de tus aliados y rivales."),
        ("nuevo", "Los PL de cada partida de Clasificatorias de 5 también se calculan."),
        ("mejora", "Un jugador sin rango y con casi ningún historial reciente se marca como «Sin rango ni historial» (cuentas nuevas o poco fiables)."),
    ]},
    {"v": "1.13.1", "fecha": "8 de noviembre de 2026", "titulo": "Clasificatorias de 5 (grupos de 5)", "items": [
        ("arreglo", "La cola «Clasificatorias de 5» se trataba como un modo desconocido y no daba recomendaciones, roles ni bans. Ahora funciona como la Grieta."),
        ("nuevo", "En esa cola el cliente enseña los nombres del equipo rival: LOL-E muestra de cada rival su rango, su forma reciente, los campeones que más juega y su maestría con el que elige."),
        ("arreglo", "Los bans de esa cola (que el cliente da de otra forma) ya se ven."),
    ]},
    {"v": "1.13.0", "fecha": "7 de noviembre de 2026", "titulo": "Novedades dentro de la aplicación", "items": [
        ("nuevo", "Esta ventana: al abrir una versión nueva verás qué ha cambiado. Puedes cerrarla y volver a consultarla en Ajustes → «Ver novedades»."),
    ]},
    {"v": "1.12.2", "fecha": "7 de noviembre de 2026", "titulo": "PL por partida y arreglos de la selección", "items": [
        ("nuevo", "PL ganados o perdidos en cada partida clasificatoria (Solo/Dúo y Flexible), con el rango actual y los ascensos o descensos."),
        ("arreglo", "El análisis de la partida recién jugada ya no muestra la anterior: LOL-E espera a que el cliente la liste."),
        ("arreglo", "En la selección de campeón, el panel de build recuerda la vista elegida (Más usada, Variantes o Situaciones)."),
    ]},
    {"v": "1.12.1", "fecha": "6 de noviembre de 2026", "titulo": "Hora en el historial", "items": [
        ("mejora", "Cada partida del Historial muestra su hora de inicio, para saber cuál fue antes y cuál después."),
    ]},
    {"v": "1.12.0", "fecha": "6 de noviembre de 2026", "titulo": "Retratos y nombres más claros", "items": [
        ("arreglo", "Los retratos de campeón ya no salen descentrados ni cortados en ninguna pantalla."),
        ("mejora", "«Núcleo» pasa a «Principales»; los huecos siguientes son «4.º, 5.º y 6.º objeto»."),
        ("mejora", "La ventana recuerda dónde estaba y se abre en el mismo monitor."),
        ("mejora", "Un solo nombre para limpiar filtros: «Restablecer filtros»."),
    ]},
]


def unseen(conf):
    return conf.get("notes_seen") != NOTES[0]["v"]


class NotesWindow:
    """Ventana de novedades. `ui` es la interfaz principal (para fuentes, colores y posición)."""

    def __init__(self, ui, on_close=None):
        self.ui, self.on_close = ui, on_close
        k = ui.kit
        w = ctk.CTkToplevel(ui.root)
        self.w = w
        w.title("LOL-E · Novedades")
        w.configure(fg_color=PAL["bg"])
        w.resizable(False, True)
        sc = ui.win_scale()
        W, H = 460, 560
        try:  # sobre la ventana principal, en su mismo monitor
            x = ui.root.winfo_rootx() + max(0, (ui.root.winfo_width() - int(W * sc)) // 2)
            y = ui.root.winfo_rooty() + 60
            w.geometry(f"{int(W * sc)}x{int(H * sc)}+{x}+{y}")
        except Exception:
            w.geometry(f"{W}x{H}")
        w.transient(ui.root)
        w.protocol("WM_DELETE_WINDOW", self.close)
        ctk.CTkLabel(w, text="Novedades", font=k.font(20, True, True), text_color=PAL["fg"], anchor="w").pack(fill="x", padx=20, pady=(18, 0))
        ctk.CTkLabel(w, text=f"Estás en la versión {NOTES[0]['v']}", font=k.font(11), text_color=PAL["dim"], anchor="w").pack(fill="x", padx=20, pady=(0, 8))
        body = ctk.CTkScrollableFrame(w, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8)
        for i, n in enumerate(NOTES):
            card = ctk.CTkFrame(body, fg_color=PAL["card"], corner_radius=10, border_width=1, border_color=PAL["border"])
            card.pack(fill="x", padx=8, pady=6)
            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=14, pady=(12, 2))
            ctk.CTkLabel(head, text=f"Versión {n['v']}", font=k.font(14, True), text_color=k.acc if i == 0 else PAL["fg"]).pack(side="left")
            ctk.CTkLabel(head, text=n["fecha"], font=k.font(10), text_color=PAL["dim"]).pack(side="right")
            ctk.CTkLabel(card, text=n["titulo"], font=k.font(12, True), text_color=PAL["fg"], anchor="w", justify="left",
                         wraplength=int(380 * sc)).pack(fill="x", padx=14, pady=(0, 6))
            for tipo, texto in n["items"]:
                label, color = TIPOS[tipo]
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=14, pady=3)
                ctk.CTkLabel(row, text=label, width=70, font=k.font(9, True), text_color=PAL[color], anchor="w").pack(side="left", anchor="n", pady=(2, 0))
                ctk.CTkLabel(row, text=texto, font=k.font(11), text_color=PAL["fg"], anchor="w", justify="left",
                             wraplength=int(300 * sc)).pack(side="left", fill="x", expand=True)
            ctk.CTkFrame(card, height=8, fg_color="transparent").pack()
        b = ctk.CTkButton(w, text="Entendido", font=k.font(12, True), fg_color=k.acc, text_color=PAL["bg"], hover_color=k.acc, command=self.close)
        b.pack(fill="x", padx=20, pady=14)
        try:
            w.after(150, w.lift)
        except Exception:
            pass

    def close(self):
        try:
            self.w.destroy()
        except Exception:
            pass
        if self.on_close:
            self.on_close()
