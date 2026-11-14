# LOL-E · Punto de partida para cualquier conversación nueva

Última actualización: 13/11/2026 (versión del código: 1.22.17). Este archivo es corto a propósito: dice dónde estamos, las reglas
y cómo seguir. El detalle va en `docs/HISTORIAL_DE_SESIONES.md` y el rumbo en `docs/PLAN_DE_FUTURO.md`.

## 0. Cómo arrancar (2 minutos)

1. Lee este archivo entero.
2. Ejecuta `python herramientas/estado.py --pruebas`: dice qué está publicado y qué no (commits desde la última publicación), si git
   está limpio, si hay partida o cliente abierto, qué versión corre en el PC del usuario y si los documentos están al día.
3. Solo si hay que decidir rumbo: `docs/PLAN_DE_FUTURO.md`. Para el porqué de algo antiguo: `docs/HISTORIAL_DE_SESIONES.md`.
4. **Antes de acabar la conversación**: actualiza la sección 2 («Estado») y añade una línea al «Registro de actualizaciones» del
   final. Una prueba (`Documentacion` en `tests_unitarios.py`) falla si este archivo no menciona la versión del código o si hay una
   herramienta de `herramientas/` que no está en la tabla de la sección 6.

## 1. Qué es

App de Windows (Python 3.12 + CustomTkinter) que lee el cliente de League of Legends para aconsejar en la selección de campeón,
mostrar build y jugadores de la partida (y, en directo, marcador y objetos), y guardar historial, repertorio y análisis. Interfaz en
español. Repositorio público `adanprietobenegas/LOL-E`, rama `main`. Pestañas: Asesor · Partida · Enfrentamiento · Repertorio ·
Historial (+ Datos y Ajustes en la cabecera). No usa claves de Riot: lee el cliente local y datos públicos (Data Dragon, Lolalytics, op.gg).

## 2. Estado (actualizar al terminar cada conversación)

**Publicado en GitHub: 1.22.17** (14/11/2026; la 1.22.16 fue la anterior).

**En `main` sin publicar** (candidata a 1.22.18):
- **Tu sesión y tu forma** (`sesion.py`, `ui_history.session_lines`; propuesta del experto coach): en el resumen del Historial, si llevas 2+ derrotas seguidas lo dice con TU dato (victorias tras 2+ derrotas frente a normales, solo con 8+ partidas y diferencia ≥ 8 puntos) y tu mejor franja horaria (diferencia ≥ 12 puntos). Sin conclusiones con muestras pequeñas. Pendiente de la misma idea: banner en el lobby/selección.
- **Registro de PL**: `diag.log` apunta ahora «Variación de PL (cola): +x PL, ahora …» o «no se pudo calcular (antes…, después…)» para cazar por qué falta el PL de algunas partidas reales (sin confirmar la causa).
- **Menos coste para el juego** (aviso de un compañero: tirones de fps aparentes; al usuario no le pasa): medido con el cliente falso, LOL-E gasta ~0 % de CPU en reposo y en partida (picos cortos de 15-45 % de un núcleo solo al cambiar de fase/pintar; 74-89 MB, 8-11 hilos). La causa NO está confirmada (puede ser otra cosa del PC). Medidas baratas: `gui.lower_priority` (prioridad «por debajo de lo normal» con `SetPriorityClass` y tipos explícitos; sin ellos fallaba en silencio), y con la ventana minimizada o oculta el bloque en vivo no se repinta (`GUI.hidden`, `on_map` pinta al volver). Ya estaba bien: la actualización automática espera a que no haya cola/selección/partida; la ventana solo es «siempre visible» en la selección por defecto (con «siempre» y el juego en pantalla sin bordes puede forzar la composición de Windows: preguntar al compañero qué ajuste usa y si tapa el juego). Si vuelve a pasar: pedir el registro y la hora exacta del tirón para cruzarlo con `diag.log`.
- Ideas de los expertos aún sin hacer: patrones repetidos entre partidas y objetivo por partida (coach), temporizadores de objetivos (plan 1.3), alerta de picos del rival, mapa de muertes; de diseño: compactar el resumen del Historial en estrecho, ficha «Racha» sola, controles de Selección en una barra, pie de op.gg más tenue.


