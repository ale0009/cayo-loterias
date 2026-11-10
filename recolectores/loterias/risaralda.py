#!/usr/bin/env python3
"""Lotería del Risaralda: resultados oficiales (solo biblioteca estándar).

Fuente: https://loteriadelrisaralda.com/sorteos/ (tabla con id interno, número, fecha y plan)
y https://loteriadelrisaralda.com/resultados?sorteo=<id interno> (mayor + todos los secos,
con valor bruto, número, serie y ciudad). Cloudflare solo inyecta su script pasivo
(/cdn-cgi/challenge-platform/scripts/jsd/main.js): no hay reto ni CAPTCHA.

lista()           → [(sorteo, 'AAAA-MM-DD')]
sorteo(s, fecha)  → {"mayor":{numero,serie}, "secos":[{numero,serie,valor}]} o None
"""
import html
import re
import time
import urllib.parse
import urllib.request

BASE = "https://loteriadelrisaralda.com"
AGENTE = "cayo-loterias/1.0 (+https://github.com/ale0009; recolector de resultados publicos)"
PAUSA = 1.0
_ids = {}  # sorteo → id interno



NOMBRE = "Lotería del Risaralda"
FUENTE = "https://loteriadelrisaralda.com/resultados"

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


def lista():
    h = pedir(f"{BASE}/sorteos/")
    filas = re.findall(r"<tr data-id='(\d+)'><td class=id>\d+</td><td class=numero>(\d+)</td>"
                       r"<td class=fecha>(\d{4}-\d{2}-\d{2})</td>", h)
    salida = []
    for i, s, f in filas:
        if int(s) < 1000:  # extraordinarios con numeración propia: otro plan
            continue
        _ids[int(s)] = i
        salida.append((int(s), f))
    return sorted(salida)


def sorteo(s, fecha=None):
    if not _ids:
        lista(); time.sleep(PAUSA)
    if s not in _ids:
        return None
    L = lineas(pedir(f"{BASE}/resultados?sorteo={_ids[s]}"))
    time.sleep(PAUSA)
    cab = next((n for n, l in enumerate(L) if l.startswith("RESULTADOS DEL SORTEO NÚMERO")), None)
    m = re.search(r"NÚMERO:\s*(\d+)\s+DEL\s+(\d{4}-\d{2}-\d{2})", L[cab]) if cab is not None else None
    if not m or int(m[1]) != s or (fecha and m[2] != fecha):
        return None
    premios = []
    for n in range(cab + 1, len(L) - 3):
        if L[n + 1].startswith("$") and re.fullmatch(r"\d{4}", L[n + 2]) and re.fullmatch(r"\d{1,3}", L[n + 3]):
            premios.append((re.sub(r"\s+", " ", L[n]).upper(), pesos(L[n + 1]), L[n + 2], L[n + 3].zfill(3)))
    mayor = next((p for p in premios if "MAYOR" in p[0]), None)
    if not mayor:
        return None
    # Todo lo que no es el mayor es un seco con nombre comercial («SECO COFRE DE DIAMANTES 3»,
    # «ESCALERA MILLONARIA»…); valor = bruto por billete.
    secos = [{"numero": n, "serie": se, "valor": v} for nom, v, n, se in premios if p_es_seco(nom)]
    return {"mayor": {"numero": mayor[2], "serie": mayor[3]}, "secos": secos}


def p_es_seco(nombre):
    return "MAYOR" not in nombre


if __name__ == "__main__":
    import json, sys
    L = lista()
    print(len(L), "sorteos; últimos:", L[-3:])
    for s in [int(x) for x in sys.argv[1:]] or [L[-1][0]]:
        print(s, json.dumps(sorteo(s), ensure_ascii=False)[:600])
