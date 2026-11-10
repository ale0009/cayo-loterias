import { iniciarTema } from './tema.js';
import { cargarDatos, listaSorteos } from './datos.js';
import { iniciarEscaner, detenerEscaner } from './escaner.js';
import {
  leerCodigo, revisarLoteria, revisarBaloto, validarBaloto, buscarSorteo,
  cifrasFinalesIguales, vence, diasHasta, pesos, codigosDesdePlanes,
} from './motor.js';

const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fechaLarga = f => new Date(f + 'T12:00').toLocaleDateString('es-CO', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
const ESTALLIDO = '<svg class="estallido" viewBox="0 0 200 200" aria-hidden="true"><path d="M100 4l16 50 48-26-22 48 54 10-48 24 34 42-52-10 2 54-32-42-32 42 2-54-52 10 34-42-48-24 54-10-22-48 48 26z"/></svg>';
const EJEMPLO = '90160004850104836702';

let D = null;              // datos cargados
let ultimo = null;         // último boleto revisado (para guardarlo)

iniciarTema($('#tema'));

// ------------------------------------------------------------------ pestañas
const tabs = [...document.querySelectorAll('[role="tab"]')];
function elegirTab(t) {
  tabs.forEach(x => {
    const sel = x === t;
    x.setAttribute('aria-selected', sel); x.tabIndex = sel ? 0 : -1;
    document.getElementById(x.getAttribute('aria-controls')).hidden = !sel;
  });
  if (t.id !== 'tab-codigo') cerrarCamara();
}
tabs.forEach((t, i) => {
  t.addEventListener('click', () => elegirTab(t));
  t.addEventListener('keydown', e => {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (d) { const n = tabs[(i + d + tabs.length) % tabs.length]; elegirTab(n); n.focus(); }
  });
});

// ------------------------------------------------------------------ código de 20 dígitos
let CODS = {};
const nombreCorto = id => (D?.planes.loterias[id]?.nombre ?? id).replace(/^Lotería (de |del )?/, '');
function pintarPartes() {
  const v = $('#codigo').value.replace(/\D/g, '');
  const c = leerCodigo(v, CODS);
  if (!v) { $('#codigo-partes').innerHTML = ''; return; }
  if (!c) { $('#codigo-partes').innerHTML = `<span class="parte mal">${v.length}/20 dígitos${v[0] && v[0] !== '9' ? ' · debe empezar por 9' : ''}</span>`; return; }
  $('#codigo-partes').innerHTML = [
    ['Lotería', c.loteria ? nombreCorto(c.loteria) : `código ${c.codigoLoteria}`],
    ['Sorteo', c.sorteo], ['Número', c.numero], ['Serie', c.serie], ['Fracción', c.fraccion],
  ].map(([k, x]) => `<span class="parte ${k === 'Lotería' && !c.loteria ? 'mal' : ''}"><b>${k}</b>${esc(x)}</span>`).join('');
}
$('#codigo').addEventListener('input', pintarPartes);
$('#p-codigo').addEventListener('submit', e => {
  e.preventDefault();
  const c = leerCodigo($('#codigo').value, CODS);
  if (!c) return mostrarError('Ese número no tiene la forma esperada: son 20 dígitos y empiezan por 9. Están impresos justo debajo del código de barras.');
  if (!c.loteria) return mostrarError(`Aún no sabemos a qué lotería corresponde el código ${c.codigoLoteria}. Conocidos: ${Object.entries(CODS).map(([k, v]) => `${nombreCorto(v)} (${k})`).join(', ')}. Usa la pestaña «Lotería a mano»: ahí están todas las loterías soportadas.`);
  $('#sello').hidden = $('#codigo').value.replace(/\D/g, '') !== EJEMPLO;
  revisarBillete({ loteria: c.loteria, sorteo: c.sorteo, numero: c.numero, serie: c.serie, fraccion: c.fraccion });
});
$('#ejemplo-codigo').addEventListener('click', () => {
  $('#codigo').value = '9 016 0004850 1048 367 02'; pintarPartes(); $('#p-codigo').requestSubmit();
});

// cámara
$('#abrir-camara').addEventListener('click', async () => {
  $('#camara').hidden = false;
  try {
    await iniciarEscaner($('#video'), codigo => {
      cerrarCamara();
      $('#codigo').value = codigo; pintarPartes(); $('#p-codigo').requestSubmit();
    }, txt => { $('#camara-estado').textContent = txt; });
  } catch (err) {
    $('#camara-estado').textContent = err?.name === 'NotAllowedError'
      ? 'No diste permiso para usar la cámara. Puedes escribir los 20 números a mano.'
      : 'No se pudo abrir la cámara. Escribe los 20 números a mano.';
  }
});
function cerrarCamara() { detenerEscaner(); $('#camara').hidden = true; }
$('#cerrar-camara').addEventListener('click', cerrarCamara);

// ------------------------------------------------------------------ lotería a mano
function llenarSorteos() {
  const lot = $('#m-loteria').value;
  $('#m-sorteo').innerHTML = listaSorteos(D[lot]).map(s => `<option value="${s.id}">${s.id} · ${fechaLarga(s.fecha)}</option>`).join('');
}
$('#m-loteria').addEventListener('change', llenarSorteos);
for (const id of ['#m-numero', '#m-serie', '#q']) $(id).addEventListener('input', e => { e.target.value = e.target.value.replace(/\D/g, ''); });
$('#p-manual').addEventListener('submit', e => {
  e.preventDefault();
  $('#sello').hidden = true;
  revisarBillete({
    loteria: $('#m-loteria').value, sorteo: Number($('#m-sorteo').value),
    numero: $('#m-numero').value.padStart(4, '0'), serie: $('#m-serie').value.padStart(3, '0'),
    fracciones: Number($('#m-fracciones').value) || undefined,
  });
});

// ------------------------------------------------------------------ Baloto
const elegidos = new Set(); let sbElegida = null;
function pintarBolillero() {
  $('#b-bolas').innerHTML = Array.from({ length: 43 }, (_, i) => i + 1)
    .map(n => `<button type="button" class="bola" data-n="${n}" aria-pressed="${elegidos.has(n)}">${String(n).padStart(2, '0')}</button>`).join('');
  $('#b-sb').innerHTML = Array.from({ length: 16 }, (_, i) => i + 1)
    .map(n => `<button type="button" class="bola" data-sb="${n}" aria-pressed="${sbElegida === n}" aria-label="Superbalota ${n}">${String(n).padStart(2, '0')}</button>`).join('');
  $('#b-cuenta').textContent = `${elegidos.size}/5`;
}
$('#b-bolas').addEventListener('click', e => {
  const n = Number(e.target.dataset.n); if (!n) return;
  if (elegidos.has(n)) elegidos.delete(n); else if (elegidos.size < 5) elegidos.add(n);
  pintarBolillero(); $(`[data-n="${n}"]`).focus();
});
$('#b-sb').addEventListener('click', e => {
  const n = Number(e.target.dataset.sb); if (!n) return;
  sbElegida = sbElegida === n ? null : n; pintarBolillero(); $(`[data-sb="${n}"]`).focus();
});
$('#b-limpiar').addEventListener('click', () => { elegidos.clear(); sbElegida = null; pintarBolillero(); });
$('#p-baloto').addEventListener('submit', e => {
  e.preventDefault();
  const nums = [...elegidos].sort((a, b) => a - b);
  const err = validarBaloto(nums, sbElegida);
  if (err) return mostrarError(err);
  $('#sello').hidden = true;
  revisarTiquete({ sorteo: Number($('#b-sorteo').value), numeros: nums, sb: sbElegida });
});

// ------------------------------------------------------------------ veredictos
function mostrarError(txt) {
  $('#veredicto').innerHTML = '<span class="no">¡Ups!</span>';
  $('#detalle').innerHTML = `<p class="error">${esc(txt)}</p>`;
}

function evaluar(b) {
  if (b.tipo === 'baloto') {
    const s = buscarSorteo(D.baloto, { sorteo: b.sorteo });
    if (!s) return { estado: 'pendiente', total: 0 };
    const r = revisarBaloto(b, s);
    const total = r.reduce((a, x) => a + (x.premio || 0), 0);
    return { estado: r.some(x => x.categoria) ? 'gano' : 'no', total, r, sorteo: s };
  }
  const s = buscarSorteo(D[b.loteria], { sorteo: b.sorteo });
  if (!s) return { estado: 'pendiente', total: 0 };
  const plan = D.planes.loterias[b.loteria];
  const r = revisarLoteria(b, s, plan);
  return { estado: r.gano ? 'gano' : 'no', total: r.netoFraccion, r, sorteo: s, plan };
}

function bloqueVence(fecha, gano) {
  if (!gano) return '';
  const lim = vence(fecha); const dias = diasHasta(lim);
  const pct = Math.max(0, Math.min(100, (dias / 365) * 100));
  return `<li>Cobra antes del <b>${fechaLarga(lim)}</b> (${dias > 0 ? `quedan ${dias} días` : 'ya venció'}).
    <div class="medidor ${dias < 60 ? 'alerta' : ''}" role="img" aria-label="Tiempo restante para cobrar: ${dias} días de 365"><span style="width:${pct}%"></span></div></li>`;
}

function revisarBillete(b) {
  const lot = b.loteria; const plan = D.planes.loterias[lot];
  ultimo = { tipo: 'loteria', ...b };
  const ev = evaluar(ultimo);
  if (ev.estado === 'pendiente') {
    const ult = listaSorteos(D[lot])[0];
    const futuro = Number(b.sorteo) > Number(ult.id);
    $('#veredicto').innerHTML = `<span class="pend">${futuro ? 'Aún no se juega' : 'Sin datos de ese sorteo'}</span>`;
    $('#detalle').innerHTML = `<p>${esc(plan.nombre)} · sorteo ${esc(b.sorteo)}. ${futuro
      ? `El último sorteo con resultados es el ${ult.id} (${fechaLarga(ult.fecha)}). Guárdalo en tu billetera y se revisará solo.`
      : 'Ese sorteo es anterior al año de datos que guarda la herramienta (los premios vencen al año).'}</p>
      <div class="acciones"><button class="boton-linea" id="guardar" type="button">Guardar en mi billetera</button></div>`;
    $('#guardar').onclick = guardarUltimo; return;
  }
  const { r, sorteo: s } = ev;
  const k = cifrasFinalesIguales(b.numero, s.mayor.numero);
  const dig = (n, marcar) => [...n].map((d, i) => `<span class="d ${marcar(i) ? 'ok' : ''}">${d}</span>`).join('');
  const etq = D.planes.etiquetas;
  const marcarPrim = r.categoria?.startsWith('tres_primeras') ? 3 : r.categoria?.startsWith('dos_primeras') ? 2 : 0;
  const marca = i => i >= 4 - k || i < marcarPrim || r.categoria === 'mayor' || r.categoria === 'mayor_sin_serie';
  $('#veredicto').innerHTML = r.gano ? '<span class="si">¡Cayó!</span>' : '<span class="no">No cayó</span>';
  $('#detalle').innerHTML = `${r.gano ? ESTALLIDO : ''}
    ${r.gano && r.desconocido ? `<p class="monto">Premio seco <small>la fuente no publica su valor: confírmalo en ${esc(new URL(plan.fuente_resultados).hostname)}</small></p>` : ''}
    ${r.gano && !r.desconocido ? `<p class="monto">${pesos(r.netoFraccion)} <small>neto por fracción · ${pesos(r.netoBillete)} el billete completo</small></p>
      <div class="en-linea fracc" role="group" aria-label="Fracciones del billete"><span class="meta">Tu billete es de</span>${[1, 2, 3, 4].map(n =>
        `<button type="button" class="mini" data-fr="${n}" aria-pressed="${n === r.fracciones}">${n} fracc.</button>`).join('')}</div>
      <p><b>${esc(etq[r.categoria] || r.categoria)}</b>${r.otras.length ? ` · también cumple: ${r.otras.map(o => esc(etq[o.clave])).join(', ')} (no se suman)` : ''}</p>` : ''}
    <dl class="comparar">
      <dt>Tu billete</dt><dd class="cifras">${dig(b.numero, marca)}<small>serie ${esc(b.serie)}${b.fraccion ? ` · fracción ${b.fraccion}` : ''}</small></dd>
      <dt>Mayor</dt><dd class="cifras">${dig(s.mayor.numero, marca)}<small>serie ${esc(s.mayor.serie)}</small></dd>
    </dl>
    <ul class="datos-cobro">
      <li>${esc(plan.nombre)} · sorteo ${s.id} · ${fechaLarga(s.fecha)} · ${s.secos.length} secos revisados.</li>
      ${s.aviso ? `<li class="aviso-fuente"><b>Ojo:</b> ${esc(s.aviso)}. ${r.gano ? '' : 'Revisa el acta oficial antes de botar el billete.'}</li>` : ''}
      ${bloqueVence(s.fecha, r.gano)}
      ${r.gano ? `<li>${esc(plan.cobro)} Lleva el billete original, entero y legible: es un documento al portador.</li>` : ''}
      <li>Fuente: <a href="${plan.fuente_resultados}" target="_blank" rel="noopener">${new URL(plan.fuente_resultados).hostname}</a></li>
    </ul>
    <div class="acciones"><button class="boton-linea" id="guardar" type="button">Guardar en mi billetera</button></div>`;
  $('#guardar').onclick = guardarUltimo;
  document.querySelectorAll('[data-fr]').forEach(x => x.onclick = () => revisarBillete({ ...b, fracciones: Number(x.dataset.fr) }));
}

function revisarTiquete(t) {
  ultimo = { tipo: 'baloto', ...t };
  const ev = evaluar(ultimo);
  if (ev.estado === 'pendiente') {
    $('#veredicto').innerHTML = '<span class="pend">Aún no se juega</span>';
    $('#detalle').innerHTML = `<p>No hay resultados del sorteo ${esc(t.sorteo)}. Guárdalo y se revisará solo.</p><div class="acciones"><button class="boton-linea" id="guardar" type="button">Guardar en mi billetera</button></div>`;
    $('#guardar').onclick = guardarUltimo; return;
  }
  const filas = ev.r.map(j => `<dt>${j.juego === 'baloto' ? 'Baloto' : 'Revancha'}</dt><dd class="fila-bolas">
      ${j.oficial.map(n => `<span class="b ${j.aciertos.includes(n) ? 'ok' : ''}">${String(n).padStart(2, '0')}</span>`).join('')}
      <span class="mas">+</span><span class="b sb ${j.acertoSB ? 'ok' : ''}">${String(j.sbOficial).padStart(2, '0')}</span>
      <small>&nbsp;${j.aciertos.length} acierto${j.aciertos.length === 1 ? '' : 's'}${j.acertoSB ? ' + SB' : ''}${j.categoria ? ` → <b>${j.acumulado ? 'premio acumulado: reclámalo' : pesos(j.premio)}</b>` : ''}</small></dd>`).join('');
  $('#veredicto').innerHTML = ev.estado === 'gano' ? '<span class="si">¡Cayó!</span>' : '<span class="no">No cayó</span>';
  $('#detalle').innerHTML = `${ev.estado === 'gano' ? ESTALLIDO + `<p class="monto">${pesos(ev.total)} <small>premio por ganador según la tabla oficial del sorteo</small></p>` : ''}
    <dl class="comparar">
      <dt>Tu jugada</dt><dd class="fila-bolas">${t.numeros.map(n => `<span class="b">${String(n).padStart(2, '0')}</span>`).join('')}<span class="mas">+</span><span class="b sb">${String(t.sb).padStart(2, '0')}</span></dd>
      ${filas}
    </dl>
    <ul class="datos-cobro">
      <li>Sorteo ${ev.sorteo.id} · ${fechaLarga(ev.sorteo.fecha)}. Un tiquete juega Baloto y Revancha.</li>
      ${bloqueVence(ev.sorteo.fecha, ev.estado === 'gano')}
      ${ev.estado === 'gano' ? `<li>${esc(D.planes.baloto.cobro)}</li>` : ''}
      <li>Fuente: <a href="https://www.baloto.com/resultados-baloto/${ev.sorteo.id}" target="_blank" rel="noopener">baloto.com</a></li>
    </ul>
    <div class="acciones"><button class="boton-linea" id="guardar" type="button">Guardar en mi billetera</button></div>`;
  $('#guardar').onclick = guardarUltimo;
}

// ------------------------------------------------------------------ billetera (localStorage)
const CLAVE = 'cayo-billetera';
function leerBilletera() { try { return JSON.parse(localStorage.getItem(CLAVE)) || []; } catch { return []; } }
function escribirBilletera(l) { try { localStorage.setItem(CLAVE, JSON.stringify(l)); } catch { /* sin almacenamiento */ } }
let billetera = leerBilletera();
const firma = b => b.tipo === 'baloto' ? `b|${b.sorteo}|${b.numeros.join('-')}|${b.sb}` : `l|${b.loteria}|${b.sorteo}|${b.numero}|${b.serie}|${b.fraccion ?? ''}`;

function guardarUltimo() {
  if (!ultimo) return;
  if (!billetera.some(b => firma(b) === firma(ultimo))) { billetera.unshift({ ...ultimo, agregado: new Date().toISOString().slice(0, 10) }); escribirBilletera(billetera); }
  pintarBilletera();
  $('#guardar').textContent = 'Guardado ✓'; $('#guardar').disabled = true;
}

function pintarBilletera() {
  const filas = billetera.map((b, i) => ({ b, i, ev: evaluar(b) }));
  const ganados = filas.filter(f => f.ev.estado === 'gano');
  const vigentes = ganados.filter(f => diasHasta(vence(f.ev.sorteo.fecha)) > 0);
  const prox = vigentes.map(f => diasHasta(vence(f.ev.sorteo.fecha))).sort((a, b) => a - b)[0];
  $('#hud').innerHTML = `<span class="pieza"><b>${billetera.length}</b> boletos</span>
    <span class="pieza oro"><b>${ganados.length}</b> con premio</span>
    <span class="pieza"><b>${pesos(vigentes.reduce((a, f) => a + f.ev.total, 0))}</b> por cobrar</span>
    ${prox !== undefined ? `<span class="pieza">vence en <b>${prox}</b> días</span>` : ''}`;
  if (!filas.length) { $('#lista').innerHTML = '<li class="vacio">Aún no guardas boletos. Revisa uno y toca «Guardar en mi billetera».</li>'; return; }
  filas.sort((x, y) => ({ gano: 0, pendiente: 1, no: 2 }[x.ev.estado] - { gano: 0, pendiente: 1, no: 2 }[y.ev.estado]));
  $('#lista').innerHTML = filas.map(({ b, i, ev }) => {
    const titulo = b.tipo === 'baloto' ? 'Baloto + Revancha' : D.planes.loterias[b.loteria]?.nombre ?? b.loteria;
    const linea = b.tipo === 'baloto' ? `${b.numeros.map(n => String(n).padStart(2, '0')).join(' ')} + ${String(b.sb).padStart(2, '0')}` : `${b.numero} · serie ${b.serie}${b.fraccion ? ` · fr. ${b.fraccion}` : ''}`;
    const est = ev.estado === 'gano' ? `Ganó ${pesos(ev.total)} · cobra antes del ${fechaLarga(vence(ev.sorteo.fecha))}`
      : ev.estado === 'pendiente' ? 'Pendiente: aún sin resultados' : 'Sin premio';
    return `<li class="boleto ${ev.estado === 'gano' ? 'gano' : ev.estado === 'pendiente' ? 'pend' : 'no'}">
      <button class="quitar" data-i="${i}" aria-label="Quitar boleto ${esc(linea)}">×</button>
      <h3>${esc(titulo)}</h3><div class="linea">${esc(linea)}</div>
      <div class="meta">Sorteo ${esc(b.sorteo)}${ev.sorteo ? ` · ${fechaLarga(ev.sorteo.fecha)}` : ''}</div>
      <div class="meta"><b>${esc(est)}</b></div></li>`;
  }).join('');
}
$('#lista').addEventListener('click', e => {
  const i = e.target.dataset.i; if (i === undefined) return;
  billetera.splice(Number(i), 1); escribirBilletera(billetera); pintarBilletera();
});
$('#vaciar').addEventListener('click', () => {
  if (billetera.length && confirm('¿Quitar todos los boletos de la billetera de este navegador?')) { billetera = []; escribirBilletera(billetera); pintarBilletera(); }
});
$('#exportar').addEventListener('click', () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(billetera, null, 1)], { type: 'application/json' }));
  a.download = `mis-boletos-${new Date().toISOString().slice(0, 10)}.json`; a.click(); URL.revokeObjectURL(a.href);
});
$('#importar').addEventListener('change', async e => {
  const f = e.target.files[0]; if (!f) return;
  try {
    const j = JSON.parse(await f.text());
    // Acepta la billetera exportada o el formato {baloto:[...], loterias:[...]}
    const nuevos = Array.isArray(j) ? j : [
      ...(j.baloto ?? []).map(b => ({ tipo: 'baloto', sorteo: b.sorteo, numeros: b.numeros, sb: b.superbalota ?? b.sb })),
      ...(j.loterias ?? []).map(l => ({ tipo: 'loteria', loteria: String(l.loteria).toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, ''),
        sorteo: l.sorteo, numero: l.numero, serie: l.serie, fraccion: parseInt(l.fraccion) || undefined, fracciones: parseInt(String(l.fraccion).split('de')[1]) || undefined })),
    ];
    const conocidas = new Set(['baloto', ...Object.keys(D.planes.loterias)]);
    let n = 0;
    for (const b of nuevos) {
      if (b.tipo === 'loteria' && !conocidas.has(b.loteria)) continue;
      if (!billetera.some(x => firma(x) === firma(b))) { billetera.push(b); n++; }
    }
    escribirBilletera(billetera); pintarBilletera();
    alert(`Se importaron ${n} boletos${nuevos.length - n ? ` (${nuevos.length - n} repetidos o de loterías aún no soportadas)` : ''}.`);
  } catch { alert('No se pudo leer ese archivo. Debe ser un JSON exportado desde esta herramienta.'); }
  e.target.value = '';
});

