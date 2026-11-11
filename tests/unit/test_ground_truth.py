import pytest

from src.domain.finding import EvidenceRef, Finding, Severity
from src.domain.ground_truth import (
    CategoryScore,
    Comparison,
    GroundTruthItem,
    ObservedItem,
    compare,
    observed_from_findings,
)

SHA = "a" * 64


def esperado(item_id, *categorias):
    return GroundTruthItem(item_id, frozenset(categorias))


def obtenido(item_id, *categorias):
    return ObservedItem(item_id, frozenset(categorias))


def hallazgo(categoria):
    return Finding(categoria, Severity.ALTA, 0.9, EvidenceRef(SHA, "pos 1"))


def puntaje(comparacion, categoria):
    return next(s for s in comparacion.scores if s.category == categoria)


def cuatro_elementos():
    verdad = [esperado("a", "arma"), esperado("b", "arma"), esperado("c"), esperado("d", "odio")]
    salidas = [obtenido("a", "arma"), obtenido("b"), obtenido("c", "arma"), obtenido("d", "odio")]
    return verdad, salidas


def test_comparador_reporta_aciertos_y_errores():
    comparacion = compare(*cuatro_elementos())

    arma = puntaje(comparacion, "arma")
    assert (arma.tp, arma.fp, arma.fn, arma.tn) == (1, 1, 1, 1)
    assert (arma.hits, arma.errors) == (2, 2)
    odio = puntaje(comparacion, "odio")
    assert (odio.tp, odio.fp, odio.fn, odio.tn) == (1, 0, 0, 3)
    assert (odio.hits, odio.errors) == (4, 0)
    assert arma.precision == 0.5
    assert arma.recall == 0.5
    assert odio.precision == 1.0
    assert odio.recall == 1.0


def test_comparador_ordena_las_categorias_alfabeticamente():
    verdad = [esperado("a", "odio", "arma")]
    salidas = [obtenido("a", "violencia")]

    comparacion = compare(verdad, salidas)

    assert [s.category for s in comparacion.scores] == ["arma", "odio", "violencia"]


def test_comparador_incluye_categorias_sin_ocurrencias():
    verdad = [esperado("a", "arma"), esperado("b")]
    salidas = [obtenido("a", "arma"), obtenido("b")]

    comparacion = compare(verdad, salidas, categories=["arma", "odio"])

    assert puntaje(comparacion, "odio") == CategoryScore("odio", 0, 0, 0, 2)


def test_comparador_precision_y_exhaustividad_indefinidas_son_none():
    verdad = [esperado("a", "arma"), esperado("b")]
    salidas = [obtenido("a"), obtenido("b", "odio")]

    comparacion = compare(verdad, salidas)

    arma = puntaje(comparacion, "arma")
    assert arma.precision is None
    assert arma.recall == 0.0
    odio = puntaje(comparacion, "odio")
    assert odio.precision == 0.0
    assert odio.recall is None
    vacia = compare(verdad, salidas, categories=["fraude"])
    assert puntaje(vacia, "fraude").precision is None
    assert puntaje(vacia, "fraude").recall is None


def test_comparador_exactitud_global():
    verdad, salidas = cuatro_elementos()

    comparacion = compare(verdad, salidas)

    assert isinstance(comparacion, Comparison)
    assert comparacion.total == 4
    assert comparacion.accuracy == 0.5
    invertido = compare(list(reversed(verdad)), salidas)
    assert invertido == comparacion


def test_comparador_exactitud_perfecta_cuando_todo_coincide():
    verdad = [esperado("a", "arma"), esperado("b")]
    salidas = [obtenido("b"), obtenido("a", "arma")]

    assert compare(verdad, salidas).accuracy == 1.0


@pytest.mark.parametrize(
    "verdad, salidas",
    [
        ([], []),
        ([esperado("a"), esperado("a")], [obtenido("a")]),
        ([esperado("a")], [obtenido("a"), obtenido("a")]),
        ([esperado("a"), esperado("b")], [obtenido("a")]),
        ([esperado("a")], [obtenido("a"), obtenido("b")]),
    ],
    ids=["vacia", "etiqueta repetida", "salida repetida", "sin salida", "sin etiqueta"],
)
def test_comparador_rechaza_muestra_vacia_repetidos_y_salidas_faltantes(verdad, salidas):
    with pytest.raises(ValueError):
        compare(verdad, salidas)


def test_salidas_desde_hallazgos_usan_la_categoria():
    hallazgos = [hallazgo("arma"), hallazgo("odio"), hallazgo("arma")]

    assert observed_from_findings("a", hallazgos) == obtenido("a", "arma", "odio")
    assert observed_from_findings("b", []) == obtenido("b")
