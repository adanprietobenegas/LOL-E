# LOL-E · Plan de futuro

Actualizado el 13/11/2026 (versión del código 1.22.12). Sustituye a `HOJA_DE_RUTA.md` y a `ESTADO_Y_PENDIENTES.md`. Lo que ya está hecho
está en `docs/HISTORIAL_DE_SESIONES.md`; el estado de hoy, en `docs/CONTINUAR.md`. **Este plan se revisa al terminar cada fase: tacha lo
hecho (con la versión) y reordena lo demás.** No es un compromiso de fechas.

## Cómo leerlo

- **P0** ahora · **P1** próximas 1–3 semanas · **P2** 1–3 meses · **P3** ideas a explorar.
- **Impacto**: A (se nota cada partida) · M (se nota a menudo) · B (mejora de fondo o puntual).
- **Esfuerzo**, en sesiones de trabajo (una conversación larga ≈ una sesión): S (< 1) · M (1–2) · L (3 o más).
- **Riesgo**: b / m / a de romper algo que ya funciona o de depender de algo que no controlamos.
- **Validar**: cómo se sabe que está bien. Casi todo lo «en partida» solo se puede validar jugando: eso es el cuello de botella real.

## Principios (ya vigentes; no se discuten sin motivo)

1. Un dato equivocado es peor que un dato ausente: si no se sabe, no se muestra (por eso hay líneas vacías y «orientativo»).
2. Los fallos se ven y quedan en el registro (`diag.log`, `error.log`); nada de `except: pass` en lecturas del cliente.
3. Dos ritmos: en selección y partida, decidir en segundos; en consulta (Repertorio, Historial, Enfrentamiento), explorar con calma.
4. Síntesis antes que cantidad: una frase con la conclusión, el detalle plegado.
5. Honestidad sobre lo no probado: se dice en las notas de cada versión.
6. Nada que dé ventaja que el propio juego no muestre: solo lo que el cliente y la API local ya enseñan (ver «Qué no hacer»).

## P0 · Ahora (esta semana)

| # | Qué | Impacto | Esfuerzo | Riesgo | Validar |
|---|---|---|---|---|---|
| 0.1 | **Publicar la 1.22.11** (Repertorio con pestaña, corrección del interbloqueo, partida en vivo) | A | S | b | `publicar.py`; que el usuario se actualice y use la pestaña |
| 0.2 | **Ver el bloque en vivo en una partida real** y ajustar: nombres de eventos de dragón/barón/heraldo, quién los mata, `position` en la Grieta, tiempos de refresco | A | S | m | Capturar la ventana con `PrintWindow` durante una partida; `diag.log` sin errores |
| 0.3 | Confirmar en la instalación del usuario la 1.22.10: líneas recalculadas, Repertorio/Historial sin toplanes como jungla | A | S | b | `estado.py` + su `diag.log`; mirar su pantalla |
| 0.4 | **Compañero a quien «no le salen» los jugadores**: conseguir su informe de diagnóstico | M | S | b | La línea «Jugadores de la partida …» del informe |

## P1 · Próximas 1–3 semanas (valor en partida y en consulta)

