# LOL-E · Historial de las sesiones del 12 y 13/11/2026

Detalle de lo hecho y lo medido, por si hace falta. Lo que importa para seguir está en `CONTINUAR.md`.

## Auditoría visual (12/11/2026)

Capturas sin cliente de LoL: `python herramientas/capturas.py [ancho] [alto] [carpeta]` (monitor secundario; salen en
`herramientas/salida/`). Usa `cache/` y jugadores inventados; `LOLE_SOLO=10,13` limita a esas pantallas.

Corregido (publicado en la 1.22.2):
- Escala tipográfica única de 5 tamaños (10, 12, 14, 17, 22) en `ui_kit.py` (`TYPE`, `tsize`): `font()` y `tkf()`
  ajustan cualquier tamaño pedido al escalón más cercano. Antes había 13 tamaños distintos.
- Inicio: sin cliente, el título es «Abre League of Legends» y la pista va debajo (antes se montaba sobre el título).
- Textos cortados: «afinidad» en la vista Lista, nota de «Enviar al cliente», botón de build del rival, notas de
  Ajustes, «Clasificatorias de 5» en Historial; el rango de un jugador desaparecía si tenía varias etiquetas.
- Partida en ventana estrecha: con plan, primero tu campeón, rival y build; los 10 jugadores van al final (en ancho
  sigue el tablero plegable arriba).
- Selección: los filtros van plegados tras un botón «Filtros» con el resumen de lo activo al lado (se recuerda si
  los dejas abiertos, `folds.rec_filters`).
- «pestaña Datos» → «Datos (botón de arriba)»; «porcentaje» → «% de victorias» en el resumen de la recomendación.

Propuestas de estructura, aplicadas el 12/11/2026 con criterio propio (el usuario dio vía libre):
- Selección: las miniaturas de las otras opciones van justo bajo la imagen, antes de las pestañas.
- Selección › Resumen: fuera la cifra de afinidad repetida (queda en el anillo y la miniatura) y la etiqueta «2/3 victorias».
- ARAM: la imagen dice «Tu campeón actual» o «Mejor del banquillo para ti»; afinidad 0 (sin datos) se enseña como «—».
- Historial estrecho: «Campeones más jugados y modos» plegado tras un enlace (`folds.hist_more`); las partidas empiezan
  en la primera pantalla. En ancho no cambia.

Sin hacer:
- Escala de espaciado: definida (`SPACE` en `ui_kit.py`) pero el código existente usa 17 valores y no está migrado.

### Segunda pasada (12/11/2026): lo que faltaba por capturar

Revisado también: análisis de una partida guardada, subpestañas del inicio (Modos, Repertorio), «Contra rival»,
«Datos» desplegado, Ajustes entero, tema claro, interfaz al 130 %, modo compacto, looks Terminal y Papel, y 470 px.
Variantes: `LOLE_CONF='{"theme":"light","scale":1.3,"compact":true,"color_theme":"Terminal","style":"Brutal"}'`.

Corregido:
- Cabecera al 115–130 % o en ventana muy estrecha: «Conectado a LoL» salía cortado. Ahora se acorta a «Conectado» /
  «Sin cliente» y, por debajo de 460 px lógicos, queda solo el punto de color.
- «Restablecer filtros» cortado en estrecho → «Quitar filtros».
- Análisis: la quinta ficha de cifras («mitigaste…») se cortaba en estrecho.

Visto y sin defectos: tema claro, compacto, Terminal, Papel, Datos, Ajustes, Modos y Repertorio.

Pendiente de esta pasada:
- «Contra rival» sin datos repite dos frases que dicen lo mismo (es del punto 2, textos).
- Al 130 % en 560 px el deslizador de volumen queda reducido a su botón; funciona, pero es poco usable.

### Tercera pasada (12/11/2026)

