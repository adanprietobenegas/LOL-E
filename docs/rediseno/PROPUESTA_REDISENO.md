# Propuesta de rediseño de LOL-E (borrador, 11/11/2026)

Estado: **NADA de esto está implementado.** Es la síntesis de una auditoría externa (tres expertos independientes: arquitectura y UX,
diseño visual y densidad, y jugador competitivo/analista de producto) más un prototipo interactivo para que lo revise el usuario.
Prototipo: `docs/rediseno/prototipo_v1.html` (ábrelo en el navegador; botones «Simular» para recorrer cola, selección, carga, partida y fin).

## Lo que pidió el usuario
- Separar totalmente el **modo en partida** (detectado: cola, selección, carga, partida) de las **consultas** (historial, builds, matchups…) y que se note en qué modo está.
- Simplificar y hacer la app más visual: sintetizar sin perder información, quitar lo innecesario.
- Estudiar navegación con barra superior, menú lateral o hamburguesa. Ver un primer diseño antes de decidir (puede pulirse o descartarse).
- El tablero de jugadores solo donde aplique (no en ARAM) y plegable.

## Coincidencias de los tres expertos
1. «Asesor» y «Partida» mezclan consulta y ayuda en vivo; el verde de «estado» se confunde con el de «conectado».
2. Demasiado texto: la guía de duelo (10-12 líneas de enfriamientos y consejos) y la build (7 filas con etiqueta) son un muro. Mejor barras comparativas, chips con veredicto, ruta de compra en una línea y la prosa en tooltip.
3. La pestaña Datos es documentación: va a Ajustes. Máximo 2 niveles de pestañas (hoy hay 3 en Selección).
4. En cada momento, una pregunta respondida en 3 segundos (carga: quién es mi rival y qué debo saber de los 10).

## Navegación (recomendación del experto UX)
- **Barra lateral de iconos** que se expande: mejor encaje con 1000x900 y mejor señal de modo. La hamburguesa se descarta como estructura principal (esconde lo que se usa a menudo); vale solo para ajustes/ayuda.
- Mapa propuesto: **En vivo** (solo con cola/partida), **Inicio** (perfil, rango, racha, últimas 5), **Campeones** (repertorio, recomendaciones, builds, meta), **Enfrentamientos**, **Historial**, **Ajustes** (incluye «Acerca de los datos»). Se elimina la pestaña Datos y se funden Modos/Repertorio.
- Modo en vivo: banda de estado ámbar con fase, temporizador y campeón; icono propio; contenido a ancho completo en una pantalla. Modo consulta: acento azul actual. Botón «Consultar» desde en vivo y «Volver a la partida» siempre visible, sin perder el estado.
- Cambio de modo: automático en cola/selección/carga/partida; al terminar, aviso reversible. Si el usuario está leyendo en consulta, valorar banner con cuenta atrás (en selección, cambio inmediato porque el tiempo manda).

## Por momento (experto jugador)
| Momento | Imprescindible | Plegado / fuera |
|---|---|---|
| Fuera de partida | Rango y PL, últimas 5, racha, campeón sugerido | Repertorio, modos, logros |
| En cola | Tiempo, rol asignado, mejor campeón por rol | Todo lo demás |
| Selección | Turno y temporizador, rival de línea, top 3 con % contra rival, bans, equilibrio de daño | Desglose de afinidad, sinergias, build completa |
| Carga | Rival de línea con %, los 10 con rango y señales (racha, especialista, fuera de línea), daño del rival | Guía de duelo |
| Partida | Build en orden, runas, rival (definitiva), timers (por verificar) | Guía, habilidades |
| Fin | Resultado y por qué, delta de PL, una frase de mejora | Estadísticas largas |

ARAM / ARAM Caos / Arena: sin línea ni rival directo; mostrar campeón, runas/build de equipo, banquillo con diferencia de victorias, composición y tipo de daño del rival, aumentos. El tablero 5 contra 5 ya **no sale** fuera de la Grieta.

## Mejoras visuales por impacto/esfuerzo (experto visual)
1. Textos explicativos fijos a tooltips «i».
2. Historial: fila con barra de resultado a la izquierda (sin botón «Victoria»), una columna menos, fecha y duración juntas.
3. Quitar KPI duplicados en Selección y las filas de afinidad a +0,0.
4. Duelo como tarjeta de barras comparativas + chips (nivel 1, escalado, hueco de trade, tipo de daño); prosa plegada.
5. Build como ruta continua con iconos.
6. Asesor en reposo: una fila de tarjetas, sin sub-pestañas, sin el «ok».
7. Enfrentamiento: barra única (buscador + chips de línea con icono + filtros plegados) y recientes como retratos.
8. Datos dentro de Ajustes; sonido fuera de la cabecera.
Principios: 4 niveles tipográficos, color con significado (verde/rojo solo con umbral, dorado = acento), 8/16/24 px, 1 mensaje principal + 3-5 secundarios por pantalla. No tocar: historial agrupado por día, retratos y anillo de afinidad, chips V/D, acordeones de equipos, selector de rival «Auto», panel lateral de Ajustes.

## Ideas del experto jugador (sin verificar)
- Datos en vivo del propio juego durante la partida (puerto local 2999): objetos del rival, timers de objetivos, contra-objetos. El proyecto ya tiene una sonda para ARAM Caos (`augments.live_probe`); falta comprobar qué entrega en la Grieta.
- Mostrar los hechizos de invocador de cada rival (el cliente los da en la carga; ya se leen en `players.game_roster`, solo falta dibujarlos).
- Resumen de una frase al terminar, comparado con la media propia.

## Riesgos y pruebas antes de comprometerse
- Detección de modo equivocada o tardía (cola cancelada, dodge, reconexión, ARAM); cambios que roban el foco; mantener dos layouts; ventana pequeña con barra expandida.
- Probar: maqueta con 3-5 personas cronometradas («¿quién es tu rival y qué build llevas?» en menos de 5 s); la detección de modo con varias partidas (dodge, remake, ARAM, personalizada); consulta a mitad de partida y vuelta; contar clics actuales hasta Historial/Enfrentamiento; comparar con el **rediseño mínimo** (solo cabecera de modo + reorden del Asesor) antes de cambiar toda la navegación; contraste para daltónicos del nuevo color de modo.

## Decisiones pendientes del usuario
1. ¿Barra lateral completa o rediseño mínimo (cabecera de modo y reorden)?
2. Cambio de modo: ¿siempre automático o con aviso y cuenta atrás cuando se está leyendo en consulta?
3. Qué recortes de la lista visual se aceptan (desgloses de afinidad, 3 vistas de recomendaciones, filtros, etc.).
4. Si se investiga el uso de los datos en vivo del juego (timers, objetos del rival).

## Cómo se generó el material de la auditoría
Capturas simuladas de cada pantalla con el arnés de pruebas (datos de ejemplo, ventana 1000x900) y tres agentes de revisión de solo lectura. Las cifras y afirmaciones de los expertos sobre datos externos (por ejemplo qué entrega el puerto 2999 o qué hace Porofessor) son opiniones sin comprobar.