| # | Qué | Impacto | Esfuerzo | Riesgo | Validar |
|---|---|---|---|---|---|
| 1.1 | ~~**«Puedes comprar…»**~~ HECHO en `main` (`shopping.py`): siguiente objeto de tu build y lo que te falta restando componentes. Falta verlo en una partida real y, si interesa, avisar con sonido cuando ya puedas comprarlo | A | S | b | Una partida real |
| 1.2 | ~~**Objeto según lo que llevan los rivales**~~ HECHO en `main` sin publicar (`shopping.counter_item`, línea en el bloque en vivo): UN objeto de la cantera de tu campeón, penetración si acumulan una defensa o defensa contra su daño dominante; solo con 2.500+ de oro rival. Falta verlo en partida real y ligarlo a «Situaciones» (heridas graves, tenacidad) | A | M | m | Partidas reales; que el consejo cambie con la partida |
| 1.3 | **Temporizadores de objetivos** (dragón, barón, heraldo, inhibidores) a partir de los eventos. **Verificar los tiempos de reaparición del parche actual antes de mostrarlos**; mostrarlos como «estimado» | A | M | m | Comparar con el reloj del juego en 2–3 partidas |
| 1.4 | ~~**Resumen de la partida al terminar, comparado contigo**~~ HECHO en `main` (KDA y farmeo frente a tu media con ese campeón). Falta, si interesa: más cifras (daño, visión) | M | S | b | Con partidas guardadas |
| 1.5 | ~~**Gráfico de PL/rango en el tiempo**~~ HECHO en `main` sin publicar (`analysis.lp_series`, ficha «Tus PL guardados» en Rango y logros). Falta, si interesa: por cola (flexible) y con marcas de cambio de división | M | M | b | Con el `lp.json` real del usuario |
| 1.6 | ~~**Repertorio: «qué aprender»**~~ HECHO en `main` sin publicar (`learn.py`, tarjeta en Repertorio): si una línea con 8+ partidas depende ≥70 % de un campeón, propone hasta 3 que ya tienes con buena tasa en el parche (Lolalytics). Falta: huecos por rivales difíciles y por línea nunca jugada | M | M | m | El usuario decide si le sirve; con su historial real |
| 1.7 | Mejorar la **jerarquía de la pantalla de selección** (la recomendación y sus alternativas arriba; lo demás plegado) a partir de lo que el usuario vea en partida real | M | M | b | Capturas y uso real |
| 1.8 | ~~**Rival de línea en directo**~~ HECHO en `main` (`live.duel`): nivel, objetos y marcador frente a él. Falta verlo en una partida real | M | S | b | Una partida real |

## P2 · 1–3 meses (calidad de fondo)

| # | Qué | Impacto | Esfuerzo | Riesgo | Validar |
|---|---|---|---|---|---|
| 2.1 | **Rendimiento del pintado**: repintar una sección cuesta ~300 ms porque Tk recalcula toda la página. Menos widgets por pantalla (widgets ligeros de Tk, construcción incremental, listas virtualizadas) | M | L | m | `tiempos.py` antes/después; objetivo: selección < 400 ms |
| 2.2 | **Partir `lol_advisor.py` (~1.600 líneas) y `ui_sections.py` (~1.700)**: configuración, cliente, lectura de datos, motor y bucle por separado; bucle principal como máquina de estados (hoy ~15 variables sueltas) | B | L | a | La batería actual (pruebas + `comprobar_todo.py` + `prueba_cliente_real.py`) debe seguir en verde en cada paso |
| 2.3 | **Robustez de las fuentes externas**: HECHO en `main` sin publicar para build y meta: sin red se usan los últimos datos guardados (marcados «stale», con su antigüedad) y, si la página de Lolalytics cambia de formato, el error lo dice y manda al informe de diagnóstico. Falta: op.gg (tendencias, puesto en la clasificación) y validadores de forma sobre el meta | A | M | m | Pruebas con red simulada (hechas); simular un cambio de formato en op.gg |
| 2.4 | **Escala visual única** (tipografía hecha; falta el espaciado: 17 valores distintos en el código) y pulido del tema claro | B | M | b | Capturas antes/después que el usuario apruebe |
| 2.5 | **Rediseño de navegación** (`docs/rediseno/prototipo_v2.html`). El usuario decide; ya se hizo el cambio puntual del Repertorio | M | L | m | Prototipo revisado por el usuario antes de tocar código |
| 2.6 | **Instalador firmado** (certificado de firma de código) o, al menos, reputación en SmartScreen: hoy algunos antivirus protestan | M | M | b | Instalar en un PC limpio |
| 2.7 | **Cliente falso: más casos del bucle**. HECHO en `main`: esquivar, caída del cliente, ARAM/Arena, reconexión, cuenta desconocida, sesiones raras (encontró un fallo real al esquivar). Falta: partida rehecha (remake), cola de dos fases, respuestas grabadas y anonimizadas a mano | B | M | b | Pruebas del bucle |
| 2.8 | ~~**Informe de diagnóstico con un clic** más completo~~ HECHO en `main` sin publicar (`lol_advisor.health_lines`: esquema, partidas con línea de regla antigua o sin línea, PL guardados, edad del meta y de las builds, ajustes relevantes). Falta, si hace falta, una guía de «qué enviar» para los compañeros | M | S | b | Un compañero lo usa |

## P3 · Ideas a explorar (sin prometer)

- **Coaching con IA**: un resumen en lenguaje natural de la partida o de tu semana. Pide decidir dónde corre el modelo, clave de API o coste, y
  qué datos salen del PC (privacidad). Esfuerzo L, riesgo a. Solo si el usuario lo quiere y con consentimiento claro.