Revisado: «Perfil completo» de un jugador (`LOLE_PERFIL=1`), Variantes y Situaciones de la build, Arena y Mayhem en
selección, ventana ancha con tema claro y con Terminal, análisis y build en ancho, y la escala 115 %.

Corregido:
- Build › Variantes: «Mayor % de victorias» se montaba sobre los iconos → «Más victorias»; en estrecho la tercera
  alternativa de cada objeto salía cortada (ahora se enseñan dos).
- Build › Situaciones: «1 tanques» → «1 tanque».
- Tablero ancho de jugadores: «Leyendo perfiles… 0 de 10» aunque ya hubiera perfiles leídos; ahora cuenta los que hay.

Sin defectos: perfil completo, Arena, Mayhem, claro y Terminal en ancho, 115 %, análisis en ancho.
Con esto la auditoría visual queda cerrada salvo las propuestas de estructura de arriba (decisión del usuario).
Nota de la herramienta: los pasos se ejecutan todos aunque `LOLE_SOLO` limite las capturas; en ancho «no encuentro el
botón Variantes» es esperado (ahí la build se ve en columnas, sin pestañas).

## Etapa 1 · Confianza en los datos (12/11/2026, publicada en la 1.22.4)

Hecho:
- Historial por cuenta: `history_<puuid>.json` y `games_<puuid>.json` (`history.hpath/gpath`, `history.ACCOUNT`).
  Los antiguos `history.json`/`games.json` se COPIAN (no se borran) a la primera cuenta cuyas partidas del cliente ya
  estén en ellos; queda anotado en `history_owner.json`. Otra cuenta empieza vacía. `account.json` recuerda la última
  cuenta para abrir sin cliente. Sin puuid no se guarda nada (antes iba al archivo común).
- Registro de diagnóstico `cache/diag.log` (`core.diag`): conexión, cuenta (8 caracteres), fases, selección, fin de
  partida, lecturas del historial y fallos del bucle. Se parte a ~400 KB. Sus últimas 30 líneas van en «Copiar informe
  de diagnóstico».
- Colas desconocidas: se apuntan una vez en el registro (`note_queue`).
- Cliente falso (`herramientas/cliente_falso.py`) y pruebas del bucle principal: cola → selección → partida → fin,
  arranque sin cuenta y dos cuentas en la misma carpeta. Las respuestas son inventadas con la forma del cliente
  real, no grabaciones.

Hecho después (13/11/2026, publicado en la 1.22.6):
- Los `except Exception: pass` de las lecturas del cliente en `lol_advisor.py` (11) y `players.py` (6) llaman ahora a
  `soft_fail(dónde)`: si el cliente no respondió, una línea en `diag.log`; si es un fallo del programa, la traza en
  `error.log`. Se dejaron tal cual los 7 que protegen al propio registro, la ventana única y la consola.
- Versión de los datos: `cache/schema.json` (`SCHEMA`, `MIGRATIONS`, `check_schema()` al arrancar). Es una versión de
  la carpeta entera, no un campo dentro de cada archivo: así una versión antigua de la app puede seguir leyéndolos.
- Cada arranque deja una línea «--- LOL-E x.y.z arranca ---» en `diag.log`.

Sin hacer de la etapa 1:
- (Descartado) Separar por cuenta los análisis guardados: van por identificador de partida, el historial ya es por
  cuenta y dos cuentas del mismo PC no pueden estar en la misma partida, así que no se pueden mezclar.
- El cliente falso usa respuestas inventadas; faltaría grabar las de una partida real.

Sin probar: la migración en la app instalada del usuario y el flujo con el cliente real. Antes de publicarlo conviene
que el usuario lo sepa: es la primera versión que cambia dónde se guarda su historial.

## Jugadores de la partida y punto 4 (12/11/2026, publicado en la 1.22.5)

