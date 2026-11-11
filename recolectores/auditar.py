#!/usr/bin/env python3
"""Auditoría nocturna: vuelve a pedir EN VIVO una muestra de sorteos ya guardados y los compara.

Es la «doble confirmación» automática. Cada noche toma unos pocos sorteos al azar por fuente
(reproducible: la semilla es la fecha), los pide de nuevo a la fuente con el mismo adaptador
del recolector y compara mayor y secos (número y serie; sin valores, que algunas fuentes omiten).
- Si no coinciden: se anota en estado.json → avisos.py abre el issue «Datos inconsistentes: X».
- Si la fuente no responde o la lectura es incompleta: «no verificable» (no es una alarma).
- Las fuentes con OCR se excluyen por defecto (variable CAYO_AUDITAR_OCR=1 para incluir 1).
No corrige los datos: solo avisa, para que una persona decida.

Uso: python3 recolectores/auditar.py [fuente ...]
"""
import datetime as dt
import importlib
import json
import os
import random
import sys
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import actualizar as a  # noqa: E402

MUESTRA = 2
MUESTRA_OCR = 1 if os.environ.get("CAYO_AUDITAR_OCR") == "1" else 0
PRESUPUESTO_FUENTE = int(os.environ.get("CAYO_PRESUPUESTO_AUDITORIA", 90))
PRESUPUESTO_TOTAL = 10 * 60
EDAD_MINIMA = 3  # días: los sorteos recién publicados aún pueden corregirse en la fuente


def huella(r):
    """Forma comparable de un resultado: mayor + conjunto de secos (Baloto: bolas de cada juego)."""
    if r is None:
        return None
    if "baloto" in r or "revancha" in r:
        return {j: (tuple(r[j]["numeros"]), r[j]["sb"]) for j in ("baloto", "revancha") if r.get(j)}
    m = r.get("mayor") or {}
    return {"mayor": (m.get("numero"), m.get("serie")),
            "secos": sorted((s["numero"], s["serie"]) for s in r.get("secos", []))}


def diferencias(guardado, vivo):
    """Lista legible de diferencias entre dos huellas ([] si coinciden)."""
    dif = []
    for k in sorted(set(guardado) | set(vivo)):
        g, v = guardado.get(k), vivo.get(k)
        if g == v:
            continue
        if k == "secos" and g is not None and v is not None:
            faltan, sobran = sorted(set(g) - set(v)), sorted(set(v) - set(g))
            dif.append(f"secos: {len(faltan)} guardados no están en vivo {faltan[:3]}; {len(sobran)} nuevos en vivo {sobran[:3]}")
        else:
            dif.append(f"{k}: guardado {g} · en vivo {v}")
    return dif


def lector(fuente):
    """Devuelve (leer(sorteo, valor_guardado) → resultado | None, es_ocr)."""
    if fuente == "baloto":
        def leer(s, v):
            return {"baloto": a.baloto_pagina("baloto", int(s)), "revancha": a.baloto_pagina("revancha", int(s))}
        return leer, False
    if fuente == "medellin":
        return (lambda s, v: a.medellin_sorteo(int(s))), False
    if fuente == "boyaca":
        def leer(s, v):
            r = a.boyaca_fecha(v["fecha"])
            return r[1] if r and str(r[0]) == str(s) else None
        return leer, False
    mod = importlib.import_module(f"loterias.{fuente}")
    preparado = {"ok": False}

    def leer(s, v):
        if not preparado["ok"]:  # algunos módulos llenan cachés (ids internos, cookies) en lista()
            try:
                mod.lista()
            except Exception:
                pass
            preparado["ok"] = True
        return mod.sorteo(int(s), v["fecha"])
    return leer, bool(getattr(mod, "OCR", False))


def muestra(db, fuente, hoy, k):
    corte = (dt.date.fromisoformat(hoy) - dt.timedelta(days=EDAD_MINIMA)).isoformat()
    candidatos = sorted(s for s, v in db["sorteos"].items() if v.get("fecha", "9") <= corte and not v.get("ocr"))
    rnd = random.Random(f"{hoy}|{fuente}")
    return rnd.sample(candidatos, min(k, len(candidatos)))


def auditar_fuente(fuente, hoy, estado, limite_total):
    db = a.cargar(fuente, None)
    if not db or not db.get("sorteos"):
        return None
    leer, es_ocr = lector(fuente)
    k = MUESTRA_OCR if es_ocr else MUESTRA
    elegidos = muestra(db, fuente, hoy, k)
    info = {"revisado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "muestra": elegidos,
            "inconsistentes": {}, "no_verificables": []}
    inicio = time.monotonic()
    for s in elegidos:
        if time.monotonic() - inicio > PRESUPUESTO_FUENTE or time.monotonic() > limite_total:
            info["no_verificables"].append(s)
            continue
        v = db["sorteos"][s]
        try:
            r = leer(s, v)
        except Exception:
            r = None
        time.sleep(a.PAUSA)
        if not r or r.get("completo") is False:
            info["no_verificables"].append(s)
            continue
        dif = diferencias(huella(v), huella(r))
        if dif:
            info["inconsistentes"][s] = {"fecha": v.get("fecha"), "diferencias": dif}
            print(f"  {fuente} {s}: INCONSISTENTE → {dif[0]}", flush=True)
        else:
            print(f"  {fuente} {s}: coincide", flush=True)
    estado.setdefault("auditoria", {})[fuente] = info
    return info


def main(argv):
    hoy = dt.date.today().isoformat()
    estado = a.cargar("estado", {"fuentes": {}})
    fuentes = argv or list(a.JUEGOS)
    limite_total = time.monotonic() + PRESUPUESTO_TOTAL
    for f in fuentes:
        print(f"[auditar {f}]", flush=True)
        try:
            auditar_fuente(f, hoy, estado, limite_total)
        except Exception as e:  # la auditoría nunca debe tumbar la publicación
            print(f"  {f}: no se pudo auditar ({str(e)[:100]})", flush=True)
    (a.DATOS / "estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
