// La topologia de la pareja, como las figuras del procedimiento de BPD: un sitio
// arriba y otro abajo, cada uno con su camino Temenos -> Proxy -> Kafka ->
// Aplicaciones, y las dos replicas entre los Kafka.
//
// El esqueleto se dibuja una vez por pareja y despues solo se actualizan textos,
// clases y colores: asi las animaciones de flujo no se reinician en cada lectura.
import { esc, n, dec, colorSitio, tenueSitio } from "./comunes.js";

let el, svg, montadoPara = null;
const W = 1000, H = 448;
const BANDA = { alto: 204, sep: 28, y0: 6 };
const X = { tm: [24, 164], px: [222, 372], kf: [444, 664], ap: [804, 976] };
const LANE = { baja: 532, sube: 576 };

const yBanda = (i) => BANDA.y0 + i * (BANDA.alto + BANDA.sep);
const cy = (i) => yBanda(i) + 116;
const KH = 120;   // alto de la caja de Kafka

export function montar(contenedor) {
  el = contenedor;
  el.innerHTML = `
    <header><h2>El ambiente, en vivo</h2><span class="sub" id="topo-sub"></span>
      <div class="der leyenda" id="topo-ley"></div></header>
    <div class="cuerpo"><div id="topo-svg"></div></div>`;
}

function nodo(id, x0, x1, y, alto, titulo, sub) {
  return `<g class="nodo" id="${id}">
    <rect class="caja" x="${x0}" y="${y - alto / 2}" width="${x1 - x0}" height="${alto}" rx="12"/>
    <text class="titulo" x="${x0 + 14}" y="${y - alto / 2 + 24}">${esc(titulo)}</text>
    <text class="sub" x="${x0 + 14}" y="${y - alto / 2 + 40}" id="${id}-sub">${esc(sub)}</text>
    <text class="dato" x="${x0 + 14}" y="${y + alto / 2 - 14}" id="${id}-dato"></text>
  </g>`;
}