Aclarado por el usuario: «la parte del profesor» es la sección tipo Porofessor, es decir, los perfiles de los 10
jugadores en la pestaña «Partida» (no el Asesor). Dos casos reales:
- En una partida suya (Flexible) faltaba un rival, el que llevaba Lee Sin. Causa probable, no confirmada con los datos
  de esa partida (el cliente ya no los daba al revisarlo): el tablero ancho repartía por línea en un diccionario y dos
  jugadores con la misma línea se pisaban. Arreglado con `ui_vs.lane_slots`: nadie se queda fuera.
- A un compañero «no le sale». Sin reproducir. Causas posibles que ya quedan cubiertas: jugaba ARAM u otro modo (ahí
  no se enseñaban jugadores: ahora salen en lista en todos los modos); o no los encontró, porque desde la 1.22.2 en
  ventana estrecha van al final (ahora hay un enlace «Ver los jugadores de la partida» que baja hasta ellos).
  Si sigue sin salirle, pedir su informe de diagnóstico: la línea «Jugadores de la partida …» dice cuántos se leyeron,
  cuántos con perfil oculto, sin campeón o sin línea, y si la cuenta era desconocida.

Punto 4:
- Etiquetas del tablero: «Primera vez con este campeón» solo si se leyeron sus maestrías y tiene 0 puntos (antes salía
  también cuando el cliente no daba la lista); «Le va bien/mal con él: 4V 1D» con 4 o más partidas recientes con ese
  campeón; «4 derrotas seguidas» en vez de «Racha -4»; «Juntos 3V 2D» en vez de «Juntos 5p · 3V».
- Análisis: una frase con la conclusión bajo la cabecera (`analysis.headline`), hecha con los mismos datos que los
  consejos.

Sin probar en una partida real.

## Rendimiento del pintado (12/11/2026, publicado en la 1.22.6)

Medir: `python herramientas/tiempos.py [ancho] [texto]` (mediana de 5 repintados por pantalla; con un texto, saca el
perfil de las acciones cuyo nombre lo contiene). Ventana de 560 px, sin partida en curso, en el PC del usuario:

| Acción | Antes | Después |
|---|---|---|
| Selección: repintar entera | 1360 ms | 1000 ms |
| Partida: repintar el plan | 1764 ms | 1316 ms |
| Partida: repintar el análisis | 1793 ms | 967 ms |
| Enfrentamiento: repintar con rival | 1836 ms | 1336 ms |
| Inicio, Historial, Datos, Ajustes | 60–420 ms | sin cambio apreciable |

Qué se quitó: recálculos completos de la ventana (`update_idletasks`) que no hacían falta.
- `Kit.reveal`: las secciones plegables que ya nacen abiertas no se animan ni miden su alto.
- `ui_kit.QuietMenu` y `calm()`: los menús desplegables y la barra de desplazamiento de CustomTkinter llamaban a
  `update_idletasks` en cada dibujo.

Lo que queda es el coste real de crear cientos de widgets de CustomTkinter (cada botón y marco dibuja sus formas en un
lienzo). Bajarlo más pide sustituirlos por widgets ligeros de Tk pantalla a pantalla, o no reconstruir lo que no cambia.
En la app real la selección se repinta sección a sección, así que el bloqueo percibido es menor que la cifra entera.
Las medidas son de la ventana de desarrollo, no de una partida real con LoL en marcha (ahí el PC va más justo).

## Prueba contra el cliente real (13/11/2026)

`python herramientas/prueba_cliente_real.py` con LoL abierto y fuera de partida: TODO BIEN. Cuenta reconocida, 200
partidas entregadas y reconocidas como suyas, historial antiguo (220) heredado sin pérdidas (233 al final), perfil,
182 maestrías y lectura de un jugador correctos, sin fallos registrados.

Hallazgo: al recién abrir el cliente, `owned-champions-minimal` contestó vacío en la primera lectura (0 campeones) y
después 257. Con la lista vacía la app trata todos los campeones como tuyos. Arreglado y publicado en la 1.22.7: se
apunta en el diagnóstico y el bucle reintenta cada 30 s hasta 12 veces mientras `owned` esté vacío.
Sigue sin probar el flujo de una partida completa con el cliente real.

