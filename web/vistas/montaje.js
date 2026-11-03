// Montar un escenario: parametros, confirmacion (doble si es peligroso) y el
// avance en vivo. Lo usan el guion y la pestana de escenarios.
import { esc, ico, duracion, post } from "./comunes.js";

const ui = { confirmando: null, segunda: false, params: {}, error: null, enviando: false };

function definicion(e, clave) {
  return (e.escenarios?.catalogo || []).find((x) => x.clave === clave);
}

// El bloque completo de un escenario: boton, confirmacion o avance.
export function bloque(e, clave, { etiqueta } = {}) {
  const d = definicion(e, clave);
  if (!d) return `<div class="mt-error">Escenario «${esc(clave)}» no declarado en escenarios.yml</div>`;
  const actual = e.escenarios?.actual;
  const bloqueo = e.escenarios?.bloqueo;
  let h = "";
  if (actual && actual.clave === clave && (actual.estado === "corriendo" || Date.now() / 1000 - (actual.fin || 0) < 90)) {
    const seg = ((actual.fin || Date.now() / 1000) - actual.inicio);
    const tit = { corriendo: `${ico("gira", "gira")} Montando · ${duracion(seg)}`, ok: `${ico("check")} Montado en ${duracion(seg)}`,
      fallo: `${ico("x")} No terminó bien` }[actual.estado];
    h += `<div class="mt-avance ${actual.estado}"><b>${tit}</b>
      <pre>${actual.lineas.slice(-5).map(esc).join("\n")}</pre></div>`;
    if (actual.estado === "corriendo") return h;
  }
  if (ui.confirmando === clave) {
    const params = (d.parametros || []).map((p) => {
      const v = ui.params[clave]?.[p.clave] ?? p.defecto;
      return `<label class="mt-param">${esc(p.nombre)}
        <input type="number" min="${p.min ?? ""}" max="${p.max ?? ""}" value="${esc(v)}" data-mt-param="${esc(clave)}:${esc(p.clave)}">
        <span class="tenue">${esc(p.unidad || "")}</span></label>`;
    }).join("");
    const peligro = d.peligroso && ui.segunda;
    h += `<div class="mt-confirmar${d.peligroso ? " peligroso" : ""}">
      <p>${peligro ? `<b>¿Seguro?</b> ` : ""}${esc(d.confirmar)}</p>${params}
      ${ui.error ? `<p class="mt-error">${esc(ui.error)}</p>` : ""}
      <div class="mt-botones">
        <button class="btn ${d.peligroso ? "peligro" : "primario"}" data-mt="confirmar" data-clave="${esc(clave)}" ${ui.enviando ? "disabled" : ""}>
          ${d.peligroso && !ui.segunda ? "Sí, continuar" : d.peligroso ? "Sí, borrar y montar" : "Sí, montar"}</button>
        <button class="btn" data-mt="cancelar">Cancelar</button>
      </div></div>`;
    return h;
  }
  h += `<button class="btn" data-mt="montar" data-clave="${esc(clave)}" ${bloqueo ? `disabled title="${esc(bloqueo)}"` : ""}>
      ${ico("capas")} ${esc(etiqueta || "Montar: " + d.nombre)}</button>`;
  if (bloqueo) h += `<div class="mt-nota">${esc(bloqueo)}</div>`;
  return h;
}

// Los clics y los parametros de los bloques. Devuelve true si los atendio.
export async function click(ev, refrescar) {
  const b = ev.target.closest("[data-mt]");
  if (!b) return false;
  const acc = b.dataset.mt, clave = b.dataset.clave;
  if (acc === "montar") { Object.assign(ui, { confirmando: clave, segunda: false, error: null }); }
  else if (acc === "cancelar") { Object.assign(ui, { confirmando: null, segunda: false, error: null }); }
  else if (acc === "confirmar") {
    const d = definicion(window.__ultimoEstado || {}, clave);
    if (d?.peligroso && !ui.segunda) { ui.segunda = true; refrescar(); return true; }
    ui.enviando = true; refrescar();
    try {
      await post(`api/escenarios/${clave}`, { confirmado: true, parametros: ui.params[clave] || {} });
      Object.assign(ui, { confirmando: null, segunda: false, error: null });
    } catch (e) { ui.error = e.message; }
    ui.enviando = false;
  }
  refrescar();
  return true;
}

export function entrada(ev) {
  const t = ev.target.closest("[data-mt-param]");
  if (!t) return;
  const [clave, p] = t.dataset.mtParam.split(":");
  ui.params[clave] = Object.assign(ui.params[clave] || {}, { [p]: t.value });
}

// Mientras se confirma no se repinta el bloque: se perderia lo que se escribe.
export const confirmando = () => ui.confirmando !== null;
