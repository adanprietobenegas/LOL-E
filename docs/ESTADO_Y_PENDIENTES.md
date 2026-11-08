# LOL-E · Estado del proyecto y pendientes

Actualizado el 5/11/2026. Versión instalada en tu PC: **1.11.2** (en GitHub está publicada la 1.8.2; la 1.11.2 está sin subir por decisión tuya).

## Qué es
App de Windows (Python + CustomTkinter) que lee el cliente de League of Legends (LCU) y te asesora en la selección de campeón. Cuatro pestañas: **Asesor**, **Enfrentamiento**, **Historial** y **Datos**. Se reparte en un instalador (Inno Setup) dentro de un `.zip` con instrucciones.

## Numeración de versiones (X.Y.Z)
- **Z** (1.4.2 → 1.4.3): arreglos y retoques pequeños.
- **Y** (1.7.0 → 1.8.0; la 1.11.2 fue de arreglos y rendimiento): función nueva que se nota al usar la app.
- **X** (→ 2.0.0): cambio grande.

## Cómo está ahora

### Hecho y comprobado (demo con datos simulados + tu cliente real)
- Asesor en la Grieta: turno con icono de línea y fases, carrusel de recomendaciones, desglose de afinidad centrado, jugadores del equipo, bans, sinergias, meta.
- ARAM (banquillo), Arena, personalizadas y otros modos: no fallan con datos incompletos (6 sesiones raras probadas) y muestran información breve.
- Asesor (pantalla de espera): tarjeta «Rango y logros» (mejor rango de la temporada, retos y percentil, maestría, honor, racha).
- Enfrentamiento (rehecho en 1.5.0): dos pasos (elige rival con buscador en lista; qué campeón le gana con podio y tabla), línea habitual del rival, filtros, campeones nuevos con pocos datos.
- Historial (rehecho en 1.5.0): resumen con estadísticas del filtro, buscador y filtros, lista por días con cabecera, cada partida se despliega (oro, daño/min, visión, objetos), carga de 20 en 20, Arena con puesto. 201 partidas guardadas desde el 08/10/2026.
- Builds (runas, objetos, hechizos, habilidades) desde Lolalytics (`builds.py`, `runes.py`, `ui_build.py`), en «Meta y build» y en Enfrentamiento. Líneas reales por meta (`meta.lane_shares`) y umbral `lane_share_min`.
- Picks en auge (`trends.py`): cambio de uso frente al parche anterior en tu servidor y 7 regiones líderes (KR, JP, TW, SG, VN, NA, OCE); probado con 10 parches y 14 regiones (China no está disponible; el nivel regional y el winrate no predicen). Ver el Léeme.
- Repertorio (`ui_pool.py`): tabla + panel de detalle (Resumen/Partidas/Build). Enfrentamientos con pocas partidas y orden «Más fiable» (intervalo de Wilson).
- Asesor: tarjeta única con pestañas e interacción (`SummaryCard`).
- Ventana: por defecto solo «por encima de las demás» durante la selección (Ajustes: Nunca / En la selección / Siempre); Alt+Tab normal el resto del tiempo.
- Datos: pesos y umbrales bloqueados con candado, desbloqueo con confirmación, «Restablecer todo».
- Ajustes rehechos (animaciones, pestaña inicial, caché, restablecer). Ventana maximizada sin encogerse al abrir Ajustes. Tema claro/oscuro rehaciendo la interfaz.
- Contenido centrado con ancho máximo (1240 px) y adaptado de 460 px a maximizada.
- Instalador y .zip; instalación sobre una versión anterior; relanzado tras actualizar.

### Medidas de rendimiento (demo)
Cambiar de pestaña: ~110–280 ms (la primera vez que se abre Enfrentamiento, ~700 ms). Abrir Ajustes: ~170 ms. Cambiar tema/acento/tamaño: ~2,5 s (rehace toda la interfaz).

