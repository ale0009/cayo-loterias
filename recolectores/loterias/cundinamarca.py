#!/usr/bin/env python3
"""Adaptador de la Lotería de Cundinamarca para recolectores/actualizar.py.

FUENTE OFICIAL: la página «Actas de Resultados» (https://www.loteriadecundinamarca.com.co/actas-resultados)
enlaza un PDF por sorteo en Azure Blob:
    https://plataformaweb.blob.core.windows.net/files/results-records/<año>/<sorteo>.pdf
Ese PDF es un ESCANEO (CamScanner): no trae texto, solo imágenes JPEG. Por eso este módulo
necesita, además de la biblioteca estándar de Python, dos programas externos:
    pdfimages  (paquete poppler-utils)   -> saca las imágenes del PDF sin recomprimirlas
    tesseract  (tesseract-ocr + -spa)    -> OCR (reconocimiento óptico de caracteres)
En GitHub Actions (ubuntu-latest):  sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-spa

La lista de sorteos no existe como dato: está escrita dentro del JavaScript de la web (Angular).
lista() descarga la portada, encuentra el «chunk» JS del componente ResultsRecordsComponent y lee
de ahí los enlaces. Las fechas de lista() son ESTIMADAS (lunes, cadencia semanal); sorteo()
devuelve la fecha real leída en el acta («En Bogotá, D.C. a los 9 del mes de Noviembre de 2026»).

Uso de prueba:  python3 cundinamarca.py 4828 4827
"""
import datetime as dt
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

try:  # dentro del repo: recolectores/actualizar.py
    import actualizar as a
    pedir, fecha_es, PAUSA, AGENTE = a.pedir, a.fecha_es, a.PAUSA, a.AGENTE
