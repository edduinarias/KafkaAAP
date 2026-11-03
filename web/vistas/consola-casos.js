// La demo por caso de uso, para el presentador. Se elige el caso y la
// direccion; la consola anticipa que va a decidir la automatizacion con el
// ambiente como esta, y muestra que decir, que hacer, que se va a ver y que pasa
// por dentro para esa salida. La vista en vivo muestra el mismo caso.
import { esc, ico, post, pintar } from "./comunes.js";
import * as montaje from "./montaje.js";

let el, error = null;
// El procedimiento se repinta con cada cambio del estado: se recuerda si el
// presentador lo dejo abierto o cerrado.
let procAbierto = true;
const RITMOS = [1, 2, 5, 10];

export function montar(contenedor, ctx) {
  el = contenedor;
  el.innerHTML = `<div id="cs-tabs"></div><div id="cs-cuerpo"></div>`;
  el.addEventListener("click", async (ev) => {
    if (await montaje.click(ev, () => ctx.refrescar())) return;
    const b = ev.target.closest("[data-cs]");
    if (!b) return;
    const acc = b.dataset.cs;
    error = null;
    try {
      if (acc === "caso") await post("api/demo/caso", { caso: b.dataset.caso || null, direccion: b.dataset.dir || null });
      else if (acc === "dir") await post("api/demo/caso", { caso: ctx.ultimo?.demo?.seleccion?.caso, direccion: b.dataset.dir });
      else if (acc === "temenos") {
        const d = ctx.ultimo?.temenos_defecto || {};
        await post("api/temenos/continuo", b.dataset.ritmo ? { sitio: d.sitio, por_segundo: +b.dataset.ritmo } : { detener: true });
      }
    } catch (e) { error = e.message; }
    ctx.refrescar();
  });
  el.addEventListener("input", montaje.entrada);
  el.addEventListener("toggle", (ev) => {
    if (ev.target.classList?.contains("cs-proc")) procAbierto = ev.target.open;
  }, true);
}

const QUIEN = { tu: "Tú", aap: "Automatización", no_se_hace: "No se ejecuta", fuera: "Fuera de esta pareja" };

function procedimiento(p) {
  if (p.error) return `<div class="cg-bloque"><label>Procedimiento §${esc(p.seccion)}</label><p class="mt-error">${esc(p.error)}</p></div>`;
  const tuyos = p.pasos.filter((x) => x.quien === "tu").length;
  const paso = (x) => `<li class="${esc(x.quien || "")}"><span class="n">${esc(x.n ?? "·")}</span><div>
      <div class="cs-paso-cab">${x.titulo ? `<b>${esc(x.titulo)}</b>` : ""}${QUIEN[x.quien] ? `<span class="cs-quien ${esc(x.quien)}">${esc(QUIEN[x.quien])}</span>` : ""}</div>
      ${x.como ? `<p>${esc(x.como)}</p>` : ""}
      ${x.porque ? `<p class="cs-porque">Por qué, según el procedimiento: «${esc(x.porque)}»</p>` : ""}
      ${x.cita ? `<p class="cs-porque">Según el procedimiento, ${esc(x.cita)}</p>` : ""}</div></li>`;
  return `<details class="cg-bloque cs-proc"${procAbierto ? " open" : ""}><summary><label>Procedimiento §${esc(p.seccion)}</label>
      <span class="tenue">${esc(p.nombre)} · ${p.pasos.length} pasos, ${tuyos} ${tuyos === 1 ? "es tuyo" : "son tuyos"}</span></summary>
    ${p.nota ? `<p class="cs-proc-nota">${esc(p.nota)}</p>` : ""}
    <ol class="cs-pasos">${p.pasos.map(paso).join("")}</ol>
    ${p.extras?.length ? `<label class="cs-extras">Además, lo que esos pasos no nombran</label><ol class="cs-pasos extras">${p.extras.map(paso).join("")}</ol>` : ""}
  </details>`;
}

const NIVEL = { nada: "ok", reanudacion: "curso", detiene: "critico", no_aplica: "neutro", no_construida: "neutro" };
const dirTxt = (d) => d.replace("_a_", " → ").toUpperCase();