## Pendiente inmediato

1. Rendimiento: repintar una sola sección pequeña cuesta ~300 ms aunque construirla sean 36 ms; el resto es el
   recálculo y redibujado de toda la página que hace Tk. Pide menos widgets por pantalla, no retoques.
   `python herramientas/tiempos.py 560 "solo"` da el desglose por sección.

## Líneas mal contadas: Renekton «de jungla» (13/11/2026, 1.22.8)

El usuario vio en el Historial y el Repertorio una partida de Renekton como jungla («estoy seguro de que no he jugado
Renekton jungla en mi vida»). Era una Solo/Dúo (8041219712). Lo que mostraron los datos reales del cliente:
- El cliente etiquetó `lane: JUNGLE` a los dos jugadores de ese equipo (Renekton y Master Yi) y a ninguno como TOP.
  Renekton llevaba Salto relámpago + Ignición; Master Yi, Aplastar + Salto.
- Cruzando las 55 partidas de Grieta del usuario (línea, Aplastar, objeto de rol): de 16 «JUNGLE» del cliente, 5
  llevaban Aplastar y 11 no. Las 11 llevaban el objeto de rol 1220/1221, el mismo que sus partidas de TOP SOLO.
- Todo lo que leía la etiqueta cruda lo heredaba: historial, estadísticas por línea (Repertorio), rival de línea
  (`find_opponent`) y la línea habitual de otros jugadores (`players._role`). `analysis.infer_roles` ya usaba Aplastar.

Arreglo: `history.role_of` como regla única, `"rv"` (versión de la regla) en cada registro y migración de esquema 1 → 2.
Con el cliente real: Renekton → TOP, 5 partidas de jungla (todas con Aplastar), ninguna jungla sin Aplastar.
Quedaron 40 entradas (en varios archivos) sin línea hasta que el cliente las vuelva a entregar; las anteriores a su
ventana de 200 partidas se quedan sin línea.
Incertidumbre: los valores de `roleBoundItem` son observados, no documentados; por eso se exige que la etiqueta sea
JUNGLE antes de reinterpretarla y, sin más pistas, la línea queda vacía.

# Sesión del 13/11/2026 (tarde y noche): detalle de lo hecho tras la 1.22.8

(Movido desde CONTINUAR.md el 13/11/2026 para que ese documento quede corto. Orden cronológico; lo vigente está resumido en CONTINUAR.md.)

### Hecho el 13/11 después de publicar la 1.22.8 (en `main`, sin publicar)

- **Rival elegido a mano**: antes solo cambiaba la build y la guía; las puntuaciones y el orden de las recomendaciones
  seguían calculándose contra el rival automático. Ahora `gui.set_opp` guarda la elección en `conf["_opp"]` (clave con
  «_»: no se escribe en config.json) y pide `recalc`; `_advise` la usa como `lane_opp` y conserva aparte
  `lane_opp_auto`. Comprobado con la app real contra el cliente falso (`LOLE_RIVAL=1 python herramientas/demo_falso.py 5 rival`):
  Malphite pasa de 9,09 a 10,89 puntos con el motivo «contra Tryndamere: 3/3»; 3 pruebas nuevas.
- **Privacidad de lo guardado** (esquema 2 → 3): `last_session.json` y `live_samples/` ya no llevan nombres ni
  identificadores (`core.scrub`), se limpian los existentes, las muestras caducan a 14 días y una prueba comprueba que la
  conexión sin verificar certificado solo va a 127.0.0.1. Queda a propósito el campo `p` (puuid de compañeros) de
  `games_<cuenta>.json`, que sostiene «Juntos 3V 2D». 4 pruebas nuevas.