- **Varias cuentas**: el historial ya es por cuenta; falta una interfaz para ver/cambiar de cuenta y comparar. M.
- **Fin de temporada** (resumen estilo «Wrapped»: campeón del año, mejor racha, rango máximo). S–M, ideal para compartir.
- **Dúo/compañeros**: «Juntos 3V 2D» ya existe; ampliarlo a una ficha del dúo habitual (campeones, líneas, % juntos). M.
- **Otros idiomas y regiones**: hoy español (EUW). i18n de los textos y selección de región. L.
- **Compartir**: exportar el análisis o el repertorio como imagen. S–M.
- **Versión para otros sistemas**: hoy solo Windows (rutas del cliente, `PrintWindow`, instalador). L; solo si hay demanda real.

## Qué NO hacer

- **Superposición («overlay») dentro del juego**: riesgo con el anticheat y la política de terceros de Riot; la ventana de LOL-E es aparte (y
  puede ir siempre visible solo en selección). Antes de cualquier cosa que se acerque a eso, leer la política vigente de Riot.
- **Seguimiento de tiempos de recarga de hechizos o ultis rivales** u otra información que el propio juego no muestre al jugador.
- Reescribir en otra tecnología de interfaz mientras Tk dé lo que hace falta (el coste no compensa).
- Más temas visuales antes de saber cuáles se usan.
- Lanzar varias tareas a la vez en la misma sesión (agota el límite de uso).
- Guardar o publicar datos de otros jugadores: lo guardado de depuración va sin nombres ni identificadores (ver `core.scrub`).

## Riesgos conocidos y cómo se mitigan

| Riesgo | Efecto | Mitigación actual / pendiente |
|---|---|---|
| Cambia el formato de Lolalytics u op.gg (HTML) | Builds o meta vacíos | Aviso en pantalla y caché; **pendiente 2.3** (validadores) |
| Cambia la API local del cliente o del juego | Lecturas vacías o líneas mal | `diag.log`, `soft_fail`, regla de líneas con señales múltiples; `validar_lineas.py` para revalidar |
| Valores del objeto de rol (1220, 1206…) son observados, no oficiales | Líneas mal deducidas si cambian | Se exige coherencia con otras señales; sin pistas la línea queda vacía; revalidar cada parche grande con `validar_lineas.py` |
| Certificados raíz de Windows incompletos | Fallos de red intermitentes | `install_certs()` (certifi) y `curl.exe` de reserva en el actualizador |
| Un cambio de interfaz pasa las pruebas pero falla al pintar | Pantalla rota | `comprobar_todo.py` recorre todas las pantallas; es obligatorio antes de publicar |
| Interbloqueos de Tk (hilos) | Ventana congelada | Recolector de basura solo en el hilo principal; vigilante `LOLE_VIGILA`; regla: nada de Tk fuera del hilo principal |
| Actualización automática rota en PC antiguos | PC atascados en una versión vieja | Corregido en la 1.22.5; los PC anteriores necesitan una instalación manual |
| Depender de una sola persona/sesión para el contexto | Se repite trabajo o se rompen reglas | `CONTINUAR.md` + `estado.py` + pruebas de frescura de documentos |

## Qué necesita decidir el usuario

1. ¿Publicar la 1.22.11 ya, o esperar a ver el bloque en vivo en una partida?
2. ¿Espaciado único de la interfaz? (cambio estético: se enseña antes/después).
3. ¿Rendimiento del pintado ahora (P2.1, trabajo grande) o seguir con valor en partida (P1)?
4. ¿Se quiere el rediseño de navegación del prototipo v2 (P2.5)?
5. ¿Hay interés en compartir LOL-E con más gente además de los compañeros? Eso sube la prioridad del instalador firmado (2.6), de las fuentes
   externas robustas (2.3) y de revisar la política de Riot.

## Cómo medir que va bien

- Cada versión pasa `comprobar_todo.py` y `prueba_cliente_real.py` en verde; el número de fallos que llegan a un compañero baja.
- Ninguna partida real queda con línea «jungla» sin Aplastar; los equipos con los cinco puestos distintos se mantienen por encima del 90 %.
- El tiempo de repintado de la selección baja de ~1 s a menos de 400 ms (P2.1).
- Cuando algo falla en un PC ajeno, el informe de diagnóstico basta para saber por qué sin pedir más.
