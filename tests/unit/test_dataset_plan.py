from dataclasses import replace

import pytest

from src.domain.dataset_plan import DatasetParams, check_minimums, plan_dataset

MIB = 1024 * 1024
TIPOS_PESADOS = {"texto", "imagen", "audio"}


def _plan(seed: int = 7, **cambios):
    return plan_dataset(seed, replace(DatasetParams(), **cambios))


def _por_heterogeneo(plan, nivel: str):
    return [caso for caso in plan.cases if caso.heterogeneo == nivel]


def test_generador_cumple_minimos_de_b3():
    plan = _plan()

    assert len(plan.cases) >= 40
    assert len(_por_heterogeneo(plan, "liviano")) + len(_por_heterogeneo(plan, "pesado")) >= 10
    assert sum(caso.messages for caso in plan.cases) >= 20_000
    assert sum(caso.images for caso in plan.cases) >= 300
    assert sum(caso.audios for caso in plan.cases) >= 150
    assert sum(1 for caso in plan.cases if caso.heavy_bytes >= 200 * MIB) >= 5
    assert check_minimums(plan) == []


def test_plan_tiene_cinco_heterogeneos_livianos_y_cinco_pesados():
    plan = _plan()
    livianos = _por_heterogeneo(plan, "liviano")
    pesados = _por_heterogeneo(plan, "pesado")

    assert len(livianos) == 5
    assert len(pesados) == 5
    for caso in pesados:
        assert caso.heavy_bytes >= 200 * MIB
        assert TIPOS_PESADOS <= set(caso.kinds)
        assert {"video", "documento"} & set(caso.kinds)
    for caso in livianos:
        assert caso.heavy_bytes == 0
        assert {"texto", "imagen", "audio", "documento"} <= set(caso.kinds)


def test_los_casos_no_heterogeneos_no_son_pesados():
    plan = _plan()

    assert all(caso.heavy_bytes == 0 for caso in _por_heterogeneo(plan, "no"))
    assert len({caso.name for caso in plan.cases}) == len(plan.cases)


def test_misma_semilla_produce_el_mismo_plan():
    assert _plan(seed=11) == _plan(seed=11)
    assert _plan(seed=11) != _plan(seed=12)


def test_plan_declara_proporcion_positiva_y_duraciones_distintas():
    plan = _plan()

    assert plan.image_positive_ratio
    assert all(0.0 < proporcion < 1.0 for proporcion in plan.image_positive_ratio.values())
    assert len(set(plan.audio_durations)) > 1
    assert len(plan.audio_durations) == sum(caso.audios for caso in plan.cases)
    assert all(segundos > 0 for segundos in plan.audio_durations)


@pytest.mark.parametrize(
    "cambios, palabra",
    [
        ({"cases": 39}, "casos"),
        ({"light_heterogeneous": 4}, "heterogeneos"),
        ({"heavy_heterogeneous": 4}, "pesados"),
        ({"messages": 19_999}, "mensajes"),
        ({"images": 299}, "imagenes"),
        ({"audios": 149}, "audios"),
        ({"heavy_bytes": 200 * MIB - 1}, "200"),
    ],
)
def test_plan_bajo_el_minimo_se_reporta(cambios, palabra):
    problemas = check_minimums(_plan(**cambios))

    assert any(palabra in problema for problema in problemas)


def test_plan_bajo_varios_minimos_los_reporta_todos():
    problemas = check_minimums(_plan(messages=1, images=1, audios=1))

    assert len(problemas) >= 3
