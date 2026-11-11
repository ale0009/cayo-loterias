"""Pruebas de la auditoría nocturna sin red (módulo de lotería falso)."""
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
import auditar  # noqa: E402

HOY = dt.date.today()
VIEJA = (HOY - dt.timedelta(days=10)).isoformat()


def res(m="1234", s="001", secos=(("5555", "002"),)):
    return {"mayor": {"numero": m, "serie": s}, "secos": [{"numero": n, "serie": se, "valor": 1} for n, se in secos]}


class Auditoria(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        a.DATOS = pathlib.Path(self.tmp.name)
        a.PAUSA = 0

    def tearDown(self):
        self.tmp.cleanup()

    def preparar(self, vivo, guardados=None, ocr=False):
        guardados = guardados or {"10": {"fecha": VIEJA, **res()}}
        (a.DATOS / "falsa.json").write_text(json.dumps({"sorteos": guardados}))
        m = types.ModuleType("loterias.falsa")
        m.lista = lambda: []
        m.sorteo = lambda s, f: vivo(s) if callable(vivo) else vivo
        m.OCR = ocr
        sys.modules["loterias.falsa"] = m

    def correr(self):
        estado = {}
        auditar.auditar_fuente("falsa", HOY.isoformat(), estado, auditar.time.monotonic() + 60)
        return estado["auditoria"]["falsa"]

    def test_coincide(self):
        self.preparar(res())
        info = self.correr()
        self.assertEqual(info["muestra"], ["10"])
        self.assertEqual(info["inconsistentes"], {})

    def test_difiere_mayor_y_secos(self):
        self.preparar(res(m="9999", secos=(("5555", "002"), ("7777", "003"))))
        info = self.correr()
        dif = info["inconsistentes"]["10"]["diferencias"]
        self.assertTrue(any("mayor" in d for d in dif))
        self.assertTrue(any("secos" in d for d in dif))

    def test_sin_respuesta_no_es_alarma(self):
        self.preparar(None)
        info = self.correr()
        self.assertEqual(info["inconsistentes"], {})
        self.assertEqual(info["no_verificables"], ["10"])

    def test_excluye_ocr_y_sorteos_recientes(self):
        self.preparar(res(m="0000"), ocr=True)
        self.assertEqual(self.correr()["muestra"], [], "OCR excluido por defecto")
        self.preparar(res(m="0000"), guardados={"11": {"fecha": HOY.isoformat(), **res()}})
        self.assertEqual(self.correr()["muestra"], [], "un sorteo de hoy todavía no se audita")

    def test_muestra_reproducible(self):
        db = {"sorteos": {str(i): {"fecha": VIEJA} for i in range(20)}}
        self.assertEqual(auditar.muestra(db, "x", HOY.isoformat(), 2), auditar.muestra(db, "x", HOY.isoformat(), 2))

    def test_huella_baloto(self):
        g = {"baloto": {"numeros": [1, 2, 3, 4, 5], "sb": 6, "premios": {}}, "revancha": {"numeros": [7, 8, 9, 10, 11], "sb": 2}}
        v = {"baloto": {"numeros": [1, 2, 3, 4, 5], "sb": 6}, "revancha": {"numeros": [7, 8, 9, 10, 12], "sb": 2}}
        self.assertEqual(len(auditar.diferencias(auditar.huella(g), auditar.huella(v))), 1)

    def test_avisos_de_auditoria(self):
        estado = {"fuentes": {}, "auditoria": {
            "valle": {"muestra": ["1"], "inconsistentes": {"1": {"fecha": "2026-01-01", "diferencias": ["mayor: x"]}}, "no_verificables": []},
            "huila": {"muestra": ["2"], "inconsistentes": {}, "no_verificables": [], "revisado": "2026-11-11T05:00"}}}
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "recolectores").mkdir(); (pathlib.Path(d) / "datos").mkdir()
            (pathlib.Path(d) / "datos" / "estado.json").write_text(json.dumps(estado))
            (pathlib.Path(d) / "recolectores" / "avisos.py").write_text((RAIZ / "recolectores" / "avisos.py").read_text())
            out = subprocess.run([sys.executable, str(pathlib.Path(d) / "recolectores" / "avisos.py")], capture_output=True, text=True, check=True).stdout
        self.assertIn("ABRIR\tDatos inconsistentes: valle", out)
        self.assertIn("CERRAR\tDatos inconsistentes: huila", out)


if __name__ == "__main__":
    unittest.main()
