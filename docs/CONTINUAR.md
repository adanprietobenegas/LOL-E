# Para continuar en una conversación nueva

Escrito el 12/11/2026. Léelo entero antes de tocar nada; después lee `docs/HOJA_DE_RUTA.md`.
`docs/ESTADO_Y_PENDIENTES.md` tiene el detalle histórico (solo si hace falta).

## Qué es

LOL-E: app de Windows (Python 3.12 + CustomTkinter) que lee el cliente de League of Legends para aconsejar en la
selección, mostrar build y jugadores de la partida, y guardar historial y análisis. Interfaz en español.
Repositorio `adanprietobenegas/LOL-E`, rama `main`.

## Dónde está

- Versión en `main` y publicada en GitHub: **1.22.4** (12/11/2026).
  La app instalada del usuario NO pasó sola de 1.22.1 a 1.22.2 (causa sin confirmar; la 1.22.3 refuerza el
  actualizador). Pendiente: que el usuario instale a mano y confirme que la siguiente versión sí llega sola.
- Pruebas: `python herramientas/tests_unitarios.py` (41, todas pasan).
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
4. Contenido: etiquetas del tablero de jugadores y conclusiones del análisis posterior.
5. Rendimiento del pintado.

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

Sin hacer de la etapa 1:
- Quitar los `except Exception: pass` restantes de `lol_advisor.py` y `players.py`.
- Versión de esquema en cada JSON guardado (solo la llevan `account.json` y `history_owner.json`).
- Los análisis guardados (`cache/analysis/<id>.json`) siguen sin separarse por cuenta.

Sin probar: la migración en la app instalada del usuario y el flujo con el cliente real. Antes de publicarlo conviene
que el usuario lo sepa: es la primera versión que cambia dónde se guarda su historial.

## Caso abierto: a un compañero «no le sale» el Asesor (12/11/2026)

El usuario lo llamó «la parte del profesor»; se entiende que es la pestaña «Asesor» (sin confirmar). No reproducido:
`python herramientas/demo_falso.py` recorre cola → selección → partida → fin con la ventana real y no da errores.
Siguiente paso: que el compañero, ya en la 1.22.4, pulse Ajustes › «Copiar informe de diagnóstico» y lo envíe. Mirar
si aparece «Cliente de LoL encontrado» (si no, LoL está en otra carpeta o no se localiza) y «Selección de campeón».
