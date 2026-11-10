#!/usr/bin/env python3
"""Adaptador de la Lotería del Cauca para recolectores/actualizar.py (solo biblioteca estándar).

Fuente de resultados: el buscador «Buscar resultados» que enlaza la portada oficial
(https://www.loteriadelcauca.gov.co → botón «Buscar resultados»), alojado por su proveedor
de software Ingesoft: https://ingesoftingenieria.com/resultados/
  - GET  → muestra el último sorteo (mayor + secos; OJO: solo 34 de los 36 secos del acta).
  - POST intSorteo=<n> → muestra ese sorteo. Sin resultados: «No se encontraron resultados…».
Cada fila: PREMIO | VALOR («8000 Millones», a veces «300 Mllones») | SORTEO | NÚMERO | SERIE | DESPACHADO A | FECHA.
Las actas oficiales en loteriadelcauca.gov.co son PDF escaneados (imagen), no sirven sin OCR.
"""
import datetime as dt
import html
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:  # dentro del repo: recolectores/cauca.py junto a actualizar.py
    from actualizar import pedir, PAUSA  # noqa: F401  (lineas, fecha_es, pesos no hacen falta)
except ImportError:  # copia mínima para probarlo suelto
    import urllib.parse
    import urllib.request
    PAUSA = 1.0

    def pedir(url, datos=None):
        cuerpo = urllib.parse.urlencode(datos).encode() if datos else None
        req = urllib.request.Request(url, data=cuerpo, headers={
            "User-Agent": "cayo-loterias/1.0 (+https://github.com/ale0009; recolector de resultados publicos)"})
        for intento in range(3):
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    return r.read().decode("utf-8", "ignore")
            except Exception:
                if intento == 2:
                    raise
                time.sleep(3 * (intento + 1))
        return ""

CAU = "https://ingesoftingenieria.com/resultados/"
INICIO_ANIO = "2025-11-01"
SECOS_PLAN = 36  # plan vigente: 300, 200, 2×100, 3×50 y 29×10 millones



NOMBRE = "Lotería del Cauca"
FUENTE = "https://ingesoftingenieria.com/resultados/"

def _filas(h):
    """Filas de la tabla de resultados → listas de 7 celdas de texto."""
    filas = []
    for tr in re.findall(r"(?is)<tr>(.*?)</tr>", h):
        celdas = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"(?is)<td>(.*?)</td>", tr)]
        if len(celdas) == 7:
            filas.append(celdas)
    return filas


def _valor(texto):
    """'8000 Millones' / '300 Mllones' / '10 Millones' → pesos brutos."""
    m = re.match(r"\s*([\d.,]+)\s*M", texto)
    return int(re.sub(r"\D", "", m[1])) * 1_000_000 if m else None


def _ultimo():
    f = _filas(pedir(CAU))
    if not f:
        raise RuntimeError("Cauca: la página de resultados no trae tabla")
    return int(f[0][2]), f[0][6]


def fecha_estimada(s):
    """Sorteo ordinario semanal (sábado). Ancla comprobada: 2583 = 2025-11-01."""
    return (dt.date(2025, 11, 1) + dt.timedelta(weeks=int(s) - 2583)).isoformat()


def lista(desde=INICIO_ANIO):
    """[(sorteo, 'AAAA-MM-DD')] desde `desde` hasta hoy.

    El buscador no publica una lista de sorteos: se toma el último (GET) y se cuentan
    semanas hacia atrás (un sorteo ordinario cada sábado, numeración consecutiva:
    2583 = 2025-11-01, 2636 = 2026-11-07, 53 semanas exactas). La fecha es estimada;
    la real viene en sorteo()["fecha"].
    """
    s, f = _ultimo()
    hoy = dt.date.fromisoformat(f)
    out = []
    while True:
        out.append((s, hoy.isoformat()))
        s, hoy = s - 1, hoy - dt.timedelta(days=7)
        if hoy.isoformat() < desde or s < 1:
            break
    return out[::-1]


def sorteo(s, fecha=None):
    """{'fecha', 'mayor': {...}, 'secos': [...]} o None si no hay datos válidos."""
    if int(s) < 1000:  # extraordinarios (Súper Extra / Súper Millonario 00X): no están en este buscador
        return None
    filas = [f for f in _filas(pedir(CAU, {"intSorteo": str(s)})) if f[2] == str(s)]
    mayor = next((f for f in filas if f[0].lower() == "mayor"), None)
    if not mayor or not re.fullmatch(r"\d{4}", mayor[3]) or not re.fullmatch(r"\d{3}", mayor[4]):
        return None
    secos = [{"numero": f[3], "serie": f[4], "valor": _valor(f[1])}
             for f in filas if f[0].lower() == "seco" and re.fullmatch(r"\d{4}", f[3]) and re.fullmatch(r"\d{3}", f[4])]
    publicada = mayor[6] if re.fullmatch(r"20\d\d-\d\d-\d\d", mayor[6]) else None
    r = {"fecha": publicada or fecha or fecha_estimada(s), "mayor": {"numero": mayor[3], "serie": mayor[4]}, "secos": secos}
    avisos = []
    if len(secos) < SECOS_PLAN:  # el buscador omite siempre los secos 35 y 36 (ver cauca.md)
        avisos.append(f"faltan {SECOS_PLAN - len(secos)} de {SECOS_PLAN} secos: ver el acta {acta_url(s, r['fecha'])}")
    if not publicada:  # algunos sorteos vienen con FECHA «0000-00-00»
        avisos.append(f"fecha publicada «{mayor[6]}»: se usa la estimada {r['fecha']}")
    elif fecha and fecha != publicada:
        avisos.append(f"fecha estimada {fecha} distinta de la publicada {publicada}")
    if avisos:
        r["aviso"] = "; ".join(avisos)
    return r


MESES = "Enero Febrero Marzo Abril Mayo Junio Julio Agosto Septiembre Octubre Noviembre Diciembre".split()


def acta_url(s, fecha):
    """Acta oficial firmada (PDF escaneado, sin texto). Patrón comprobado con 2583, 2635 y 2636."""
    a, m, _ = fecha.split("-")
    return f"https://www.loteriadelcauca.gov.co/phocadownload/actaresultados/{a}/{MESES[int(m) - 1]}/Acta%20{s}.pdf"


if __name__ == "__main__":  # prueba: python3 cauca.py [sorteo ...]
    import json
    L = lista(); time.sleep(PAUSA)
    print(f"lista: {len(L)} sorteos, de {L[0]} a {L[-1]}")
    pedidos = [int(x) for x in sys.argv[1:]] or [s for s, _ in L[-3:]]
    fechas = dict(L)
    for s in pedidos:
        r = sorteo(s, fechas.get(s)); time.sleep(PAUSA)
        if not r:
            print(s, "→ None"); continue
        tot = sum(x["valor"] or 0 for x in r["secos"])
        print(f"{s} {r['fecha']} mayor {r['mayor']['numero']}-{r['mayor']['serie']} · {len(r['secos'])} secos · "
              f"suma secos ${tot:,}")
        print("   aviso:", r.get("aviso", "ninguno"))
        print("   primeros secos:", json.dumps(r["secos"][:3], ensure_ascii=False))
