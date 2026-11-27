"""Ayuda de LOL-E: qué es cada pantalla, cuándo la verás y de dónde salen sus datos, y las preguntas que se hace quien acaba de instalarla.

Solo datos y búsqueda (sin ventana), para poder probarlos. Es la capa A de la «guía»: ayuda contextual y un panel de preguntas con buscador. Las mismas preguntas servirán
de menú para la demostración en vivo cuando se construya (cada una podrá enlazar a una lección). Los textos describen lo que la app hace hoy: si cambia una pantalla,
hay que cambiar aquí su frase (una prueba comprueba que cada pregunta apunta a una página que existe)."""
import unicodedata

import parche

# clave de página -> (nombre en la barra, qué es, cuándo la verás, de dónde sale)
PAGES = {
    "Asesor": ("Inicio", "Tu perfil, tu rango y cómo ha ido (gráfica), tus últimas partidas y tu sesión. En la selección de campeón se convierte en el asesor con los campeones recomendados.",
               "Siempre. Con el cliente abierto verás tus datos y, al entrar en selección, cambia sola.",
               "Tu cliente de LoL (perfil, rango, historial) y, para las recomendaciones, Lolalytics y op.gg."),
    "Partida": ("En vivo", "El plan de tu partida: campeón, rival de línea, build y runas recomendadas y, ya jugando, marcador, objetivos y los 10 jugadores. Al terminar, el análisis.",
                "Desde que hay cola, selección o partida (la barra se tiñe de ámbar); después, el análisis de la última.",
                "Lolalytics y op.gg para builds y runas; tu cliente y la API local del propio juego para el marcador en vivo."),
    "Enfrentamiento": ("Enfrentamiento", "Qué campeón le gana a cuál en cada línea, con porcentajes de todos los jugadores y cómo te va a ti.",
                       "Cuando quieras preparar o revisar un cruce. En la selección se rellena con tu rival de línea.",
                       "Lolalytics (todos los jugadores) y tu historial guardado."),
    "Repertorio": ("Campeones", "Tu repertorio: con qué campeones juegas, cómo te va con cada uno y a cuál conviene sumar si dependes mucho de uno.",
                   "Siempre que quieras revisar tus campeones.", "Tu historial guardado y Lolalytics."),
    "Historial": ("Historial", "Todas tus partidas guardadas, con filtros, resumen, patrón de derrotas, dónde mueres y «Tu año en LoL».",
                  "Cuando quieras revisar o buscar partidas.",
                  "El cliente solo entrega las más recientes: LOL-E guarda cada partida que ve para que el historial crezca."),
    "Parche": ("Parche", "Las notas oficiales del último parche, en español y tal como las publica Riot, y cómo se está moviendo el juego con él: qué campeones suben o bajan en victorias y uso, quién cambia de línea y qué pasó con los que tocaron las notas.",
               "Cuando salga un parche nuevo la barra lo avisa con un punto. Las primeras horas hay pocas partidas: las estadísticas lo dicen.",
               "Las notas, de leagueoflegends.com/es-es (Riot); las estadísticas, de Lolalytics (partidas clasificatorias en solitario de tu elo)."),
    "Datos": ("Datos", "De dónde sale cada dato, cómo se calcula la afinidad, los umbrales y un glosario.",
              "Cuando quieras saber cuánto fiarte de algo.", "Es la propia documentación de la app."),
}

