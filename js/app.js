import { iniciarTema } from './tema.js';
import { cargarDatos, listaSorteos } from './datos.js';
import { iniciarEscaner, detenerEscaner } from './escaner.js';
import {
  leerCodigo, revisarLoteria, revisarBaloto, validarBaloto, buscarSorteo,
  cifrasFinalesIguales, vence, diasHasta, pesos, codigosDesdePlanes, aplicarVariante, varianteDe,
} from './motor.js';
import * as Billetera from './billetera.js';
import * as Fotos from './fotos.js';
import { leerCodigoEnFoto } from './lector-foto.js';

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
const nombreDe = id => D?.planes.loterias[id]?.nombre ?? D?.sinDatos?.[id]?.nombre ?? id;
const nombreCorto = id => nombreDe(id).replace(/^Lotería (de |de la |del )?/, '');
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
  if (!D[b.loteria]) return { estado: 'sin-datos', total: 0, info: D.sinDatos[b.loteria] };
  const s = buscarSorteo(D[b.loteria], { sorteo: b.sorteo });
  if (!s) return { estado: 'pendiente', total: 0 };
  const plan = D.planes.loterias[b.loteria];
  // Si se eligió un precio con variante (p. ej. $24.000) y no se sabe cuántas fracciones tiene, se usan las de esa variante.
  const v = varianteDe(plan, b.precio);
  const bb = v && !b.fracciones ? { ...b, fracciones: v.fracciones } : b;
  const r = aplicarVariante(revisarLoteria(bb, s, plan), plan, b.precio);
  // Si el valor es un rango «a confirmar», se cuenta el mínimo (lo seguro).
  return { estado: r.gano ? 'gano' : 'no', total: r.netoFraccionMin ?? r.netoFraccion, max: r.netoFraccionMax, r, sorteo: s, plan };
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
  if (ev.estado === 'sin-datos') {
    const info = ev.info ?? { nombre: lot };
    $('#veredicto').innerHTML = '<span class="pend">Aún sin resultados</span>';
    $('#detalle').innerHTML = `<p><b>${esc(info.nombre)}</b> · sorteo ${esc(b.sorteo)} · ${esc(b.numero)} serie ${esc(b.serie)}${b.fraccion ? ` · fracción ${b.fraccion}` : ''}.</p>
      <p>Todavía no tenemos los resultados de esta lotería${info.motivo ? `: ${esc(info.motivo)}` : '.'} ${info.fuente_resultados ? `Consúltalo en la <a href="${info.fuente_resultados}" target="_blank" rel="noopener">web oficial</a>.` : ''}</p>
      <p class="ayuda">Guárdalo en tu billetera: se revisará solo cuando la herramienta tenga sus resultados.</p>
      <div class="acciones"><button class="boton-linea" id="guardar" type="button">Guardar en mi billetera</button></div>`;
    $('#guardar').onclick = guardarUltimo; return;
  }
  if (ev.estado === 'pendiente') {
    const ult = listaSorteos(D[lot])[0];
    const ilegible = D.estado.ilegibles?.[lot]?.[String(b.sorteo)];
    if (ilegible) {
      $('#veredicto').innerHTML = '<span class="pend">Revísalo en la fuente</span>';
      $('#detalle').innerHTML = `<p class="error">${esc(plan.nombre)} · sorteo ${esc(b.sorteo)}: la lotería solo lo publicó como imagen y no se pudo leer de forma confiable después de varios intentos. Para no darte un resultado dudoso, consúltalo en la <a href="${plan.fuente_resultados}" target="_blank" rel="noopener">fuente oficial</a>.</p>`;
      return;
    }
    const futuro = Number(b.sorteo) > Number(ult.id);
    $('#veredicto').innerHTML = `<span class="pend">${futuro ? 'Aún no se juega' : 'Sin datos de ese sorteo'}</span>`;
    const primero = listaSorteos(D[lot]).at(-1);
    const hueco = !futuro && Number(b.sorteo) >= Number(primero.id);
    $('#detalle').innerHTML = `<p>${esc(plan.nombre)} · sorteo ${esc(b.sorteo)}. ${futuro
      ? `El último sorteo con resultados es el ${ult.id} (${fechaLarga(ult.fecha)}). Guárdalo en tu billetera y se revisará solo.`
      : hueco
        ? `Ese sorteo todavía no se ha podido leer de la fuente${plan.ocr ? ' (se publica como imagen y se reintenta cada noche)' : ''}. Guárdalo en tu billetera y se revisará solo; mientras tanto, consulta la <a href="${plan.fuente_resultados}" target="_blank" rel="noopener">fuente oficial</a>.`
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
    ${r.gano && !r.desconocido ? `<p class="monto">${r.netoFraccionMax ? `${pesos(r.netoFraccionMin)} – ${pesos(r.netoFraccionMax)}` : pesos(r.netoFraccion)} <small>${r.aConfirmar ? 'por fracción · <b>a confirmar al cobrar</b>' : `neto por fracción · ${pesos(r.netoBillete)} el billete completo`}</small></p>
      <div class="en-linea fracc" role="group" aria-label="Fracciones del billete"><span class="meta">Tu billete es de</span>${[1, 2, 3, 4].map(n =>
        `<button type="button" class="mini" data-fr="${n}" aria-pressed="${n === r.fracciones}">${n} fracc.</button>`).join('')}</div>
      ${plan.variantes?.length ? `<div class="en-linea fracc" role="group" aria-label="Precio del billete"><span class="meta">Pagaste</span>
        <button type="button" class="mini" data-precio="" aria-pressed="${!b.precio}">el precio del plan</button>${plan.variantes.map(v =>
        `<button type="button" class="mini" data-precio="${v.precio_billete}" aria-pressed="${Number(b.precio) === v.precio_billete}">${pesos(v.precio_billete)} el billete</button>`).join('')}</div>` : ''}
      ${r.variante ? `<p class="aviso-fuente">${esc(r.variante.nota)}</p>` : ''}
      <p><b>${esc(etq[r.categoria] || r.categoria)}</b>${r.otras.length ? ` · también cumple: ${r.otras.map(o => esc(etq[o.clave])).join(', ')} (no se suman)` : ''}</p>` : ''}
    <dl class="comparar">
      <dt>Tu billete</dt><dd class="cifras">${dig(b.numero, marca)}<small>serie ${esc(b.serie)}${b.fraccion ? ` · fracción ${b.fraccion}` : ''}</small></dd>
      <dt>Mayor</dt><dd class="cifras">${dig(s.mayor.numero, marca)}<small>serie ${esc(s.mayor.serie)}</small></dd>
    </dl>
    <ul class="datos-cobro">
      <li>${esc(plan.nombre)} · sorteo ${s.id} · ${fechaLarga(s.fecha)} · ${s.secos.length} secos revisados.</li>
      ${plan.ocr ? `<li class="aviso-fuente"><b>Leído con OCR:</b> ${esc(plan.aviso_ocr)} <a href="${plan.fuente_resultados}" target="_blank" rel="noopener">Ver resultados oficiales</a>.</li>` : ''}
      ${s.aviso ? `<li class="aviso-fuente"><b>Ojo:</b> ${esc(s.aviso)}. ${r.gano ? '' : 'Revisa el acta oficial antes de botar el billete.'}</li>` : ''}
      ${D.estado.auditoria?.[lot]?.inconsistentes?.[s.id] ? `<li class="aviso-fuente"><b>Verificación nocturna:</b> al volver a consultar este sorteo, la fuente mostró algo distinto a lo guardado. Confírmalo en la <a href="${plan.fuente_resultados}" target="_blank" rel="noopener">web oficial</a>.</li>` : ''}
      ${D.estado.auditoria?.[lot]?.muestra?.includes(s.id) && !D.estado.auditoria[lot].inconsistentes?.[s.id] ? '<li>Este sorteo se volvió a verificar contra la fuente en la auditoría nocturna y coincide.</li>' : ''}
      ${bloqueVence(s.fecha, r.gano)}
      ${r.gano ? `<li>${esc(plan.cobro)} Lleva el billete original, entero y legible: es un documento al portador.</li>` : ''}
      <li>Fuente: <a href="${plan.fuente_resultados}" target="_blank" rel="noopener">${new URL(plan.fuente_resultados).hostname}</a></li>
    </ul>
    <div class="acciones"><button class="boton-linea" id="guardar" type="button">Guardar en mi billetera</button></div>`;
  $('#guardar').onclick = guardarUltimo;
  document.querySelectorAll('[data-fr]').forEach(x => x.onclick = () => revisarBillete({ ...b, fracciones: Number(x.dataset.fr) }));
  document.querySelectorAll('[data-precio]').forEach(x => x.onclick = () => revisarBillete({ ...b, precio: Number(x.dataset.precio) || undefined }));
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

// ------------------------------------------------------------------ billetera v2 (localStorage, ver js/billetera.js)
let cartera = Billetera.leer();
const guardarCartera = () => Billetera.escribir(cartera);

function guardarUltimo() {
  if (!ultimo) return;
  const r = Billetera.fusionar(cartera.boletos, [ultimo], 'manual');
  if (r.agregados) { cartera = { ...cartera, boletos: r.lista }; guardarCartera(); }
  pintarBilletera();
  $('#guardar').textContent = r.agregados ? 'Guardado ✓' : 'Ya estaba guardado'; $('#guardar').disabled = true;
}

const ORDEN_ESTADO = { gano: 0, pendiente: 1, 'sin-datos': 2, no: 3 };
function evaluarGrupo(g) {
  const evs = g.boletos.map(b => ({ b, ev: evaluar(b) }));
  const gano = evs.filter(x => x.ev.estado === 'gano');
  const estado = gano.length ? 'gano' : evs.some(x => x.ev.estado === 'pendiente') ? 'pendiente' : evs[0].ev.estado;
  const total = gano.reduce((a, x) => a + x.ev.total, 0);
  const max = gano.some(x => x.ev.max) ? gano.reduce((a, x) => a + (x.ev.max ?? x.ev.total), 0) : null;
  return { g, evs, estado, total, max, sorteo: evs.find(x => x.ev.sorteo)?.ev.sorteo };
}

function pintarBilletera() {
  const grupos = Billetera.agrupar(cartera.boletos).map(evaluarGrupo);
  const ganados = grupos.filter(x => x.estado === 'gano');
  const vigentes = ganados.filter(x => diasHasta(vence(x.sorteo.fecha)) > 0);
  const prox = vigentes.map(x => diasHasta(vence(x.sorteo.fecha))).sort((a, b) => a - b)[0];
  const suma = vigentes.reduce((a, x) => a + x.total, 0);
  const sumaMax = vigentes.reduce((a, x) => a + (x.max ?? x.total), 0);
  $('#hud').innerHTML = `<span class="pieza"><b>${cartera.boletos.length}</b> boletos</span>
    <span class="pieza oro"><b>${ganados.length}</b> con premio</span>
    <span class="pieza"><b>${pesos(suma)}${sumaMax > suma ? ` – ${pesos(sumaMax)}` : ''}</b> por cobrar</span>
    ${prox !== undefined ? `<span class="pieza">vence en <b>${prox}</b> días</span>` : ''}`;
  pintarFiltros(grupos);
  $('#lista').classList.toggle('con-fotos', vista === 'fotos');
  if (!grupos.length) { $('#lista').innerHTML = '<li class="vacio">Aún no guardas boletos. Revisa uno y toca «Guardar en mi billetera», o sube fotos de tus boletos.</li>'; return; }
  grupos.sort((x, y) => ORDEN_ESTADO[x.estado] - ORDEN_ESTADO[y.estado]);
  const visibles = grupos.filter(x => filtroB === 'todos' || (filtroB === 'pendiente' ? ['pendiente', 'sin-datos'].includes(x.estado) : x.estado === filtroB));
  liberarUrls();
  $('#lista').innerHTML = visibles.map(({ g, evs, estado, total, max, sorteo }) => {
    const b = g.boletos[0];
    const titulo = b.tipo === 'baloto' ? 'Baloto + Revancha' : nombreDe(b.loteria);
    const fr = g.boletos.map(x => x.fraccion).filter(Boolean);
    const linea = b.tipo === 'baloto' ? `${b.numeros.map(n => String(n).padStart(2, '0')).join(' ')} + ${String(b.sb).padStart(2, '0')}`
      : `${b.numero} · serie ${b.serie}${fr.length ? ` · fr. ${fr.join(', ')}${b.fracciones ? ` de ${b.fracciones}` : ''}` : ''}`;
    const monto = max && max > total ? `${pesos(total)} – ${pesos(max)} (a confirmar)` : pesos(total);
    const est = estado === 'gano' ? `Ganó ${monto}${g.boletos.length > 1 ? ` en ${evs.filter(x => x.ev.estado === 'gano').length} fracciones` : ''} · cobra antes del ${fechaLarga(vence(sorteo.fecha))}`
      : estado === 'pendiente' ? 'Pendiente: aún sin resultados'
      : estado === 'sin-datos' ? 'Sin datos de esta lotería: consúltalo en la web oficial' : 'Sin premio';
    const foto = g.boletos.find(x => x.fotoId)?.fotoId;
    const img = vista !== 'fotos' ? '' : foto
      ? `<img class="miniatura" data-foto="${foto}" alt="Foto del boleto: ${esc(titulo)} ${esc(linea)}" tabindex="0">`
      : '<div class="sin-foto">Sin foto</div>';
    return `<li class="boleto ${estado === 'gano' ? 'gano' : estado === 'no' ? 'no' : 'pend'}">
      <button class="quitar" data-ids="${g.boletos.map(x => x.id).join(',')}" aria-label="Quitar ${esc(titulo)} ${esc(linea)}">×</button>
      ${img}<h3>${esc(titulo)}</h3><div class="linea">${esc(linea)}</div>
      <div class="meta">Sorteo ${esc(b.sorteo)}${sorteo ? ` · ${fechaLarga(sorteo.fecha)}` : ''}${b.precio ? ` · billete de ${pesos(b.precio)}` : ''}</div>
      <div class="meta"><b>${esc(est)}</b></div></li>`;
  }).join('') || '<li class="vacio">Ningún boleto con ese filtro.</li>';
  if (vista === 'fotos') pintarMiniaturas();
}

// ------------------------------------------------------------------ vista con fotos, filtros y zoom
let vista = 'lista', filtroB = 'todos';
const urls = [];
function liberarUrls() { while (urls.length) URL.revokeObjectURL(urls.pop()); }
const urlDe = blob => { const u = URL.createObjectURL(blob); urls.push(u); return u; };
async function pintarMiniaturas() {
  for (const img of document.querySelectorAll('#lista img[data-foto]')) {
    const f = await Fotos.leer(img.dataset.foto).catch(() => null);
    if (f?.mini) img.src = urlDe(f.mini); else img.replaceWith(Object.assign(document.createElement('div'), { className: 'sin-foto', textContent: 'Foto no encontrada en este navegador' }));
  }
}
function pintarFiltros(grupos) {
  const n = k => grupos.filter(x => k === 'todos' || (k === 'pendiente' ? ['pendiente', 'sin-datos'].includes(x.estado) : x.estado === k)).length;
  $('#filtros-billetera').innerHTML = [['todos', 'Todos'], ['gano', 'Con premio'], ['pendiente', 'Pendientes o sin datos'], ['no', 'Sin premio']]
    .map(([k, txt]) => `<button type="button" data-filtro="${k}" aria-pressed="${k === filtroB}">${txt} (${n(k)})</button>`).join('');
}
$('#filtros-billetera').addEventListener('click', e => { const f = e.target.closest('[data-filtro]')?.dataset.filtro; if (f) { filtroB = f; pintarBilletera(); } });
$('#modo-vista').addEventListener('click', e => {
  const v = e.target.closest('[data-vista]')?.dataset.vista; if (!v) return;
  vista = v; document.querySelectorAll('#modo-vista button').forEach(b => b.setAttribute('aria-pressed', b.dataset.vista === v));
  pintarBilletera();
});
async function ampliar(hash) {
  const f = await Fotos.leer(hash).catch(() => null);
  if (!f) return;
  const d = $('#zoom-foto'); const img = d.querySelector('img');
  img.src = urlDe(f.blob); img.alt = 'Foto del boleto ampliada';
  d.showModal();
}
document.addEventListener('click', e => { const h = e.target.closest('img[data-foto]')?.dataset.foto; if (h) ampliar(h); });
document.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.matches?.('img[data-foto]')) ampliar(e.target.dataset.foto); });