**Incluido en la 1.22.17** (publicada): Historial: el resultado se ve sin mirar al chip de la derecha (franja gruesa a la izquierda y aro de color en la foto, fondo liso; `ui_history.row`). La actualización automática funciona (el usuario pasó solo de 1.22.5 a 1.22.9).

**Incluido en la 1.22.11** (publicada; `python herramientas/estado.py` muestra si hay algo nuevo sin publicar):
- **Pestaña Repertorio propia**, entre Enfrentamiento e Historial (antes estaba escondida en la tarjeta de logros del inicio). Ctrl+1…6;
  el Historial pasa de Ctrl+4 a Ctrl+5.
- **Corrección de un interbloqueo real de la ventana**: un finalizador de Tkinter ejecutado por el recolector de basura desde otro
  hilo dejaba la ventana congelada para siempre. Ahora el recolector solo corre en el hilo principal (`GUI.gc_tick`).
- **Partida en vivo** (`live.py`, `ui_live.py`, `augments.fetch_live`): en «Partida», durante la partida, marcador, objetivos y los 10
  jugadores con nivel, bajas, farmeo, objetos y oro en objetos, más una lectura de los objetos rivales (tipo de daño y defensas).
  Se repinta solo ese bloque cada ~10 s. Interruptor en Ajustes (`live_enabled`). **Probado con datos inventados y con el bucle contra el
  cliente simulado; NO visto aún con una partida real** (los nombres de los eventos de dragón/barón/heraldo y quién los mata son según la
  documentación de la API; las muestras reales que tenía el usuario eran de Mayhem y no los traen).

- **«Siguiente objeto de tu build» en el bloque en vivo** (`shopping.py`, `ui_live.buy_hint`): con tu oro y lo que llevas, cuál es el siguiente objeto de tu
  build de la web y cuánto te falta restando los componentes que ya tienes (recetas de Data Dragon: `items.py` pasa al esquema 4 y añade `from`; sin red conserva el
  esquema anterior y esta frase no sale). Probado con la build real de Lolalytics y el catálogo real; solo con datos en vivo inventados.
- **El pie de la ventana** ya no se queda en «Conectado. Cargando tus datos…» una vez cargados los datos.
- **Corrección del cierre de partidas tras ESQUIVAR** (hallazgo de un escenario nuevo del cliente simulado): al acabar una selección sin que
  empezara partida, el motor daba por terminada la partida ANTERIOR (decía «Partida terminada», la reanalizaba, esperaba hasta 8 veces si
  el rango no se había movido y guardaba «0 PL» para ella, pudiendo pisar su variación real). Ahora `played` distingue esquivar de jugar, el
  motor espera si la fase sigue en «ChampSelect» y `analysis.save_lp` no sustituye una variación real por un 0.
- **Tu partida frente a tu media** (`analysis.vs_average`, `average_lines`): bajo el titular del análisis, tu KDA y farmeo frente a tu media con ese
  campeón (o en el modo si hay menos de 3 partidas); marca bueno/malo solo si se aleja un 25 %.
- **Tu rival directo en el bloque en vivo** (`live.duel`, `duel_line`): nivel, objetos y marcador frente a él, con «va por delante» solo si la
  diferencia es clara (≥ 15 % y ≥ 500 de oro).
- **Pruebas del bucle ampliadas** con el cliente simulado: esquivar, caída del cliente a mitad de selección, ARAM y Arena, reconexión, cuenta
  desconocida que luego aparece (el reloj del test avanza ~40 s por paso), y las sesiones raras que antes comprobaba `test_modes.py` (que
  necesitaba el cliente real). Construcción diferida de los controles de filtros (ahorra ~30 ms por repintado de la selección, medido a/b).

