# Propuesta de rediseño de LOL-E (borrador, 11/11/2026)

Estado: **NADA de esto está implementado.** Es la síntesis de una auditoría externa (tres expertos independientes: arquitectura y UX,
diseño visual y densidad, y jugador competitivo/analista de producto) más un prototipo interactivo para que lo revise el usuario.
Prototipo de navegación ACTUAL (14/11/2026): **`docs/rediseno/prototipo_v3.html`** (barra lateral que se expande, pantalla «En vivo» separada de la consulta, botones para simular cola, selección, partida y fin; incluye lo que existe hoy: sesión, gráfica de rango, «Tu año en LoL», avisos del rival y temporizadores). Antes: `docs/rediseno/prototipo_v1.html` (ábrelo en el navegador; botones «Simular» para recorrer cola, selección, carga, partida y fin).

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

---

## Ronda 2 (11/11/2026): temas de color, estilos y claves del campeón
Prototipo: `docs/rediseno/prototipo_v2.html` (selector de tema, estilo, claro/oscuro y campeón). Datos en `temas_color.json`, `estilos_ui.json` y `claves_campeon.json` (misma carpeta). Sigue sin implementarse nada.

### Temas de color (experto en color, contrastes WCAG calculados y daltonismo simulado)
- **Hallazgo clave:** los colores semánticos son FIJOS para todos los temas: positivo menta (#6FF0CC oscuro / #006A5D claro), negativo rojo-coral (#FF5C6C / #991B2F), aliado azul, rival naranja, aviso ámbar. Los acentos libres de verdad son violeta, cian, magenta y lima. Victoria y derrota llevan además signo ▲ ▼ (en claro, la protanopía no se arregla solo con color).
- **Recomendados (5-6 para Ajustes):** predeterminado (oro, con el modo en vivo pasando a coral porque el ámbar se confundía con el oro), **F1 Abisal** (azul noche, cian, violeta), **F4 Neón medianoche** (negro azulado, violeta, lima: la mejor separación consulta/en vivo), **F2 Brasa** (grafito cálido, cian, lima), **F3 Bosque** (verde profundo, lila, lima), **3c Cloud Dancer corregido** (el único crema cálido; el vivo pasa a violeta). 7c Galactic corregido, como séptimo, es el más débil con daltonismo.
- **Las 10 ideas del usuario:** 4 (Peach Fuzz), 5 (Forest/Jungle), 6 (Saffron/Cherry) y 9 (Tangerine/Acid lime) se descartan porque chocan con rival, positivo, aviso, Oro o bronce y no se arreglan sin cambiar su identidad; 1, 2, 3, 7, 8 y 10 funcionan solo cambiando el color del modo en vivo (detalles en `temas_color.json` y en las notas del prototipo).
- Aviso: los contrastes se midieron contra el fondo y las dos superficies de cada tema, no sobre imágenes ni gráficos. F1: el cian queda cerca del color de Aspirante (dE 11).

### Estilos de tarjeta (experto en UI; Tk no tiene desenfoque, ni sombras difusas, ni transparencia por widget)
- **Ofrecer: Plano (por defecto), Brutal y Cristal.** Orden de implementación: Plano (refactor de tokens), Brutal (el más fiel y barato: bordes de 2 px y sombra dura desplazada), Cristal (último: borde y filo claros, degradado cacheado en cabecera y fondo; se llama «aproximación», nunca se promete desenfoque).
- **Neumorfismo: fuera.** Contraste ≈1,1:1 (incumple WCAG 1.4.11) y exige sombras difusas dobles que Tk no hace.
- Tokens (radio, borde, sombra, relleno, separación) en `estilos_ui.json`. Brutal: sombra solo en las 6-10 tarjetas principales, no en filas ni chips. Medir antes el tiempo de reconstrucción (hoy ~2,5 s al cambiar de tema).

### Claves del campeón en la build (investigación con fuentes; sin implementar)
- Datos verificados (wiki oficial y Skill-Capped, parche 26.22): **Kai'Sa** evoluciona Q con 100 de AD de objetos, W con 100 de AP y E con 100 % de velocidad de ataque (los umbrales bajan a 56 y 70 % a nivel alto; la fuerza adaptativa no cuenta); orden habitual Q, luego E, luego W. **Kha'Zix**: cada rango de R da un punto de evolución; orden Q, luego R, luego situacional (W hacia el nivel 12). También **Nasus** y **Veigar** (acumulación permanente).
- **Sin verificar (no escribir como hechos):** los niveles exactos de evolución de Kha'Zix según la fuente, y las mecánicas de Viego, Sylas y Yone. Otros candidatos con fuente en la wiki: Sion, Cho'Gath, Senna, Smolder, Aurelion Sol, Zeri, Ornn.
- **Cómo hacerlo:** Data Dragon (es_ES) trae el texto oficial de cada evolución en los tooltips de Q/W/E de Kai'Sa («Evolucionada») y los umbrales máximos (effectBurn), así que se puede detectar y mostrar solo; los umbrales por nivel, el orden recomendado y los avisos necesitan una tabla curada a mano con fuente y parche (formato en `claves_campeon.json`).
- Idea extra: una barra de progreso hacia cada evolución con los objetos que llevas (necesitaría leer los objetos en vivo; sin verificar).

---

## Ronda 3 (11/11/2026): revisión de TODOS los campeones (claves de build)
Archivo: `docs/rediseno/claves_campeones.json` (**borrador**, no se usa todavía en la app). Se descargó de Data Dragon 16.22.1 (es_ES) la pasiva y las habilidades de los 173 campeones y 5 revisores automáticos (35 campeones cada uno) decidieron cuáles tienen mecánicas que cambian compras, subida de habilidades o patrón de juego, verificándolas en la wiki oficial.
- **Resultado:** 82 de 173 campeones con al menos una clave (112 avisos, 43 acumulaciones, 37 de objetos, 20 formas, 14 evoluciones, 7 de orden de habilidades). Entre ellos Kai'Sa, Kha'Zix, Aphelios, Aurelion Sol, Azir, Bard, Bel'Veth, Cho'Gath, Elise, Gnar, Jayce, Jhin, Kayn, Nasus, Nidalee, Ornn, Senna, Sion, Smolder, Sylas, Syndra, Udyr, Veigar, Viego, Viktor, Zeri y más (lista completa en el JSON).
- **Error detectado por el usuario y corregido:** un revisor puso que Cassiopeia «no puede comprar botas desde el 26.01». Es al revés: hasta el 25.x no podía; desde el 26.01 SÍ puede comprarlas. Comprobado con el texto de su pasiva en Data Dragon (15.24.1: «no puede comprar botas»; 16.1.1 y 16.22.1: solo «las bonificaciones a la velocidad de movimiento son más efectivas») y con la nota de la página Boots de la wiki. Su pasiva da entre un 5 y un 36 % más de efectividad a la velocidad de movimiento (desde el 26.18).
- **Limitaciones honestas:** solo se usó la wiki (no se abrió ninguna guía externa, así que NINGÚN orden de habilidades está contrastado); las páginas se leyeron parcialmente; el parche «26.22» es aproximado; 25 claves quedan marcadas `revisar: true` (afirman prohibiciones o cambios de parche) y hay discrepancias abiertas (Tahm Kench, Rumble, letras de Kalista, Tendencias violentas de Kled). Un cruce automático de cifras con Data Dragon no sirvió (sus textos no llevan los números).
- **Antes de usarlo en la app:** segunda verificación independiente (otra fuente distinta de la wiki, y diferencia entre versiones de Data Dragon para detectar cambios como el de Cassiopeia), revisar las 25 marcadas y una muestra del resto, y decidir qué tipos mostrar (propuesta: evoluciones, acumulaciones, formas y avisos de objetos; los avisos de detalle de habilidades, plegados).

---

## Ronda 4 (11/11/2026): segunda verificación independiente de los 173 campeones
`docs/rediseno/claves_campeones.json` pasa de borrador a **verificado en dos pasadas**. Cinco verificadores independientes volvieron a comprobar cada clave de la primera pasada con fuentes distintas de la wiki (notas oficiales de parche de Riot 26.x, Data Dragon, CommunityDragon, Meraki, riftpatchnotes y Lolalytics 16.22 Emerald+) y revisaron de nuevo los campeones que se habían descartado.
- **Resultado:** de 233 claves de la primera pasada, 107 confirmadas, 114 corregidas, 2 refutadas y 10 sin confirmar (estas 12 quedan en `no_mostrar`); 29 claves nuevas aportadas por un verificador. Quedan **250 claves mostrables en 95 campeones**, y órdenes de habilidades de 168 campeones (Lolalytics 16.22).
- **La primera pasada tenía muchos errores** (casi la mitad de las claves necesitó corrección). Ejemplos: Cassiopeia SÍ puede comprar botas desde el 26.01 (su pasiva, +5-36 % de efectividad de la velocidad de movimiento desde el 26.18); la Q de Aphelios gasta 10 de munición, no 1; Devorar de Tahm Kench es la R; la ejecución de la R de Garen es 125/200/275 más 25/30/35 % de la vida perdida (no un umbral del 20/23/26 %); Yone guarda el daño con la E, no con la R; los datos de Mel eran anteriores a su rework del 26.22; «Shyvana sin Destello en forma de dragón» no aparece en ninguna fuente (descartada).
- **Fuentes que fallaron:** U.GG, Metasrc y esports.gg dieron 403; las notas 26.1 a 26.3 dieron 404 con el patrón de URL usado; Meraki está desfasado (parches 14.x a 25.x) y no se usó para cifras actuales. Mobalytics, OP.GG, LeagueOfGraphs y Skill-Capped apenas se consultaron.
- **Avisos:** los cambios de Gangplank, Garen y Graves de las notas 26.17-26.22 son de League Classic, no de la Grieta; las cifras de Varus, Vayne y Zyra chocan entre fuentes y se omitieron. La verdad cambia con cada parche: hay que revisar el archivo cuando salga uno nuevo (la pasiva de Cassiopeia cambió dos veces en 2026).
- **Siguiente paso (si se implementa):** tabla en el programa con aviso de parche, mostrar evoluciones, acumulaciones, formas y avisos de objetos, y el orden de habilidades (que la app ya trae de Lolalytics en la build; no duplicar). Comparar el parche del archivo con el de Data Dragon al arrancar y avisar si está caducado.

---

## Ronda 5 (12/11/2026): temas, looks y Datos aparte (IMPLEMENTADO en la 1.22.0)
- **Dos ejes independientes:** el tema de color (paleta) y el estilo de las tarjetas (Plano, Brutal, Cristal) se combinan libremente; el estilo cambia esquinas, bordes y sombras en TODA la app mediante tokens (no solo en las tarjetas principales: el radio de cada widget se multiplica por el factor del estilo).
- **Looks:** Terminal, Papel, Blueprint, Hextech, Arcade, Neón Tokio y Océano traen su propia paleta (oscura y clara), tipografía, forma y estilo de título; ignoran el selector de estilo.
- **Auditorías:** contraste (todos los temas pasan 4,5:1 en texto y 4,4:1 en colores de estado, comprobado en las pruebas) y fidelidad de estilos. Correcciones aplicadas: colores de rango legibles en claro, bordes de estado con los colores del tema, victoria/derrota también por forma, Cristal más claro y con filo a todo el ancho, sombras sin muescas.
- **Datos fuera de las pestañas:** botón junto a Ajustes (4 pestañas: Asesor, Partida, Enfrentamiento, Historial).
- **Siguiente (no hecho):** la barra lateral completa del prototipo v2, texturas de fondo y degradados cacheados con PIL, bordes en chips y selectores para Brutal.