// ------------------------------------------------------------------ subir fotos (solo local)
$('#subir-fotos').addEventListener('change', async e => {
  const archivos = [...e.target.files]; e.target.value = '';
  if (!archivos.length) return;
  const usadas = new Set(cartera.boletos.map(b => b.fotoId).filter(Boolean));
  let nuevas = 0, repetidas = 0, leidas = 0;
  await Fotos.espacio();
  for (const [i, f] of archivos.entries()) {
    $('#estado-fotos').textContent = `Procesando foto ${i + 1} de ${archivos.length}…`;
    try {
      const hash = await Fotos.huella(f);
      if (usadas.has(hash) || await Fotos.existe(hash)) { repetidas++; continue; }
      const { mini, ancho, alto } = await Fotos.miniatura(f);
      const lectura = await leerCodigoEnFoto(f, CODS);
      if (lectura) leidas++;
      await Fotos.guardar({ hash, blob: f, mini, ancho, alto, nombre: f.name, agregado: new Date().toISOString(), estado: 'pendiente', lectura });
      nuevas++;
    } catch { /* foto ilegible o formato no soportado (p. ej. HEIC fuera de Safari): se omite */ }
  }
  $('#estado-fotos').textContent = `${nuevas} foto${nuevas === 1 ? '' : 's'} nueva${nuevas === 1 ? '' : 's'}${repetidas ? ` · ${repetidas} repetida${repetidas === 1 ? '' : 's'} omitida${repetidas === 1 ? '' : 's'}` : ''}${nuevas ? ` · código leído en ${leidas}` : ''}.`;
  pintarBandeja();
});

