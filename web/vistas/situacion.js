// La situacion en una frase, y la cifra que la resume: que sitio atiende.
import { esc, ico, icoNivel, n, colorSitio, pintar } from "./comunes.js";

let el;
const ETIQUETA = {
  ok: "Todo en orden", info: "Información", aviso: "Atención", espera: "Esperando una persona",
  critico: "Contingencia", en_curso: "Automatización en curso",
};

export function montar(contenedor) { el = contenedor; }

export function actualizar(e) {
  const s = e.situacion || {};
  el.dataset.nivel = s.nivel || "info";
  const activo = e.activo;
  const sitio = activo ? e.sitios[activo] : null;
  const c = e.contenido || {};
  const otro = (e.pareja.sitios || []).find((x) => x !== activo);
  const datosActivo = sitio?.datos;
  const icono = s.nivel === "en_curso" ? ico("gira", "gira") : ico(icoNivel(s.nivel));

  const heroeActivo = activo
    ? `<div class="bloque">
         <div class="rotulo">Atiende la operación</div>
         <div class="valor" style="color:${colorSitio(e, activo)}">${esc(activo.toUpperCase())}</div>
         <div class="pie">${sitio.rol === "caido" || sitio.rol === "sin_conexion"
           ? `<span style="color:var(--critico-tinta);font-weight:700">${ico("x")} su Kafka no responde</span>`
           : `${esc(sitio.titulo)}${otro ? ` · ${esc(otro.toUpperCase())} en espera` : ""}`}</div>
       </div>`
    : `<div class="bloque"><div class="rotulo">Atiende la operación</div><div class="valor chico tenue">sin definir</div></div>`;

  let heroeContenido = "";
  if (c.medido) {
    heroeContenido = `<div class="sep"></div>
      <div class="bloque">
        <div class="rotulo">Contenido entre sitios</div>
        <div class="valor chico">${c.transito ? `${ico("gira")} al día, en movimiento` : c.igual ? `${ico("igual")} idéntico` : `${ico("distinto")} difiere en ${n(c.diferencia)}`}</div>
        <div class="pie">${datosActivo ? `${n(datosActivo.retenidos)} mensajes en el tópico` : ""}</div>
      </div>`;
  }

  pintar(el, `
    <div class="icono-grande">${icono}</div>
    <div>
      <div class="etiqueta-nivel">${esc(ETIQUETA[s.nivel] || "")}</div>
      <h2>${esc(s.titulo || "")}</h2>
      <p>${esc(s.detalle || "")}</p>
    </div>
    <div class="heroe">${heroeActivo}${heroeContenido}</div>`);
}
