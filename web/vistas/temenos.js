// El simulador de Temenos: publica transacciones por la micro-app productora
// del sitio, que entra por su proxy como lo haria el core bancario.
import { esc, ico, n, dinero, hora, colorSitio, post, pintar } from "./comunes.js";

let el, estadoEl, feed, sitioSel = "auto", ritmo = 1, enCurso = false, ultimo;

export function montar(contenedor) {
  el = contenedor;
  el.innerHTML = `<header><h2>Temenos · simulador</h2><span class="sub">transacciones de prueba</span></header>
    <div class="cuerpo">
      <p class="temenos-intro">Publica transacciones por la micro-app productora del sitio. Entran por el proxy, igual que las del core bancario, y llegan al Kafka que el proxy indique.</p>
      <div class="controles-tm">
        <div class="fila-tm"><span class="rot">Entra por</span><div class="segmentado" id="tm-sitio"></div></div>
        <div class="fila-tm"><span class="rot">Lote</span>
          <button class="btn" data-lote="10">${ico("enviar")} 10</button>
          <button class="btn" data-lote="50">${ico("enviar")} 50</button>
          <button class="btn" data-lote="100">${ico("enviar")} 100</button></div>
        <div class="fila-tm"><span class="rot">Continuo</span>
          <select class="sel-tm" id="tm-ritmo" aria-label="Transacciones por segundo">
            ${[1, 2, 5, 10, 20, 40].map((v) => `<option value="${v}"${v === ritmo ? " selected" : ""}>${v} tx/s</option>`).join("")}
          </select>
          <button class="btn primario" id="tm-continuo">${ico("enviar")} Iniciar</button></div>
        <div class="estado-tm" id="tm-estado"></div>
      </div>
      <table class="feed" id="tm-feed"></table>
    </div>`;
  estadoEl = el.querySelector("#tm-estado");
  feed = el.querySelector("#tm-feed");
  el.querySelector("#tm-sitio").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-s]");
    if (!b) return;
    sitioSel = b.dataset.s;
    ultimo && actualizar(ultimo);
  });
  el.querySelectorAll("button[data-lote]").forEach((b) => b.addEventListener("click", () => lote(+b.dataset.lote, b)));
  el.querySelector("#tm-ritmo").addEventListener("change", (ev) => { ritmo = +ev.target.value; });
  el.querySelector("#tm-continuo").addEventListener("click", alternarContinuo);
}

const sitioPedido = () => (sitioSel === "auto" ? null : sitioSel);

async function lote(cant, boton) {
  if (enCurso) return;
  enCurso = true; boton.disabled = true;
  mensaje(`Enviando ${n(cant)} transacciones…`);
  try {
    const r = await post("api/temenos/lote", { sitio: sitioPedido(), cantidad: cant });
    mensaje(`${n(r.enviados)} de ${n(r.total)} transacciones aceptadas por el proxy de ${r.sitio.toUpperCase()}.`);
  } catch (e) {
    mensaje(`No se pudo publicar: ${e.message}`, true);
  } finally { enCurso = false; boton.disabled = false; }
}

async function alternarContinuo() {
  const activo = ultimo?.temenos?.continuo;
  try {
    if (activo) { await post("api/temenos/continuo", { detener: true }); mensaje("Flujo continuo detenido."); }
    else {
      const r = await post("api/temenos/continuo", { sitio: sitioPedido(), por_segundo: ritmo });
      mensaje(`Flujo continuo: ${r.continuo.por_segundo} tx/s por el proxy de ${r.continuo.sitio.toUpperCase()}.`);
    }
  } catch (e) { mensaje(`No se pudo: ${e.message}`, true); }
}

function mensaje(t, error = false) {
  estadoEl.textContent = t;
  estadoEl.classList.toggle("error", error);
}

const vistos = new Set();
export function actualizar(e) {
  ultimo = e;
  const S = e.pareja.sitios;
  const tm = e.temenos || {};
  const auto = e.activo ? `Automático · ${e.activo.toUpperCase()}` : "Automático";
  pintar(el.querySelector("#tm-sitio"), [["auto", auto], ...S.map((s) => [s, s.toUpperCase()])].map(([k, t]) =>
    `<button data-s="${k}" class="${k === sitioSel ? "sel" : ""}" title="${k === "auto" ? "La micro-app del sitio que atiende" : `La micro-app de ${esc(k.toUpperCase())}`}">${esc(t)}</button>`).join(""));
  const bc = el.querySelector("#tm-continuo");
  const c = tm.continuo;
  const htmlBtn = c ? `${ico("pausa")} Detener (${c.por_segundo} tx/s · ${n(c.enviados)} enviadas)` : `${ico("enviar")} Iniciar`;
  if (bc._h !== htmlBtn) { bc.innerHTML = htmlBtn; bc._h = htmlBtn; }
  bc.classList.toggle("activo", !!c);
  bc.classList.toggle("primario", !c);
  if (c?.ultimo_error) mensaje(`Flujo continuo: ${c.ultimo_error}`, true);

  const filas = (tm.ultimas || []).slice(0, 6).map((x) => {
    const clave = x.id + x.t;
    const nueva = feed._html && !vistos.has(clave);
    vistos.add(clave);
    return `<tr class="${nueva ? "nueva" : ""}" title="${esc([x.id, x.canal, x.sistema, x.latencia_ms != null ? Math.round(x.latencia_ms) + " ms" : null].filter(Boolean).join(" · "))}">
      <td class="tenue">${hora(x.t)}</td>
      <td><span class="sitio-rot" style="font-size:12px"><i style="background:${colorSitio(e, x.sitio)}"></i>${esc(x.sitio.toUpperCase())}</span></td>
      <td>${esc((x.tipo || "").replace(/_/g, " ").toLowerCase())}</td>
      <td class="monto">${dinero(x.monto)} <span class="tenue" style="font-weight:500">${esc(x.moneda || "")}</span></td>
      <td><span class="cuenta">${esc(x.origen || "")} → ${esc(x.destino || "")}</span></td></tr>`;
  }).join("");
  const total = Object.values(tm.totales || {}).reduce((a, b) => a + b, 0);
  const html = filas
    ? `<thead><tr><th>Hora</th><th>Por</th><th>Operación</th><th class="monto">Monto</th><th>Cuentas</th></tr></thead><tbody>${filas}</tbody>
       <caption style="caption-side:bottom;text-align:left;padding-top:6px" class="tenue">${n(total)} transacciones publicadas desde esta página · cuentas enmascaradas</caption>`
    : `<tbody><tr><td class="vacio" style="border:0">Todavía no se publicó nada desde esta página.</td></tr></tbody>`;
  const base = html.replace(/ class="nueva"/g, ' class=""');
  if (feed._base !== base) { feed.innerHTML = html; feed._base = base; feed._html = html; }
}