except ImportError:  # copia mínima para probarlo suelto
    AGENTE = "cayo-loterias/1.0 (+https://github.com/ale0009; recolector de resultados publicos)"
    PAUSA = 1.0
    MESES = {m: i for i, m in enumerate(
        "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}

    def pedir(url, datos=None):
        req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode("utf-8", "ignore")

    def fecha_es(texto):
        m = re.search(r"(\d{1,2})\s*(?:de|/)\s*([A-Za-zñáéíóú]+)\s*(?:de|/)\s*(\d{4})", texto)
        if not m or m[2].lower() not in MESES:
            return None
        return dt.date(int(m[3]), MESES[m[2].lower()], int(m[1])).isoformat()

WEB = "https://www.loteriadecundinamarca.com.co"
BLOB = "https://plataformaweb.blob.core.windows.net/files/results-records"
# Ancla para estimar fechas: sorteo 4828 = lunes 9 de noviembre de 2026 (leído en su acta).
ANCLA = (4828, dt.date(2026, 11, 9))
# Plan vigente (Acuerdo 08 de 2023): 61 secos. Valor bruto por billete -> cantidad.
SECOS_ESPERADOS = {500_000_000: 1, 300_000_000: 1, 100_000_000: 1, 50_000_000: 3, 20_000_000: 20, 10_000_000: 35}

_URLS = {}  # sorteo -> URL del PDF, llenado por lista()



NOMBRE = "Lotería de Cundinamarca"
FUENTE = "https://www.loteriadecundinamarca.com.co/actas-resultados"
OCR = True  # lee imágenes: necesita tesseract (y poppler o Pillow)

def _bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception:
            if intento == 2:
                raise
            time.sleep(3 * (intento + 1))


def _fecha_estimada(s):
    return (ANCLA[1] - dt.timedelta(weeks=ANCLA[0] - s)).isoformat()


def actas():
    """[(etiqueta, url)] tal como los publica la página de Actas de Resultados (2 consultas)."""
    portada = pedir(WEB + "/")
    main = re.search(r'src="(main-[A-Z0-9]+\.js)"', portada)[1]
    time.sleep(PAUSA)
    js = pedir(f"{WEB}/{main}")
    chunk = re.search(r'import\("\./(chunk-[A-Z0-9]+\.js)"\)\.then\(\w+=>\w+\.ResultsRecordsComponent\)', js)[1]
    time.sleep(PAUSA)
    js = pedir(f"{WEB}/{chunk}")
    return re.findall(r'label:"([^"]+)",url:"(https://[^"]+\.pdf)"', js)


def lista():
    """[(sorteo, 'AAAA-MM-DD' estimada)] de los sorteos ORDINARIOS con acta publicada.
    Se omiten los extraordinarios (etiquetas «Extra», «18», «LNCR10»...) y los enlaces
    de relleno «test.pdf» (la web los usa para todo 2025)."""
    vistos = {}
    for etiqueta, url in actas():
        m = re.fullmatch(r"Acta Sorteo (\d{4})\.pdf", etiqueta)
        if not m or not url.endswith(f"/{m[1]}.pdf"):
            continue
        s = int(m[1])
        _URLS[s] = url
        vistos[s] = _fecha_estimada(s)
    # Huecos en la numeración (p. ej. 4806 no está enlazado pero su PDF sí existe): se añaden
    # como candidatos con la URL deducida; sorteo() devuelve None si el PDF no existe (404).
    for s in range(min(vistos, default=0), max(vistos, default=-1)):
        vistos.setdefault(s, _fecha_estimada(s))
    return sorted(vistos.items())


def _tesseract(img, psm):
    return subprocess.run(["tesseract", str(img), "-", "--psm", psm, "-l", "spa"],
                          capture_output=True, text=True, check=True).stdout


def _ocr_pdf(pdf_bytes):
    """Tres lecturas OCR independientes del acta, cada una como texto completo:
      1) imágenes originales del PDF, modo 6 (bloque de texto uniforme): la mejor en general;
      2) las mismas imágenes, modo 4 (una columna): rescata filas tapadas a medias por la firma;
      3) la página re-dibujada a 300 ppp en grises, modo 6: otra imagen, otros errores.
    Luego leer_acta() vota fila por fila."""
    for prog in ("pdfimages", "pdftoppm", "tesseract"):
        if not shutil.which(prog):
            raise RuntimeError(f"falta el programa «{prog}» (poppler-utils / tesseract-ocr)")
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "acta.pdf").write_bytes(pdf_bytes)
        subprocess.run(["pdfimages", "-all", str(p / "acta.pdf"), str(p / "img")], check=True)
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", str(p / "acta.pdf"), str(p / "pag")], check=True)
        imgs = [i for i in sorted(p.glob("img-*")) if i.stat().st_size >= 60_000]  # sin el logotipo 434x60
        pags = sorted(p.glob("pag-*.png"))
        return ["\n".join(_tesseract(i, "6") for i in imgs),
                "\n".join(_tesseract(i, "4") for i in imgs),
                "\n".join(_tesseract(i, "6") for i in pags)]


# valor en la columna VALOR, luego NÚMERO (4 cifras) y SERIE (3), tolerando basura del OCR (“ : . , -)
FILA = re.compile(r"(\d+)\W{0,2}MILLONES[\W_]{0,6}?(\d{4})[\W_]{1,6}?(\d{3})(?!\d)")
MAYOR = re.compile(r"PREMIO\s+MAYOR\W+(\d+)\b.*?(?<!\d)(\d{4})[\W_]{1,6}?(\d{3})(?!\d)")
# Planes conocidos (bruto por billete -> cantidad de secos), según el valor del mayor.
PLANES = {10_000_000_000: SECOS_ESPERADOS,  # vigente (visto en actas de junio a noviembre de 2026)
          6_000_000_000: {300_000_000: 1, 100_000_000: 1, 20_000_000: 5, 10_000_000: 15, 6_000_000: 32}}  # enero 2026


def _filas(texto):
    """[(valor, numero, serie)] de los secos, en el orden del acta."""
    return [(int(m[1]) * 1_000_000, m[2], m[3]) for l in texto.splitlines()
            if "MAYOR" not in l.upper() for m in [FILA.search(l)] if m]


def _parecidos(x, y):  # el valor no cuenta: también se lee mal (10 -> 40) y se decide por votos
    return sum(a != b for a, b in zip(x[1] + x[2], y[1] + y[2])) <= 1


def leer_acta(lecturas):
    """Interpreta las lecturas OCR de un acta y vota. Devuelve dict o None."""
    if isinstance(lecturas, str):
        lecturas = [lecturas]
    base = lecturas[0]
    cab = re.search(r"SORTEO\s+(\d{4})", base)
    fecha = None
    m = re.search(r"a\s+los\s+(\d{1,2})\s+del?\s+mes\s+de\s+([A-Za-zñáéíóú]+)\s+de(?:l)?\s+(\d{4})", base, re.I)
    if m:
        fecha = fecha_es(f"{m[1]} de {m[2]} de {m[3]}")
    votos_mayor = {}
    for t in lecturas:
        mm = MAYOR.search(t)
        if mm:
            votos_mayor[mm.groups()] = votos_mayor.get(mm.groups(), 0) + 1
    if not votos_mayor:
        return None
    mayor = max(votos_mayor, key=votos_mayor.get)
    # Agrupa las filas de las tres lecturas: una fila = mismas cifras salvo como mucho una distinta.
    # Cada grupo admite como mucho una fila de cada lectura (dos filas distintas del acta pueden
    # diferir en una sola cifra, p. ej. 1228-237 y 1228-257 en el sorteo 4828). Se prefiere
    # el grupo idéntico, luego el del mismo valor y por último cualquiera parecido.
    grupos, de = [], []  # grupos: [[fila, ...]]; de: [{lecturas que ya aportaron}]
    for n, t in enumerate(lecturas):
        for f in _filas(t):
            libres = [i for i, g in enumerate(grupos) if n not in de[i] and _parecidos(g[0], f)]
            libres.sort(key=lambda i: (grupos[i][0][1:] != f[1:], grupos[i][0][0] != f[0]))
            if libres:
                grupos[libres[0]].append(f); de[libres[0]].add(n)
            else:
                grupos.append([f]); de.append({n})
    plan = PLANES.get(int(mayor[0]) * 1_000_000)
    secos, dudas = [], []
    for g in grupos:
        # voto por cifra (k = 0..6 sobre «numero+serie»); en empate gana la primera lectura (modo 6)
        cifras = "".join(max(dict.fromkeys((f[1] + f[2])[k] for f in g),
                             key=lambda c: sum((f[1] + f[2])[k] == c for f in g)) for k in range(7))
        if len({f[1] + f[2] for f in g}) > 1:
            dudas.append(f"{cifras[:4]}-{cifras[4:]}: lecturas {sorted({f[1] + '-' + f[2] for f in g})}")
        valores = [f[0] for f in g]
        valor = max(dict.fromkeys(valores), key=valores.count)
        if len(set(valores)) > 1:
            dudas.append(f"{cifras[:4]}-{cifras[4:]}: valores leídos {sorted(set(valores))}")
        secos.append({"numero": cifras[:4], "serie": cifras[4:], "valor": valor, "votos": len(g)})
    # Si sobran filas en una categoría (una lectura con dos cifras mal), quita las de menos votos.
    if plan:
        for v, n in plan.items():
            de_v = [s for s in secos if s["valor"] == v]
            for s in sorted(de_v, key=lambda s: s["votos"])[:max(0, len(de_v) - n)]:
                secos.remove(s)
                dudas.append(f"descartada {s['numero']}-{s['serie']} ({s['votos']} voto)")
    cuenta = {}
    for s in secos:
        cuenta[s["valor"]] = cuenta.get(s["valor"], 0) + 1
    # El acta dice «NOTA: La realización de los 62 premios…» (mayor + secos): otra comprobación.
    total = [int(x) for t in lecturas for x in re.findall(r"realizaci\S*\s+de\s+los\s+(\d+)\s+premios", t, re.I)]
    total = max(set(total), key=total.count) if total else None
    if total and total != 1 + len(secos):
        dudas.append(f"el acta anuncia {total} premios y se leyeron {1 + len(secos)}")
    completo = (plan is not None and cuenta == plan and votos_mayor[mayor] >= 2
                and total in (None, 1 + len(secos)))
    return {"sorteo_acta": int(cab[1]) if cab else None, "fecha": fecha,
            "mayor": {"numero": mayor[1], "serie": mayor[2]}, "valor_mayor": int(mayor[0]) * 1_000_000,
            "secos": [{k: s[k] for k in ("numero", "serie", "valor")} for s in secos],
            "completo": completo, "dudas": dudas}


def sorteo(s, fecha=None):
    """{'mayor':{numero,serie}, 'secos':[{numero,serie,valor}], ...} o None si no hay acta.
    Claves extra: 'fecha' (la real, leída en el acta; puede diferir de la estimada por festivos o
    aplazamientos), 'valor_mayor' (bruto), 'completo' (True si cuadra con el plan conocido, con el
    total «62 premios» del acta y con al menos 2 lecturas del mayor) y 'dudas' (desacuerdos del
    OCR resueltos por votación). Recomendado: guardar solo si completo es True."""
    año = (fecha or _fecha_estimada(s))[:4]
    url = _URLS.get(s) or f"{BLOB}/{año}/{s}.pdf"
    try:
        pdf = _bytes(url)
    except Exception as e:
        if "404" in str(e):
            return None
        raise
    if not pdf.startswith(b"%PDF"):
        return None
    r = leer_acta(_ocr_pdf(pdf))
    if not r or (r["sorteo_acta"] and r["sorteo_acta"] != s):
        return None
    r.pop("sorteo_acta")
    r["fecha"] = r["fecha"] or fecha
    return r


if __name__ == "__main__":
    import json
    if len(sys.argv) > 1:
        pedidos = [int(x) for x in sys.argv[1:]]
    else:
        L = lista()
        print(f"{len(L)} sorteos ordinarios con acta: {L[0]} … {L[-1]}")
        time.sleep(PAUSA)
        pedidos = [s for s, _ in L[-3:]]
    for s in pedidos:
        r = sorteo(s)
        time.sleep(PAUSA)
        print(s, json.dumps(r, ensure_ascii=False))
