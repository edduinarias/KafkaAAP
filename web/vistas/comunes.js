// Utilidades compartidas por las vistas: escape, formatos, iconos y colores.

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const NUM = new Intl.NumberFormat("es-DO");
const DEC = new Intl.NumberFormat("es-DO", { maximumFractionDigits: 1 });
const DOP = new Intl.NumberFormat("es-DO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const n = (x) => (x === null || x === undefined ? "—" : NUM.format(x));
export const dec = (x) => (x === null || x === undefined ? "—" : DEC.format(x));
export const dinero = (x) => (x === null || x === undefined ? "—" : DOP.format(x));

export const hora = (t) => {
  const d = typeof t === "number" ? new Date(t * 1000) : new Date(t);
  return isNaN(d) ? "" : d.toLocaleTimeString("es-DO", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
};
export const horaCorta = (t) => {
  const d = typeof t === "number" ? new Date(t * 1000) : new Date(t);
  return isNaN(d) ? "" : d.toLocaleTimeString("es-DO", { hour: "2-digit", minute: "2-digit", hour12: false });
};

export function duracion(seg) {
  if (seg === null || seg === undefined || isNaN(seg)) return "";
  seg = Math.max(0, Math.round(seg));
  if (seg < 60) return `${seg} s`;
  const m = Math.floor(seg / 60), s = seg % 60;
  if (m < 60) return s ? `${m} min ${s} s` : `${m} min`;
  const h = Math.floor(m / 60), mm = m % 60;
  if (h < 48) return mm ? `${h} h ${mm} min` : `${h} h`;
  return `${Math.floor(h / 24)} días`;
}
export const haceCuanto = (iso) => {
  const t = new Date(iso).getTime();
  return isNaN(t) ? "" : "hace " + duracion((Date.now() - t) / 1000);
};
export const faltaPara = (iso) => (new Date(iso).getTime() - Date.now()) / 1000;

// Color de identidad de cada sitio, por su posicion en la pareja.
export function colorSitio(estado, s) {
  const i = (estado?.pareja?.sitios || []).indexOf(s);
  return i === 1 ? "var(--s2)" : "var(--s1)";
}
export function tenueSitio(estado, s) {
  const i = (estado?.pareja?.sitios || []).indexOf(s);
  return i === 1 ? "var(--s2-tenue)" : "var(--s1-tenue)";
}

// Iconos de trazo, en linea para no depender de nada externo.
const P = {
  check: '<path d="M5 12.5l4.2 4.2L19 7"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  alerta: '<path d="M12 3.5l9.5 16.5h-19z"/><path d="M12 10v4.5M12 17.6v.2"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.2"/>',
  reloj: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
  arena: '<path d="M7 3h10M7 21h10M8 3c0 5 8 5 8 9s-8 4-8 9M16 3c0 5-8 5-8 9s8 4 8 9"/>',
  gira: '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',
  flecha: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  externo: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  escudo: '<path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
  engranaje: '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v2.6M12 18.6v2.6M21.2 12h-2.6M5.4 12H2.8M18.5 5.5l-1.8 1.8M7.3 16.7l-1.8 1.8M18.5 18.5l-1.8-1.8M7.3 7.3L5.5 5.5"/>',
  robot: '<rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 4v4M9 13h.01M15 13h.01M9.5 16.5h5"/>',
  punto: '<circle cx="12" cy="12" r="3.5" fill="currentColor" stroke="none"/>',
  circulo: '<circle cx="12" cy="12" r="8"/>',
  cambio: '<path d="M4 8h13l-3-3M20 16H7l3 3"/>',
  datos: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  sol: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  luna: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
  llave: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3M15 8l2 2"/>',
  enviar: '<path d="M4 12l16-8-6 16-3-7z"/><path d="M11 13l9-9"/>',
  pausa: '<path d="M9 5v14M15 5v14"/>',
  play: '<path d="M7 5l12 7-12 7z"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  pin: '<path d="M9 4h6l-1 6 3 3H7l3-3zM12 13v7"/>',
  guion: '<path d="M8 6h12M8 12h12M8 18h12"/><circle cx="4" cy="6" r="1" fill="currentColor"/><circle cx="4" cy="12" r="1" fill="currentColor"/><circle cx="4" cy="18" r="1" fill="currentColor"/>',
  capas: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
  rayo: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  igual: '<path d="M5 9h14M5 15h14"/>',
  distinto: '<path d="M5 9h14M5 15h14M16 4L8 20"/>',
};
export const ico = (nombre, clase = "") =>
  `<svg class="ico ${clase}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[nombre] || ""}</svg>`;

// Icono por nivel de evento o de estado.
export const icoNivel = (nivel) => ({
  ok: "check", critico: "x", aviso: "alerta", espera: "arena", en_curso: "gira", operacion: "robot",
  cambio: "cambio", dato: "datos", info: "info",
}[nivel] || "info");

export async function post(url, cuerpo) {
  // X-Demo: el servidor solo acepta acciones de su propia pagina.
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-Demo": "1" }, body: JSON.stringify(cuerpo || {}) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
  return d;
}

// Repinta un contenedor solo si su contenido cambio: evita parpadeos y que se
// pierdan el foco, la seleccion o un <details> abierto.
export function pintar(el, html) {
  if (el._html !== html) {
    el.innerHTML = html;
    el._html = html;
    return true;
  }
  return false;
}