const opcionesLoteria = sel => [...Object.entries(D.planes.loterias), ...Object.entries(D.sinDatos)]
  .map(([k, v]) => `<option value="${k}" ${k === sel ? 'selected' : ''}>${esc(v.nombre)}${D[k] ? '' : ' (sin datos)'}</option>`).join('');

async function pintarBandeja() {
  const pendientes = (await Fotos.listar().catch(() => [])).filter(f => f.estado === 'pendiente');
  $('#bandeja').hidden = !pendientes.length;
  $('#bandeja-cuenta').textContent = pendientes.length ? `(${pendientes.length})` : '';
  $('#lista-bandeja').innerHTML = pendientes.map(f => {
    const c = f.lectura ? leerCodigo(f.lectura.codigo, CODS) : null;
    return `<li class="pendiente-foto" data-hash="${f.hash}">
      <img data-foto="${f.hash}" data-mini="1" alt="Foto subida ${esc(f.nombre || '')}" tabindex="0">
      <form class="form-foto" autocomplete="off">
        <p class="lectura ${c ? 'ok' : ''}">${c ? `Código leído (${esc(f.lectura.via)}): revisa y guarda.` : 'No se pudo leer el código de barras: escribe los datos.'}</p>
        <div class="campos">
          <label>Tipo <select name="tipo"><option value="loteria">Lotería</option><option value="baloto">Baloto</option></select></label>
          <label class="solo-lot">Lotería <select name="loteria">${opcionesLoteria(c?.loteria ?? 'medellin')}</select></label>
          <label>Sorteo <input name="sorteo" inputmode="numeric" value="${c?.sorteo ?? ''}" required></label>
          <label class="solo-lot">Número <input name="numero" class="num4" inputmode="numeric" maxlength="4" value="${c?.numero ?? ''}"></label>
          <label class="solo-lot">Serie <input name="serie" class="num3" inputmode="numeric" maxlength="3" value="${c?.serie ?? ''}"></label>
          <label class="solo-lot">Fracción <input name="fraccion" inputmode="numeric" maxlength="2" value="${c?.fraccion ?? ''}"></label>
          <label class="solo-lot">De (fracciones) <input name="fracciones" inputmode="numeric" maxlength="2"></label>
          <label class="solo-bal" hidden>Números (5) <input name="numeros" placeholder="01 06 08 15 41"></label>
          <label class="solo-bal" hidden>Superbalota <input name="sb" inputmode="numeric" maxlength="2"></label>
        </div>
        <div class="acciones"><button class="boton" type="submit">Guardar boleto</button><button class="boton-texto" type="button" data-descartar>Descartar foto</button></div>
        <p class="error" hidden></p>
      </form></li>`;
  }).join('');
  liberarUrls();
  for (const img of document.querySelectorAll('#lista-bandeja img[data-foto]')) {
    const f = pendientes.find(x => x.hash === img.dataset.foto); if (f?.mini) img.src = urlDe(f.mini);
  }
}
$('#lista-bandeja').addEventListener('change', e => {
  if (e.target.name !== 'tipo') return;
  const form = e.target.form, bal = e.target.value === 'baloto';
  form.querySelectorAll('.solo-lot').forEach(x => { x.hidden = bal; });
  form.querySelectorAll('.solo-bal').forEach(x => { x.hidden = !bal; });
});
$('#lista-bandeja').addEventListener('click', async e => {
  if (!e.target.matches('[data-descartar]')) return;
  const hash = e.target.closest('[data-hash]').dataset.hash;
  await Fotos.borrar(hash); pintarBandeja();
});
$('#lista-bandeja').addEventListener('submit', async e => {
  e.preventDefault();
  const form = e.target, hash = form.closest('[data-hash]').dataset.hash, d = Object.fromEntries(new FormData(form));
  const err = m => { const p = form.querySelector('.error'); p.textContent = m; p.hidden = false; };
  let boleto;
  if (d.tipo === 'baloto') {
    const numeros = (d.numeros.match(/\d+/g) || []).map(Number).sort((a, b) => a - b);
    const problema = validarBaloto(numeros, d.sb);
    if (problema) return err(problema);
    boleto = { tipo: 'baloto', sorteo: Number(d.sorteo), numeros, sb: Number(d.sb) };
  } else {
    if (!/^\d{1,4}$/.test(d.numero) || !/^\d{1,3}$/.test(d.serie) || !/^\d+$/.test(d.sorteo)) return err('Revisa el sorteo, el número (4 cifras) y la serie (3 cifras).');
    boleto = { tipo: 'loteria', loteria: d.loteria, sorteo: Number(d.sorteo), numero: d.numero.padStart(4, '0'), serie: d.serie.padStart(3, '0'),
      fraccion: Number(d.fraccion) || undefined, fracciones: Number(d.fracciones) || undefined };
  }
  const r = Billetera.fusionar(cartera.boletos, [{ ...boleto, fotoId: hash }], 'foto');
  if (!r.agregados) return err('Ese boleto ya estaba en tu billetera.');
  cartera = { ...cartera, boletos: r.lista }; guardarCartera();
  const f = await Fotos.leer(hash); await Fotos.guardar({ ...f, estado: 'asignada' });
  vista = 'fotos'; document.querySelectorAll('#modo-vista button').forEach(b => b.setAttribute('aria-pressed', b.dataset.vista === 'fotos'));
  pintarBandeja(); pintarBilletera();
});
$('#lista').addEventListener('click', e => {
  const ids = e.target.dataset.ids; if (!ids) return;
  const quitar = new Set(ids.split(','));
  const fotos = cartera.boletos.filter(b => quitar.has(b.id) && b.fotoId).map(b => b.fotoId);
  cartera = { ...cartera, boletos: cartera.boletos.filter(b => !quitar.has(b.id)) }; guardarCartera(); pintarBilletera();
  for (const h of fotos) if (!cartera.boletos.some(b => b.fotoId === h)) Fotos.borrar(h).catch(() => {});
});
$('#vaciar').addEventListener('click', () => {
  if (confirm('¿Quitar todos los boletos y sus fotos de la billetera de este navegador? No se puede deshacer.')) {
    cartera = { version: 2, boletos: [] }; guardarCartera(); Fotos.vaciar().catch(() => {}); pintarBilletera(); pintarBandeja();
  }
});
$('#exportar').addEventListener('click', () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(cartera, null, 1)], { type: 'application/json' }));
  a.download = `mis-boletos-${new Date().toISOString().slice(0, 10)}.json`; a.click(); URL.revokeObjectURL(a.href);
});
$('#importar').addEventListener('change', async e => {
  const f = e.target.files[0]; if (!f) return;
  try {
    const nuevos = Billetera.normalizarImportado(JSON.parse(await f.text()));
    const r = Billetera.fusionar(cartera.boletos, nuevos, 'importado');
    cartera = { ...cartera, boletos: r.lista }; guardarCartera(); pintarBilletera();
    const sinDatos = nuevos.filter(b => b.tipo === 'loteria' && !D[b.loteria]).length;
    alert(`Se importaron ${r.agregados} boletos${r.repetidos ? ` (${r.repetidos} repetidos omitidos)` : ''}.${sinDatos ? ` ${sinDatos} son de loterías que aún no tienen resultados: quedan guardados y se revisarán cuando los haya.` : ''}`);
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
  // Aviso visible si los datos se quedaron viejos o alguna fuente está fallando (la página se vigila sola).
  const horas = est.actualizado ? (Date.now() - new Date(est.actualizado)) / 36e5 : Infinity;
  const caidas = Object.entries(est.fuentes || {}).filter(([k, v]) => !v.ok && (D.planes.loterias[k] || k === 'baloto'))
    .map(([k]) => D.planes.loterias[k]?.nombre ?? 'Baloto');
  const partes = [];
  if (horas > 72) partes.push(`Los resultados no se actualizan desde hace ${Math.floor(horas / 24)} días.`);
  if (caidas.length) partes.push(`Fuente con problemas: ${caidas.join(', ')}. Sus últimos sorteos pueden faltar; el aviso ya se registró automáticamente.`);
  if (partes.length) { $('#alerta-datos').textContent = partes.join(' '); $('#alerta-datos').hidden = false; }
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
  pintarBolillero(); pintarUltimos(); pintarBilletera(); pintarBandeja();
  // Abre en un estado útil: el ejemplo real del piloto (un billete con premio pequeño).
  $('#codigo').value = '9 016 0004850 1048 367 02'; pintarPartes();
  $('#sello').hidden = false;
  revisarBillete({ loteria: 'medellin', sorteo: 4850, numero: '1048', serie: '367', fraccion: 2, fracciones: 2 });
})();
