import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  leerCodigo, categoriaBaloto, revisarBaloto, revisarLoteria, categoriasLoteria,
  vence, pesos, validarBaloto, cifrasFinalesIguales, buscarSorteo,
} from '../js/motor.js';

const planes = JSON.parse(readFileSync(new URL('../datos/planes.json', import.meta.url)));
const MED = planes.loterias.medellin;
const BOY = planes.loterias.boyaca;

// Resultados oficiales copiados de las fuentes (casos del piloto de 20 boletos reales).
const B2648 = {
  baloto: { numeros: [1, 3, 6, 8, 35], sb: 1, premios: { '3': { ganadores: 4037, por_ganador: 7450 }, '0+SB': { ganadores: 15672, por_ganador: 6000 } } },
  revancha: { numeros: [12, 13, 17, 25, 34], sb: 4, premios: {} },
};
const B2671 = {
  baloto: { numeros: [16, 20, 34, 37, 39], sb: 13, premios: {} },
  revancha: { numeros: [7, 12, 19, 34, 35], sb: 9, premios: { '2+SB': { ganadores: 2362, por_ganador: 3700 } } },
};
const M4850 = { mayor: { numero: '2608', serie: '301' }, secos: [{ numero: '1956', serie: '459', valor: 1e9 }] };

test('lee el código de barras de un billete de Medellín', () => {
  assert.deepEqual(leerCodigo('9016 0004831 8057 160 02'), {
    codigoLoteria: '016', loteria: 'medellin', sorteo: 4831, numero: '8057', serie: '160', fraccion: 2,
  });
});

test('lee el código de Boyacá y rechaza códigos mal formados', () => {
  assert.equal(leerCodigo('90040004616167518502').loteria, 'boyaca');
  assert.equal(leerCodigo('90040004616167518502').numero, '1675');
  assert.equal(leerCodigo('1234'), null);
  assert.equal(leerCodigo('80040004616167518502'), null);
  assert.equal(leerCodigo('90990004616167518502').loteria, null, 'lotería desconocida');
});

test('categorías de Baloto', () => {
  assert.equal(categoriaBaloto(5, true), '5+SB');
  assert.equal(categoriaBaloto(3, false), '3');
  assert.equal(categoriaBaloto(2, false), null);
  assert.equal(categoriaBaloto(2, true), '2+SB');
  assert.equal(categoriaBaloto(1, true), '0+SB');
  assert.equal(categoriaBaloto(0, false), null);
});

test('piloto: Baloto 2648 paga 3 aciertos ($7.450)', () => {
  const [b, r] = revisarBaloto({ numeros: [1, 6, 8, 15, 41], sb: 2 }, B2648);
  assert.deepEqual(b.aciertos, [1, 6, 8]);
  assert.equal(b.categoria, '3');
  assert.equal(b.premio, 7450);
  assert.equal(r.categoria, null);
});

test('piloto: Revancha 2671 paga 2 + Superbalota ($3.700)', () => {
  const [b, r] = revisarBaloto({ numeros: [12, 14, 16, 34, 38], sb: 9 }, B2671);
  assert.equal(b.categoria, null, 'en Baloto solo 2 aciertos sin SB');
  assert.equal(r.categoria, '2+SB');
  assert.equal(r.premio, 3700);
});

test('piloto: Medellín 4850, 1048-367 gana última cifra sin serie ($10.500 por fracción de 2)', () => {
  const r = revisarLoteria({ numero: '1048', serie: '367', fracciones: 2 }, M4850, MED);
  assert.equal(r.categoria, 'ultima_sin_serie');
  assert.equal(r.netoBillete, 21000);
  assert.equal(r.netoFraccion, 10500);
});

test('piloto: Boyacá 4616, 1675-185 no gana', () => {
  const r = revisarLoteria({ numero: '1675', serie: '185' }, { mayor: { numero: '1990', serie: '044' }, secos: [] }, BOY);
  assert.equal(r.gano, false);
});

test('premio mayor y seco con serie', () => {
  assert.equal(revisarLoteria({ numero: '2608', serie: '301' }, M4850, MED).categoria, 'mayor');
  const s = revisarLoteria({ numero: '1956', serie: '459', fracciones: 3 }, M4850, MED);
  assert.equal(s.categoria, 'seco');
  assert.equal(s.netoBillete, 664000000);
});

test('las aproximaciones no se suman: gana la de mayor valor', () => {
  // 2618 con la serie del mayor: dos primeras con serie (3.984.000) y serie del mayor (21.000)
  const r = revisarLoteria({ numero: '2618', serie: '301' }, M4850, MED);
  assert.equal(r.categoria, 'dos_primeras_con_serie');
  assert.ok(r.otras.some(o => o.clave === 'serie_mayor'));
});

test('tres últimas cifras sin serie y seco en otra serie', () => {
  assert.equal(revisarLoteria({ numero: '9608', serie: '001' }, M4850, MED).categoria, 'tres_ultimas_sin_serie');
  assert.equal(categoriasLoteria({ numero: '1956', serie: '000' }, M4850, MED)[0].clave, 'seco_sin_serie');
});

test('utilidades', () => {
  assert.equal(vence('2026-08-28'), '2027-08-28');
  assert.equal(pesos(10500), '$10.500');
  assert.equal(cifrasFinalesIguales('1048', '2608'), 1);
  assert.equal(validarBaloto([1, 2, 3, 4, 5], 16), null);
  assert.match(validarBaloto([1, 1, 3, 4, 5], 2), /distintos/);
  assert.match(validarBaloto([1, 2, 3, 4, 44], 2), /43/);
  assert.match(validarBaloto([1, 2, 3, 4, 5], 17), /16/);
  const db = { sorteos: { '10': { fecha: '2026-01-01' } } };
  assert.equal(buscarSorteo(db, { fecha: '2026-01-01' }).id, '10');
  assert.equal(buscarSorteo(db, { sorteo: 11 }), null);
});
