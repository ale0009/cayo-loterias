// Motor de premios: funciones puras, sin red ni DOM. Se prueban con `node --test`.

/** Códigos de lotería del código de barras comprobados en billetes reales (los demás vienen de planes.json). */
export const CODIGOS = { '016': 'medellin', '004': 'boyaca' };

/**
 * Lee el número de 20 dígitos impreso bajo el código de barras de un billete.
 * Estructura: 9 · lotería(3) · sorteo(7) · número(4) · serie(3) · fracción(2).
 * Acepta espacios o guiones. Devuelve null si no tiene esa forma.
 */
export function leerCodigo(texto, codigos = CODIGOS) {
  const c = String(texto ?? '').replace(/\D/g, '');
  if (c.length !== 20 || c[0] !== '9') return null;
  const codigo = c.slice(1, 4);
  return {
    codigoLoteria: codigo,
    loteria: codigos[codigo] ?? null,
    sorteo: Number(c.slice(4, 11)),
    numero: c.slice(11, 15),
    serie: c.slice(15, 18),
    fraccion: Number(c.slice(18, 20)),
  };
}

/** Categoría de Baloto para k aciertos con o sin Superbalota; null si no paga. */
export function categoriaBaloto(k, sb) {
  if (sb) return k >= 2 ? `${k}+SB` : '0+SB'; // la fila oficial «0 + SB» cubre 0 y 1 acierto (supuesto, ver /proceso/)
  return k >= 3 ? String(k) : null;
}

/** Revisa una jugada {numeros:[5], sb} contra un sorteo del archivo datos/baloto.json. */
export function revisarBaloto(jugada, sorteo) {
  const nums = jugada.numeros.map(Number);
  return ['baloto', 'revancha'].filter(j => sorteo?.[j]).map(j => {
    const of = sorteo[j];
    const aciertos = nums.filter(n => of.numeros.includes(n));
    const acertoSB = Number(jugada.sb) === of.sb;
    const categoria = categoriaBaloto(aciertos.length, acertoSB);
    const fila = categoria ? of.premios?.[categoria] : null;
    let premio = fila ? fila.por_ganador : 0;
    // Si nadie más acertó la categoría, la tabla dice $0: el premio es el acumulado y hay que reclamarlo.
    const acumulado = Boolean(categoria && fila && fila.ganadores === 0);
    return { juego: j, oficial: of.numeros, sbOficial: of.sb, aciertos, acertoSB, categoria, premio, acumulado };
  });
}

const PRIMERAS = (a, b, n) => a.slice(0, n) === b.slice(0, n);
const ULTIMAS = (a, b, n) => a.slice(-n) === b.slice(-n);

/**
 * Todas las categorías que cumple un billete {numero, serie} frente a un sorteo {mayor, secos}.
 * Devuelve [{clave, netoBillete, detalle}] ordenado de mayor a menor valor.
 */
export function categoriasLoteria(boleto, sorteo, plan) {
  const num = String(boleto.numero).padStart(4, '0');
  const serie = String(boleto.serie).padStart(3, '0');
  const { numero: m, serie: ms } = sorteo.mayor;
  const neto = plan.neto_billete;
  const out = [];
  const add = (clave, valor, detalle = '') => { if (valor) out.push({ clave, netoBillete: valor, detalle }); };

  if (num === m && serie === ms) add('mayor', neto.mayor);
  for (const s of sorteo.secos ?? []) {
    if (num !== s.numero) continue;
    if (serie === s.serie) {
      // Si la fuente no publica el valor del seco, igual se avisa: el premio existe aunque no sepamos cuánto es.
      if (s.valor) add('seco', Math.round(s.valor * plan.factor_neto_secos), `${s.numero}-${s.serie}`);
      else out.push({ clave: 'seco', netoBillete: Number.MAX_SAFE_INTEGER, desconocido: true, detalle: `${s.numero}-${s.serie}` });
    }
    else add('seco_sin_serie', neto.seco_sin_serie, `${s.numero}-${s.serie}`);
  }
  const con = serie === ms;
  const suf = con ? '_con_serie' : '_sin_serie';
  if (num === m && !con) add('mayor_sin_serie', neto.mayor_sin_serie);
  if (num !== m) {
    if (PRIMERAS(num, m, 3)) add('tres_primeras' + suf, neto['tres_primeras' + suf]);
    if (ULTIMAS(num, m, 3)) add('tres_ultimas' + suf, neto['tres_ultimas' + suf]);
    if (PRIMERAS(num, m, 2)) add('dos_primeras' + suf, neto['dos_primeras' + suf]);
    if (ULTIMAS(num, m, 2)) add('dos_ultimas' + suf, neto['dos_ultimas' + suf]);
    if (ULTIMAS(num, m, 1)) add(con ? 'ultima_con_serie' : 'ultima_sin_serie', neto[con ? 'ultima_con_serie' : 'ultima_sin_serie']);
    if (con) add('serie_mayor', neto.serie_mayor);
  }
  // Categorías propias de algunas loterías (Valle, Huila…): solo cuentan si el plan las define.
  const extra = plan.neto_billete_extra ?? {};
  const x = (clave, cumple) => { if (cumple && extra[clave]) add(clave, extra[clave]); };
  const vecino = d => String((Number(m) + d + 10000) % 10000).padStart(4, '0');
  const invertido = [...m].reverse().join('');
  const mismasCifras = [...num].sort().join('') === [...m].sort().join('');
  if (num !== m) {
    for (const s of ['_con_serie', '_sin_serie']) {
      if ((s === '_con_serie') !== con) continue;
      x('anterior_al_mayor' + s, num === vecino(-1));
      x('posterior_al_mayor' + s, num === vecino(1));
      x('mayor_invertido' + s, invertido !== m && num === invertido);
      x('combinado' + s, mismasCifras);
      x('primera_y_ultima' + s, num[0] === m[0] && num[3] === m[3]);
      x('primera_y_dos_ultimas' + s, num[0] === m[0] && num.slice(2) === m.slice(2));
      x('dos_primeras_y_ultima' + s, num.slice(0, 2) === m.slice(0, 2) && num[3] === m[3]);
      x('dos_del_centro' + s, num.slice(1, 3) === m.slice(1, 3));
    }
  }
  // «Gana fijo» (Huila): un número que paga en cualquier serie.
  if (sorteo.ganafijo?.numero === num) x('ganafijo_sin_serie', true);
  // Premios especiales que publica la fuente (p. ej. «El Travieso del Tolima»): pagan en cualquier serie.
  for (const e of sorteo.especiales ?? []) {
    if (e.numero !== num || !(e.sin_serie || e.serie === serie)) continue;
    if (extra.especial_sin_serie) add('especial_sin_serie', extra.especial_sin_serie, e.nombre ?? '');
    else out.push({ clave: 'especial_sin_serie', netoBillete: Number.MAX_SAFE_INTEGER, desconocido: true, detalle: e.nombre ?? '' });
  }
  return out.sort((a, b) => b.netoBillete - a.netoBillete);
}

