#!/usr/bin/env python3
"""Extra de Colombia (Sorteo Extraordinario de Colombia): resultados oficiales (solo biblioteca estándar).

Lista:     https://extradecolombia.com.co/sorteos/  (número · nombre · fecha ISO · premio mayor)
Resultado: https://extradecolombia.com.co/resultados/?CodigoSorteo=N
           (mayor, secos «1 Seco de 20 Millones» + 4 cifras sueltas + «Serie | 204», bonos,
            recambio y la tabla de APROXIMACIONES con valores NETOS de ese sorteo).
Cloudflare solo inyecta su script pasivo (/cdn-cgi/challenge-platform/scripts/jsd/main.js);
el «captcha» que aparece es el estilo del reCAPTCHA del formulario de contacto. Sin reto.
robots.txt: solo bloquea /wp-admin/.

Se omiten los «Sorteo 00NN - Convenio Lotería X» (código 2026MMDD00NN): son extraordinarios
en convenio con otras loterías, con otro plan. Los BONO (casa, carro, viaje, moto) y el
RECAMBIO GANADOR son lanzamientos adicionales del plan de incentivos: van en "especiales".

lista()           → [(sorteo, 'AAAA-MM-DD')]
sorteo(s, fecha)  → {"mayor":{numero,serie}, "secos":[{numero,serie,valor}],
                     "especiales":[...], "aproximaciones":{nombre: neto}} o None
"""
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://extradecolombia.com.co"
AGENTE = "cayo-loterias/1.0 (+https://github.com/ale0009; recolector de resultados publicos)"
PAUSA = 1.0



NOMBRE = "Extra de Colombia"
FUENTE = "https://extradecolombia.com.co/resultados/"

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
    L = lineas(pedir(f"{BASE}/sorteos/"))
    salida = []
    for n in range(len(L) - 2):
        if re.fullmatch(r"\d{4}", L[n]) and L[n + 1].startswith(f"Sorteo {L[n]}") \
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", L[n + 2]):
            salida.append((int(L[n]), L[n + 2]))
    return sorted(set(salida))


def _digitos(L, n):
    """4 cifras sueltas a partir de L[n] → ('0764', n+4) o (None, n)."""
    d = L[n:n + 4]
    if len(d) == 4 and all(re.fullmatch(r"\d", x) for x in d):
        return "".join(d), n + 4
    return None, n


def _serie(L, n):
    """'Serie' + '320'  o  'Serie | 043'  o  'Serie | N/A' → ('320', n')."""
    if L[n] == "Serie" and n + 1 < len(L) and re.fullmatch(r"\d{1,3}", L[n + 1]):
        return L[n + 1].zfill(3), n + 2
    m = re.fullmatch(r"Serie\s*\|\s*(\S+)", L[n])
    if m:
        return (m[1].zfill(3) if m[1].isdigit() else None), n + 1
    return None, n


def sorteo(s, fecha=None):
    try:
        h = pedir(f"{BASE}/resultados/?CodigoSorteo={s}")
    except urllib.error.HTTPError as e:  # código inexistente → el sitio responde 500
        if e.code == 500:
            return None
        raise
    finally:
        time.sleep(PAUSA)
    if not re.search(rf'<option value="{s}"\s+selected', h):  # la página mostró otro sorteo
        return None
    L = lineas(h)
    i = next((n for n, l in enumerate(L) if re.fullmatch(r"Premio Mayor [\d.]+ Millones", l)), None)
    if i is None:
        return None
    num, k = _digitos(L, i + 1)
    serie, k = _serie(L, k)
    if not num or not serie:
        return None
    secos, especiales = [], []
    n = k
    while n < len(L) and L[n] != "APROXIMACIONES":
        m = re.fullmatch(r"\d+ Seco de ([\d.]+) Millones", L[n])
        nombre = L[n]
        d, k2 = _digitos(L, n + 1)
        if d is None:  # recambio: 2 cifras
            if n + 2 < len(L) and all(re.fullmatch(r"\d", x) for x in L[n + 1:n + 3]):
                d, k2 = "".join(L[n + 1:n + 3]), n + 3
        if d is not None and k2 < len(L):
            se, k3 = _serie(L, k2)
            if m:
                secos.append({"numero": d, "serie": se, "valor": int(m[1].replace(".", "")) * 1_000_000})
            else:
                especiales.append({"nombre": nombre, "numero": d, "serie": se})
            n = k3 if k3 > k2 else k2
            continue
        n += 1
    aprox = {}
    if n < len(L):
        j = n + 1
        while j + 1 < len(L) and L[j] != "¿Necesitas más Información?":
            if L[j + 1].startswith("$"):
                aprox[re.sub(r"\s+", " ", L[j]).upper()] = pesos(L[j + 1])
                j += 3
                continue
            j += 1
    return {"mayor": {"numero": num, "serie": serie}, "secos": secos,
            "especiales": especiales, "aproximaciones": aprox}


if __name__ == "__main__":
    import json, sys
    L = lista()
    print(len(L), "sorteos; últimos:", L[-3:])
    for s in [int(x) for x in sys.argv[1:]] or [L[-1][0]]:
        print(s, json.dumps(sorteo(s), ensure_ascii=False)[:900])