### NO comprobado
- Selección de campeón **real** con compañeros reales, ni partidas reales de ARAM, Arena o personalizadas (solo sesiones simuladas).
- Escalado real de pantalla de Windows (solo simulado al 125 y 150 %).
- Si los sonidos se oyen bien y a buen volumen.
- Flujo completo de **auto-actualización** (comprobar, descargar, verificar, instalar) con un `latest.json` publicado de verdad.
- El cuadro de confirmación al desbloquear los pesos (se sustituyó en las pruebas).

## Decisiones tomadas (no reabrir sin motivo)
- **Sin la API oficial de Riot** (Match-V5 con clave): descartada por ti. El historial solo crece con lo que el cliente entrega (~20 partidas por vez); no se puede recuperar lo anterior a usar LOL-E.
- Tipos de partida: se deciden por `gameMode`/`gameType` del cliente (CHERRY = Arena, CUSTOM_GAME = Personalizada), no solo por el número de cola (1750 = Arena 3x6, no figura en la lista oficial de colas de Riot).
- Fuentes: cliente de LoL (lo personal), Data Dragon (campeones, iconos, objetos), Meraki (posiciones), Lolalytics (meta y enfrentamientos), op.gg (perfil público), CommunityDragon (emblemas). OneTricks solo como enlace (bloquea bots).
- Iconos de la app: solo tipografía «LOL-E».

