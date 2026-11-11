// Escáner de código de barras con la cámara. Usa el lector nativo del navegador si existe
// (BarcodeDetector) y, si no, zxing-cpp en WebAssembly (vendor/zxing-wasm). Solo acepta lecturas con la
// forma del código de 20 dígitos: así se descartan las lecturas falsas.
import { leerCodigo } from './motor.js';

const FORMATOS = ['code_128', 'itf', 'code_39', 'codabar', 'ean_13'];
let parar = null;

export async function iniciarEscaner(video, alLeer, alEstado) {
  detenerEscaner();
  if (!navigator.mediaDevices?.getUserMedia) {
    alEstado('Este navegador no permite usar la cámara. Escribe los 20 números a mano.');
    return;
  }
  const valido = txt => leerCodigo(txt) ? txt.replace(/\D/g, '') : null;

  if ('BarcodeDetector' in window) {
    const soportados = await window.BarcodeDetector.getSupportedFormats().catch(() => []);
    const formatos = FORMATOS.filter(f => soportados.includes(f));
    if (formatos.length) {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      video.srcObject = stream; await video.play();
      const det = new window.BarcodeDetector({ formats: formatos });
      let vivo = true;
      parar = () => { vivo = false; stream.getTracks().forEach(t => t.stop()); video.srcObject = null; };
      const ciclo = async () => {
        if (!vivo) return;
        try {
          for (const c of await det.detect(video)) {
            const v = valido(c.rawValue);
            if (v) { detenerEscaner(); alLeer(v); return; }
          }
        } catch { /* cuadro sin datos: seguimos */ }
        setTimeout(ciclo, 180);
      };
      alEstado('Buscando el código… acércalo hasta que llene el recuadro.');
      ciclo();
      return;
    }
  }
  // Sin lector nativo: zxing-cpp (WebAssembly, incluido en vendor/) sobre cuadros del video.
  const { prepareZXingModule, readBarcodes } = await import('../vendor/zxing-wasm/es/reader/index.js');
  prepareZXingModule({ overrides: { locateFile: (r, pre) => r.endsWith('.wasm') ? new URL('../vendor/zxing-wasm/zxing_reader.wasm', import.meta.url).href : pre + r }, fireImmediately: false });
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1920 } } });
  video.srcObject = stream; await video.play();
  const lienzo = document.createElement('canvas'); const g = lienzo.getContext('2d', { willReadFrequently: true });
  let vivo = true;
  parar = () => { vivo = false; stream.getTracks().forEach(t => t.stop()); video.srcObject = null; lienzo.width = 0; };
  alEstado('Buscando el código… acércalo hasta que llene el recuadro.');
  const ciclo = async () => {
    if (!vivo || !video.videoWidth) { if (vivo) setTimeout(ciclo, 200); return; }
    lienzo.width = video.videoWidth; lienzo.height = video.videoHeight;
    g.drawImage(video, 0, 0);
    try {
      for (const r of await readBarcodes(g.getImageData(0, 0, lienzo.width, lienzo.height), { formats: ['Code128', 'ITF', 'Code39', 'Codabar'], tryHarder: true, maxNumberOfSymbols: 4 })) {
        const v = valido(r.text);
        if (v) { detenerEscaner(); alLeer(v); return; }
      }
    } catch { /* cuadro sin código */ }
    if (vivo) setTimeout(ciclo, 250);
  };
  ciclo();
}

export function detenerEscaner() {
  if (parar) { try { parar(); } catch { /* ya estaba detenido */ } parar = null; }
}
