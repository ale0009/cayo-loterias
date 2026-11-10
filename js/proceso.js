import { iniciarTema } from './tema.js';
import { cargarDatos } from './datos.js';
import { barrasH, dispersion, rangos, mediana, probBaloto } from './graficas.js';

iniciarTema(document.querySelector('#tema'));
const $ = s => document.querySelector(s);
const pct = p => (p * 100).toLocaleString('es-CO', { maximumSignificantDigits: 3 }) + ' %';

// 1. Piloto: apostado vs recuperado (precios impresos en los boletos; calculado aquí)
$('#g-piloto').innerHTML = barrasH([
  { etiqueta: 'Apostado en Baloto', valor: 90000, texto: '$90.000' },
  { etiqueta: 'Recuperado en Baloto', valor: 11150, texto: '$11.150', clase: 'oro' },
  { etiqueta: 'Apostado en loterías', valor: 84000, texto: '$84.000' },
  { etiqueta: 'Recuperado en loterías', valor: 10500, texto: '$10.500', clase: 'oro' },
], { titulo: 'Apostado frente a recuperado en el piloto' });

// 2. Plan de premios de Medellín: cantidad de premios por clase (plan oficial de 3 fracciones)
$('#g-plan').innerHTML = barrasH([
  { etiqueta: 'Premio mayor', valor: 1, clase: 'rojo' },
  { etiqueta: 'Secos (con serie)', valor: 44, clase: 'rojo' },
  { etiqueta: '3 cifras con serie', valor: 18 },
  { etiqueta: '2 cifras con serie', valor: 180 },
  { etiqueta: 'Mayor en otra serie', valor: 499 },
  { etiqueta: 'Última cifra con serie', valor: 891 },
  { etiqueta: '3 cifras sin serie', valor: 8982 },
  { etiqueta: 'Serie del mayor', valor: 8910 },
  { etiqueta: 'Secos en otra serie', valor: 21956 },
  { etiqueta: '2 cifras sin serie', valor: 89820 },
  { etiqueta: 'Última cifra sin serie', valor: 444609, clase: 'oro' },
], { log: true, izq: 190, titulo: 'Cantidad de premios por clase en un sorteo de la Lotería de Medellín' });

// 3. Probabilidad de k aciertos en Baloto
$('#g-prob').innerHTML = barrasH([0, 1, 2, 3, 4, 5].map(k => ({
  etiqueta: `${k} acierto${k === 1 ? '' : 's'}`, valor: probBaloto(k),
  texto: k === 5 ? '1 en 962.598' : pct(probBaloto(k)), clase: k >= 3 ? 'oro' : '',
})), { log: false, izq: 110, titulo: 'Probabilidad de acertar k números en Baloto' }) +
  '<p class="nota">La Superbalota (1 de 16) se suma aparte: una de cada 16 jugadas la acierta.</p>';

(async () => {
  let D;
  try { D = await cargarDatos('../datos/'); } catch (e) {
    $('#estado-proceso').textContent = 'No se pudieron cargar los datos para las gráficas en vivo: ' + e.message; return;
  }
  const sorteos = Object.values(D.baloto.sorteos);
  const juegos = sorteos.flatMap(s => ['baloto', 'revancha'].map(j => s[j]).filter(Boolean));
  $('#estado-proceso').textContent = `Datos: ${sorteos.length} sorteos de Baloto y Revancha, ${Object.keys(D.medellin.sorteos).length} de Medellín y ${Object.keys(D.boyaca.sorteos).length} de Boyacá · actualizado ${new Date(D.estado.actualizado).toLocaleDateString('es-CO')}.`;

  // 4. ¿«0 + SB» incluye 1 acierto? Razón de ganadores (0+SB)/(2+SB) en cada sorteo
  const razones = juegos.map(j => j.premios?.['0+SB']?.ganadores / j.premios?.['2+SB']?.ganadores).filter(v => Number.isFinite(v) && v > 0);
  const solo0 = probBaloto(0) / probBaloto(2), cero1 = (probBaloto(0) + probBaloto(1)) / probBaloto(2);
  const med = mediana(razones);
  $('#g-sb').innerHTML = dispersion(razones, [
    { valor: solo0, etiqueta: `si fuera solo 0 aciertos: ${solo0.toFixed(1)}`, clase: 'cian' },
    { valor: cero1, etiqueta: `si incluye 1 acierto: ${cero1.toFixed(1)}` },
  ], { titulo: 'Razón entre ganadores de 0+SB y de 2+SB por sorteo' });
  const cerca = Math.abs(med - cero1) < Math.abs(med - solo0);
  $('#t-sb').textContent = `Mediana observada: ${med.toFixed(1)} en ${razones.length} sorteos. ${cerca
    ? 'Queda más cerca de la hipótesis «0 o 1 acierto + SB»: por eso la herramienta paga esa fila también a quien acierta 1 número + Superbalota.'
    : 'Queda más cerca de «solo 0 aciertos»; la interpretación de la herramienta debe revisarse.'} La gente no elige números al azar (fechas, patrones), así que los puntos se dispersan.`;

  // 5. Premio real por categoría (solo Baloto, con ganadores)
  const cats = ['4+SB', '4', '3+SB', '3', '2+SB', '0+SB'];
  $('#g-categorias').innerHTML = rangos(cats.map(c => {
    const v = sorteos.map(s => s.baloto?.premios?.[c]).filter(p => p && p.ganadores > 0).map(p => p.por_ganador);
    return { etiqueta: c, min: Math.min(...v), max: Math.max(...v), mediana: mediana(v) };
  }).filter(f => Number.isFinite(f.min)), { titulo: 'Rango del premio por categoría de Baloto' });
})();
