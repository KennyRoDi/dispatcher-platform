"""Pruebas de conformidad: todo adaptador real de un puerto debe pasarlas, igual que su doble."""
import io
from datetime import datetime, timezone

import pytest

from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.priority import Priority
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


def comprobar_chunk_staging(staging):
    """`staging` empieza vacío; `load_manifest` de una subida inexistente lanza KeyError."""
    with pytest.raises(KeyError):
        staging.load_manifest("u1")
    staging.save_manifest("u1", {"sha256": "abc", "size": 6})
    assert staging.load_manifest("u1") == {"sha256": "abc", "size": 6}
    assert staging.received("u1") == set()
    staging.put_chunk("u1", 1, b"def")
    staging.put_chunk("u1", 0, b"abc")
    staging.put_chunk("u1", 0, b"abc")
    assert staging.received("u1") == {0, 1}
    with staging.open_chunk("u1", 1) as chunk:
        assert chunk.read() == b"def"
    staging.discard("u1")
    with pytest.raises(KeyError):
        staging.load_manifest("u1")
    with pytest.raises(KeyError):
        staging.put_chunk("u1", 0, b"abc")
    assert staging.received("u1") == set()