// ------------------------------------------------------------------ ¿cuándo cayó?
$('#f-buscar').addEventListener('submit', e => {
  e.preventDefault();
  const q = $('#q').value.padStart(4, '0');
  const hits = [];
  for (const lot of Object.keys(D.planes.loterias)) {
    for (const s of listaSorteos(D[lot])) {
      if (s.mayor.numero === q) hits.push({ lot, s, tipo: 'mayor', serie: s.mayor.serie });
      for (const x of s.secos) if (x.numero === q) hits.push({ lot, s, tipo: 'seco', serie: x.serie, valor: x.valor });
    }
  }
  const total = Object.keys(D.planes.loterias).reduce((a, l) => a + Object.keys(D[l].sorteos).length, 0);
  $('#r-buscar').innerHTML = hits.length
    ? `<p><b>${q}</b> salió ${hits.length} ${hits.length === 1 ? 'vez' : 'veces'} en ${total} sorteos revisados.</p><ul class="hallazgos">${hits.map(h =>
        `<li><span class="tag ${h.tipo}">${h.tipo}</span>${esc(D.planes.loterias[h.lot].nombre)} · sorteo ${h.s.id} · ${fechaLarga(h.s.fecha)} · serie <b>${h.serie}</b>${h.valor ? ` · ${pesos(h.valor)} brutos` : ''}</li>`).join('')}</ul>`
    : `<p>El <b>${q}</b> no salió como mayor ni como seco en los ${total} sorteos del último año. Con 10.000 números posibles y unos 50 por sorteo, lo normal es que la mayoría nunca aparezca.</p>`;
});

