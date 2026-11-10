#!/usr/bin/env python3
"""Recolector de la Lotería del Huila (sorteo ordinario, martes 10:30 p. m.).

Fuente: la API REST de WordPress del sitio oficial. Cada sorteo se publica como
una entrada de la categoría «Sorteos» (id 1), con el mayor y los 27 secos en tablas:
  https://loteriadelhuila.com/wp-json/wp/v2/posts?categories=1&per_page=100&after=...
Una sola consulta trae el último año completo (título + contenido), así que
`lista()` guarda el contenido en caché y `sorteo()` no vuelve a pedir nada.

Solo biblioteca estándar. Usa `pedir, lineas, fecha_es, pesos` de actualizar.py
(si no se encuentra, usa copias mínimas idénticas).
"""
import datetime as dt
import html
import json
import pathlib
import re
import sys
import time
import urllib.parse

RAIZ_REPO = pathlib.Path("/home/alejandro/Datos/Projects/herramientas/cayo-loterias/recolectores")
for _p in (pathlib.Path(__file__).resolve().parent, RAIZ_REPO):
    if (_p / "actualizar.py").exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
try:
    from actualizar import pedir, lineas, fecha_es, pesos, PAUSA  # noqa: F401
except ImportError:  # copias mínimas (mismo comportamiento que actualizar.py)
    import urllib.request
    PAUSA = 1.0
    AGENTE = "cayo-loterias/1.0 (+https://github.com/ale0009; recolector de resultados publicos)"
    MESES = {m: i for i, m in enumerate(
        "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}

    def pedir(url, datos=None):
        cuerpo = urllib.parse.urlencode(datos).encode() if datos else None
        req = urllib.request.Request(url, data=cuerpo, headers={"User-Agent": AGENTE})
        for intento in range(3):
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    return r.read().decode("utf-8", "ignore")
            except Exception:
                if intento == 2:
                    raise
                time.sleep(3 * (intento + 1))
        return ""

    def lineas(html_txt):
        t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", html_txt)
        t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
        return [l.strip() for l in t.split("\n") if l.strip()]

    def fecha_es(texto):
        m = re.search(r"(\d{1,2})\s*(?:de|/)\s*([A-Za-zñáéíóú]+)\s*(?:de|/)\s*(\d{4})", texto)
        if not m:
            return None
        return dt.date(int(m[3]), MESES[m[2].lower()], int(m[1])).isoformat()

    def pesos(texto):
        return int(re.sub(r"\D", "", texto) or 0)

HUI = "https://loteriadelhuila.com"
API = f"{HUI}/wp-json/wp/v2/posts"
CATEGORIA_SORTEOS = 1
GANAFIJO_BRUTO = 4_518_072  # plan 2025: 180 premios «Ganafijo sin serie» (el número en cualquier serie)
SECOS_ESPERADOS = 27        # 1×100 M + 1×60 M + 10×20 M + 15×10 M

_cache = {}  # sorteo -> {"fecha", "contenido", "titulo"}



NOMBRE = "Lotería del Huila"
FUENTE = "https://loteriadelhuila.com/category/sorteos/"

def _paginas(despues):
    """Entradas de la categoría Sorteos publicadas después de `despues` (AAAA-MM-DD)."""
    pagina = 1
    while True:
        q = urllib.parse.urlencode({
            "categories": CATEGORIA_SORTEOS, "per_page": 100, "page": pagina,
            "after": f"{despues}T00:00:00", "orderby": "date", "order": "desc",
            "_fields": "id,slug,date,title,content"})
        try:
            lote = json.loads(pedir(f"{API}?{q}"))
        except Exception:  # WordPress responde 400 cuando se pide una página que no existe
            if pagina > 1:
                return
            raise
        yield from lote
        if len(lote) < 100:
            return
        pagina += 1
        time.sleep(PAUSA)


def lista(desde=None):
    """[(sorteo, 'AAAA-MM-DD')] del sorteo más reciente hacia atrás (por defecto, ~1 año).

    La fecha sale del TÍTULO («sorteo 4780 – 3 de noviembre de 2026»), no de la fecha
    de publicación, que a veces es el día siguiente. Se eliminan entradas duplicadas
    (slugs «…-2») y se marcan los extraordinarios.
    """
    desde = desde or (dt.date.today() - dt.timedelta(days=380)).isoformat()
    # margen de 7 días: la entrada se publica el mismo día o uno después del sorteo
    despues = (dt.date.fromisoformat(desde) - dt.timedelta(days=7)).isoformat()
    vistos = {}
    for p in _paginas(despues):
        titulo = html.unescape(p["title"]["rendered"])
        m = re.search(r"sorteo\s+(\d+)", titulo, re.I)
        fecha = fecha_es(titulo) or p["date"][:10]
        if not m or fecha < desde:
            continue
        s = int(m[1])
        if "extraordinari" in titulo.lower() or s < 1000:
            print(f"  huila extraordinario {s} {fecha}: omitido", flush=True)
            continue
        if s in vistos:  # duplicado: se conserva el primero (el más reciente)
            continue
        vistos[s] = fecha
        _cache[s] = {"fecha": fecha, "titulo": titulo, "contenido": p["content"]["rendered"]}
    return sorted(vistos.items(), reverse=True)


def _contenido(s, fecha):
    if s in _cache:
        return _cache[s]["contenido"]
    # Sin caché: se busca la entrada por su slug (patrón estable desde 2025)
    d = dt.date.fromisoformat(fecha)
    mes = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()[d.month - 1]
    slug = f"resultado-loteria-del-huila-sorteo-{s}-{d.day}-de-{mes}-de-{d.year}"
    q = urllib.parse.urlencode({"slug": slug, "_fields": "title,content"})
    lote = json.loads(pedir(f"{API}?{q}"))
    time.sleep(PAUSA)
    if not lote:  # último recurso: búsqueda por texto dentro de la categoría
        q = urllib.parse.urlencode({"categories": CATEGORIA_SORTEOS, "search": f"sorteo {s}",
                                    "_fields": "title,content", "per_page": 10})
        lote = [p for p in json.loads(pedir(f"{API}?{q}"))
                if re.search(rf"sorteo\s+{s}\b", html.unescape(p["title"]["rendered"]), re.I)]
        time.sleep(PAUSA)
    return lote[0]["content"]["rendered"] if lote else None


def sorteo(s, fecha):
    """{"mayor": {...}, "secos": [{"numero","serie","valor"}], "ganafijo": {...}} o None."""
    c = _contenido(s, fecha)
    if not c:
        return None
    mayor, secos, ganafijo = None, [], None
    # cada bloque: <h3>TÍTULO</h3> <table>…<td>NNNN</td><td>SSS</td>…</table>
    for titulo, cuerpo in re.findall(r"(?s)<h3>(.*?)</h3>(.*?)(?=<h3>|$)", c):
        titulo = html.unescape(re.sub(r"<[^>]+>", "", titulo)).upper().strip()
        filas = re.findall(r"<td>\s*(\d{4})\s*</td>\s*<td>\s*(\d{3})\s*</td>", cuerpo)
        if titulo.startswith("PREMIO MAYOR"):
            if filas:
                mayor = {"numero": filas[0][0], "serie": filas[0][1]}
        elif "GANAFIJO" in titulo:
            if filas:  # vale en cualquier serie (la web la publica como «000»)
                ganafijo = {"numero": filas[0][0], "serie": None, "valor": GANAFIJO_BRUTO}
        elif "SECO" in titulo:
            v = re.search(r"SECO DE\s+([\d.]+)\s+MILLONES", titulo)
            valor = pesos(v[1]) * 1_000_000 if v else None
            secos += [{"numero": n, "serie": se, "valor": valor} for n, se in filas]
    if not mayor:
        return None
    if len(secos) != SECOS_ESPERADOS:
        print(f"  huila {s}: AVISO {len(secos)} secos (se esperaban {SECOS_ESPERADOS})", flush=True)
    r = {"mayor": mayor, "secos": secos}
    if ganafijo:
        r["ganafijo"] = ganafijo
    return r


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    L = lista("2025-11-01")
    print(f"{len(L)} sorteos desde 2025-11-01: {L[-1]} … {L[0]}")
    for s, f in L[:n]:
        r = sorteo(s, f)
        print(s, f, json.dumps(r, ensure_ascii=False))
