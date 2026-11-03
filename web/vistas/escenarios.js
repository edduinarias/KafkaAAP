// Montar cualquier escenario suelto, fuera del guion. Cada tarjeta dice si el
// ambiente ya esta ahi y que caso de uso habilita.
import { esc, ico, pintar } from "./comunes.js";
import * as montaje from "./montaje.js";

let el;

export function montar(contenedor, ctx) {
  el = contenedor;
  el.innerHTML = `<p class="pd-intro">Preparan el ambiente con las herramientas de escenario. Nunca lanzan una operación: eso se hace en AAP.</p>
    <div class="es-lista" id="es-lista"></div>`;
  el.addEventListener("click", (ev) => montaje.click(ev, () => ctx.refrescar()));
  el.addEventListener("input", montaje.entrada);
}

export function actualizar(e) {
  window.__ultimoEstado = e;
  if (montaje.confirmando() && el.querySelector(".mt-confirmar input:focus")) return;
  const nombres = {};
  (e.casos?.filas || []).forEach((f) => f.celdas.forEach((c) => c.operaciones.forEach((o) => { nombres[o.operacion] = o.nombre; })));
  const html = (e.escenarios?.catalogo || []).map((d) => `
    <div class="es-tarjeta${d.vigente ? " vigente" : ""}${d.peligroso ? " peligroso" : ""}">
      <div class="es-cab"><b>${esc(d.nombre)}</b>${d.vigente ? `<span class="chip ok">${ico("check")} el ambiente está aquí</span>` : ""}</div>
      <p>${esc(d.descripcion)}</p>
      ${d.habilita?.length ? `<div class="es-habilita">Habilita: ${d.habilita.map((o) => `<span class="chip curso">${esc(nombres[o] || o)}</span>`).join(" ")}</div>` : ""}
      <div class="es-accion">${montaje.bloque(e, d.clave, { etiqueta: "Montar" })}</div>
    </div>`).join("");
  pintar(el.querySelector("#es-lista"), html);
}
