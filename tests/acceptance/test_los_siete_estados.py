import fakeredis
import pytest
from fastapi.testclient import TestClient

import src.coordinator.main as main
from src.adapters.redis_case_state import RedisCaseState
from src.coordinator import conexion
from src.domain.case_state import CaseState
from tests.ayudas_cierre import crear_caso, reportar

pytestmark = [pytest.mark.acceptance, pytest.mark.usefixtures("sin_autorizacion")]


@pytest.fixture
def entorno(monkeypatch):
    redis_falso = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conexion, "redis_client", redis_falso)
    return TestClient(main.app), redis_falso


def estado(redis_falso, case_id):
    return RedisCaseState(redis_falso).state(case_id)


def test_queued_al_crear_el_caso(entorno):
    cliente, redis_falso = entorno
    case_id, _ = crear_caso(cliente)
    assert estado(redis_falso, case_id) is CaseState.QUEUED


def test_processing_mientras_faltan_subtareas(entorno):
    cliente, redis_falso = entorno
    case_id, (s1, _) = crear_caso(cliente, 2)
    reportar(cliente, case_id, s1)
    assert estado(redis_falso, case_id) is CaseState.PROCESSING


def test_completed_con_todas_exitosas(entorno):
    cliente, redis_falso = entorno
    case_id, ids = crear_caso(cliente, 2)
    for sid in ids:
        reportar(cliente, case_id, sid)
    assert estado(redis_falso, case_id) is CaseState.COMPLETED


def test_partially_completed_con_exitosas_y_fallidas(entorno):
    cliente, redis_falso = entorno
    case_id, (s1, s2) = crear_caso(cliente, 2)
    reportar(cliente, case_id, s1)
    reportar(cliente, case_id, s2, status="failed", error="x", error_type="E")
    assert estado(redis_falso, case_id) is CaseState.PARTIALLY_COMPLETED


def test_failed_con_todas_fallidas(entorno):
    cliente, redis_falso = entorno
    case_id, ids = crear_caso(cliente, 2)
    for sid in ids:
        reportar(cliente, case_id, sid, status="failed", error="x", error_type="E")
    assert estado(redis_falso, case_id) is CaseState.FAILED


def test_cancelled_y_no_cambia_con_reportes_tardios(entorno):
    cliente, redis_falso = entorno
    case_id, (s1, _) = crear_caso(cliente, 2)
    assert cliente.post(f"/cases/{case_id}/cancel").status_code == 200
    reportar(cliente, case_id, s1)
    assert estado(redis_falso, case_id) is CaseState.CANCELLED


def test_retrying_cuando_el_reaper_reencola_y_luego_completa(entorno):
    cliente, redis_falso = entorno
    case_id, (s1,) = crear_caso(cliente)
    redis_falso.hset(f"case:{case_id}", "status", "retrying")
    assert estado(redis_falso, case_id) is CaseState.RETRYING
    reportar(cliente, case_id, s1)
    assert estado(redis_falso, case_id) is CaseState.COMPLETED


def test_el_historial_de_un_caso_cerrado_termina_en_su_estado_final_una_sola_vez(entorno):
    cliente, redis_falso = entorno
    case_id, (s1,) = crear_caso(cliente)
    reportar(cliente, case_id, s1)
    reportar(cliente, case_id, s1)
    estados = [e for e, _ in RedisCaseState(redis_falso).history(case_id)]
    assert estados[-1] is CaseState.COMPLETED
    assert estados.count(CaseState.COMPLETED) == 1
