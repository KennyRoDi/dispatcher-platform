"""Pruebas de conformidad: todo adaptador real de un puerto debe pasarlas, igual que su doble."""
import io
from datetime import datetime, timezone

import pytest

from src.application.ports import KeyUnavailable, ResourceReader
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


def comprobar_key_provider(proveedor, kek):
    """`proveedor` tiene `kek` disponible: la devuelve como 32 bytes, igual en cada llamada."""
    obtenida = proveedor.kek()
    assert isinstance(obtenida, bytes)
    assert len(obtenida) == 32
    assert obtenida == kek
    assert proveedor.kek() == obtenida


def comprobar_key_provider_sin_kek(proveedor):
    """`proveedor` no tiene `kek`: falla cerrado con `KeyUnavailable`, nunca con otro valor."""
    with pytest.raises(KeyUnavailable):
        proveedor.kek()