function pestanas(d) {
  const sel = d.seleccion?.caso;
  return `<div class="cs-tabs">${d.casos.map((c) => `<button class="cs-tab${c.clave === sel ? " sel" : ""}${c.proximo ? " proximo" : ""}"
      data-cs="caso" data-caso="${esc(c.clave)}" ${c.proximo ? "disabled" : ""} title="${esc(c.que_es)}">${esc(c.nombre)}${c.seccion ? ` <small>${esc(c.seccion)}</small>` : ""}${c.proximo ? ` <small>· próximo</small>` : ""}</button>`).join("")}
    ${sel ? `<button class="cs-tab limpiar" data-cs="caso" data-caso="" title="Dejar de mostrar el caso en la vista en vivo">${ico("x")}</button>` : ""}</div>`;
}

function temenosControl(e, quiere) {
  const c = e.temenos?.continuo;
  const chips = RITMOS.map((r) => `<button class="cs-ritmo${c?.por_segundo === r ? " sel" : ""}" data-cs="temenos" data-ritmo="${r}">${r}/s</button>`).join("");
  if (quiere === "detener") {
    return c ? `<button class="btn primario" data-cs="temenos">${ico("pausa")} Detener Temenos</button>`
      : `<div class="gn-ok">${ico("check")} Temenos detenido</div>`;
  }
  return `<div class="cs-temenos">${c ? `<span class="gn-ok">${ico("check")} Temenos a ${c.por_segundo} tx/s</span>` : `<span>Encender Temenos:</span>`}
    ${chips}${c ? `<button class="btn chico" data-cs="temenos">${ico("pausa")} Detener</button>` : ""}</div>`;
}

