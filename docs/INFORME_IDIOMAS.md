# Informe: LOL-E en varios idiomas (español + inglés primero)

Redactado el 23/11/2026 para trabajarlo en próximas sesiones. Objetivo del usuario: portugués, inglés, francés y alemán a largo plazo; **de momento factible: español + inglés**.
Nada de esto está implementado. Lo marcado «(verificado)» se comprobó en el código o en la red; lo marcado «(general)» es conocimiento general o de fuentes externas y conviene
confirmarlo al implementar.

## 1. Estado actual (verificado en el código)

- Todos los textos están escritos en español **dentro del código**: unas **1 950 cadenas con tildes o signos españoles** (hay más sin tildes), en ~60 módulos.
  Los que más: `novedades.py` (232), `ui_sections.py` (137), `gui.py` (124), `tour.py` (110), `lol_advisor.py` (103), `ui_views.py` (91), `ui_analysis.py` (89), `ui_history.py` (81),
  `ayuda.py` (80), `ui_patch.py` (72), `ui_build.py` (71), `analysis.py` (70).
- No hay sistema de traducción. Lo único parecido a idioma: `lol_advisor.py:325` lee `/riotclient/region-locale` del cliente (solo para la región).
- **Fuentes externas y su idioma:**
  - Data Dragon: nombres de campeones en `en_US` (`lol_advisor.py:207`); objetos, runas y guía de campeón en `es_ES` (`items.py:18`, `runes.py:31`, `guide.py:48`).
  - Notas de parche de Riot: `leagueoflegends.com/es-es/...` (`parche.py:24-25`) y el analizador busca textos en español (p. ej. «Corrección de errores», cabeceras de sección).
  - op.gg y Lolalytics: se usan por identificadores (región, campeón), así que casi no dependen del idioma; hay que revisar qué texto se extrae de op.gg.
  - Data Dragon ofrece 28 idiomas (verificado en `https://ddragon.leagueoflegends.com/cdn/languages.json`): incluye `en_US`, `es_ES`, `es_MX`, `es_AR`, `pt_BR`, `fr_FR`, `de_DE`, `it_IT`… Es decir, nombres de campeones, objetos y runas se pueden pedir en cualquiera.
- **Claves internas en español** que se guardan o comparan: `ROLE_ES` (`analysis.py:20`: «Superior», «Jungla»…), `LANE_NAMES` (`matchups.py:10`), `LANE_ES` (`parche_stats.py:15`),
  y `patrones.py` compara con `"línea"` (líneas 110 y 150). Hay que separar «clave» (`TOP`, `JUNGLE`…) de «texto mostrado» antes de traducir, y revisar qué se guarda en disco con texto en español
  (historial, `lp.json`, análisis) para no romper datos de usuarios existentes (migración o claves nuevas).
- **Archivos de texto largo**: `docs/guia.template.html` (guía de la app; `build_release.py:72`), `docs/PRIVACIDAD.md`, `docs/NOTAS_DE_VERSION.txt`, textos del instalador (`build_release.py`), `ayuda.py`, `tour.py`.
- Hay cadenas **con datos** (números, nombres, plurales): «ganas 21 PL», «hace 3 días», «el 62 % de tus 8 muertes…». Cada idioma las construye distinto.

## 2. Opciones técnicas para traducir (de más simple a más completa)

### A. Diccionario propio con el texto español como clave (la más sencilla; **recomendada para empezar**)
`_("texto en español")` devuelve la traducción si existe y, si no, el mismo texto. Un archivo `idiomas/en.json` con `{"texto español": "English text"}`.
- Ventajas: **migración incremental** (se envuelve una pantalla cada vez; lo no traducido sigue saliendo en español, nunca se rompe nada); sin dependencias; se prueba con tests.
- Plurales y datos: usar `.format` con marcadores `{n}` y una función `plural(n, uno, otros)`; para español e inglés basta «uno / otros». Portugués, francés y alemán tampoco necesitan más
  (francés trata el 0 y el 1 como singular: pequeño detalle).
