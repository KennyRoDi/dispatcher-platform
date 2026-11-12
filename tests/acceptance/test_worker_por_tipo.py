import pytest

from src.application.dispatch_case import DispatchCase
from src.domain.decomposition import CaseSource, SourceKind
from src.domain.priority import Priority
from src.domain.subtask import ContentKind
from tests.dobles import FakeClock, FakeWorkQueue

pytestmark = pytest.mark.acceptance

COLA_POR_TIPO = {
    ContentKind.TEXT: "queue:text",
    ContentKind.IMAGE: "queue:image",
    ContentKind.AUDIO: "queue:audio",
}


def consumir_todo(cola, nombre_cola, worker_id):
    tomadas = []
    while (subtarea := cola.take(nombre_cola, worker_id, timeout=0)) is not None:
        tomadas.append(subtarea)
    return tomadas


def test_worker_de_cada_tipo_consume_solo_lo_suyo():
    cola = FakeWorkQueue()
    fuentes = [
        CaseSource("a" * 64, "chat.txt", SourceKind.TEXT),
        CaseSource("b" * 64, "foto.png", SourceKind.IMAGE),
        CaseSource("c" * 64, "nota.mp3", SourceKind.AUDIO),
        CaseSource("d" * 64, "clip.mp4", SourceKind.VIDEO),
    ]
    DispatchCase(cola, FakeClock()).execute("C-1", fuentes, Priority.ALTA)

    consumidas = {
        tipo: consumir_todo(cola, nombre, f"worker-{tipo.value}") for tipo, nombre in COLA_POR_TIPO.items()
    }

    for tipo, subtareas in consumidas.items():
        assert subtareas and all(s.kind is tipo for s in subtareas)
    assert {s.source_sha256 for s in consumidas[ContentKind.AUDIO]} == {"c" * 64, "d" * 64}
    assert {s.source_sha256 for s in consumidas[ContentKind.IMAGE]} == {"b" * 64, "d" * 64}
    assert [s.source_sha256 for s in consumidas[ContentKind.TEXT]] == ["a" * 64]
    assert sum(len(s) for s in consumidas.values()) == 5
    assert all(not cola.colas[nombre] for nombre in COLA_POR_TIPO.values())