**Incluido en la 1.22.12** (publicada):
- **Fuentes externas más robustas**: si Lolalytics no responde, la build y el meta usan lo último guardado y lo dicen («No se pudo actualizar ahora…»); si la página cambió de formato, el mensaje lo explica en vez de decir que no hay build. Lo mismo para las builds de op.gg y las tendencias. Además: el meta rechaza tasas de victoria fuera de escala y el puesto de op.gg no se borra si la página lo pierde. Pruebas con red simulada (`BuildSinRed`, `MetaSinRed`, `MetaFormato`, `Op_ggSinRed`, `PuestoOpgg`).
- **«Qué aprender» en Repertorio** (`learn.py`): si una línea que juegas mucho depende de un solo campeón, propone un segundo de los que tienes con buena tasa en el parche. Solo sale con 8+ partidas en la línea; probado con datos de ejemplo (captura 18).
- **Ficha «Tus PL guardados»** en Rango y logros del inicio: línea de PL acumulados por partida clasificatoria (`analysis.lp_series` sobre `lp.json`); solo se ve con 3+ partidas con dato. Probado con una serie de ejemplo (captura 17b).

**Incluido en la 1.22.13** (publicada):
- **Remake en el bucle** (`history.is_remake`, escenario `remake` del cliente simulado): al acabar una partida anulada no se espera hasta 64 s a un cambio de PL que no llegará ni se guarda una variación de 0.
- **Tu partida frente a tu media, con daño y visión por minuto** (`analysis.vs_average`: `dpm`, `vpm`; la visión solo en la Grieta).
- **Revisión del código** (`code-review` alto sobre lo acumulado tras la 1.22.12): corregidos 9 hallazgos. La reserva sin red solo se usa si encaja (misma región en tendencias, mismo rango en el meta); una build obsoleta se reintenta cada 5 min; la marca «últimos datos guardados» se ve en la build de ARAM y en las botas de op.gg (las tendencias obsoletas no avisan en pantalla); las medias por minuto cuentan los ceros reales.
- **Aviso sonoro al poder comprar** el siguiente objeto de tu build (`GUI.buy_alert`, ajuste `buy_alert`, una vez por objeto; usa «Avisos sonoros»). Nota del botón de diagnóstico con la guía de qué enviar.
- **Objeto contra los rivales** en el bloque en vivo (`shopping.counter_item`, `ui_live.counter_hint`): un solo objeto de tu cantera (penetración si acumulan defensa; si no, armadura o RM contra su daño dominante). Solo datos en vivo inventados; captura 10d.
- **Informe de diagnóstico más completo** (`health_lines` y los ajustes relevantes en `copy_diagnostics`): esquema de datos, partidas de la Grieta con línea de regla antigua o sin línea, PL guardados, edad del meta y de las builds.

**Incluido en la 1.22.14** (publicada), hallado con una partida real el 14/11/2026:
**En `main` sin publicar** (candidata a 1.22.16):
- **Rango estimado hacia atrás** (`lpseries.estimate`, `ui_lp`): las partidas sin PL guardado se estiman con las medianas propias de PL por victoria/derrota, ancladas en los puntos reales y las fotos de op.gg; a trazos, interruptor «Solo reales». Fuentes revisadas: LCU solo rango actual, op.gg ~10 días (se acumulan), League of Graphs bloqueado; no se probaron endpoints no documentados de op.gg.

**Incluido en la 1.22.15** (publicada):
- **Gráfica de rango: el tramo no cambiaba nada** (aviso del usuario con su historial real: solo 6 puntos de Solo/Dúo, todos entre el 09 y el 11/11, así que 7, 30, 90 días, año y todo contenían lo mismo). Ahora el eje es el tramo elegido aunque el historial sea más corto, y una nota dice desde cuándo hay datos guardados. Idea pendiente: reconstruir hacia atrás una estimación de PL con las victorias y derrotas del historial (225 partidas) marcada como estimada; no se ha hecho por la imprecisión (LP por partida varía ~14 a 26).