- **Puerta previa a publicar** (`herramientas/comprobar_todo.py`): nació de un error real. Un cambio mío en `ui_build.py` pasaba
  las pruebas pero fallaba al pintar la build; solo lo vio una captura. Ahora el recorrido de pantallas es parte de la puerta
  (`capturas.py` devuelve código 1 si hay errores; `LOLE_SINFOTO=1` recorre sin guardar imágenes) y se comprobó que falla
  si se inyecta ese mismo error.
- **Certificados** (ver «Lo que se sabe del cliente»): arreglo de fondo, sin publicar. Lo ideal es que vaya en la 1.22.9: es el
  único cambio pendiente que puede arreglar fallos de red a otras personas. Comprobado: op.gg y GitHub fallaban y ahora van;
  el paquete construido incluye `certifi/cacert.pem`. Sin probar ejecutando el `.exe` construido.
- **Parche de la build**: `builds.patch_of` lee «Patch 16.22» de la página de Lolalytics (26.22 en numeración pública) y
  `builds.load` guarda `patch` y `read` con la build; la nota de fuente dice «parche 26.22, leída hoy» y avisa si el
  parche es anterior al del juego (`ui_build.source_note`). Las builds guardadas antes no lo traen: solo muestran la fuente.
  Error cazado por las capturas: en `ui_build.render()` el nombre `core` es una lista local, no el módulo; usar
  funciones de módulo (`current_patch()`).
- No se pudo ampliar la validación del objeto de rol: el cliente se cerró. `validar_lineas.py` queda listo para
  cuando esté abierto; solo con eso se podría usar el objeto de rol también en las partidas con línea «NONE»
  (8 de las 55 de Grieta del usuario quedan sin línea).

### Revisión con la 1.22.9 en el PC del usuario (13/11/2026, 17:20)

- Se actualizó sola de la 1.22.6 a la 1.22.9 (`diag.log`: «arranca» ×2) y aplicó las migraciones de esquema 1→2→3 y de
  privacidad; «Partida 8041219712: la línea pasa de ? a TOP» (Renekton) en la instalación real.
- Ventana real capturada con `PrintWindow` (la captura de pantalla normal sacaba lo que tapaba la ventana): nivel 901, los tres
  rangos con PL y V/D, maestría 1.307 y las últimas 5 partidas coinciden con el cliente.
- **Hallazgo**: el cliente entregó 20 partidas aunque se le pidieron 200 (antes daba 200), así que solo 13 de las 61 de Grieta
  se recalcularon con la regla de líneas; 48 quedaron pendientes. El detalle por id sí funciona para partidas antiguas.
  Arreglo en `main` (SIN publicar): `lol_advisor._refresh_old_games` las recalcula con su detalle (60 por lectura, las más
  recientes primero). Con el cliente real, sobre una copia: 46 de 46 recalculadas, 18 con otra línea, 0 pendientes.
  Hace falta publicarlo (1.22.10) para que llegue a la instalación del usuario; esperar a que no esté en cola ni en partida
  (la actualización automática instala en «Lobby»).
- **Partida real revisada (Flexible 440, 17:26–17:59)**: el `diag.log` de la instalación muestra el ciclo entero con el cliente real
  (Lobby → Matchmaking → ReadyCheck → selección → InProgress con «10 leídos, 0 con perfil oculto, 0 sin campeón, 0 sin línea» →
  PreEndOfGame → «Partida terminada» → EndOfGame → None). Quedó guardada: Seraphine, apoyo, victoria, 1/6/14; el análisis
  coincide con el historial; ningún error nuevo. En el momento de la partida el cliente sí entregó 200 partidas.
