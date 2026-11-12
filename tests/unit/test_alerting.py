import json
import logging

import pytest

from src.application.alerting import AlertingFindingStore, SafeAlertPublisher, notify_case_closed
from src.application.ports import AlertPublisher, FindingStore
from src.domain.finding import EvidenceRef, Finding, Severity
from tests.dobles import FakeAlertPublisher, FakeFindingStore


def _hallazgo(severidad, posicion="p", detail=""):
    return Finding("amenaza", severidad, 0.9, EvidenceRef("c" * 64, posicion), detail)


class PublicadorRoto:
    def __init__(self, error=None):
        self.error = error or RuntimeError("redis caido")
        self.llamadas = 0

    def publish(self, kind, case_id, detail):
        self.llamadas += 1
        raise self.error


class AlmacenRoto:
    def add(self, case_id, findings):
        raise OSError("disco lleno")

    def list(self, case_id):
        return []


def _seguro(inner, log=None):
    return SafeAlertPublisher(inner, log or logging.getLogger("test.alertas"))


def test_safe_publisher_reenvia_la_alerta():
    interno = FakeAlertPublisher()

    _seguro(interno).publish("incidencia_alta", "c1", "{}")

    assert interno.alertas == [("incidencia_alta", "c1", "{}")]


def test_safe_publisher_cumple_el_puerto():
    assert isinstance(_seguro(FakeAlertPublisher()), AlertPublisher)


def test_safe_publisher_absorbe_y_registra_el_error(caplog):
    with caplog.at_level(logging.ERROR, logger="test.alertas"):
        _seguro(PublicadorRoto()).publish("caso_finalizado", "c1", "{}")

    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_safe_publisher_no_absorbe_base_exception():
    with pytest.raises(KeyboardInterrupt):
        _seguro(PublicadorRoto(KeyboardInterrupt())).publish("k", "c1", "{}")


def test_incidencia_alta_publica_alerta():
    interno, publicador = FakeFindingStore(), FakeAlertPublisher()
    almacen = AlertingFindingStore(interno, publicador)

    almacen.add("c1", [_hallazgo(Severity.ALTA, posicion="msg:7")])

    (kind, case_id, detail), = publicador.alertas
    assert (kind, case_id) == ("incidencia_alta", "c1")
    assert json.loads(detail) == {"categoria": "amenaza", "confianza": 0.9, "sha256": "c" * 64, "posicion": "msg:7"}


def test_hallazgos_baja_y_media_no_publican():
    publicador = FakeAlertPublisher()
    almacen = AlertingFindingStore(FakeFindingStore(), publicador)

    almacen.add("c1", [_hallazgo(Severity.BAJA), _hallazgo(Severity.MEDIA)])

    assert publicador.alertas == []


def test_una_alerta_por_hallazgo_alto_en_orden():
    publicador = FakeAlertPublisher()
    almacen = AlertingFindingStore(FakeFindingStore(), publicador)

    almacen.add("c1", [_hallazgo(Severity.ALTA, "p1"), _hallazgo(Severity.BAJA, "p2"), _hallazgo(Severity.ALTA, "p3")])

    assert [json.loads(d)["posicion"] for _, _, d in publicador.alertas] == ["p1", "p3"]


def test_el_decorador_no_cambia_lo_guardado_ni_listado():
    interno = FakeFindingStore()
    almacen = AlertingFindingStore(interno, FakeAlertPublisher())
    hallazgos = [_hallazgo(Severity.ALTA), _hallazgo(Severity.BAJA)]

    almacen.add("c1", hallazgos)

    assert interno.list("c1") == hallazgos
    assert almacen.list("c1") == hallazgos
    assert almacen.list("otro") == []


def test_el_decorador_cumple_el_puerto():
    assert isinstance(AlertingFindingStore(FakeFindingStore(), FakeAlertPublisher()), FindingStore)


def test_guarda_antes_de_alertar():
    orden = []

    class Almacen(FakeFindingStore):
        def add(self, case_id, findings):
            orden.append("guardar")
            super().add(case_id, findings)

    class Publicador(FakeAlertPublisher):
        def publish(self, kind, case_id, detail):
            orden.append("alertar")

    AlertingFindingStore(Almacen(), Publicador()).add("c1", [_hallazgo(Severity.ALTA)])

    assert orden == ["guardar", "alertar"]


def test_fallo_de_alerta_no_afecta_pipeline(caplog):
    interno, roto = FakeFindingStore(), PublicadorRoto()
    almacen = AlertingFindingStore(interno, _seguro(roto))
    hallazgos = [_hallazgo(Severity.ALTA), _hallazgo(Severity.ALTA, "p2")]

    with caplog.at_level(logging.ERROR, logger="test.alertas"):
        almacen.add("c1", hallazgos)

    assert interno.list("c1") == hallazgos
    assert roto.llamadas == 2
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_fallo_al_guardar_no_publica_alerta():
    publicador = FakeAlertPublisher()
    almacen = AlertingFindingStore(AlmacenRoto(), publicador)

    with pytest.raises(OSError):
        almacen.add("c1", [_hallazgo(Severity.ALTA)])

    assert publicador.alertas == []


@pytest.mark.parametrize("estado", ["completed", "partially_completed", "failed"])
def test_cierre_publica_una_alerta_con_el_estado(estado):
    publicador = FakeAlertPublisher()

    notify_case_closed(publicador, "c1", estado)

    (kind, case_id, detail), = publicador.alertas
    assert (kind, case_id) == ("caso_finalizado", "c1")
    assert estado in detail


@pytest.mark.parametrize("estado", ["cancelled", "processing", "pending"])
def test_estado_no_terminal_o_cancelado_se_rechaza(estado):
    publicador = FakeAlertPublisher()

    with pytest.raises(ValueError):
        notify_case_closed(publicador, "c1", estado)

    assert publicador.alertas == []


def test_fallo_de_alerta_en_cierre_no_propaga():
    roto = PublicadorRoto()

    notify_case_closed(_seguro(roto), "c1", "completed")

    assert roto.llamadas == 1


def test_cierre_con_publicador_sin_envolver_tampoco_propaga(caplog):
    roto = PublicadorRoto()

    with caplog.at_level(logging.ERROR):
        notify_case_closed(roto, "c1", "completed")

    assert roto.llamadas == 1
    assert caplog.records


def test_alertas_no_se_repiten_ante_un_add_once_ignorado():
    interno, publicador = FakeFindingStore(), FakeAlertPublisher()
    almacen = AlertingFindingStore(interno, publicador)
    hallazgos = [_hallazgo(Severity.ALTA, "p1")]

    assert almacen.add_once("c1", "s1", hallazgos) is True
    assert almacen.add_once("c1", "s1", hallazgos) is False

    assert len(publicador.alertas) == 1
    assert interno.list("c1") == hallazgos