- **Gráfica «Tu rango en el tiempo»** (`lpseries.py` + `ui_lp.py`; sustituye a la ficha «Tus PL guardados» y a `analysis.lp_series`): visible siempre en Inicio › Rango y logros, con eje de fechas, rango real (divisiones marcadas), filtros 20 partidas / 7 / 30 / 90 días / este año / todo, cola Solo-Dúo o Flexible, y al pasar el ratón un cuadro con el icono del campeón, resultado y PL de la partida (no se dibujan iconos por partida: no cabrían). Dos fuentes: `lp.json` (partidas vistas por LOL-E) y las FOTOS DIARIAS de rango del perfil de op.gg (`lpHistories`, solo trae ~10 jornadas; `save_lp_snapshots` las acumula en `opgg_lp.json` cada vez que se actualiza op.gg). Líneas de referencia del cliente (pico de la temporada y fin de la anterior) si caen dentro del tramo. **Rango de todas las temporadas: no hay fuente viable** (League of Graphs está tras Cloudflare y se apunta solo mientras sigue la cuenta; el cliente solo da la temporada actual y la anterior; op.gg ~10 jornadas; la API de Riot no tiene historial de PL). Pendiente de ver con datos reales; el formato de la etiqueta de división de op.gg en rangos no apex (`label`) no se ha visto (solo Maestro+ en la muestra pública).
- **Rediseño del «en vivo»** (opinión del usuario tras su partida real: recargaba mucho, era largo y tapaba la build y las runas): `ui_live.LiveView` se construye UNA vez y `update()` solo cambia lo que cambió (sin repintar); tira compacta arriba (reloj, barras de bajas y de oro en objetos, objetivos con color de quién va por delante, siguiente compra, objeto contra rivales, rival directo) y los diez jugadores en un pliegue («Los 10 jugadores en directo», emparejados por línea en ancho, apilados en estrecho), colocado DEBAJO de la build y las runas. Orden de la pestaña Plan: tira, campeón y rival, build/runas, pliegue de jugadores, tablero, claves, duelo, guía.
- **Runas con opciones**: `builds.parse_rune_pages` / `fetch_rune_pages` (endpoint `ep=rune` de Lolalytics): «Más usada» y «Mayor % de victorias» con su % de victorias, uso y partidas; selector en la fila Runas.
- **Pantalla en blanco al acabar la partida** (vista en la partida real del 14/11): al terminar, la pestaña pasa sola a «Análisis» y, si estabas desplazado abajo en el bloque en vivo, el desplazamiento quedaba fuera del contenido. `GameView.refresh` vuelve arriba al cambiar de pestaña o de partida (captura `10e_fin_con_scroll`).
- **Variación de PL no guardada** en esa partida (`lp.json` sin entrada nueva; «esperas 0»): `rank_before` salía vacío. Ahora el rango previo se lee al encontrar partida (`rank_snapshot`, se reintenta en cada fase hasta empezar) y el registro dice «Rango antes de la partida…» o «Sin el rango de antes…». **Causa exacta no confirmada**: mirar el `diag.log` de la próxima partida clasificatoria.
- **Torres e inhibidores contaban 0 en partidas reales**: el código real es `Turret_TOrder_…` / `Inhib_TChaos_…` y `live._side` esperaba `_T1_/_T2_`. Corregido (acepta ambos formatos), con la muestra real: 3 y 7 torres, 2 inhibidores. Los eventos `DragonKill`, `HeraldKill` y `BaronKill` SÍ eran correctos (nombre y equipo por `KillerName`); además existe `HordeKill` (larvas del vacío), ahora se cuenta («Larvas»).

***Pendiente de ver en la realidad*** (no se puede cerrar sin el usuario o sin otra partida):
1. La instalación del usuario corría la 1.22.9 el 13/11 a las 17:59: basta con cerrar y abrir LOL-E fuera de cola para pasar a la
   1.22.10. Después, en su `diag.log` debe aparecer «Partidas antiguas recalculadas con su detalle…», y su Historial/Repertorio no deben
   tener toplanes como jungla.
