# Informe: comercializar LOL-E (legal, anuncios, monetización) y fondos de la interfaz

Redactado el 23/11/2026. **No es asesoramiento legal.** Lo que dice Riot cambia: antes de cualquier paso comercial hay que releer las páginas fuente (enlaces abajo).
Marcas: «(Riot)» = texto literal o resumido de una página oficial de Riot leída hoy; «(Overwolf)» = interpretación de un tercero, no vale como regla de Riot; «(general)» = conocimiento general a confirmar.

## 1. Qué dice Riot (fuentes leídas el 23/11/2026)

Fuentes: [Políticas generales](https://developer.riotgames.com/policies/general) (actualizada 29/05/2025), [Políticas por juego](https://developer.riotgames.com/policies/game-specific) (21/08/2026),
[Documentación de League](https://developer.riotgames.com/docs/lol), [Aplicaciones de terceros (soporte)](https://support.riotgames.com/en-us/riot/events/third-party-applications) (feb. 2025),
[Legal Jibber Jabber](https://www.riotgames.com/legal), [resumen de Overwolf](https://dev.overwolf.com/ow-native/guides/game-compliance/riot-games).

### Registro y aprobación
- (Riot) Si el producto atiende a jugadores hay que **registrarlo en el Developer Portal aunque no use las API oficiales**. Para usar la API del cliente (LCU) también hay que registrarlo.
- (Riot) La LCU «no está oficialmente soportada» para terceros: sin garantías de documentación, estabilidad ni aviso de cambios (resumen del agente; releer). **LOL-E depende de ella y del puerto 2999 local.**
- (Riot) **Monetizar solo si el producto está registrado y con estado «Approved» o «Acknowledged»**. No hay en las páginas leídas plazos, tasas ni proceso detallado. La página `/app-type` redirige a un inicio de sesión: hay que entrar con la cuenta de desarrollador para ver los tipos de aplicación.
- (Riot) Claves: una clave de producción por producto; «la clave no puede ir en el código, sobre todo si se distribuye un binario». (LOL-E no usa clave de Riot hoy; si se usara habría que ponerla en un servidor propio.)

### Monetización permitida
- (Riot) Debe haber **un nivel gratuito, que «puede incluir publicidad»**. Cobrar es posible con suscripciones, donaciones o crowdfunding, inscripciones a torneos y monedas del juego no canjeables. El contenido de pago debe ser «transformador» (no limitarse a reproducir datos públicos).
- (Riot) Nada de apuestas ni juego; no «abusar» de los jugadores ni precios injustos (lo decide Riot).
- (Riot) «No puedes poner anuncios en propiedades de Riot: dentro del juego, pantallas de carga y el cliente de Riot.» Una ventana propia fuera del juego no es propiedad de Riot, pero **las páginas leídas no dicen expresamente si se permiten anuncios dentro de una app de terceros** → preguntarlo por el Developer Portal.
- (Overwolf) Desde 2025 prohíbe anuncios flotantes/superpuestos en el juego; y dice que desde el 1/11/2026 solo aprueba apps con su monetización (solo afecta a quien publique en su plataforma).

### Integridad del juego (lo que más puede afectar a LOL-E)
- (Riot, literal) No se puede «usar o incorporar información que no esté en el cliente del juego y dé ventaja competitiva (p. ej. seguir los tiempos de recarga de ultis enemigos)».
- (Riot, literal) «No pueden proporcionar información específica de la partida que el jugador no conocería antes.» «Apps que dicten decisiones del jugador.» «No pueden identificar ni analizar a jugadores deliberadamente ocultos por el juego.»
- (Riot, literal) «No pueden crear alternativas a los sistemas de clasificación oficiales (p. ej. calculadoras de MMR o ELO).» «Pueden destacar decisiones importantes y dar varias opciones» (es decir, recomendar con opciones está permitido; decidir por el jugador no).
- (Riot, literal) **«No pueden mostrar porcentajes de victoria de aumentos (Augments) ni de objetos del modo Arena.»**
- (Riot, literal) Overlays con **datos estáticos disponibles antes de la partida** están aprobados.
- (Riot, soporte) No debe haber software que comprometa la integridad «desde que pulsas Jugar hasta que sales»: exponer información oculta, actuar por el jugador, **sacar conclusiones durante la partida** («primero juega, luego analiza»), ampliar el campo de visión.
- (LOL-E: los avisos en vivo de picos del rival se quitaron el 26/11/2026.)
- (Overwolf, no Riot) Prohíbe notificaciones de picos de poder, seguimiento de recargas/hechizos enemigos y «temporizadores de ulti»; en selección de campeón de Solo/Dúo anonimizar a los no acompañantes («Aliado #»); no mostrar datos de «Classic» ni Brawl agregados (esto último no aparece en las páginas de Riot que se leyeron: **verificar**).

### Marca y propiedad intelectual
- (Riot) Obligatorio y visible: «[Producto] no está respaldado por Riot Games y no refleja las opiniones de Riot Games ni de nadie implicado oficialmente…» (+ texto de marcas). Usar Data Dragon y el Press Kit; no copiar el estilo o función de productos de Riot; logos de Riot solo cuando sea inevitable.
- (Riot) Cuidado con apps que dejan usar sus recursos gratis (arte de campeones, modelos).
- (Riot) Historial de partidas personalizadas: no mostrarlo públicamente sin consentimiento del jugador.

## 2. Cruce con LOL-E: puntos a revisar antes de cualquier uso comercial

| Función de LOL-E | Riesgo con las reglas de arriba | Qué hacer |
|---|---|---|
| Aumentos/mejoras (`augments.py`, ARAM Caos) | Riot prohíbe porcentajes de victoria de aumentos y de objetos de Arena | **Ya cumplido en el código** (`augments.py` solo cuenta elecciones, sin victorias). Revisar que `aram_builds.py` / `ui_mayhem.py` no muestren winrates de objetos en modos tipo Arena |
| Temporizadores de partida (dragón, Heraldo, Barón, inhibidores) | Riot cita como ejemplo prohibido las **recargas de ultis enemigos**; los objetivos son información del propio juego (eventos de la API local), pero «temporizadores» llaman la atención | Preguntar al soporte del Developer Portal por temporizadores de objetivos; no incluir nunca recargas/hechizos enemigos |
| Consejos en partida («sacar conclusiones durante la partida», «dictar decisiones») | Riot no quiere conclusiones en partida | Revisar el tono de la pantalla En vivo: mostrar datos, no órdenes |
| Estimación de PL ganados/perdidos | «Alternativas a la clasificación oficial: calculadoras de MMR/ELO» | El PL real viene del cliente (diferencia entre antes y después); las estimaciones (+21/−19 medio) quizá sean un caso límite: valorar quitarlas o rotularlas como estimación histórica propia |
| Selección de campeón: recomendaciones con rivales/aliados | Anonimato en Solo/Dúo (Overwolf); «no analizar jugadores ocultos» (Riot) | Comprobar qué nombres se enseñan en selección de campeón y en qué colas; anonimizar si hace falta |
| Datos de Classic/Brawl agregados | (Overwolf) no aprobados | Ver si LOL-E agrega datos de esas colas (op.gg/Lolalytics) |
| Notas de parche de Riot: texto y banner copiados en la app | Contenido de Riot; las notas son públicas pero reproducirlas íntegras con fines comerciales es una zona gris | Enlazar siempre a la fuente, citar y no revender el contenido |
| Imágenes de campeones/objetos (Data Dragon) | Permitido para desarrollo (Riot pide Data Dragon) | Mantener Data Dragon como única fuente |
| Aviso «no respaldado por Riot» | Obligatorio y visible | **Ya existe** (Ajustes › Acerca de, guía y LEEME). Valorar enseñarlo también en la pantalla de inicio si se monetiza |
| Datos de otras webs (op.gg, Lolalytics, onetricks) | Sus condiciones de uso (scraping, uso comercial) | Revisar términos antes de monetizar; una app comercial que raspa webs ajenas es más arriesgada que una gratuita |
| Contador de instalaciones | RGPD/privacidad | Ya es opt-in y anónimo; si hay anuncios habrá que ampliar la política de privacidad |

### API oficial de Riot (https://developer.riotgames.com/apis)
Lista las API web soportadas (match-v5, league-v4, maestría, invocador…), todas con clave de desarrollador y límites de peticiones. Sirve para (1) registrar el producto y pedir la clave (paso previo a monetizar) y
(2) sustituir datos hoy leídos del cliente o de webs externas (historial, rango) por fuentes soportadas y más estables. La clave debe estar en un servidor propio (p. ej. el Worker de Cloudflare), nunca en la app (Riot lo prohíbe).
La selección de campeón y los datos en vivo seguirán viniendo del cliente local. A estudiar: qué cobertura da frente a lo que usa LOL-E y la limitación de peticiones para muchos usuarios.

## 3. Formas de monetizar (de menos a más riesgo)

1. **Donaciones** (Ko-fi, GitHub Sponsors, Buy Me a Coffee): Riot las lista como forma válida (con producto registrado y aprobado). Un botón «Apoyar LOL-E» en Ajustes y la página de GitHub; sin anuncios, sin cambios en rendimiento. Es lo más seguro.
2. **Patrocinio / enlace de afiliado visible y estático**: una tarjeta propia (imagen + texto + enlace) sin código de terceros, sin seguimiento. Control total del contenido (sin apuestas, sin contenido inadecuado).
3. **Versión de pago opcional (suscripción)**: Riot exige un nivel gratuito y que el pago sea «transformador»: p. ej. historia ilimitada en la nube, exportaciones, temas. No bloquear lo esencial.
4. **Redes de anuncios** (AdSense, etc.): peor opción técnica y de privacidad (ver §5); además la política dice que el nivel gratuito *puede* incluir publicidad pero no aclara si se permite en una app de terceros.

## 4. Anuncios «a la izquierda, debajo de Parche»: cómo hacerlo sin molestar ni gastar rendimiento

Reglas propias que propongo (coinciden con lo que pidió el usuario):
- **Solo en reposo**: la tarjeta **no existe** (ni se carga) en cola, aceptar partida, selección de campeón, partida ni pantalla final. Reutilizar `busy()` de `gui.py`; al entrar en cualquiera de esas fases se oculta y se cancela toda descarga.
- **Sin web embebida ni JavaScript de terceros**: una imagen estática (p. ej. 200×110 px) descargada de un servidor propio (Cloudflare) **como mucho una vez al día** y cacheada en disco; clic abre el navegador. Coste de CPU/memoria ≈ 0 y sin rastreo.
- **Ubicación**: debajo de «Parche» en el carril izquierdo, tamaño fijo, sin animación, sin sonido, sin ventanas emergentes; botón «Ocultar» (y recordarlo) y ajuste en Privacidad.
- **Nunca** en el cliente de Riot ni encima del juego (prohibido por Riot); **nunca** en «En vivo» durante la partida.
- **Contenido propio** (sin redes de anuncios): evita consentimiento de cookies, perfilado y que aparezca algo inadecuado.
- Implementación estimada: un `CTkFrame` con una `CTkImage`, un módulo `patrocinio.py` (descarga con caché y tope de tamaño, validación de que sea PNG/JPG) y una ruta `/anuncio` en el Worker. Pocas horas; con pruebas de «oculto cuando `busy()`».
- Si algún día se usa una red de anuncios: exige **web embebida** (WebView2), consentimiento RGPD (CMP), políticas de cookies y más memoria/CPU. No lo recomiendo.

## 5. Asuntos legales y administrativos (general, España/UE; confirmar con una gestoría o abogado)

- **Ingresos**: tributación como autónomo (alta en Hacienda y Seguridad Social, IVA) o sociedad; incluso las donaciones/ingresos regulares cuentan.
- **Marca y licencia**: el nombre «LOL-E» recuerda a «LoL»; revisar que no genere confusión con las marcas de Riot (usar el aviso de no respaldo). Elegir una licencia para el código (hoy no hay una declarada; valorar si abrirlo o cerrarlo).
- **Aviso legal y condiciones de uso** (LSSI), **política de privacidad** ampliada (RGPD): qué datos, base legal (consentimiento), quién es el responsable, derechos de acceso/borrado (ya se borra al desactivar), contacto.
- **Anuncios**: si hubiera terceros, consentimiento previo y revocable; contenido adecuado (nada de apuestas/alcohol/juego; Riot prohíbe apuestas).
- **Soporte y responsabilidad**: una app de pago implica garantías de consumidor (reembolsos, 14 días de desistimiento en venta online, etc.).
- **Dependencia de Riot**: pueden cambiar o retirar la LCU o revocar el registro; no hay obligación de avisar. Un negocio sobre esto es frágil.

## 6. Plan sugerido (ordenado)

1. **Ahora, sin comercializar**: revisar y adaptar lo marcado «prioridad alta» en la tabla §2 (estimación de PL, nombres en selección, winrates de objetos en modos tipo Arena). Registrar LOL-E en el Developer Portal (gratuito) para tener estado «Acknowledged/Approved» y preguntar por anuncios y temporizadores de objetivos. Guardar la respuesta por escrito.
2. **Donaciones** (botón «Apoyar» en Ajustes y GitHub): menor riesgo, tras el registro.
3. **Tarjeta de patrocinio estática** (§4) solo si Riot confirma que se permite y con las reglas propias de arriba.
4. **Suscripción opcional** más adelante, con nivel gratuito completo.
5. Asesoría fiscal/legal antes del primer ingreso.

## 7. Fondos e imagen de la interfaz (consulta del 23/11/2026)

- La app ya tiene **12 temas** en Ajustes (5 de color: Abisal, Neón medianoche, Brasa, Bosque, Cloud Dancer; 7 looks: Terminal, Papel, Blueprint, Hextech, Arcade, Neón Tokio, Océano), así que cambiar el tono de fondo ya es posible.
- Un **degradado real** es más difícil: Tk no tiene widgets transparentes; las tarjetas y bloques llevan color sólido y cada contenedor pinta su propio fondo. Un degradado visible solo en los márgenes/carril exigiría poner una imagen de fondo en la ventana y hacer «transparentes» los contenedores (que en CustomTkinter heredan un color sólido, no la imagen). Opciones realistas:
  - **A. Tonos por zona (sólidos)**: carril, cabecera y contenido con tonos ligeramente distintos del mismo color (efecto «bandas»), sin degradado: barato y estable.
  - **B. Imagen/degradado solo en márgenes y carril** (un `Canvas` detrás, contenedores principales sin fondo propio): trabajo medio y arriesgado para el rendimiento al redimensionar.
  - **C. Degradado dentro de las tarjetas** (cabeceras de tarjeta con una imagen generada): sencillo, pero la preferencia del usuario es sobria (franja y aro sí; degradado con icono no).
- Maquetas hechas a partir de la captura real (el degradado reemplaza el fondo oscuro; **es el caso ideal**, el resultado real dependería de la opción elegida): `docs/rediseno/fondos/comparativa_fondos.png` y `fondo_A.png … fondo_D.png` (A azul medianoche, B violeta profundo, C brasa, D resplandor dorado).
- Pendiente de decidir: qué variante gusta y si compensa el coste (recomendación: A «tonos por zona» con el color de la variante elegida; el degradado completo solo si se elige B y se mide el coste).
