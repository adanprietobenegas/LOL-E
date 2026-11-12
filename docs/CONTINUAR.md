# Para continuar en una conversación nueva

Escrito el 12/11/2026. Léelo entero antes de tocar nada; después lee `docs/HOJA_DE_RUTA.md`.
`docs/ESTADO_Y_PENDIENTES.md` tiene el detalle histórico (solo si hace falta).

## Qué es

LOL-E: app de Windows (Python 3.12 + CustomTkinter) que lee el cliente de League of Legends para aconsejar en la
selección, mostrar build y jugadores de la partida, y guardar historial y análisis. Interfaz en español.
Repositorio `adanprietobenegas/LOL-E`, rama `main`.

## Dónde está

- Versión en `main`, instalada en el PC del usuario y publicada en GitHub: **1.22.1** (publicada el 12/11/2026).
- Pruebas: `python herramientas/tests_unitarios.py` (32, todas pasan).
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

1. Auditoría visual, pantalla a pantalla, con capturas nuevas (las antiguas estaban en una carpeta temporal).
   Objetivo: qué se ve primero, qué sobra, escala tipográfica y de espaciado únicas en `ui_kit.py`.
2. Textos: «WR» por «% vict.» donde quepa; estados vacíos y de error que digan qué hacer.
3. Etapa 1 de la hoja de ruta: historial separado por cuenta, registro de diagnóstico, cliente falso para
   probar el flujo cola → selección → partida → fin.
4. Contenido: etiquetas del tablero de jugadores y conclusiones del análisis posterior.
5. Rendimiento del pintado.