// ------------------------------------------------------------------ últimos resultados
function pintarUltimos() {
  const bal = listaSorteos(D.baloto)[0];
  const bolas = (o) => o ? `<div class="fila-bolas">${o.numeros.map(n => `<span class="b">${String(n).padStart(2, '0')}</span>`).join('')}<span class="mas">+</span><span class="b sb">${String(o.sb).padStart(2, '0')}</span></div>` : '<p class="meta">Sin datos</p>';
  const lot = Object.keys(D.planes.loterias).map(l => {
    const s = listaSorteos(D[l])[0];
    return `<div class="tarjeta"><h3>${esc(D.planes.loterias[l].nombre)}</h3><div class="meta">Sorteo ${s.id} · ${fechaLarga(s.fecha)}</div>
      <div class="cifras">${s.mayor.numero}<small>serie ${s.mayor.serie}</small></div></div>`;
  }).join('');
  $('#ultimos').innerHTML = `<div class="tarjeta"><h3>Baloto</h3><div class="meta">Sorteo ${bal.id} · ${fechaLarga(bal.fecha)}</div>${bolas(bal.baloto)}</div>
    <div class="tarjeta"><h3>Revancha</h3><div class="meta">Sorteo ${bal.id}</div>${bolas(bal.revancha)}</div>${lot}`;
  const est = D.estado;
  const fuentes = Object.entries(est.fuentes || {}).map(([k, v]) => `<span><span class="punto ${v.ok ? '' : 'mal'}"></span>${k}</span>`).join(' · ');
  $('#estado-datos').innerHTML = `Datos actualizados: ${est.actualizado ? new Date(est.actualizado).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }) : '—'} · ${fuentes}`;
}

