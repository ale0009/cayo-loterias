import { test } from 'node:test';
import assert from 'node:assert/strict';
import { barrasH, dispersion, rangos, mediana, probBaloto } from '../js/graficas.js';

test('probabilidades de Baloto suman 1 y coinciden con la combinatoria', () => {
  const s = [0, 1, 2, 3, 4, 5].reduce((a, k) => a + probBaloto(k), 0);
  assert.ok(Math.abs(s - 1) < 1e-12);
  assert.ok(Math.abs(probBaloto(5) - 1 / 962598) < 1e-15);
  // razón teórica (0 o 1 + SB) / (2 + SB) = 10,325
  assert.ok(Math.abs((probBaloto(0) + probBaloto(1)) / probBaloto(2) - 10.325) < 1e-9);
});

test('mediana', () => {
  assert.equal(mediana([3, 1, 2]), 2);
  assert.equal(mediana([4, 1, 2, 3]), 2.5);
  assert.equal(mediana([]), 0);
});

test('las gráficas devuelven SVG con texto escapado', () => {
  const s = barrasH([{ etiqueta: 'a<b', valor: 10 }, { etiqueta: 'c', valor: 1000 }], { log: true, titulo: 't' });
  assert.match(s, /^<svg/); assert.match(s, /a&lt;b/);
  assert.match(dispersion([1, 2, 3], [{ valor: 2, etiqueta: 'ref' }]), /linea-ref/);
  assert.match(rangos([{ etiqueta: '3', min: 5000, max: 20000, mediana: 9000 }]), /mediana/);
});
