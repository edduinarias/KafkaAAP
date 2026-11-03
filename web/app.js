// Orquestador de la pagina: recibe el estado del servidor por SSE y se lo pasa a
// cada vista. Cada vista es un modulo independiente con montar() y actualizar();
// agregar una es importarla y sumarla a VISTAS con el id de su contenedor.
//
// Es la vista en vivo: la que se proyecta. Solo mira; lo que mueve el
// laboratorio esta en la consola (consola.html, en su propio puerto).
// Atajo: F alterna la vista funcional y la tecnica.

import * as encabezado from "./vistas/encabezado.js";
import * as situacion from "./vistas/situacion.js";
import * as topologia from "./vistas/topologia.js";
import * as operacion from "./vistas/operacion.js";
import * as datos from "./vistas/datos.js";
import * as linea from "./vistas/linea.js";
import * as pie from "./vistas/pie.js";
import * as caso from "./vistas/caso-vivo.js";

const VISTAS = [
  ["encabezado", encabezado],
  ["caso", caso],
  ["situacion", situacion],
  ["topologia", topologia],
  ["operacion", operacion],
  ["datos", datos],
  ["linea", linea],
  ["pie", pie],
];

const ctx = {
  ultimo: null,          // ultimo estado recibido
  recibido: 0,           // cuando llego (ms)
  conectado: false,
  refrescar: () => ctx.ultimo && aplicar(ctx.ultimo),
  alternarVista: () => {
    const funcional = !document.documentElement.classList.contains("modo-funcional");
    document.documentElement.classList.toggle("modo-funcional", funcional);
    try { localStorage.setItem("vista", funcional ? "funcional" : "tecnica"); } catch (e) {}
    ctx.refrescar();
  },
};

for (const [id, v] of VISTAS) {
  const el = document.getElementById(id);
  try { v.montar?.(el, ctx); } catch (e) { console.error("montar", id, e); }
}

function aplicar(estado) {
  // La marca del cliente, si la configuracion la trae.
  const m = estado.marca || {};
  if (m.color_banda) {
    document.documentElement.style.setProperty("--banda", m.color_banda);
    document.documentElement.style.setProperty("--banda-2", m.color_banda);
  }
  for (const [id, v] of VISTAS) {
    try { v.actualizar?.(estado, ctx); } catch (e) { console.error("vista", id, e); }
  }
}

function recibir(estado) {
  ctx.ultimo = estado;
  ctx.recibido = Date.now();
  aplicar(estado);
}

// SSE con reconexion; si el navegador no lo soporta, consulta periodica.
function conectar() {
  if (!("EventSource" in window)) {
    setInterval(() => fetch("api/estado").then((r) => r.json()).then(recibir).catch(() => {}), 2000);
    return;
  }
  const es = new EventSource("api/eventos");
  es.addEventListener("estado", (e) => {
    ctx.conectado = true;
    try { recibir(JSON.parse(e.data)); } catch (err) { console.error(err); }
  });
  es.onerror = () => { ctx.conectado = false; encabezado.marcarConexion?.(ctx); };
}

fetch("api/estado").then((r) => r.json()).then((d) => { if (d && d.sitios) recibir(d); }).catch(() => {});
conectar();

// Atajos de teclado, salvo mientras se escribe en un campo.
document.addEventListener("keydown", (ev) => {
  if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement?.tagName)) return;
  const k = ev.key.toLowerCase();
  if (k === "f") { ev.preventDefault(); ctx.alternarVista(); }
});

// El indicador "en vivo" y los tiempos relativos avanzan aunque no llegue nada.
setInterval(() => { encabezado.marcarConexion?.(ctx); }, 1000);
