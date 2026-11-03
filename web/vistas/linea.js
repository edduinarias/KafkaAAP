// La linea de tiempo: cada cambio del ambiente y de la operacion, en palabras.
import { esc, ico, icoNivel, hora } from "./comunes.js";

let el, lista, filtro = "todo";
const vistos = new Set();
const FILTROS = [["todo", "Todo"], ["operacion", "Operación"], ["ambiente", "Ambiente"], ["datos", "Datos"]];

export function montar(contenedor) {
  el = contenedor;
  el.innerHTML = `<header><h2>Línea de tiempo</h2>
      <div class="der filtros" id="lt-filtros">${FILTROS.map(([k, t]) =>
        `<button class="filtro${k === filtro ? " sel" : ""}" data-f="${k}">${t}</button>`).join("")}</div></header>
    <div class="cuerpo"><ul class="eventos" id="lt-lista"></ul></div>`;
  lista = el.querySelector("#lt-lista");
  el.querySelector("#lt-filtros").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-f]");
    if (!b) return;
    filtro = b.dataset.f;
    el.querySelectorAll(".filtro").forEach((x) => x.classList.toggle("sel", x === b));
    lista._html = null;
    pintarLista();
  });
}

let ultimos = [];
function pintarLista() {
  const ev = ultimos.filter((x) => filtro === "todo" || x.grupo === filtro ||
    (filtro === "ambiente" && ["ambiente", "rol", "simulacion", "sistema"].includes(x.grupo)));
  const html = ev.length ? ev.map((x) => {
    const clave = x.t + x.texto;
    const nuevo = lista._html && !vistos.has(clave);
    vistos.add(clave);
    return `<li class="evento ${esc(x.nivel)}${nuevo ? " nuevo" : ""}"><span class="h num">${hora(x.t)}</span>
      ${ico(icoNivel(x.nivel))}<span>${esc(x.texto)}</span></li>`;
  }).join("") : `<li class="vacio">Sin cambios todavía. Todo lo que pase en el ambiente o en AAP aparece aquí.</li>`;
  const sinMarcas = html.replace(/ nuevo"/g, '"');
  if (lista._base !== sinMarcas) {
    lista.innerHTML = html;
    lista._base = sinMarcas;
    lista._html = html;
  }
}

export function actualizar(e) {
  // El avance del guion es del presentador: el publico no lo ve.
  ultimos = (e.eventos || []).filter((x) => x.grupo !== "guion");
  pintarLista();
}
