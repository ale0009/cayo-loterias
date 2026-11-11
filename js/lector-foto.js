// Busca el código de 20 dígitos en una FOTO. Usa zxing-cpp compilado a WebAssembly (vendor/zxing-wasm),
// que lee mucho mejor que el port viejo de ZXing en JavaScript. En el piloto leyó los billetes sintéticos
// de cerca, de lejos y girados, y 5 de las 20 fotos reales de loterías; el port viejo no leyó ninguna.
// Si no se lee, la página ofrece el formulario al lado de la foto. Solo se acepta una lectura con la
// estructura válida (leerCodigo), así que las lecturas falsas se descartan.
import { leerCodigo } from './motor.js';
import { prepareZXingModule, readBarcodes } from '../vendor/zxing-wasm/es/reader/index.js';

// El .wasm se carga desde el propio sitio, no desde un CDN: la herramienta no depende de terceros.
prepareZXingModule({
  overrides: { locateFile: (ruta, prefijo) => ruta.endsWith('.wasm') ? new URL('../vendor/zxing-wasm/zxing_reader.wasm', import.meta.url).href : prefijo + ruta },
  fireImmediately: false,
});

const OPCIONES = { formats: ['Code128', 'ITF', 'Code39', 'Codabar'], tryHarder: true, tryRotate: true, tryInvert: false, tryDownscale: true, maxNumberOfSymbols: 6 };
const FORMATOS_NATIVOS = ['code_128', 'itf', 'code_39', 'codabar'];

function valido(texto, codigos) {
  const t = String(texto ?? '').replace(/\D/g, '');
  return leerCodigo(t, codigos) ? t : null;
}

async function conZxingCpp(blob, codigos) {
  for (const r of await readBarcodes(blob, OPCIONES)) {
    const t = valido(r.text, codigos);
    if (t) return { codigo: t, via: `zxing-cpp, ${r.format}` };
  }
  return null;
}

async function conNativo(blob, codigos) {
  if (!('BarcodeDetector' in globalThis)) return null;
  let bmp;
  try {
    const soportados = await BarcodeDetector.getSupportedFormats();
    const formatos = FORMATOS_NATIVOS.filter(f => soportados.includes(f));
    if (!formatos.length) return null;
    bmp = await createImageBitmap(blob);
    for (const c of await new BarcodeDetector({ formats: formatos }).detect(bmp)) {
      const t = valido(c.rawValue, codigos);
      if (t) return { codigo: t, via: 'lector del navegador' };
    }
  } catch { /* sin lector nativo utilizable */ } finally { bmp?.close?.(); }
  return null;
}

/** Devuelve {codigo, via} o null. Procesa una foto a la vez. */
export async function leerCodigoEnFoto(blob, codigos) {
  try {
    return (await conZxingCpp(blob, codigos)) ?? (await conNativo(blob, codigos));
  } catch {
    return conNativo(blob, codigos);
  }
}