function esqueleto(e) {
  const S = e.pareja.sitios;
  let h = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Topología de la pareja ${esc(e.pareja.clave)}">
    <defs>
      <marker id="punta" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0L10 5L0 10z" fill="context-stroke"/></marker>
    </defs>`;
  // Bandas de sitio
  S.forEach((s, i) => {
    const y = yBanda(i);
    h += `<g id="b-${s}">
      <rect class="banda-sitio" id="b-${s}-r" x="2" y="${y}" width="${W - 4}" height="${BANDA.alto}" rx="16"/>
      <text class="rot-sitio" x="24" y="${y + 32}" id="b-${s}-et">${esc(s.toUpperCase())}</text>
      <text class="rot-sitio-2" x="${24 + 14 * s.length + 14}" y="${y + 31}" id="b-${s}-tit"></text>
      <g id="b-${s}-rol"><rect rx="12" height="24" y="${y + 13}"/><text class="rol" y="${y + 29.5}" text-anchor="middle"></text></g>
    </g>`;
  });
  // Rutas (debajo de los nodos)
  S.forEach((s, i) => {
    const y = cy(i);
    h += ruta(`r-tm-${s}`, `M${X.tm[1]} ${y}H${X.px[0]}`);
    S.forEach((d, j) => {
      const yd = cy(j);
      const dpath = i === j
        ? `M${X.px[1]} ${y}H${X.kf[0]}`
        : `M${X.px[1]} ${y + (j > i ? 14 : -14)}C${X.px[1] + 46} ${y + (j > i ? 14 : -14)} ${X.kf[0] - 46} ${yd + (j > i ? -14 : 14)} ${X.kf[0]} ${yd + (j > i ? -14 : 14)}`;
      h += ruta(`r-px-${s}-${d}`, dpath);
    });
    h += ruta(`r-ap-${s}`, `M${X.kf[1]} ${y}H${X.ap[0]}`);
  });
  // Replicas entre los Kafka: la que baja (del sitio 1 al 2) y la que sube.
  const yTop = cy(0) + KH / 2, yBot = cy(1) - KH / 2;
  h += ruta(`r-mm-${S[0]}_${S[1]}`, `M${LANE.baja} ${yTop}V${yBot}`, true);
  h += ruta(`r-mm-${S[1]}_${S[0]}`, `M${LANE.sube} ${yBot}V${yTop}`, true);
  // Las dos replicas se nombran en una tarjeta propia, con fondo, entre las
  // dos bandas: sueltas, el borde de las bandas les pasaba por encima.
  const MC = { x: 596, y: (yBanda(0) + BANDA.alto + yBanda(1)) / 2 - 34, w: 200, h: 68 };
  h += `<g id="mm-card">
    <rect class="mm-card" x="${MC.x}" y="${MC.y}" width="${MC.w}" height="${MC.h}" rx="10"/>
    <text class="mm-cap" x="${MC.x + 12}" y="${MC.y + 16}">RÉPLICAS</text>
    ${[[S[0], S[1], "↓"], [S[1], S[0], "↑"]].map(([o, d, f], i) => `
    <g id="mm-${o}_${d}"><title id="mm-${o}_${d}-tip"></title>
      <text class="lane-rot" x="${MC.x + 12}" y="${MC.y + 36 + i * 20}" id="mm-${o}_${d}-t">${f} ${esc(o.toUpperCase())} → ${esc(d.toUpperCase())}</text>
      <text class="lane-est" x="${MC.x + MC.w - 12}" y="${MC.y + 36 + i * 20}" text-anchor="end" id="mm-${o}_${d}-e"></text>
    </g>`).join("")}
  </g>`;
  // Nodos
  S.forEach((s, i) => {
    const y = cy(i);
    h += nodo(`n-tm-${s}`, X.tm[0], X.tm[1], y, 78, "Temenos", "core bancario · simulado");
    h += nodo(`n-px-${s}`, X.px[0], X.px[1], y, 78, "Proxy", "Kroxylicious");
    h += nodo(`n-ap-${s}`, X.ap[0], X.ap[1], y, 78, "Aplicaciones", "");
    const k0 = X.kf[0], top = y - KH / 2;
    h += `<g class="nodo" id="n-kf-${s}">
      <rect class="caja" x="${k0}" y="${top}" width="${X.kf[1] - k0}" height="${KH}" rx="14"/>
      <text class="titulo" x="${k0 + 16}" y="${top + 25}">Kafka</text>
      <text class="sub" x="${k0 + 16}" y="${top + 42}" id="n-kf-${s}-sub"></text>
      <g id="n-kf-${s}-brokers"></g>
      <text class="grande" x="${k0 + 16}" y="${top + 78}" id="n-kf-${s}-num"></text>
      <text class="ritmo" x="${X.kf[1] - 16}" y="${top + 76}" text-anchor="end" id="n-kf-${s}-ritmo"></text>
      <text class="sub" x="${k0 + 16}" y="${top + 95}" id="n-kf-${s}-lbl">mensajes en el tópico</text>
      <text class="dato" x="${k0 + 16}" y="${top + 112}" id="n-kf-${s}-dato"></text>
      <g id="n-kf-${s}-cruz" class="oculto">
        <path class="cruz" d="M${X.kf[1] - 34} ${top + 62}l16 16M${X.kf[1] - 18} ${top + 62}l-16 16"/>
      </g>
    </g>`;
  });
  h += `</svg>`;
  return h;
}

function ruta(id, d, flecha = false) {
  return `<path class="ruta" id="${id}" d="${d}" ${flecha ? 'marker-end="url(#punta)"' : ""}/>
          <path class="ruta flujo oculto" id="${id}-f" d="${d}"/>`;
}

const $ = (id) => svg.getElementById ? svg.getElementById(id) : svg.querySelector("#" + CSS.escape(id));
function texto(id, t) { const x = $(id); if (x && x.textContent !== t) x.textContent = t; }
function attr(id, k, v) { const x = $(id); if (x && x.getAttribute(k) !== String(v)) x.setAttribute(k, v); }
function clase(id, c, on) { const x = $(id); if (x) x.classList.toggle(c, !!on); }

function ponerRuta(id, { activa, color, flujo, lento, rota }) {
  clase(id, "activa", activa);
  clase(id, "rota", activa && rota);
  attr(id, "style", activa ? `stroke:${rota ? "var(--critico)" : color}` : "");
  const f = `${id}-f`;
  clase(f, "oculto", !flujo);
  clase(f, "lento", lento);
  attr(f, "style", flujo ? `stroke:${color}` : "");
}

export function actualizar(e) {
  const S = e.pareja.sitios;
  const clave = S.join("|");
  if (montadoPara !== clave) {
    el.querySelector("#topo-svg").innerHTML = esqueleto(e);
    svg = el.querySelector("svg");
    montadoPara = clave;
  }
  const tm = e.temenos || {};
  const recientes = new Set((tm.ultimas || []).filter((x) => Date.now() / 1000 - x.t < 6).map((x) => x.sitio));
  if (tm.continuo) recientes.add(tm.continuo.sitio);

  texto("topo-sub", e.pareja.descripcion || "");
  el.querySelector("#topo-ley").innerHTML = S.map((s) =>
    `<span><i style="background:${colorSitio(e, s)}"></i>${esc(s.toUpperCase())} · ${esc(e.sitios[s]?.titulo || "")}</span>`).join("");

  S.forEach((s) => {
    const v = e.sitios[s];
    const col = colorSitio(e, s);
    const activo = v.rol === "activo";
    // Banda
    attr(`b-${s}-r`, "style", `fill:${activo ? tenueSitio(e, s) : "var(--superficie-2)"};stroke:${activo ? col : "var(--linea)"};stroke-width:${activo ? 2 : 1}`);
    attr(`b-${s}-et`, "style", `fill:${col}`);
    texto(`b-${s}-tit`, `${v.titulo}`);
    const rol = {
      activo: ["ATIENDE LA OPERACIÓN", col, "#fff"], en_espera: ["EN ESPERA", "var(--superficie)", "var(--tinta-2)"],
      caido: ["KAFKA NO RESPONDE", "var(--critico)", "#fff"], sin_conexion: ["SIN CONEXIÓN CON EL SITIO", "var(--critico)", "#fff"],
      leyendo: ["LEYENDO…", "var(--superficie)", "var(--tenue)"],
    }[v.rol] || ["", "transparent", "inherit"];
    const g = $(`b-${s}-rol`);
    const ancho = 26 + rol[0].length * 7.6;
    const xr = W - 20 - ancho;
    g.querySelector("rect").setAttribute("x", xr);
    g.querySelector("rect").setAttribute("width", ancho);
    g.querySelector("rect").setAttribute("style", `fill:${rol[1]};stroke:${v.rol === "en_espera" || v.rol === "leyendo" ? "var(--linea-fuerte)" : rol[1]}`);
    const tt = g.querySelector("text");
    tt.setAttribute("x", xr + ancho / 2);
    tt.setAttribute("style", `fill:${rol[2]}`);
    if (tt.textContent !== rol[0]) tt.textContent = rol[0];

    // Kafka
    const k = v.kafka || {};
    const d = v.datos;
    const caido = v.rol === "caido" || v.rol === "sin_conexion";
    clase(`n-kf-${s}`, "caido", caido);
    clase(`n-kf-${s}-cruz`, "oculto", !caido);
    texto(`n-kf-${s}-sub`, `${k.listos ?? "?"} de ${k.total ?? "?"} brokers listos${k.caida_simulada ? " · caída simulada" : ""}`);
    if (caido) {
      texto(`n-kf-${s}-num`, v.rol === "sin_conexion" ? "Sin conexión" : "No responde");
      attr(`n-kf-${s}-num`, "style", "fill:var(--critico-tinta);font-size:24px");
      texto(`n-kf-${s}-lbl`, d ? `último dato: ${n(d.retenidos)} mensajes` : "");
      texto(`n-kf-${s}-dato`, k.caida_simulada ? "simulacro de caída activo" : "");
      texto(`n-kf-${s}-ritmo`, "");
    } else {
      texto(`n-kf-${s}-num`, d ? n(d.retenidos) : "…");
      attr(`n-kf-${s}-num`, "style", "");
      texto(`n-kf-${s}-lbl`, "mensajes en el tópico");
      texto(`n-kf-${s}-dato`, d ? `consumidos ${n(d.posicion)} · pendientes ${n(d.atraso)}` : "");
      texto(`n-kf-${s}-ritmo`, d && d.ritmo > 0 ? `+${dec(d.ritmo)}/s` : "");
    }
    // Brokers
    const gb = $(`n-kf-${s}-brokers`);
    const bro = (k.brokers || []);
    const html = bro.map((b, i) => `<circle class="broker" cx="${X.kf[1] - 22 - (bro.length - 1 - i) * 18}" cy="${cy(S.indexOf(s)) - KH / 2 + 22}" r="7"
        style="fill:${b.listo ? "var(--ok)" : "var(--critico)"}"><title>${esc(b.nombre)} · ${b.listo ? "listo" : esc(b.motivo || b.fase)}${b.reinicios ? ` · ${b.reinicios} reinicios` : ""}</title></circle>`).join("");
    if (gb._h !== html) { gb.innerHTML = html; gb._h = html; }

    // Proxy
    const px = v.proxy || {};
    texto(`n-px-${s}-sub`, "Kroxylicious");
    texto(`n-px-${s}-dato`, px.destino ? `envía al Kafka de ${px.destino.toUpperCase()}` : v.leido ? "sin destino" : "");
    attr(`n-px-${s}-dato`, "style", px.destino ? `fill:${colorSitio(e, px.destino)};font-weight:700` : "");
    clase(`n-px-${s}`, "apagado", !v.alcanzable);

    // Temenos
    const t = v.temenos;
    const enviando = recientes.has(s);
    // El envio continuo de este sitio: lo entregado y, si el Kafka no responde,
    // lo que no se entrega. La micro-app no lo reintenta: se pierde.
    const c = tm.continuo?.sitio === s ? tm.continuo : null;
    const falla = !!c?.ultimo_error;
    texto(`n-tm-${s}-dato`, !t ? (v.leido ? "sin micro-app" : "") :
      c ? (falla ? "no logra publicar" : `enviando ${c.por_segundo} tx/s`) : enviando ? "enviando lote" : (t.listas > 0 ? "listo para publicar" : "detenido"));
    texto(`n-tm-${s}-sub`, c ? (falla ? `${n(c.errores)} sin entregar` : `${n(c.enviados)} entregadas`) : "core bancario · simulado");
    attr(`n-tm-${s}-dato`, "style", falla ? "fill:var(--critico-tinta);font-weight:700" : "");
    attr(`n-tm-${s}-sub`, "style", falla ? "fill:var(--critico-tinta)" : "");
    clase(`n-tm-${s}`, "apagado", !t || t.listas === 0);

    // Aplicaciones
    const ap = v.consumidor;
    texto(`n-ap-${s}-sub`, ap ? ap.nombre : "");
    texto(`n-ap-${s}-dato`, ap ? (ap.estado === "procesando" ? `● procesando · ${ap.listas}/${ap.replicas}` : ap.estado === "arrancando" ? `arrancando · ${ap.listas}/${ap.replicas}` : "detenidas · 0 réplicas") : "");
    attr(`n-ap-${s}-dato`, "style", ap?.estado === "procesando" ? "fill:var(--ok-tinta);font-weight:700" : "");
    clase(`n-ap-${s}`, "apagado", !ap || ap.replicas === 0);

    // Rutas del sitio
    const dest = px.destino;
    const kd = dest ? e.sitios[dest] : null;
    const destVivo = kd && kd.rol !== "caido" && kd.rol !== "sin_conexion";
    // Si Temenos no logra entregar, la ruta se ve cortada aunque el Kafka responda.
    const llega = destVivo && !falla;
    ponerRuta(`r-tm-${s}`, { activa: !!t && t.listas > 0 && !!dest, color: dest ? colorSitio(e, dest) : "", flujo: enviando && llega, rota: (kd && !destVivo) || falla });
    S.forEach((d2) => {
      // Un proxy que apunta a un Kafka caido es justo lo que hay que ver: en rojo.
      ponerRuta(`r-px-${s}-${d2}`, { activa: dest === d2, color: colorSitio(e, d2), flujo: dest === d2 && enviando && llega, rota: dest === d2 && (!destVivo || falla) });
    });
    ponerRuta(`r-ap-${s}`, { activa: ap && ap.replicas > 0, color: col, flujo: ap && ap.listas > 0 && d && d.consumo > 0 });
  });

  // Replicas
  (e.replicaciones || []).forEach((r) => {
    const id = `r-mm-${r.clave}`;
    const col = colorSitio(e, r.origen);
    const encendida = r.estado === "ACTIVO" || r.estado === "PAUSADO";
    ponerRuta(id, { activa: encendida, color: col, flujo: r.copiando, lento: false });
    attr(`mm-${r.clave}-t`, "style", `fill:${encendida ? col : "var(--tenue)"}`);
    const conFallas = r.estado === "ACTIVO" && (r.conectores || []).length && !r.conectores_ok;
    // Corto: la fila tiene el ancho de la tarjeta. El detalle va en el tooltip.
    const estado = conFallas ? "con fallas" : r.copiando ? "copiando" : r.texto;
    texto(`mm-${r.clave}-e`, estado);
    attr(`mm-${r.clave}-e`, "style", conFallas ? "fill:var(--critico-tinta)" : r.estado === "PAUSADO" ? "fill:var(--aviso-tinta)"
      : encendida ? `fill:${col}` : "fill:var(--tenue)");
    const conectores = (r.conectores || []).length ? (r.conectores_ok ? "conectores en marcha" : "conectores con fallas") : "sin conectores";
    texto(`mm-${r.clave}-tip`, `${r.titulo} · ${r.nombre || ""} · vive en ${r.vive_en.toUpperCase()} · ${conectores}`);
  });
}
