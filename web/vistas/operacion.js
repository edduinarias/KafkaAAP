// La operacion de AAP en curso (o la ultima): sus cuatro fases, el plan de
// acciones con su resultado real, el estado esperado contra el que se ve ahora
// y los controles previos. Sin operacion, lo que se puede lanzar.
import { esc, ico, n, hora, horaCorta, duracion, haceCuanto, pintar } from "./comunes.js";

let el, cuerpo, abiertos = new Set();

export function montar(contenedor) {
  el = contenedor;
  el.innerHTML = `<header><h2>Operación de AAP</h2><span class="sub" id="op-sub"></span><div class="der" id="op-der"></div></header>
    <div class="cuerpo" id="op-cuerpo"></div>`;
  cuerpo = el.querySelector("#op-cuerpo");
  // Recordar que <details> abrio la persona, entre repintados.
  cuerpo.addEventListener("toggle", (ev) => {
    const id = ev.target.dataset?.id;
    if (!id) return;
    if (ev.target.open) { abiertos.add(id); abiertos.delete("cerrado:" + id); }
    else { abiertos.delete(id); abiertos.add("cerrado:" + id); }
  }, true);
}

const ESTADO_OP = {
  successful: ["ok", "check", "Terminó bien"], failed: ["critico", "x", "Falló"], error: ["critico", "x", "Error"],
  canceled: ["neutro", "x", "Cancelada"], running: ["curso", "gira", "En curso"], pending: ["curso", "reloj", "En cola"],
  waiting: ["curso", "reloj", "En cola"], new: ["curso", "reloj", "Nueva"],
};

function chipEstado(op) {
  if (op.en_curso && op.fases?.[1]?.estado === "esperando") return `<span class="chip espera">${ico("arena")} Esperando aprobación</span>`;
  const [c, i, t] = ESTADO_OP[op.estado] || ["neutro", "info", op.estado];
  return `<span class="chip ${c}">${ico(i, i === "gira" ? "gira" : "")} ${esc(t)}</span>`;
}

function paso(f, i, op) {
  const icono = { hecho: ico("check"), fallo: ico("x"), en_curso: ico("gira", "gira"), esperando: ico("arena"),
    omitido: "–", cancelado: "–" }[f.estado] || String(i + 1);
  let detalle = f.subtitulo;
  if (f.clave === "aprobacion" && op.aprobacion?.por && f.estado === "hecho") detalle = `aprobó ${op.aprobacion.por}`;
  if (f.clave === "aprobacion" && f.estado === "fallo") detalle = op.aprobacion?.resultado || "no aprobada";
  if (f.clave === "validacion" && op.prechecks?.length && f.estado !== "pendiente") {
    const ok = op.prechecks.filter((p) => p.ok).length;
    detalle = `${ok} de ${op.prechecks.length} controles en verde`;
  }
  if (f.clave === "ejecucion" && op.acciones?.length && f.estado !== "pendiente" && f.estado !== "omitido") {
    const h = op.acciones.filter((a) => a.estado === "hecho").length;
    detalle = `${h} de ${op.acciones.length} acciones`;
  }
  if (f.estado === "omitido") detalle = "no aplica";
  return `<div class="paso ${f.estado}"><div class="bola">${icono}</div>
    <div class="nombre">${esc(f.titulo)}</div><div class="detalle">${esc(detalle)}</div></div>`;
}

function esperas(r) {
  if (!r) return "";
  return `${r + 1} comprobaciones hasta quedar listo`;
}

function accion(a, i) {
  const est = { hecho: `${ico("check")} hecho`, en_curso: `${ico("gira", "gira")} en curso`, fallo: `${ico("x")} falló`,
    pendiente: `${ico("circulo")} pendiente` }[a.estado] || esc(a.estado);
  const espera = a.reintentos && a.estado !== "pendiente"
    ? (a.estado === "en_curso" ? `esperando · comprobación ${a.reintentos + 1}` : esperas(a.reintentos)) : null;
  return `<li class="accion ${a.estado}">
    <div class="n">${a.estado === "hecho" ? ico("check") : a.estado === "fallo" ? ico("x") : i + 1}</div>
    <div><div class="t">${esc(a.titulo)}</div><div class="tec solo-tecnico">${esc(a.tecnico)}</div>
      ${a.dato ? `<div class="dato solo-tecnico">${esc(a.dato)}</div>` : ""}
      ${espera ? `<div class="dato">${esc(espera)}</div>` : ""}</div>
    <div class="est">${est}</div></li>`;
}

