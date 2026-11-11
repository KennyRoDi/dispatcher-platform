from datetime import datetime, timezone

import pytest

from src.adapters.routing_config import RUTA_POR_DEFECTO, cargar_tabla
from src.application.ports import RoutingPolicy
from src.domain.priority import Priority
from src.domain.routing import NoLiveNodeClass
from src.domain.subtask import ContentKind, Subtask
from tests.dobles import FakeRoutingPolicy

pytestmark = pytest.mark.integration


def subtarea(kind):
    return Subtask(
        id="s1",
        case_id="c1",
        kind=kind,
        source_sha256="0" * 64,
        priority=Priority.from_name("alta"),
        enqueued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_routing_con_dos_clases_de_worker():
    politica = cargar_tabla(RUTA_POR_DEFECTO)
    assert isinstance(politica, RoutingPolicy)
    assert isinstance(FakeRoutingPolicy(), RoutingPolicy)
    vivas = {"cpu", "gpu"}

    destino = {k: politica.route(subtarea(k), sorted(vivas)) for k in ContentKind}
    assert set(destino.values()) <= vivas
    assert destino[ContentKind.TEXT] == "cpu"

    vivas.discard(destino[ContentKind.AUDIO])
    alternativa = politica.route(subtarea(ContentKind.AUDIO), sorted(vivas))
    assert alternativa in vivas

    vivas.clear()
    with pytest.raises(NoLiveNodeClass):
        politica.route(subtarea(ContentKind.AUDIO), [])