- Inconvenientes: la clave es el texto, así que **cambiar una frase en español obliga a actualizar su traducción**; una herramienta de comprobación debe avisar de claves huérfanas y de textos sin traducir.

### B. `gettext` de la biblioteca estándar (PO/MO)
Estándar, mismo patrón `_("texto")` y plurales de verdad (`ngettext`). Flujo: extraer con `pybabel extract` (Babel) o `pygettext`, traducir `.po`, compilar a `.mo`, carpeta `locale/<idioma>/LC_MESSAGES/lole.mo`.
- Ventajas: herramientas y plataformas de traducción colaborativa (Weblate, Crowdin, Transifex) que leen PO directamente; plurales correctos para todos los idiomas.
- Inconvenientes: más pasos de construcción (compilar `.mo`), incluir `locale/` en el ejecutable y localizarlo cuando va empaquetado (PyInstaller: `datas` en el `.spec` y ruta bajo `sys._MEIPASS`) (general).
- Fuentes consultadas: [guía de gettext en Python (Phrase)](https://phrase.com/blog/posts/translate-python-gnu-gettext/), [Babel: catálogos de mensajes](https://babel.pocoo.org/en/stable/messages.html), [comparación JSON/gettext (Phrase)](https://phrase.com/blog/posts/python-localization).

### C. Project Fluent (`fluent.runtime`)
Archivos `.ftl` donde el traductor controla plurales, género y variantes. Más potente, pero añade dependencia (usa Babel) y es más lento con plurales (según fluent-compiler); selección de idioma y
alternativas hay que programarlas (general). Excesivo para una app de este tamaño.
- Fuentes: [Using fluent.runtime](https://projectfluent.org/python-fluent/fluent.runtime/dev/usage.html), [comparaciones](https://fluent-compiler.readthedocs.io/en/stable/implementations.html).

### D. `tkinter-msgcat` (msgcat de Tcl/Tk)
Existe como paquete pequeño, pero sin mantenimiento reciente (2022) y no sirve para textos fuera de widgets; descartado.

**Recomendación:** empezar con **A** (diccionario con clave en español, JSON) y, si se suman idiomas con comunidad o más complejidad, **migrar a B** (la clave sigue siendo el texto, así que pasar de JSON a PO es mecánico: un script convierte `en.json` a `en.po`).

## 3. Cómo extraer las cadenas sin hacerlo a mano

1. Un script con `ast` que recorra los `.py` y liste las cadenas literales con caracteres españoles (o las que están en llamadas a `CTkLabel(text=…)`, `status(…)`, `messagebox`, etc.), con archivo y línea.
2. Revisión por pantalla: clasificar «texto visible» / «clave interna» / «dato» y envolver los visibles con `_()`. Hacerlo **módulo a módulo**, con un test por módulo que compruebe que, con idioma `es`, el resultado es idéntico al actual (evita regresiones).
3. Prueba global: un test que cargue cada idioma y compruebe que todas las claves usadas existen y que los `{marcadores}` coinciden entre español e inglés.
4. Cadenas construidas por partes («Hace » + n + « días») hay que reescribirlas como frase completa con marcadores antes de traducirlas.

## 4. Qué depende del idioma además de los textos

| Elemento | Qué hay que hacer |
|---|---|
| Nombres de campeones, objetos, runas | Pedir Data Dragon con el idioma elegido (`en_US`, `es_ES`, `pt_BR`, `fr_FR`, `de_DE`). Cachear por idioma (la caché actual asume `es_ES`/`en_US` fijos). |
| Notas de parche (`parche.py`) | Riot publica por idioma (`/es-es/`, `/en-us/`…). El analizador depende de textos españoles; hay que parametrizar los literales por idioma o basar el análisis en la estructura HTML. Opción intermedia: en inglés leer `/en-us/` con sus propios literales. **Es lo más delicado.** |
| Roles y líneas | Separar clave (`TOP`, `JUNGLE`, `MIDDLE`, `BOTTOM`, `SUPPORT`) del texto; traducir solo al mostrar. |
| Fechas, números, «hace N días» | Funciones de formato por idioma (`15,3 %` en español, `15.3%` en inglés). |
| Guía HTML, PRIVACIDAD, instalador, notas de versión | Un archivo por idioma (`guia.es.html`, `guia.en.html`) y plantilla común; el instalador (Inno/NSIS, según `build_release.py`) admite varios idiomas (confirmar). |
| Ayuda, tour, novedades | Textos largos: sacarlos a archivos por idioma; `novedades.py` solo traducir lo reciente (las versiones antiguas pueden quedarse en español). |
| Ventana de permiso del contador | Debe estar traducida desde el principio: es el texto más sensible. |
| Servidor (panel de administrador) | Solo lo ves tú; puede seguir en español. |

## 5. Elegir el idioma

- Por defecto: el del cliente de League (`/riotclient/region-locale` → `locale`, p. ej. `es_ES`, `en_US`, `pt_BR`) o, si no hay cliente, el de Windows. Selector manual en Ajustes › Idioma.
- Cambiar de idioma: lo más simple es **reiniciar** la app tras el cambio (evita repintar toda la interfaz en caliente); hay un mecanismo de reinicio ya usado para actualizaciones.
- Regla de caída: idioma pedido → inglés → español. Una clave sin traducir nunca debe mostrar un hueco.

## 6. Plan por fases (propuesta)

1. **Base** (sin cambios visibles): módulo `i18n.py` (`_()`, `plural()`, carga de `idiomas/*.json`, idioma activo, caída), tests, y herramienta `herramientas/extraer_textos.py` que lista y comprueba cadenas.
2. **Migración a `_()` por pantallas**, de las menos a las más complejas (Ajustes, ventana de permiso, Historial, Plan, Selección…), con prueba de «en español queda idéntico».
3. **Inglés**: traducción de `en.json` (primer borrador asistido y **revisión por alguien con inglés nativo o muy bueno**), selector en Ajustes, Data Dragon por idioma, formatos.
4. **Parche y fuentes** en inglés (la parte delicada), guía, PRIVACIDAD, instalador, ayuda y tour.
5. **Más idiomas** (pt_BR, fr_FR, de_DE): solo archivos de textos + revisión nativa + literales del analizador de parche. Valorar pasar a PO/Weblate si hay colaboradores.

Estimación orientativa (general, a validar): fases 1-2 son la parte pesada (muchas sesiones, mecánicas); la fase 3 depende de la revisión de la traducción; cada idioma nuevo después es pequeño.

## 7. Riesgos y decisiones abiertas

- **Mantenimiento**: cada texto nuevo hay que traducirlo en todos los idiomas. Mitigación: test que falla si falta una clave en `en.json` y la regla «sin traducir = español» para no bloquear.
- **Calidad**: las traducciones automáticas necesitan revisión humana, sobre todo términos del juego (cada región tiene su vocabulario oficial: se pueden sacar de los textos del propio cliente/Data Dragon).
- **Datos guardados con texto español**: revisar (historial, análisis, ajustes) antes de cambiar claves.
- **Notas de parche**: el analizador es frágil por idioma; decidir si inglés lee `/en-us/` con literales propios.
- **Decisiones del usuario pendientes**: ¿empezar por español + inglés? ¿selector automático (cliente) o solo manual? ¿traducción asistida y quién la revisa? ¿publicar el inglés en una versión propia (p. ej. 1.25.0)?

## 8. Primeros pasos concretos para la próxima sesión

1. Escribir `herramientas/extraer_textos.py` (recuento y listado por módulo) y guardar el resultado como línea base.
2. Crear `i18n.py` + `idiomas/en.json` + tests; migrar **una** pantalla pequeña (la ventana de permiso) como prueba de concepto.
3. Parametrizar `items.py`, `runes.py`, `guide.py` y la caché de nombres con el idioma de Data Dragon.
4. Revisar `parche.py` y listar los literales en español que usa para decidir cómo parametrizarlos.
