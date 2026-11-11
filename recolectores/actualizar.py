#!/usr/bin/env python3
"""Recolector de resultados oficiales de loterías colombianas.

Solo usa la biblioteca estándar de Python. Lee los JSON que ya existen en datos/,
pide únicamente los sorteos que faltan y vuelve a escribir los archivos.
Lo ejecuta GitHub Actions cada noche (.github/workflows/recolectar.yml).

Uso:
  python3 recolectores/actualizar.py                 # actualiza todo
  python3 recolectores/actualizar.py baloto          # solo un juego
  python3 recolectores/actualizar.py --desde 2025-11-01
"""
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
DATOS = RAIZ / "datos"
AGENTE = "cayo-loterias/1.0 (+https://github.com/ale0009; recolector de resultados publicos)"
PAUSA = 1.0  # segundos entre consultas: una por sorteo, sin prisa
MESES = {m: i for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}


# ---------------------------------------------------------------- utilidades
def pedir(url, datos=None):
    cuerpo = urllib.parse.urlencode(datos).encode() if datos else None
    req = urllib.request.Request(url, data=cuerpo, headers={"User-Agent": AGENTE})
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:  # red inestable: reintenta con espera creciente
            if intento == 2:
                raise
            time.sleep(3 * (intento + 1))
    return ""


def lineas(html_txt):
    t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", html_txt)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    return [l.strip() for l in t.split("\n") if l.strip()]


def fecha_es(texto):
    """'07 de Marzo de 2026' o '20/Febrero/2026' → '2026-03-07'."""
    m = re.search(r"(\d{1,2})\s*(?:de|/)\s*([A-Za-zñáéíóú]+)\s*(?:de|/)\s*(\d{4})", texto)
    if not m:
        return None
    mes = m[2].lower()
    if mes not in MESES:  # tolera errores de OCR o de digitación: «junlo» → junio, «setiembre» → septiembre
        import difflib
        parecido = difflib.get_close_matches(mes, MESES, n=1, cutoff=0.7)
        if not parecido:
            return None
        mes = parecido[0]
    try:
        return dt.date(int(m[3]), MESES[mes], int(m[1])).isoformat()
    except ValueError:  # día imposible (p. ej. 31 de junio): mejor sin fecha que una fecha falsa
        return None


def pesos(texto):
    return int(re.sub(r"\D", "", texto) or 0)


def cargar(nombre, base):
    ruta = DATOS / f"{nombre}.json"
    return json.loads(ruta.read_text()) if ruta.exists() else base


DIAS = 400  # los premios vencen al año: se guarda un poco más y se poda lo viejo


def limite_por_defecto():
    return (dt.date.today() - dt.timedelta(days=DIAS)).isoformat()


