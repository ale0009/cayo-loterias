// Carga los JSON de datos/ (los escribe el recolector cada noche). Sin red externa: todo vive en el repo.
const ARCHIVOS = ['baloto', 'medellin', 'boyaca', 'planes', 'estado'];

export async function cargarDatos(base = './datos/') {
  const pares = await Promise.all(ARCHIVOS.map(async n => {
    const r = await fetch(`${base}${n}.json`, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`No se pudo leer datos/${n}.json (HTTP ${r.status}).`);
    return [n, await r.json()];
  }));
  return Object.fromEntries(pares);
}

/** Sorteos de un juego ordenados del más reciente al más antiguo: [{id, fecha, ...}]. */
export function listaSorteos(db) {
  return Object.entries(db.sorteos).map(([id, v]) => ({ id, ...v })).sort((a, b) => Number(b.id) - Number(a.id));
}
