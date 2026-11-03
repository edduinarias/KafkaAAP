// La banda superior de la vista en vivo: de que se trata, quien la construyo,
// si esta en vivo, si Temenos esta escribiendo (solo lo muestra: esta vista no
// mueve nada) y el estado de las credenciales (nunca sus valores).
import { esc, ico, duracion, faltaPara, pintar } from "./comunes.js";

let el, credEl, vivoEl, tmEl, ctxRef;

export function montar(contenedor, ctx) {
  el = contenedor;
  ctxRef = ctx;
  el.innerHTML = `
    <div class="marca">
      <img id="logo-cliente" alt="" class="oculto">
      <div>
        <div class="cliente" id="cliente">Banco Popular Dominicano</div>
        <h1>Continuidad de Kafka <b>· en vivo</b></h1>
      </div>
      <span class="pareja-chip" id="pareja-chip">${ico("datos")} <span>—</span></span>
    </div>
    <div class="espacio"></div>
    <span class="temenos-pill solo-indicador" id="temenos-pill" title="El core bancario simulado"></span>
    <div class="vista-sw" role="group" aria-label="Vista">
      <button data-v="funcional" title="Vista para todo público (tecla F)">Funcional</button>
      <button data-v="tecnica" title="Con el detalle técnico (tecla F)">Técnica</button>
    </div>
    <div class="credenciales" id="credenciales"></div>
    <div class="vivo caido" id="vivo"><span class="punto"></span><span class="txt">Conectando</span><span class="edad"></span></div>
    <button class="boton-tema" id="tema" title="Cambiar entre claro y oscuro" aria-label="Cambiar tema">${ico("luna")}</button>
    <div class="autor">
      <div>
        <div class="por">Solución construida por</div>
        <div class="rh" id="rh-texto"><i></i>Red Hat</div>
      </div>
      <img id="logo-redhat" alt="Red Hat" class="oculto">
    </div>`;
  credEl = el.querySelector("#credenciales");
  vivoEl = el.querySelector("#vivo");
  tmEl = el.querySelector("#temenos-pill");
  // Logos opcionales: si estan en assets/, se usan; si no, queda el texto.
  cargarLogo(el.querySelector("#logo-cliente"), "assets/logo-cliente");
  cargarLogo(el.querySelector("#logo-redhat"), "assets/logo-redhat", () => el.querySelector("#rh-texto").classList.add("oculto"));
  el.querySelector("#tema").addEventListener("click", alternarTema);
  el.querySelector(".vista-sw").addEventListener("click", (ev) => {
    const b = ev.target.closest("button[data-v]");
    if (!b) return;
    const quiere = b.dataset.v === "funcional";
    if (quiere !== document.documentElement.classList.contains("modo-funcional")) ctx.alternarVista();
    pintarVista();
  });
  pintarBotonTema();
  pintarVista();
}

function cargarLogo(img, base, alCargar) {
  const ext = ["svg", "png"];
  const probar = (i) => {
    if (i >= ext.length) return;
    img.onerror = () => probar(i + 1);
    img.onload = () => { img.classList.remove("oculto"); alCargar?.(); };
    img.src = `${base}.${ext[i]}`;
  };
  probar(0);
}

function temaActual() {
  const t = document.documentElement.dataset.theme;
  if (t) return t;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
function alternarTema() {
  const nuevo = temaActual() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = nuevo;
  try { localStorage.setItem("tema", nuevo); } catch (e) {}
  pintarBotonTema();
}
function pintarBotonTema() {
  el.querySelector("#tema").innerHTML = ico(temaActual() === "dark" ? "sol" : "luna");
}
function pintarVista() {
  const f = document.documentElement.classList.contains("modo-funcional");
  el.querySelectorAll(".vista-sw button").forEach((b) => b.classList.toggle("sel", (b.dataset.v === "funcional") === f));
}

export function marcarConexion(ctx) {
  if (!vivoEl) return;
  const edad = ctx.recibido ? (Date.now() - ctx.recibido) / 1000 : null;
  const vivo = ctx.conectado && edad !== null && edad < 10;
  vivoEl.classList.toggle("caido", !vivo);
  vivoEl.querySelector(".txt").textContent = vivo ? "En vivo" : ctx.recibido ? "Reconectando" : "Conectando";
  vivoEl.querySelector(".edad").textContent = edad === null ? "" : edad < 3 ? "ahora" : `hace ${duracion(edad)}`;
  if (ctx.ultimo) pintarCredenciales(ctx.ultimo.credenciales || []);
  pintarVista();
}

function pintarCredenciales(creds) {
  const html = creds.map((c) => {
    let nivel = "ok", texto;
    if (!c.cargado) { nivel = "critico"; texto = "sin token"; }
    else if (!c.valido) { nivel = "critico"; texto = c.error === "HTTP 401" ? "vencido" : (c.error || "no válido"); }
    else if (c.vence) {
      const s = faltaPara(c.vence);
      if (s <= 0) { nivel = "critico"; texto = "vencido"; }
      else { nivel = s < 7200 ? "aviso" : "ok"; texto = duracion(s).replace(/ \d+ s$/, "").replace(/ \d+ min$/, ""); }
    } else texto = "vigente";
    const icono = nivel === "ok" ? "check" : nivel === "aviso" ? "reloj" : "x";
    const titulo = [`Token de ${c.nombre}`, c.identidad && `identidad: ${c.identidad}`, c.archivo && `archivo: ${c.archivo}`,
      c.vence && `vence: ${new Date(c.vence).toLocaleString("es-DO")}`, c.nota].filter(Boolean).join("\n");
    return `<span class="cred ${nivel}" title="${esc(titulo)}">${ico(icono)}<b>${esc(c.nombre)}</b><span class="tenue">${esc(texto)}</span></span>`;
  }).join("");
  pintar(credEl, html);
}

export function actualizar(estado, ctx) {
  const p = estado.pareja || {};
  const chip = el.querySelector("#pareja-chip span");
  chip.textContent = `Pareja ${String(p.clave || "").toUpperCase()}`;
  chip.parentElement.title = p.descripcion || "";
  if (estado.marca?.cliente) el.querySelector("#cliente").textContent = estado.marca.cliente;
  const c = estado.temenos?.continuo;
  const html = c
    ? `<span class="punto-tm"></span><b>Temenos</b> ${c.por_segundo} tx/s por ${esc(c.sitio.toUpperCase())}`
    : `<span class="punto-tm apagado"></span><b>Temenos</b> detenido`;
  if (tmEl._h !== html) { tmEl.innerHTML = html; tmEl._h = html; }
  tmEl.classList.toggle("encendido", !!c);
  marcarConexion(ctx);
}
