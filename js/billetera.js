// Billetera v2: modelo de datos, migración e importación. Sin DOM: se prueba con node --test.
// Se guarda en localStorage («cayo-billetera-v2»). La v1 («cayo-billetera») queda intacta como respaldo.

export const CLAVE_V1 = 'cayo-billetera';
export const CLAVE_V2 = 'cayo-billetera-v2';

const hoy = () => new Date().toISOString().slice(0, 10);
const nuevoId = () => globalThis.crypto?.randomUUID?.() ?? `b${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

/** «Medellín», «medellin», «Lotería de Medellín» → «medellin». */
export function idLoteria(nombre) {
  return String(nombre ?? '').toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')
    .replace(/^loteria\s+(de\s+|del\s+)?/, '').replace(/\s+/g, '');
}

/** Identidad de un boleto: dos boletos con la misma firma son el mismo papel. */
export function firma(b) {
  if (b.tipo === 'baloto') return `b|${b.sorteo}|${[...b.numeros].map(Number).sort((x, y) => x - y).join('-')}|${b.sb}`;
  if (b.tipo === 'chance') return `c|${b.loteria}|${b.fecha}|${b.cifras}|${b.modalidad}|${b.valor}`;
  return `l|${b.loteria}|${b.sorteo}|${b.numero}|${b.serie}|${b.fraccion ?? ''}`;
}

/** Identidad del billete completo (todas sus fracciones comparten esta clave). */
export function claveBillete(b) {
  return b.tipo === 'loteria' ? `l|${b.loteria}|${b.sorteo}|${b.numero}|${b.serie}` : firma(b);
}

export function completar(b, origen = 'manual') {
  return { ...b, id: b.id || nuevoId(), origen: b.origen || origen, agregado: b.agregado || hoy() };
}

export function migrar(v1) {
  return { version: 2, boletos: (Array.isArray(v1) ? v1 : []).map(b => completar(b, 'importado')) };
}

/**
 * Acepta: la billetera v1 (array), la v2 ({version:2, boletos}) o el formato del piloto
 * ({baloto:[...], loterias:[...]}, con «superbalota» y fracciones «3 de 3» o numéricas).
 * Devuelve un array de boletos sin id (se completan al fusionar).
 */
export function normalizarImportado(j) {
  if (Array.isArray(j)) return j.map(b => ({ ...b, loteria: b.loteria ? idLoteria(b.loteria) : b.loteria }));
  if (j && j.version === 2 && Array.isArray(j.boletos)) return normalizarImportado(j.boletos);
  if (!j || typeof j !== 'object') return [];
  const fr = l => {
    if (typeof l.fraccion === 'string' && /de/.test(l.fraccion)) {
      const [a, t] = l.fraccion.split(/\s*de\s*/).map(x => parseInt(x, 10));
      return { fraccion: Number.isFinite(a) ? a : undefined, fracciones: Number.isFinite(t) ? t : undefined };
    }
    return { fraccion: parseInt(l.fraccion, 10) || undefined, fracciones: parseInt(l.fracciones, 10) || undefined };
  };
  return [
    ...(j.baloto ?? []).map(b => ({ tipo: 'baloto', sorteo: b.sorteo, numeros: b.numeros, sb: b.superbalota ?? b.sb })),
    ...(j.loterias ?? []).map(l => ({ tipo: 'loteria', loteria: idLoteria(l.loteria), sorteo: l.sorteo, numero: String(l.numero).padStart(4, '0'),
      serie: String(l.serie).padStart(3, '0'), ...fr(l), ...(l.precio ? { precio: Number(l.precio) } : {}) })),
  ];
}

/** Agrega los nuevos sin repetir (por firma). Devuelve la lista nueva y cuántos entraron. */
export function fusionar(lista, nuevos, origen = 'importado') {
  const vistas = new Set(lista.map(firma));
  const out = [...lista];
  let agregados = 0, repetidos = 0;
  for (const b of nuevos) {
    const f = firma(b);
    if (vistas.has(f)) { repetidos++; continue; }
    vistas.add(f); out.push(completar(b, origen)); agregados++;
  }
  return { lista: out, agregados, repetidos };
}

/** Agrupa las fracciones del mismo billete. Baloto y chance quedan en grupos de uno. */
export function agrupar(boletos) {
  const grupos = new Map();
  for (const b of boletos) {
    const k = claveBillete(b);
    if (!grupos.has(k)) grupos.set(k, { clave: k, tipo: b.tipo, boletos: [] });
    grupos.get(k).boletos.push(b);
  }
  for (const g of grupos.values()) g.boletos.sort((a, b) => (a.fraccion ?? 0) - (b.fraccion ?? 0));
  return [...grupos.values()];
}

/** Lee la billetera v2; si solo existe la v1, la migra (sin borrarla). */
export function leer(almacen = globalThis.localStorage) {
  try {
    const v2 = JSON.parse(almacen.getItem(CLAVE_V2));
    if (v2?.version === 2) return v2;
    const v1 = JSON.parse(almacen.getItem(CLAVE_V1));
    const m = migrar(v1 || []);
    if (m.boletos.length) escribir(m, almacen);
    return m;
  } catch { return { version: 2, boletos: [] }; }
}

export function escribir(datos, almacen = globalThis.localStorage) {
  try { almacen.setItem(CLAVE_V2, JSON.stringify(datos)); return true; } catch { return false; }
}
