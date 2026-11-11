"""Pruebas de conformidad: todo adaptador real de un puerto debe pasarlas, igual que su doble."""
import io
from datetime import datetime, timedelta, timezone

import pytest

from src.application.ports import AlertPublisher, ResourceReader
from src.domain.alert_policy import StoredAlert
from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.priority import Priority
from src.domain.resources import ResourceUsage
from src.domain.subtask import ContentKind, QueueFull, Subtask


def subtarea(identificador="s1"):
    return Subtask(identificador, "c1", ContentKind.TEXT, "abc", Priority.ALTA, datetime(2026, 11, 3, tzinfo=timezone.utc))


def comprobar_work_queue(crear):
    """`crear(capacidad)` devuelve una cola vacía con ese límite por cola."""
    cola = crear(1)
    assert cola.take("q", "w1", 0) is None
    assert cola.has_capacity("q")
    cola.enqueue("q", subtarea())
    assert not cola.has_capacity("q")
    with pytest.raises(QueueFull):
        cola.enqueue("q", subtarea("s2"))
    tomada = cola.take("q", "w1", 0)
    assert tomada == subtarea()
    assert cola.has_capacity("q")
    assert cola.in_flight("w1") == [subtarea()]
    cola.acknowledge("w1", tomada)
    assert cola.in_flight("w1") == []


def comprobar_object_store(almacen):
    assert not almacen.exists("abc")
    almacen.put("abc", io.BytesIO(b"hola"), 4)
    assert almacen.exists("abc")
    assert almacen.open("abc").read() == b"hola"
    almacen.put("abc", io.BytesIO(b"hola"), 4)
    assert almacen.open("abc").read() == b"hola"


def comprobar_finding_store(almacen):
    hallazgo = Finding("amenaza", Severity.ALTA, 0.9, EvidenceRef("abc", "linea 3"))
    assert almacen.list("c1") == []
    almacen.add("c1", [hallazgo])
    assert almacen.list("c1") == [hallazgo]
    assert almacen.list("c2") == []


def comprobar_analyzer(analizador, path):
    hallazgos = analizador.analyze(path)
    assert isinstance(hallazgos, list)
    for hallazgo in hallazgos:
        assert isinstance(hallazgo, Finding)
        assert hallazgo.evidence.object_sha256
        assert hallazgo.evidence.position
        assert 0 <= hallazgo.confidence <= 1


def comprobar_resource_reader(lector, esperado):
    assert isinstance(lector, ResourceReader)
    uso = lector.read()
    assert isinstance(uso, ResourceUsage)
    assert uso == esperado
    assert isinstance(uso.worker_id, str) and uso.worker_id
    assert type(uso.memory_current) is int and uso.memory_current >= 0
    assert type(uso.memory_max) is int and uso.memory_max > 0
    assert uso.memory_available == max(uso.memory_max - uso.memory_current, 0)


def comprobar_alert_publisher(publicador):
    assert isinstance(publicador, AlertPublisher)
    assert publicador.publish("incidencia_alta", "c1", '{"categoria": "amenaza"}') is None
    assert publicador.publish("caso_finalizado", "c1", '{"estado": "completed"}') is None


def comprobar_alert_reader(publicador, lector, reloj):
    """`publicador` y `lector` comparten el mismo canal; `reloj` es el que usa el publicador."""
    from src.application.ports import AlertReader  # puerto nuevo de F-14 parte 2

    assert isinstance(lector, AlertReader)
    assert lector.recent(10) == []
    inicio = reloj.now()
    publicador.publish("incidencia_alta", "c1", '{"categoria": "amenaza"}')
    reloj.advance(timedelta(minutes=5))
    publicador.publish("caso_finalizado", "c2", '{"estado": "completed"}')
    ultima, primera = lector.recent(10)
    assert isinstance(ultima, StoredAlert) and isinstance(primera, StoredAlert)
    assert (primera.kind, primera.case_id, primera.detail) == ("incidencia_alta", "c1", '{"categoria": "amenaza"}')
    assert (ultima.kind, ultima.case_id, ultima.detail) == ("caso_finalizado", "c2", '{"estado": "completed"}')
    assert primera.emitted_at == inicio
    assert ultima.emitted_at == inicio + timedelta(minutes=5)
    assert primera.emitted_at.utcoffset() == timedelta(0)
    assert isinstance(primera.alert_id, str) and primera.alert_id
    assert primera.alert_id != ultima.alert_id
    assert lector.recent(1) == [ultima]


def comprobar_case_catalog(crear):
    """`crear(caso)` devuelve un catálogo que contiene solo ese `CaseInfo`."""
    from src.domain.consolidated_report import CaseInfo, CaseSource

    instante = datetime(2026, 11, 3, tzinfo=timezone.utc)
    caso = CaseInfo("c1", "completed", instante, instante, (CaseSource("a" * 64, "a.txt", "texto", "completed"),))
    catalogo = crear(caso)
    assert catalogo.case("c1") == caso
    assert catalogo.case("inexistente") is None


def comprobar_token_verifier(verificador, token_valido, identidad, tokens_invalidos):
    from src.application.ports import Identity, InvalidToken, TokenVerifier

    assert isinstance(verificador, TokenVerifier)
    obtenida = verificador.verify(token_valido)
    assert isinstance(obtenida, Identity)
    assert obtenida == identidad
    for token in (*tokens_invalidos, ""):
        with pytest.raises(InvalidToken):
            verificador.verify(token)