/** Resultado final de un billete: la categoría de mayor valor (las aproximaciones no se suman). */
export function revisarLoteria(boleto, sorteo, plan) {
  const todas = categoriasLoteria(boleto, sorteo, plan);
  const fracciones = Number(boleto.fracciones) || plan.fracciones;
  const mejor = todas[0] ?? null;
  const desconocido = Boolean(mejor?.desconocido);
  return {
    gano: Boolean(mejor),
    categoria: mejor?.clave ?? null,
    desconocido,
    netoBillete: desconocido ? 0 : mejor?.netoBillete ?? 0,
    netoFraccion: mejor && !desconocido ? Math.round(mejor.netoBillete / fracciones) : 0,
    fracciones,
    otras: todas.slice(1),
    mayor: sorteo.mayor,
  };
}

/** Cuántas cifras finales coinciden con el mayor (para resaltarlas en pantalla). */
export function cifrasFinalesIguales(a, b) {
  let k = 0;
  while (k < 4 && a[3 - k] === b[3 - k]) k++;
  return k;
}

/** Fecha límite para cobrar: 1 año después del sorteo (Ley 1393 de 2010, art. 12). */
export function vence(fechaISO) {
  const [y, m, d] = fechaISO.split('-').map(Number);
  return `${y + 1}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

export function diasHasta(fechaISO, hoy = new Date()) {
  const f = new Date(fechaISO + 'T23:59:59');
  return Math.ceil((f - hoy) / 86400000);
}

export function pesos(v) {
  return '$' + Math.round(v).toLocaleString('es-CO').replace(/,/g, '.');
}

/** Busca un sorteo por número o, si no hay número, por fecha. */
export function buscarSorteo(db, { sorteo, fecha }) {
  if (sorteo && db.sorteos[String(sorteo)]) return { id: String(sorteo), ...db.sorteos[String(sorteo)] };
  if (fecha) {
    const hit = Object.entries(db.sorteos).find(([, v]) => v.fecha === fecha);
    if (hit) return { id: hit[0], ...hit[1] };
  }
  return null;
}

/** Valida una jugada de Baloto: 5 números distintos del 1 al 43 y Superbalota del 1 al 16. */
export function validarBaloto(numeros, sb) {
  const n = numeros.map(Number);
  if (n.length !== 5 || n.some(x => !Number.isInteger(x) || x < 1 || x > 43)) return 'Elige 5 números del 1 al 43.';
  if (new Set(n).size !== 5) return 'Los 5 números deben ser distintos.';
  const s = Number(sb);
  if (!Number.isInteger(s) || s < 1 || s > 16) return 'La Superbalota va del 1 al 16.';
  return null;
}

/** Mapa código de barras → id de lotería a partir de planes.json. */
export function codigosDesdePlanes(planes) {
  const m = { ...CODIGOS };
  for (const [id, p] of Object.entries(planes.loterias)) if (p.codigo_barras) m[p.codigo_barras] = id;
  return m;
}
