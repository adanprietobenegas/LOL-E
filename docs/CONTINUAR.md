# Para continuar en una conversación nueva

Escrito el 13/11/2026. Léelo entero antes de tocar nada. El detalle de lo hecho los días 12 y 13/11 está en
`docs/HISTORIAL_DE_SESIONES.md` (solo si hace falta) y el rumbo general en `docs/HOJA_DE_RUTA.md`.

## Qué es

LOL-E: app de Windows (Python 3.12 + CustomTkinter) que lee el cliente de League of Legends para aconsejar en la
selección, mostrar build y jugadores de la partida, y guardar historial y análisis. Interfaz en español.
Repositorio público `adanprietobenegas/LOL-E`, rama `main`.

## Dónde está (13/11/2026)

- **Publicada en GitHub: 1.22.8** (13/11/2026): el arreglo de las líneas (Renekton figuraba como jungla).
  En `main`, SIN publicar: elegir el rival de línea a mano ahora recalcula también las puntuaciones (ver abajo).
- Pruebas: `python herramientas/tests_unitarios.py` → 63, todas pasan. Con LoL abierto y fuera de partida:
  `python herramientas/prueba_cliente_real.py` (solo lectura, sobre una copia temporal) → TODO BIEN con la 1.22.8.
- La actualización automática funciona: el usuario confirmó que su 1.22.5 pasó sola a la 1.22.6. Cualquier PC con una
  versión anterior a la 1.22.5 necesita instalar a mano UNA vez (tenía guardada vacía la dirección de actualizaciones).
- **Sin probar:** el flujo de una partida completa (cola → selección → partida → fin) con el cliente real. Solo se ha
  visto con el cliente falso (`herramientas/cliente_falso.py`, respuestas inventadas) y la lectura en reposo con el real.

## Reglas del usuario

- **Preguntar antes de publicar una versión** (`gh release create`; el modo automático lo bloquea hasta que el usuario
  lo confirma en el chat). Subir commits a `main` no necesita permiso.
- No construir (`python build_release.py`) ni subir instaladores mientras haya partida en curso
  (`tasklist | grep -i "League of Legends.exe"`). Esperar a que acabe.
- Ser honesto con lo que no se ha probado en una partida real. Mantener docs y notas de versión al día.
- El rediseño de navegación (`docs/rediseno/prototipo_v2.html`) no se implementa hasta que lo revise.
- Ventanas de prueba, en el monitor secundario (posición -1366,209).
- El usuario da vía libre con «hazlo como creas / ten buen criterio»: decidir y explicar, sin preguntar lo
  convencional. Responder en español.

## Cómo trabajar sin agotar el límite

- **Sin subagentes en paralelo** (siete a la vez agotaron el límite de 5 horas en dos minutos). Trabajar en línea.
- Los archivos grandes (`ui_sections.py`, `lol_advisor.py`, `gui.py`, `ui_views.py`) se leen por fragmentos con Grep y
  Read con `offset`/`limit`, nunca enteros.
- La carpeta `%LOCALAPPDATA%\LOL-E` que ve la sesión puede ser una copia virtualizada y antigua: no sirve para
  diagnosticar la app instalada. Probar con la carpeta `cache/` del proyecto o con `prueba_cliente_real.py`.
- Para ediciones grandes con acentos y comillas, escribir un script `.py` en el scratchpad y ejecutarlo (los
  heredocs de Bash con comillas mezcladas fallan). Los archivos del proyecto usan CRLF: leer con `newline=""`.

## Publicar una versión

1. Subir `APP_VERSION` en `lol_advisor.py`, entrada arriba en `novedades.py` y en `docs/NOTAS_DE_VERSION.txt`.
2. Sin partida en curso: `python build_release.py` y después las pruebas (una comprueba que `release/latest.json`
   coincide con la versión).
3. Commit y push. Con el sí del usuario:
   `gh release create vX.Y.Z "release\Instalar-LOL-E-X.Y.Z.exe" "release\LOL-E-X.Y.Z.zip" "release\latest.json" --title "LOL-E X.Y.Z" --notes "…" --target main`
4. Comprobar `curl -sL https://github.com/adanprietobenegas/LOL-E/releases/latest/download/latest.json`: GitHub puede
   tardar un minuto en servir la versión nueva.

