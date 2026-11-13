# Para continuar en una conversación nueva

Escrito el 12/11/2026. Léelo entero antes de tocar nada; después lee `docs/HOJA_DE_RUTA.md`.
`docs/ESTADO_Y_PENDIENTES.md` tiene el detalle histórico (solo si hace falta).

## Qué es

LOL-E: app de Windows (Python 3.12 + CustomTkinter) que lee el cliente de League of Legends para aconsejar en la
selección, mostrar build y jugadores de la partida, y guardar historial y análisis. Interfaz en español.
Repositorio `adanprietobenegas/LOL-E`, rama `main`.

## Dónde está

- Versión en `main` y publicada en GitHub: **1.22.7** (13/11/2026).
- **Por qué no se actualizaban los PC antiguos (resuelto en la 1.22.5):** su `config.json` guardaba `"update_url": ""`
  y eso tapaba la dirección de fábrica; la app nunca buscaba versiones. `load_conf` ya trata el vacío como «la de
  fábrica». Cada PC con una versión anterior a la 1.22.5 necesita UNA instalación manual; después llegan solas.
  CONFIRMADO el 13/11/2026: una 1.22.5 instalada pasó sola a la 1.22.6.
- Pruebas: `python herramientas/tests_unitarios.py` (48, todas pasan).
- Pendiente de que el usuario confirme en su app que el análisis del ARAM de Lillia ya no muestra Sona.

## Reglas del usuario

- Preguntar antes de publicar una versión. El comando `gh release create` lo bloquea el modo automático hasta
  que el usuario lo confirma en el chat.
- No construir (`python build_release.py`) ni instalar mientras haya partida en curso.
- Ser honesto con lo que no se ha probado en una partida real. Mantener docs y notas de versión al día.
- El rediseño de navegación (`docs/rediseno/prototipo_v2.html`) no se implementa hasta que lo revise.
- Ventanas de prueba, en el monitor secundario (posición -1366,209).

## Cómo trabajar sin agotar el límite

- **Sin subagentes en paralelo.** Siete a la vez agotaron el límite de 5 horas en dos minutos.
- Una auditoría por conversación; aplicar lo que salga y hacer commit antes de pasar a la siguiente.
- Los archivos grandes (`ui_sections.py`, `lol_advisor.py`, `gui.py`, `ui_views.py`) se leen por fragmentos
  con Grep y Read con `offset`/`limit`, nunca enteros.
- La carpeta `%LOCALAPPDATA%\LOL-E` que ve la sesión es una copia virtualizada y antigua: no sirve para
  diagnosticar la app instalada. Para probar con datos reales, usar la carpeta `cache/` del proyecto.

## Publicar una versión

1. Subir `APP_VERSION` en `lol_advisor.py`, entrada arriba en `novedades.py` y en `docs/NOTAS_DE_VERSION.txt`.
2. `python build_release.py` y después las pruebas (una comprueba que `release/latest.json` coincide).
3. Commit y push. Con el sí del usuario:
   `gh release create vX.Y.Z "release\Instalar-LOL-E-X.Y.Z.exe" "release\LOL-E-X.Y.Z.zip" "release\latest.json" --title "LOL-E X.Y.Z" --notes "…" --target main`

## Siguiente trabajo, por orden

1. ~~Auditoría visual~~ **hecha el 12/11/2026** (ver «Auditoría visual» abajo). Quedan sus propuestas de estructura,
   que esperan la decisión del usuario.
2. ~~Textos~~ **hecho el 12/11/2026** (publicado en la 1.22.4). «WR» ya no aparecía
   en ninguna cadena visible. Reescritos los estados vacíos y de error que no decían qué hacer (análisis sin
   cliente, meta sin datos con su causa, filtros sin resultados, maestría, modos, baneos, buscador, Mayhem, pie de
   op.gg). Los fallos al pintar ahora se guardan en el registro de errores, no solo pasan por el pie.
3. ~~Etapa 1~~ **hecha en parte el 12/11/2026** (publicada en la 1.22.4). Ver «Etapa 1» abajo.
4. ~~Contenido~~ **hecho el 12/11/2026** (publicado en la 1.22.5). Ver «Jugadores de la partida y punto 4» abajo.
5. ~~Rendimiento del pintado~~ **hecho en parte el 12/11/2026** (publicado en la 1.22.6). Ver «Rendimiento» abajo.

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
