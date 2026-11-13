# LOL-E · Hoja de ruta

Escrita el 12/11/2026, con la versión 1.22.1. Define el rumbo; no es un compromiso de fechas.
El estado del día a día sigue en `ESTADO_Y_PENDIENTES.md`.

## De dónde sale

- **Revisado a fondo:** cómo se asocia cada partida contigo (fallo real Sona/Lillia) y el actualizador.
- **Revisado por encima:** vocabulario de los textos (es coherente: «rival» en toda la app, sin «enemigo» ni
  «oponente») y el motor de recomendación (el % de victorias ya está suavizado con un valor previo).
- **Sin revisar todavía:** jerarquía visual pantalla a pantalla, rendimiento del pintado, contenido del análisis
  posterior y etiquetas del tablero de jugadores. Las siete auditorías con agentes se cortaron por el límite de
  uso sin entregar informe. Las etapas 2 y 3 de abajo son, por tanto, criterio propio y no resultado de auditoría.

## Principios

1. **Un dato equivocado es peor que un dato ausente.** Si no se sabe, no se muestra (ya se aplica al análisis).
2. **Los fallos se ven.** Nada de `except: pass` en lecturas del cliente: se registran y se reintentan.
3. **Dos modos, dos ritmos.** En selección y partida: decidir en segundos. En consulta: explorar con calma.
4. **Síntesis antes que cantidad.** Una línea con la conclusión; el detalle, plegado.
5. **Honestidad sobre lo no probado.** Lo que no se ha visto en una partida real se dice.

## Etapa 1 · Confianza en los datos (siguiente)

| Qué | Por qué | Esfuerzo |
|---|---|---|
| HECHO · Historial separado por cuenta (`history_<puuid>.json`) con migración | Hoy dos cuentas en el mismo PC mezclan partidas | Medio |
| HECHO · Registro de diagnóstico (`cache/diag.log`: fases, lecturas, cuántas partidas llegaron) | Los fallos que cuentas de palabra no dejan rastro que consultar | Bajo |
| HECHO · Quitar los `except Exception: pass` de las lecturas del cliente en `lol_advisor.py` y `players.py` | Mismo motivo | Bajo |
| HECHO (respuestas inventadas, no grabadas) · Cliente falso y pruebas del flujo cola → selección → partida → fin | El bucle principal no tiene ninguna prueba | Medio |
| HECHO · Colas desconocidas: avisar en el registro la primera vez que aparece una | La 1740 salió como «Otros» sin que nadie lo notara | Bajo |
| HECHO (una por carpeta: `cache/schema.json`) · Versión de esquema de los datos guardados | Poder migrar sin romper datos antiguos | Bajo |

## Etapa 2 · Claridad y legibilidad

- Auditoría visual pendiente, pantalla a pantalla, con capturas reales: qué se ve primero y qué debería verse.
- Hecho (12/11/2026): escala tipográfica única de 5 tamaños desde `ui_kit.py` y auditoría visual con capturas
  (`herramientas/capturas.py`; resultado en `CONTINUAR.md`). Pendiente: migrar el espaciado a la escala `SPACE`.
- Hecho (12/11/2026): no queda «WR» en ninguna cadena visible.
- Hecho (12/11/2026): estados vacíos y de error que dicen qué pasa y qué hacer.
- Decidir el rediseño de navegación (`docs/rediseno/prototipo_v2.html`): barra lateral o pestañas actuales.
  Sigue pendiente de tu revisión; no se implementa sin ella.
- Texturas o degradados de fondo para los looks, si tras probarlos piden más.

## Etapa 3 · Más valor en partida

- Datos en vivo (puerto 2999): objetos del rival, oro estimado y temporizadores. Ya se guardan muestras.
- Tablero de jugadores: fuera de su rol habitual, primera vez con el campeón, racha, dúos. Con umbrales
  prudentes para no etiquetar con 3 partidas.
- Resumen de una frase al terminar cada partida.
- Hecho (13/11/2026, sin publicar): recalcular las recomendaciones cuando eliges el rival a mano.
- Antigüedad visible de cada dato de build y meta (parche en que se leyó).

## Etapa 4 · Mantenimiento

- Partir `lol_advisor.py` (68 KB): configuración, cliente, lectura de datos, motor y bucle en módulos propios.
- Bucle principal como máquina de estados explícita (hoy son unas 15 variables sueltas).
- Partir `ui_sections.py` (86 KB) por sección.
- Publicación con un solo comando que construya, pase las pruebas y compruebe el instalador.

## Seguridad y privacidad

- Hecho: el actualizador solo acepta GitHub por HTTPS y comprueba la huella SHA-256 del instalador.
- Hecho (13/11/2026, sin publicar): `last_session.json` y `live_samples/` se escriben sin nombres ni identificadores
  (`core.scrub`), lo ya guardado se limpia con la migración de esquema 2 → 3 y las muestras en vivo caducan a las dos
  semanas. Una prueba fija que la verificación de certificado solo se desactiva para `127.0.0.1` (el cliente de LoL y
  su puerto 2999). Se deja a propósito: los identificadores de compañeros en `games_<cuenta>.json` (campo `p`), que son
  los que permiten «Juntos 3V 2D»; son identificadores, no nombres, y no salen de tu PC.

## Qué no hacer

- Reescribir en otra tecnología de interfaz: el coste no compensa mientras Tk dé lo que hace falta.
- Añadir más temas antes de saber cuáles se usan.
- Lanzar muchas auditorías a la vez: una por sesión, aplicando lo que salga antes de pasar a la siguiente.