# (id, pregunta, respuesta de una o dos frases, destino: nombre de página, «ajustes» o None, palabras clave)
TOPICS = [
    ("que_es", "¿Qué es LOL-E y qué lee de mi PC?",
     "Es un asesor que lee tu cliente de LoL (y la API local del juego durante la partida) para recomendarte campeones y builds y analizar tus partidas. "
     "Solo escribe objetos o runas si tú lo pides; las estadísticas salen de Lolalytics y op.gg.", "Datos", "que es lee pc privacidad datos cliente"),
    ("seguro", "¿Es seguro? ¿Me pueden sancionar?",
     "LOL-E lee tu cliente y la API local de la partida. Solo escribe si se lo pides (con un botón o activando el envío automático): tu conjunto de objetos y la página de runas «LOL-E» (no borra páginas). "
     "No inyecta nada ni juega por ti. "
     "Aun así, la última palabra la tiene Riot y no hay garantía formal.", "Datos", "seguro baneo ban sancion riot vanguard permitido"),
    ("antes", "¿Qué veo antes de jugar?",
     "En Inicio: tu perfil, tu rango, la gráfica de tu rango en el tiempo, tus últimas partidas y, si llevas derrotas seguidas, un aviso de sesión.", "Asesor",
     "inicio perfil rango grafica sesion antes"),
    ("cola", "¿Qué pasa cuando busco partida?",
     "En la barra lateral, «Partida» pasa a llamarse «En vivo» y se tiñe de ámbar, y arriba aparece una banda con la fase (cola, selección, partida) y un botón para ir y volver "
     "entre la partida y la consulta.", "Partida", "cola buscar partida banda ambar en vivo fase"),
    ("elegir", "¿Cómo elijo campeón?",
     "En la selección, Inicio te recomienda campeones para tu línea con una afinidad de 0 a 100. Puedes filtrar (Mi rol, Mis campeones, Meta fuerte) y mirar "
     "Resumen, Contra rival, Sinergias y Meta y build.", "Asesor", "elegir campeon recomendado afinidad seleccion filtros"),
    ("runas_builds", "¿Dónde encuentro las runas y builds recomendadas?",
     "En la selección, en «Meta y build» del campeón. Con tu campeón marcado, también en «En vivo»: hechizos, runas (más usada o mayor % de victorias), habilidades, "
     "objetos y botas, con pestañas Más usada, Variantes y Situaciones.", "Partida", "runas build objetos botas hechizos habilidades recomendadas"),
    ("en_partida", "¿Cómo uso la app durante la partida?",
     "Mira «En vivo»: arriba el marcador, los objetivos (con avisos estimados de dragón, larvas y Barón), tu siguiente objeto y tu objetivo; debajo va tu build (las runas, "
     "tras un enlace) y después los 10 jugadores, plegados. Si no quieres los datos en vivo, se apagan en Ajustes.", "Partida", "partida jugando en vivo marcador objetivos dragon barón siguiente objeto"),
    ("terminar", "¿Qué veo al terminar la partida?",
     "En «Partida › Análisis»: primero un resumen; en el análisis completo, la comparación con tu rival y tu media, tu objetivo y el botón para guardar la tarjeta "
     "de la partida.", "Partida", "terminar fin analisis pl resultado tarjeta objetivo"),
    ("historial", "¿Cómo reviso mis partidas?",
     "En Historial: busca y filtra, mira tu resumen (sesión, patrón de derrotas, dónde mueres) y abre «Tu año en LoL». Cada partida se despliega con su detalle.", "Historial",
     "historial revisar partidas filtros patron donde mueres año"),
    ("enfrentamiento", "¿Cómo comparo un enfrentamiento?",
     "En Enfrentamiento: elige a tu rival (o toca uno reciente) y verás qué campeón le gana más, con datos de todos los jugadores y los tuyos.", "Enfrentamiento",
     "enfrentamiento rival comparar counter contra"),
    ("aprender", "¿Qué campeones me conviene aprender?",
     "En Campeones, «Qué aprender»: si en una línea dependes mucho de un solo campeón, te propone hasta tres que ya tienes con buena tasa en el parche.", "Repertorio",
     "aprender campeones repertorio alternativa ban"),
    ("primera", "¿Qué pasa en mi primera partida con LOL-E?",
     "Tu rango y estadísticas salen solos del cliente. El historial propio empieza con tus partidas recientes y crece mientras usas LOL-E; al acabar cada una aparece su resumen.", "Historial",
     "primera partida empezar nuevo historial instalar"),
    ("afinidad", "¿Qué significa la afinidad?",
     "Un número de 0 a 100: cuánto encaja un campeón contigo ahora mismo (tu historial, el parche, tu equipo y tu rival). No es una probabilidad de ganar; los pesos se ven en Datos.", "Datos",
     "afinidad puntos recomendacion numero que significa"),
    ("jugadores", "¿Qué veo de los otros nueve jugadores?",
     "En «En vivo» hay un tablero plegable con los 10: rango, rachas y lo que más juega cada uno, y tu rival de línea. Los datos salen del cliente.", "Partida",
     "jugadores equipo rival tablero carga rango racha"),
    ("patron", "¿Qué es el patrón de mis derrotas y mi objetivo?",
     "Con tus partidas analizadas, LOL-E busca qué se repite cuando pierdes (muertes tempranas, farmeo, oro). Si hay patrón, te marca un objetivo para la partida y luego dice si lo cumpliste.", "Historial",
     "patron derrotas objetivo muertes sesion tilt"),
    ("modos", "¿Y en ARAM, Arena u otros modos?",
     "Sin líneas ni rival directo: en ARAM ves tu campeón, su build y el banquillo; en Arena y otros, el análisis al terminar. La build de línea es solo de la Grieta.", "Asesor",
     "aram arena mayhem modos sin linea otros"),
    ("compartir", "¿Cómo comparto mis partidas?",
     "En el análisis, «Guardar tarjeta de la partida»; en el Historial, «Tu año en LoL» con «Guardar como imagen». Las dos crean un PNG.", "Historial",
     "compartir imagen tarjeta año png guardar"),
    ("parche", "¿Dónde veo las notas del parche y cómo va el parche nuevo?",
     "En «Parche»: arriba las notas oficiales de Riot en español, con filtros por campeones, objetos o modos, y en «Estadísticas» cómo cambian victorias, uso y baneos frente al parche anterior.", "Parche",
     "parche notas version cambios nerf buff estadisticas meta actualizacion"),
    ("atajos", "¿Hay atajos de teclado?",
     "Ctrl+1 a Ctrl+7 cambian de pantalla, las flechas también, F1 abre la ayuda y Esc cierra Ajustes o la guía.", "Asesor", "atajos teclado ctrl f1 flechas"),
    ("contra_rivales", "¿Cuáles son los mejores campeones contra mis rivales?",
     "En la selección, la tarjeta «Mejores campeones contra tus rivales» enseña los 5 campeones que más ganan a tu rival de línea y los 3 que más ganan a cada uno de los demás rivales elegidos, "
     "con el porcentaje y las partidas de cada cruce. Aparte de la afinidad: aquí solo cuenta el enfrentamiento. Marca los que tienes.", "Asesor",
     "mejores contra rivales counter enemigos enfrentamiento seleccion picks"),
    ("actualizar", "¿Cómo busco actualizaciones sin cerrar la app?",
     "Pulsa el número de versión de arriba (vX.Y.Z) y verás «buscando…», «al día ✓» o «hay una nueva». También está en Ajustes › «Buscar actualizaciones ahora».", "ajustes",
     "actualizar actualizacion version nueva buscar update"),
    ("fuentes", "¿De dónde sale la información y cuánto me puedo fiar?",
     "Builds y porcentajes: Lolalytics y op.gg. Tu historial y rango: tu cliente. El marcador en vivo: la API local del juego. Los datos con pocas partidas se marcan, y "
     "los avisos de objetivos son estimaciones.", "Datos", "fuentes de donde sale informacion fiable lolalytics opgg datos"),
    ("personalizar", "¿Cómo la personalizo?",
     "En Ajustes y datos: tema y color, tamaño, barra lateral, avisos sonoros, si la ventana va siempre encima y los datos en vivo.", "ajustes",
     "personalizar ajustes tema color tamaño sonido barra"),
    ("sin_datos", "¿Por qué no veo datos o no se detecta el cliente?",
     "Abre League of Legends e inicia sesión: LOL-E se conecta solo (arriba debe poner «Conectado a LoL»). Si ya está abierto y no conecta, reinicia LOL-E. "
     "Sin partidas guardadas, el Historial y las estadísticas están vacíos hasta que juegues.", "ajustes", "no veo datos no detecta cliente conectado vacio error diagnostico"),
]


