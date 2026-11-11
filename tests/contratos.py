"""Pruebas de conformidad: todo adaptador real de un puerto debe pasarlas, igual que su doble."""
import io
import json
from datetime import datetime, timezone

import pytest

from src.application.ports import ResourceReader
from src.domain.custody_chain import GENESIS_HASH, verify_chain
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


def comprobar_custody_log(log, leer, llave):
    """`leer()` devuelve `(líneas, ancla)` tal como las dejó `log`; `llave` es la que sella."""
    assert leer()[0] == []
    ingreso, resultado = "a" * 64, "b" * 64
    log.record(ingreso, "ingreso", ingreso, "recepcion")
    log.record(ingreso, "transcribir", resultado, "worker-1")
    lineas, ancla = leer()
    assert verify_chain(lineas, llave, ancla) == []
    primera, segunda = (json.loads(linea) for linea in lineas)
    assert (primera["seq"], segunda["seq"]) == (0, 1)
    assert primera["prev_hash"] == GENESIS_HASH
    assert segunda["prev_hash"] == primera["entry_hash"]
    assert (primera["evidence_sha256"], primera["operation"], primera["result_sha256"], primera["actor"]) == (
        ingreso, "ingreso", ingreso, "recepcion")
    assert (segunda["evidence_sha256"], segunda["operation"], segunda["result_sha256"], segunda["actor"]) == (
        ingreso, "transcribir", resultado, "worker-1")
    assert (ancla.seq, ancla.entry_hash) == (1, segunda["entry_hash"])
    with pytest.raises(ValueError):
        log.record(None, "ingreso", ingreso, "recepcion")
    assert leer() == (lineas, ancla)