function plegable(id, titulo, cuenta, contenido, abiertoPorDefecto) {
  const abierto = abiertos.has(id) || (abiertoPorDefecto && !abiertos.has("cerrado:" + id));
  return `<details class="plegable seccion-op" data-id="${id}" ${abierto ? "open" : ""}>
    <summary><h4><span class="flecha">›</span> ${esc(titulo)} <span class="cuenta">${esc(cuenta)}</span></h4></summary>
    ${contenido}</details>`;
}

function vistaOperacion(e, op) {
  const ini = op.inicio ? new Date(op.inicio) : null, fin = op.fin ? new Date(op.fin) : null;
  const dur = ini ? ((fin || new Date()) - ini) / 1000 : null;
  const dir = op.direccion ? op.direccion.replace("_a_", " → ").toUpperCase() : "";
  let h = `<div class="op-cab">
      <div class="logo-op">${ico("robot")}</div>
      <div style="min-width:0">
        <h3>${esc(op.nombre)}</h3>
        ${op.variante ? `<div class="variante">${esc(op.variante)}</div>` : ""}
        <div class="meta">
          <span>Pareja ${esc(op.pareja)}</span>${dir ? `<span>${esc(dir)}</span>` : ""}
          ${ini ? `<span>${horaCorta(op.inicio)}${fin ? `–${horaCorta(op.fin)}` : ""} · ${duracion(dur)}</span>` : ""}
          <span>flujo #${op.id}</span>
          ${op.url ? `<a href="${esc(op.url)}" target="_blank" rel="noopener">Ver en AAP ${ico("externo")}</a>` : ""}
        </div>
      </div>
      ${chipEstado(op)}
    </div>
    <div class="pasos">${op.fases.map((f, i) => paso(f, i, op)).join("")}</div>`;

  if (op.en_curso && op.fases[1].estado === "esperando") {
    h += `<div class="aviso-caja espera">${ico("arena")}<div><b>La automatización espera una firma</b>
      <p>Validó el estado real y propuso el plan. Nada se modifica hasta que una persona lo apruebe en AAP.
      ${op.url_aprobaciones ? `<a href="${esc(op.url_aprobaciones)}" target="_blank" rel="noopener">Abrir la bandeja de aprobaciones ${ico("externo")}</a>` : ""}</p></div></div>`;
  }
  if (op.garantia?.titulo) {
    h += `<div class="aviso-caja critico">${ico("alerta")}<div><b>${esc(op.garantia.titulo)}</b><p>${esc(op.garantia.motivo || "")}</p></div></div>`;
  }
  if (op.fallo) {
    h += `<div class="aviso-caja critico">${ico("x")}<div><b>Se detuvo en: ${esc(op.fallo.tarea)}</b><p>${esc(op.fallo.msg || "")}</p></div></div>`;
  }
  if (op.nada_que_hacer) {
    h += `<div class="aviso-caja ok">${ico("check")}<div><b>No había nada que hacer</b><p>${esc(op.motivo_sin_cambios || "El objetivo ya estaba cumplido.")}</p></div></div>`;
  }
  if (op.acciones?.length) {
    const hechas = op.acciones.filter((a) => a.estado === "hecho").length;
    const aprobado = op.fases[1].estado === "hecho";
    h += `<div class="seccion-op"><h4>${aprobado ? "Plan aprobado" : "Plan propuesto"} <span class="cuenta">${hechas} de ${op.acciones.length} acciones</span></h4>
      <ol class="acciones">${op.acciones.map(accion).join("")}</ol></div>`;
  }
  if (op.esperado?.length) {
    const ok = op.esperado.filter((x) => x.cumple).length;
    h += `<div class="seccion-op"><h4>${op.en_curso ? "Cómo debe quedar" : "Cómo quedó"} · en vivo <span class="cuenta">${ok} de ${op.esperado.length}</span></h4>
      <div class="esperado">${op.esperado.map((x) => `<div class="esp ${x.cumple ? "si" : "no"}">${ico(x.cumple ? "check" : "circulo")}<span>${esc(x.texto)}</span></div>`).join("")}</div></div>`;
  }
  if (op.prechecks?.length) {
    const ok = op.prechecks.filter((p) => p.ok).length;
    h += plegable("prechecks", "Controles previos", `${ok} de ${op.prechecks.length} en verde`,
      `<div class="controles">${op.prechecks.map((p) => `<div class="control ${p.ok ? "si" : "no"}">${ico(p.ok ? "check" : "x")}
        <div><span class="solo-funcional">${esc(p.funcional || p.nombre)}${p.ok ? "" : `<span class="m"> · ${esc(p.msg)}</span>`}</span>
        <span class="solo-tecnico"><b>${esc(p.nombre)}</b> <span class="m">· ${esc(p.msg)}</span></span></div></div>`).join("")}</div>`,
      op.en_curso && op.fases[0].estado !== "hecho");
  }
  if (op.verificacion?.length) {
    const okv = op.verificacion.filter((v) => v.ok).length;
    h += `<div class="seccion-op solo-funcional"><h4>Verificación final <span class="cuenta">${okv} de ${op.verificacion.length} comprobaciones en verde</span></h4></div>`;
    h += `<div class="solo-tecnico">` + plegable("verificacion", "Verificación final", `${op.verificacion.filter((v) => v.ok).length} de ${op.verificacion.length}`,
      `<div class="controles">${op.verificacion.map((v) => `<div class="control ${v.ok ? "si" : "no"}">${ico(v.ok ? "check" : "x")}<div class="m">${esc(v.msg)}</div></div>`).join("")}</div>`, false) + `</div>`;
  }
  return h;
}

