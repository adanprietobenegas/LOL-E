"""Todo lo que se puede ajustar en el cálculo, con su explicación: pesos de la afinidad y umbrales de las reglas.

La pestaña «Datos» de la ventana se genera a partir de este archivo, así que lo que se explica allí es exactamente lo que se usa.
"""

# (nombre, qué es, qué pasa si lo subes, qué pasa si lo bajas)
WEIGHT_INFO = {
    "mastery": ("Maestría",
                "Cuánto pesa tu maestría con el campeón. Tu campeón con más puntos vale el máximo; el resto, proporcional.",
                "Recomienda sobre todo tus campeones de siempre.", "Da más cabida a campeones que juegas poco."),
    "winrate": ("Tus victorias",
                "Tu porcentaje de victorias con el campeón (en tu línea si tienes partidas ahí; si no, el de la temporada). "
                "Se suaviza: con pocas partidas se acerca al 50 %.",
                "Se fía más de tus resultados reales.", "Se fía menos de resultados con pocas partidas."),
    "role": ("Encaje con tu rol",
             "Si el campeón se juega de verdad en la línea que te ha tocado (según las posiciones de Meraki Analytics).",
             "Penaliza más los campeones que no son de tu línea.", "Tolera más campeones de otras líneas."),
    "comp": ("Necesidades del equipo",
             "Lo que falta en tu equipo: un tanque si no hay, daño físico o mágico si está desequilibrado, control si hay poco.",
             "Prioriza completar la composición.", "Prioriza tus gustos sobre la composición."),
    "counter": ("Contra tu rival",
                "Tu historial con ese campeón contra el rival de tu línea (de tu cliente y de op.gg).",
                "Pesa más cómo te ha ido contra ese rival.", "Ignora más los enfrentamientos pasados."),
    "synergy": ("Sinergia con tu equipo",
                "Reglas de composición con los aliados ya elegidos (dúo de línea, frontal y carry, control y asesino, "
                "daño complementario) más tu historial jugando con cada pareja.",
                "Prioriza campeones que encajan con tus compañeros.", "Elige más por ti mismo que por el equipo."),
    "meta": ("Meta del parche",
             "Tasa de victorias del campeón en tu línea y rango este parche (Lolalytics). Vale +1 a partir de 54 % y −1 por debajo de 46 %.",
             "Recomienda más lo que está fuerte ahora.", "Ignora el estado del parche."),
}

# clave: (nombre, valor por defecto, mínimo, máximo, paso, qué es, qué pasa si lo subes / lo bajas)
PARAM_INFO = {
    "min_games_mine": ("Partidas para «Mis campeones»", 3, 1, 20, 1,
                       "Partidas que necesitas con un campeón para que cuente como tuyo en el filtro «Mis campeones».",
                       "Filtro más estricto: solo campeones muy jugados.", "Filtro más laxo: basta con haberlo probado."),
    "off_role_games": ("Partidas para jugar fuera de rol", 3, 1, 20, 1,
                       "Si un campeón no es de tu línea pero ya lo has jugado ahí al menos estas veces, se acepta como opción.",
                       "Solo acepta fuera de rol lo que has jugado mucho.", "Acepta fuera de rol con pocas partidas."),
    "lane_share_min": ("Línea alternativa: % de partidas", 2, 1, 30, 1,
                       "Un campeón se considera «de tu línea» aunque no sea la habitual si, según el meta, se juega ahí al menos este "
                       "porcentaje de sus partidas (por ejemplo, Ezreal en Central). Así no se descartan los picks que ahora se juegan "
                       "en otras líneas.",
                       "Solo cuentan líneas alternativas muy jugadas.", "Más campeones fuera de su línea habitual entran en «Mi rol»."),
    "meta_strong": ("«Meta fuerte» desde (% victorias)", 52.0, 50.0, 56.0, 0.5,
                    "A partir de este porcentaje se añade la etiqueta «Meta fuerte» a un campeón.",
                    "Etiqueta más exclusiva.", "Etiqueta más frecuente."),
    "meta_weak": ("«Meta débil» hasta (% victorias)", 48.5, 44.0, 50.0, 0.5,
                  "Por debajo de este porcentaje se añade la etiqueta «Meta débil».",
                  "Marca como débiles más campeones.", "Marca como débiles solo los peores."),
    "meta_filter": ("Filtro «Meta fuerte» (% mínimo)", 50.5, 48.0, 55.0, 0.5,
                    "Porcentaje mínimo para que un campeón pase el filtro «Meta fuerte» de encima del carrusel.",
                    "Filtro más estricto.", "Filtro más laxo."),
    "winrate_prior": ("Suavizado de tus victorias", 4, 0, 20, 1,
                      "Partidas «virtuales» al 50 % que se suman a las tuyas. Evita que 1 victoria de 1 parezca un 100 %.",
                      "Desconfía más de muestras pequeñas.", "Se fía de muestras pequeñas."),
    "pair_games": ("Partidas por pareja de campeones", 2, 1, 10, 1,
                   "Partidas jugando tu campeón con un aliado concreto para tener en cuenta vuestro historial.",
                   "Exige más historial para influir.", "Basta con muy pocas partidas."),
    "ban_games": ("Partidas para sugerir un ban", 2, 1, 10, 1,
                  "Partidas contra un rival de línea para poder sugerir banearlo.",
                  "Solo sugiere rivales que has visto mucho.", "Sugiere con poca experiencia."),
    "ban_loss": ("Derrotas para sugerir un ban (%)", 60, 50, 90, 5,
                 "Porcentaje de derrotas contra ese rival a partir del cual se sugiere banearlo.",
                 "Solo sugiere rivales que te ganan casi siempre.", "Sugiere rivales que te ganan a menudo."),
}
DEFAULT_PARAMS = {k: v[1] for k, v in PARAM_INFO.items()}

# fuentes de datos: (id, nombre, qué da, para qué se usa, opcional)
SOURCES = [
    ("lcu", "Tu cliente de LoL", "Tu perfil, rangos, historial, maestría y la selección de campeón; también el perfil público de tus compañeros "
     "que el cliente ya muestra.", "Todo lo personal: afinidad, rol, historial, jugadores del equipo.", False),
    ("ddragon", "Data Dragon (Riot)", "Lista de campeones, iconos, arte, iconos de invocador y versión del parche.",
     "Nombres, tipos de campeón, daño físico o mágico y las imágenes.", False),
    ("meraki", "Meraki Analytics", "En qué líneas se juega cada campeón y sus atributos (control, resistencia, utilidad…).",
     "Encaje con tu rol, sinergias y consejos de construcción.", False),
    ("opgg", "op.gg (tu perfil público)", "Tus estadísticas de la temporada y tus enfrentamientos, por campeón y rival.",
     "Más historial del que guarda tu cliente: victorias y «contra rival».", True),
    ("meta", "Lolalytics: meta del parche", "Victorias, uso y baneos de cada campeón por línea y rango (una petición por línea al día).",
     "Etiquetas de meta, la pestaña «Meta y build» y un punto en la afinidad.", True),
    ("matchups", "Lolalytics: enfrentamientos", "Tabla de resultados de un campeón contra todos los demás en su línea (una descarga por rival, "
     "se guarda un día).", "La pestaña «Enfrentamiento»: mejores picks contra un rival.", True),
    ("cdragon", "CommunityDragon", "Emblemas de rango.", "Solo decorativo.", False),
]
