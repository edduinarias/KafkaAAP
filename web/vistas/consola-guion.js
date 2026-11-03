// El guion del presentador: el paso actual con lo que se dice, lo que se hace,
// lo que se va a ver (marcado cuando la pagina lo detecta) y lo que pasa por
// dentro. La consola marca sola cada paso cuando se cumple.
import { esc, ico, horaCorta, post, pintar } from "./comunes.js";
import * as montaje from "./montaje.js";

let el, error = null;

export function montar(contenedor, ctx) {
  el = contenedor;
  el.innerHTML = `<div id="cg-cab"></div><div id="cg-paso"></div>`;
  el.addEventListener("click", async (ev) => {
    if (await montaje.click(ev, () => ctx.refrescar())) return;
    const b = ev.target.closest("[data-cg]");
    if (!b) return;
    const acc = b.dataset.cg;
    try {
      error = null;
      if (acc === "temenos-encender" || acc === "temenos-detener") {
        const d = ctx.ultimo?.temenos_defecto || {};
        await post("api/temenos/continuo", acc === "temenos-detener" ? { detener: true } : { sitio: d.sitio, por_segundo: d.por_segundo });
      } else {
        if (acc === "ir" && !confirm(`¿Ir al paso ${+b.dataset.i + 1}? Los pasos siguientes vuelven a quedar pendientes.`)) return;
        if (acc === "iniciar" && ctx.ultimo?.guion?.activo && !confirm("¿Empezar el guion desde el principio?")) return;
        if (acc === "terminar" && !confirm("¿Terminar el guion?")) return;
        await post("api/guion", { accion: acc, indice: b.dataset.i });
      }
    } catch (e) { error = e.message; }
    ctx.refrescar();
  });
  el.addEventListener("input", montaje.entrada);
}

function nombreCaso(e, op) {
  for (const f of e.casos?.filas || []) for (const c of f.celdas) for (const o of c.operaciones) if (o.operacion === op) return o.nombre;
  return op;
}

function cabecera(e, g) {
  const actos = g.actos || {};
  const porActo = {};
  g.pasos.forEach((p) => { (porActo[p.acto] = porActo[p.acto] || []).push(p); });
  if (!g.activo) {
    const completo = g.hechos && g.hechos === g.total;
    return `<div class="cg-inicio">
      <div><h2>${completo ? `${ico("check")} Demo completa` : "Guion de la demo"}</h2>
        <p>Cada paso dice qué decir, qué hacer y qué vas a ver. La consola los marca sola cuando se cumplen.</p>
        <ul class="cg-actos">${Object.entries(porActo).map(([a, ps]) => `<li><b>Acto ${a} · ${esc(actos[a]?.titulo || "")}</b>
          <span class="tenue">${esc(actos[a]?.tarda || "")}${actos[a]?.opcional ? " · opcional" : ""} · pasos ${ps[0].indice + 1} a ${ps[ps.length - 1].indice + 1}</span></li>`).join("")}</ul></div>
      <button class="btn primario grande" data-cg="iniciar">${ico("play")} Iniciar el guion</button></div>`;
  }
  const fila = Object.entries(porActo).map(([a, ps]) => `<div class="cg-acto"><span class="cg-acto-tit">Acto ${a} · ${esc(actos[a]?.titulo || "")}</span>
      <div class="cg-chips">${ps.map((p) => `<button class="cg-chip ${p.estado}" data-cg="${p.estado === "actual" ? "" : "ir"}" data-i="${p.indice}"
        title="${esc(p.titulo)}">${p.estado === "hecho" ? ico("check") : p.indice + 1}</button>`).join("")}</div></div>`).join("");
  return `<div class="cg-progreso">${fila}
      <div class="cg-botones"><button class="btn chico" data-cg="iniciar">Empezar de nuevo</button>
        <button class="btn chico" data-cg="terminar">Terminar</button></div></div>`;
}

