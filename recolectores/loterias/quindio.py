#!/usr/bin/env python3
"""Lotería del Quindío: resultados oficiales (solo biblioteca estándar).

Fuente: https://www.loteriaquindio.com.co/index.php/consultar_sorteo
La página es Laravel: el <select name="numero_sorteo"> usa un id interno
(value=995 → «Sorteo 3023»). Para ver otro sorteo hay que hacer POST con el
_token CSRF y la cookie de sesión de la primera visita (no hay CAPTCHA en ese
formulario; el GET con ?numero_sorteo= se ignora).
La tabla trae: ITEM · PREMIO · VALOR (bruto) · RESULTADO «NNNN-S» · ENVIADO A.
La serie viene sin ceros a la izquierda («4879-30» → serie 030).

lista()            → [(sorteo, 'AAAA-MM-DD')]  (corte por bisección; fechas intermedias interpoladas)
sorteo(s, fecha)   → {"fecha", "mayor":{numero,serie}, "secos":[{numero,serie,valor}]} o None
"""
import datetime as dt
import html
import http.cookiejar
import re
import time
import urllib.parse
import urllib.request

URL = "https://www.loteriaquindio.com.co/index.php/consultar_sorteo"
POST = "https://www.loteriaquindio.com.co/consultar_sorteo"
AGENTE = "cayo-loterias/1.0 (+https://github.com/ale0009; recolector de resultados publicos)"
PAUSA = 1.0

_jar = http.cookiejar.CookieJar()
_abridor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))
_estado = {}  # token, ids {sorteo: id interno}, pagina inicial



NOMBRE = "Lotería del Quindío"
FUENTE = "https://www.loteriaquindio.com.co/index.php/consultar_sorteo"

def pedir(url, datos=None):
    cuerpo = urllib.parse.urlencode(datos).encode() if datos else None
    req = urllib.request.Request(url, data=cuerpo, headers={"User-Agent": AGENTE, "Referer": URL})
    for intento in range(3):
        try:
            with _abridor.open(req, timeout=40) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            if intento == 2:
                raise
            time.sleep(3 * (intento + 1))
    return ""


def lineas(h):
    t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", h)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    return [l.strip() for l in t.split("\n") if l.strip()]


def _portada():
    if not _estado:
        h = pedir(URL)
        _estado["token"] = re.search(r'name="_token" value="([^"]+)"', h)[1]
        _estado["ids"] = {int(s): v for v, s in re.findall(
            r'<option value="(\d+)"[^>]*>\s*Sorteo (\d+)\s*<', h)}
        _estado["portada"] = h
    return _estado


def _tabla(h):
    """Devuelve (sorteo, fecha, filas[(premio, valor, numero, serie)])."""
    L = lineas(h)
    i = next((n for n, l in enumerate(L) if l == "Resultado Sorteo"), None)
    if i is None:
        return None
    m = re.match(r"(\d+) del (\d{4}-\d{2}-\d{2})", L[i + 1])
    if not m:
        return None
    filas = []
    for n in range(i + 2, len(L) - 2):
        r = re.fullmatch(r"(\d{4})-(\d{1,3})", L[n + 2])
        if re.fullmatch(r"[\d.]+", L[n + 1]) and r and not L[n].isdigit():
            filas.append((L[n], int(L[n + 1].replace(".", "")), r[1], r[2].zfill(3)))
    return int(m[1]), m[2], filas


def _pagina(s):
    """Tabla de un sorteo (con caché para no pedirla dos veces)."""
    e = _portada()
    cache = e.setdefault("cache", {})
    if s not in cache:
        h = pedir(POST, {"_token": e["token"], "numero_sorteo": e["ids"][s], "numero": "", "serie": ""})
        time.sleep(PAUSA)
        t = _tabla(h)
        cache[s] = t if t and t[0] == s else None
    return cache[s]


def lista(desde="2025-11-01"):
    """Sorteos desde `desde`. Las fechas no están en el <select>: se busca el corte por
    bisección (≈10 consultas con fecha real) y las fechas intermedias se interpolan;
    sorteo() devuelve siempre la fecha real en la clave "fecha"."""
    e = _portada()
    t = _tabla(e["portada"])
    nums = sorted(s for s in e["ids"] if s >= 1000)
    conocidas = {t[0]: t[1]} if t else {}
    lo, hi = 0, len(nums) - 1
    while lo < hi:  # primer sorteo con fecha >= desde
        mid = (lo + hi) // 2
        p = _pagina(nums[mid])
        if p is None:  # página vacía: se trata como antigua
            lo = mid + 1
            continue
        conocidas[nums[mid]] = p[1]
        if p[1] >= desde:
            hi = mid
        else:
            lo = mid + 1
    elegidos = nums[lo:]
    anclas = sorted((s, dt.date.fromisoformat(f)) for s, f in conocidas.items())
    salida = []
    for s in elegidos:
        if s in conocidas:
            salida.append((s, conocidas[s])); continue
        a = max((x for x in anclas if x[0] < s), default=anclas[0])
        b = min((x for x in anclas if x[0] > s), default=anclas[-1])
        if a[0] == b[0]:
            f = a[1]
        else:
            f = a[1] + (b[1] - a[1]) * (s - a[0]) / (b[0] - a[0])
        salida.append((s, max(f, dt.date.fromisoformat(desde)).isoformat()))
    return salida


def sorteo(s, fecha=None):
    e = _portada()
    if s not in e["ids"]:
        return None
    t = _pagina(s)
    if not t or not t[2]:
        return None
    filas = t[2]
    mayor = next((f for f in filas if "MAYOR" in f[0].upper()), None)
    if not mayor:
        return None
    secos = [{"numero": n, "serie": se, "valor": v} for p, v, n, se in filas
             if "SECO" in p.upper()]
    return {"fecha": t[1], "mayor": {"numero": mayor[2], "serie": mayor[3]}, "secos": secos}


if __name__ == "__main__":
    import json, sys
    L = lista()
    print(len(L), "sorteos; últimos:", L[-3:])
    for s in [int(x) for x in sys.argv[1:]] or [L[-1][0]]:
        print(s, json.dumps(sorteo(s), ensure_ascii=False)[:600])
