// Los datos del topico de la aplicacion en cada sitio, y su evolucion: cuantos
// mensajes tiene, cuantos consumieron las aplicaciones, cuantos faltan, y si
// los dos sitios tienen el mismo contenido.
import { esc, ico, n, dec, hora, colorSitio, pintar } from "./comunes.js";

let el, tabla, comp, graf, tip, ultimo;
const M = { iz: 54, de: 64, ar: 10, ab: 24 };

export function montar(contenedor) {
  el = contenedor;
  el.innerHTML = `<header><h2>Datos en vivo</h2><span class="sub mono" id="dt-topico"></span></header>
    <div class="cuerpo">
      <div class="comparacion" id="dt-comp"></div>
      <table class="tabla" id="dt-tabla"></table>
      <div class="grafico" id="dt-graf">
        <div style="display:flex;align-items:baseline;gap:10px;justify-content:space-between">
          <div style="font:700 12.5px var(--display)">Mensajes en el tópico <span class="tenue" style="font:500 12px var(--texto)">· últimos minutos</span></div>
          <div class="leyenda" id="dt-ley"></div>
        </div>
        <svg id="dt-svg" preserveAspectRatio="none"></svg>
        <div class="tip oculto" id="dt-tip"></div>
      </div>
    </div>`;
  tabla = el.querySelector("#dt-tabla");
  comp = el.querySelector("#dt-comp");
  graf = el.querySelector("#dt-svg");
  tip = el.querySelector("#dt-tip");
  graf.addEventListener("mousemove", mover);
  graf.addEventListener("mouseleave", () => { tip.classList.add("oculto"); const c = graf.querySelector(".cruz"); if (c) c.style.display = "none"; });
  new ResizeObserver(() => ultimo && dibujar(ultimo)).observe(graf);
}

export function actualizar(e) {
  ultimo = e;
  el.querySelector("#dt-topico").textContent = (e.pareja.topicos || []).join(", ");
  const S = e.pareja.sitios;
  const c = e.contenido || {};
  let ch;
  if (!c.medido) ch = `<div class="signo tenue">?</div><div><b>${esc(c.texto || "Sin medición")}</b><span>La comparación necesita leer los dos sitios.</span></div>`;
  else if (c.transito) ch = `<div class="signo">${ico("gira")}</div><div><b>${esc(c.texto)}</b><span>La réplica copia en segundos lo que entra; con carga viva, siempre hay algo en camino.</span></div>`;
  else if (c.igual) ch = `<div class="signo">${ico("igual")}</div><div><b>${esc(c.texto)}</b><span>Mismos mensajes retenidos en el tópico de los dos sitios.</span></div>`;
  else {
    const rep = (e.replicaciones || []).find((r) => r.destino !== c.adelante && r.copiando);
    ch = `<div class="signo" style="color:${colorSitio(e, c.adelante)}">${ico("distinto")}</div><div><b>${esc(c.texto)}</b>
      <span>${rep ? `La réplica ${esc(rep.origen.toUpperCase())} → ${esc(rep.destino.toUpperCase())} los está copiando ahora.` : "Se compara lo retenido en el tópico, no el número de offset."}</span></div>`;
  }
  comp.classList.toggle("igual", !!c.igual);
  pintar(comp, ch);

  const filas = S.map((s) => {
    const v = e.sitios[s], d = v.datos;
    const viejo = d && !d.vigente;
    return `<tr${viejo ? ' class="tenue" title="Última medición: el sitio no responde ahora"' : ""}>
      <td><span class="sitio-rot"><i style="background:${colorSitio(e, s)}"></i>${esc(s.toUpperCase())}
        <small>${v.rol === "activo" ? "atiende" : v.rol === "en_espera" ? "en espera" : v.rol === "caido" ? "no responde" : ""}</small></span></td>
      <td class="big">${d ? n(d.retenidos) : "—"}</td>
      <td${v.rol !== "activo" && d ? ' title="Posición que la réplica trae del sitio que atiende, cada cierto tiempo. Las aplicaciones de este sitio están detenidas."' : ""}>${d ? n(d.posicion) : "—"}${v.rol !== "activo" && d ? '<div class="tenue" style="font-size:10.5px">replicado</div>' : ""}</td>
      <td>${d ? n(d.atraso) : "—"}</td>
      <td>${d ? (d.ritmo > 0 ? `+${dec(d.ritmo)}/s` : "0/s") : "—"}</td>
      <td class="solo-tecnico">${d ? (d.sub_replicadas ? `<span style="color:var(--critico-tinta);font-weight:700">${ico("alerta")} ${n(d.sub_replicadas)}</span>` : `<span style="color:var(--ok-tinta)">${ico("check")} 0</span>`) : "—"}</td></tr>`;
  }).join("");
  pintar(tabla, `<thead><tr><th>Sitio</th><th>Mensajes en el tópico</th><th>Consumidos</th><th>Pendientes</th><th>Entrando</th><th class="solo-tecnico" title="Particiones sub-replicadas">Sub-replicadas</th></tr></thead><tbody>${filas}</tbody>`);
  el.querySelector("#dt-ley").innerHTML = S.map((s) => `<span><i style="background:${colorSitio(e, s)}"></i>${esc(s.toUpperCase())}</span>`).join("");
  dibujar(e);
}

