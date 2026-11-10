#!/usr/bin/env python3
"""Adaptador de la Lotería del Valle (Beneficencia del Valle del Cauca) para «¿Cayó?».

Fuente: la tabla pública https://loteriadelvalle.com/resultado_v2/vistas/tabla.php, que
pide sus datos por POST a resultado_v2/controladores/revisar_controlador.php:
  datos=tabla_normal                  → JSON con TODOS los sorteos desde 4695 (2023):
                                        sorteo, fecha y premio mayor (número + serie).
  datos=complemento_secos&sorteo=N    → JSON con los secos del sorteo N: número, serie,
                                        "seco" (código de categoría 2..6) y posición.
El valor de cada seco NO viene en el JSON: la propia página lo deduce del código "seco"
según el rango del sorteo (js/tabla.js). Aquí se replica esa tabla y se comprobó contra el
PDF oficial (resultado_v2/vistas/pdfexport.php, sorteopdf=N).

Los sorteos con número < 1000 son extraordinarios (otro plan de premios): lista() los omite.
Solo biblioteca estándar.
"""
import json
import pathlib
import re
import sys
import time

try:  # dentro del repo: reutiliza las utilidades de recolectores/actualizar.py
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from actualizar import pedir, PAUSA  # noqa: F401  (lineas, fecha_es y pesos no hacen falta: la fuente es JSON)
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

VALLE = "https://loteriadelvalle.com"
CTRL = f"{VALLE}/resultado_v2/controladores/revisar_controlador.php"
M = 1_000_000

# Valor BRUTO de cada seco según su código, copiado de resultado_v2/vistas/js/tabla.js.
# Plan vigente (sorteo >= 4766): 1×500M, 2×100M, 3×60M, 1×40M, 25×30M = 32 secos.
PLAN_ACTUAL = {"2": 500 * M, "3": 100 * M, "4": 60 * M, "5": 40 * M}, 30 * M
PLAN_4776 = {"2": 500 * M, "3": 50 * M, "4": 30 * M, "5": 20 * M}, 15 * M
PLAN_4695 = {"2": 240 * M, "3": 120 * M, "4": 30 * M, "5": 15 * M}, 12 * M
PLAN_4749 = {"2": 300 * M, "3": 100 * M, "4": 70 * M, "5": 49 * M}, 12 * M  # sorteos 4749 y 4762



NOMBRE = "Lotería del Valle"
FUENTE = "https://loteriadelvalle.com/resultado_v2/vistas/tabla.php"

def valor_seco(sorteo, codigo):
    if sorteo < 1000:
        return None  # extraordinario: no se soporta
    if sorteo == 4776:
        tabla, otro = PLAN_4776
    elif sorteo >= 4766:
        tabla, otro = PLAN_ACTUAL
    elif sorteo in (4749, 4762):
        tabla, otro = PLAN_4749
    elif sorteo >= 4695:
        tabla, otro = PLAN_4695
    else:
        return None
    return tabla.get(str(codigo).strip(), otro)


_tabla = None


def _tabla_normal():
    """Una sola consulta para todos los mayores; se guarda en memoria durante la ejecución."""
    global _tabla
    if _tabla is None:
        _tabla = json.loads(pedir(CTRL, {"datos": "tabla_normal"}).strip().lstrip("﻿"))
        time.sleep(PAUSA)
    return _tabla


def lista(incluir_extraordinarios=False):
    """[(sorteo, 'AAAA-MM-DD')] de todos los sorteos publicados (desde 2023), del más viejo al más nuevo."""
    out = []
    for x in _tabla_normal():
        s = int(x["sorteo"])
        if s < 1000 and not incluir_extraordinarios:
            continue
        out.append((s, str(x["fecha"])[:10]))
    return sorted(out, key=lambda t: t[1])


def sorteo(s, fecha=None):
    s = int(s)
    if s < 1000:
        return None  # extraordinario
    fila = next((x for x in _tabla_normal() if int(x["sorteo"]) == s), None)
    if not fila or (fecha and str(fila["fecha"])[:10] != fecha):
        return None
    cuerpo = pedir(CTRL, {"datos": "complemento_secos", "sorteo": str(s)}).strip().lstrip("﻿")
    time.sleep(PAUSA)
    if not cuerpo:
        return None  # sorteo aún sin secos publicados
    secos = sorted(json.loads(cuerpo), key=lambda x: (int(x["seco"]), int(x["posicion"])))
    mayor = fila["mayor"]
    if not re.fullmatch(r"\d{4}", mayor["resultado"]) or not re.fullmatch(r"\d{3}", mayor["serie"]):
        return None
    return {"mayor": {"numero": mayor["resultado"], "serie": mayor["serie"]},
            "secos": [{"numero": x["resultado"], "serie": x["serie"], "valor": valor_seco(s, x["seco"])}
                      for x in secos if str(x["seco"]).strip() != "1"]}


if __name__ == "__main__":  # prueba: python3 valle.py [n_sorteos]
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    L = [t for t in lista() if t[0] >= 4821]  # desde 2025-11-01
    print(f"{len(L)} sorteos ordinarios desde 2025-11-01: {L[0]} … {L[-1]}")
    for s, f in L[-n:]:
        r = sorteo(s, f)
        tot = sum(x["valor"] or 0 for x in r["secos"]) if r else 0
        print(s, f, r["mayor"] if r else None, f"{len(r['secos'])} secos, total {tot:,}" if r else "")
        if r:
            print("   ", r["secos"][:3], "…")
