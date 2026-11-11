import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.redis_case_state import RedisCaseState
from src.coordinator import conexion
from src.domain.case_state import CaseState
from tests.ayudas_cierre import crear_caso, reportar

pytestmark = pytest.mark.usefixtures("sin_autorizacion")


@pytest.fixture
def entorno(monkeypatch):
    redis_falso = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", redis_falso)
    return TestClient(main.app), redis_falso


def test_reporte_duplicado_responde_idempotente_y_no_duplica_historial(entorno):
    cliente, redis_falso = entorno
    case_id, (s1,) = crear_caso(cliente)
    primero = reportar(cliente, case_id, s1)
    segundo = reportar(cliente, case_id, s1)
    assert primero.status_code == segundo.status_code == 200
    assert segundo.json()["case_status"] == "completed"
    historial = RedisCaseState(redis_falso).history(case_id)
    assert [e for e, _ in historial].count(CaseState.COMPLETED) == 1


def test_el_cierre_deja_historial_con_processing_antes_del_estado_final(entorno):
    cliente, redis_falso = entorno
    case_id, (s1,) = crear_caso(cliente)
    reportar(cliente, case_id, s1)
    estados = [e for e, _ in RedisCaseState(redis_falso).history(case_id)]
    assert estados == [CaseState.PROCESSING, CaseState.COMPLETED]


def test_resultado_invalido_sigue_rechazado_con_422_sin_marcar_la_subtarea(entorno):
    cliente, redis_falso = entorno
    case_id, (s1,) = crear_caso(cliente)
    assert reportar(cliente, case_id, s1, status="raro").status_code == 422
    assert reportar(cliente, case_id, s1).status_code == 200
    assert RedisCaseState(redis_falso).counts(case_id) == (1, 0)


def test_respuesta_del_reporte_incluye_el_estado_del_caso(entorno):
    cliente, _ = entorno
    case_id, (s1, _s2) = crear_caso(cliente, 2)
    cuerpo = reportar(cliente, case_id, s1).json()
    assert cuerpo["case_status"] != "completed"
    assert cuerpo["subtask_status"] == "completed"
