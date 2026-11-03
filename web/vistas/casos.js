// La matriz de casos de uso: parejas por casos, con lo que ya esta certificado,
// lo que esta en curso y lo que viene. Sale del contrato y del catalogo.
import { esc, ico, pintar } from "./comunes.js";

let el, cuerpo;
const ESTADO = {
  certificado: ["ok", "escudo", "Certificado"],
  en_construccion: ["curso", "engranaje", "En construcción"],
  proximo: ["neutro", "reloj", "Próximo"],
};

export function montar(contenedor) {
  el = contenedor;
  el.innerHTML = `<header><h2>Casos de uso</h2><span class="sub">lo construido y lo que viene, por pareja</span></header>
    <div class="cuerpo" id="cs-cuerpo"></div>`;
  cuerpo = el.querySelector("#cs-cuerpo");
}

export function actualizar(e) {
  const m = e.casos || { casos: [], filas: [] };
  const cols = m.casos.length;
  let h = `<div class="matriz" style="--cols:${cols}">
    <div class="encab"><div></div>${m.casos.map((c) => `<div title="${esc(c.proposito)}">${esc(c.nombre)}</div>`).join("")}</div>`;
  m.filas.forEach((f) => {
    h += `<div class="fila-m"><div class="pareja${f.actual ? " actual" : ""}"><b>${esc(f.nombre)}</b><span>${esc(f.descripcion)}</span></div>`;
    f.celdas.forEach((c) => {
      const [cl, ic, tx] = c.en_curso ? ["curso", "gira", "En curso"] : ESTADO[c.estado] || ESTADO.proximo;
      const ops = c.operaciones.length
        ? `<div class="ops">${c.operaciones.map((o) => `<span>${o.en_curso ? ico("gira", "gira") : ico("check")}
            ${o.url ? `<a href="${esc(o.url)}" target="_blank" rel="noopener" title="${esc(o.flujo)}">${esc(o.etapa || o.nombre)}</a>` : esc(o.etapa || o.nombre)}
            ${o.variantes?.length ? `<span class="tenue">· ${o.variantes.length} variantes</span>` : ""}</span>`).join("")}</div>`
        : `<div class="prop">${esc(c.proposito)}</div>`;
      h += `<div class="celda ${c.en_curso ? "en_curso" : c.estado}">
        <div class="cab"><b>${esc(c.nombre)}</b><span class="chip ${cl}">${ico(ic, ic === "gira" ? "gira" : "")} ${tx}</span></div>${ops}</div>`;
    });
    h += `</div>`;
  });
  h += `</div>`;
  pintar(cuerpo, h);
}
