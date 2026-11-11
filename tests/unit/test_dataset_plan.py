from dataclasses import replace

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.domain.dataset_plan import (
    AUDIO_SECONDS_RANGE,
    DatasetParams,
    DatasetPlan,
    check_minimums,
    plan_dataset,
)

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


SEMILLAS = [0, 1, 7, 99, -1, 2**63, -(2**70), 2**200]


@pytest.mark.parametrize("semilla", SEMILLAS)
def test_totales_del_plan_son_exactos_y_nombres_unicos(semilla):
    plan = _plan(seed=semilla)

    assert sum(caso.messages for caso in plan.cases) == 20_000
    assert sum(caso.images for caso in plan.cases) == 300
    assert sum(caso.audios for caso in plan.cases) == 150
    assert len(plan.audio_durations) == 150
    assert len({caso.name for caso in plan.cases}) == len(plan.cases) == 40
    assert check_minimums(plan) == []


@pytest.mark.parametrize("semilla", SEMILLAS)
def test_totales_exactos_con_parametros_no_multiplos(semilla):
    plan = _plan(seed=semilla, messages=20_003, images=301, audios=151)

    assert sum(caso.messages for caso in plan.cases) == 20_003
    assert sum(caso.images for caso in plan.cases) == 301
    assert sum(caso.audios for caso in plan.cases) == 151
    assert len(plan.audio_durations) == 151


def test_cada_caso_con_un_tipo_recibe_conteo_de_ese_tipo():
    plan = _plan()

    for caso in plan.cases:
        assert (caso.messages > 0) == ("texto" in caso.kinds)
        assert (caso.images > 0) == ("imagen" in caso.kinds)
        assert (caso.audios > 0) == ("audio" in caso.kinds)


def test_duraciones_de_audio_quedan_en_el_rango_declarado():
    bajo, alto = AUDIO_SECONDS_RANGE
    for semilla in SEMILLAS:
        assert all(bajo <= s <= alto for s in _plan(seed=semilla).audio_durations)


def test_la_semilla_cambia_el_contenido_y_no_solo_su_campo():
    assert _plan(seed=1).audio_durations != _plan(seed=2).audio_durations
    assert _plan(seed=1).image_positive_ratio != _plan(seed=2).image_positive_ratio


def test_plan_identico_entre_procesos_con_distinto_hashseed():
    raiz = Path(__file__).resolve().parents[2]
    codigo = (
        "from src.domain.dataset_plan import DatasetParams, plan_dataset;"
        "print(repr(plan_dataset(5, DatasetParams())))"
    )
    salidas = {
        subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=raiz,
            env={**os.environ, "PYTHONHASHSEED": hashseed, "PYTHONPATH": str(raiz)},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for hashseed in ("1", "2", "random")
    }

    assert len(salidas) == 1
    assert repr(plan_dataset(5, DatasetParams())) + "\n" in salidas


def test_plan_vacio_incumple_los_siete_minimos():
    problemas = check_minimums(DatasetPlan(seed=0, cases=(), image_positive_ratio={}, audio_durations=()))

    assert len(problemas) == 7
    assert all(" de al menos " in problema for problema in problemas)


def test_params_en_cero_producen_conteos_cero_y_se_reportan():
    plan = _plan(messages=0, images=0, audios=0)

    assert plan.audio_durations == ()
    assert sum(caso.messages + caso.images + caso.audios for caso in plan.cases) == 0
    assert len(check_minimums(plan)) == 3


def test_casos_del_plan_igualan_el_parametro_cases():
    assert len(_plan(cases=3).cases) == 3


def test_total_de_audios_se_conserva_con_pocos_casos_sin_heterogeneos():
    plan = _plan(cases=1, light_heterogeneous=0, heavy_heterogeneous=0)

    assert sum(caso.audios for caso in plan.cases) == 150


@pytest.mark.parametrize("cambios", [{"messages": -5}, {"images": -1}, {"audios": -1}, {"heavy_bytes": -1}])
def test_parametros_negativos_se_rechazan(cambios):
    with pytest.raises(ValueError):
        _plan(**cambios)
