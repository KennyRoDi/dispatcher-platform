import pytest

from scripts.measure import m3_no_bloqueo
from scripts.measure.m3_no_bloqueo import bloque, percentil, resumir


def test_los_bloques_son_deterministas_y_distintos_por_semilla():
    assert bloque(1, 0, 32) == bloque(1, 0, 32)
    assert bloque(1, 0, 32) != bloque(2, 0, 32)
    assert bloque(1, 0, 32) != bloque(1, 1, 32)
    assert len(bloque(1, 5, 1000)) == 1000


def test_percentil_de_lista_vacia_es_none():
    assert percentil([], 50) is None


def test_resume_latencias_y_errores_por_fase():
    filas = [
        {"fase": "antes", "codigo": 200, "latencia_ms": 2.0},
        {"fase": "durante", "codigo": 200, "latencia_ms": 3.0},
        {"fase": "durante", "codigo": 200, "latencia_ms": 9.0},
        {"fase": "durante", "codigo": 0, "latencia_ms": 10000.0},
    ]
    resumen = resumir(filas)
    assert resumen["antes"] == {"n": 1, "errores": 0, "p50_ms": 2.0, "p95_ms": 2.0, "max_ms": 2.0, "media_ms": 2.0}
    assert (resumen["durante"]["n"], resumen["durante"]["errores"], resumen["durante"]["max_ms"]) == (2, 1, 9.0)
    assert resumen["despues"]["n"] == 0 and resumen["despues"]["p50_ms"] is None


def test_si_la_subida_falla_el_muestreo_termina(monkeypatch):
    class Respuesta:
        status_code = 200

    monkeypatch.setattr(m3_no_bloqueo.requests.Session, "get", lambda self, url, timeout: Respuesta())
    monkeypatch.setattr(m3_no_bloqueo.time, "sleep", lambda _s: None)

    def falla(*_):
        raise RuntimeError("complete fallo")

    monkeypatch.setattr(m3_no_bloqueo, "subir_lento", falla)
    with pytest.raises(RuntimeError):
        m3_no_bloqueo.medir("http://x", 1, 1, 1, 1, 0.0, 0.0)
