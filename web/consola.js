// La consola de la demo: la pantalla del presentador. Los casos de uso, lo que
// esta pasando ahora, y las herramientas que mueven el laboratorio.
// La vista en vivo (la que se proyecta) esta en su propio puerto y solo mira.
//
// Atajo: T enciende o detiene Temenos.

import * as cabecera from "./vistas/consola-cabecera.js";
import * as casosDemo from "./vistas/consola-casos.js";
import * as guion from "./vistas/consola-guion.js";
import * as ahora from "./vistas/consola-ahora.js";
import * as escenarios from "./vistas/escenarios.js";
import * as temenos from "./vistas/temenos.js";
import { post, ico } from "./vistas/comunes.js";

const ctx = {
  ultimo: null,
  recibido: 0,
  conectado: false,
  refrescar: () => ctx.ultimo && aplicar(ctx.ultimo),
  alternarTemenos: () => post("api/temenos/alternar").then(() => {}).catch((e) => alert(e.message)),
};

// Herramientas: pestanas con los modulos que ya existen.
// El guion de punta a punta queda como recorrido sugerido, opcional.
const PESTANAS = [["escenarios", "Escenarios", escenarios], ["temenos", "Temenos", temenos], ["recorrido", "Recorrido sugerido", guion]];
const herr = document.getElementById("herramientas");
herr.innerHTML = `<nav class="pd-pestanas">${PESTANAS.map(([k, t]) => `<button data-p="${k}">${t}</button>`).join("")}</nav>
  <div class="pd-cuerpo">${PESTANAS.map(([k]) => `<section class="pd-seccion" data-p="${k}" id="h-${k}"></section>`).join("")}</div>`;
function elegir(k) {
  herr.querySelectorAll("[data-p]").forEach((x) => x.classList.toggle("sel", x.dataset.p === k));
  try { localStorage.setItem("herramienta", k); } catch (e) {}
}
herr.querySelector(".pd-pestanas").addEventListener("click", (ev) => {
  const b = ev.target.closest("button[data-p]");
  if (b) elegir(b.dataset.p);
});
let inicial = "escenarios";
try { inicial = localStorage.getItem("herramienta") || inicial; } catch (e) {}
if (!PESTANAS.some(([k]) => k === inicial)) inicial = "escenarios";
elegir(inicial);

const VISTAS = [
  ["cabecera", cabecera], ["casos", casosDemo], ["ahora", ahora],
  ...PESTANAS.map(([k, , m]) => ["h-" + k, m]),
];
for (const [id, v] of VISTAS) {
  try { v.montar?.(document.getElementById(id), ctx); } catch (e) { console.error("montar", id, e); }
}

function aplicar(estado) {
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

function conectar() {
  const es = new EventSource("api/eventos");
  es.addEventListener("estado", (e) => {
    ctx.conectado = true;
    try { recibir(JSON.parse(e.data)); } catch (err) { console.error(err); }
  });
  es.onerror = () => { ctx.conectado = false; cabecera.marcarConexion?.(ctx); };
}
fetch("api/estado").then((r) => r.json()).then((d) => { if (d && d.sitios) recibir(d); }).catch(() => {});
conectar();

document.addEventListener("keydown", (ev) => {
  if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement?.tagName)) return;
  if (ev.key.toLowerCase() === "t") { ev.preventDefault(); ctx.alternarTemenos(); }
});
setInterval(() => cabecera.marcarConexion?.(ctx), 1000);
