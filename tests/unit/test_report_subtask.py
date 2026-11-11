from datetime import timedelta

import pytest

from src.application.ports import CaseStateStore
from src.application.report_subtask import ReportSubtask
from src.domain.case_state import CaseState
from tests.contratos import comprobar_case_state_store
from tests.dobles import FakeCaseStateStore, FakeClock


@pytest.fixture
def almacen():
    almacen = FakeCaseStateStore()
    almacen.set_state("c1", CaseState.PROCESSING, FakeClock().now())
    return almacen


@pytest.fixture
def reportar(almacen):
    return ReportSubtask(almacen, FakeClock()).execute


def test_el_doble_cumple_el_puerto_y_el_contrato():
    assert isinstance(FakeCaseStateStore(), CaseStateStore)
    comprobar_case_state_store(FakeCaseStateStore())


def test_sin_cerrar_mientras_faltan_reportes(reportar, almacen):
    assert reportar("c1", "s1", "completed", 2) is None
    assert almacen.state("c1") is CaseState.PROCESSING
    assert almacen.counts("c1") == (1, 0)


def test_caso_de_uso_cierra_una_sola_vez(reportar, almacen):
    reportar("c1", "s1", "completed", 2)
    assert reportar("c1", "s2", "completed", 2) is CaseState.COMPLETED
    assert reportar("c1", "s2", "completed", 2) is None
    assert reportar("c1", "s1", "failed", 2) is None
    historial = almacen.history("c1")
    assert [estado for estado, _ in historial].count(CaseState.COMPLETED) == 1
    assert historial[-1][0] is CaseState.COMPLETED
    assert almacen.counts("c1") == (2, 0)


def test_reporte_duplicado_no_cuenta_dos_veces(reportar, almacen):
    reportar("c1", "s1", "completed", 2)
    assert reportar("c1", "s1", "completed", 2) is None
    assert almacen.counts("c1") == (1, 0)
    assert almacen.state("c1") is CaseState.PROCESSING


@pytest.mark.parametrize(
    "resultados, esperado",
    [
        (("completed", "completed"), CaseState.COMPLETED),
        (("failed", "failed"), CaseState.FAILED),
        (("completed", "failed"), CaseState.PARTIALLY_COMPLETED),
    ],
)
def test_estado_final_segun_resultados(almacen, resultados, esperado):
    caso = ReportSubtask(almacen, FakeClock())
    caso.execute("c1", "s1", resultados[0], 2)
    assert caso.execute("c1", "s2", resultados[1], 2) is esperado
    assert almacen.state("c1") is esperado


def test_la_transicion_queda_con_la_hora_del_reloj():
    almacen, reloj = FakeCaseStateStore(), FakeClock()
    almacen.set_state("c1", CaseState.PROCESSING, reloj.now())
    reloj.advance(timedelta(minutes=5))
    ReportSubtask(almacen, reloj).execute("c1", "s1", "completed", 1)
    assert almacen.history("c1")[-1] == (CaseState.COMPLETED, reloj.now())


def test_caso_cancelado_conserva_su_estado(almacen):
    almacen.set_state("c1", CaseState.CANCELLED, FakeClock().now())
    caso = ReportSubtask(almacen, FakeClock())
    assert caso.execute("c1", "s1", "completed", 1) is None
    assert almacen.state("c1") is CaseState.CANCELLED
    assert almacen.counts("c1") == (1, 0)
    assert len(almacen.history("c1")) == 2


def test_caso_en_cola_pasa_por_procesamiento_antes_de_cerrar():
    almacen = FakeCaseStateStore()
    almacen.set_state("c1", CaseState.QUEUED, FakeClock().now())
    assert ReportSubtask(almacen, FakeClock()).execute("c1", "s1", "completed", 1) is CaseState.COMPLETED
    assert [estado for estado, _ in almacen.history("c1")] == [
        CaseState.QUEUED, CaseState.PROCESSING, CaseState.COMPLETED
    ]


def test_caso_en_reintento_cierra_pasando_por_procesamiento():
    almacen = FakeCaseStateStore()
    almacen.set_state("c1", CaseState.RETRYING, FakeClock().now())
    assert ReportSubtask(almacen, FakeClock()).execute("c1", "s1", "failed", 1) is CaseState.FAILED
    assert [estado for estado, _ in almacen.history("c1")][-2:] == [CaseState.PROCESSING, CaseState.FAILED]


def test_resultado_desconocido_se_rechaza(reportar, almacen):
    with pytest.raises(ValueError):
        reportar("c1", "s1", "raro", 1)
    assert almacen.counts("c1") == (0, 0)
