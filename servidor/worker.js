// LOL-E · contador anónimo de instalaciones (Cloudflare Worker + KV). Solo para quien mantiene LOL-E.
//
// Qué recibe de cada LOL-E que haya dicho «sí»: un número aleatorio de instalación y la versión. La zona (país, región y unas coordenadas REDONDEADAS a medio grado,
// unos 50 km) la deduce de la conexión con los datos que Cloudflare ya añade a la petición (request.cf). NO guarda la dirección IP ni la cabecera de nadie, no escribe
// registros y no usa cookies. Todo se guarda en una sola clave de KV («idx») con un registro mínimo por instalación.
//
// Rutas:  POST /ping {id, v}      una instalación avisa (como mucho una vez al día)
//         POST /olvidar {id}      una instalación retira el permiso: se borra su registro
//         GET  /resumen?k=CLAVE   datos agregados en JSON (solo el administrador)
//         GET  /panel?k=CLAVE     panel con mapa y gráficas (solo el administrador)
// Cualquier otra cosa: 404. La CLAVE es el secreto ADMIN_TOKEN del Worker (mínimo 16 caracteres).

const ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const VER_RE = /^\d{1,3}\.\d{1,3}\.\d{1,3}$/;
const KEEP_DAYS = 120;          // días de actividad que se recuerdan por instalación
const MAX_BODY = 512;           // bytes que se aceptan en un aviso
const MAX_INSTALLS = 20000;     // tope de seguridad del índice

export const dayNumber = (ms) => Math.floor(ms / 86400000);
export const dayIso = (n) => new Date(n * 86400000).toISOString().slice(0, 10);

/** Zona aproximada a partir de request.cf (país, región, coordenadas a medio grado). */
export function coarse(cf) {
  const c = cf || {};
  const half = (x) => (x !== undefined && x !== null && x !== "" && !isNaN(+x) ? Math.round(+x * 2) / 2 : null);
  return {
    c: String(c.country || "").slice(0, 2).toUpperCase(),
    r: String(c.region || "").slice(0, 60),
    la: half(c.latitude),
    lo: half(c.longitude),
  };
}

/** Valida un aviso: devuelve {id, v} o null. */
export function parsePing(text) {
  if (typeof text !== "string" || text.length > MAX_BODY) return null;
  let o;
  try { o = JSON.parse(text); } catch { return null; }
  if (!o || typeof o !== "object" || !ID_RE.test(String(o.id)) || !VER_RE.test(String(o.v))) return null;
  return { id: String(o.id), v: String(o.v) };
}

/** Aplica un aviso al índice (objeto id → registro). Devuelve {idx, changed}; `changed` false si no hay nada nuevo que guardar. */
export function applyPing(idx, id, v, geo, today) {
  const cur = idx[id];
  if (!cur) {
    if (Object.keys(idx).length >= MAX_INSTALLS) return { idx, changed: false };
    idx[id] = { f: today, l: today, v, c: geo.c, r: geo.r, la: geo.la, lo: geo.lo, d: [today] };
    return { idx, changed: true };
  }
  const same = cur.l === today && cur.v === v && cur.c === geo.c && cur.r === geo.r && cur.la === geo.la && cur.lo === geo.lo;
  if (same) return { idx, changed: false };
  cur.l = today; cur.v = v; cur.c = geo.c; cur.r = geo.r; cur.la = geo.la; cur.lo = geo.lo;
  if (!cur.d.includes(today)) cur.d.push(today);
  cur.d = cur.d.filter((d) => d > today - KEEP_DAYS);
  return { idx, changed: true };
}

export function forgetId(idx, id) {
  if (!(id in idx)) return { idx, changed: false };
  delete idx[id];
  return { idx, changed: true };
}

/** Datos agregados para el administrador. Nada de aquí identifica a una instalación concreta. */
export function summarize(idx, today) {
  const recs = Object.values(idx);
  const active = (n) => recs.filter((r) => r.l >= today - (n - 1)).length;
  const act30 = recs.filter((r) => r.l >= today - 29);
  const versiones = {};
  const zonas = {};
  for (const r of act30) {
    versiones[r.v] = (versiones[r.v] || 0) + 1;
    const k = `${r.c}|${r.r}`;
    const z = zonas[k] || (zonas[k] = { c: r.c, r: r.r, la: r.la, lo: r.lo, n: 0 });
    z.n += 1;
  }
  const dias = [];
  for (let d = today - 29; d <= today; d++) {
    dias.push({ d: dayIso(d), activas: recs.filter((r) => r.d.includes(d)).length, nuevas: recs.filter((r) => r.f === d).length });
  }
  return {
    hoy: dayIso(today),
    total: recs.length,
    activas: { 1: active(1), 7: active(7), 30: active(30) },
    versiones,
    zonas: Object.values(zonas).sort((a, b) => b.n - a.n),
    dias,
  };
}