## Pendientes (por orden de utilidad)
1. **Publicar la 1.11.2**: el repo es público (https://github.com/adanprietobenegas/LOL-E, cuenta adanprietobenegas) y la 1.8.2 está en Releases. Para publicar: `python build_release.py`, `git add -A; git commit; git push` y `gh release create vX.Y.Z` con el `.exe`, el `.zip` y `latest.json`. El código vive en `Documents\LOL-E`. No se suben `cache/`, `release/`, `docs/img/demo/`, `config.json` ni `season_seed.json` (llevan tu nombre de LoL); las capturas de `docs/img` van con el nombre redactado.
2. **Actualizaciones automáticas**: activas desde la 1.8.2 (leen `releases/latest/download/latest.json`). Quien tenga la 1.8.0 o 1.8.1 debe instalar la 1.8.2 o posterior a mano una vez. El flujo completo (descargar, verificar, instalar) no se ha visto actualizar de verdad: se verá al publicar la 1.11.2.
3. **Probar en partida real**: una selección de campeón con compañeros, y un ARAM, un Arena y una personalizada, y revisar el historial y el «Error.log» de `%LOCALAPPDATA%\LOL-E\cache`.
4. **Aviso de Windows (SmartScreen)**: sin firma de código sale «Windows protegió su PC». Firmar cuesta dinero; de momento está explicado en el Léeme.
5. **op.gg**: el aviso del pie ya es corto; si sigue fallando (se vio «op.gg no disponible» con la 1.4.3) hay que revisar cache\\error.log: probablemente op.gg bloquea la petición. Es secundario (solo afina estadísticas de temporada).
6. **Parche 26.22**: Lolalytics aún no tiene muestra suficiente; se usan los datos del 26.21 y la app lo indica (reintenta cada 3 h). Sin acción.
7. Pendiente de pedir/decidir: tops por campeón (Fiora 68.º de EUW): no hay fuente fiable; recorridos de jungla recomendados: no hay fuente abierta; datos en directo durante la partida (Live Client API en el puerto 2999) sin implementar.
8. Ideas aparcadas: sinergias de dúo más finas, tendencia del rival de línea, builds por objetos usando el historial.

## Riesgos conocidos
- La API del cliente de LoL (LCU) **no está soportada oficialmente** para terceros: Riot puede cambiarla sin aviso.
- Lolalytics y op.gg se leen de sus páginas web: si cambian su diseño, esa parte falla (el resto sigue funcionando y la app lo indica).
- Las estadísticas de terceros no son oficiales.

## Cómo construir y probar (para mañana)
- Python: `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`. Inno Setup 6 en `%LOCALAPPDATA%\Programs\Inno Setup 6`.
- Carpeta de trabajo: `%USERPROFILE%\Documents\LOL-E` (git). Para compilar hace falta `cache/` con `champions.json`, `meraki.json` e `icons/` (datos públicos; no están en el repo).
- Construir: `python build_release.py` (genera `release/LOL-E-<versión>.zip`, `Instalar-LOL-E-<versión>.exe` y `latest.json`). Trabaja en `%TEMP%\lolb` por el límite de 260 caracteres de Windows.
- Versión: constante `APP_VERSION` en `lol_advisor.py`.
- Probar sin jugar: `herramientas/demo_live.py` abre la app con una partida simulada y se maneja escribiendo órdenes en un archivo (ver la cabecera del script). `herramientas/test_modes.py` prueba sesiones raras (Arena, personalizada, ARAM vacío). Ambos usan `shots2.py` (necesita el cliente de LoL abierto) y escriben en `herramientas/salida/` (ignorada por git).
- Regla: **no editar archivos UTF-8 con los cmdlets de PowerShell** (corrompen los acentos); usar Python o el editor.

## Mapa del código
| Archivo | Para qué |
|---|---|
| `app.py`, `iniciar*.bat` | Arranque (ventana / consola) |
| `lol_advisor.py` | Motor: lee el cliente, datos del jugador, puntuación, modos, bucle principal |
| `gui.py` | Ventana: cabecera, pestañas, ajustes, actualizaciones, eventos |
| `ui_sections.py` | Secciones del Asesor (turno, recomendaciones, equipo, rivales…) |
| `ui_views.py` | Enfrentamiento y Datos |
| `ui_history.py`, `history.py` | Historial (vista y archivo local) |
| `ui_kit.py` | Colores, componentes, iconos, animaciones |
| `ui_pool.py`, `ui_build.py` | Repertorio y panel de build |
| `builds.py`, `runes.py`, `trends.py` | Builds y runas (Lolalytics), picks en auge |
| `meta.py`, `matchups.py`, `players.py`, `synergy.py`, `items.py`, `params.py`, `sounds.py`, `updater.py` | Fuentes de datos y utilidades |
| `build_release.py`, `docs/` | Empaquetado y documentación |


PENDIENTE (anotado el 6 de noviembre de 2026)
  · Revisar el detalle desplegado de cada partida del Historial: el usuario
    lo ve pobre y con información innecesaria (nivel, oro, daño/min, CS/min,
    visión, lista de objetos en texto, id de partida). Rediseñarlo con lo que
    de verdad ayude. También: tarjeta borrosa al 125-150 %, doble reescalado
    de retratos y escala única de tamaños de retrato (auditoría de imágenes).

REVISIÓN DEL DETALLE DESPLEGADO DEL HISTORIAL (ui_history.py, método detail, ~línea 615)
  Qué muestra hoy: una línea de texto con nivel, oro, daño/min, CS/min y visión;
  los iconos de objetos; los mismos objetos en texto ("Objetos: ..."); y
  "Partida del ... · número ...". Problemas:
  · El texto de objetos repite los iconos (ya tienen tooltip): quitarlo.
  · La fecha repite la de la cabecera del día y el número de partida solo sirve
    para depurar: moverlos a un tooltip o quitarlos.
  · Todo va en una frase corrida: sin jerarquía ni comparación. Ideas: tarjetas
    pequeñas con valor y referencia ("CS/min 7,9 · tu media 6,8"), mini barra de
    daño frente al equipo y botón "Ver análisis" que lleve a Partida > Análisis
    con esa partida (ya existe el análisis completo, el detalle debería ser
    solo un resumen que enlace a él).
  · Nivel y oro aportan poco por sí solos; priorizar lo que cambia decisiones
    (diferencia de oro a los 15 min, muertes antes del 15, objetivos).
  · Hay que decidir qué ve cada modo (Arena, ARAM, Normales/Clasificatoria).
  Estado: solo revisado, sin cambios hechos.

CLASIFICATORIAS DE 5 (RANKED 5s, cola 710): INVESTIGACIÓN Y MEJORAS (8 nov 2026)
  Fuentes: soporte de Riot (support.riotgames.com/en-us/league-of-legends/events/ranked-5s),
  dev "the return of ranked 5s" (leagueoflegends.com, 27-05-2026), notas del parche 26.13,
  LoLTheory (blog de terceros), mensajes en X sobre el "Enemy Scouting". No se encontraron
  hilos de Reddit con datos fiables; el resto es comunidad/terceros.
  Lo que es: cola solo para grupos completos de 5, sin límite de rango, solo viernes a domingo
  (4 PM-4 AM hora del servidor según soporte). Experimento 1: 26-jun a 6-sep-2026.
  Experimento 2: 11-sep-2026 a 7-ene-2027 (después, sin anunciar). Escalera, MMR y LP propios,
  5 partidas de colocación, sin decay. Tournament Draft: 3 bans y 3 picks, luego 2 bans y 2 picks.
  Comprobado en una selección real (cliente): bans A0,E5,A1,E6,A2,E7; picks A0,E5,E6,A1,A2,E7;
  bans E8,A3,E9,A4; picks E8,A3,A4,E9 (A = tu equipo, E = rival). Tu equipo trae la línea
  asignada; los rivales NO traen línea. Los nombres de los rivales sí son visibles.
  El cliente NO expone el "scouting" de Riot (probado: no hay endpoint); el desplegable de Riot
  (top campeones, maestría y rendimiento reciente de cada rival) no se puede copiar de ahí,
  pero LOL-E ya calcula casi lo mismo con los datos del cliente.
  Hecho: la cola se trata como la Grieta; rivales con rango, forma, campeones y maestría;
  bans desde las acciones; rango propio de la cola; PL por partida; aviso "Sin rango ni historial".
  Mejoras pendientes, por orden de valor:
  1. BANEOS DIRIGIDOS: sugerir bans por jugador rival: su campeón más jugado, su mayor maestría y
     su % de victoria reciente con él. Más importante en la 2.ª fase de bans (se ven 6 picks).
  2. Bans de la 2.ª fase: sugerir el campeón que completa la composición rival o que contrarresta
     tus picks ya bloqueados, y proteger tu pick pendiente.
  3. Deducir la línea de cada rival (rol habitual del jugador + posiciones del campeón) y de ahí
     tu rival directo (lane_opp), que hoy queda vacío en esta cola.
  4. Mostrar el orden del draft (de quién es el turno y cuántos bans/picks quedan) y el
     cronómetro por fase.
  5. Resumen de equipo: media de rango propia y rival, aviso de grandes diferencias (Riot dice que
     equilibra las disparidades) y de cuentas nuevas (smurf).
  6. Quinto tile de rango "5v5" en el resumen de Asesor y filtro propio en el Historial.
  7. Los 9 perfiles tardan ~15 s en cargar: cargar primero a los rivales o subir los hilos.
  8. Mostrar en Ajustes/Datos que la cola solo está disponible fines de semana y hasta el 7-ene-2027.

  ESTADO (1.14.0): hechas las mejoras 1 (bans dirigidos), 3 (línea probable y rival directo),
  4 (turnos), 5 (resumen de equipos), 6 (bloque de rango 5v5; el filtro del Historial ya existía
  como "Clasificatorias de 5"), 7 (rivales primero, 6 hilos) y 8 (aviso de fines de semana y fecha).
  Parcial: 2 (2.ª tanda de bans) solo cambia el título y ya cuenta con los picks vistos; falta sugerir
  el campeón que completa la composición rival o contrarresta tus picks bloqueados.
