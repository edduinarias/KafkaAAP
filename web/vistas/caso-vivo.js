// La franja del caso de uso en la vista en vivo: que caso se esta mostrando y
// que va a hacer -o hizo- la automatizacion, en una frase para el publico. La
// elige el presentador en la consola; sin caso elegido, no se muestra.
import { esc, ico, pintar } from "./comunes.js";

let el;
const NIVEL = { nada: "ok", reanudacion: "curso", detiene: "critico", no_aplica: "neutro", no_construida: "neutro" };

export function montar(contenedor) { el = contenedor; }

export function actualizar(e) {
  const s = e.demo?.seleccion;
  el.classList.toggle("oculto", !s);
  if (!s) return pintar(el, "");
  const real = s.real;
  let estado;
  if (real && real.salida != null) {
    estado = real.coincide
      ? `<span class="cv-real ok">${ico("check")} La automatización decidió: ${esc(real.titulo_real || real.salida)}</span>`
      : `<span class="cv-real aviso">${ico("alerta")} La automatización decidió: ${esc(real.titulo_real || real.salida)}</span>`;
  } else if (real) {
    estado = `<span class="cv-real curso">${ico("gira", "gira")} Validando el estado real…</span>`;
  } else {
    estado = `<span class="cv-real">${ico("info")} Lo que va a hacer</span>`;
  }
  pintar(el, `
    <div class="cv-caso"><span class="cv-rotulo">Caso de uso${s.seccion ? ` · procedimiento ${esc(s.seccion)}` : ""}</span>
      <b>${esc(s.nombre)}</b><span class="cv-dir">${esc(s.direccion.replace("_a_", " → ").toUpperCase())}</span></div>
    <div class="cv-salida ${s.salida.nivel || NIVEL[s.anticipo.salida] || "curso"}">
      ${estado}
      <b>${esc(s.titulo_salida)}</b><span>${esc(s.salida.frase_publico || s.anticipo.motivo || "")}</span>
    </div>`);
}
