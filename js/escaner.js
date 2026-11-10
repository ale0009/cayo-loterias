// Escáner de código de barras con la cámara. Usa el lector nativo del navegador si existe
// (BarcodeDetector) y, si no, ZXing (vendor/zxing.min.js, MIT). Solo acepta lecturas con la
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
  if (!window.ZXing) { alEstado('No se cargó el lector de códigos. Escribe los 20 números a mano.'); return; }
  const Z = window.ZXing;
  const hints = new Map([[Z.DecodeHintType.TRY_HARDER, true],
    [Z.DecodeHintType.POSSIBLE_FORMATS, [Z.BarcodeFormat.CODE_128, Z.BarcodeFormat.ITF, Z.BarcodeFormat.CODE_39, Z.BarcodeFormat.CODABAR]]]);
  const lector = new Z.BrowserMultiFormatReader(hints, 250);
  parar = () => lector.reset();
  alEstado('Buscando el código… acércalo hasta que llene el recuadro.');
  await lector.decodeFromVideoDevice(undefined, video, (res) => {
    if (!res) return;
    const v = valido(res.getText());
    if (v) { detenerEscaner(); alLeer(v); }
  });
}

export function detenerEscaner() {
  if (parar) { try { parar(); } catch { /* ya estaba detenido */ } parar = null; }
}
