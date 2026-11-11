// Fotos de boletos guardadas SOLO en este navegador (IndexedDB). Nada se sube a ningún servidor:
// un boleto es un documento al portador y su foto equivale a dinero.
// Cada foto se identifica por su huella SHA-256: la misma foto enviada dos veces se guarda una sola vez.

const BASE = 'cayo';
const ALMACEN = 'fotos';
let conexion = null;

function abrir() {
  if (conexion) return conexion;
  conexion = new Promise((ok, mal) => {
    const pet = indexedDB.open(BASE, 1);
    pet.onupgradeneeded = () => { pet.result.createObjectStore(ALMACEN, { keyPath: 'hash' }); };
    pet.onsuccess = () => ok(pet.result);
    pet.onerror = () => mal(pet.error);
  });
  return conexion;
}

async function tx(modo, fn) {
  const db = await abrir();
  return new Promise((ok, mal) => {
    const t = db.transaction(ALMACEN, modo);
    const r = fn(t.objectStore(ALMACEN));
    t.oncomplete = () => ok(r?.result);
    t.onerror = () => mal(t.error);
  });
}

export async function huella(blob) {
  const buf = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

/** Miniatura WebP (lado mayor 480 px) para pintar la billetera sin cargar la foto completa. */
export async function miniatura(blob, lado = 480) {
  const bmp = await createImageBitmap(blob);
  const k = Math.min(1, lado / Math.max(bmp.width, bmp.height));
  const c = document.createElement('canvas');
  c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
  c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
  const dims = { ancho: bmp.width, alto: bmp.height };
  bmp.close();
  const mini = await new Promise(ok => c.toBlob(ok, 'image/webp', 0.8));
  c.width = c.height = 0;
  return { mini, ...dims };
}

export const guardar = registro => tx('readwrite', s => s.put(registro));
export const leer = hash => tx('readonly', s => s.get(hash));
export const listar = () => tx('readonly', s => s.getAll());
export const borrar = hash => tx('readwrite', s => s.delete(hash));
export const vaciar = () => tx('readwrite', s => s.clear());
export const existe = async hash => Boolean(await leer(hash));

/** Pide al navegador no borrar estos datos y devuelve cuánto espacio se usa. */
export async function espacio() {
  try { await navigator.storage?.persist?.(); } catch { /* opcional */ }
  try { return await navigator.storage.estimate(); } catch { return null; }
}
