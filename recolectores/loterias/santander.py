#!/usr/bin/env python3
"""Adaptador de la Lotería de Santander para recolectores/actualizar.py.

Fuentes (descubiertas leyendo el JS del sitio oficial, que es Astro + WordPress sin cabeza):
- Resultados: la propia web oficial (/resultados/) solo muestra una IMAGEN GIF por sorteo
  (https://www.loteriasantander.gov.co/image/sorteo/sorteoNNNN.gif). Los datos en texto los
  publica la lotería en Datos Abiertos Colombia (Socrata), conjunto 4zwu-ra3f
  «Resultados por sorteo Loteria Santander»: una fila por premio {premio, sorteo, numero, serie}.
  La web oficial consulta ese mismo conjunto para saber cuál es el último sorteo.
- Calendario (sorteo → fecha): lista fija embebida en el JS del componente Resultados
  (/_astro/Resultados.<hash>.js), de 2003 a 2027. El conjunto de datos NO trae fecha.

Solo biblioteca estándar. Pausa ≥ 1 s entre consultas.
"""
import datetime as dt
import re
import sys
import time
import urllib.parse

try:  # dentro del repo: recolectores/santander.py junto a actualizar.py
    from actualizar import pedir, PAUSA
except ImportError:  # copia mínima para probarlo suelto
    sys.path.insert(0, "/home/alejandro/Datos/Projects/herramientas/cayo-loterias/recolectores")
    from actualizar import pedir, PAUSA

WEB = "https://www.loteriasantander.gov.co"
SODA = "https://www.datos.gov.co/resource/4zwu-ra3f.json"
FUENTE_RESULTADOS = "https://www.datos.gov.co/Comercio-Industria-y-Turismo/Resultados-por-sorteo-Loteria-Santander/4zwu-ra3f"
ANCLA = (5095, dt.date(2026, 11, 6))  # para el plan B del calendario (viernes semanales)



NOMBRE = "Lotería de Santander"
FUENTE = "https://www.datos.gov.co/resource/4zwu-ra3f"

def _soda(params):
    import json
    url = SODA + "?" + urllib.parse.urlencode(params, safe="$(),'=<>!")
    return json.loads(pedir(url))


def ultimo_publicado():
    """Mayor número de sorteo con datos en Datos Abiertos (igual que hace la web oficial)."""
    r = _soda({"$select": "max(sorteo) as s", "$where": "sorteo != '5'"})
    return int(r[0]["s"]) if r and r[0].get("s") else None


def _calendario():
    """[(sorteo, fecha)] leídos del JS oficial; si cambia el formato, plan B: viernes semanales."""
    try:
        h = pedir(f"{WEB}/resultados/")
        m = re.search(r'component-url="(/_astro/Resultados\.[^"]+\.js)"', h)
        time.sleep(PAUSA)
        js = pedir(WEB + m[1]) if m else ""
        cal = [(int(s), f) for s, f in re.findall(r"sorteo:`(\d+)`,fecha:`(\d{4}-\d{2}-\d{2})`", js)]
        if len(cal) > 50:
            return cal
    except Exception as e:  # noqa: BLE001
        print(f"  santander: calendario oficial no disponible ({e}); uso viernes semanales", flush=True)
    s0, f0 = ANCLA
    return [(s0 + k, (f0 + dt.timedelta(weeks=k)).isoformat()) for k in range(-60, 60)]


def lista(desde=None):
    """Sorteos ya jugados y publicados desde `desde` (por defecto, los últimos ~380 días)."""
    desde = desde or (dt.date.today() - dt.timedelta(days=380)).isoformat()
    cal = _calendario()
    time.sleep(PAUSA)
    tope = ultimo_publicado()
    hoy = dt.date.today().isoformat()
    return sorted((s, f) for s, f in cal if f >= desde and f <= hoy and (tope is None or s <= tope))


def _valor(premio):
    """'SECO 10 MILLONES' / 'SECO 10 MM' / 'SECO DE 10 M' → 10000000 (bruto)."""
    m = re.search(r"(\d+)\s*(?:MILLONES|MM|M)\b", premio.upper())
    return int(m[1]) * 1_000_000 if m else None


def sorteo(s, fecha=None):
    """{"mayor": {...}, "secos": [...]} del sorteo `s` o None si no está publicado.

    Ignora filas promocionales (p. ej. «GANA CON SERIE» en el 5090) y quita filas
    repetidas (el 5078 aparece triplicado en el conjunto de datos).
    """
    filas = _soda({"$where": f"sorteo = '{int(s)}'", "$order": ":id", "$limit": "1000"})
    vistos, mayores, secos = set(), [], []
    for f in filas:
        premio = f.get("premio", "").strip().upper()
        clave = (premio, f.get("numero"), f.get("serie"))
        if clave in vistos:
            continue
        vistos.add(clave)
        num = (f.get("numero") or "").strip().zfill(4)
        ser = (f.get("serie") or "").strip().zfill(3)
        if not re.fullmatch(r"\d{4}", num) or not re.fullmatch(r"\d{3}", ser):
            continue
        if premio == "PREMIO MAYOR":
            mayores.append({"numero": num, "serie": ser})
        elif premio.startswith("SECO"):
            secos.append({"numero": num, "serie": ser, "valor": _valor(premio)})
    if len(mayores) != 1:
        return None
    secos.sort(key=lambda x: -(x["valor"] or 0))  # orden estable: de mayor a menor valor
    return {"mayor": mayores[0], "secos": secos}


if __name__ == "__main__":  # prueba: python3 santander.py [n]
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    L = lista("2025-11-01")
    print(f"lista(): {len(L)} sorteos, de {L[0]} a {L[-1]}")
    for s, f in L[-n:]:
        time.sleep(PAUSA)
        r = sorteo(s, f)
        if not r:
            print(s, f, "sin datos"); continue
        tot = {}
        for x in r["secos"]:
            tot[x["valor"]] = tot.get(x["valor"], 0) + 1
        print(s, f, "mayor", r["mayor"], "| secos:", len(r["secos"]),
              {f"{k // 1_000_000}M": v for k, v in tot.items()}, "| primeros:", r["secos"][:2])
