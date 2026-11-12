"""Pruebas unitarias del escenario de caida de worker (F-34).

TDD: pruebas en rojo, sin implementacion aun. Sin red, sin sleep: solo
funciones puras sobre datos sinteticos.
"""
import pytest


def worker_crash():
    from importlib import import_module
    return import_module("scenarios.worker_crash")


class TestEvaluar:
    def test_cumple_si_todo_se_reasigna_sin_perdidas_ni_duplicadas(self):
        veredicto = worker_crash().evaluar(
            creadas=5, terminadas=5, perdidas=0, duplicadas=0, estado_caso="completed"
        )
        assert veredicto["cumple"] is True
        assert veredicto["problemas"] == []

    @pytest.mark.parametrize(
        "creadas, terminadas, perdidas, duplicadas, estado, fragmento",
        [
            (5, 4, 0, 0, "completed", "perdid"),
            (5, 5, 0, 1, "completed", "duplicad"),
            (5, 5, 0, 0, "failed", "completed"),
            (3, 5, 0, 0, "completed", "más terminadas que creadas"),
        ],
    )
    def test_senala_cada_incumplimiento(self, creadas, terminadas, perdidas, duplicadas, estado, fragmento):
        veredicto = worker_crash().evaluar(
            creadas=creadas, terminadas=terminadas, perdidas=perdidas,
            duplicadas=duplicadas, estado_caso=estado,
        )
        assert veredicto["cumple"] is False
        assert any(fragmento in p for p in veredicto["problemas"])


class TestTiempos:
    def test_tiempo_deteccion_es_cuando_el_worker_deja_de_estar_vivo(self):
        muestras = [(0.0, True), (5.0, True), (10.0, True), (15.5, False), (16.0, False)]
        assert worker_crash().tiempo_deteccion(muestras) == pytest.approx(15.5)

    def test_tiempo_deteccion_sin_caida_es_none(self):
        muestras = [(0.0, True), (5.0, True)]
        assert worker_crash().tiempo_deteccion(muestras) is None

    def test_tiempo_reasignacion_es_cuando_vuelve_a_la_cola_original(self):
        muestras = [(15.5, False), (20.0, False), (24.2, True), (25.0, True)]
        assert worker_crash().tiempo_reasignacion(muestras) == pytest.approx(24.2)

    def test_tiempo_reasignacion_sin_reasignar_es_none(self):
        muestras = [(15.5, False), (20.0, False)]
        assert worker_crash().tiempo_reasignacion(muestras) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