// ------------------------------------------------------------------ arranque
(async () => {
  try {
    D = await cargarDatos();
  } catch (err) {
    $('#veredicto').innerHTML = '<span class="no">Sin datos</span>';
    $('#detalle').innerHTML = `<p class="error">No se pudieron cargar los resultados: ${esc(err.message)} Si abriste el archivo directamente, sírvelo con un servidor local (por ejemplo <code>python3 -m http.server</code>).</p>`;
    $('#ultimos').innerHTML = '';
    return;
  }
  CODS = codigosDesdePlanes(D.planes);
  $('#m-loteria').innerHTML = Object.entries(D.planes.loterias).map(([k, v]) => `<option value="${k}">${esc(v.nombre)}</option>`).join('');
  llenarSorteos();
  $('#b-sorteo').innerHTML = listaSorteos(D.baloto).map(s => `<option value="${s.id}">${s.id} · ${fechaLarga(s.fecha)}</option>`).join('');
  pintarBolillero(); pintarUltimos(); pintarBilletera();
  // Abre en un estado útil: el ejemplo real del piloto (un billete con premio pequeño).
  $('#codigo').value = '9 016 0004850 1048 367 02'; pintarPartes();
  $('#sello').hidden = false;
  revisarBillete({ loteria: 'medellin', sorteo: 4850, numero: '1048', serie: '367', fraccion: 2, fracciones: 2 });
})();
