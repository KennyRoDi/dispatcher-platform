from datetime import datetime, timezone
from importlib import import_module

import pytest

from src.application.ports import RoutingPolicy
from src.domain.priority import Priority
from src.domain.subtask import ContentKind, Subtask


def dominio():
    return import_module("src.domain.routing")


def adaptador():
    return import_module("src.adapters.routing_config")


def subtarea(kind):
    return Subtask(
        id="s1",
        case_id="c1",
        kind=kind,
        source_sha256="0" * 64,
        priority=Priority.from_name("high"),
        enqueued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


REGLAS = {
    ContentKind.TEXT: ("cpu",),
    ContentKind.IMAGE: ("cpu",),
    ContentKind.AUDIO: ("gpu", "cpu"),
}


def tabla():
    return dominio().RoutingTable(REGLAS)


def test_tabla_elige_clase_de_nodo():
    t = tabla()
    assert t.route(subtarea(ContentKind.AUDIO), ["cpu", "gpu"]) == "gpu"
    assert t.route(subtarea(ContentKind.TEXT), ["gpu", "cpu"]) == "cpu"


def test_sin_nodo_preferido_usa_alternativa():
    assert tabla().route(subtarea(ContentKind.AUDIO), ["cpu"]) == "cpu"


def test_sin_ninguna_clase_activa_falla_explicito():
    with pytest.raises(dominio().NoLiveNodeClass) as error:
        tabla().route(subtarea(ContentKind.AUDIO), ["arm"])
    assert issubclass(dominio().NoLiveNodeClass, ValueError)
    assert "audio" in str(error.value) and "gpu" in str(error.value)


def test_sin_clases_vivas_falla_explicito():
    with pytest.raises(dominio().NoLiveNodeClass):
        tabla().route(subtarea(ContentKind.TEXT), [])


def test_route_no_muta_la_subtarea():
    s = subtarea(ContentKind.AUDIO)
    tabla().route(s, ["gpu"])
    assert s.node_class is None


@pytest.mark.parametrize(
    "reglas",
    [
        {},
        {**REGLAS, ContentKind.AUDIO: ()},
        {**REGLAS, ContentKind.AUDIO: ("gpu", "gpu")},
        {**REGLAS, ContentKind.AUDIO: ("gpu", "")},
        {**REGLAS, "video": ("cpu",)},
    ],
    ids=["vacia", "lista-vacia", "duplicados", "clase-vacia", "tipo-desconocido"],
)
def test_tabla_invalida_falla_al_arrancar(reglas):
    with pytest.raises(ValueError):
        dominio().RoutingTable(reglas)


def test_routing_table_cumple_el_puerto():
    assert isinstance(tabla(), RoutingPolicy)


TOML_VALIDO = """
[rutas]
text = ["cpu"]
image = ["cpu"]
audio = ["gpu", "cpu"]

[evidencia]
text = "Medición pendiente"
image = "Medición pendiente"
audio = "Medición pendiente: docs/modulo-M5-computo.md"
"""


def escribir(tmp_path, contenido):
    ruta = tmp_path / "routing.toml"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_config_carga_la_tabla(tmp_path):
    t = adaptador().cargar_tabla(escribir(tmp_path, TOML_VALIDO))
    assert t.route(subtarea(ContentKind.AUDIO), ["cpu"]) == "cpu"
    assert t.route(subtarea(ContentKind.AUDIO), ["cpu", "gpu"]) == "gpu"


@pytest.mark.parametrize(
    "contenido",
    [
        "",
        '[rutas]\ntext = ["cpu"]\nimage = ["cpu"]\n',
        '[rutas]\ntext = ["cpu"]\nimage = ["cpu"]\naudio = []\n',
        '[rutas]\ntext = ["cpu"]\nimage = ["cpu"]\naudio = ["cpu"]\nvideo = ["cpu"]\n',
    ],
    ids=["sin-rutas", "tipo-sin-ruta", "lista-vacia", "tipo-desconocido"],
)
def test_config_invalida_falla_al_arrancar(tmp_path, contenido):
    with pytest.raises(ValueError):
        adaptador().cargar_tabla(escribir(tmp_path, contenido))


def test_config_del_repositorio_es_valida():
    t = adaptador().cargar_tabla(adaptador().RUTA_POR_DEFECTO)
    for kind in ContentKind:
        assert t.route(subtarea(kind), ["cpu", "gpu"]) in {"cpu", "gpu"}