function escala(e) {
  const S = e.pareja.sitios;
  const h = (e.historia || []).filter((p) => S.some((s) => p[s + "_ret"] !== null && p[s + "_ret"] !== undefined));
  const ancho = graf.clientWidth || 600, alto = graf.clientHeight || 180;
  if (!h.length) return null;
  const t1 = h[h.length - 1].t, t0 = Math.min(h[0].t, t1 - 120);
  let lo = Infinity, hi = -Infinity;
  h.forEach((p) => S.forEach((s) => { const v = p[s + "_ret"]; if (v !== null && v !== undefined) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }));
  if (hi - lo < 10) { const m = (hi + lo) / 2; lo = Math.max(0, Math.floor(m - 10)); hi = Math.ceil(m + 10); }
  const pad = (hi - lo) * 0.12; lo = Math.max(0, lo - pad); hi = hi + pad;
  const x = (t) => M.iz + (t - t0) / (t1 - t0 || 1) * (ancho - M.iz - M.de);
  const y = (v) => M.ar + (1 - (v - lo) / (hi - lo || 1)) * (alto - M.ar - M.ab);
  return { h, t0, t1, lo, hi, x, y, ancho, alto, S };
}

function ticks(lo, hi, k = 4) {
  const paso = Math.pow(10, Math.floor(Math.log10((hi - lo) / k || 1)));
  const err = (hi - lo) / k / paso;
  const p = paso * (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1);
  const out = [];
  for (let v = Math.ceil(lo / p) * p; v <= hi; v += p) out.push(v);
  return out;
}

function dibujar(e) {
  const k = escala(e);
  graf.setAttribute("viewBox", `0 0 ${graf.clientWidth || 600} ${graf.clientHeight || 180}`);
  if (!k) { graf.innerHTML = `<text class="eje" x="50%" y="50%" text-anchor="middle">esperando mediciones…</text>`; return; }
  const { h, x, y, ancho, alto, S, t0, t1, lo, hi } = k;
  let s = "";
  ticks(lo, hi).forEach((v) => {
    s += `<line class="rejilla" x1="${M.iz}" x2="${ancho - M.de}" y1="${y(v)}" y2="${y(v)}"/>
          <text class="eje" x="${M.iz - 8}" y="${y(v) + 3.5}" text-anchor="end">${n(v)}</text>`;
  });
  s += `<line class="base" x1="${M.iz}" x2="${ancho - M.de}" y1="${alto - M.ab}" y2="${alto - M.ab}"/>`;
  const marcas = ancho < 520 ? 2 : 4;
  for (let i = 0; i <= marcas; i++) {
    const t = t0 + (t1 - t0) * i / marcas;
    const etiqueta = t1 - t0 < 600 ? hora(t) : hora(t).slice(0, 5);
    s += `<text class="eje" x="${x(t)}" y="${alto - 6}" text-anchor="${i === 0 ? "start" : i === marcas ? "end" : "middle"}">${etiqueta}</text>`;
  }
  // Lineas: la del segundo sitio debajo, con un anillo de superficie, para que
  // si coinciden se vean las dos.
  const fin = [];
  [...S].reverse().forEach((st) => {
    const pts = h.filter((p) => p[st + "_ret"] !== null && p[st + "_ret"] !== undefined);
    if (!pts.length) return;
    const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)} ${y(p[st + "_ret"]).toFixed(1)}`).join("");
    const col = colorSitio(e, st);
    s += `<path class="anillo" d="${d}"/><path class="serie" d="${d}" style="stroke:${col}"/>`;
    const u = pts[pts.length - 1];
    fin.push({ st, col, x: x(u.t), y: y(u[st + "_ret"]), v: u[st + "_ret"] });
  });
  // Etiquetas al final de cada linea, separadas si se pisan.
  fin.sort((a, b) => a.y - b.y);
  for (let i = 1; i < fin.length; i++) if (fin[i].y - fin[i - 1].y < 14) fin[i].y = fin[i - 1].y + 14;
  fin.forEach((f) => {
    s += `<circle cx="${f.x}" cy="${y(f.v)}" r="4" style="fill:${f.col};stroke:var(--superficie);stroke-width:2"/>
          <text class="rot-fin" x="${f.x + 8}" y="${f.y + 4}">${esc(f.st.toUpperCase())} ${n(f.v)}</text>`;
  });
  s += `<line class="cruz" y1="${M.ar}" y2="${alto - M.ab}" style="display:none"/>`;
  graf.innerHTML = s;
}

function mover(ev) {
  if (!ultimo) return;
  const k = escala(ultimo);
  if (!k) return;
  const r = graf.getBoundingClientRect();
  const px = ev.clientX - r.left;
  let mejor = null, dist = Infinity;
  k.h.forEach((p) => { const d = Math.abs(k.x(p.t) - px); if (d < dist) { dist = d; mejor = p; } });
  if (!mejor) return;
  const cruz = graf.querySelector(".cruz");
  const cx = k.x(mejor.t);
  if (cruz) { cruz.setAttribute("x1", cx); cruz.setAttribute("x2", cx); cruz.style.display = ""; }
  tip.innerHTML = `<div class="h">${hora(mejor.t)}</div>` + k.S.map((s) =>
    `<div class="f"><span><i style="background:${colorSitio(ultimo, s)}"></i> ${esc(s.toUpperCase())}</span><b class="num">${n(mejor[s + "_ret"])}</b></div>`).join("");
  tip.classList.remove("oculto");
  const top = Math.min(...k.S.map((s) => mejor[s + "_ret"] ?? Infinity).map((v) => (isFinite(v) ? k.y(v) : k.alto / 2)));
  tip.style.left = `${Math.max(70, Math.min(r.width - 70, cx))}px`;
  tip.style.top = `${graf.offsetTop + Math.max(40, top - 10)}px`;
}
