#!/usr/bin/env python3
"""Lotería del Tolima: resultados oficiales (solo biblioteca estándar).

Fuente: https://loteriadeltolima.com/resultados/?sorteo=N  (HTML con mayor y todos los secos)
Fechas: https://loteriadeltolima.com/historico/ (lista «SORTEO 4144 del 18-11-2025» o
«SORTEO 4194 NOV 03 DEL 2026»); la cabecera de cada resultado trae la fecha real
(«MARTES, 18 DE NOVIEMBRE DE 2025»), que sorteo() devuelve en la clave "fecha".
Cloudflare solo inyecta su script pasivo (/cdn-cgi/challenge-platform/scripts/jsd/main.js):
no hay reto «Just a moment» ni CAPTCHA. robots.txt: Disallow vacío.

El bloque «EL TRAVIESO DEL TOLIMA» (valor 1.084.337, serie «000») es un premio que juega
SIN serie (paga 4 cifras en cualquiera de las 280 series): no se mezcla con los secos y se
devuelve aparte en "especiales".

lista()           → [(sorteo, 'AAAA-MM-DD')]
sorteo(s, fecha)  → {"fecha", "mayor":{numero,serie}, "secos":[{numero,serie,valor}], "especiales":[...]} o None
"""
import datetime as dt
import html
import re
import time
import urllib.parse
import urllib.request

BASE = "https://loteriadeltolima.com"
AGENTE = "cayo-loterias/1.0 (+https://github.com/ale0009; recolector de resultados publicos)"
PAUSA = 1.0
MESES = {m: i for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}
CORTOS = {m[:3]: i for m, i in MESES.items()}



NOMBRE = "Lotería del Tolima"
FUENTE = "https://loteriadeltolima.com/resultados/"

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


def lineas(h):
    t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", h)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    return [l.strip() for l in t.split("\n") if l.strip()]


def pesos(t):
    return int(re.sub(r"\D", "", t) or 0)


def _fecha_hist(txt):
    """'18-11-2025' · '9-01-2024' · 'NOV 03 DEL 2026' · 'SEPTIEMBRE 07 DEL 2026' → ISO."""
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})", txt)
    if m:
        return dt.date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    m = re.search(r"([A-Za-zÁÉÍÓÚáéíóú]+)\.?\s+(\d{1,2})\s+DEL?\s+(\d{4})", txt, re.I)
    if m and m[1][:3].lower() in CORTOS:
        return dt.date(int(m[3]), CORTOS[m[1][:3].lower()], int(m[2])).isoformat()
    return None


def lista():
    # Números válidos: el <select name='sorteo'> de /resultados/ (incluye el último sorteo).
    h = pedir(f"{BASE}/resultados/")
    i = h.find("<form method='GET'>")
    nums = sorted({int(v) for v in re.findall(r"value='(\d+)'", h[i:i + 40000]) if int(v) >= 1000})
    # Cabecera de la portada: fecha real del último sorteo.
    L = lineas(h)
    ult = None
    k = next((n for n, l in enumerate(L) if l.startswith("RESULTADOS SORTEO")), None)
    if k is not None:
        ult = (pesos(L[k]), _fecha_larga(L[k + 1]))
    time.sleep(PAUSA)
    # Fechas del histórico (texto libre con erratas: se toma lo que se pueda leer).
    hist = {}
    texto = " ".join(lineas(pedir(f"{BASE}/historico/")))
    for m in re.finditer(r"SORTEO\s*(\d{4})\s*((?:del\s*)?\d{1,2}-\d{1,2}-\d{4}|[A-Za-z]+\.?\s+\d{1,2}\s+DEL?\s+\d{4})",
                         texto, re.I):
        f = _fecha_hist(m[2])
        if f:
            hist.setdefault(int(m[1]), f)
    if ult and ult[1]:
        hist[ult[0]] = ult[1]
    salida, previa = [], None
    for s in nums:
        f = hist.get(s)
        if not f and previa:  # sin fecha publicada: semana siguiente a la anterior (sorteo() trae la real)
            f = (dt.date.fromisoformat(previa) + dt.timedelta(days=7)).isoformat()
        if f:
            salida.append((s, f))
            previa = f
    return salida


def _fecha_larga(t):
    m = re.search(r"(\d{1,2}) DE ([A-ZÁÉÍÓÚ]+) DE (\d{4})", t.upper())
    if not m or m[2].lower() not in MESES:
        return None
    return dt.date(int(m[3]), MESES[m[2].lower()], int(m[1])).isoformat()


def sorteo(s, fecha=None):
    L = lineas(pedir(f"{BASE}/resultados/?sorteo={s}"))
    time.sleep(PAUSA)
    k = next((n for n, l in enumerate(L) if l.startswith("RESULTADOS SORTEO")), None)
    if k is None or pesos(L[k]) != s:
        return None
    fecha_real = _fecha_larga(L[k + 1])
    bloques, actual = [], None
    n = k + 2
    while n < len(L):
        l = L[n]
        if l in ("Contáctanos", "Contactanos"):
            break
        if l == "NÚMERO" and n + 3 < len(L) and L[n + 2] == "SERIE":
            if actual:
                actual["pares"].append((L[n + 1], L[n + 3]))
            n += 4
            continue
        if l.startswith("$"):  # «$ 270» + «MILLONES»
            if actual:
                actual["valor"] = pesos(l) * (1_000_000 if n + 1 < len(L) and L[n + 1] == "MILLONES" else 1)
            n += 1
            continue
        if re.fullmatch(r"[\d.]+", l) and actual and actual["valor"] is None:  # «1084337.00»
            actual["valor"] = int(float(l))
            n += 1
            continue
        if l == "MILLONES":
            n += 1
            continue
        actual = {"nombre": l, "valor": None, "pares": []}
        bloques.append(actual)
        n += 1
    if not bloques or "MAYOR" not in bloques[0]["nombre"] or not bloques[0]["pares"]:
        return None
    mayor = bloques[0]["pares"][0]
    secos, especiales = [], []
    for b in bloques[1:]:
        for num, serie in b["pares"]:
            if "TRAVIESO" in b["nombre"].upper():
                especiales.append({"nombre": b["nombre"], "numero": num, "valor": b["valor"], "sin_serie": True})
            else:
                secos.append({"numero": num, "serie": serie, "valor": b["valor"]})
    return {"fecha": fecha_real or fecha, "mayor": {"numero": mayor[0], "serie": mayor[1]},
            "secos": secos, "especiales": especiales}


if __name__ == "__main__":
    import json, sys
    L = lista()
    print(len(L), "sorteos; últimos:", L[-3:])
    for s in [int(x) for x in sys.argv[1:]] or [L[-1][0]]:
        print(s, json.dumps(sorteo(s), ensure_ascii=False)[:600])
