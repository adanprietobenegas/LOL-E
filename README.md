# LOL-E

Asesor de selección de campeón para League of Legends (Windows). Lee el cliente del juego en local (LCU), te recomienda campeón durante la selección, y además trae historial, repertorio, enfrentamientos y meta. Escrito en Python con CustomTkinter, con interfaz en español.

> Proyecto personal, no afiliado a Riot Games. No usa la API oficial de Riot: lee el cliente local y datos públicos (Data Dragon, Meraki, Lolalytics, op.gg).

## Descargar e instalar (Windows 10/11)

**[⬇ Descargar la última versión](https://github.com/adanprietobenegas/LOL-E/releases/latest)**

1. En la página de *Releases*, baja a **Assets** y descarga **`LOL-E-x.y.z.zip`** (lleva el instalador y las instrucciones). Si prefieres ir directo, descarga **`Instalar-LOL-E-x.y.z.exe`**.
2. Descomprime el `.zip` (clic derecho → *Extraer todo*) y haz doble clic en **`1_Instalar-LOL-E-x.y.z`**.
3. Si Windows muestra «SmartScreen» (el instalador no está firmado), pulsa **Más información → Ejecutar de todos modos**.
4. Abre **LOL-E** desde el menú Inicio, deja abierto el cliente de League of Legends y entra en una selección de campeón.

No hace falta tener Python ni nada más. Se actualiza solo: al abrirse avisa si hay una versión nueva. Para desinstalar: *Configuración → Aplicaciones*. Más detalle en `docs/LEEME_PRIMERO.txt` (también va dentro del `.zip`).

> Los archivos `latest.json` que ves en los Releases los usa la app para detectar actualizaciones; no tienes que descargarlos.
## Qué hay aquí

| Carpeta / archivo | Contenido |
|---|---|
| `app.py` | Punto de entrada |
| `lol_advisor.py` | Motor de recomendación y lectura del cliente |
| `gui.py`, `ui_*.py` | Interfaz (ventana, historial, repertorio, enfrentamientos, build…) |
| `meta.py`, `matchups.py`, `builds.py`, `trends.py`, `items.py`, `runes.py`, `players.py`, `history.py` | Datos y análisis |
| `updater.py` | Actualización automática (lee un `latest.json`) |
| `build_release.py` | Genera el instalador (PyInstaller + Inno Setup) y el `.zip` |
| `docs/` | Léeme, notas de versión, guía visual, estado y pendientes, capturas |
| `guide.py`, `ui_guide.py`, `ui_opp.py` | Guía de juego y duelo de línea (Data Dragon) y selector de rival de línea |
| `itemset.py`, `sounds.py` | Envío de la build al cliente como conjunto de objetos; sonidos por fase |
| `herramientas/` | Scripts de demo y pruebas de modos de juego; `tests_unitarios.py` (14 pruebas de la lógica, sin cliente ni ventana: `python herramientas/tests_unitarios.py`) |

## Para desarrolladores: ejecutarlo desde el código

Lo normal es usar el instalador. Esto es solo si quieres tocar el código.

Requiere Python 3.12.

```bash
pip install -r requirements.txt
python app.py
```

## Crear el instalador

Requiere además Inno Setup 6.

```bash
python build_release.py
```

El resultado queda en `release/` (no se sube al repositorio; se publica como *Release* de GitHub).

## Versiones

Numeración X.Y.Z: Z arreglos, Y funciones nuevas visibles, X cambios grandes. Historial en `docs/NOTAS_DE_VERSION.txt`.

## Aviso legal

LOL-E no está respaldado por Riot Games y no refleja las opiniones de Riot Games ni de nadie oficialmente involucrado en la producción o gestión de League of Legends. League of Legends y Riot Games son marcas comerciales o marcas registradas de Riot Games, Inc.

LOL-E no modifica el juego ni lee su memoria: solo consulta el cliente local mediante su interfaz LCU, y datos públicos de terceros (Data Dragon, Meraki, Lolalytics, op.gg, OneTricks). Cada fuente tiene sus propias condiciones de uso; los datos se guardan en caché y se consultan con moderación. Licencia del código: MIT (ver LICENSE).