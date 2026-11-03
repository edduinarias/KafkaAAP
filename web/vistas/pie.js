// El pie: la autoria y de donde sale cada lectura, con su frescura.
import { esc, pintar } from "./comunes.js";

let el;
const NOMBRES = { sitio_co: "API CO", sitio_ca: "API CA", metricas_co: "métricas CO", metricas_ca: "métricas CA",
  metricas: null, aap: "AAP", credenciales: "credenciales", vista: null };

export function montar(contenedor) { el = contenedor; }

export function actualizar(e) {
  const f = e.salud || {};
  const fuentes = Object.entries(f).filter(([k]) => NOMBRES[k] !== null).map(([k, v]) => {
    const nombre = NOMBRES[k] || k.replace("_", " ");
    const clase = !v.ok ? "mal" : v.antiguedad > 20 && k !== "credenciales" ? "vieja" : "";
    const t = !v.ok ? (v.error || "error") : `${(v.ms / 1000).toFixed(1).replace(".", ",")} s`;
    return `<span class="fuente ${clase}" title="${esc(v.ok ? "última lectura correcta" : "la última lectura falló")}"><i></i>${esc(nombre)} ${esc(t)}</span>`;
  }).join("");
  pintar(el, `
    <span class="firma"><i></i><span>Solución construida por <b>Red Hat</b> · Ansible Automation Platform · OpenShift · Streams for Apache Kafka</span></span>
    <span class="fuentes">${fuentes}</span>`);
}
