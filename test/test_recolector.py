"""Pruebas del recolector sin red: reintentos, sorteos ilegibles, presupuesto de tiempo y avisos."""
import datetime as dt
import json
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "recolectores"))
import actualizar as a  # noqa: E402

HOY = dt.date.today()


def falso(sorteos):
    """Módulo de lotería falso: sorteos = {numero: resultado | None | 'incompleto' | 'error'}."""
    m = types.ModuleType("loterias.falsa")
    m.NOMBRE, m.FUENTE = "Falsa", "https://ejemplo.invalid"
    m.lista = lambda: [(s, (HOY - dt.timedelta(days=7 * i)).isoformat()) for i, s in enumerate(sorted(sorteos, reverse=True))]

    def sorteo(s, fecha):
        r = sorteos[s]
        if r == "error":
            raise ValueError("página rara")
        if r == "incompleto":
            return {"completo": False}
        return r
    m.sorteo = sorteo
    return m


class Recolector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        a.DATOS = pathlib.Path(self.tmp.name)
        a.PAUSA = 0
        a.ESTADO.clear()
        a.ESTADO.update({"fuentes": {}})

    def tearDown(self):
        self.tmp.cleanup()

    def correr(self, mod):
        sys.modules["loterias.falsa"] = mod
        return a.actualizar_modulo("falsa", (HOY - dt.timedelta(days=400)).isoformat())

    def test_guarda_y_filtra_campos(self):
        ok = {"mayor": {"numero": "1234", "serie": "001"}, "secos": [], "texto_ocr": "NOMBRE Y CÉDULA"}
        self.assertEqual(self.correr(falso({10: ok})), 1)
        guardado = json.loads((a.DATOS / "falsa.json").read_text())["sorteos"]["10"]
        self.assertNotIn("texto_ocr", guardado)  # nunca se guarda texto crudo

    def test_reintenta_y_luego_marca_ilegible(self):
        mod = falso({11: "incompleto", 12: "error"})
        for noche in range(a.REINTENTOS):
            self.correr(mod)
        self.assertIn("11", a.ESTADO["ilegibles"]["falsa"])
        self.assertIn("12", a.ESTADO["ilegibles"]["falsa"])
        llamadas = []
        mod.sorteo = lambda s, f: llamadas.append(s)
        self.correr(mod)
        self.assertEqual(llamadas, [], "un sorteo ilegible no se vuelve a pedir")

    def test_presupuesto_de_tiempo(self):
        viejo = a.PRESUPUESTO
        a.PRESUPUESTO = -1  # sin tiempo: no debe pedir nada, pero sí guardar el archivo
        try:
            self.assertEqual(self.correr(falso({13: {"mayor": {"numero": "1", "serie": "1"}, "secos": []}})), 0)
            self.assertTrue((a.DATOS / "falsa.json").exists())
        finally:
            a.PRESUPUESTO = viejo

    def test_corrige_anio_mal_digitado(self):
        futuro = (HOY.replace(year=HOY.year + 1) - dt.timedelta(days=1)).isoformat()
        r = a.corregir_fecha({"fecha": futuro})
        self.assertEqual(r["fecha"][:4], str(HOY.year))
        self.assertIn("se corrigió", r["aviso"])

    def test_fechas_con_errores_de_ocr(self):
        self.assertEqual(a.fecha_es("15 de junlo de 2026"), "2026-06-15")
        self.assertEqual(a.fecha_es("1 de setiembre de 2026"), "2026-09-01")
        self.assertIsNone(a.fecha_es("31 de junio de 2026"))
        self.assertIsNone(a.fecha_es("3 de xyz de 2026"))

    def test_avisos(self):
        estado = {"fuentes": {"valle": {"ok": False, "fallos_seguidos": 3, "error": "HTTP 500"},
                              "huila": {"ok": True, "revisado": "hoy"}},
                  "ilegibles": {"manizales": {"4999": {"fecha": "2026-11-04"}}}}
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "recolectores").mkdir(); (pathlib.Path(d) / "datos").mkdir()
            (pathlib.Path(d) / "datos" / "estado.json").write_text(json.dumps(estado))
            script = (RAIZ / "recolectores" / "avisos.py").read_text()
            (pathlib.Path(d) / "recolectores" / "avisos.py").write_text(script)
            out = subprocess.run([sys.executable, str(pathlib.Path(d) / "recolectores" / "avisos.py")],
                                 capture_output=True, text=True, check=True).stdout
        self.assertIn("ABRIR\tFuente caída: valle", out)
        self.assertIn("CERRAR\tFuente caída: huila", out)
        self.assertIn("ABRIR\tSorteos ilegibles: manizales", out)


if __name__ == "__main__":
    unittest.main()
