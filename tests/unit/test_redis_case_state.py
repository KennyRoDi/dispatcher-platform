from datetime import datetime, timedelta, timezone

import fakeredis
import pytest

from src.adapters.redis_case_state import RedisCaseState
from src.application.ports import CaseStateStore
from src.domain.case_state import CaseState
from tests.contratos import comprobar_case_state_store

INICIO = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def redis_falso():
    return fakeredis.FakeRedis(decode_responses=True)


def test_case_state_redis_cumple_el_contrato(redis_falso):
    almacen = RedisCaseState(redis_falso)
    assert isinstance(almacen, CaseStateStore)
    comprobar_case_state_store(almacen)


def test_estado_se_escribe_en_el_hash_del_caso_para_el_resto_de_rutas(redis_falso):
    almacen = RedisCaseState(redis_falso)
    almacen.set_state("c1", CaseState.PROCESSING, INICIO)
    assert redis_falso.hget("case:c1", "status") == "processing"


def test_estado_inicial_es_el_que_dejo_el_coordinador(redis_falso):
    redis_falso.hset("case:c1", mapping={"status": "queued"})
    assert RedisCaseState(redis_falso).state("c1") is CaseState.QUEUED


def test_historial_conserva_orden_e_instantes_aunque_se_reabra_el_adaptador(redis_falso):
    RedisCaseState(redis_falso).set_state("c1", CaseState.PROCESSING, INICIO)
    RedisCaseState(redis_falso).set_state("c1", CaseState.FAILED, INICIO + timedelta(seconds=5))
    assert RedisCaseState(redis_falso).history("c1") == [
        (CaseState.PROCESSING, INICIO),
        (CaseState.FAILED, INICIO + timedelta(seconds=5)),
    ]


def test_historial_devuelve_instantes_con_zona_horaria_utc(redis_falso):
    almacen = RedisCaseState(redis_falso)
    almacen.set_state("c1", CaseState.PROCESSING, INICIO)
    (_, instante), = almacen.history("c1")
    assert instante.utcoffset() == timedelta(0)


def test_reporte_duplicado_no_cambia_el_conteo_aunque_cambie_el_resultado(redis_falso):
    almacen = RedisCaseState(redis_falso)
    assert almacen.mark_reported("c1", "s1", "completed") is True
    assert almacen.mark_reported("c1", "s1", "failed") is False
    assert almacen.counts("c1") == (1, 0)


def test_casos_distintos_no_comparten_reportes(redis_falso):
    almacen = RedisCaseState(redis_falso)
    assert almacen.mark_reported("c1", "s1", "completed") is True
    assert almacen.mark_reported("c2", "s1", "completed") is True
    assert almacen.counts("c2") == (1, 0)


def test_mark_reported_rechaza_resultado_desconocido_sin_registrarlo(redis_falso):
    almacen = RedisCaseState(redis_falso)
    with pytest.raises(ValueError):
        almacen.mark_reported("c1", "s1", "raro")
    assert almacen.counts("c1") == (0, 0)
    assert almacen.mark_reported("c1", "s1", "completed") is True


def test_estado_con_valor_corrupto_no_rompe_la_lectura(redis_falso):
    redis_falso.hset("case:c1", mapping={"status": "inventado"})
    assert RedisCaseState(redis_falso).state("c1") is None


def test_segundo_cierre_terminal_no_se_aplica_ni_duplica_historial(redis_falso):
    almacen = RedisCaseState(redis_falso)
    assert almacen.set_state("c1", CaseState.PROCESSING, INICIO) is True
    assert almacen.set_state("c1", CaseState.COMPLETED, INICIO) is True
    assert almacen.set_state("c1", CaseState.FAILED, INICIO) is False
    assert almacen.state("c1") is CaseState.COMPLETED
    assert [e for e, _ in almacen.history("c1")] == [CaseState.PROCESSING, CaseState.COMPLETED]


def test_identificador_de_subtarea_repetido_con_hilos_cuenta_una_vez(redis_falso):
    almacen = RedisCaseState(redis_falso)
    for _ in range(3):
        almacen.mark_reported("c1", "s1", "completed")
    assert almacen.counts("c1") == (1, 0)