- **Hallazgo grande: la etiqueta de línea del cliente falla mucho.** En esa partida, 4 de 10 jugadores mal etiquetados (Jax
  «jungla», Fizz «top», Nami «bot», Jhin «mid»); `find_opponent` daba «nadie» para el apoyo. En 30 partidas / 60 equipos:
  solo 14 equipos con los cinco puestos distintos según el cliente (29 equipos con 2 junglas y 0 toplane). Se vio que el
  objeto de rol reparte bien: 1206 mid (44 casos), 1209 jungla con Aplastar (50), 1220/1221 top, 1208/2055 apoyo, y las botas
  (3006, 3008, 3009, 3020, 3047, 3158) el tirador (42 de 44). Con la regla nueva: **55 de 60 equipos completos**.
  `history.role_of` (objeto de rol > botas con etiqueta BOTTOM/MIDDLE > Aplastar > etiqueta) y `history.team_roles` (completa un
  equipo por eliminación); `find_opponent` las usa; `ROLE_V = 2`, así que las partidas guardadas con la regla v1 se recalculan
  (las que el cliente lista al conectar; el resto con `_refresh_old_games`). Comprobado con el cliente real: TODO BIEN, 0 pendientes.
  `python herramientas/validar_lineas.py 30` reproduce la medida (necesita el cliente abierto y en reposo).
- **Lo anterior se publicó en la 1.22.10** (recalcular partidas antiguas por su detalle + regla de líneas v2).
  Antes de publicar: `python herramientas/publicar.py --sin-probar "..."` y esperar a que el usuario no esté en cola ni en partida.
- Privacidad: desde mi vista no se puede verificar `last_session.json` ni parte de `live_samples/` (la carpeta de datos que ve
  la sesión mezcla copias antiguas); el usuario puede comprobarlo con el comando de PowerShell de abajo.
  `Select-String -Path "$env:LOCALAPPDATA\LOL-E\cache\live_samples\*","$env:LOCALAPPDATA\LOL-E\cache\last_session.json" -Pattern '"(summonerName|riotId|gameName|puuid)":\s*"[^"]+"' | Measure-Object`
  (debe dar Count 0).

### Interbloqueo de la ventana por el recolector de basura (13/11/2026, en `main`, SIN publicar → 1.22.11)

El recorrido de pantallas de `comprobar_todo.py` se colgó (3 de 3 veces con tuberías; con salida a archivo pasaba). El vigilante
(`LOLE_VIGILA=200` en `capturas.py` vuelca la pila de cada hilo tras N segundos) mostró la causa, que es un fallo REAL de la app:
el hilo de la ventana esperaba en `Thread.start()` (pedir la build de Mayhem) a que arrancase el hilo nuevo, y ese hilo, al arrancar,
disparó el recolector de basura, que ejecutó `tkinter.font.Font.__del__`: llamada a Tk desde otro hilo, que Tk deja esperando al hilo de
la ventana → interbloqueo, ventana congelada para siempre. Puede ocurrir en la app real siempre que la ventana arranque un hilo.
Arreglo: `GUI.__init__` hace `gc.disable()` y `GUI.gc_tick` recolecta en el hilo principal (generación joven cada 5 s, todo cada minuto).
Tras el arreglo: dos recorridos con tuberías en 170 s y la comprobación completa en verde. Lección: ante un cuelgue de Tk, volcar las pilas.

### Repertorio con pestaña propia (13/11/2026, en `main`, SIN publicar → 1.22.11)

El usuario dijo que el Repertorio le gustaba pero estaba «bastante oculto»: era un segmento de la tarjeta «Rango y logros · Modos ·
Repertorio» al final de la pantalla de inicio (hay que bajar, pulsar un segmento pequeño, y no existía durante la selección ni la
partida). Ahora es la pestaña **Repertorio** entre Enfrentamiento e Historial (`ui_pool.PoolView`, `gui.pool_view`); la tarjeta de
inicio conserva «Rango y logros» y «Modos». Ctrl+1…6 (Asesor, Partida, Enfrentamiento, Repertorio, Historial, Datos: el Historial
pasa de Ctrl+4 a Ctrl+5); «Al abrir» en Ajustes ofrece también Repertorio e Historial; LEEME actualizado. Comprobado a 470, 560 y
1340 px (caben las cinco pestañas; en ancho se ve la tabla con el detalle al lado, como estaba diseñado). No cambia el resto de
la navegación: el rediseño completo (`docs/rediseno/prototipo_v2.html`) sigue sin hacerse hasta que el usuario lo revise.
Al subir la versión, añadir la entrada en `novedades.py` y `NOTAS_DE_VERSION.txt`.