2. La selección de campeón y «Partida» (incluido el bloque en vivo) en pantalla durante una partida real. Capturar la ventana del usuario
   con `PrintWindow` (la captura normal sale con lo que tape la ventana).
3. El compañero a quien «no le salen» los jugadores de la partida: sin reproducir. Pedirle el informe de diagnóstico (Ajustes).
4. Decisiones del usuario: espaciado único de la interfaz, y el rendimiento del pintado (pide menos elementos por pantalla).

**Borrador de las notas de la 1.22.11** (pegar en `novedades.py` y `NOTAS_DE_VERSION.txt` al subir la versión):
- nuevo: «La pestaña Repertorio tiene ya su propio sitio en la barra, entre Enfrentamiento e Historial (antes estaba al final de la
  pantalla de inicio). Atajos: Ctrl+1…6.»
- nuevo: «En directo, en Partida: marcador, torres, dragones y heraldos, y los cinco rivales con su nivel, bajas, farmeo, objetos y oro en
  objetos, con una lectura de qué daño llevan y cuánta defensa acumulan. Se puede desactivar en Ajustes.»
- nuevo: «En el bloque en vivo, tu siguiente objeto de la build con lo que te falta de oro (restando los componentes que ya llevas) y cómo vas frente a tu rival directo.»
- nuevo: «Al terminar la partida, tu KDA y tu farmeo frente a tu media con ese campeón.»
- arreglo: «Si esquivabas una partida, LOL-E daba por terminada la anterior (la reanalizaba, esperaba y podía borrar su variación de PL). Ya no.»
- arreglo: «Corregido un fallo raro que podía dejar la ventana congelada para siempre (un objeto de la interfaz se destruía desde otro
  hilo mientras la ventana esperaba a ese hilo).»

## 3. Reglas del usuario

- **Preguntar antes de publicar una versión** (`gh release create`; el modo automático lo bloquea hasta que el usuario lo confirma en el
  chat). Subir commits a `main` no necesita permiso. Una autorización vale para esa versión, no para las siguientes.
- No construir (`build_release.py`) ni subir instaladores con partida en curso (`tasklist | grep -i "League of Legends.exe"`); durante
  una partida, no tocar el PC del usuario salvo lectura. La actualización automática instala en el «Lobby» y reinicia LOL-E: publicar
  cuando el usuario no vaya a entrar en cola.
- Ser honesto con lo no probado en una partida real (decirlo en las notas de la publicación, `publicar.py --sin-probar` lo exige).
- El rediseño completo de navegación (`docs/rediseno/prototipo_v2.html`) no se implementa hasta que el usuario lo revise. Se han hecho
  cambios puntuales que él pidió (Repertorio con pestaña).
- Ventanas de prueba en el monitor secundario (posición -1366,209).
- Cuando el usuario dice «hazlo como creas / ten buen criterio»: decidir y explicar, sin preguntar lo convencional. Responder en español.
- **No copiar datos de la carpeta de datos del usuario (`%LOCALAPPDATA%\LOL-E`) al repositorio, que es público**, aunque estén «limpios»:
  el sistema lo bloquea. Si hace falta una muestra, inventarla con la estructura real (ver `cliente_falso.live_sample()`).

## 4. Cómo trabajar

- **Sin subagentes en paralelo** (siete a la vez agotaron el límite de 5 horas en dos minutos). Trabajar en línea, por orden.
- Archivos grandes (`ui_sections.py`, `lol_advisor.py`, `gui.py`, `ui_views.py`) se leen por fragmentos (Grep, Read con `offset`/`limit`).
- La carpeta `%LOCALAPPDATA%\LOL-E` que ve la sesión mezcla copias antiguas (el sistema la virtualiza): sirve el `diag.log` (archivo nuevo)
  pero no `history.json`, `config.json`… antiguos. Probar con `cache/` del proyecto o con `prueba_cliente_real.py`.