function vistaReposo(e) {
  const op = e.operacion;
  const ultima = op && !op.visible
    ? `<p>Última: «${esc(op.nombre)}» ${op.estado === "successful" ? "terminó bien" : esc(op.estado)} ${op.fin ? haceCuanto(op.fin) : ""}.</p>` : "";
  const fila = (e.casos?.filas || []).find((f) => f.actual);
  const ops = (fila?.celdas || []).flatMap((c) => c.operaciones);
  return `<div class="reposo">
      <div class="titular"><div class="logo-op">${ico("escudo")}</div>
        <div><h3>Sin operación en curso</h3>${ultima || "<p>La automatización está lista. Cada operación valida el estado real antes de proponer nada.</p>"}</div></div>
      <div class="seccion-op" style="margin-top:2px"><h4>Lo que se puede lanzar desde AAP · pareja ${esc((e.pareja.clave || "").toUpperCase())}</h4>
        <div class="lanzables">${ops.map((o) => `<div class="lanzable"><b>${esc(o.nombre)}</b>
            <span class="p">${esc(o.proposito)}</span>
            ${o.variantes?.length ? `<span class="v">${o.variantes.map(esc).join(" · ")}</span>` : ""}
            ${o.url ? `<a href="${esc(o.url)}" target="_blank" rel="noopener">${esc(o.flujo)} ${ico("externo")}</a>` : ""}</div>`).join("")}
        </div></div>
    </div>`;
}

export function actualizar(e) {
  const op = e.operacion;
  const visible = op && op.visible;
  el.querySelector("#op-sub").textContent = visible
    ? (op.en_curso ? "en curso, leída de AAP en vivo" : `terminada ${op.fin ? haceCuanto(op.fin) : ""}`) : "";
  pintar(cuerpo, visible ? vistaOperacion(e, op) : vistaReposo(e));
}
