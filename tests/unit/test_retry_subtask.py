from datetime import timedelta
from importlib import import_module

import pytest

from src.application.ports import RetryScheduler
from src.domain.case_state import CaseState
from src.domain.retry import GiveUp, Retry, RetryPolicy
from tests.contratos import comprobar_retry_scheduler
from tests.dobles import FakeCaseStateStore, FakeClock, FakeRetryScheduler


@pytest.fixture
def reloj():
    return FakeClock()


@pytest.fixture
def almacen(reloj):
    almacen = FakeCaseStateStore()
    almacen.set_state("c1", CaseState.PROCESSING, reloj.now())
    return almacen


@pytest.fixture
def planificador(reloj):
    return FakeRetryScheduler(reloj)


@pytest.fixture
def reintentar(almacen, planificador, reloj):
    politica = RetryPolicy(max_attempts=3, base=1, cap=30)
    caso_de_uso = import_module("src.application.retry_subtask").RetrySubtask(
        almacen, planificador, reloj, politica, lambda: 0.0
    )
    return caso_de_uso.execute


def test_el_doble_cumple_el_puerto_y_el_contrato(reloj):
    assert isinstance(FakeRetryScheduler(reloj), RetryScheduler)
    comprobar_retry_scheduler(FakeRetryScheduler(reloj), reloj)


def test_reintento_pasa_el_caso_por_retrying(reintentar, almacen, planificador, reloj):
    decision = reintentar("c1", "s1", 1)
    assert decision == Retry(delay=1.0)
    assert almacen.state("c1") is CaseState.RETRYING
    assert almacen.history("c1")[-1] == (CaseState.RETRYING, reloj.now())
    assert planificador.programadas == [("s1", 1.0)]
    assert almacen.counts("c1") == (0, 0)
    reloj.advance(timedelta(seconds=1))
    assert planificador.promote_due(reloj.now()) == ["s1"]


def test_fallo_agotado_no_reencola_y_reporta_failed(reintentar, almacen, planificador):
    decision = reintentar("c1", "s1", 3)
    assert isinstance(decision, GiveUp)
    assert planificador.programadas == []
    assert almacen.state("c1") is CaseState.PROCESSING
    assert almacen.counts("c1") == (0, 0)


def test_caso_cancelado_no_se_reintenta(reintentar, almacen, planificador, reloj):
    almacen.set_state("c1", CaseState.CANCELLED, reloj.now())
    historial = almacen.history("c1")
    assert reintentar("c1", "s1", 1) is None
    assert almacen.state("c1") is CaseState.CANCELLED
    assert almacen.history("c1") == historial
    assert planificador.programadas == []
