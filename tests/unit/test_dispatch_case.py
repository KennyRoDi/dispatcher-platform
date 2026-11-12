import logging
from datetime import datetime, timezone

import pytest

from src.application.dispatch_case import DispatchCase
from src.domain.decomposition import CaseSource, SourceKind
from src.domain.priority import Priority
from src.domain.subtask import ContentKind, QueueFull
from tests.dobles import FakeClock, FakeWorkQueue

TEXTO = CaseSource("a" * 64, "chat.txt", SourceKind.TEXT)
IMAGEN = CaseSource("b" * 64, "foto.png", SourceKind.IMAGE)
AUDIO = CaseSource("c" * 64, "nota.mp3", SourceKind.AUDIO)
VIDEO = CaseSource("d" * 64, "clip.mp4", SourceKind.VIDEO)
COLAS = ("queue:text", "queue:image", "queue:audio")


def test_dispatch_encola_cada_subtarea_en_la_cola_de_su_tipo():
    cola = FakeWorkQueue()
    reloj = FakeClock(datetime(2026, 11, 5, 9, 30, tzinfo=timezone.utc))

    encoladas = DispatchCase(cola, reloj).execute("C-1", [TEXTO, IMAGEN, AUDIO, VIDEO], Priority.ALTA)

    assert [(c, s.source_sha256, s.kind) for c, s in encoladas] == [
        ("queue:text", TEXTO.sha256, ContentKind.TEXT),
        ("queue:image", IMAGEN.sha256, ContentKind.IMAGE),
        ("queue:audio", AUDIO.sha256, ContentKind.AUDIO),
        ("queue:image", VIDEO.sha256, ContentKind.IMAGE),
        ("queue:audio", VIDEO.sha256, ContentKind.AUDIO),
    ]
    for nombre in COLAS:
        assert cola.colas[nombre] == [s for c, s in encoladas if c == nombre]
    assert sum(len(cola.colas[n]) for n in COLAS) == 5
    assert all(s.enqueued_at == reloj.now() for _, s in encoladas)
    assert all(s.case_id == "C-1" and s.priority is Priority.ALTA for _, s in encoladas)


def test_dispatch_con_cola_llena_no_encola_nada():
    cola = FakeWorkQueue(capacidad=1)
    cola.colas["queue:audio"].append("ocupada")

    with pytest.raises(QueueFull):
        DispatchCase(cola, FakeClock()).execute("C-1", [TEXTO, IMAGEN, AUDIO], Priority.MEDIA)

    assert cola.colas["queue:text"] == []
    assert cola.colas["queue:image"] == []
    assert cola.colas["queue:audio"] == ["ocupada"]


def test_dispatch_registra_log_de_routing(caplog):
    cola = FakeWorkQueue()

    with caplog.at_level(logging.INFO):
        encoladas = DispatchCase(cola, FakeClock()).execute("C-1", [TEXTO, VIDEO], Priority.BAJA)

    lineas = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO and r.getMessage().startswith("routing ")]
    assert lineas == [
        f"routing case=C-1 subtask={s.id} kind={s.kind.value} source={s.source_sha256} queue={c}"
        for c, s in encoladas
    ]
    assert len(lineas) == 3