- Para ediciones con acentos y comillas, escribir un script `.py` en el scratchpad y ejecutarlo. **Cuidado: en un script lanzado desde la
  línea de órdenes, `\\n` llega como un salto de línea real; usa la herramienta de edición para esas cadenas.** Los archivos del proyecto
  usan CRLF: leer y escribir con `newline=""`.
- Un cambio de interfaz se comprueba con `capturas.py` (mirar la imagen) y se cierra con `comprobar_todo.py`: las pruebas unitarias no pintan nada.
- Ante un cuelgue de Tk, volcar las pilas: `LOLE_VIGILA=200` en `capturas.py` (`faulthandler`) mostró el interbloqueo del recolector.
- Un comando encadenado con `&&` sigue aunque unas pruebas fallen si usas `grep` sobre su salida: comprueba el resultado antes de hacer commit.

## 5. Publicar una versión

1. Subir `APP_VERSION` en `lol_advisor.py`, entrada arriba en `novedades.py` y en `docs/NOTAS_DE_VERSION.txt`; actualizar este archivo. Commit y push.
2. `python herramientas/publicar.py --sin-probar "lo que NO se ha probado"`: comprueba partida, git limpio y subido, versión coherente,
   pasa `comprobar_todo.py` (~10 min), construye, verifica instalador y huella SHA-256, escribe `release/notas_X.Y.Z.md` desde `novedades.py`
   y muestra el comando `gh release create ...`. No publica.
3. Con el sí del usuario en el chat, lanzar ese comando.
4. `python herramientas/publicar.py --verificar`: espera a que el actualizador vea la versión nueva (GitHub tarda a veces un minuto).
5. Marcar la versión como publicada en la sección 2.

## 6. Herramientas (carpeta `herramientas/`)

| Herramienta | Para qué |
|---|---|
| `estado.py` | Foto del estado real (versión, qué está sin publicar, git, cliente, instalación del usuario, documentos). `--pruebas` |
| `comprobar_todo.py` | **Antes de publicar** (~10 min, sin cliente): pruebas + recorrido de TODAS las pantallas a 560 y 1340 px + la app entera contra el cliente falso |
| `publicar.py` | Prepara una publicación de principio a fin (sección 5); no publica por sí solo. `--verificar`, `--ensayo` |
| `tests_unitarios.py` | Pruebas sin ventana ni cliente (incluye el bucle principal contra el cliente falso y la regla de líneas) |
| `capturas.py [ancho] [alto] [carpeta]` | Capturas de todas las pantallas sin cliente; `LOLE_SOLO`, `LOLE_PAGINAS`, `LOLE_CONF`, `LOLE_PERFIL`, `LOLE_SINFOTO`, `LOLE_VIGILA` |
| `cliente_falso.py` | Cliente de LoL de mentira con guion por pasos y datos inventados con la estructura real (`live_sample()`) |
| `demo_falso.py` | La app entera (ventana + bucle) contra el cliente falso, con una captura por fase; `LOLE_RIVAL=1` |
| `prueba_cliente_real.py` | Con LoL abierto y en reposo: lectura de solo lectura contra el cliente REAL (cuenta, historial, migración, líneas, perfil) |
| `validar_lineas.py [n]` | Con el cliente abierto: cruza etiqueta de línea, Aplastar y objeto de rol en n partidas (valida `history.role_of`) |
| `tiempos.py [ancho] [texto]` | Mide y perfila el pintado de cada pantalla y el coste del recolector |
| `generar_claves.py` | Genera `assets/claves.json` (claves de los campeones) desde `docs/rediseno/claves_campeones.json` |
| `demo_live.py`, `shots2.py`, `test_modes.py` | Antiguas: capturas y demo que necesitan el cliente REAL abierto y compañeros inventados; sustituidas por `capturas.py` y `demo_falso.py`, que no lo necesitan |

