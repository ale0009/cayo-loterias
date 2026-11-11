#!/usr/bin/env python3
"""Adaptador de la Lotería de Manizales para el recolector de «¿Cayó?».

Qué publica el sitio oficial (https://loteriademanizales.com):
  * /resultados-anteriores/  -> lista de sorteos con fecha ("Sorteo 4980 Noviembre 04 de 2026")
                                y, por sorteo, 4 IMÁGENES (mayor + secos1/2/3). Los secos SOLO
                                están en imágenes: no hay texto, JSON, PDF ni API que los liste.
  * / (inicio)               -> el último premio mayor en TEXTO (número y serie).
  * https://api.loteriademanizales.com/consultar-resultados (Laravel, POST con CSRF)
                             -> verificador de UN billete (numero+serie+sorteo) que devuelve
                                la categoría y el valor NETO. No lista ganadores.

Por eso:
  * lista()  usa solo la biblioteca estándar.
  * sorteo() descarga las 4 imágenes y las lee con OCR (programa `tesseract` + Pillow).
    Esto ROMPE la regla «solo biblioteca estándar»: en GitHub Actions hace falta
        sudo apt-get install -y tesseract-ocr && pip install pillow
    Sin ellos, sorteo() devuelve solo el mayor del último sorteo (texto de la portada) y
    secos vacíos, marcado con "incompleto": True.
  * Cada sorteo leído por OCR se valida: número de sorteo impreso en la imagen, cantidad de
    secos por grupo ("10 SECOS DE $50 MILLONES") y el mayor contra el verificador oficial.
    Si algo no cuadra, sorteo() devuelve None (mejor nada que datos falsos).

Interfaz igual a la de los otros adaptadores:
  lista()            -> [(sorteo:int, 'AAAA-MM-DD')]   (solo ordinarios, solo fechas pasadas)
  sorteo(s, fecha)   -> {"mayor": {"numero","serie"}, "secos": [{"numero","serie","valor"}],
                         "especiales": [{"numero","sin_serie": True,"nombre": "Premio Gana Siempre"}]} | None
                        (valor = premio BRUTO en pesos, igual que Medellín y Boyacá)
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import http.cookiejar

try:  # dentro del repo: reutiliza las utilidades comunes
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "recolectores"))
    from actualizar import pedir, lineas, fecha_es, pesos, PAUSA, AGENTE  # noqa: F401
except Exception:  # copia mínima para probarlo suelto
    import urllib.parse
    AGENTE = "cayo-loterias/1.0 (+https://github.com/ale0009; recolector de resultados publicos)"
    PAUSA = 1.0
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

MAN = "https://loteriademanizales.com"
ANTERIORES = MAN + "/resultados-anteriores/"
VERIFICADOR = "https://api.loteriademanizales.com/consultar-resultados"
MESES_ES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
# Imágenes de adorno que aparecen entre los resultados y no son de ningún sorteo.
ADORNOS = re.compile(r"(?i)aproximaciones|codigo-qr|chatgpt|horizontal|bono|carro|moto|mundialista|extra|whatsapp|cropped")

_cache = {}



NOMBRE = "Lotería de Manizales"
FUENTE = "https://loteriademanizales.com/resultados-anteriores/"
OCR = True  # lee imágenes: necesita tesseract (y poppler o Pillow)

def _anteriores():
    if "ant" not in _cache:
        _cache["ant"] = pedir(ANTERIORES)
    return _cache["ant"]


def _principal(h):
    """Contenido de <main> sin los bloques de spam ocultos (el sitio tiene texto de casinos inyectado)."""
    i, j = h.find("<main"), h.find("</main>")
    h = h[i:j] if i >= 0 and j > i else h
    return re.sub(r'(?s)<div style="position: fixed[^"]*">.*?</div>', " ", h)


# ---------------------------------------------------------------- lista de sorteos
def lista():
    """Sorteos ordinarios con fecha, sacados del texto de /resultados-anteriores/.

    Formatos vistos: 'Sorteo 4980 Noviembre 04 de 2026', 'Sorteo 4931-  Noviembre 26 de 2025',
    'Sorteo 4955  Mayo 13 de 2026'. Los extraordinarios no llevan 'Sorteo NNNN' y quedan fuera.
    La página también anuncia sorteos FUTUROS del mes en curso: se descartan por fecha.
    """
    L = lineas(_principal(_anteriores()))
    hoy = dt.date.today().isoformat()
    vistos = {}
    for l in L:
        m = re.match(r"(?i)sorteo\s+(\d{4})\s*-?\s*([a-záéíóú]+)\s+(\d{1,2})\s+de\s+(\d{4})", l)
        if not m or m[2].lower() not in MESES_ES:
            continue
        f = dt.date(int(m[4]), MESES_ES.index(m[2].lower()) + 1, int(m[3])).isoformat()
        if f <= hoy:
            vistos[int(m[1])] = f
    return sorted(vistos.items())


# ---------------------------------------------------------------- imágenes por sorteo
def _tipo(nombre):
    n = nombre.lower()
    if n.startswith(("mayor", "resultados")):
        return "mayor"
    m = re.match(r"secos-?([123])", n)
    return "secos" + m[1] if m else None


def _imagenes():
    """{sorteo: {"mayor": url, "secos1": url, ...}} siguiendo el orden del documento.

    Los nombres son irregulares (Mayor_4980.jpg, mayor4976.png, Secos-34952.jpeg, secos1.png...).
    Una imagen sin número hereda el sorteo de la anterior; si ese tipo ya estaba ocupado, pasa
    al sorteo siguiente. El OCR comprueba después el número impreso en cada imagen.
    """
    if "img" in _cache:
        return _cache["img"]
    urls = re.findall(r'<a href="(https://loteriademanizales\.com/wp-content/uploads/[^"]+\.(?:jpe?g|png|webp))"',
                      _principal(_anteriores()))
    res, actual = {}, None
    for u in urls:
        nombre = u.rsplit("/", 1)[1]
        tipo = _tipo(nombre)
        if not tipo or ADORNOS.search(nombre):
            continue
        num = re.search(r"(4\d{3})", nombre)
        if num:
            actual = int(num[1])
        elif actual is not None and tipo in res.get(actual, {}):
            actual += 1
        if actual is None:
            continue
        res.setdefault(actual, {}).setdefault(tipo, u)
    _cache["img"] = res
    return res


# ---------------------------------------------------------------- OCR
def _ocr_disponible():
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def _tess(ruta, psm, digitos=False, tsv=False):
    cmd = ["tesseract", ruta, "-", "--psm", str(psm)]
    if digitos:
        cmd += ["-c", "tessedit_char_whitelist=0123456789"]
    if tsv:
        cmd += ["tsv"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout


# Dos diseños vistos: 2026 = cajas amarillas con cifras azul oscuro; 2025 = cajas moradas
# con cifras blancas sobre fondo naranja.
def _es_amarilla(r, g, b):
    return r > 200 and g > 170 and r - b > 50


def _es_morada(r, g, b):
    return 60 < r < 160 and g < 90 and 60 < b < 170 and abs(r - b) < 50


def _estilo(im):
    w, h = im.size
    px = im.load()
    am = mo = 0
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            r, g, b = px[x, y][:3]
            am += _es_amarilla(r, g, b)
            mo += _es_morada(r, g, b)
    # en el diseño morado el fondo naranja también parece "amarillo": decide la presencia de morado
    return "morada" if mo > 0.02 * (w * h / 16) else "amarilla"


def _cajas(im):
    """Rectángulos de color (donde van número, serie, sorteo...) por componentes conexas."""
    w, h = im.size
    px = im.load()
    es = _es_morada if _estilo(im) == "morada" else _es_amarilla
    amarillo = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if es(*px[x, y][:3]):
                amarillo[y * w + x] = 1
    vista = bytearray(w * h)
    cajas = []
    for i in range(w * h):
        if not amarillo[i] or vista[i]:
            continue
        pila, vista[i] = [i], 1
        x0 = x1 = i % w
        y0 = y1 = i // w
        n = 0
        while pila:
            k = pila.pop(); n += 1
            x, y = k % w, k // w
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            for v in (k - 1, k + 1, k - w, k + w):
                if 0 <= v < w * h and amarillo[v] and not vista[v] and abs(v % w - x) <= 1:
                    vista[v] = 1; pila.append(v)
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if 18 <= bh <= 90 and bw >= 8 and n > 0.3 * bw * bh:
            cajas.append([x0, y0, x1, y1])
    # Las cifras grandes del premio mayor parten su caja en trozos: se unen los trozos
    # estrechos (<60 px) de la misma fila separados por <=3 px. Número y serie quedan a 5-7 px.
    cajas.sort(key=lambda c: (c[1] // 6, c[0]))
    unidas = []
    for c in cajas:
        u = next((u for u in unidas if abs(u[1] - c[1]) <= 4 and abs(u[3] - c[3]) <= 4
                  and -6 <= c[0] - u[2] <= 3 and (c[2] - c[0] < 60 and u[4] < 60)), None)
        if u:
            u[2], u[1], u[3], u[4] = max(u[2], c[2]), min(u[1], c[1]), max(u[3], c[3]), c[2] - c[0]
        else:
            unidas.append(c + [c[2] - c[0]])
    return [tuple(u[:4]) for u in unidas if u[2] - u[0] >= 35]


# Cinco lecturas distintas de cada caja; vale la cifra que repiten al menos 3.
# Con una sola lectura había ~2 errores por sorteo (7322 -> 1322, 5370 -> 9370); con el voto, 0.
_MODOS = [("gris", 3, 0), ("gris", 2, 0), ("color", 3, 10), ("color", 2, 30), ("gris", 4, 0)]
# Diseño morado (cajas más pequeñas): solo gris invertido a varias escalas, recorte casi sin margen.
_MODOS_MORADA = [("gris", 2, 0), ("gris", 3, 0), ("gris", 4, 0), ("gris", 5, 0), ("color", 2, 0)]


def _leer_caja(im, caja, tmp, estilo="amarilla"):
    from PIL import Image, ImageOps
    x0, y0, x1, y1 = caja
    morada = estilo == "morada"
    m_ = 1 if morada else 3
    recorte = im.crop((x0 + m_, y0 + m_, x1 - m_ + 1, y1 - m_ + 1))
    votos = []
    for tipo, k, d in (_MODOS_MORADA if morada else _MODOS):
        if tipo == "gris":
            m = ImageOps.autocontrast(recorte.convert("L"))
            if morada:  # cifras blancas sobre morado: invertir
                m = ImageOps.invert(m)
        else:  # máscara por color: azul oscuro (B > R) sobre amarillo, o blanco sobre morado
            m = Image.new("L", recorte.size, 255)
            p, q = recorte.load(), m.load()
            for y in range(recorte.height):
                for x in range(recorte.width):
                    r, g, b = p[x, y][:3]
                    if (min(r, g, b) > 150 + d // 2) if morada else (b > r + d):
                        q[x, y] = 0
        m = ImageOps.expand(m.resize((m.width * k, m.height * k), Image.LANCZOS), 20, fill=255)
        m.save(tmp)
        votos.append(re.sub(r"\D", "", _tess(tmp, 7, digitos=True)))
    from collections import Counter
    t, n = Counter(votos).most_common(1)[0]
    return t if n >= 3 else "?"


def _titulos_una_pasada(g):
    lin = {}
    for fila in _tess(g, 11, tsv=True).splitlines()[1:]:
        p = fila.split("\t")
        if len(p) < 12 or not p[11].strip():
            continue
        y = (int(p[7]) + int(p[9]) / 2) / 2  # centro de la palabra, en píxeles de la imagen original
        lin.setdefault((p[2], p[3], p[4]), [y, []])[1].append(p[11].strip())
    lineas_txt = sorted((y, " ".join(ws)) for y, ws in lin.values())
    res = []
    for y, t in lineas_txt:
        m = re.search(r"(\d{1,2})\s*SECOS?\b", t.upper())
        if not m:
            continue
        valor = None
        for y2, t2 in lineas_txt:
            if 0 < y2 - y < 45 and "MILLON" in t2.upper():
                v = re.search(r"(\d[\d.]*)\s*MILLON", t2.upper().replace(" ", ""))
                if v and 1 <= pesos(v[1]) <= 5000:
                    valor = pesos(v[1]) * 1_000_000
                break
        res.append((y, int(m[1]), valor))
    return res


def _encabezados(ruta):
    """[(y, {cantidades leídas}, valor_bruto|None)] de los títulos 'N SECOS DE' + '$X MILLONES'.

    Se hacen varias pasadas de OCR (distintos umbrales) y se juntan por altura: a veces una
    pasada lee '16 SECOS' donde dice '10'. sorteo() acepta el grupo si alguna de las cantidades
    leídas coincide con los pares encontrados. Los títulos sin 'SECOS' ('$3.000 MILLONES PREMIO
    MAYOR', 'Premio Gana Siempre') se ignoran. Si la cifra en millones no se lee en ninguna
    pasada, el valor queda en None y sorteo() lo pregunta al verificador oficial.
    """
    from PIL import Image
    from collections import Counter
    base = Image.open(ruta).convert("RGB")
    if _estilo(base) == "morada":  # títulos blancos sobre naranja: quedarse solo con lo blanco
        variantes = [base.point(lambda v, u=u: 255 if v > u else 0).convert("L").point(lambda v: 0 if v == 255 else 255)
                     for u in (160, 180, 200)]
    else:
        gris = base.convert("L")
        variantes = [gris, gris.point(lambda v: 255 if v > 128 else 0), gris.point(lambda v: 0 if v > 128 else 255)]
    juntos = []
    for i, im in enumerate(variantes):
        g = f"{ruta}.{i}.png"
        im.resize((im.width * 2, im.height * 2), Image.LANCZOS).save(g)
        for y, n, v in _titulos_una_pasada(g):
            e = next((e for e in juntos if abs(e[0] - y) < 15), None)
            if not e:
                e = [y, [], []]; juntos.append(e)
            e[1].append(n)
            if v:
                e[2].append(v)
    return [(y, frozenset(ns), Counter(vs).most_common(1)[0][0] if vs else None) for y, ns, vs in sorted(juntos)]


def _leer_imagen(url, s, tmpdir):
    """Devuelve (sorteo_impreso, pares[(y, numero, serie)], encabezados)."""
    from PIL import Image
    ruta = os.path.join(tmpdir, "img" + os.path.splitext(url)[1])
    local = os.environ.get("MANIZALES_CACHE")  # carpeta opcional para no repetir descargas al probar
    copia = os.path.join(local, url.split("/uploads/")[-1].replace("/", "_")) if local else None
    if copia and os.path.exists(copia):
        shutil.copy(copia, ruta)
    else:
        req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(req, timeout=40) as r, open(ruta, "wb") as f:
            f.write(r.read())
        time.sleep(PAUSA)
        if copia:
            os.makedirs(local, exist_ok=True); shutil.copy(ruta, copia)
    im = Image.open(ruta).convert("RGB")
    cajas = sorted(_cajas(im), key=lambda c: (c[1], c[0]))
    tmp = os.path.join(tmpdir, "caja.png")
    estilo = _estilo(im)
    leidas = [(c, _leer_caja(im, c, tmp, estilo)) for c in cajas]
    impreso = next((int(t) for c, t in leidas if re.fullmatch(r"4\d{3}", t) and c[1] < im.height * 0.15), None)
    pares, usadas, solos = [], set(), []
    for c, t in leidas:
        if c[1] < im.height * 0.12 or not re.fullmatch(r"\d{4}", t):
            continue
        cy = (c[1] + c[3]) / 2
        vecinas = [(d[0] - c[2], j) for j, (d, u) in enumerate(leidas)
                   if j not in usadas and re.fullmatch(r"\d{3}", u) and abs((d[1] + d[3]) / 2 - cy) < 12
                   and 0 <= d[0] - c[2] < (c[2] - c[0])]
        if vecinas:
            j = min(vecinas)[1]
            usadas.add(j)
            pares.append((cy, t, leidas[j][1]))
        else:
            solos.append(t)  # número sin serie al lado: el «Premio Gana Siempre» de la imagen del mayor
    # cajas que el voto no pudo leer: si están en la zona de resultados, el sorteo no es fiable
    dudosas = sum(1 for c, t in leidas if t == "?" and c[1] >= im.height * 0.12 and c[3] < im.height * 0.9)
    return impreso, pares, _encabezados(ruta), dudosas, solos


class Verificador:
    """Verificador oficial de billetes (api.loteriademanizales.com, Laravel con token CSRF)."""

    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.addheaders = [("User-Agent", AGENTE)]
        self.tok = None
        self.consultas = 0

    def __call__(self, numero, serie, s):
        """-> (titulo, neto) p. ej. ('... SECO 3 DE 200 MILLONES', 132800000) o ('... NO ...', 0)."""
        if not self.tok:
            h = self.op.open(VERIFICADOR, timeout=40).read().decode("utf-8", "ignore")
            self.tok = re.search(r'name="csrf-token" content="([^"]+)"', h)[1]
            time.sleep(PAUSA)
        req = urllib.request.Request(VERIFICADOR, data=urllib.parse.urlencode(
            {"numero": numero, "serie": serie, "sorteo": str(s)}).encode(),
            headers={"X-CSRF-TOKEN": self.tok, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})
        j = json.loads(self.op.open(req, timeout=40).read().decode())
        self.consultas += 1
        time.sleep(PAUSA)
        neto = re.search(r"\$([\d.]+)", j.get("text", ""))
        return j.get("titulo", ""), pesos(neto[1]) if neto else 0


def _mayor_portada(s):
    """Último mayor en texto en la portada: '4980' ... dígitos duplicados (cara y reverso de la tarjeta)."""
    L = lineas(_principal(pedir(MAN + "/")))
    if str(s) not in L[:40]:
        return None
    i = L.index(str(s))
    dig = []
    for l in L[i + 1:i + 40]:
        if re.fullmatch(r"\d", l):
            dig.append(l)
        elif dig:
            break
    d = dig[::2]  # cada dígito sale dos veces
    return {"numero": "".join(d[:4]), "serie": "".join(d[4:7])} if len(d) == 7 else None


# ---------------------------------------------------------------- un sorteo
def sorteo(s, fecha=None, verificar="mayor", ver=None):
    """Lee el sorteo s de sus 4 imágenes oficiales.

    verificar: "mayor" (por defecto: 1 consulta), "grupo" (mayor + primer seco de cada grupo,
    ~9 consultas) o "todos" (cada seco, ~52 consultas: ideal para el sorteo nuevo de cada semana).
    Además se consulta el verificador cuando el OCR no pudo leer el valor de un grupo.
    """
    if not _ocr_disponible():
        m = _mayor_portada(s)
        return {"mayor": m, "secos": [], "incompleto": True} if m else None
    imgs = _imagenes().get(s)
    if not imgs or not all(k in imgs for k in ("mayor", "secos1", "secos2", "secos3")):
        print(f"  manizales {s}: no encuentro sus 4 imágenes", file=sys.stderr)
        return None
    ver = ver or Verificador()
    mayor, grupos, especiales = None, [], []
    with tempfile.TemporaryDirectory() as tmp:
        for tipo in ("mayor", "secos1", "secos2", "secos3"):
            impreso, pares, enc, dudosas, solos = _leer_imagen(imgs[tipo], s, tmp)
            if tipo == "mayor" and len(solos) == 1:
                # «Premio Gana Siempre»: un número de 4 cifras que paga en cualquier serie
                especiales = [{"numero": solos[0], "sin_serie": True, "nombre": "Premio Gana Siempre"}]
            if impreso != s:
                print(f"  manizales {s}: la imagen {tipo} dice sorteo {impreso}", file=sys.stderr)
                return None
            if dudosas:
                print(f"  manizales {s}: {tipo} tiene {dudosas} cajas ilegibles", file=sys.stderr)
                return None
            enc = sorted(enc)
            propios = {e: [] for e in enc}
            for (y, n, se) in sorted(pares):
                arriba = [e for e in enc if e[0] < y]
                if not arriba:  # sin título 'N SECOS' encima: el premio mayor
                    if tipo == "mayor" and mayor is None:
                        mayor = {"numero": n, "serie": se}
                    else:
                        print(f"  manizales {s}: {tipo} par suelto {n}-{se}", file=sys.stderr)
                        return None
                    continue
                propios[arriba[-1]].append({"numero": n, "serie": se, "valor": arriba[-1][2]})
            for e, lst in propios.items():
                if len(lst) not in e[1]:
                    print(f"  manizales {s}: {tipo} grupo de {e[1]} secos, leí {len(lst)}", file=sys.stderr)
                    return None
                grupos.append(lst)
    if not mayor or not grupos:
        return None
    secos = [x for g in grupos for x in g]
    if len({(x["numero"], x["serie"]) for x in secos + [mayor]}) != len(secos) + 1:
        return None
    # verificación contra la fuente oficial
    t, _ = ver(mayor["numero"], mayor["serie"], s)
    if "PREMIO MAYOR" not in t.upper():
        print(f"  manizales {s}: el verificador no confirma el mayor ({t})", file=sys.stderr)
        return None
    for g in grupos:
        revisar = g if verificar == "todos" else g[:1] if (verificar == "grupo" or g[0]["valor"] is None) else []
        for x in revisar:
            t, _ = ver(x["numero"], x["serie"], s)
            m = re.search(r"SECO\s*\d+\s*DE\s*([\d.]+)\s*MILLON", t.upper())
            if not m:
                print(f"  manizales {s}: el verificador no confirma {x['numero']}-{x['serie']} ({t})", file=sys.stderr)
                return None
            v = pesos(m[1]) * 1_000_000
            if g[0]["valor"] is None:
                for y in g:
                    y["valor"] = v
            elif v != x["valor"]:
                print(f"  manizales {s}: valor {x['valor']} por OCR, {v} según verificador", file=sys.stderr)
                return None
    r = {"mayor": mayor, "secos": secos}
    if especiales:
        r["especiales"] = especiales
    return r


if __name__ == "__main__":
    L = lista()
    print(f"lista(): {len(L)} sorteos, de {L[0]} a {L[-1]}")
    v = Verificador()
    modo = os.environ.get("VERIFICAR", "mayor")
    for s in [int(a) for a in sys.argv[1:]] or [L[-1][0]]:
        f = dict(L).get(s)
        t0 = time.time()
        r = sorteo(s, f, verificar=modo, ver=v)
        print(f"{s} {f} ({time.time() - t0:.0f} s, {v.consultas} consultas al verificador hasta ahora)")
        print(json.dumps(r, ensure_ascii=False) if r else None)
