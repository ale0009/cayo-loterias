// Selector de tema: auto → claro → oscuro. Se recuerda en este navegador si se puede.
const ORDEN = ['auto', 'claro', 'oscuro'];
const ATRIB = { claro: 'light', oscuro: 'dark' };

function leer() {
  try { return localStorage.getItem('cayo-tema') || 'auto'; } catch { return 'auto'; }
}
function aplicar(t) {
  const r = document.documentElement;
  if (ATRIB[t]) r.dataset.theme = ATRIB[t]; else delete r.dataset.theme;
}

export function iniciarTema(boton) {
  let actual = leer();
  aplicar(actual);
  if (!boton) return;
  const pintar = () => { boton.textContent = `Tema: ${actual}`; };
  pintar();
  boton.addEventListener('click', () => {
    actual = ORDEN[(ORDEN.indexOf(actual) + 1) % ORDEN.length];
    aplicar(actual);
    try { localStorage.setItem('cayo-tema', actual); } catch { /* sin almacenamiento: no pasa nada */ }
    pintar();
  });
}
