// Lo que esta pasando ahora, en corto, para el presentador: la situacion,
// quien atiende, el contenido, Temenos y la operacion de AAP.
import { esc, ico, icoNivel, n, colorSitio, post, pintar } from "./comunes.js";

let el;

export function montar(contenedor, ctx) {
  el = contenedor;
  el.innerHTML = `<header><h2>Ahora</h2><span class="sub">lo mismo que ve el público</span></header><div class="cuerpo" id="ah"></div>`;
  el.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-ah]");
    if (!b) return;
    const d = ctx.ultimo?.temenos_defecto || {};
    try {
      await post("api/temenos/continuo", b.dataset.ah === "detener" ? { detener: true } : { sitio: d.sitio, por_segundo: d.por_segundo });
    } catch (e) { alert(e.message); }
  });
}

export function actualizar(e) {
  const s = e.situacion || {}, c = e.contenido || {}, t = e.temenos?.continuo, op = e.operacion;
  const filas = e.pareja.sitios.map((x) => {
    const v = e.sitios[x], d = v.datos;
    return `<span class="sitio-rot"><i style="background:${colorSitio(e, x)}"></i>${esc(x.toUpperCase())}
      <small>${v.rol === "activo" ? "atiende" : v.rol === "en_espera" ? "en espera" : v.rol === "caido" ? "no responde" : v.rol}</small></span>
      <b class="num">${d ? n(d.retenidos) : "—"}</b>`;
  }).join("");
  let opHtml = `<span class="tenue">Sin operación en curso</span>`;
  if (op?.visible) {
    const chip = op.en_curso ? (op.fases[1].estado === "esperando" ? `<span class="chip espera">${ico("arena")} Esperando aprobación</span>` : `<span class="chip curso">${ico("gira", "gira")} En curso</span>`)
      : op.estado === "successful" ? `<span class="chip ok">${ico("check")} Terminó bien</span>` : `<span class="chip critico">${ico("x")} ${esc(op.estado)}</span>`;
    opHtml = `<div><b>${esc(op.nombre)}</b>${op.variante ? ` <span class="tenue">· ${esc(op.variante)}</span>` : ""}</div>
      <div class="ah-op">${chip}<span class="tenue">${esc(op.fase_texto || "")}</span>${op.url ? `<a href="${esc(op.url)}" target="_blank" rel="noopener">AAP ${ico("externo")}</a>` : ""}</div>`;
  }
  pintar(el.querySelector("#ah"), `
    <div class="ah-sit" data-nivel="${esc(s.nivel || "info")}">${ico(icoNivel(s.nivel))}<div><b>${esc(s.titulo || "")}</b><span>${esc(s.detalle || "")}</span></div></div>
    <div class="ah-grid">
      <label>Mensajes</label><div class="ah-sitios">${filas}</div>
      <label>Contenido</label><div>${c.transito ? ico("gira") : c.igual ? ico("igual") : ico("distinto")} ${esc(c.texto || "")}</div>
      <label>Temenos</label><div class="ah-tm">${t ? `<span class="chip ok">${t.por_segundo} tx/s por ${esc(t.sitio.toUpperCase())}${t.errores ? ` · ${t.errores} lotes con error` : ""}</span>
        <button class="btn chico" data-ah="detener">${ico("pausa")} Detener</button>`
        : `<span class="chip neutro">detenido</span><button class="btn chico" data-ah="encender">${ico("play")} Encender</button>`}</div>
      <label>AAP</label><div>${opHtml}</div>
    </div>`);
}