# término (en mayúsculas, como sale en la pantalla) -> explicación corta, para el globo al pasar el ratón
GLOSARIO = {
    "KDA MEDIO": "(bajas + asistencias) entre muertes, sumando todas las partidas (no es la media de cada una).",
    "KDA": "(bajas + asistencias) entre muertes. Por encima de 3 se considera bueno.",
    "RACHA": "Las victorias o derrotas seguidas más recientes.",
    "VICTORIAS": "Porcentaje de partidas ganadas dentro de lo que ves ahora (según los filtros).",
    "DURACIÓN MEDIA": "Lo que dura de media tu partida, en minutos.",
    "PL": "Puntos de liga: al llegar a 100 subes de división; si bajas de 0, pierdes la división (con protección al subir).",
    "AFINIDAD": "De 0 a 100: cuánto encaja un campeón contigo ahora mismo. No es una probabilidad de ganar.",
    "MI ROL": "Solo campeones que se juegan en tu línea asignada.",
    "MIS CAMPEONES": "Solo los campeones que tienes desbloqueados.",
    "META FUERTE": "Solo campeones con buena tasa de victoria en este parche (Lolalytics).",
}


if not parche.ACTIVO:   # pantalla Parche reservada
    PAGES.pop('Parche', None)
    TOPICS[:] = [t for t in TOPICS if t[0] != 'parche']


def glossary(term):
    """La explicación de un término, o None."""
    return GLOSARIO.get((term or "").upper())


def _norm(text):
    """Minúsculas y sin acentos, para buscar sin preocuparse de ellos."""
    return "".join(c for c in unicodedata.normalize("NFD", (text or "").lower()) if unicodedata.category(c) != "Mn")


def search(query):
    """Las preguntas que encajan con lo escrito (todas las palabras, en la pregunta, la respuesta o las claves); sin texto, todas. Mantiene el orden del catálogo."""
    words = _norm(query).split()
    if not words:
        return list(TOPICS)
    out = []
    for t in TOPICS:
        hay = _norm(" ".join((t[1], t[2], t[4])))
        if all(w in hay for w in words):
            out.append(t)
    return out


def page_help(key):
    """(nombre, qué es, cuándo, de dónde sale) de una página, o None."""
    return PAGES.get(key)
