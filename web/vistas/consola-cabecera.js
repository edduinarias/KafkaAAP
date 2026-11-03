// La banda superior de la consola: que es, el enlace a la vista en vivo, el
// estado de Temenos (con su boton) y si la consola esta conectada.
import { esc, ico, duracion } from "./comunes.js";

let el, tmEl, vivoEl, enlaceEl;

export function montar(contenedor, ctx) {
  el = contenedor;
  el.innerHTML = `
    <div class="marca">
      <div>
        <div class="cliente" id="cc-cliente">Banco Popular Dominicano</div>
        <h1>Consola de la demo <b>· Kafka DR</b></h1>
      </div>
    </div>
    <div class="espacio"></div>
    <button class="temenos-pill" id="cc-temenos" title="Encender o detener Temenos (tecla T)"></button>
    <a class="boton-demo" id="cc-vivo" target="_blank" rel="noopener" title="La pantalla que ve el público">${ico("externo")} Abrir la vista en vivo</a>
    <div class="vivo caido" id="cc-conexion"><span class="punto"></span><span class="txt">Conectando</span></div>
    <button class="boton-tema" id="cc-tema" title="Claro u oscuro">${ico("luna")}</button>
    <div class="autor"><div><div class="por">Solución construida por</div><div class="rh"><i></i>Red Hat</div></div></div>`;
  tmEl = el.querySelector("#cc-temenos");
  vivoEl = el.querySelector("#cc-conexion");
  enlaceEl = el.querySelector("#cc-vivo");
  tmEl.addEventListener("click", () => ctx.alternarTemenos());
  el.querySelector("#cc-tema").addEventListener("click", () => {
    const actual = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const nuevo = actual === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nuevo;
    try { localStorage.setItem("tema", nuevo); } catch (e) {}
  });
}

export function marcarConexion(ctx) {
  if (!vivoEl) return;
  const edad = ctx.recibido ? (Date.now() - ctx.recibido) / 1000 : null;
  const ok = ctx.conectado && edad !== null && edad < 10;
  vivoEl.classList.toggle("caido", !ok);
  vivoEl.querySelector(".txt").textContent = ok ? "Conectada" : "Reconectando";
}

export function actualizar(e, ctx) {
  if (e.marca?.cliente) el.querySelector("#cc-cliente").textContent = e.marca.cliente;
  const p = e.puertos || {};
  if (p.vivo) enlaceEl.href = `${location.protocol}//${location.hostname}:${p.vivo}/`;
  const c = e.temenos?.continuo;
  const html = c
    ? `<span class="punto-tm"></span><b>Temenos</b> ${c.por_segundo} tx/s por ${esc(c.sitio.toUpperCase())}<span class="accion-tm">${ico("pausa")}</span>`
    : `<span class="punto-tm apagado"></span><b>Temenos</b> detenido<span class="accion-tm">${ico("play")}</span>`;
  if (tmEl._h !== html) { tmEl.innerHTML = html; tmEl._h = html; }
  tmEl.classList.toggle("encendido", !!c);
  marcarConexion(ctx);
}