function haces(p, e) {
  const out = [];
  if (p.escenario) out.push(montaje.bloque(e, p.escenario));
  if (p.temenos) {
    const c = e.temenos?.continuo, d = e.temenos_defecto || {};
    if (p.temenos === "encender") {
      out.push(c ? `<div class="gn-ok">${ico("check")} Temenos escribiendo: ${c.por_segundo} tx/s por ${esc(c.sitio.toUpperCase())}</div>`
        : `<button class="btn primario" data-cg="temenos-encender">${ico("play")} Encender Temenos · ${d.por_segundo || 5} tx/s por ${esc((d.sitio || "co").toUpperCase())}</button>`);
    } else {
      out.push(c ? `<button class="btn primario" data-cg="temenos-detener">${ico("pausa")} Detener Temenos</button>`
        : `<div class="gn-ok">${ico("check")} Temenos detenido</div>`);
    }
  }
  if (p.aap) {
    const a = p.aap;
    const flujo = (e.casos?.filas || []).flatMap((f) => f.celdas).flatMap((c) => c.operaciones).find((o) => o.operacion === a.operacion);
    out.push(`<div class="gn-aap">
      ${a.url ? `<a class="btn primario" href="${esc(a.url)}" target="_blank" rel="noopener">${ico("externo")} Abrir el flujo en AAP</a>` : ""}
      <div class="gn-form">Flujo <b>${esc(flujo?.flujo || a.operacion)}</b><br>En el formulario: <b>pareja core</b> · <b>dirección ${esc(a.direccion || "")}</b></div></div>`);
    const op = p.operacion;
    if (op) {
      const s = e.situacion || {};
      const t = op.en_curso ? `${ico("gira", "gira")} Flujo #${op.id} en curso: ${esc(e.operacion?.fase_texto || "")}`
        : op.estado === "successful" ? `${ico("check")} Flujo #${op.id} terminó bien`
        : `${ico("alerta")} Flujo #${op.id}: ${esc(s.titulo || op.estado)}. Corrige y vuelve a lanzarlo.`;
      out.push(`<div class="gn-op ${op.en_curso ? "curso" : op.estado === "successful" ? "ok" : "aviso"}">${t}</div>`);
    }
  }
  if (p.manual) out.push(`<button class="btn primario" data-cg="listo">${ico("check")} Listo, siguiente paso</button>`);
  return out.join("");
}

function pasoActual(e, g) {
  const p = g.pasos[g.indice];
  const sig = g.pasos[g.indice + 1];
  return `<article class="cg-paso">
    <div class="cg-tit"><span class="cg-n">${p.indice + 1}</span>
      <div><h2>${esc(p.titulo)}</h2>
        <div class="cg-meta"><span class="chip curso">${esc(nombreCaso(e, p.caso))}</span>${p.tarda ? `<span class="tenue">${ico("reloj")} ${esc(p.tarda)}</span>` : ""}</div></div></div>
    <div class="cg-bloque cg-dices"><label>Dices</label><blockquote>«${esc(p.dices)}»</blockquote>
      ${p.amplia?.length ? `<ul class="cg-amplia">${p.amplia.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}</div>
    <div class="cg-bloque"><label>Haces</label><p>${esc(p.haces)}</p>
      ${p.avisos.map((a) => `<div class="gn-aviso">${ico("alerta")}<span>${esc(a)}</span></div>`).join("")}
      <div class="gn-acciones">${haces(p, e)}</div></div>
    ${p.ves.length ? `<div class="cg-bloque"><label>Vas a ver</label><ul class="cg-ves">${p.ves.map((v) =>
      `<li class="${v.visto ? "si" : ""}">${ico(v.visto ? "check" : "circulo")}<span>${esc(v.texto)}</span></li>`).join("")}</ul></div>` : ""}
    ${p.por_dentro ? `<details class="cg-dentro"><summary>Por dentro <span class="tenue">· si preguntan qué hace la automatización</span></summary><p>${esc(p.por_dentro)}</p></details>` : ""}
    <div class="cg-nav">
      ${p.indice > 0 ? `<button class="btn chico" data-cg="ir" data-i="${p.indice - 1}">${ico("flecha", "atras")} Paso anterior</button>` : "<span></span>"}
      ${p.manual ? "" : `<button class="gn-saltar" data-cg="listo">Marcar como hecho y seguir</button>`}
    </div>
    ${sig ? `<div class="cg-siguiente">Después: <b>${sig.indice + 1} · ${esc(sig.titulo)}</b></div>` : ""}
  </article>`;
}

export function actualizar(e) {
  window.__ultimoEstado = e;
  const g = e.guion || { pasos: [] };
  pintar(el.querySelector("#cg-cab"), cabecera(e, g) + (error ? `<p class="mt-error">${esc(error)}</p>` : ""));
  if (montaje.confirmando() && el.querySelector(".mt-confirmar input:focus")) return;
  pintar(el.querySelector("#cg-paso"), g.activo && g.pasos.length ? pasoActual(e, g) : "");
}
