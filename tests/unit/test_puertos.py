from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.application import ports
from src.domain.chat_message import ChatMessage
from src.domain.priority import Priority
from src.domain.resources import ResourceUsage
from src.domain.subtask import ContentKind, Subtask
from tests import contratos, dobles


@pytest.mark.parametrize("puerto, doble", [
    (ports.Clock, dobles.FakeClock()),
    (ports.Analyzer, dobles.FakeAnalyzer()),
    (ports.ObjectStore, dobles.FakeObjectStore()),
    (ports.WorkQueue, dobles.FakeWorkQueue()),
    (ports.AlertPublisher, dobles.FakeAlertPublisher()),
    (ports.FindingStore, dobles.FakeFindingStore()),
    (ports.CustodyLog, dobles.FakeCustodyLog()),
    (ports.RoutingPolicy, dobles.FakeRoutingPolicy()),
    (ports.ResourceReader, dobles.FakeResourceReader()),
    (ports.ConversationParser, dobles.FakeConversationParser()),
])
def test_cada_doble_cumple_su_puerto(puerto, doble):
    assert isinstance(doble, puerto)


def test_cola_doble_cumple_el_contrato():
    contratos.comprobar_work_queue(lambda capacidad: dobles.FakeWorkQueue(capacidad))


def test_almacen_doble_cumple_el_contrato():
    contratos.comprobar_object_store(dobles.FakeObjectStore())


def test_hallazgos_dobles_cumplen_el_contrato():
    contratos.comprobar_finding_store(dobles.FakeFindingStore())


def test_reloj_doble_avanza_sin_esperar():
    reloj = dobles.FakeClock()
    inicio = reloj.now()
    reloj.advance(timedelta(seconds=5))
    assert reloj.now() - inicio == timedelta(seconds=5)


def test_subtarea_viaja_serializada_sin_perder_datos():
    original = Subtask("s1", "c1", ContentKind.AUDIO, "abc", Priority.CRITICA,
                       datetime(2026, 11, 3, tzinfo=timezone.utc), attempts=2, node_class="gpu")
    assert Subtask.from_dict(original.to_dict()) == original


def test_memoria_disponible_nunca_es_negativa():
    assert ResourceUsage("w1", memory_current=5, memory_max=3).memory_available == 0
    assert ResourceUsage("w1", memory_current=1, memory_max=3).memory_available == 2


def test_mensaje_exige_hora_con_zona():
    with pytest.raises(ValueError):
        ChatMessage(datetime(2026, 11, 3), "Ana", "hola", "linea 1")


def test_el_ejemplo_de_exportacion_esta_disponible():
    assert Path("tests/datos/chat_whatsapp.txt").read_text(encoding="utf-8").count(" - ") >= 3
