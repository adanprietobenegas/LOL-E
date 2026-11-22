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

const cmpVer = (a, b) => {
  const x = a.split(".").map(Number), y = b.split(".").map(Number);
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] - y[i];
  return 0;
};

/** Datos agregados para el administrador. Nada de aquí identifica a una instalación concreta. */
export function summarize(idx, today) {
  const recs = Object.values(idx);
  const active = (n) => recs.filter((r) => r.l >= today - (n - 1)).length;
  const act30 = recs.filter((r) => r.l >= today - 29);
  const versiones = {};
  const zonas = {};
  const paises = {};
  const antig = { "0-6": 0, "7-29": 0, "30-89": 0, "90+": 0 };
  for (const r of act30) {
    versiones[r.v] = (versiones[r.v] || 0) + 1;
    const k = `${r.c}|${r.r}`;
    const z = zonas[k] || (zonas[k] = { c: r.c, r: r.r, la: r.la, lo: r.lo, n: 0 });
    z.n += 1;
    paises[r.c || ""] = (paises[r.c || ""] || 0) + 1;
    const edad = today - r.f;
    antig[edad < 7 ? "0-6" : edad < 30 ? "7-29" : edad < 90 ? "30-89" : "90+"] += 1;
  }
  // historia (hasta KEEP_DAYS días): activas y nuevas por día, y total acumulado
  const desde = today - KEEP_DAYS + 1;
  const activasDia = {}, nuevasDia = {};
  for (const r of recs) {
    for (const d of r.d) activasDia[d] = (activasDia[d] || 0) + 1;
    nuevasDia[r.f] = (nuevasDia[r.f] || 0) + 1;
  }
  let acum = recs.filter((r) => r.f < desde).length;
  const serie = [];
  const porSemana = [0, 0, 0, 0, 0, 0, 0], diasSemana = [0, 0, 0, 0, 0, 0, 0];
  for (let d = desde; d <= today; d++) {
    const a = activasDia[d] || 0, n = nuevasDia[d] || 0;
    acum += n;
    serie.push({ d: dayIso(d), activas: a, nuevas: n, total: acum });
    const wd = new Date(d * 86400000).getUTCDay();
    porSemana[wd] += a; diasSemana[wd] += 1;
  }
  const dias = serie.slice(-30).map((x) => ({ d: x.d, activas: x.activas, nuevas: x.nuevas }));
  const semana = porSemana.map((s, i) => (diasSemana[i] ? Math.round((s / diasSemana[i]) * 10) / 10 : 0));   // media de activas por día de la semana (0 = domingo)
  const cohorte = (n) => { const c = recs.filter((r) => r.f <= today - n); return { n: c.length, siguen: c.filter((r) => r.l >= today - (n - 1)).length }; };
  const vs = Object.keys(versiones).sort(cmpVer);
  return {
    hoy: dayIso(today),
    total: recs.length,
    activas: { 1: active(1), 7: active(7), 30: active(30) },
    inactivas: recs.length - act30.length,
    versiones,
    ultima: vs.length ? vs[vs.length - 1] : "",
    zonas: Object.values(zonas).sort((a, b) => b.n - a.n),
    paises: Object.keys(paises).map((c) => ({ c, n: paises[c] })).sort((a, b) => b.n - a.n),
    antiguedad: antig,
    retencion: { d7: cohorte(7), d30: cohorte(30) },
    semana,
    dias,
    serie,
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
        + "img-src 'self' data: https://server.arcgisonline.com https://unpkg.com; connect-src 'self'",
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
:root{--bg:#0b1118;--card:#141d29;--fg:#e8eef6;--dim:#8b9bb0;--acc:#c8aa6e;--ok:#3ddc84;--bar:#2a3a50}
@media (prefers-color-scheme: light){:root{--bg:#f3f5f8;--card:#fff;--fg:#14202e;--dim:#5d6b7c;--acc:#8a6d2b;--ok:#1b8a4b;--bar:#dfe5ee}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:1000px;margin:0 auto;padding:20px 16px 48px}h1{font-size:22px;margin:0 0 4px}.sub{color:var(--dim);margin:0 0 18px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:12px}
.card{background:var(--card);border-radius:12px;padding:14px 16px}.kpi b{display:block;font-size:28px;color:var(--acc)}.kpi span{color:var(--dim);font-size:13px}
h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);margin:0 0 10px;display:flex;justify-content:space-between;align-items:center;gap:8px}
#mapa{height:380px;border-radius:10px;background:#0006}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
@media (max-width:720px){.row{grid-template-columns:1fr}}
.g{width:100%;height:130px;display:block}.eje{display:flex;justify-content:space-between;color:var(--dim);font-size:11.5px;margin-top:2px}
.nota{color:var(--dim);font-size:12.5px;margin-top:14px}.lg{color:var(--dim);font-size:12px;margin:6px 0 0}.lg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 8px;vertical-align:-1px}
.rng button{background:transparent;color:var(--dim);border:1px solid #8884;border-radius:6px;padding:2px 8px;font:inherit;font-size:12px;cursor:pointer;margin-left:4px}
.rng button.on{color:var(--fg);border-color:var(--acc)}
.b{display:grid;grid-template-columns:minmax(80px,38%) 1fr auto;gap:8px;align-items:center;padding:3px 0;font-size:14px}
.b .t{height:10px;border-radius:5px;background:var(--bar);overflow:hidden}.b .t i{display:block;height:100%;background:var(--acc);border-radius:5px}.b .n{font-variant-numeric:tabular-nums;color:var(--dim)}
.b .l{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.vacio{color:var(--dim);font-size:13px}
</style></head><body><main>
<h1>LOL-E · Uso</h1><p class="sub" id="sub">Cargando…</p>
<div class="kpis" id="kpis"></div>
<div class="card"><h2>Zonas aproximadas (activas en 30 días)</h2><div id="mapa"></div></div>
<div class="row"><div class="card"><h2><span>Instalaciones acumuladas</span><span class="rng" data-g="acum"></span></h2><svg id="g-acum" class="g" viewBox="0 0 300 120" preserveAspectRatio="none"></svg><div class="eje" id="e-acum"></div></div>
<div class="card"><h2><span>Activas por día</span><span class="rng" data-g="act"></span></h2><svg id="g-act" class="g" viewBox="0 0 300 120" preserveAspectRatio="none"></svg><div class="eje" id="e-act"></div>
<p class="lg"><i style="background:var(--acc)"></i>activas<i style="background:var(--ok)"></i>nuevas</p></div></div>
<div class="row"><div class="card"><h2>Media de activas por día de la semana</h2><div id="semana"></div></div>
<div class="card"><h2>Antigüedad (activas en 30 días)</h2><div id="antig"></div><p class="nota" id="reten"></p></div></div>
<div class="row"><div class="card"><h2>Versiones (activas en 30 días)</h2><div id="vers"></div></div>
<div class="card"><h2>Países</h2><div id="paises"></div></div></div>
<div class="card" style="margin-top:12px"><h2>Comunidades / regiones</h2><div id="zonas"></div></div>
<p class="nota">Una «instalación» es un número aleatorio que cada LOL-E envía solo si su usuario lo aceptó; no identifica a nadie. La zona sale de la conexión (región y coordenadas
redondeadas a ~50 km); la dirección IP no se guarda. Puntos aproximados: puede haber gente que use VPN o conexiones móviles con otra ubicación. La historia llega a 120 días;
«acumuladas» cuenta las instalaciones que siguen registradas (las que retiran el permiso desaparecen del total).</p></main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
(function(){
  var k=new URLSearchParams(location.search).get('k')||'',NS='http://www.w3.org/2000/svg';
  function el(t,txt,cls){var e=document.createElement(t);if(txt!==undefined)e.textContent=txt;if(cls)e.className=cls;return e}
  function $(i){return document.getElementById(i)}
  function bars(id,rows){var box=$(id);if(!rows.length){box.appendChild(el('p','Sin datos todavía','vacio'));return}
    var mx=Math.max.apply(null,rows.map(function(r){return r[1]}).concat([1]));
    rows.forEach(function(r){var b=el('div',undefined,'b'),t=el('div',undefined,'t'),i=el('i');i.style.width=(100*r[1]/mx)+'%';t.appendChild(i);
      b.appendChild(el('span',r[0],'l'));b.appendChild(t);b.appendChild(el('span',String(r[1]),'n'));box.appendChild(b)})}
  function rect(g,x,y,w,h,fill,tip){var r=document.createElementNS(NS,'rect');r.setAttribute('x',x);r.setAttribute('y',y);r.setAttribute('width',w);r.setAttribute('height',Math.max(h,0));r.setAttribute('fill',fill);
    var t=document.createElementNS(NS,'title');t.textContent=tip;r.appendChild(t);g.appendChild(r)}
  function chart(kind,serie,n){var g=$('g-'+kind),e=$('e-'+kind),s=serie.slice(-n);g.textContent='';var w=300/s.length;
    if(kind==='acum'){var mn=Math.min.apply(null,s.map(function(x){return x.total})),mx=Math.max.apply(null,s.map(function(x){return x.total}).concat([1])),sp=Math.max(mx-mn,1);
      s.forEach(function(x,i){var h=10+108*((x.total-mn)/sp);rect(g,i*w,119-h,w+.5,h,'var(--acc)',x.d+': '+x.total+' instalaciones')});
      e.textContent='';e.appendChild(el('span',s[0].d+' · '+mn));e.appendChild(el('span',s[s.length-1].d+' · '+mx))}
    else{var m=Math.max.apply(null,s.map(function(x){return x.activas}).concat([1]));
      s.forEach(function(x,i){var h=118*x.activas/m,hn=118*x.nuevas/m,tip=x.d+': '+x.activas+' activas, '+x.nuevas+' nuevas';
        rect(g,i*w+.5,119-h,Math.max(w-1,.5),Math.max(h,.5),'var(--acc)',tip);if(x.nuevas)rect(g,i*w+.5,119-hn,Math.max(w-1,.5),hn,'var(--ok)',tip)});
      e.textContent='';e.appendChild(el('span',s[0].d));e.appendChild(el('span','máx '+m))}}
  function ranges(serie){document.querySelectorAll('.rng').forEach(function(box){var kind=box.getAttribute('data-g'),btns=[];
    [30,60,serie.length].forEach(function(n){if(n>serie.length)return;var b=el('button',n===serie.length&&n>60?'todo':n+' d');
      b.onclick=function(){btns.forEach(function(x){x.className=''});b.className='on';chart(kind,serie,n)};btns.push(b);box.appendChild(b)});
    btns[0].onclick()})}
  fetch('/resumen?k='+encodeURIComponent(k),{cache:'no-store'}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(d){
    $('sub').textContent='Al '+d.hoy+' · '+d.total+' instalaciones registradas';
    var pct=function(c){return c.n?Math.round(100*c.siguen/c.n)+' %':'—'};
    var enUlt=d.versiones[d.ultima]||0,act=d.activas[30];
    [['Instalaciones',d.total],['Activas hoy',d.activas[1]],['Activas en 7 días',d.activas[7]],['Activas en 30 días',act],
     ['Con la última versión',act?Math.round(100*enUlt/act)+' %':'—'],['Retención a 7 días',pct(d.retencion.d7)],['Sin avisar en 30 días',d.inactivas]].forEach(function(x){
      var c=el('div',undefined,'card kpi');c.appendChild(el('b',String(x[1])));c.appendChild(el('span',x[0]));$('kpis').appendChild(c)});
    if(d.serie&&d.serie.length)ranges(d.serie);
    var dn=['Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'];bars('semana',[1,2,3,4,5,6,0].map(function(i){return [dn[i],d.semana[i]]}));
    bars('antig',Object.keys(d.antiguedad).map(function(x){return [x==='90+'?'Más de 90 días':'Hace '+x+' días',d.antiguedad[x]]}));
    $('reten').textContent='Retención: de las instalaciones con más de 7 días, siguen activas '+pct(d.retencion.d7)+' (en la última semana); con más de 30 días, '+pct(d.retencion.d30)+' (en el último mes).';
    bars('vers',Object.keys(d.versiones).sort(function(a,b){var x=a.split('.'),y=b.split('.');for(var i=0;i<3;i++)if(+x[i]!==+y[i])return +y[i]-+x[i];return 0}).map(function(v){return [v+(v===d.ultima?' (última)':''),d.versiones[v]]}));
    var nm=null;try{nm=new Intl.DisplayNames(['es'],{type:'region'})}catch(e){}
    bars('paises',d.paises.map(function(p){var n=p.c?(nm?nm.of(p.c):p.c):'Desconocido';return [n,p.n]}));
    bars('zonas',d.zonas.map(function(z){return [(z.r||'Sin región')+(z.c?' ('+z.c+')':''),z.n]}));
    if(window.L){var oscuro=!window.matchMedia||!matchMedia('(prefers-color-scheme: light)').matches,m=L.map('mapa',{scrollWheelZoom:false}).setView([40.2,-3.7],5);
      var TILES='https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/'+(oscuro?'World_Dark_Gray_Base':'World_Light_Gray_Base')+'/MapServer/tile/{z}/{y}/{x}';
      var tl=L.tileLayer(TILES,{maxZoom:9,attribution:'Tiles © Esri'}).addTo(m),fallos=0;
      tl.on('tileerror',function(){if(++fallos===3)$('sub').textContent+=' · El mapa base no se pudo cargar (los puntos y las zonas siguen siendo correctos)'});
      var pts=[];d.zonas.forEach(function(z){if(z.la===null||z.lo===null)return;pts.push([z.la,z.lo]);
        L.circleMarker([z.la,z.lo],{radius:7+4*Math.sqrt(z.n),color:'#c8aa6e',fillColor:'#c8aa6e',fillOpacity:.55,weight:1})
         .bindTooltip((z.r||'Sin región')+' · '+z.n).addTo(m)});
      if(pts.length>1)m.fitBounds(pts,{padding:[40,40],maxZoom:7});else if(pts.length===1)m.setView(pts[0],7)}
  }).catch(function(){$('sub').textContent='No se pudo leer el resumen: ¿clave incorrecta?'});
})();
</script></body></html>`;