### Estado de lo pendiente (13/11/2026, tras publicar la 1.22.10)

Hecho y sin nada sin subir. Lo que queda NO se puede cerrar sin el usuario o sin otra partida:
1. **La instalación del usuario aún corre la 1.22.9** (el `diag.log` termina en la partida de las 17:59). La app mira
   actualizaciones al abrir y cada 3 h: basta con cerrarla y abrirla fuera de cola. Después comprobar en su `diag.log`:
   «--- LOL-E 1.22.10 arranca ---», «Partidas antiguas recalculadas con su detalle…» y que `games_<cuenta>.json` tiene todas las
   partidas de Grieta con `rv: 2` (el comando de la sesión del 13/11 lo cuenta). Y que el Historial/Repertorio ya no tienen toplanes como jungla.
2. **Selección de campeón y pestaña «Partida» con los 10 jugadores en directo** con el cliente real: solo se vieron en el registro
   y en los datos guardados, no en pantalla. Ver la ventana con `PrintWindow` (ver la sesión) mientras el usuario juega.
3. **Compañero a quien «no le salen» los jugadores**: sin reproducir; pedirle su informe de diagnóstico (Ajustes).
4. Decisiones del usuario: espaciado único; rendimiento del pintado (menos widgets por pantalla).
5. Etapa 3 que pide partidas: datos en vivo del puerto 2999, antigüedad de otros datos.
El cliente simulado ya devuelve el detalle de la Grieta con la forma real (etiquetas mal puestas, objetos de rol, Aplastar), así que las
pruebas del bucle cubren la línea y el rival de línea.

### Siguiente trabajo, por orden

1. **Publicar lo acumulado** (rival a mano, privacidad de lo guardado —esquema 3—, parche de la build) como 1.22.9 si el usuario lo
   confirma; al subir la versión, escribir las notas en `novedades.py` y `NOTAS_DE_VERSION.txt`. Que el usuario mire en su Historial y su Repertorio que
   ya no hay toplanes como jungla, y en su próxima partida que salen los 10 jugadores y que el Historial suma la nueva.
2. **Probar una partida completa con el cliente real** (lo único que queda sin ver): cola, selección, carga, partida
   y fin. Lo más útil: que el usuario juegue con LOL-E abierto y después pasar `prueba_cliente_real.py` y mirar
   `cache/diag.log` de su instalación (pedirle el informe de diagnóstico).
3. **Compañero a quien «no le salen» los jugadores de la partida**: sin reproducir. Pedirle el informe de diagnóstico
   con la 1.22.5 o posterior; la línea «Jugadores de la partida …» dice cuántos se leyeron y cuántos con perfil oculto.
4. **Rendimiento del pintado** (hecho en parte, ver el historial): repintar una sección cuesta ~300 ms por el
   recálculo de toda la página que hace Tk; bajarlo pide menos widgets por pantalla. `tiempos.py 560 "solo"`.
5. **Espaciado único**: `SPACE` está definido en `ui_kit.py` pero el código usa 17 valores distintos. Es una decisión
   estética: enseñar al usuario un antes/después antes de migrar.
6. **Cliente falso con respuestas grabadas de una partida real** en vez de inventadas.
7. **Etapa 3 de la hoja de ruta** (más valor en partida): datos en vivo del puerto 2999, resumen de una frase al terminar,
   recalcular recomendaciones al elegir rival a mano, antigüedad visible de los datos de build y meta.
