// Gráficas en SVG propio (sin librerías). Funciones puras: reciben datos y devuelven el texto SVG.
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = n => Math.round(n).toLocaleString('es-CO').replace(/,/g, '.');

/** Barras horizontales. filas: [{etiqueta, valor, clase?, texto?}]. log=true usa escala logarítmica. */
export function barrasH(filas, { ancho = 640, alto_fila = 30, izq = 210, log = false, titulo = '' } = {}) {
  const max = Math.max(...filas.map(f => f.valor));
  const esc_ = v => log ? Math.log10(Math.max(1, v)) / Math.log10(Math.max(10, max)) : v / max;
  const util = ancho - izq - 90;
  const alto = filas.length * alto_fila + 10;
  const barras = filas.map((f, i) => {
    const y = i * alto_fila + 5; const w = Math.max(2, esc_(f.valor) * util);
    return `<text x="${izq - 8}" y="${y + alto_fila / 2 + 4}" text-anchor="end">${esc(f.etiqueta)}</text>
      <rect class="barra ${f.clase || ''}" x="${izq}" y="${y + 4}" width="${w.toFixed(1)}" height="${alto_fila - 10}"/>
      <text class="num" x="${izq + w + 6}" y="${y + alto_fila / 2 + 4}">${esc(f.texto ?? fmt(f.valor))}</text>`;
  }).join('');
  return `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="${esc(titulo)}"><line class="eje" x1="${izq}" y1="0" x2="${izq}" y2="${alto}"/>${barras}</svg>`;
}

/** Puntos por sorteo con líneas de referencia horizontales. refs: [{valor, etiqueta, clase}] */
export function dispersion(valores, refs, { ancho = 640, alto = 230, titulo = '' } = {}) {
  const max = Math.max(...valores, ...refs.map(r => r.valor)) * 1.1;
  const izq = 40, abajo = 24, util = ancho - izq - 10, h = alto - abajo - 10;
  const y = v => 10 + h - (v / max) * h;
  const pts = valores.map((v, i) => `<circle class="punto-dato" cx="${(izq + (i + 0.5) * util / valores.length).toFixed(1)}" cy="${y(v).toFixed(1)}" r="3.2"/>`).join('');
  const lineas = refs.map(r => `<line class="linea-ref ${r.clase || ''}" x1="${izq}" x2="${ancho - 10}" y1="${y(r.valor)}" y2="${y(r.valor)}"/>
    <text x="${ancho - 12}" y="${y(r.valor) - 6}" text-anchor="end" class="num">${esc(r.etiqueta)}</text>`).join('');
  const reja = [0, 0.25, 0.5, 0.75, 1].map(f => `<line class="reja" x1="${izq}" x2="${ancho - 10}" y1="${y(max * f)}" y2="${y(max * f)}"/><text x="${izq - 6}" y="${y(max * f) + 4}" text-anchor="end" class="num">${(max * f).toFixed(0)}</text>`).join('');
  return `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="${esc(titulo)}">${reja}<line class="eje" x1="${izq}" y1="${10 + h}" x2="${ancho - 10}" y2="${10 + h}"/>
    ${pts}${lineas}<text x="${izq}" y="${alto - 4}">sorteos del último año →</text></svg>`;
}

/** Rango (mín–máx) y mediana por categoría. filas: [{etiqueta, min, max, mediana}] en pesos. Escala log. */
export function rangos(filas, { ancho = 640, alto_fila = 30, izq = 80, titulo = '' } = {}) {
  const max = Math.max(...filas.map(f => f.max)); const min = Math.max(1000, Math.min(...filas.map(f => f.min || max)));
  const lmin = Math.log10(min), lmax = Math.log10(max), util = ancho - izq - 110;
  const x = v => izq + ((Math.log10(Math.max(min, v)) - lmin) / (lmax - lmin || 1)) * util;
  const alto = filas.length * alto_fila + 24;
  const cuerpo = filas.map((f, i) => {
    const yy = i * alto_fila + alto_fila / 2 + 4;
    return `<text x="${izq - 8}" y="${yy + 4}" text-anchor="end" class="num">${esc(f.etiqueta)}</text>
      <line class="rango" x1="${x(f.min)}" x2="${x(f.max)}" y1="${yy}" y2="${yy}"/>
      <circle class="mediana" cx="${x(f.mediana)}" cy="${yy}" r="6"/>
      <text class="num" x="${x(f.max) + 10}" y="${yy + 4}">$${fmt(f.mediana)}</text>`;
  }).join('');
  return `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="${esc(titulo)}">${cuerpo}
    <text x="${izq}" y="${alto - 4}">escala logarítmica · punto = mediana · línea = mínimo a máximo</text></svg>`;
}

export function mediana(a) {
  const s = [...a].sort((x, y) => x - y); const m = s.length >> 1;
  return s.length ? (s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2) : 0;
}

/** Probabilidad de acertar k de 5 en Baloto (5 de 43). */
export function probBaloto(k) {
  const C = (n, r) => { let x = 1; for (let i = 0; i < r; i++) x = x * (n - i) / (i + 1); return x; };
  return C(5, k) * C(38, 5 - k) / C(43, 5);
}
