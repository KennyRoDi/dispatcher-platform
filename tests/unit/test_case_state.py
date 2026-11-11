import pytest

from src.domain.case_state import Barrier, CaseState, InvalidTransition, final_state, transition

PERMITIDAS = {
    (CaseState.QUEUED, CaseState.PROCESSING),
    (CaseState.QUEUED, CaseState.CANCELLED),
    (CaseState.PROCESSING, CaseState.COMPLETED),
    (CaseState.PROCESSING, CaseState.PARTIALLY_COMPLETED),
    (CaseState.PROCESSING, CaseState.FAILED),
    (CaseState.PROCESSING, CaseState.RETRYING),
    (CaseState.PROCESSING, CaseState.CANCELLED),
    (CaseState.RETRYING, CaseState.PROCESSING),
    (CaseState.RETRYING, CaseState.FAILED),
    (CaseState.RETRYING, CaseState.CANCELLED),
}
TERMINALES = {CaseState.COMPLETED, CaseState.PARTIALLY_COMPLETED, CaseState.FAILED, CaseState.CANCELLED}


def test_existen_los_siete_estados():
    assert {e.value for e in CaseState} == {
        "queued", "processing", "completed", "partially_completed", "failed", "retrying", "cancelled"
    }


@pytest.mark.parametrize("actual", list(CaseState))
@pytest.mark.parametrize("destino", list(CaseState))
def test_tabla_de_transiciones(actual, destino):
    if (actual, destino) in PERMITIDAS:
        assert transition(actual, destino) == destino
    else:
        with pytest.raises(InvalidTransition):
            transition(actual, destino)


@pytest.mark.parametrize("terminal", sorted(TERMINALES, key=lambda e: e.value))
def test_transicion_invalida_se_rechaza(terminal):
    for destino in CaseState:
        with pytest.raises(InvalidTransition):
            transition(terminal, destino)


@pytest.mark.parametrize(
    ("completadas", "fallidas", "esperado"),
    [
        (3, 0, CaseState.COMPLETED),
        (0, 3, CaseState.FAILED),
        (2, 1, CaseState.PARTIALLY_COMPLETED),
        (1, 2, CaseState.PARTIALLY_COMPLETED),
    ],
)
def test_estado_final_por_combinacion(completadas, fallidas, esperado):
    assert final_state(completadas, fallidas) == esperado


def test_estado_final_de_caso_cancelado_no_cambia():
    assert final_state(2, 1, actual=CaseState.CANCELLED) == CaseState.CANCELLED


def test_barrier_no_cuenta_dos_veces():
    barrier = Barrier(expected=2)
    assert barrier.report("s1", "completed") is True
    assert barrier.report("s1", "completed") is False
    assert barrier.is_closed() is False
    assert barrier.report("s2", "failed") is True
    assert barrier.is_closed() is True


def test_barrier_duplicado_tras_cierre_no_reabre_ni_cambia():
    barrier = Barrier(expected=1)
    assert barrier.report("s1", "completed") is True
    assert barrier.report("s1", "failed") is False
    assert barrier.is_closed() is True


def test_barrier_sin_reportes_esta_abierto():
    assert Barrier(expected=3).is_closed() is False


def test_barrier_duplicado_con_otro_resultado_conserva_el_primero():
    barrier = Barrier(expected=1)
    barrier.report("s1", "completed")
    barrier.report("s1", "failed")
    assert barrier._outcomes == {"s1": "completed"}


def test_barrier_cierre_no_depende_del_orden():
    for orden in (["a", "b", "c"], ["c", "a", "b"], ["b", "b", "c", "a", "a"]):
        barrier = Barrier(expected=3)
        for subtask_id in orden:
            barrier.report(subtask_id, "completed")
        assert barrier.is_closed() is True


def test_barrier_caso_vacio_cierra_de_inmediato():
    assert Barrier(expected=0).is_closed() is True


def test_barrier_cierre_una_sola_vez_por_reportes_nuevos():
    barrier = Barrier(expected=2)
    nuevos = [barrier.report(s, "completed") for s in ("a", "b", "a", "b", "a")]
    assert nuevos == [True, True, False, False, False]


@pytest.mark.parametrize("estado", list(CaseState))
def test_transicion_a_si_mismo_se_rechaza(estado):
    with pytest.raises(InvalidTransition):
        transition(estado, estado)


def test_caso_cancelado_no_se_reabre_por_conteos():
    assert final_state(0, 0, actual=CaseState.CANCELLED) == CaseState.CANCELLED
    assert final_state(0, 5, actual=CaseState.CANCELLED) == CaseState.CANCELLED


def test_estado_final_de_cualquier_conteo_es_terminal():
    for completadas in range(4):
        for fallidas in range(4):
            assert final_state(completadas, fallidas) in TERMINALES