## 7. Lo que se sabe del cliente de LoL y del entorno (costó descubrirlo)

- **La etiqueta de línea del cliente (`timeline.lane`) falla mucho**: en 60 equipos reales solo 14 tenían los cinco puestos distintos.
  Regla propia en `history.role_of` / `team_roles` (objeto de rol `stats.roleBoundItem`: 1220/1221 top, 1209 jungla, 1206 mid, 1208/2055 apoyo,
  botas 3006/3008/3009/3020/3047/3158 el tirador; Aplastar = jungla): 55 de 60 equipos completos. Son valores observados, no de Riot.
- El cliente entrega a veces solo 20 partidas aunque se pidan 200; el detalle por identificador (`/lol-match-history/v1/games/{id}`) sí sirve partidas antiguas.
- Tras abrir el cliente, algunas lecturas llegan vacías un rato (p. ej. los campeones en propiedad): se reintenta.
- **Certificados de internet**: en algunos Windows Python falla con `CERTIFICATE_VERIFY_FAILED` por una raíz que Windows aún no tiene (visto con op.gg y GitHub).
  `lol_advisor.install_certs()` suma los de `certifi`; el actualizador tiene además `curl.exe` de reserva. El contexto sin verificar certificado solo se usa para 127.0.0.1.
- **API local de la partida** (`https://127.0.0.1:2999/liveclientdata/allgamedata`, solo existe en partida): por jugador `championName`, `rawChampionName`
  (clave del icono), `team` ORDER/CHAOS, `level`, `scores`, `isDead`, `respawnTimer`, `items` (con `itemID`, `price`, `count`, `slot`, `consumable`) y `position`
  (`NONE` en Mayhem); `activePlayer.currentGold`; `events.Events` (ChampionKill, TurretKilled, InhibKilled, …). Único acceso: `augments.fetch_live`.
- El historial se guarda por cuenta (`history_<puuid>.json`); los antiguos sin dueño se copian a la primera cuenta que los reconoce. `cache/schema.json` versiona los datos.
- **Tkinter y hilos**: no llamar a Tk desde otro hilo, ni dejar que el recolector de basura destruya objetos de Tk fuera del hilo principal (interbloqueo).
  En `ui_build.render()` el nombre `core` es una lista local, no el módulo: usar funciones de módulo (`current_patch()`).
- `cache/diag.log` (conexión, cuenta, fases, lecturas, migraciones) y `cache/error.log` son lo primero que pedir a quien diga que «no le sale» algo:
  Ajustes › «Copiar informe de diagnóstico». La instalación del usuario es `%LOCALAPPDATA%\Programs\LOL-E`; sus datos, `%LOCALAPPDATA%\LOL-E`.

## 8. Siguiente trabajo

Ver `docs/PLAN_DE_FUTURO.md` (prioridades, esfuerzo y dependencias). Lo inmediato es: ver el bloque en
vivo en una partida real, y las decisiones pendientes del usuario de la sección 2.

## 9. Registro de actualizaciones de este documento

- 13/11/2026 (noche, 3): «Siguiente objeto» en vivo (`shopping.py`), pie sin «Cargando…», demo ARAM en `comprobar_todo`.
- 13/11/2026 (noche, 2): partida en vivo ampliada (rival directo), comparación con tu media, corrección del cierre tras esquivar, escenarios del bucle; plan y
  estado al día.
- 13/11/2026 (noche): reorganizado en capas (este archivo + `PLAN_DE_FUTURO.md` + `HISTORIAL_DE_SESIONES.md` + `herramientas/estado.py`); añadidas pruebas de
  frescura de documentos. Estado: 1.22.15 publicada.
- 13/11/2026 (tarde): 1.22.5 a 1.22.10 publicadas (actualizador, certificados, regla de líneas v2, recálculo de partidas antiguas). Ver el historial.
- 12/11/2026: auditoría visual, textos, etapa 1 (historial por cuenta, diagnóstico, cliente falso), rendimiento. Ver el historial.