function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-robots-tag": "noindex" },
});
const notFound = () => new Response("No encontrado", { status: 404, headers: { "cache-control": "no-store" } });

async function loadIdx(env) { return (await env.STATS.get("idx", "json")) || {}; }

async function handlePing(request, env) {
  const p = parsePing(await request.text());
  if (!p) return new Response("datos no válidos", { status: 400 });
  const today = dayNumber(Date.now());
  const { idx, changed } = applyPing(await loadIdx(env), p.id, p.v, coarse(request.cf), today);
  if (changed) await env.STATS.put("idx", JSON.stringify(idx));
  return new Response("ok");
}

async function handleForget(request, env) {
  let o = null;
  try { o = JSON.parse((await request.text()).slice(0, MAX_BODY)); } catch { /* cuerpo no válido */ }
  if (!o || !ID_RE.test(String(o.id))) return new Response("datos no válidos", { status: 400 });
  const { idx, changed } = forgetId(await loadIdx(env), String(o.id));
  if (changed) await env.STATS.put("idx", JSON.stringify(idx));
  return new Response("ok");   // igual de bien si no existía: no se revela qué instalaciones hay
}

async function handleAdmin(request, env, url) {
  const tok = String(env.ADMIN_TOKEN || "");
  if (tok.length < 16 || !safeEqual(url.searchParams.get("k") || "", tok)) return notFound();   // sin clave, la ruta «no existe»
  if (url.pathname === "/resumen") return json(summarize(await loadIdx(env), dayNumber(Date.now())));
  return new Response(PANEL, {
    headers: {
      "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "referrer-policy": "no-referrer", "x-robots-tag": "noindex",
      "content-security-policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; style-src 'self' 'unsafe-inline' https://unpkg.com; "
        + "img-src 'self' data: https://*.tile.openstreetmap.org https://unpkg.com; connect-src 'self'",
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (request.method === "POST" && url.pathname === "/ping") return await handlePing(request, env);
      if (request.method === "POST" && url.pathname === "/olvidar") return await handleForget(request, env);
      if (request.method === "GET" && (url.pathname === "/resumen" || url.pathname === "/panel")) return await handleAdmin(request, env, url);
    } catch (e) {
      return new Response("error", { status: 500 });
    }
    return notFound();
  },
};

// ---------------------------------------------------------------- panel del administrador (una sola página, sin dependencias salvo el mapa)
export const PANEL = `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>LOL-E · Uso</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
:root{--bg:#0b1118;--card:#141d29;--fg:#e8eef6;--dim:#8b9bb0;--acc:#c8aa6e;--ok:#3ddc84}
@media (prefers-color-scheme: light){:root{--bg:#f3f5f8;--card:#fff;--fg:#14202e;--dim:#5d6b7c;--acc:#8a6d2b;--ok:#1b8a4b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px 48px}h1{font-size:22px;margin:0 0 4px}.sub{color:var(--dim);margin:0 0 18px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:14px}
.card{background:var(--card);border-radius:12px;padding:14px 16px}.kpi b{display:block;font-size:30px;color:var(--acc)}.kpi span{color:var(--dim);font-size:13px}
h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);margin:0 0 10px}
#mapa{height:380px;border-radius:10px;background:#0006}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
@media (max-width:720px){.row{grid-template-columns:1fr}}table{width:100%;border-collapse:collapse}td{padding:5px 0;border-bottom:1px solid #8883}td:last-child{text-align:right;font-variant-numeric:tabular-nums}
#graf{width:100%;height:120px;display:block}.nota{color:var(--dim);font-size:12.5px;margin-top:14px}
</style></head><body><main>
<h1>LOL-E · Uso</h1><p class="sub" id="sub">Cargando…</p>
<div class="kpis" id="kpis"></div>
<div class="card"><h2>Zonas aproximadas (activas en 30 días)</h2><div id="mapa"></div></div>
<div class="row"><div class="card"><h2>Activas por día (30 días)</h2><svg id="graf" viewBox="0 0 300 120" preserveAspectRatio="none"></svg><p class="nota">Barras claras: instalaciones nuevas.</p></div>
<div class="card"><h2>Versiones</h2><table id="vers"></table></div></div>
<div class="card" style="margin-top:12px"><h2>Comunidades / regiones</h2><table id="zonas"></table></div>
<p class="nota">Una «instalación» es un número aleatorio que cada LOL-E envía solo si su usuario lo aceptó; no identifica a nadie. La zona sale de la conexión (región y coordenadas
redondeadas a ~50 km); la dirección IP no se guarda. Puntos aproximados: puede haber gente que use VPN o conexiones móviles con otra ubicación.</p></main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
(function(){
  var k=new URLSearchParams(location.search).get('k')||'';
  function el(t,txt,cls){var e=document.createElement(t);if(txt!==undefined)e.textContent=txt;if(cls)e.className=cls;return e}
  fetch('/resumen?k='+encodeURIComponent(k),{cache:'no-store'}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(d){
    document.getElementById('sub').textContent='Al '+d.hoy+' · '+d.total+' instalaciones registradas';
    var kp=document.getElementById('kpis');
    [['Instalaciones',d.total],['Activas hoy',d.activas[1]],['Activas en 7 días',d.activas[7]],['Activas en 30 días',d.activas[30]]].forEach(function(x){
      var c=el('div',undefined,'card kpi');c.appendChild(el('b',x[1]));c.appendChild(el('span',x[0]));kp.appendChild(c)});
    var vs=document.getElementById('vers');Object.keys(d.versiones).sort().reverse().forEach(function(v){
      var tr=el('tr');tr.appendChild(el('td',v));tr.appendChild(el('td',d.versiones[v]));vs.appendChild(tr)});
    var zt=document.getElementById('zonas');d.zonas.forEach(function(z){
      var tr=el('tr');tr.appendChild(el('td',(z.r||'Sin región')+(z.c?' ('+z.c+')':'')));tr.appendChild(el('td',z.n));zt.appendChild(tr)});
    var mx=Math.max.apply(null,d.dias.map(function(x){return x.activas}).concat([1])),g=document.getElementById('graf'),w=300/d.dias.length;
    d.dias.forEach(function(x,i){
      var h=118*x.activas/mx,r=document.createElementNS('http://www.w3.org/2000/svg','rect');
      r.setAttribute('x',i*w+1);r.setAttribute('width',w-2);r.setAttribute('y',119-h);r.setAttribute('height',Math.max(h,0.5));r.setAttribute('fill','#c8aa6e');
      var t=document.createElementNS('http://www.w3.org/2000/svg','title');t.textContent=x.d+': '+x.activas+' activas, '+x.nuevas+' nuevas';r.appendChild(t);g.appendChild(r);
      if(x.nuevas){var n=document.createElementNS('http://www.w3.org/2000/svg','rect'),hn=118*x.nuevas/mx;
        n.setAttribute('x',i*w+1);n.setAttribute('width',w-2);n.setAttribute('y',119-hn);n.setAttribute('height',hn);n.setAttribute('fill','#3ddc84');g.appendChild(n)}});
    if(window.L){var m=L.map('mapa',{scrollWheelZoom:false}).setView([40.2,-3.7],5);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:9,attribution:'© OpenStreetMap'}).addTo(m);
      var pts=[];d.zonas.forEach(function(z){if(z.la===null||z.lo===null)return;pts.push([z.la,z.lo]);
        L.circleMarker([z.la,z.lo],{radius:7+4*Math.sqrt(z.n),color:'#c8aa6e',fillColor:'#c8aa6e',fillOpacity:.45,weight:1})
         .bindTooltip((z.r||'Sin región')+' · '+z.n).addTo(m)});
      if(pts.length>1)m.fitBounds(pts,{padding:[40,40],maxZoom:7});else if(pts.length===1)m.setView(pts[0],7)}
  }).catch(function(){document.getElementById('sub').textContent='No se pudo leer el resumen: ¿clave incorrecta?'});
})();
</script></body></html>`;
