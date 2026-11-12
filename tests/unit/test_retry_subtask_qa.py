import pytest

from src.application.retry_subtask import RetrySubtask
from src.domain.case_state import CaseState, InvalidTransition
from src.domain.retry import GiveUp, Retry, RetryPolicy
from tests.dobles import FakeCaseStateStore, FakeClock, FakeRetryScheduler


def armar(estado, max_attempts=3):
    reloj = FakeClock()
    almacen = FakeCaseStateStore()
    if estado is not None:
        almacen.set_state("c1", estado, reloj.now())
    planificador = FakeRetryScheduler(reloj)
    caso = RetrySubtask(almacen, planificador, reloj, RetryPolicy(max_attempts, 1, 30), lambda: 0.0)
    return caso, almacen, planificador


@pytest.mark.parametrize(
    "estado", [CaseState.COMPLETED, CaseState.FAILED, CaseState.PARTIALLY_COMPLETED, CaseState.QUEUED]
)
def test_estado_sin_transicion_a_retrying_se_rechaza_sin_programar(estado):
    caso, almacen, planificador = armar(estado)
    historial = almacen.history("c1")
    with pytest.raises(InvalidTransition):
        caso.execute("c1", "s1", 1)
    assert planificador.programadas == []
    assert almacen.history("c1") == historial


def test_reintento_repetido_en_retrying_no_duplica_la_transicion():
    caso, almacen, planificador = armar(CaseState.PROCESSING)
    caso.execute("c1", "s1", 1)
    caso.execute("c1", "s1", 2)
    estados = [e for e, _ in almacen.history("c1")]
    assert estados == [CaseState.PROCESSING, CaseState.RETRYING]
    assert [d for _, d in planificador.programadas] == [1.0, 2.0]


def test_subtarea_repetida_deja_un_solo_vencimiento():
    caso, almacen, planificador = armar(CaseState.PROCESSING)
    caso.execute("c1", "s1", 1)
    caso.execute("c1", "s1", 1)
    assert len(planificador._vencimientos) == 1


def test_agotado_en_retrying_devuelve_giveup_sin_tocar_estado_ni_cola():
    caso, almacen, planificador = armar(CaseState.RETRYING)
    historial = almacen.history("c1")
    assert isinstance(caso.execute("c1", "s1", 3), GiveUp)
    assert almacen.history("c1") == historial
    assert planificador.programadas == []


def test_agotado_en_estado_terminal_no_lanza():
    caso, _, planificador = armar(CaseState.FAILED)
    assert isinstance(caso.execute("c1", "s1", 3), GiveUp)
    assert planificador.programadas == []


def test_con_n_uno_el_primer_fallo_no_reintenta():
    caso, almacen, planificador = armar(CaseState.PROCESSING, max_attempts=1)
    assert isinstance(caso.execute("c1", "s1", 1), GiveUp)
    assert almacen.state("c1") is CaseState.PROCESSING
    assert planificador.programadas == []


def test_cancelado_no_se_reintenta_aunque_hayan_agotado_los_intentos():
    caso, almacen, planificador = armar(CaseState.CANCELLED)
    assert caso.execute("c1", "s1", 99) is None
    assert planificador.programadas == []


def test_reintento_programa_la_espera_calculada_y_solo_vence_despues():
    caso, _, planificador = armar(CaseState.PROCESSING)
    decision = caso.execute("c1", "s1", 2)
    assert decision == Retry(delay=2.0)
    reloj = FakeClock()
    assert planificador.promote_due(reloj.now()) == []


@pytest.mark.xfail(strict=True, raises=AttributeError, reason="DEFECTO QA: caso inexistente (state None) lanza AttributeError en transition (case_state.py f-string current.value) en vez de InvalidTransition")
def test_caso_inexistente_se_rechaza_con_transicion_invalida():
    caso, _, planificador = armar(None)
    with pytest.raises(InvalidTransition):
        caso.execute("c1", "s1", 1)
    assert planificador.programadas == []
