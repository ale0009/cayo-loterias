// Carga los JSON de datos/ (los escribe el recolector cada noche). Sin red externa: todo vive en el repo.
// Las loterías disponibles salen de datos/planes.json: agregar una no exige tocar este archivo.
async function leer(base, nombre) {
  const r = await fetch(`${base}${nombre}.json`, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`No se pudo leer datos/${nombre}.json (HTTP ${r.status}).`);
  return r.json();
}

export async function cargarDatos(base = './datos/') {
  const [planes, estado, baloto] = await Promise.all(['planes', 'estado', 'baloto'].map(n => leer(base, n)));
  const D = { planes, estado, baloto };
  const ids = Object.keys(planes.loterias);
  const lotes = await Promise.all(ids.map(id => leer(base, id).catch(() => null)));
  ids.forEach((id, i) => {
    // Una lotería sin datos (fuente caída desde el inicio) no rompe la página: se oculta.
    if (lotes[i] && Object.keys(lotes[i].sorteos).length) D[id] = lotes[i];
    else delete planes.loterias[id];
  });
  return D;
}

/** Sorteos de un juego ordenados del más reciente al más antiguo: [{id, fecha, ...}]. */
export function listaSorteos(db) {
  return Object.entries(db.sorteos).map(([id, v]) => ({ id, ...v })).sort((a, b) => Number(b.id) - Number(a.id));
}
