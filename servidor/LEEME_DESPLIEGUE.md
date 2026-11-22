# Contador anónimo de instalaciones de LOL-E: cómo desplegarlo (solo para el administrador)

## Qué es

Un programita (un *Cloudflare Worker*) que vive en internet, gratis, y hace tres cosas:

1. Recibe un aviso diario de cada LOL-E **que haya dicho «sí»** (un número aleatorio y la versión).
2. Deduce la **zona aproximada** (comunidad autónoma o región) de la conexión de ese aviso y **descarta la dirección IP**. Guarda solo país, región y unas coordenadas
   redondeadas a medio grado (unos 50 km).
3. Te enseña, solo a ti y con una clave, un **panel con mapa, activas por día, versiones y regiones** (y un resumen dentro de la propia LOL-E, en Ajustes › Administrador).

Nada de esto funciona hasta que lo despliegas y pones su dirección en `stats.py`: mientras `STATS_URL` esté vacío, LOL-E ni pregunta ni envía nada.

Coste: **0 €**. El plan gratuito de Cloudflare permite 100.000 peticiones al día y 1.000 escrituras al día; cada instalación escribe una vez al día, así que aguanta ~1.000 instalaciones.

## Antes de empezar (una sola vez)

1. Una cuenta gratuita de Cloudflare: <https://dash.cloudflare.com/sign-up> (basta un correo; no pide tarjeta).
2. Node.js (versión LTS): <https://nodejs.org>. Se instala como cualquier programa. Comprueba en una terminal: `node -v`.

## Despliegue (unos 10 minutos)

Abre una terminal en la carpeta `servidor` de este proyecto y ejecuta, en orden:

```bash
npx wrangler login
```
Se abre el navegador para que autorices a Wrangler con tu cuenta de Cloudflare.

```bash
npx wrangler kv namespace create STATS
```
Imprime algo como `id = "a1b2c3…"`. **Copia ese id y pégalo en `wrangler.toml`**, en lugar de `PEGA_AQUI_EL_ID`.

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```
Eso genera tu **clave de administrador** (apúntala en un gestor de contraseñas; quien la tenga ve el panel). Ahora guárdala en el servidor:

```bash
npx wrangler secret put ADMIN_TOKEN
```
Pega la clave cuando la pida (mínimo 16 caracteres; con menos, el panel queda cerrado a propósito).

```bash
npx wrangler deploy
```
Al terminar muestra la dirección, algo como `https://lole-stats.TU-SUBDOMINIO.workers.dev`. **Esa es tu `STATS_URL`.**

## Probarlo

1. Abre `https://lole-stats.TU-SUBDOMINIO.workers.dev/panel?k=TU_CLAVE` → debe salir el panel con todo a 0.
2. Un aviso de prueba (desde PowerShell o una terminal; el id es inventado):

```bash
curl -X POST https://lole-stats.TU-SUBDOMINIO.workers.dev/ping -H "Content-Type: application/json" -d "{\"id\":\"3f2b9c1e-8a47-4d3b-9e60-1a2b3c4d5e6f\",\"v\":\"1.23.0\"}"
```
   Recarga el panel: sale 1 instalación en tu zona. Bórrala con:

```bash
curl -X POST https://lole-stats.TU-SUBDOMINIO.workers.dev/olvidar -H "Content-Type: application/json" -d "{\"id\":\"3f2b9c1e-8a47-4d3b-9e60-1a2b3c4d5e6f\"}"
```
3. Sin clave o con una mala, `/panel` y `/resumen` responden «No encontrado»: es lo esperado.

## Conectar LOL-E

1. En `stats.py`, pon la dirección: `STATS_URL = "https://lole-stats.TU-SUBDOMINIO.workers.dev"` (o dile a Claude «la URL es …» y lo hace).
2. Publica una versión nueva (el flujo de siempre). Quien se actualice verá **una sola vez** una ventana que explica qué se envía y qué no, con «No, gracias» destacado. Hasta que
   alguien diga «Sí», no se envía nada de su instalación. Se puede cambiar en Ajustes › Privacidad (al apagarlo se borra el registro de esa instalación en el servidor).
3. **Tu pantalla de administrador dentro de LOL-E:** abre `%LOCALAPPDATA%\LOL-E\config.json` (con LOL-E cerrada) y añade tu clave:
   ```json
   "admin_token": "TU_CLAVE"
   ```
   Al abrir Ajustes verás, solo tú, la sección **Administrador**: instalaciones totales y activas (hoy, 7 y 30 días) y el botón **«Abrir el panel de uso (mapa)»**.
   El mismo panel se abre desde cualquier navegador con `…/panel?k=TU_CLAVE` (guárdalo en favoritos, también en el móvil).

## Cómo leer el panel

- **Instalaciones**: números aleatorios distintos que han avisado alguna vez y siguen registrados. Una persona que reinstala LOL-E puede contar dos veces (cada instalación crea su número).
- **Activas hoy / 7 / 30 días**: instalaciones que han avisado en ese tramo. Como el aviso es diario y solo con la app abierta, son un mínimo razonable de uso real.
- **Mapa y regiones**: puntos aproximados (±50 km). Quien use VPN o datos móviles puede salir en otra zona.
- **Activas por día**: barras doradas = activas; la parte verde = instalaciones nuevas ese día.

## Ver cómo queda sin desplegar nada

Desde la carpeta `servidor`: `python -m http.server 8123` y abre <http://localhost:8123/panel_demo.html> (datos inventados). Las pruebas del servidor están en
<http://localhost:8123/prueba.html> (deben acabar en «RESULTADO: TODO BIEN»).

## Mantenimiento

- **Cambiar la clave**: `npx wrangler secret put ADMIN_TOKEN` otra vez (y actualizar `admin_token` en tu `config.json`).
- **Actualizar el servidor** tras tocar `worker.js`: `npx wrangler deploy`. Si lo creaste desde el panel web de Cloudflare: Workers y Pages › tu Worker › «Edit code», pega todo `worker.js` (borrando lo anterior) y «Deploy».
- **Borrar todos los datos**: `npx wrangler kv key delete --binding=STATS idx`. **Apagar el servicio**: borra el Worker en el panel de Cloudflare; LOL-E lo ignora (los avisos fallan en silencio).
- **Quién puede ver qué**: los datos viven solo en tu cuenta de Cloudflare. El Worker no escribe registros de peticiones ni guarda IP.

## Reglas para no meterse en líos (RGPD)

- La función es **opt-in** (apagada hasta que el usuario acepta) y se explica en la ventana de permiso y en `docs/PRIVACIDAD.md`.
- No ampliar lo que se envía sin volver a pedir permiso. El texto «Se envía / No se envía» de la ventana y de Ajustes debe seguir siendo cierto.
- Si alguien pide que borres su registro: puede apagar el interruptor (se borra solo) o puedes borrar todo con el comando de arriba.