def guardar(nombre, obj):
    corte = limite_por_defecto()
    obj["sorteos"] = dict(sorted(((k, v) for k, v in obj["sorteos"].items() if v.get("fecha", "9") >= corte),
                                 key=lambda kv: int(kv[0])))
    (DATOS / f"{nombre}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


# ---------------------------------------------------------------- Baloto y Revancha
BALOTO = "https://www.baloto.com"


def baloto_pagina(juego, sorteo):
    L = lineas(pedir(f"{BALOTO}/resultados-{juego}/{sorteo}"))
    cab = next((i for i, l in enumerate(L) if l.startswith("SORTEO ")), None)
    if cab is None or pesos(L[cab]) != sorteo:
        return None
    fecha = fecha_es(L[cab + 2])
    i = next(n for n, l in enumerate(L) if l.startswith("ACUMULADO DEL SORTEO"))
    bolas = [int(x) for x in L[i + 1:i + 20] if re.fullmatch(r"\d{2}", x)][:6]
    j = L.index("PREMIO POR GANADOR")
    premios, n = {}, j + 1
    while n < len(L) and re.fullmatch(r"\d", L[n]):
        if L[n + 1] == "+":
            clave, n = L[n] + "+SB", n + 3
        else:
            clave, n = L[n], n + 1
        premios[clave] = {"ganadores": pesos(L[n + 1]), "por_ganador": pesos(L[n + 2])}
        n += 3
    return {"fecha": fecha, "numeros": bolas[:5], "sb": bolas[5], "premios": premios,
            "acumulado": L[i].split(":")[-1].strip()}


def ultimo_baloto():
    h = pedir(f"{BALOTO}/resultados")
    return max(int(x) for x in re.findall(r"resultados-baloto/(\d+)", h))


def actualizar_baloto(desde):
    db = cargar("baloto", {"juego": "Baloto y Revancha", "fuente": BALOTO + "/resultados", "sorteos": {}})
    tope = ultimo_baloto()
    nuevos = 0
    # Recorre toda la ventana (~400 días, 3 sorteos por semana) y pide solo lo que falta:
    # así un sorteo que falló una noche se vuelve a intentar la siguiente.
    for s in range(tope - 172, tope + 1):
        if str(s) in db["sorteos"]:
            continue
        try:
            b = baloto_pagina("baloto", s)
        except Exception as e:  # una página rara no frena al resto
            print(f"  baloto {s}: error al leer ({str(e)[:80]})", flush=True); b = None
        time.sleep(PAUSA)
        if not b:
            continue
        if desde and b["fecha"] < desde:
            continue
        try:
            r = baloto_pagina("revancha", s)
        except Exception:
            r = None
        time.sleep(PAUSA)
        db["sorteos"][str(s)] = {"fecha": b["fecha"], "baloto": {k: v for k, v in b.items() if k != "fecha"},
                                 "revancha": {k: v for k, v in (r or {}).items() if k != "fecha"} or None}
        nuevos += 1
        print(f"  baloto {s} {b['fecha']}", flush=True)
    guardar("baloto", db)
    return nuevos


# ---------------------------------------------------------------- Lotería de Medellín
MED = "https://loteriademedellin.com.co"
# Orden fijo en que la plantilla oficial publica los 44 secos (plan de premios 2025-2026).
MED_SECOS = [1_000_000_000] * 2 + [700_000_000] * 2 + [500_000_000] * 2 + [100_000_000] * 6 \
    + [50_000_000] * 7 + [20_000_000] * 10 + [10_000_000] * 15


def medellin_lista():
    h = pedir(f"{MED}/historico-de-resultados/")
    return [(int(v), f) for v, f in re.findall(
        r'data-lottery_id="16" value="(\d+)"\s*>[^<]*\((\d{4}-\d{2}-\d{2})\)', h)]


def medellin_sorteo(s):
    j = json.loads(pedir(f"{MED}/wp-admin/admin-ajax.php", {
        "action": "wp_get_results_lottery_template", "is_front": "true",
        "lottery_id": "16", "draw_id": str(s), "post_type": "results_template"}))
    L = lineas(j.get("html", ""))
    toks = [x for x in L if re.fullmatch(r"\d{3,4}", x)]
    if not toks or toks[0] != str(s):
        return None
    nums = toks[1:]
    pares = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
    mayor, secos = pares[0], pares[1:]
    valores = MED_SECOS if len(secos) == len(MED_SECOS) else [None] * len(secos)
    return {"mayor": {"numero": mayor[0], "serie": mayor[1]},
            "secos": [{"numero": n, "serie": se, "valor": v} for (n, se), v in zip(secos, valores)]}


def actualizar_medellin(desde):
    db = cargar("medellin", {"juego": "Lotería de Medellín", "fuente": MED + "/historico-de-resultados/", "sorteos": {}})
    nuevos = 0
    for s, fecha in medellin_lista():
        if str(s) in db["sorteos"] or (desde and fecha < desde):
            continue
        try:
            r = medellin_sorteo(s)
        except Exception as e:
            print(f"  medellin {s}: error al leer ({str(e)[:80]})", flush=True); r = None
        time.sleep(PAUSA)
        if r:
            db["sorteos"][str(s)] = {"fecha": fecha, **r}
            nuevos += 1
            print(f"  medellin {s} {fecha}", flush=True)
    guardar("medellin", db)
    return nuevos


# ---------------------------------------------------------------- Lotería de Boyacá
BOY = "https://loteriadeboyaca.gov.co/resultados/"


def boyaca_fechas():
    h = pedir(BOY)
    i = h.find('name="fecha"')
    return re.findall(r"<option>(\d{4}-\d{2}-\d{2})</option>", h[i:i + 20000])


def boyaca_fecha(fecha):
    L = lineas(pedir(BOY, {"fecha": fecha}))
    i = next((n for n, l in enumerate(L) if l.startswith("Resultado sorteo #")), None)
    if i is None:
        return None
    s = pesos(L[i])
    j = L.index("Número Ganador", i)
    digitos = []
    n = j + 1
    while L[n] != "Serie":
        digitos.append(L[n]); n += 1
    k = n + 1; serie = []
    while re.fullmatch(r"\d", L[k]) and len(serie) < 3:
        serie.append(L[k]); k += 1
    secos = []
    m = L.index("Resultados secos", k)
    n = m + 1
    while n + 2 < len(L):
        if "$" in L[n] and "Millones" in L[n] and re.fullmatch(r"\d{4}", L[n + 1]) and re.fullmatch(r"\d{3}", L[n + 2]):
            v = re.search(r"\$([\d.]+)\s*Millones", L[n])
            secos.append({"numero": L[n + 1], "serie": L[n + 2],
                          "valor": int(v[1].replace(".", "")) * 1_000_000 if v else None})
            n += 3
        elif secos:
            break
        else:
            n += 1
    return s, {"fecha": fecha, "mayor": {"numero": "".join(digitos), "serie": "".join(serie)}, "secos": secos}


def actualizar_boyaca(desde):
    db = cargar("boyaca", {"juego": "Lotería de Boyacá", "fuente": BOY, "sorteos": {}})
    ya = {v["fecha"] for v in db["sorteos"].values()}
    limite = desde
    nuevos = 0
    for f in boyaca_fechas():
        if f in ya or f < limite:
            continue
        try:
            r = boyaca_fecha(f)
        except Exception as e:
            print(f"  boyaca {f}: error al leer ({str(e)[:80]})", flush=True); r = None
        time.sleep(PAUSA)
        if r and r[0] < 1000:  # sorteo extraordinario: otro plan de premios, aún no soportado
            print(f"  boyaca extraordinario {r[0]} {f}: omitido", flush=True)
            continue
        if r:
            db["sorteos"][str(r[0])] = r[1]
            nuevos += 1
            print(f"  boyaca {r[0]} {f}", flush=True)
    guardar("boyaca", db)
    return nuevos


# ---------------------------------------------------------------- loterías en módulos aparte
# Cada archivo recolectores/loterias/<id>.py define:
#   NOMBRE, FUENTE, lista() -> [(sorteo, 'AAAA-MM-DD')], sorteo(s, fecha) -> {"mayor": {...}, "secos": [...]} | None
REINTENTOS = 5         # noches que se reintenta un sorteo que no se pudo leer antes de marcarlo ilegible
PRESUPUESTO = int(os.environ.get("CAYO_PRESUPUESTO", 12 * 60))  # segundos máximos por fuente y por noche; lo que falte sigue la noche siguiente
ESTADO = {}            # se llena en main(); guarda reintentos y sorteos ilegibles entre noches


def actualizar_modulo(ident, desde):
    import importlib
    mod = importlib.import_module(f"loterias.{ident}")
    db = cargar(ident, {"juego": mod.NOMBRE, "fuente": mod.FUENTE, "sorteos": {}})
    reint = ESTADO.setdefault("reintentos", {}).setdefault(ident, {})
    ilegibles = ESTADO.setdefault("ilegibles", {}).setdefault(ident, {})
    inicio, nuevos, fallidos = time.monotonic(), 0, 0
    hoy = dt.date.today().isoformat()
    try:
        for s, fecha in mod.lista():
            k = str(s)
            if k in db["sorteos"] or k in ilegibles or fecha < desde or fecha > hoy:
                continue
            if time.monotonic() - inicio > PRESUPUESTO:
                print(f"  {ident}: se acabó el tiempo de esta noche; sigue mañana", flush=True)
                break
            try:
                r = mod.sorteo(s, fecha)
            except Exception as e:  # una página rara no frena al resto de sorteos
                r = {"completo": False}
                print(f"  {ident} {s}: error al leer ({str(e)[:80]})", flush=True)
            time.sleep(PAUSA)
            if r and r.get("completo") is False:
                fallidos += 1
                reint[k] = reint.get(k, 0) + 1
                if reint[k] >= REINTENTOS:
                    ilegibles[k] = {"fecha": fecha, "desde": hoy}
                    reint.pop(k, None)
                    print(f"  {ident} {s}: ilegible tras {REINTENTOS} noches; se remite a la fuente oficial", flush=True)
                else:
                    print(f"  {ident} {s}: lectura incompleta ({reint[k]}/{REINTENTOS}), se reintenta otra noche", flush=True)
                continue
            if r and r.get("mayor", {}).get("numero"):
                r = corregir_fecha(r)
                # Solo se guardan campos de resultados: nunca texto crudo (las actas traen nombres y cédulas).
                r = {kk: v for kk, v in r.items() if kk in CAMPOS}
                if getattr(mod, "OCR", False):
                    r["ocr"] = True
                db["sorteos"][k] = {"fecha": fecha, **r}
                reint.pop(k, None)
                nuevos += 1
                print(f"  {ident} {s} {fecha}", flush=True)
    finally:
        guardar(ident, db)  # lo leído se conserva aunque la fuente falle a mitad de camino
        corte = limite_por_defecto()
        for d in (reint, ilegibles):
            for k in [k for k, v in d.items() if isinstance(v, dict) and v.get("fecha", "9") < corte]:
                d.pop(k)
    return nuevos


CAMPOS = {"fecha", "mayor", "secos", "aviso", "ganafijo", "especiales"}


def corregir_fecha(r):
    """Algunas fuentes publican el año mal digitado (p. ej. 2027 en vez de 2026). Si la fecha cae en
    el futuro y un año antes es una fecha ya pasada, se corrige y se deja constancia en «aviso»."""
    f = r.get("fecha")
    hoy = dt.date.today().isoformat()
    if f and f > hoy:
        antes = f"{int(f[:4]) - 1}{f[4:]}"
        if antes <= hoy:
            r = {**r, "fecha": antes}
            r["aviso"] = "; ".join(filter(None, [r.get("aviso"), f"la fuente publica la fecha {f}; se corrigió a {antes}"]))
    return r


def modulos():
    carpeta = pathlib.Path(__file__).resolve().parent / "loterias"
    return sorted(p.stem for p in carpeta.glob("*.py") if not p.stem.startswith("_"))


# ---------------------------------------------------------------- principal
JUEGOS = {"baloto": actualizar_baloto, "medellin": actualizar_medellin, "boyaca": actualizar_boyaca}
for _m in modulos():
    JUEGOS[_m] = (lambda ident: (lambda desde: actualizar_modulo(ident, desde)))(_m)


def main(argv):
    desde = None
    if "--desde" in argv:
        desde = argv[argv.index("--desde") + 1]
        argv = [a for a in argv if a not in ("--desde", desde)]
    desde = desde or limite_por_defecto()
    elegidos = argv or list(JUEGOS)
    DATOS.mkdir(exist_ok=True)
    estado = cargar("estado", {"fuentes": {}})
    ESTADO.clear(); ESTADO.update(estado)
    fallos = 0
    ahora = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    for j in elegidos:
        print(f"[{j}]", flush=True)
        previo = ESTADO["fuentes"].get(j, {})
        try:
            n = JUEGOS[j](desde)
            ESTADO["fuentes"][j] = {"ok": True, "nuevos": n, "revisado": ahora(), "ultimo_ok": ahora(), "fallos_seguidos": 0}
        except Exception as e:  # una fuente caída no detiene a las demás
            fallos += 1
            ESTADO["fuentes"][j] = {**previo, "ok": False, "error": str(e)[:200], "revisado": ahora(),
                                    "fallos_seguidos": previo.get("fallos_seguidos", 0) + 1}
            print(f"  ERROR {j}: {e}", flush=True)
    ESTADO["actualizado"] = ahora()
    (DATOS / "estado.json").write_text(json.dumps(ESTADO, ensure_ascii=False, indent=1) + "\n")
    return 1 if fallos == len(elegidos) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
