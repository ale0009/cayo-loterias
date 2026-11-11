#!/usr/bin/env python3
"""Revisa datos/estado.json después de recolectar y escribe en stdout las acciones de aviso.

Formato de cada línea (lo consume el workflow con `gh issue`):
  ABRIR<TAB>título<TAB>cuerpo     → abrir un issue si no hay uno abierto con ese título
  CERRAR<TAB>título<TAB>comentario → cerrar el issue con ese título si está abierto
Así la herramienta avisa sola cuando una fuente se cae o cambia de formato, y cierra el aviso
cuando se recupera. Nadie tiene que vigilarla.
"""
import json
import pathlib

UMBRAL = 3  # noches seguidas fallando antes de avisar
estado = json.loads((pathlib.Path(__file__).resolve().parent.parent / "datos" / "estado.json").read_text())

for fuente, info in sorted(estado.get("fuentes", {}).items()):
    titulo = f"Fuente caída: {fuente}"
    if info.get("fallos_seguidos", 0) >= UMBRAL:
        cuerpo = (f"El recolector de **{fuente}** lleva {info['fallos_seguidos']} noches seguidas fallando.\\n\\n"
                  f"Último error: `{info.get('error', '¿?')}`\\n\\nÚltima vez que funcionó: {info.get('ultimo_ok', 'nunca')}.\\n\\n"
                  "Lo más probable es que la página de la lotería cambió de formato o de dirección. "
                  f"Revisa `recolectores/` y su prueba. Este aviso se cierra solo cuando la fuente vuelva a responder.")
        print(f"ABRIR\t{titulo}\t{cuerpo}")
    elif info.get("ok"):
        print(f"CERRAR\t{titulo}\tLa fuente volvió a responder el {info.get('revisado')}. Cerrado automáticamente.")

for fuente, sorteos in sorted(estado.get("ilegibles", {}).items()):
    titulo = f"Sorteos ilegibles: {fuente}"
    if sorteos:
        lista = ", ".join(f"{s} ({v['fecha']})" for s, v in sorted(sorteos.items()))
        print(f"ABRIR\t{titulo}\tNo se pudieron leer tras varias noches: {lista}. "
              "La página remite a la fuente oficial para esos sorteos. Si el formato de las imágenes cambió, hay que ajustar el lector.")
    else:
        print(f"CERRAR\t{titulo}\tYa no hay sorteos ilegibles.")