function cuerpo(e) {
  const s = e.demo?.seleccion;
  if (!s) {
    return `<div class="cs-intro"><h2>Casos de uso</h2>
      <p>Uno por capítulo del procedimiento operativo de BPD. Elige un caso: la consola anticipa qué va a decidir la automatización con el ambiente como está, y la vista en vivo lo muestra al público.</p>
      <p class="tenue">El failover del §2.1 y la conmutación planificada del §1.2 se lanzan con el mismo flujo de AAP: la automatización elige por el estado real. Por eso cada caso dice si el ambiente está en su punto de partida.</p></div>`;
  }
  const a = s.anticipo, sal = s.salida, nivel = sal.nivel || NIVEL[a.salida] || "curso";
  const real = s.real;
  let h = `<div class="cs-cab"><div><h2>${esc(s.nombre)}${s.seccion ? ` <span class="cs-seccion">Procedimiento ${esc(s.seccion)}</span>` : ""}</h2><p>${esc(s.que_es)}</p></div>
    <div class="cs-dir"><span>Dirección</span><div class="segmentado">${s.direcciones.map((d) =>
      `<button class="${d === s.direccion ? "sel" : ""}" data-cs="dir" data-dir="${esc(d)}">${esc(dirTxt(d))}</button>`).join("")}</div></div></div>`;

  if (s.etapas?.length) {
    h += `<div class="cs-etapas">${s.etapas.map((x, i) => `<div class="cs-etapa${x.actual ? " actual" : ""}"><span class="n">${i + 1}</span>
      <div><b>${esc(x.operacion === "failback_preparativos" ? "Preparativos" : "Restauración")}</b><span class="tenue">${esc(x.titulo)}</span></div></div>`).join(`<span class="cs-flecha">${ico("flecha")}</span>`)}
      <div class="cs-etapa-nota tenue">Entre las dos etapas una persona confirma: paso 8 del procedimiento.</div></div>`;
  }

  h += `<div class="cs-anticipo ${nivel}">
      <label>Ahora, con el ambiente como está, la automatización…</label>
      <h3>${esc(s.titulo_salida)}</h3>
      <p class="cs-frase">${esc(sal.frase_publico || "")}</p>
      ${a.motivo ? `<p class="cs-motivo">${esc(a.motivo)}</p>` : ""}
      ${(a.fallas || []).slice(1).map((f) => `<p class="cs-motivo">${ico("x")} ${esc(f)}</p>`).join("")}
      ${(a.avisos || []).map((x) => `<div class="gn-aviso">${ico("alerta")}<span>${esc(x)}</span></div>`).join("")}
      ${a.acciones?.length && ["reanudacion", "detiene"].includes(a.salida) ? `<ol class="cs-acciones">${a.acciones.map((x) =>
        `<li class="${x.aplicada ? "si" : ""}">${esc(x.titulo)}${x.aplicada ? ` <span class="tenue">· ya aplicada</span>` : ""}</li>`).join("")}</ol>` : ""}
      ${a.transicion ? `<span class="cs-tec solo-tecnico">transición ${esc(a.transicion)}</span>` : ""}
    </div>`;

  if (real) {
    const t = real.salida == null ? `${ico("gira", "gira")} Flujo #${real.id}: validando…`
      : real.coincide ? `${ico("check")} Flujo #${real.id}: la automatización decidió <b>${esc(real.titulo_real || real.salida)}</b>, como se anticipó`
      : `${ico("alerta")} Flujo #${real.id}: se anticipó <b>${esc(real.anticipado)}</b> y la automatización decidió <b>${esc(real.titulo_real || real.salida)}</b>`;
    h += `<div class="cs-real ${real.salida == null ? "curso" : real.coincide ? "ok" : "aviso"}">${t}</div>`;
  }

  h += `<div class="cg-bloque cg-dices"><label>Dices</label><blockquote>«${esc(sal.dices || "")}»</blockquote>
      ${sal.amplia?.length ? `<ul class="cg-amplia">${sal.amplia.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}</div>`;

  const acciones = [];
  if (sal.temenos) acciones.push(temenosControl(e, sal.temenos));
  if (sal.nivel !== "neutro" && (["nada", "reanudacion", "detiene"].includes(a.salida) || a.salida === a.transicion)) {
    acciones.push(`<div class="gn-aap">${s.url_flujo ? `<a class="btn primario" href="${esc(s.url_flujo)}" target="_blank" rel="noopener">${ico("externo")} Abrir el flujo en AAP</a>` : ""}
      <div class="gn-form">En el formulario: <b>pareja core</b> · <b>dirección ${esc(s.direccion)}</b></div></div>`);
  }
  h += `<div class="cg-bloque"><label>Haces</label><p>${esc(sal.haces || "")}</p><div class="gn-acciones">${acciones.join("")}</div>
      ${error ? `<p class="mt-error">${esc(error)}</p>` : ""}</div>`;

  if (sal.ves?.length) {
    h += `<div class="cg-bloque"><label>Vas a ver</label><ul class="cg-ves">${sal.ves.map((v) =>
      `<li class="${v.visto ? "si" : ""}">${ico(v.visto ? "check" : "circulo")}<span>${esc(v.texto)}</span></li>`).join("")}</ul></div>`;
  }
  if (s.procedimiento) h += procedimiento(s.procedimiento);
  if (sal.por_dentro) h += `<details class="cg-dentro"><summary>Por dentro <span class="tenue">· si preguntan qué hace la automatización</span></summary><p>${esc(sal.por_dentro)}</p></details>`;

  if (s.otras?.length) {
    h += `<div class="cs-otras"><label>Otras situaciones de este caso</label>${s.otras.map((x) => `<div class="cs-otra">
        <div><b>${esc(x.titulo)}</b><span>${esc(x.frase)}</span></div>
        <div class="cs-otra-acc">${x.montar ? montaje.bloque(e, x.montar, { etiqueta: "Montar el escenario" })
          : x.salida === "nada" ? `<button class="btn chico" data-cs="dir" data-dir="${esc(s.destino)}_a_${esc(s.origen)}">Elegir ${esc(dirTxt(s.destino + "_a_" + s.origen))}</button>`
          : `<span class="tenue">${esc(x.pista || "")}</span>`}</div></div>`).join("")}</div>`;
  }
  return h;
}

export function actualizar(e) {
  window.__ultimoEstado = e;
  const d = e.demo || { casos: [] };
  pintar(el.querySelector("#cs-tabs"), pestanas(d));
  if (montaje.confirmando() && el.querySelector(".mt-confirmar input:focus")) return;
  pintar(el.querySelector("#cs-cuerpo"), cuerpo(e));
}
