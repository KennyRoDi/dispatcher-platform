"""Pruebas unitarias del escenario de reinicio del coordinador (F-35).

TDD: pruebas en rojo, sin implementacion aun. Sin red, sin sleep.
"""
import pytest


def coordinator_restart():
    from importlib import import_module
    return import_module("scenarios.coordinator_restart")


class TestEvaluar:
    def test_cumple_si_los_mismos_subtask_id_siguen_tras_el_reinicio(self):
        antes = {"s1": "pending", "s2": "running", "s3": "completed"}
        despues = {"s1": "pending", "s2": "running", "s3": "completed"}
        veredicto = coordinator_restart().evaluar(creadas=3, contadas_antes=antes, contadas_despues=despues)
        assert veredicto["cumple"] is True
        assert veredicto["problemas"] == []

    def test_detecta_subtarea_perdida_tras_el_reinicio(self):
        antes = {"s1": "pending", "s2": "running"}
        despues = {"s1": "pending"}
        veredicto = coordinator_restart().evaluar(creadas=2, contadas_antes=antes, contadas_despues=despues)
        assert veredicto["cumple"] is False
        assert any("perdid" in p for p in veredicto["problemas"])

    def test_detecta_subtarea_duplicada_o_fantasma_tras_el_reinicio(self):
        antes = {"s1": "pending"}
        despues = {"s1": "pending", "s2": "pending"}
        veredicto = coordinator_restart().evaluar(creadas=1, contadas_antes=antes, contadas_despues=despues)
        assert veredicto["cumple"] is False
        assert any("duplicad" in p for p in veredicto["problemas"])

    def test_detecta_discrepancia_contra_el_total_creado(self):
        antes = {"s1": "pending", "s2": "pending"}
        despues = {"s1": "pending", "s2": "pending"}
        veredicto = coordinator_restart().evaluar(creadas=3, contadas_antes=antes, contadas_despues=despues)
        assert veredicto["cumple"] is False
        assert any("3" in p and "2" in p for p in veredicto["problemas"])


class TestTiempoDeArranque:
    def test_tiempo_de_arranque_es_la_diferencia_entre_instantes(self):
        assert coordinator_restart().tiempo_de_arranque(inicio=10.0, listo=10.35) == pytest.approx(0.35)

    def test_tiempo_de_arranque_no_puede_ser_negativo(self):
        with pytest.raises(ValueError):
            coordinator_restart().tiempo_de_arranque(inicio=10.0, listo=9.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
