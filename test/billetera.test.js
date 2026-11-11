import { test } from 'node:test';
import assert from 'node:assert/strict';
import { idLoteria, firma, claveBillete, migrar, normalizarImportado, fusionar, agrupar, leer, escribir, CLAVE_V1, CLAVE_V2 } from '../js/billetera.js';

const almacen = (inicial = {}) => { const m = new Map(Object.entries(inicial)); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), m }; };
const v1 = [
  { tipo: 'baloto', sorteo: 2648, numeros: [1, 6, 8, 15, 41], sb: 2 },
  { tipo: 'loteria', loteria: 'medellin', sorteo: 4821, numero: '7985', serie: '473', fraccion: 3, fracciones: 3 },
];

test('idLoteria normaliza nombres con tildes y prefijos', () => {
  assert.equal(idLoteria('Medellín'), 'medellin');
  assert.equal(idLoteria('Lotería de Boyacá'), 'boyaca');
  assert.equal(idLoteria('Lotería del Meta'), 'meta');
});

test('migrar de v1 a v2 asigna id y origen, y leer() no borra la v1', () => {
  const a = almacen({ [CLAVE_V1]: JSON.stringify(v1) });
  const d = leer(a);
  assert.equal(d.version, 2);
  assert.equal(d.boletos.length, 2);
  assert.ok(d.boletos.every(b => b.id && b.origen === 'importado'));
  assert.ok(a.m.has(CLAVE_V1), 'la v1 queda como respaldo');
  assert.ok(a.m.has(CLAVE_V2));
  // idempotente: leer de nuevo no duplica
  assert.equal(leer(a).boletos.length, 2);
  assert.equal(migrar(null).boletos.length, 0);
});

test('importar el formato del piloto (fracción «3 de 3», superbalota) y la v2', () => {
  const piloto = { baloto: [{ sorteo: 2671, numeros: [12, 14, 16, 34, 38], superbalota: 9 }],
    loterias: [{ loteria: 'Medellín', sorteo: 4850, numero: '1048', serie: '367', fraccion: '2 de 2' },
      { loteria: 'bogota', sorteo: 2852, numero: '2859', serie: '124', fraccion: 3, fracciones: 3 }] };
  const n = normalizarImportado(piloto);
  assert.equal(n.length, 3);
  assert.deepEqual([n[1].loteria, n[1].fraccion, n[1].fracciones], ['medellin', 2, 2]);
  assert.equal(n[0].sb, 9);
  assert.equal(n[2].loteria, 'bogota', 'Bogotá ya no se descarta');
  assert.equal(normalizarImportado({ version: 2, boletos: v1 }).length, 2);
});

test('fusionar no repite boletos (misma firma)', () => {
  const r1 = fusionar([], v1);
  const r2 = fusionar(r1.lista, [...v1, { ...v1[1], fraccion: 2 }]);
  assert.equal(r2.agregados, 1);
  assert.equal(r2.repetidos, 2);
  assert.equal(firma({ tipo: 'baloto', sorteo: 1, numeros: [5, 1, 3, 2, 4], sb: 1 }), firma({ tipo: 'baloto', sorteo: 1, numeros: [1, 2, 3, 4, 5], sb: 1 }));
});

test('agrupar junta las fracciones del mismo billete (caso real 4821: fracciones 2 y 3)', () => {
  const fr2 = { ...v1[1], fraccion: 2 };
  const grupos = agrupar([v1[1], v1[0], fr2]);
  assert.equal(grupos.length, 2);
  const g = grupos.find(x => x.tipo === 'loteria');
  assert.deepEqual(g.boletos.map(b => b.fraccion), [2, 3]);
  assert.equal(claveBillete(fr2), claveBillete(v1[1]));
});

test('escribir y leer v2', () => {
  const a = almacen();
  escribir({ version: 2, boletos: [{ id: 'x', tipo: 'baloto', sorteo: 1, numeros: [1, 2, 3, 4, 5], sb: 1 }] }, a);
  assert.equal(leer(a).boletos[0].id, 'x');
});