## Herramientas (carpeta `herramientas/`)

| Herramienta | Para qué |
|---|---|
| `tests_unitarios.py` | 63 pruebas sin ventana ni cliente (incluye el bucle principal contra el cliente falso) |
| `prueba_cliente_real.py` | Lectura de solo lectura contra el cliente REAL (cuenta, historial, migración, líneas, perfil) |
| `capturas.py [ancho] [alto] [carpeta]` | Capturas de todas las pantallas sin cliente; `LOLE_SOLO`, `LOLE_PAGINAS`, `LOLE_CONF`, `LOLE_PERFIL` |
| `demo_falso.py` | La app entera (ventana + bucle) contra el cliente falso, con una captura por fase |
| `tiempos.py [ancho] [texto]` | Mide y perfila el pintado de cada pantalla |
| `validar_lineas.py [n]` | Con el cliente abierto: cruza etiqueta de línea, Aplastar y objeto de rol en n partidas (valida `history.role_of`) |
| `cliente_falso.py` | Cliente de mentira con guion por pasos (lo usan las pruebas y la demo) |

## Lo que se sabe del cliente de LoL (cosas que costaron descubrir)

- La etiqueta de línea del cliente (`timeline.lane`) FALLA: etiqueta JUNGLE a toplanes y puede dejar dos jungleros y
  ningún TOP en un equipo. La jungla se reconoce por llevar Aplastar (hechizo 11). Regla única: `history.role_of`.
  El objeto de rol (`stats.roleBoundItem`: 1220/1221 top, 1209 jungla, 1208/2055 apoyo) es un valor observado.
- Tras abrir el cliente, algunas lecturas llegan vacías un rato (p. ej. `owned-champions-minimal`): se reintenta.
- El cliente solo entrega las últimas ~200 partidas; LOL-E guarda las que ve. Historial por cuenta:
  `history_<puuid>.json`; los antiguos sin dueño se copian a la primera cuenta que los reconoce.
- `cache/diag.log` (conexión, cuenta, fases, lecturas) y `cache/error.log` son lo primero que pedir a quien diga que
  «no le sale» algo: Ajustes › «Copiar informe de diagnóstico».

## Hecho el 13/11 después de publicar la 1.22.8 (en `main`, sin publicar)

- **Rival elegido a mano**: antes solo cambiaba la build y la guía; las puntuaciones y el orden de las recomendaciones
  seguían calculándose contra el rival automático. Ahora `gui.set_opp` guarda la elección en `conf["_opp"]` (clave con
  «_»: no se escribe en config.json) y pide `recalc`; `_advise` la usa como `lane_opp` y conserva aparte
  `lane_opp_auto`. Comprobado con la app real contra el cliente falso (`LOLE_RIVAL=1 python herramientas/demo_falso.py 5 rival`):
  Malphite pasa de 9,09 a 10,89 puntos con el motivo «contra Tryndamere: 3/3»; 3 pruebas nuevas.
- **Privacidad de lo guardado** (esquema 2 → 3): `last_session.json` y `live_samples/` ya no llevan nombres ni
  identificadores (`core.scrub`), se limpian los existentes, las muestras caducan a 14 días y una prueba comprueba que la
  conexión sin verificar certificado solo va a 127.0.0.1. Queda a propósito el campo `p` (puuid de compañeros) de
  `games_<cuenta>.json`, que sostiene «Juntos 3V 2D». 4 pruebas nuevas.
- **Parche de la build**: `builds.patch_of` lee «Patch 16.22» de la página de Lolalytics (26.22 en numeración pública) y
  `builds.load` guarda `patch` y `read` con la build; la nota de fuente dice «parche 26.22, leída hoy» y avisa si el
  parche es anterior al del juego (`ui_build.source_note`). Las builds guardadas antes no lo traen: solo muestran la fuente.
  Error cazado por las capturas: en `ui_build.render()` el nombre `core` es una lista local, no el módulo; usar
  funciones de módulo (`current_patch()`).
- No se pudo ampliar la validación del objeto de rol: el cliente se cerró. `validar_lineas.py` queda listo para
  cuando esté abierto; solo con eso se podría usar el objeto de rol también en las partidas con línea «NONE»
  (8 de las 55 de Grieta del usuario quedan sin línea).

## Siguiente trabajo, por orden

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
